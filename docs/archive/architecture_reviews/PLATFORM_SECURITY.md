# QMA Platform Security Blueprint (vNext)

This document outlines the 4-Layer Security Architecture for the QMA Intelligence Marketplace. 
As the platform evolves from a monolith into an Open Ecosystem (Webhooks/Plugins), the primary threat model shifts from **Remote Code Execution (RCE)** to **Platform Abuse, Fraud, and Marketplace Manipulation**.

## Core Philosophy
1. **Zero Trust Integration:** We do not trust the Provider's server, their schema, their response time, or their DNS.
2. **Opaque Payloads:** Provider data is completely isolated. They cannot inject top-level fields (e.g., price, status) to forge system states.
3. **Cryptoeconomic Integrity:** AI Agents are automated buyers. The platform must mathematically and programmatically prevent Sybil attacks and fake reputation farming.

---

## Layer 1 — Registration & Onboarding
The first line of defense before a Provider is even allowed to be called by an Agent.

- **URL & SSRF Validation:** `api_base_url` must be strictly validated. Rejection of local/private IP ranges (`127.0.0.1`, `169.254.169.254`, etc.) to prevent Server-Side Request Forgery against QMA's internal infrastructure or Cloud Metadata.
- **Domain Ownership Verification:** Providers must prove ownership of their `api_base_url` domain (e.g., via DNS TXT record or a `.well-known` challenge) before being activated.
- **Wallet & Identity:** Verification of the USDC revenue wallet.
- **Schema Validation:** The `/manifest` endpoint is strictly parsed. Overly large manifests or schemas with malicious structures are rejected.

---

## Layer 2 — Runtime (Network & Protocol)
The active defenses executing during every `score()`, `deliver()`, and `verify()` API call.

- **Anti-Spoofing (HMAC):** All requests sent to the Provider include `X-QMA-Signature` (HMAC-SHA256) and `X-QMA-Timestamp`. This prevents attackers from bypassing QMA and hitting the Provider directly.
- **Strict Timeouts:** Hard timeouts (e.g., 3s for score, 15s for deliver) to prevent DDoS via connection exhaustion (Slowloris-style attacks).
- **DNS Rebinding Protection:** The hostname is re-resolved and re-validated immediately before the HTTP connection is established.
- **Response Bomb Protection:** Outbound HTTP clients read data via streams. If a Provider attempts to return a massively inflated payload (e.g., >1MB) to crash QMA's RAM, the connection is instantly aborted.
- **Circuit Breaker:** If a Provider times out or returns 5xx errors multiple times consecutively, they are automatically disabled (e.g., 10 minutes) to prevent cascading failures in Agent logic.

---

## Layer 3 — Marketplace (Cryptoeconomics & Reputation)
Preventing fraud, manipulation, and economic attacks against the Agent ecosystem.

- **Provider Reputation Layer:** A mandatory Calibration pipeline that scores Providers based on their historical accuracy (Win Rate, Precision, ROI).
- **Sybil Detection:** Detecting and penalizing Providers who create fake buyer accounts to purchase their own reports, artificially inflating their volume/reputation.
- **Staking / Minimum Thresholds:** Before a Provider's intelligence is blindly trusted by top-tier Agents, they must achieve a minimum number of unique buyers or stake collateral.
- **Opaque Payload Isolation:** The QMA Orchestrator enforces that pricing (`amount_usdc`) and confidence metrics are locked at the `score` phase. The Provider's `deliver` payload is nested inside a `"payload"` object, removing any ability to overwrite system-level invoice states.

---

## Layer 4 — Content Safety & Presentation
Protecting the human users and Frontend UI from malicious data returned by Providers.

- **Data Sanitization:** All text payloads rendered on the Frontend (Markdown, HTML) must pass through strict sanitizers (e.g., DOMPurify).
- **No Executable Content:** Complete stripping of `<script>`, `<iframe>`, and JavaScript event handlers (e.g., `onload`).
- **SVG Blocking/Sanitization:** Disallow untrusted SVGs which can contain embedded XSS payloads.
- **File Scanning:** Any binary files or links provided in the payload must be treated as untrusted and potentially scanned before being served to the end user.
