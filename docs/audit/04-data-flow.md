# 04. Data Flow Review

This report models the three core workflows in QMA (Report Purchase, Report Unlock, and Provider Payout), based on direct source code inspection of the Python backend and `arc_gateway/server.ts`.

## 1. Report Purchase Flow
**Description:** The purchase flow utilizes two-leg revenue splitting via HTTP 402 protocols.

```mermaid
sequenceDiagram
    participant Client
    participant Backend as QMA Backend (Python)
    participant ArcGateway as Arc Gateway (Node.js)
    participant Circle as Circle API (Smart Contract)

    Client->>Backend: POST /api/v1/payment/invoice/create
    Backend->>Backend: allocate_split_legs_raw() (Split calculations)
    Backend->>Backend: Sign HMAC (SPLIT_LEG_URL_SECRET) into pay_url
    Backend-->>Client: Return Invoice with split legs (pay_url)
    
    Client->>ArcGateway: GET pay_url (e.g., /qma-access/split-leg?leg_id=...)
    ArcGateway-->>Client: HTTP 402 Payment Required (Recipient wallet details)
    
    Client->>Client: Sign transaction with wallet
    Client->>ArcGateway: GET pay_url (With payment-signature header)
    
    ArcGateway->>Backend: POST /api/internal/.../reserve (Lock leg)
    ArcGateway->>Circle: POST /v1/transfer (facilitator.settle)
    Circle-->>ArcGateway: Return settlementId
    
    ArcGateway->>Circle: Update status (fetchCircleTransfer)
    ArcGateway->>ArcGateway: Sign HMAC (SPLIT_RECEIPT_SECRET)
    ArcGateway->>Backend: POST /api/internal/.../record (With receipt)
    Backend->>Backend: Verify signature & Update invoice to "paid"
    ArcGateway-->>Client: HTTP 200 OK (Payment successful)
```

**Risk & Security Analysis:**
- Communication between `arc_gateway` and the backend is authenticated via HMAC signatures (`SPLIT_RECEIPT_SECRET`), preventing malicious mock settlement injections into `/api/internal/.../record`.
- USDC flows directly into creator wallets via Circle Gateway settlement, removing custodial treasury risks on the primary sales path.

## 2. Report Unlock Flow
**Description:** Once an invoice is paid, clients redeem short-lived access tokens to unlock reports.

```mermaid
sequenceDiagram
    participant Client
    participant Backend as QMA Backend (Python)
    participant Provider as Provider (AI Model)
    participant Database as Local JSON / Supabase Storage

    Client->>Backend: POST /api/v1/providers/{id}/full-report (With Access Token)
    Backend->>Backend: verify_access_token() (Verify signature & expiry)
    Backend->>Backend: Verify invoice.status == 'paid'
    
    Backend->>Provider: provider.deliver() (Generate intelligence)
    Provider-->>Backend: Report result
    
    Backend->>Database: create_wallet_report_snapshot() (Record Entitlement)
    Backend-->>Client: Return Report JSON
```

**Risk Analysis:**
- All primary delivery endpoints (`full-report`, `preview`) enforce strict token verification, returning HTTP 403 on missing or invalid tokens.

## 3. Provider Payout Flow (Creator Claims)
**Description:** Secondary payout mechanism for creators claiming earnings accumulated outside direct-split transactions.

### Data Flow Architecture
1. **Entry Point:** Frontend client submits signed claim request.
2. **API Endpoint:** `POST /api/v1/creators/claim` (in `providers.py`).
3. **Service Layer:** `deps.recover_creator_claim_signer` (verification), `deps.allocate_creator_claim` (ledger deduction), and internal dispatch to `arc_gateway/server.ts` (`POST /api/creator/claim`).
4. **Repository Layer:** `deps.get_creator_claims_db()` and `deps.save_creator_claim_record()`.
5. **Database Entities:** Records tracking `claim_id`, `claimant_address`, `amount_usdc`, and `status`.
6. **State Transitions:** `requested` → `paid` (success) or `failed` (failure).
7. **Validation Points:**
   - Cryptographic signature matches `claimant_address`.
   - `requested_amount <= total_available` (`earned_final` minus `paid` and `pending` claims).
   - Internal communication secured via `x-qma-internal-secret`.

```mermaid
sequenceDiagram
    participant Creator as Creator Client
    participant Backend as QMA Backend (Python)
    participant ArcGateway as Arc Gateway (Node.js)
    participant Blockchain as Arc Testnet (Smart Contract)

    Creator->>Backend: POST /api/v1/creators/claim (With Signature)
    Backend->>Backend: recover_creator_claim_signer() (Verify wallet signature)
    Backend->>Backend: Check balance & Assign claim_id
    Backend->>Backend: Record claim in "requested" state
    
    Backend->>ArcGateway: POST /api/creator/claim (With x-qma-internal-secret)
    ArcGateway->>ArcGateway: Load CLAIM_PAYOUT_PRIVATE_KEY
    ArcGateway->>Blockchain: ERC20.transfer(recipient, amount)
    Blockchain-->>ArcGateway: Return Transaction Hash (txHash)
    
    ArcGateway-->>Backend: HTTP 200 (txHash, status: success)
    Backend->>Backend: Update status = "paid"
    Backend-->>Creator: HTTP 200 (Claim Successful)
```

**Resilience Analysis:**
- Network timeout handling between backend dispatch and gateway transfers requires transactional idempotency keys to prevent accidental double-submission or state drift.
