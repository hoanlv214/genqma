# 05. Architecture Review

This report reviews the overall codebase layout of QMA, focusing on components and modules not directly inspected in Phases 1–4, and cross-references findings against previous conclusions.

## 0. Top-Level Directory Layout

```
qma/
├── .env / .env.example / .env.local.example / .env.advanced.example
├── agents/              [NODE/TS — Buyer-side autonomous AI agent runtime & SDK]
├── arc_gateway/         [NODE/TS — Payment relay sidecar]
├── backend/             [PYTHON — FastAPI backend service]
├── data/                [Sample datasets for quantitative engine]
├── docs/                [Documentation and audit logs]
├── examples/            [Integration and smoke test scripts]
├── frontend/            [REACT/Vite web application]
├── logs/                [Runtime execution logs]
├── node_modules/        [Third-party dependencies]
├── paid_intelligence_kit/ [PYTHON package — access token & pricing primitives]
├── public/              [Legacy static assets]
├── scripts/             [Operations and database migration scripts]
├── tests/               [Pytest test suite]
├── _refs/               [Reference specifications and hackathon snapshots]
├── main.py              [Deployment shim re-exporting backend.app.main]
├── qma_engine.py        [Statistical ML engine: KMeans, LedoitWolf, NearestNeighbors]
├── market_data.py       [Market data fetchers]
├── storage.py           [Storage abstractions: JsonStorage / SupabaseStorage]
├── render.yaml          [Deployment topology: Render backend and gateway]
└── vercel.json          [Deployment topology: Vercel frontend target]
```

## 1. Backend Subsystems (`backend/app/`)

### Inspected Modules & Roles
| Directory / File | Inspected Component | Observations |
|---|---|---|
| `backend/app/core/` | `config.py`, `security_schemes.py`, `provider_registry.py`, `rate_limit.py`, `openapi_responses.py` | Centralized security headers and shared OpenAPI configuration. |
| `backend/app/repositories/` | `storage.py` | Storage facade interfacing with `paid_intelligence_kit` and persistent stores. |
| `backend/app/schemas/` | Pydantic response and request models (`agent.py`, `chat.py`, `errors.py`, `payments.py`, `providers.py`, `wallets.py`) | Strongly typed schema layer. |
| `backend/app/api/v1/router.py` | Verified | Deprecated top-level router aggregator; active routes use modular factory includes in `backend/app/main.py`. |
| `backend/app/services/security.py` | Verified | Admin token verification using `hmac.compare_digest`. |
| `backend/app/services/plugins/` | `funding_provider.py`, `oi_provider.py`, `webhook_provider.py` | Provider plugin implementations. |

## 2. Frontend Subsystems (`frontend/src/`)

- `frontend/src/main.tsx` — Application entry point initializing styles and React router.
- `frontend/src/state/` — State stores (`invoiceStore.ts`, `reportStore.ts`, `walletStore.tsx`) managing local client state via React Context and `localStorage`. No secret leaks observed.
- `frontend/src/app/` — Application shell and route declarations.

## 3. Security Scheme Alignment
Auditing `core/security_schemes.py` confirms that administrative routes enforce strict constant-time HMAC comparison via `require_admin_token()`, while public wallet telemetry gracefully redacts private payment fields when tokens are omitted.

## 4. Storage Architecture (JSON vs Supabase)
The system supports dual storage backends:
- **`JsonStorage`**: Default for local development.
- **`SupabaseStorage`**: Activated when `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are populated (configured on production Render instances).

**Scalability Finding**: In `SupabaseStorage.load_invoices()`, queries fetch recent records with a default page limit (`limit: "2000"`). At scale, settlement deduplication must be enforced via database `UNIQUE` constraints rather than in-memory dictionary scans.

## 5. Buyer-Side Autonomous Agent (`agents/`)
The `agents/` workspace houses the TypeScript agent runtime (`qma-agents`):
- **Planner (`planner/llmPlanner.ts`)**: Bounded LLM generation restricted to selecting candidate IDs.
- **Policy Engine (`policy/validateDecision.ts`)**: Deterministic policy layer enforcing budget ceilings, maximum price limits, and entitlement checks before authorizing transactions.
- **Executor (`executor/paymentExecutor.ts`)**: Integrates with Circle Agent Wallets and gasless Arc rails, enforcing self-payment guards.

## 6. Build Targets
`vercel.json` designates `frontend/dist` as the sole production web artifact, confirming that legacy static files in root `public/` are non-blocking artifacts.

## 7. Engine & Market Data
`qma_engine.py` and `market_data.py` provide quantitative analog lookups and funding rate aggregations, feeding structured inputs into the marketplace pipeline.

---
**Summary**: The modular separation across FastAPI backend services, React web applications, Arc payment relays, and TypeScript autonomous agent runners forms a cohesive and secure marketplace ecosystem.
