# 02. Payment Lifecycle Review

This report analyzes the payment lifecycle, idempotency guarantees, and anti-fraud / race condition defenses within the QMA x402 architecture.

## 1. Settlement Validation (Anti-Fake Payment)
Core logic resides in `backend/app/services/settlement_validation.py` and invocation sites in `main.py`.

### 1.1 Data Origin Validation
**Evidence (`main.py:937-977` - Split Leg Payment Processing):**
```python
937:             has_authoritative_gateway_claims = bool(submitted.payer_address and submitted.gateway_status)
938:             receipt_valid = verify_split_receipt(
939:                 invoice_id=invoice_id, leg_id=leg_id, pay_to=leg.get("pay_to"),
940:                 settled_amount_raw=submitted.amount_raw, settlement_id=submitted.settlement_id,
941:                 receipt=submitted.sidecar_receipt,
942:                 payer_address=submitted.payer_address,
943:                 gateway_status=submitted.gateway_status,
944:             ) if has_authoritative_gateway_claims else verify_split_receipt(
945:                 invoice_id=invoice_id, leg_id=leg_id, pay_to=leg.get("pay_to"),
946:                 settled_amount_raw=submitted.amount_raw, settlement_id=submitted.settlement_id,
947:                 receipt=submitted.sidecar_receipt,
948:             )
949:             if not receipt_valid and has_authoritative_gateway_claims:
950:                 # A legacy relay may include payer/status in its body while
951:                 # still returning a five-field receipt. Keep it on the
952:                 # authoritative Circle-lookup path instead of rejecting it.
953:                 has_authoritative_gateway_claims = False
954:                 receipt_valid = verify_split_receipt(
955:                     invoice_id=invoice_id, leg_id=leg_id, pay_to=leg.get("pay_to"),
956:                     settled_amount_raw=submitted.amount_raw, settlement_id=submitted.settlement_id,
957:                     receipt=submitted.sidecar_receipt,
958:                 )
959:             if not receipt_valid:
960:                 raise HTTPException(status_code=400, detail=f"Invalid sidecar receipt for split leg {leg_id}.")
...
963:             if has_authoritative_gateway_claims:
964:                 # Arc Gateway already fetched and validated this settlement
965:                 # against Circle before signing the sidecar receipt. The HMAC
966:                 # binds payer and status, so avoid repeating the remote GET.
967:                 settlement = {
968:                     "status": submitted.gateway_status,
969:                     "toAddress": leg.get("pay_to"),
970:                     "fromAddress": submitted.payer_address,
971:                     "amount": submitted.amount_raw,
972:                 }
973:             else:
974:                 # Compatibility path for receipts issued before payer/status
975:                 # were included in the signed sidecar proof.
976:                 settlement = fetch_circle_settlement(submitted.settlement_id)
977:             validate_arc_split_leg_payment(invoice, leg, settlement, payer_address=proof.payer_address)
```

**Evidence (`main.py:1053-1054` - Non-Split Legacy Processing):**
```python
1053:         settlement = fetch_circle_settlement(proof.settlement_id)
1054:         validate_arc_payment(invoice, settlement, payer_address=proof.payer_address)
```

- **Rationale:** 
  - Line 937 evaluates `has_authoritative_gateway_claims` from request payloads.
  - Before constructing the `settlement` dictionary at line 967, the entire payload must pass `verify_split_receipt()`.
  - **Fallback behavior (lines 949-958):** Accommodates relays providing 7 fields while signing only the 5 legacy fields. When the 7-field check fails, it degrades `has_authoritative_gateway_claims` to `False` and re-verifies the 5-field HMAC.
  - **Can this fallback be exploited?** No. Downgrading the flag routes execution through the `else` branch (line 973), triggering direct `fetch_circle_settlement()` queries against the Circle Gateway API instead of trusting submitted payloads.
  - Tampering with `submitted.gateway_status` on modern 7-field receipts invalidates HMAC verification at line 960.
- **Severity: Low** (Secure trust-delegation design).
- **Recommendation:** Maintain current cryptographic signature checks.

### 1.2 Currency & Gateway Support Validation
**Evidence (`settlement_validation.py:15-21`):**
```python
    settlement_meta = invoice.get("settlement") or {}
    settlement_currency = settlement_meta.get("currency", "USDC")
    if settlement_currency != "USDC" or settlement_meta.get("gateway_supported") is False:
        raise HTTPException(
            status_code=400,
            detail=f"{settlement_currency} settlement is not enabled for Circle Gateway runtime.",
        )
```
- **Rationale:** Invoice metadata originates from internal configuration via `hydrate_payment_schema()` (`invoice_builder.py:75`). Clients cannot inject arbitrary currency parameters.
- **Severity: Low**

### 1.3 Settlement Status Lifecycle
**Evidence (`settlement_validation.py:66-73`):**
```python
    if REQUIRE_COMPLETED_SETTLEMENT:
        accepted_statuses = {"completed", "confirmed"}
        rejected_msg = f"Strict mode: settlement status is '{settlement.get('status')}'."
    else:
        accepted_statuses = {"received", "batched", "completed", "confirmed"}
        rejected_msg = f"Settlement status is '{settlement.get('status')}'; payment has not been accepted by Circle yet."
    if settlement.get("status") not in accepted_statuses:
        raise HTTPException(status_code=402, detail=rejected_msg)
```
- **Rationale:** Accepting `received` and `batched` provides low-latency settlement (<500ms). If an upstream batch is dropped, `invoice_has_failed_settlement` transitions invoices to `disputed`.
- **Severity: Low (Accepted Tradeoff)**

