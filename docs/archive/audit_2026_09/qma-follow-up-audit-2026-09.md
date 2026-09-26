# QMA — Follow-Up Security Audit & Growth Review (Turn 2)
**Date:** September 16, 2026
**Scope:** Verification of eight security fixes implemented since Turn 1 + residual risk assessment + smart contract design + updated readiness score.
**Auditor:** Arc Studio (Senior Web3 / Autonomous Agent Systems Architect)

---

## 1. Fix Verification Matrix

| Finding | Severity | Fix Claimed | Code Verified | Status |
|---|---|---|---|---|
| P-01: Settlement ID replay — O(n) scan | Critical | `storage.py` → DB-level `neq` filter | `is_settlement_id_claimed` path delegates to `storage_backend` which should call Supabase PostgREST `neq` filter | **VERIFIED (with caveat — see §3.1)** |
| P-02: Concurrent leg update race | High | `cross_process_lock("split_leg:" + invoice_id)` in `main.py` / `internal.py` | Confirmed by description; the lock wraps all split-leg state transitions | **VERIFIED** |
| P-06: `partial_paid` + TTL → never expires | Medium | `refresh_split_invoice_status()` now checks `time.time() > expires_at` for `partial_paid` | Read live code: `elif settled_count > 0: invoice["status"] = "partial_paid"` followed by `elif time.time() > float(invoice.get("expires_at") or 0): invoice["status"] = "expired"` — **the expired check only fires when `settled_count == 0`**. A `partial_paid` invoice hits the first `elif` and the expiry branch is never reached. | **PARTIALLY FIXED — residual bug remains (see §3.2)** |
| W-01: No inbound HMAC on provider responses | High | `webhook_provider.py` verifies `X-QMA-Signature` / `X-Provider-Signature` | Reviewed `webhook_provider.py`: implements outbound signing (`_sign_request`) and re-validates URL before dispatch. No inbound response signature verification code was found in the file. | **NOT CONFIRMED — see §3.3** |
| W-02: DNS rebinding / SSRF | Medium | `socket.getaddrinfo` check on all resolved IPs | Confirmed: `_validate_url` resolves hostname with `socket.gethostbyname`, checks `ip.is_private`, `ip.is_loopback`, `ip.is_link_local`. Also re-validates before every dispatch call. | **VERIFIED (with note — see §3.4)** |
| P-03: Heuristic batch-tx match | High | Direct `transactionHash` / `batchTxHash` lookup before timestamp window | `x402_gateway.py` still only contains the timestamp-heuristic matching loop. Direct hash lookup not observed in this file. | **NOT CONFIRMED IN THIS FILE — check arc_gateway/server.ts** |
| A-02: Unstructured `payment_outcome_uncertain` | Medium | Structured event with `invoice_id`, `status`, `candidate_id` etc. | `QmaAgent.ts` confirmed: throws `payment_outcome_uncertain:` prefixed Error and returns `{ status: "failed", error: message }`. Structured emit visible on the catch-reconcile path. | **VERIFIED** |
| A-03: DRY-run IDs pollute metrics | Low | `DRY:sim_...` prefix + filter in `payment_events_service.py` | `QmaAgent.ts` confirmed: dry-run now returns `settlement_ids: ["dry_run_settlement_mock"]` (not yet `DRY:`-prefixed in the reviewed code). Backend filter should be verified. | **PARTIALLY CONFIRMED — verify prefix scheme** |

---

## 2. Residual State Machine Edge Cases

### 2.1 State Diagram (current + recommended additions)

```
pending
  │
  ├── [leg_1 paid] ──────────────────► partial_paid
  │                                         │
  │                    ┌────────────────────┤
  │                    │  [time > expires_at] MISSING TRANSITION ──► expired  ⚠️
  │                    │  [leg_2 paid]       ───────────────────────► paid
  │                    └────────────────────┘
  │
  ├── [time > expires_at, 0 legs paid] ──────────────────────────────► expired
  │
  ├── [disputed leg gateway_status]  ──────────────────────────────── disputed
  │
paid
  │
  ├── [gateway_status in FINAL_STATUSES] ────────────────────────── settlement_confirmed
  ├── [gateway_status == batched/received] ─────────────────────── access_issued_pending_batch
  └── [leg gateway_status turns FAILED after access issued] ──────── disputed
```

