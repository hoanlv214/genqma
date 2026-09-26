# Process Log — Phase 4: Data Flow Review

## Declared Scope
- `backend/app/main.py`
- `backend/app/services/invoice_builder.py`
- `backend/app/services/x402_gateway.py`
- `backend/app/services/payment_state_machine.py`
- `arc_gateway/server.ts`
- Related files governing payment settlement, report delivery, and provider claims.

## Sequential Execution Steps

### Step 1: Inspection of `arc_gateway/server.ts`
- Tool used: `list_dir`, `view_file`
- Target: `arc_gateway/server.ts`
- Findings: Complete review across lines 1 to 950. Analyzed 2 primary endpoints:
  - `GET /qma-access/split-leg`: Ingests payment proofs (x402 batching), invokes Circle Gateway `facilitator.settle`, and callbacks to backend `/api/internal/.../record` to record leg completion.
  - `POST /api/creator/claim`: Performs on-chain ERC20 USDC transfers to creator wallets using the configured hot wallet key.

### Step 2: Invoice Creation & Validation Flow (Report Purchase)
- Target: `backend/app/api/v1/endpoints/payments.py` (`create_invoice`), `backend/app/services/invoice_builder.py` (`allocate_split_legs_raw`).
- Findings: Invoices generate dynamic split legs, each containing an HMAC-signed `pay_url` pointing to `arc_gateway`.

### Step 3: Report Delivery & Unlock Flow (Report Unlock)
- Target: `backend/app/api/v1/endpoints/reports.py` (`provider_full_report`), `backend/app/main.py` (`run_paid_provider_report`).
- Findings: Confirmed access token verification → Provider report generation → Entitlement snapshot creation → Client response.

### Step 4: Creator Claim & Payout Flow (Provider Payout)
- Target: `backend/app/api/v1/endpoints/providers.py` (lines 270-397).
- Findings: Creator signs claim message → Backend validates wallet and balance → Records claim in `creator_claims_db` → Dispatches `POST /api/creator/claim` to `arc_gateway` with `x-qma-internal-secret`.

### Step 5: Payout State Reconciliation Review
- Traced backend balance calculation:
  - `backend/app/main.py` (L704-740): `allocate_creator_claim`.
  - `backend/app/services/providers_meta.py` (L231-280): `build_provider_stats` calculating `claimable` balance.
  - `backend/app/services/creator_claims.py` (L167-189): `creator_claim_amounts` logic.

## Directly Inspected Files
- `arc_gateway/server.ts` (lines 1-950)
- `backend/app/api/v1/endpoints/providers.py` (lines 270-397)
- `backend/app/main.py` (lines 704-740, 1272-1300)
- `backend/app/services/providers_meta.py` (lines 231-280)
- `backend/app/services/creator_claims.py` (lines 167-189)
- `backend/app/core/state.py` (lines 144-166)

## Search & Grep Queries
| Query | Results | Purpose |
|---|---|---|
| `api/v1/creators/claim` | 1 match | Locate creator claim route |
| `split-leg` in `backend/app/services` | 2 matches | Locate invoice `pay_url` generator |
| `(?i)retry\|idempotent\|webhook` in `arc_gateway/server.ts` | 2 matches | Inspect retry mechanics |