## 2. Token & Receipt Signing (Cryptographic Integrity)
### 2.1 Split Receipt Verification
**Evidence (`payment_signing.py:114-125`):**
```python
    if payer_address is not None and gateway_status is not None:
        fields.extend([
            normalize_address(payer_address),
            str(gateway_status).strip().lower(),
        ])
        if buyer_wallet_address is not None:
            fields.append(normalize_address(buyer_wallet_address))
    payload = split_hmac_payload(fields)
    return hmac.new(SPLIT_RECEIPT_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
```
- **Rationale:** Strict character sets for normalized addresses, integer raw units, and enum keywords prevent HMAC canonicalization attacks. `hmac.compare_digest` guards against timing side-channels.
- **Severity: Low**

## 3. Split Leg Lifecycle & Race Condition Defense
### 3.1 Double Claim Prevention
**Evidence (`invoice_builder.py:182-189`):**
```python
    for other_id, other_invoice in (all_invoices or {}).items():
        if other_id == exclude_invoice_id:
            continue
        if other_invoice.get("settlement_id") == settlement_id:
            return True
        for leg in (other_invoice.get("split") or {}).get("legs") or []:
            if leg.get("settlement_id") == settlement_id:
                return True
```
- **Rationale:** Scanning in-memory dictionaries prevents double claims within single instances. At scale, this linear lookup should be backed by database `UNIQUE` constraints on `settlement_id`.
- **Severity: Medium (Scalability Risk)**

### 3.2 Process Concurrency & Locks
**Evidence (`core/state.py:68-101`):**
```python
class cross_process_lock:
    def __init__(self, key: str, timeout_seconds: float = 15.0):
        safe_key = "".join(c if c.isalnum() or c in "-_:." else "_" for c in key)
        self._path = os.path.join(_LOCK_DIR, f"{safe_key}.lock")
        self._timeout = timeout_seconds
        self._fh = None

    def __enter__(self):
        if not _FLOCK_AVAILABLE:
            return self
        os.makedirs(_LOCK_DIR, exist_ok=True)
        self._fh = open(self._path, "a+")
        deadline = time.time() + self._timeout
        while True:
            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                if time.time() > deadline:
                    self._fh.close()
                    self._fh = None
                    raise HTTPException(status_code=409, detail="Another settlement verification...")
                time.sleep(0.05)
```
- **Rationale:** OS-level advisory locking (`fcntl.flock`) protects single-host concurrent execution. Multi-node clusters require distributed locking (e.g., Redis Redlock) or database transactional locks.
- **Severity: High (Multi-Instance Distributed Risk)**

## 4. Invoice Integrity (Split Allocation & Wallet Routing)
**Evidence (`invoice_builder.py:86-94`):**
```python
def allocate_split_legs_raw(total_raw: int, creator_bps: int, platform_bps: int) -> dict:
    weights = [max(0, int(creator_bps)), max(0, int(platform_bps))]
    if sum(weights) != 10000:
        raise HTTPException(status_code=400, detail="Creator/platform split must total 10000 bps.")
    if total_raw <= 0:
        raise HTTPException(status_code=400, detail="Invoice amount must be greater than 0.")
    ideals = [(total_raw * weight) / 10000 for weight in weights]
    floors = [int(value) for value in ideals]
    leftover = total_raw - sum(floors)
```
- **Rationale:** The Largest-Remainder apportionment algorithm prevents fractional rounding loss in raw token units.
- **Severity: Low**

## 5. Entitlement Issuance
**Evidence (`invoice_builder.py:257-271`):**
```python
    access_status = invoice_access_status(invoice)
    access_token = None
    if access_status in {"settlement_confirmed", "access_issued_pending_batch"}:
        access_token = sign_access_token(
            invoice_id=invoice_id,
            provider_id=invoice.get("provider_id"),
            tier=invoice.get("tier"),
            buyer_wallet_address=invoice.get("buyer_wallet_address"),
            payer_address=invoice.get("payer_address"),
            expires_at=time.time() + ACCESS_TOKEN_TTL_SECONDS,
        )
```
- **Rationale:** Scoped tokens cryptographically bind `invoice_id`, `provider_id`, `tier`, and payer address, preventing privilege escalation.
- **Severity: Low**

## 6. Upstream Resilience
**Evidence (`x402_gateway.py:7-16`):**
```python
def fetch_circle_settlement(settlement_id: str, *, gateway_api: str) -> dict:
    try:
        resp = requests.get(f"{gateway_api}/v1/x402/transfers/{settlement_id}", timeout=10)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Circle Gateway lookup failed: {exc}")
```
- **Rationale:** Upstream timeouts raise HTTP 502 gracefully.
- **Severity: Low**

---
**Summary**: Split allocations and HMAC-verified receipt validation form a resilient, deterministic settlement pipeline on Arc.