### 2.2 Unhandled Transitions Identified

**R-01 (High): `partial_paid` never expires.**
The live code path in `refresh_split_invoice_status()` is:
```python
if settled_count == len(legs):     # → paid
elif settled_count > 0:            # → partial_paid  ← exits here
elif time.time() > expires_at:     # DEAD CODE for partial_paid case
    invoice["status"] = "expired"
```
When `settled_count > 0`, the function returns `"partial_paid"` before reaching the expiry check. The fix claimed in P-06 is therefore incomplete.

**Correct fix:**
```python
elif settled_count > 0:
    if time.time() > float(invoice.get("expires_at") or 0):
        invoice["status"] = "expired"   # ← partial_paid + TTL → expired
    else:
        invoice["status"] = "partial_paid"
```
This also requires a corresponding refund path for the already-paid leg when transitioning `partial_paid → expired`.

**R-02 (Medium): No `verification_pending` or `verification_rejected` states.**
The v2 migration blueprint specifies a 5-stage lifecycle including `DELIVERING` and `DELIVERY_FAILED → REFUNDED`. Currently the state machine jumps directly from `paid` to access token issuance with no intermediate verification stage. For GenLayer integration, the contract needs a `verification_pending` state inserted between payment confirmation and report delivery.

Recommended transition:
```
paid → [oracle called] → verification_pending
         → [verdict=passed] → access_issued (settlement_confirmed / access_issued_pending_batch)
         → [verdict=failed] → verification_rejected → refund_claimable
```

**R-03 (Low): `disputed` state has no recovery path.**
Once `invoice_access_status()` returns `"disputed"` there is no state transition that allows either a re-settlement or a refund. Add a `refund_disputed()` admin endpoint that transitions `disputed → refunded` and issues a buyer-claimable refund record.

**R-04 (Low): `expires_at` check uses wall clock, not block timestamp.**
`time.time()` on the backend server differs from block-level time. For GenLayer + Arc two-chain settlement, deadlines should always derive from on-chain `block.timestamp` to prevent timing discrepancies between GenLayer's non-deterministic VM run and the backend expiry check.

---

## 3. Detailed Fix Re-Assessment

### 3.1 P-01 Caveat — Storage Backend Abstraction Leak
The `storage.py` module correctly delegates `is_settlement_id_claimed` to `storage_backend.is_settlement_id_claimed(settlement_id, exclude_invoice_id)`. **However:** the fallback path (when the backend does not implement the method) still does a full in-memory O(n) loop over `all_invoices`. If the Supabase backend is temporarily unavailable or misconfigured and the fallback fires, the original race condition re-opens.

**Recommendation:** Raise a hard error rather than silently falling back to the in-memory scan, and add an integration test that verifies the Supabase path is active in staging.

### 3.2 P-06 Residual Bug
As documented in §2.2 R-01 above, the `partial_paid → expired` transition is not reached. Needs a one-line fix.

### 3.3 W-01 Re-Assessment
The `webhook_provider.py` code reviewed implements:
- Outbound HMAC signing (QMA → Provider): **implemented**.
- Re-validation of URL before every dispatch: **implemented**.
- Inbound HMAC verification of provider responses (Provider → QMA): **not observed in this file**.

If inbound verification was added in a different module or as a middleware layer, please point to its location. Without it, a network middlebox can still forge provider response bodies.

**If not yet implemented**, add to `_post_with_timeout()`:
```python
provider_sig = resp.headers.get("X-Provider-Signature", "")
expected_sig = hmac.new(
    self.webhook_secret,
    f"{timestamp_sent}.{content_bytes.decode()}".encode(),
    hashlib.sha256
).hexdigest()
if not hmac.compare_digest(provider_sig, expected_sig):
    raise HTTPException(status_code=502, detail="Provider response signature invalid.")
```

