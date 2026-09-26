# 03. Authorization Review

This report audits authentication, authorization schemes, and access control across all QMA endpoints.

## 1. Missing Authorization & Access Control Analysis
Summary of endpoint authentication policies:

| Route | Auth Dependency | Classification | Rationale |
|---|---|---|---|
| `GET /api/v1/platform/*` | None | Public | Platform statistics designed for public visibility. Sensitive fields stripped via `deps.compact_payment_event`. |
| `POST /api/v1/payment/withdraw` | Cryptographic Signature in Payload | Public | Authenticated via cryptographic signature verification over `WithdrawRequest` payload (EIP-712 style) inside `deps.submit_withdraw()`. |
| `POST /api/v1/creators/apply` | None | Public | Open onboarding for creators. |
| `POST /api/v1/creators/claim` | Cryptographic Signature in Payload | Public | Authenticated via `recover_creator_claim_signer` over the claim payload. |
| `POST /api/v1/chat` | Missing Access Token (IDOR) | Defect | **Critical Finding:** See Section 1.1. |

### 1.1 Missing Access Token on Chat Route (IDOR Vulnerability)
**Evidence (`chat.py:17-132`):**
```python
    @migrated.post(
        "/api/v1/chat",
        response_model=ChatResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(402, 404, 429, 500),
    )
    def handle_chat_request(payload: ChatRequest):
        """Answers interactive user queries regarding a paid report."""
        invoice_id = payload.invoice_id
        user_message = payload.message

        deps.reload_persistent_state()

        invoices_db = deps.get_invoices_db()
        paid_reports = deps.get_paid_reports()
        invoice = invoices_db.get(invoice_id)
        report_record = None

        if invoice:
            settlement_id = invoice.get("settlement_id")
            for record in paid_reports.values():
                rec_report = record.get("report") or {}
                rec_inv = rec_report.get("invoice") or {}
                if rec_inv.get("invoice_id") == invoice_id or (settlement_id and record.get("settlement_id") == settlement_id):
                    report_record = record
                    break
        else:
            for record in paid_reports.values():
                rec_report = record.get("report") or {}
                rec_inv = rec_report.get("invoice") or {}
                if rec_inv.get("invoice_id") == invoice_id:
                    report_record = record
                    invoice = rec_inv
                    break

        if not invoice or invoice.get("status") != "paid":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="A valid, paid invoice is required to use AI Chat.",
            )

        if not report_record or not report_record.get("report"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report data not found for this invoice. Settle and retrieve the report first.",
            )
```
- **Rationale:** Report retrieval endpoints (`/api/v1/reports/pdf`, `/api/v1/reports/raw`) require `qma_access_token: Optional[str] = Security(...)`. `chat.py` only checked if `invoice_id` had `status == "paid"` without validating that the requester owns the token. This creates an Insecure Direct Object Reference (IDOR) if an `invoice_id` is intercepted or guessed.
- **Severity: High (IDOR)**
- **Recommendation:** Inject `qma_access_token: Optional[str] = Security(qma_access_token_header)` and enforce `deps.hydrate_access_entitlement(invoice_id, token=qma_access_token)`.

### 1.2 Access Token Protection Verification on Reports Routes
**Evidence (`reports.py:47-60`):**
```python
    @migrated.post(
        "/api/v1/providers/{provider_id}/full-report",
        tags=["Reports"],
        response_model=ProviderReportResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(400, 402, 403, 404, 429, 500),
    )
    def provider_full_report(
        provider_id: str,
        query: QueryModel,
        invoice_id: str = Query(...),
        qma_access_token: Optional[str] = Security(qma_access_token_header),
        access_token: Optional[str] = Query(default=None),
    ):
```

**Tracing through Core Logic:**
- `main.py:1272-1280`: Token is forwarded to `authorize_paid_invoice`.
- `main.py:1206-1210`: `token_payload = verify_access_token(token or "")`.
- `payment_signing.py:161-165`: `verify_access_token` raises `HTTPException(403)` on empty or invalid tokens.
- **Conclusion:** `/reports` routes strictly enforce valid cryptographic access tokens.
- **Severity: Low** (Secure).

### 1.3 Wallet Ownership Verification
**Evidence (`wallets.py:293-314`):**
```python
    @migrated.get(
        "/api/v1/wallets/{address}/reports/{entitlement_id}",
...
    def get_wallet_report_detail(
        address: str,
        entitlement_id: str,
        qma_wallet_token: Optional[str] = Security(qma_wallet_token_header),
        wallet_token: Optional[str] = Query(default=None),
    ):
        deps.verify_wallet_profile_token(address, qma_wallet_token or wallet_token or "")
        record = deps.load_paid_report_by_id(address, entitlement_id)
        if not record:
            raise HTTPException(status_code=404, detail="Paid report snapshot not found for this wallet.")
```
- **Rationale:** `verify_wallet_profile_token` enforces wallet-scoped authorization before loading records by `(address, entitlement_id)`.
- **Severity: Low** (Secure).

## 2. Timing Attack Prevention (Internal Secret)
**Evidence (`internal.py:20-25`):**
```python
    def require_internal_gateway_secret(x_qma_internal_secret: str = Security(qma_internal_secret_header)):
        if not deps.arc_gateway_internal_secret:
            raise HTTPException(status_code=503, detail="QMA_ARC_GATEWAY_INTERNAL_SECRET is not configured.")
        if not hmac.compare_digest(str(x_qma_internal_secret or ""), deps.arc_gateway_internal_secret):
            raise HTTPException(status_code=403, detail="Internal gateway secret required.")
        return True
```
- **Rationale:** Secret comparison uses constant-time `hmac.compare_digest()` to eliminate timing side-channels.
- **Severity: Low** (Secure).

## 3. Administrative Privileges (Admin Token Schemes)

### 3.1 Creator Application Review
**Evidence (`providers.py:243-257`):**
```python
    @migrated.post("/api/v1/creators/applications/{application_id}/review", ...)
    def review_creator_application(
        application_id: str,
        req: CreatorReviewRequest,
        x_qma_admin_token: Optional[str] = Security(qma_admin_token_header),
    ):
        """Admin review endpoint for marketplace provider applications."""
        deps.require_admin_token(x_qma_admin_token)
```
- **Rationale:** Administrative endpoints enforce `require_admin_token()` unconditionally.
- **Severity: Low**

### 3.2 Dynamic Scope / Mixed Auth
**Evidence (`providers.py:73-83`):**
```python
    def list_providers(
        include_disabled: bool = Query(default=False),
        x_qma_admin_token: Optional[str] = Security(qma_admin_token_header),
    ):
        if include_disabled:
            deps.require_admin_token(x_qma_admin_token)
```
- **Rationale:** Public clients view enabled providers; administrative parameter flags require admin token credentials.
- **Severity: Low**

### 3.3 Public Configuration Diagnostics
**Evidence (`providers.py:140-147`):**
```python
    def get_admin_public_config():
        """Public hints for showing admin/seller controls in the browser."""
        return {
            "seller_wallet": deps.normalize_address(deps.payment_wallet_address),
            "admin_wallet": deps.normalize_address(deps.admin_wallet_address),
            "admin_token_required": True,
            "admin_token_configured": bool(deps.admin_token),
        }
```
- **Rationale:** Exposes only public wallet addresses and boolean configuration flags without leaking private keys or secrets.
- **Severity: Low**

---
**Summary**: QMA employs robust cryptographic authorization, constant-time comparisons, and role-based segregation.
