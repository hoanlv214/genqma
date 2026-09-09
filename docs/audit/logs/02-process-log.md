# Process Log — Phase 2: Payment Lifecycle Review

## Declared Scope
- `payment_state_machine.py`
- `x402_gateway.py`
- `settlement_validation.py`
- `payment_signing.py`
- `invoice_builder.py`
- Related files governing payment state transitions (`internal.py`, `main.py`).

## Sequential Execution Steps

### Step 1: Inspection of `payment_state_machine.py`
- Tool used: `view_file`
- Target: `backend/app/services/payment_state_machine.py`
- Findings: Read 157 lines (full file). Evaluated state transitions across `paid`, `partial_paid`, `pending`, `expired`, and `disputed`.

### Step 2: Inspection of `x402_gateway.py`
- Tool used: `view_file`
- Target: `backend/app/services/x402_gateway.py`
- Findings: Read 77 lines (full file). Analyzed `fetch_circle_settlement` and `find_arc_batch_tx`.

### Step 3: Inspection of `settlement_validation.py`
- Tool used: `view_file`
- Target: `backend/app/services/settlement_validation.py`
- Findings: Read 80 lines (full file). Validated `toAddress`, `amount`, and `currency` consistency checks.

### Step 4: Inspection of `payment_signing.py`
- Tool used: `view_file`
- Target: `backend/app/services/payment_signing.py`
- Findings: Read 166 lines (full file). Verified HMAC signature schemes for leg receipts and access tokens.

### Step 5: Inspection of `invoice_builder.py`
- Tool used: `view_file`
- Target: `backend/app/services/invoice_builder.py`
- Findings: Read 388 lines (full file). Validated `creator_share_bps` vs `platform_share_bps` allocation algorithms.

### Step 6: Inspection of State Transition Callers (`internal.py`, `main.py`)
- Tool used: `grep_search`, `view_file`
- Findings: Verified how `verify_payment` and `verify_split_payment` wrapper routines in `main.py` persist state changes.

### Step 7: Data Tracing for Settlement Proofs
- Traced `has_authoritative_gateway_claims` evaluation and verified that submitted settlement proofs must pass HMAC verification before population into execution context.

### Step 8: Apportionment & Entitlement Logic
- Inspected Largest-Remainder apportionment algorithm in `allocate_split_legs_raw` and scoped token generation in `invoice_payment_state_response`.

### Step 9: Evaluation of `cross_process_lock`
- Target: `backend/app/core/state.py` (lines 68-120).
- Findings: Confirmed implementation uses OS-level advisory locks (`fcntl.flock`) on `/tmp/qma-locks`.

## Directly Inspected Files
- `backend/app/services/payment_state_machine.py` (lines 1–157)
- `backend/app/services/x402_gateway.py` (lines 1–77)
- `backend/app/services/settlement_validation.py` (lines 1–80)
- `backend/app/services/payment_signing.py` (lines 1–166)
- `backend/app/services/invoice_builder.py` (lines 1–388)
- `backend/app/api/v1/endpoints/internal.py` (lines 1–204)
- `backend/app/main.py` (lines 930–1100)
- `backend/app/core/state.py` (lines 68–120)

## Search & Grep Queries
| Query | Results | Purpose |
|---|---|---|
| `validate_arc_` in `backend/app` | 6 matches | Locate validation callers |
| `api/internal` in `backend/app` | 4 matches | Check internal relay routes |