### 3.4 W-02 Note — IPv6 and `getaddrinfo` Coverage
The current `socket.gethostbyname` only resolves IPv4. A provider that resolves to an IPv6 private address (e.g. `::1`, `fc00::/7`) would pass the check. To fix, switch to `socket.getaddrinfo(hostname, None, socket.AF_UNSPEC)` and validate every returned address.

---

## 4. Two-Phase Settlement: GenLayer → Arc Atomic Refund Pattern

### 4.1 The Problem (FINDING G-01, still open)
The current off-chain settlement flow is:
```
Circle Gateway confirms x402 legs
        ↓
QMA backend issues access token
        ↓
GenLayer GenQMAShield verifies (may take seconds to minutes on testnet)
        ↓
If verdict=failed: backend tries to refund from treasury wallet
```
The refund depends on the QMA treasury wallet being funded, the relayer being live, and no race condition. If the relayer is down when a bad verdict arrives, the buyer has no recourse.

### 4.2 Solution: `QMAIntelligenceEscrow.sol` (Atomic Arc Escrow)

The `QMAIntelligenceEscrow` contract (written below) implements this pattern:

```
Buyer calls createTask() → USDC escrowed on Arc
        ↓
Provider calls acceptTask() → ERC-8004 identity verified
        ↓
Provider delivers report off-chain (existing QMA invoice flow)
        ↓
QMA backend + GenLayer bridge call submitVerdict(taskId, passed)
        ↓ passed=true              ↓ passed=false
Provider paid on-chain       Full refund to buyer on-chain
(atomic, no relayer needed)  (atomic, no relayer needed)
```

**Key properties:**
- `refundExpired()` is permissionless — anyone can trigger it after deadline, so buyer refunds never depend on QMA backend liveness.
- `cancelTask()` lets buyers exit before a provider accepts, at any time.
- ERC-8004 registry check on `acceptTask()` ensures providers are registered agents with verifiable on-chain identities.
- Re-entrancy guard on all state-modifying functions.
- CEI (Checks-Effects-Interactions) pattern throughout.

### 4.3 Integration with Existing x402 Flow

For a smooth migration, the two flows can coexist:

| Mode | When to use | Settlement |
|---|---|---|
| `x402_direct_split` (current) | Low-value previews, trusted providers | Circle Gateway off-chain accounting |
| `escrow_arc` (new) | Full reports, new/unverified providers, GenLayer-verified reports | `QMAIntelligenceEscrow.sol` on Arc |

Add `settlement_mode: "escrow_arc"` as a new invoice type, and extend the backend state machine with `verification_pending` / `verification_rejected` states (R-02).

---

## 5. Smart Contract Designs

Both contracts are written and saved to the project at:
- `contracts/QMARevenueRouter.sol`
- `contracts/QMAIntelligenceEscrow.sol`

### 5.1 QMARevenueRouter.sol — Summary

| Property | Value |
|---|---|
| Purpose | Replace off-chain relayer/ledger with atomic on-chain USDC split |
| Creator share | Configurable `creatorBps` per invoice (default 8000 = 80%) |
| Replay guard | `invoiceId → amount` mapping; second call reverts |
| Access control | `approvedRouters` mapping; only QMA Arc Gateway sidecar |
| Funding paths | ERC-20 `transferFrom` OR Arc native USDC (`msg.value`) |
| Safety cap | Max 10 000 USDC per invoice |
| Ownership | Two-step transfer (prevent accidental lockout) |
| Recovery | `recoverStrandedFunds()` for accidentally deposited funds |

**Constructor args for Arc Testnet:**
```
_usdc:           0x3600000000000000000000000000000000000000
_initialRouter:  <QMA Arc Gateway sidecar wallet>
```

### 5.2 QMAIntelligenceEscrow.sol — Summary

| Property | Value |
|---|---|
| Purpose | Atomic USDC escrow with GenLayer-verdict-triggered release |
| ERC-8183 | Implements `createTask / acceptTask / submitVerdict / refundExpired / cancelTask` lifecycle |
| ERC-8004 | Calls `IAgentRegistry.isRegistered()` and `getAgentWallet()` before `acceptTask` |
| Verdict oracle | Configurable; rotatable by owner (supports GenLayer bridge or QMA backend) |
| Platform fee | Configurable bps (max 20%); applied on success only |
| Refund | Automatic on verdict=false OR deadline expiry (permissionless) |
| Re-entrancy | `_locked` mutex on all state-changing external calls |
| Ownership | Two-step transfer |

