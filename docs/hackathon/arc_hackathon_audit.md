# QMA — Arc Programmable Money Hackathon Audit

Audit date: 2026-07-18  
Repository scope: current QMA source tree on `main`; `_refs/` is treated as reference material and is not evidence of a QMA runtime capability.  
Criteria: the Arc hackathon requirements supplied in the audit brief, with the [Encode Arc Hackathon page](https://www.encodeclub.com/my-programmes/arc-hackathon) as the referenced programme page.

This is an implementation audit, not a product claim. A capability is marked as implemented only when the current source contains an executable path or a testable contract for it. Documentation alone is not treated as proof.

## Executive Summary

| Area | Score | Assessment |
|---|---:|---|
| Overall readiness | **64/100** | Strong Arc Testnet/USDC/Gateway/x402 MVP and a real bounded CLI payment path; important gaps remain around browser-native autonomy, durable hosted sessions, broader Circle product usage, and final-submission evidence. |
| DeFi track readiness | **35/100** | Payments, treasury-like platform/provider accounting, and settlement are implemented. Lending, borrowing, yield, liquidity provision, FX and broader DeFi primitives are not present. |
| Agentic Economy track readiness | **72/100** | The CLI can make bounded decisions, create invoices, pay split x402 legs through Circle Agent Wallet, verify settlement, and unlock reports. The browser path still requires a human wallet signature, and the autonomous worker is process-local rather than a durable hosted service. |

The strongest demonstrated product is an agent-facing, pay-per-call market-intelligence marketplace: a policy-bounded buyer selects a report, QMA creates a provider-bound invoice, Circle Gateway/x402 settles creator and platform legs on Arc Testnet, and the backend verifies the settlement before issuing access.

The score is intentionally below final-submission readiness. The source proves the payment and agent paths, but it does not prove a production deployment, a submitted three-minute pitch/demo, or a durable autonomous worker serving multiple user sessions. The UI copilot and CLI are also materially different: the CLI has a Circle Agent Wallet executor, while the browser flow uses an injected EVM wallet and asks the user to sign.

## Feature Inventory

### Live market-signal discovery

Status: **Implemented**

Locations:

- `backend/app/api/v1/endpoints/market.py` — live anomaly and recommendation routes.
- `backend/app/services/agent_recommendations.py` — provider recommendation aggregation.
- `market_data.py` and the provider implementations — live market input adapters.
- `frontend/src/hooks/useAgentBuyer.ts` — browser decision fallback and candidate consumption.

Evidence: the backend exposes `/api/v1/providers/*/live-anomalies` and `/api/v1/agent/recommendations`; the agent decision service consumes live recommendations and produces evaluated candidates. The source includes provider IDs, symbols, scores, query snapshots, tiers and suggested prices.

Description: QMA turns live market conditions into candidate reports rather than selling a generic static dataset.

### Multi-provider market-intelligence marketplace

Status: **Partially Implemented**

Locations:

- `backend/app/api/v1/endpoints/providers.py`.
- `backend/app/services/agent_recommendations.py`.
- `backend/app/services/agent_decision.py:97-238`.
- `frontend/src/components/agent/AgentBuyerModalContent.tsx:213-217`.

Evidence: candidate evaluation includes provider, tier, score, price and rejection reasons; the UI displays provider comparison rows. The current providers are primarily the existing memory providers and there is no independent provider-quality/latency reputation system; the repository itself calls this out in `README.md:253-255`.

### Provider-bound dynamic report pricing

Status: **Implemented for the current provider pricing model; limited as a market mechanism**

Locations:

- `backend/app/services/agent_decision.py:92-97`.
- `backend/app/api/v1/endpoints/payments.py` and invoice-building services.
- `backend/app/services/invoice_builder.py`.

Evidence: the decision service resolves the price for a candidate/tier before eligibility and budget checks; invoices bind price, provider, query and tier. This is dynamic/provider-bound pricing, but there is no evidence of a supply/demand auction or provider-configurable market pricing algorithm.

### Deterministic and optional LLM decisioning

Status: **Implemented**

Locations:

- `backend/app/services/agent_decision.py:42-507`.
- `backend/app/api/v1/endpoints/agent.py:16-43`.
- `agents/src/planner/llmPlanner.ts`.
- `agents/src/providers/openai.ts`.
- `tests/test_agent_decision.py`.

Evidence: the endpoint accepts a natural-language prompt and bounded policy fields. The service prepares eligible candidates, applies budget/max-price/ownership/provider/tier checks, optionally calls OpenAI with a strict decision schema, validates the returned candidate against server-side candidates, and falls back to deterministic policy when LLM use is disabled or unavailable. Tests cover validated purchase decisions, ownership, provider comparison, rejection codes and LLM candidate validation.

### Bounded autonomous CLI sessions

Status: **Implemented, process-local**

Locations:

- `agents/src/session/policy.ts:17-124`.
- `agents/src/session/loop.ts:65-121`.
- `examples/agent_session.mjs:100-252`.
- `agents/src/session/state.ts`.

Evidence: policy includes budget, max price, providers, tiers, minimum score, max purchases/attempts, duration, polling, cooldowns, ownership avoidance and stop conditions. The loop observes, chooses, purchases, records failures/actions and stops at policy limits. `examples/agent_session.mjs` calls `/api/v1/agent/decision` and drives the payment child process.

Limitation: state is held by the running CLI process. No backend session table, queue, hosted worker, restart recovery or multi-tenant worker is evidenced.

### Circle Agent Wallet CLI payment executor

Status: **Implemented with external CLI/session prerequisites**

Locations:

- `agents/src/executor/paymentExecutor.ts:192-249`.
- `agents/src/wallets/signer.ts`.
- `examples/agent_session.mjs:37-42,121-122,160-198`.
- `README.md:116-131,238-245`.

Evidence: the executor invokes the Circle CLI service-payment command for an explicitly selected agent-wallet address, then validates returned settlement ID, receipt, recipient and amount. Split legs are executed sequentially, already-settled legs are recovered, self-payment is rejected, and uncertain outcomes are not blindly retried. The CLI requires the Circle CLI login/session and a funded Gateway balance.

### Browser human-wallet purchase flow

Status: **Implemented; not autonomous**

Locations:

- `frontend/src/services/wallet.ts:17-35`.
- `frontend/src/hooks/useWalletConnection.ts:70-96`.
- `frontend/src/services/x402.ts:33-110`.
- `frontend/src/hooks/useAgentBuyer.ts:527-701`.

Evidence: the browser uses injected MetaMask/Rabby/OKX-compatible EIP-1193 providers, checks/switches to Arc Testnet, requests `eth_signTypedData_v4`, submits `payment-signature`, calls payment verification, then fetches the report. The UI explicitly displays “Wallet signature requested. Confirm in your wallet” in `frontend/src/components/modals/AgentBuyerModalContent.tsx:270-278`.

### x402 split payment and settlement verification

Status: **Implemented**

Locations:

- `arc_gateway/server.ts:363-566`.
- `backend/app/services/payment_state_machine.py:33-78,98-154`.
- `backend/app/services/payment_signing.py`.
- `backend/app/services/settlement_validation.py`.
- `docs/ARC_PAYMENT.md` and `PAYMENT_FLOW.md`.

Evidence: each split leg is signed, checked against invoice/provider/tier/amount/recipient, reserved, verified by Circle’s batching facilitator, settled, queried for transfer details, recorded with a receipt, and later reconciled by the backend. The invoice is only considered paid when all required legs have settlement proof.

### Creator/platform revenue split

Status: **Implemented as direct Gateway split accounting**

Locations:

- `backend/app/services/payment_state_machine.py:45-72`.
- `backend/app/services/payment_events_service.py:45-162`.
- `arc_gateway/server.ts:404-566`.
- `backend/app/api/v1/endpoints/providers.py` creator claim/withdraw routes.

Evidence: invoices contain creator and platform legs; the payment event service computes creator/platform shares and direct Gateway split metadata; provider and platform payment activity is exposed in API responses.

Important boundary: `backend/app/services/circle_client.py:131-133` states that the split is an accounting ledger over USDC receipts, not an on-chain split contract.

### Wallet-bound entitlements and paid-report access

Status: **Implemented**

Locations:

- `backend/app/services/payment_state_machine.py:144-154`.
- `backend/app/api/v1/endpoints/reports.py`.
- `backend/app/api/v1/endpoints/wallets.py`.
- `backend/app/services/payment_signing.py`.
- `frontend/src/services/walletProfileSession.ts:59-98`.

Evidence: payment verification issues a short-lived access token only after invoice/settlement validation; wallet profile access uses a signed wallet message and a wallet token; reports and entitlements are bound to wallet/invoice data.

### Creator earnings and withdrawal

Status: **Implemented, with relayer/treasury dependencies**

Locations:

- `backend/app/services/creator_claims.py`.
- `backend/app/api/v1/endpoints/providers.py`.
- `backend/app/api/v1/endpoints/payments.py`.
- `arc_gateway/server.ts:713-883`.

Evidence: the project exposes provider earnings, creator claims and withdrawal flows. The gateway contains relayed Gateway mint/claim and USDC transfer execution paths. This is payout infrastructure, not lending/yield DeFi.

### Public traction and settlement analytics

Status: **Implemented**

Locations:

- `backend/app/services/payment_events_service.py:202-311`.
- `backend/app/api/v1/endpoints/platform.py:110-178`.
- `frontend/src/components/traction/TractionPage.tsx:22-145`.
- `frontend/src/components/traction/PlatformAnalyticsPanel.tsx:47-240`.

Evidence: the public traction endpoint derives settled reports, volume, payer/buyer-type provenance, daily settlement activity, providers and recent settlements from persisted payment events. The analytics panel exposes paginated payment, wallet and provider activity.

### OpenAPI and Scalar documentation

Status: **Implemented**

Locations:

- `backend/app/main.py:217-401` — metadata, custom OpenAPI and `/scalar`.
- `frontend/src/components/docs/DocsPage.tsx:1-8` — Scalar React reference pointed at `/openapi.json`.
- `backend/app/api/v1/endpoints/*` — route descriptions, response models and documented errors.

Evidence: FastAPI publishes `/openapi.json`; backend `/scalar` uses `scalar-fastapi`; frontend `/docs` renders `@scalar/api-reference-react`. This documents the API but does not itself add payment or agent functionality.

### Deployment topology

Status: **Configured; deployment consistency requires operational verification**

Locations:

- `render.yaml` — `qma-api` and `qma-arc-gateway` services on `main`.
- `vercel.json` — Vite build/output and SPA rewrite.
- `frontend/vite.config.ts` — local API/Gateway proxy.
- `README.md:15-27` — documented rebuild URLs and deployment caveat.

Evidence: Render has separate Python API and Node gateway services; Vercel builds `frontend` and rewrites routes to the SPA. The README explicitly warns that deployed URLs/branch/environment configuration must be verified before treating them as current.

## Requirement Mapping

Status vocabulary is exactly: Implemented, Partially Implemented, Missing, or Unclear.

| Requirement | Status | Evidence | Notes |
|---|---|---|---|
| Build a real product on Arc | Implemented | `backend/app/core/config.py:57-72`; `arc_gateway/server.ts:89-99`; `render.yaml` | Arc Testnet is the configured runtime network and Gateway rail. |
| Use USDC as the core money layer | Implemented | `backend/app/core/config.py:97-98`; `arc_gateway/server.ts:90-94`; `backend/app/services/circle_client.py:48-76` | Runtime settlement assets are explicitly USDC-only. |
| Meaningful use of Arc | Implemented | `backend/app/core/config.py:59-72`; `arc_gateway/server.ts:96-105,756-777` | Arc Testnet RPC, chain/network, USDC contract, Gateway wallet/minter and Arcscan are wired. |
| Sub-second Arc settlement advantage | Partially Implemented | `arc_gateway/server.ts:473-485`; `backend/app/services/circle_client.py:233-283` | The code uses Gateway and tracks Circle settlement versus later Arc batch indexing; no latency benchmark or SLA is part of the product contract. |
| DeFi track: stablecoin-native payments | Implemented | `arc_gateway/server.ts:404-566`; `frontend/src/services/x402.ts:33-110` | Real x402 payment authorization and settlement path. |
| DeFi track: treasury workflow | Partially Implemented | `backend/app/services/payment_events_service.py:45-162`; `backend/app/api/v1/endpoints/platform.py` | Platform treasury and provider earnings/withdrawal exist; no broader treasury automation or multi-asset treasury strategy. |
| DeFi track: settlement workflow | Implemented | `backend/app/services/payment_state_machine.py:33-154`; `backend/app/services/circle_client.py:36-81` | Split legs, settlement state and reconciliation are implemented. |
| DeFi track: liquidity | Missing | No liquidity-pool, LP, market-making or liquidity-management implementation found in runtime code | Gateway balances are payment balances, not market liquidity. |
| DeFi track: lending | Missing | No lending protocol, collateral, interest or loan state found in runtime code | — |
| DeFi track: borrowing | Missing | No borrowing, debt or repayment state found in runtime code | — |
| DeFi track: yield | Missing | No yield strategy, vault or accrual implementation found in runtime code | — |
| DeFi track: FX | Missing | No FX quote, exchange, StableFX or currency conversion execution found | Runtime settlement is USDC-only. |
| DeFi track: programmable money / conditional flow | Partially Implemented | `agents/src/session/policy.ts:17-124`; `backend/app/services/payment_state_machine.py:33-154`; split-leg signing in `arc_gateway/server.ts:404-566` | User/system policies and multi-step settlement are programmable off-chain workflows; no custom on-chain programmable-money contract is present. |
| Agentic track: clear decision logic tied to real signals | Implemented | `backend/app/services/agent_decision.py:97-238,462-507`; `agents/src/session/loop.ts:65-121` | Decisions use live candidates, score, price, provider, tier, ownership and budget. |
| Agent holds a wallet | Partially Implemented | `agents/src/executor/paymentExecutor.ts:219-249`; `frontend/src/services/wallet.ts:17-35` | CLI can use Circle Agent Wallet; browser uses a user-controlled injected wallet, not a Circle Agent Wallet. |
| Autonomous spending in USDC | Partially Implemented | `examples/agent_session.mjs:160-198`; `agents/src/executor/paymentExecutor.ts:192-214` | CLI live mode can pay after setup; browser requires a human signature. |
| Autonomous settlement | Implemented for CLI path | `arc_gateway/server.ts:473-525`; `backend/app/services/payment_state_machine.py:33-78` | CLI executor submits payment; gateway/facilitator settles and backend verifies all legs. |
| Risk management | Implemented | `agents/src/session/policy.ts:72-124`; `agents/src/executor/paymentExecutor.ts:187-214`; `backend/app/services/agent_decision.py:250-279,439-462` | Budget, max price, ownership, provider/tier, self-payment, recipient/amount binding, idempotency and stop conditions are enforced. |
| Agent-to-service payments | Implemented | `examples/agent_session.mjs:130-252`; `arc_gateway/server.ts:404-566` | QMA reports are the paid service and the agent buys them through x402. |
| Agent-to-agent payments | Missing | No agent identity-to-agent recipient protocol or agent service registry was found | Provider wallets are revenue recipients, not autonomous agent identities. |
| Agent Stack starter-kit integration | Partially Implemented | `agents/src/session/*`, `agents/src/executor/*`, `agents/src/planner/*`; no Circle Agent Stack SDK dependency in `package.json` | QMA has analogous typed policy/session/executor patterns, but no direct starter-kit package integration was found. |
| Nanopayments | Partially Implemented | `arc_gateway/package.json:13-15`; `README.md:170-180`; Gateway x402 split legs | QMA uses small x402/Gateway payments and batching; no separate Circle Nanopayments API/package was found. |
| Paymaster | Missing | No paymaster, gas sponsorship or user-operation flow found | Arc USDC gas and Gateway reduce funding friction, but that is not Paymaster integration. |
| Checkpoint 1: project/team/idea | Partially Implemented | `README.md`; repository and deployment configuration | The repository contains an idea/product description; submission-platform team/project state is not verifiable from code. |
| Checkpoint 2: repository/progress summary | Implemented as repository evidence | `README.md`, `docs/`, `examples/`, tests and deployment files | Whether the checkpoint was submitted on time is outside source-code evidence. |
| Final: functional MVP deployed on Arc | Partially Implemented | `render.yaml`, `vercel.json`, Arc/Gateway runtime code, `README.md:15-27` | Deployment configuration and source exist; current production health and exact deployment parity must be verified externally. |
| Final: public code repo | Unclear | Repository is present in the current workspace; public visibility is not provable from local source | No repository URL was supplied as an auditable source fact. |
| Final: three-minute video pitch/demo | Missing | No final video asset/link found in the reviewed repository | A live CLI example is not a submitted video. |
| Final: deck | Missing | No final submission deck found in the reviewed repository | — |

## Agentic Economy Analysis

### Agent wallet ownership

**Partially implemented.** The CLI’s Circle executor accepts an explicit agent-wallet address and calls the Circle CLI (`agents/src/executor/paymentExecutor.ts:219-249`). The project documentation distinguishes the logical Circle Agent Wallet address from the backing payer identity (`README.md:128-131`), and the Gateway sidecar preserves `buyer_wallet_address` while recording the settlement payer (`arc_gateway/server.ts:494-520`).

The browser does not create or log into a Circle Agent Wallet. It stores an injected EVM address in the wallet store and uses the browser provider (`frontend/src/services/wallet.ts:17-35`, `frontend/src/state/walletStore.tsx:12-27`).

### Autonomous spending

**Partially implemented.** In CLI live mode, the session chooses a candidate, creates an invoice and launches the payment executor without asking for a browser signature (`examples/agent_session.mjs:160-198`). The actual Circle CLI login, wallet funding, Gateway deposit and spending policy setup remain prerequisites outside the session loop. In the browser, `useAgentBuyer` reaches `awaiting_signature` and calls the injected wallet signing path (`frontend/src/hooks/useAgentBuyer.ts:581-588`; `frontend/src/services/x402.ts:86-103`).

### Autonomous settlement

**Implemented on the CLI path.** The Gateway sidecar builds split payment requirements, calls `facilitator.verify`, calls `facilitator.settle`, fetches the Circle transfer, validates amount/pay-to/payer/status, and records an idempotent receipt (`arc_gateway/server.ts:404-566`). The backend marks a split invoice paid only after required legs have settlement IDs (`backend/app/services/payment_state_machine.py:33-78`).

### Risk management

**Implemented.** Controls include:

- user/session limits: budget, max price, providers, tiers, minimum score, max purchases, max attempts, duration and polling (`agents/src/session/policy.ts:17-124`);
- ownership and duplicate avoidance in candidate selection (`backend/app/services/agent_decision.py:82-188`, `agents/src/session/loop.ts:38-63`);
- server-side validation of an LLM candidate against canonical candidates (`backend/app/services/agent_decision.py:336-462`);
- invoice-bound provider/tier/amount/pay-to checks (`arc_gateway/server.ts:425-439`);
- self-payment rejection and split-leg proof validation (`arc_gateway/server.ts:440-513`, `agents/src/executor/paymentExecutor.ts:204-214`);
- idempotent/reconciliation-aware handling for already paid or uncertain legs (`agents/src/executor/paymentExecutor.ts:187-214`, `backend/app/services/payment_state_machine.py:98-154`).

### Agent decision logic

**Implemented with optional LLM assistance.** The LLM is not the payment authority. `agent_decision.py` uses the model only to propose a minimal plan; QMA resolves and validates the canonical candidate, or uses deterministic fallback. This is a meaningful safety boundary for a paid agent.

### Agent-to-service payments

**Implemented.** QMA itself is the paid report service. The agent obtains a report invoice, pays x402 split legs and receives the report/access token. The CLI and browser both call the same backend decision/payment contracts, although their executors differ.

### Agent-to-agent payments

**Missing.** No source path identifies another autonomous agent as a service recipient or initiates a payment between two agent identities. `provider_owner_wallet` and creator revenue wallets represent providers, not an agent-to-agent protocol.

### Nanopayments readiness

**Partially implemented.** The payment amounts are small and the Gateway uses Circle x402 batching (`arc_gateway/package.json:13-15`). This is technically compatible with machine payments, but no explicit Nanopayments SDK/API integration or agent marketplace service discovery is present.

### Paymaster readiness

**Missing.** No `UserOperation`, paymaster, gas sponsorship, or smart-account transaction flow was found. Arc’s USDC-denominated gas and Gateway balance are not a Paymaster implementation.

## DeFi Analysis

| Capability | Status | Evidence |
|---|---|---|
| Payments | Implemented | `arc_gateway/server.ts:404-566`; `frontend/src/services/x402.ts:33-110` |
| Treasury | Partially Implemented | Platform treasury address and creator/platform revenue accounting in `backend/app/services/payment_events_service.py:45-162`; Gateway balance in `backend/app/services/circle_client.py:48-81` |
| Settlement | Implemented | `backend/app/services/payment_state_machine.py:33-154`; `backend/app/services/circle_client.py:36-81` |
| Stablecoin workflow | Implemented | `backend/app/core/config.py:97-98`; USDC-only Gateway requirements in `arc_gateway/server.ts:89-105` |
| Liquidity | Missing | No LP, pool, market-making or liquidity management implementation |
| Lending | Missing | No lending/loan/collateral state |
| Borrowing | Missing | No borrowing/debt/repayment state |
| Yield | Missing | No yield strategy/vault/accrual state |
| FX | Missing | No FX conversion or StableFX integration; settlement is USDC-only |
| Programmable money | Partially Implemented | Bounded spending policy plus multi-step split settlement; no custom on-chain programmable-money contract |

QMA is therefore not currently a broad DeFi protocol. Its credible DeFi-track claim is stablecoin-native payment, settlement, treasury accounting and payout infrastructure on Arc, not lending/yield/liquidity/FX.

## Circle & Arc Integration Audit

| Product/integration | Status | Evidence | Boundary |
|---|---|---|---|
| Circle Wallets | Partially Implemented | Circle Agent Wallet CLI executor in `agents/src/executor/paymentExecutor.ts:219-249`; browser wallet in `frontend/src/services/wallet.ts:17-35` | No Circle user-controlled/modular wallet SDK in frontend; no browser Agent Wallet login/OTP flow. |
| Agent Stack | Partially Implemented | Typed QMA session/policy/executor modules under `agents/src/`; `examples/agent_session.mjs` | Patterns are implemented locally; no direct Circle starter-kit dependency/API was found. |
| App Kits | Missing | No Circle Send/Bridge/Swap/Unified Balance App Kit dependency or runtime import found | Gateway client is not App Kit. |
| USDC | Implemented | `backend/app/core/config.py:97-98`; `arc_gateway/server.ts:89-105` | Runtime settlement asset. |
| Arc | Implemented on testnet | `backend/app/core/config.py:59-72`; `arc_gateway/server.ts:96-99,756-777` | Current evidence targets Arc Testnet, not mainnet. |
| Gateway | Implemented | `arc_gateway/server.ts:99,363-566`; `backend/app/services/circle_client.py:36-81` | Used for x402 transfer verification, balance, settlement and split flow. |
| CCTP | Missing | No CCTP client, attestation or burn/mint transfer flow found | Gateway’s own settlement path is not evidence of CCTP. |
| Circle Contracts | Partially Implemented | `arc_gateway/server.ts:625-696,756-777` uses Gateway wallet/minter and USDC contract calls | No custom Circle Contracts deployment/management flow found. |
| Nanopayments | Partially Implemented | `@circle-fin/x402-batching` in `arc_gateway/package.json`; QMA micro-payment flow | No separate Nanopayments product API integration found. |
| StableFX | Missing | No StableFX imports, routes or execution flow found | — |
| Paymaster | Missing | No paymaster/user-operation/gas-sponsorship code found | — |

## Autonomous Agent Assessment

### Does QMA satisfy the definition?

**Partially, with a credible CLI demonstration but not across the whole product.** The CLI path satisfies the operational shape after one-time setup: an agent process has a wallet address, applies a policy to live signals, creates a QMA invoice, pays USDC through Circle Gateway/x402, settles split legs, verifies receipts and unlocks a report without a per-purchase human signature.

The browser path does **not** satisfy “without a human in the loop”: `useAgentBuyer` explicitly enters `awaiting_signature` and `frontend/src/services/x402.ts:86-88` requests a wallet signature from an injected provider. The README states this limitation directly at `README.md:251-252`.

### Human intervention required

- CLI: initial Circle CLI email/OTP login, wallet creation, wallet funding/Gateway deposit and any external spending-policy setup.
- CLI: a human must start and keep the process running; there is no hosted worker or durable session service.
- Browser: connect an injected wallet and approve each x402 signature; wallet rejection/retry/cancellation are user actions.
- Deployment: operators must configure secrets, provider wallets, Gateway/API URLs and deploy both services.

### Autonomous actions

- Parse the buyer objective and bounded policy.
- Retrieve/evaluate candidates and provider comparisons.
- Exclude candidates over budget/max price, already owned, wrong provider/tier or below minimum score.
- Choose a candidate and create a provider-bound invoice.
- In CLI live mode, invoke the Circle Agent Wallet payment executor.
- Pay creator/platform legs sequentially, recover already paid legs and validate settlement proofs.
- Submit verification, retrieve the paid report and stop/wait/retry according to the session policy.

### User-defined constraints

`agents/src/session/policy.ts:17-124` exposes budget, max price, providers, tiers, minimum score, max purchases, max attempts, duration, polling interval, cooldowns, ownership avoidance, auto-deposit and upgrade behavior.

### System-defined constraints

- Server-side candidate and price resolution (`backend/app/services/agent_decision.py:97-188`).
- Invoice-bound provider, tier, amount and recipient (`arc_gateway/server.ts:425-439`).
- Required split-leg completion before access (`backend/app/services/payment_state_machine.py:33-78,144-154`).
- Wallet self-payment and settlement-proof checks (`arc_gateway/server.ts:470-513`; `agents/src/executor/paymentExecutor.ts:204-214`).
- Invoice expiry, internal secret, URL/receipt signatures and rate limits in backend/gateway routes.

## Submission Readiness

### Checkpoint 1

Status: **Likely ready at source level; submission status not verifiable**

The repository contains a clear idea, product description, architecture and Arc/USDC payment design. Whether the project/team were entered on the hackathon platform is not represented in source code.

### Checkpoint 2

Status: **Ready as repository evidence; submission status not verifiable**

The repository contains backend, frontend, agent runtime, tests, deployment configuration and progress documentation. The latest local backend suite passes (`51 passed`), while the frontend TypeScript check passed in the combined command but the production build failed in this restricted environment while loading `frontend/vite.config.ts`; this is an environment verification result, not evidence of a runtime product failure.

### Final submission

Status: **Partially ready**

Source-level MVP pieces exist, but the following final-submission evidence is not present or cannot be proven from the repository:

- a verified current deployed end-to-end run on Arc Testnet;
- a three-minute video pitch/demo;
- a final deck;
- a public repository URL and submission-platform metadata;
- browser-side autonomous Circle Agent Wallet support;
- durable hosted autonomous sessions if the demo promises a web worker rather than a locally running CLI.

### Blockers ranked by severity

#### Critical

1. Final video and deck are absent from the repository, so the final submission package is incomplete.
2. A final deployed end-to-end demonstration is not provable from source alone; the configured URLs and environment must be checked together.

#### High

1. Browser agent is human-signature based, while the autonomous Circle Agent Wallet executor is CLI-only (`README.md:100-131`).
2. No durable hosted worker/session persistence exists; the agent loop is process-local (`agents/src/session/loop.ts:65-121`).
3. No agent-to-agent payment flow, Paymaster flow or direct Agent Stack SDK integration.

#### Medium

1. Provider comparison exists, but independent provider reputation/latency quality is not fully implemented (`README.md:253-255`).
2. Creator/platform split is ledger/accounting based rather than an on-chain split contract (`backend/app/services/circle_client.py:131-133`).
3. No App Kit, CCTP, StableFX, lending, liquidity or yield path; these are not required for the agent track but limit DeFi-track breadth.

#### Low

1. Public traction includes current/final settlement provenance, but production observability and historical trend validation are still lightweight.
2. The current source contains both legacy and rebuild deployment realities; `README.md:257-259` calls this out and operators must select the intended deployment consistently.

## Recommended Improvements

The ordering below prioritizes judging impact for the Agentic Economy track and does not imply that every Circle product is needed.

| Rank | Improvement | Judging impact | Complexity | Estimated effort | Relevant files |
|---:|---|---|---|---|---|
| 1 | Add a hosted autonomous-session worker with durable session state, policy, events, idempotent resume and cancellation | Critical: turns the CLI demonstration into a repeatable product for web users | High | 4–7 days | `backend/app/api/v1/endpoints/agent.py`, new agent-session service/repository, `agents/src/session/*`, frontend agent UI |
| 2 | Add a Circle Agent Wallet-backed web session with explicit custody/identity model and visible consent/spending limits | Critical: closes the browser-vs-CLI autonomy gap | High | 4–7 days | frontend wallet integration, backend agent-session identity binding, `agents/src/executor/*` |
| 3 | Produce a deterministic three-minute live demo showing signal selection, policy, Circle wallet payment, split settlement and unlock | Critical: directly improves final judging evidence | Medium | 1–2 days | `examples/agent_session.mjs`, `examples/README.md`, submission assets |
| 4 | Add a reproducible deployment smoke test covering API, Gateway, OpenAPI, one dry-run and one funded testnet run | High: reduces the risk of a broken final demo | Medium | 1–2 days | `render.yaml`, `vercel.json`, `tests/`, deployment scripts |
| 5 | Make provider routing a first-class scored decision: quality, price, freshness, latency, historical hit rate and ownership | High: demonstrates why autonomous routing is economically useful | Medium | 2–4 days | `backend/app/services/agent_recommendations.py`, `agent_decision.py`, provider schemas/UI |
| 6 | Add agent-to-service receipts and a public machine-readable session event stream/webhook | High: makes autonomous economic activity auditable | Medium | 2–3 days | `backend/app/api/v1/endpoints/agent.py`, payment event service, frontend event UI |
| 7 | Add Circle Agent Stack starter-kit integration or document a direct compatibility adapter with tests | Medium/High: makes the use of Circle’s agent ecosystem unambiguous | Medium | 2–4 days | `agents/`, `package.json`, `examples/`, docs |
| 8 | Add a clearly bounded Nanopayments-compatible service registry or paid provider endpoint | Medium: strengthens agent-to-service economics beyond one marketplace | Medium | 2–4 days | `arc_gateway/`, backend provider registry, `agents/src/qma/client.ts` |
| 9 | Add independent provider reputation and payout reliability metrics | Medium: improves trust and routing quality | Medium | 3–5 days | `backend/app/services/payment_events_service.py`, provider schemas/endpoints, traction UI |
| 10 | If pursuing DeFi track, add one narrow programmable-money feature such as conditional treasury release or a real App Kit/CCTP flow | Medium for agent track, high for DeFi track | High | 5–10 days | new domain service/contract integration, `backend/app/services/`, `agents/`, deployment config |

## Verification Notes

- Backend test command executed during this audit: `pytest -q` → **51 passed in 2.81s**.
- Frontend command executed in `frontend/`: `npm.cmd run typecheck` → **passed**; `npm.cmd run build` → **failed in the current restricted execution environment** while esbuild attempted to resolve `frontend/vite.config.ts` and reported `Cannot read directory "../../../../..": Access is denied.` This report does not treat that environment-specific result as proof that the source build is invalid; it remains an operational verification item before submission.
- No live payment was initiated by this audit.
- `_refs/` was not used as evidence of QMA runtime behavior.
- Secrets and environment values were not copied into this report.

## Objective Conclusion

QMA is a credible Arc Testnet agent-commerce MVP, strongest in the Agentic Economy track. It already demonstrates a real economic loop: bounded signal selection → provider-bound price/invoice → USDC x402 Gateway split settlement → receipt verification → wallet-bound report access. The main qualification is scope: autonomous execution is currently strongest in the CLI path, while the browser assistant remains a human-authorized payment flow. The project should present that distinction explicitly and prioritize a durable hosted session plus a reproducible live demo before claiming full “without a human in the loop” coverage.
