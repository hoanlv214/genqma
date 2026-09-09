# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.1] - 2026-07-22

### Security (Critical Fixes)
- **IDOR Vulnerability:** Fixed an IDOR in `/api/v1/chat` where users could query paid reports without a valid Access Token by passing an unpaid `invoice_id`. Now explicitly requires and verifies `qma_access_token`.
- **Database Double-Claim:** Added `UNIQUE INDEX` constraints for `settlement_id` on `qma_invoices` and `qma_payment_events` in Supabase to prevent the same Circle transfer from being claimed multiple times.
- **Creator Payout Double-Spend:** Updated backend Creator Payout logic to mark claims as `unknown` (instead of `failed`) if the ARC Gateway HTTP request times out or returns a 502 error. This prevents the creator's claimable balance from being incorrectly restored during network latency, averting a double-spend against the platform treasury.

### Changed
- **Strict V2 API Typings:** Enforced strict Pydantic parsing (`ProviderReportResponse`) in `main.py` instead of dictionary manipulation. Segregated all domain-specific payload data into the `payload` block, preventing payload schema collisions with the platform envelope. 
- **Frontend Query State Sync:** Stripped UI-specific metadata (`synthetic`, `tier`, `provider_id`) from queries before hashing, fixing a bug where frontend caches failed to retrieve purchased reports due to differing `query_hash` states.
- **Performance:** Refactored `storage.py` and `invoice_builder.py` to use `is_settlement_id_claimed` natively instead of an O(N) memory sweep with `limit=2000`.