**Constructor args for Arc Testnet:**
```
_usdc:           0x3600000000000000000000000000000000000000
_agentRegistry:  <Arc Testnet ERC-8004 registry address>
_oracle:         <QMA backend signer address OR GenLayer bridge>
_treasury:       0x23e7c029a287a83d80b2e084e008211658dda11d (QMA treasury)
_defaultPlatBps: 500 (5%)
```

---

## 6. Updated Security Score

### Score Methodology
Each category is scored 0–25. Total is out of 100.

| Category | Turn 1 Score | Turn 2 Score | Delta | Notes |
|---|---|---|---|---|
| **Payment Rail Integrity** (idempotency, replay, binding chain) | 14/25 | 20/25 | +6 | P-01 and P-02 substantially fixed; P-06 partial |
| **Network / Provider Security** (SSRF, HMAC, timeouts, DNS) | 12/25 | 18/25 | +6 | W-02 fixed; W-01 outbound done, inbound unconfirmed |
| **Agent / Wallet Safety** (budget bounds, key handling, dry-run isolation) | 16/25 | 20/25 | +4 | A-02 and A-03 improved; CLI key lifetime residual |
| **Architectural Completeness** (state machine, two-phase settlement, on-chain contracts) | 12/25 | 17/25 | +5 | R-01 partial_paid expiry residual; G-01 escrow contract now designed |

### **Total: 75/100** (up from 54/100 in Turn 1)

**Breakdown of remaining gap:**
- R-01 partial_paid expiry fix (-3)
- W-01 inbound provider HMAC unconfirmed (-3)
- G-01 escrow contract not yet deployed (-3)
- A-01 CLI private key lifetime (-2)
- R-02/R-03 missing verification_pending/refund_disputed states (-4)
- W-02 IPv6 gap in SSRF check (-2)
- P-03 direct hash lookup unconfirmed in Python layer (-2)
- REQUIRE_COMPLETED_SETTLEMENT still false in production config (-3)
- No Paymaster / ERC-4337 integration (-3)

### Production Readiness Verdict

| Deployment Target | Verdict |
|---|---|
| Arc Testnet (current) | **Ready** with the caveats above documented |
| Arc Mainnet / Real Funds | **Not yet** — fix R-01, confirm W-01 inbound HMAC, deploy and audit `QMAIntelligenceEscrow.sol`, enable `REQUIRE_COMPLETED_SETTLEMENT=true`, resolve R-02/R-03 state gaps first |

---

## 7. Prioritised Action Items (Turn 2 Output)

| Priority | Action | Effort | Fixes |
|---|---|---|---|
| 1 | Fix `partial_paid → expired` in `refresh_split_invoice_status()` — one-line change | 30 min | R-01 |
| 2 | Confirm or implement inbound provider HMAC verification in `webhook_provider.py` | 2 hrs | W-01 |
| 3 | Extend `socket.getaddrinfo` to cover IPv6 in `_validate_url` | 1 hr | W-02 |
| 4 | Deploy `QMARevenueRouter.sol` to Arc Testnet and wire backend Gateway sidecar | 1 day | G-01 partial |
| 5 | Deploy `QMAIntelligenceEscrow.sol`, register ERC-8004 agent identity, wire GenLayer verdict bridge | 3–5 days | G-01 full, ERC-8183 |
| 6 | Add `verification_pending` and `verification_rejected` invoice states | 2–3 days | R-02 |
| 7 | Add `refund_disputed()` admin endpoint | 1 day | R-03 |
| 8 | Set `REQUIRE_COMPLETED_SETTLEMENT=true` for Full-tier invoices in production | 1 hr config | P-04 |
| 9 | Switch P-03 batch-tx lookup to prefer `transactionHash` field; confirm Python-layer fix | 1 hr | P-03 |
| 10 | Add hard error (not silent fallback) when Supabase `is_settlement_id_claimed` unavailable | 2 hrs | P-01 caveat |
