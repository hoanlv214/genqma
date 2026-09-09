# Quant Memory Agent (QMA)

QMA is a paid analog-retrieval terminal for crypto derivatives regimes.

It is not a direct prediction model. It answers a narrower research question:

> When the market looked like this before, what happened next?

For Lepton, QMA is positioned as a pay-per-call market intelligence agent on Arc:

> QMA scans live crypto funding anomalies, ranks which signals are worth buying, sells historical analog intelligence as USDC micro-reports, verifies Circle Gateway/x402 settlement on Arc Testnet, and tracks paid signal entitlements per wallet.

The current demo combines:

- a quant retrieval engine using historical MEXC funding/backtest data,
- a FastAPI backend,
- a short landing page at `/` for judges,
- a terminal-style web UI,
- live MEXC anomaly scanning,
- real Arc Testnet / Circle x402 batching payments,
- wallet profile, payment ledger, seller metrics, and Arcscan tx tracking.
- a reusable `paid_intelligence_kit/` primitive for query-bound paid APIs.

## Current Product Shape

QMA is best described as an agent-commerce research tool:

- Quant layer: historical regime retrieval and evidence diagnostics.
- Commerce layer: paid micro-reports through Circle x402 batching.
- UX layer: wallet-aware analyst terminal with payment flow visibility.
- Admin layer: payer breakdown, seller Gateway balances, recent payments.

The core report is a paid "regime analog" view. A buyer pays a small USDC fee, QMA verifies the Circle Gateway settlement, then unlocks a report containing matched historical analogs, weighted outcome distribution, OOD diagnostics, and evidence-quality warnings.

QMA now has two paid tiers:

- `preview`: `0.001 USDC`, lightweight regime preview with top analog hints and upgrade CTA.
- `full`: `0.005 USDC`, complete report with analog table, percentiles, confidence intervals, diagnostics, and payment evidence.

The Agent Picks panel is suggest-then-pay: the agent ranks live anomalies and recommends a tier, but the user still confirms the Arc/Circle payment in their wallet.

QMA also exposes a provider marketplace layer. The first registered provider is:

- `funding_memory`: Funding Memory Provider, backed by `QMAEngine`.

Each provider declares metadata, owner wallet, pricing, input schema, output schema, and paid report types. The current payment settlement still routes to the configured Arc/Circle treasury wallet for MVP simplicity, but invoices, ledgers, metrics, and entitlements already carry `provider_id`, `provider_owner_wallet`, and `buyer_type` so additional providers can be added without rewriting payment logic.

Paid API access is server-bound:

- invoice creation stores a fingerprint of the full query snapshot, not only the token symbol,
- payment verification requires the private `invoice_secret` returned only during invoice creation,
- successful verification returns a short-lived signed QMA access token,
- `/api/v1/analyze` requires that token and rejects changed query parameters.

Machine-readable provider API:

```http
GET  /api/v1/providers
GET  /api/v1/providers/funding_memory
POST /api/v1/payment/invoice
POST /api/v1/payment/verify
POST /api/v1/providers/funding_memory/preview
POST /api/v1/providers/funding_memory/full-report
GET  /api/v1/entitlements/wallet/{address}
GET  /api/v1/metrics
```

For external AI agents, set `buyer_type` to `agent` when creating an invoice:

```json
{
  "provider_id": "funding_memory",
  "resource_type": "qma_signal_report",
  "buyer_type": "agent",
  "tier": "full",
  "symbol": "HYPE",
  "fundingRate": -0.003,
  "marketCap": 10000000,
  "FDV": 20000000,
  "circRatio": 0.5,
  "fromATH": -70,
  "volume24h": 500000
}
```

## Repository Layout

```text
qma/
  main.py                 FastAPI app, payment verification, metrics, report API
  providers.py            Provider interface, registry, FundingMemoryProvider
  qma_engine.py           Quant retrieval engine
  storage.py              JSON/Supabase persistence backend
  index.html              Short Lepton landing page served at /
  app.html                QMA dashboard served at /app
  user.html               Wallet history page served at /user
  marketplace.html        Provider marketplace served at /marketplace
  public/
    app.js                Frontend state, wallet, payment, profile, report rendering
    user.js               Wallet profile page logic
    marketplace.js        Provider marketplace page logic
    styles.css            Shared tokens, reset, and common UI styles
    index.css             Landing-only polish and supported-by logo rail
    app.css               Dashboard layout and responsive overrides
    user.css              Wallet profile page overrides
    marketplace.css       Provider marketplace page overrides
    assets/               Favicon and partner logos
  arc_gateway/
    server.ts             Circle x402 batching sidecar
    decode-batch.ts       Batch decode helper
    package.json          Node dependencies and scripts
  paid_intelligence_kit/  Reusable paid API primitives for Arc micropayments
  docs/
    ARC_PAYMENT.md        Short Arc/Circle payment notes
    LEPTON_DEMO.md        Short demo/pitch script for the hackathon
    SUPABASE.md           Durable persistence setup
    API_SECURITY.md       Rate limit and API security notes
    CLOUDFLARE.md         Edge protection setup
  data/
    sample_funding_historical_analysis.csv
    sample_trading_analysis.csv
  payment_ledger.json     Local verified payment ledger
  paid_reports.json       Local paid entitlement/report store
  .env.example            Minimal environment template
  .env.local.example      Local development overrides
  .env.advanced.example   Optional tuning and deploy overrides
  .gitignore              Ignores secrets/logs/local runtime files
```

Data sources are currently loaded from the sibling `tin_hieu` project:

```text
tin_hieu/json/mexc/funding_historical_analysis.csv
tin_hieu/json/mexc/trading_analysis.csv
```

Override paths with:

```env
QMA_HISTORICAL_DB_PATH=...
QMA_BACKTEST_OUTCOME_PATH=...
```

## Data Pipeline

The current canonical pipeline is in `data_pipeline/`, not the older one-off scripts in `tin_hieu/`.

Run status only:

```powershell
python data_pipeline\run_pipeline.py --status
```

Run the full data update:

```powershell
python data_pipeline\run_pipeline.py
```

Run individual steps:

```powershell
python data_pipeline\run_pipeline.py --step 1
python data_pipeline\run_pipeline.py --step 2
```

Debug one funding-history token:

```powershell
python data_pipeline\step1_update_funding_raw.py --token SPCXSTOCK --workers 1 --page-size 15 --proxy-mode off --max-page-retries 1
```

If direct Python requests are reset by MEXC, try proxy mode with low concurrency:

```powershell
python data_pipeline\step1_update_funding_raw.py --token SPCXSTOCK --workers 1 --page-size 15 --proxy-mode auto --timeout 8 --max-page-retries 2
```

Step 1 uses `curl_cffi` with Chrome impersonation because MEXC often resets plain `requests` clients. The primary funding endpoint is:

```text
https://api.mexc.com/api/v1/contract/funding_rate/history
```

Fallback endpoints are disabled by default. Enable them only for debugging:

```powershell
$env:MEXC_ENABLE_FALLBACK_ENDPOINTS="true"
```

### Step 1: update raw funding history

Script:

```text
data_pipeline/step1_update_funding_raw.py
```

Inputs:

```text
tin_hieu/json/mexc/future_token_mexc_new.json
tin_hieu/list_proxy_live.txt              optional
```

Output:

```text
tin_hieu/json/mexc/funding_data/<TOKEN>_funding_full.json
```

What it does:

- reads the MEXC futures token list,
- calls MEXC funding-rate history for each token,
- appends only records newer than the last stored `settleTime`,
- keeps each token's raw history as JSON.

This replaces the older fetcher logic in `tin_hieu/mexc_funding_historical.py` for QMA runs.

### Step 2: rebuild QMA feature CSV

Script:

```text
data_pipeline/step2_rebuild_csv.py
```

Input:

```text
tin_hieu/json/mexc/funding_data/*_funding_full.json
```

Output:

```text
tin_hieu/json/mexc/funding_historical_analysis.csv
```

What it does:

- scans raw funding JSONs,
- keeps only anomaly events where `fundingRate < -0.005` by default,
- deduplicates by `(symbol, settleTime)`,
- fetches current MEXC ticker/introduce metadata for market cap, FDV, circulation, ATH distance, volume, and open interest proxy,
- appends new rows into `funding_historical_analysis.csv`.

Important limitation:

Step 2 currently enriches old funding events with current market metadata from MEXC, not point-in-time metadata from the historical `settleTime`. This is acceptable for a hackathon demo, but it can introduce look-ahead bias. A production-grade pipeline should snapshot or reconstruct point-in-time market cap, FDV, circulation, volume, and ATH distance.

### Backtest outcome CSV

QMA also requires:

```text
tin_hieu/json/mexc/trading_analysis.csv
```

This file is produced by the funding backtest scripts in `tin_hieu/`, especially the `backtest_funding_long*.py` family. It must contain the realized outcome labels that QMA joins to the funding feature rows:

```text
token, settle_time, profit_pct, candles_to_peak, risk_reward_ratio
```

The current engine performs an inner join:

```text
funding_historical_analysis.symbol + "_" + funding_historical_analysis.settleTime
trading_analysis.token + "_" + trading_analysis.settle_time
```

If an anomaly event has no matching backtest outcome row, it is not usable as a QMA analog.

### Engine data contract

`qma/qma_engine.py` expects `funding_historical_analysis.csv` to include:

```text
symbol, settleTime, fundingRate, marketCap, FDV, circRatio, fromATH(%), volume24h, amount
```

It expects `trading_analysis.csv` to include:

```text
token, settle_time, profit_pct, candles_to_peak, risk_reward_ratio
```

Rows are dropped when required fields are missing, market/volume fields are non-positive, or `circRatio` is outside `(0, 1.5]`.

Current local dataset snapshot:

```text
funding_historical_analysis.csv : 4,161 anomaly feature rows, 316 symbols
trading_analysis.csv            : 3,858 outcome rows, 463 tokens
joined rows                     : 436
clean joined rows used by QMA   : 287
join rate                       : about 10.48% of feature rows
feature date range              : 2024-02-05 to 2025-08-20
joined date range               : 2024-02-06 to 2025-07-25
```

This explains the UI diagnostic `Clean joined rows`: QMA is not using every funding event. It only uses events that also have a backtest label and pass feature-quality filters.

### Legacy analysis scripts

The older `tin_hieu` scripts are still useful as references, but they are not the main QMA refresh path:

| File | Current role |
|---|---|
| `tin_hieu/mexc_funding_historical.py` | Original MEXC fetcher. Superseded by `data_pipeline/step1_update_funding_raw.py` for QMA. |
| `tin_hieu/funding_historical_analysis.py` | Large legacy analysis file; mostly historical/experimental code plus continuous-negative-funding analysis. Not the canonical CSV builder. |
| `tin_hieu/funding_historical_analysis_updatecsv.py` | Adds `collectCycle` into a derived CSV. Optional analysis helper, not required by QMA engine today. |
| `tin_hieu/funding_historical_analysis_detail.py` | Funding range and continuous-negative-sequence analysis with charts/JSON output. Research helper. |
| `tin_hieu/funding_historical_analysis_detail copy.py` | More advanced funding-cost version of the detail script. Research helper; rename before using seriously. |
| `tin_hieu/funding_historical_analysis_v2.py` | Mostly commented/archive version around collectCycle-aware analysis. Not active pipeline code. |

## Services

Open:

```text
http://127.0.0.1:8000      landing page
http://127.0.0.1:8000/app  QMA dashboard
http://127.0.0.1:8000/docs OpenAPI docs
```

## Deployment Recommendation

For the hackathon, the safest shape is:

```text
Vercel:
  landing page / frontend shell

Railway, Render, or VPS:
  FastAPI backend
  QMA engine dependencies
  Arc Gateway sidecar
  private full dataset
```

Vercel can deploy FastAPI, but QMA has heavier Python dependencies and private data concerns. The public repo should keep sample CSVs and crawler scripts; the production backend should load the full provider dataset through `QMA_HISTORICAL_DB_PATH` and `QMA_BACKTEST_OUTCOME_PATH`.

If the landing/dashboard is served from a different origin than FastAPI, set the frontend API base:

```html
<script>
  window.QMA_API_BASE_URL = "https://qma-api.onrender.com";
</script>
```

When `QMA_API_BASE_URL` is blank, the UI uses same-origin API calls, which is ideal for local development.

Run both services locally.

Backend:

```powershell
python qma\main.py
```

Arc Gateway sidecar:

```powershell
cd qma\arc_gateway
npm install
npm start
```

Default URLs:

- QMA app: `http://127.0.0.1:8000`
- Arc Gateway sidecar: `http://127.0.0.1:3000`
- Circle Gateway API: `https://gateway-api-testnet.circle.com`
- Arcscan: `https://testnet.arcscan.app`

## Environment

Use `qma/.env.example` as the starting point. Add values from `.env.local.example` for local
development and `.env.advanced.example` only when you need to override defaults.

```env
QMA_PAYMENT_AMOUNT_USDC=0.05
QMA_ARC_SELLER_ADDRESS=0x23e7c029a287a83d80b2e084e008211658dda11d
QMA_ARC_GATEWAY_URL=http://127.0.0.1:3000
QMA_CIRCLE_GATEWAY_API=https://gateway-api-testnet.circle.com
QMA_ARC_EXPLORER=https://testnet.arcscan.app
```

Important optional variables:

```env
QMA_ARC_GATEWAY_WALLET=0x0077777d7EBA4688BDeF3E311b846F25870A19B9
QMA_INVOICE_TTL_SECONDS=900
QMA_ACCESS_TOKEN_TTL_SECONDS=300
QMA_ACCESS_TOKEN_SECRET=replace-with-a-long-random-secret
QMA_REQUIRE_COMPLETED_SETTLEMENT=false
QMA_ARC_DEFAULT_DEPOSIT_USDC=1.00
QMA_ARC_APPROVE_USDC=10.00
```

Do not commit `.env`. It may contain private keys or wallet-specific settings.

## Payment Model

QMA uses Circle x402 batching on Arc Testnet.

There are three different balances/addresses that must not be confused:

| Label | Meaning |
|---|---|
| Buyer wallet | The user's normal Arc Testnet wallet holding USDC. |
| Circle Gateway contract | The contract buyers deposit USDC into before x402 spends can happen. Default: `0x0077777d7EBA4688BDeF3E311b846F25870A19B9`. |
| Seller wallet | The QMA treasury wallet configured by `QMA_ARC_SELLER_ADDRESS`. Payments are credited through Circle Gateway and later finalized in batches. |

Payment steps:

1. User connects EVM wallet on Arc Testnet.
2. User submits a query; QMA creates an invoice.
3. UI checks buyer Circle Gateway balance.
4. If Gateway balance is too low:
   - user approves USDC allowance to the Circle Gateway contract,
   - user deposits USDC into Circle Gateway.
5. For each report, user signs an EIP-712 x402 authorization.
6. Circle accepts the authorization and returns a settlement UUID.
7. QMA verifies the settlement through Circle's transfer API.
8. The report unlocks.
9. Later, Circle batches settlements on-chain; then QMA can resolve an Arcscan tx link.

Key UX point:

- `approve` does not spend funds.
- `deposit` moves USDC from buyer wallet into Circle Gateway balance.
- `Sign payment authorization` does not create a wallet tx. It spends from Circle Gateway balance.
- Arcscan tx appears only after Circle submits the on-chain batch.

This is why a user may sign several report purchases without seeing wallet USDC change every time. The wallet was charged during deposit; later report purchases spend down Gateway balance.

## Unlock Policy

Default:

```env
QMA_REQUIRE_COMPLETED_SETTLEMENT=false
```

In this mode, QMA unlocks when Circle returns a settlement status such as `received`, `batched`, `completed`, or `confirmed`.

This matches x402-style UX: the payment authorization is accepted quickly, while the on-chain batch tx may arrive later.

Strict mode:

```env
QMA_REQUIRE_COMPLETED_SETTLEMENT=true
```

In strict mode, QMA blocks report access until Circle settlement is `completed` or `confirmed`. This makes accounting stricter but can make demos feel slow because Arc Testnet batch submission may take minutes.

Recommended hackathon demo setting:

```env
QMA_REQUIRE_COMPLETED_SETTLEMENT=false
```

The UI clearly shows whether the settlement is only accepted by Circle or already confirmed on Arcscan.

## Payment Status Semantics

| Status | Meaning | User-facing behavior |
|---|---|---|
| `received` | Circle accepted the x402 authorization. | Report can unlock in default mode; Arcscan tx pending. |
| `batched` | Settlement is in a batch pipeline. | Continue polling. |
| `completed` | Batch finalized on-chain. | Arcscan tx should be resolvable. |
| `confirmed` | Final confirmed state. | Same as completed for QMA purposes. |

The UI and `/api/v1/metrics` expose:

- seller Gateway available balance,
- seller pending batch balance,
- payer address,
- settlement id,
- Arcscan tx hash when available.

## Frontend UX

The UI is a terminal-style dashboard.

Main user workflows:

- connect wallet,
- disconnect wallet,
- view wallet profile,
- inspect buyer wallet balance vs buyer Gateway balance,
- submit paid QMA report query,
- see Circle Gateway payment flow,
- inspect settlement status and Arcscan tx,
- view historical purchased signals,
- admin-style view of recent payments and wallet usage,
- seller-only withdrawal control when connected as the seller wallet.

Important UI labels:

- Buyer Wallet: normal on-chain USDC.
- Buyer Gateway Balance: prepaid spendable balance inside Circle Gateway.
- Circle Gateway Contract: deposit target.
- Seller Gateway Available: funds available to seller after settlement.
- Seller Pending Batch: funds accepted by Circle but not yet finalized on-chain.

## API Overview

### App and Engine

```http
GET /
```

Serves the QMA terminal UI.

```http
GET /api/v1/health
```

Returns engine status, dataset profile, Arc Gateway config, seller wallet, Circle Gateway contract, seller Gateway balance, and strict-mode policy.

```http
GET /api/v1/engine/profile
```

Returns feature columns, dataset profile, cluster metadata, OOD reference thresholds, and validation warnings.

```http
GET /api/v1/providers/funding_memory/live-anomalies
```

Scans MEXC futures tickers for highly negative funding anomalies. Results are cached for 30 seconds.

```http
POST /api/v1/analyze?invoice_id=...
```

Runs QMA analog retrieval for a paid invoice.

After payment verification, include the returned access token:

```http
X-QMA-Access-Token: <access_token>
```

The request body must match the query snapshot paid by the invoice.

Body:

```json
{
  "symbol": "HYPE",
  "fundingRate": -0.012,
  "marketCap": 8000000,
  "FDV": 60000000,
  "circRatio": 0.15,
  "fromATH": -92.0,
  "volume24h": 5200000,
  "amount": 1000000
}
```

### Payments and Metrics

```http
POST /api/v1/payment/invoice
```

Creates a local invoice bound to the full query payload and returns an x402 resource URL plus a private `invoice_secret`.

```http
POST /api/v1/payment/verify?invoice_id=...
```

Verifies a Circle settlement id plus `invoice_secret` against Circle Gateway, records it in `payment_ledger.json`, and returns a short-lived `access_token` for `/api/v1/analyze`.

```http
GET /api/v1/payment/settlement/{settlement_id}
```

Fetches Circle settlement status and attempts to resolve the Arcscan batch tx.

```http
GET /api/v1/metrics
```

Returns total paid reports, revenue, seller Gateway balance, pending batch balance, payer breakdown, and recent payments.

```http
GET /api/v1/metrics/wallet/{address}
```

Returns one wallet's Gateway balance, spending history, purchased symbols, and recent payments.

```http
POST /api/v1/payment/withdraw
```

Submits a seller withdrawal flow. The backend requires Circle Gateway to return a real mint attestation and signature before the frontend opens the wallet transaction.

## Arc Gateway Sidecar

The Node service in `qma/arc_gateway/server.ts` wraps Circle's x402 batching middleware.

Main routes:

```http
GET /health
```

Returns sidecar health, network, seller, and amount.

```http
GET /qma-access
```

x402-protected resource. Without payment, returns a `PAYMENT-REQUIRED` challenge. With a valid `payment-signature`, returns a settlement id.

```http
GET /api/balance/{address}
```

Returns Circle Gateway balance for the address.

```http
GET /api/wallet-status/{address}
```

Returns on-chain Arc USDC balance and USDC allowance to the Circle Gateway contract.

```http
GET /api/deposit-calldata/{address}?amount=1.00&approveAmount=10.00
```

Builds EVM transaction calldata for:

- USDC `approve(GatewayWallet, approveAmount)`
- GatewayWallet `deposit(USDC, amount)`

```http
GET /api/settlement/{id}
GET /api/batch-tx/{id}
```

Debug helpers for settlement status and batch tx lookup.

## Quant Engine

QMA loads historical funding events and backtest outcomes, joins them by symbol/time, cleans invalid rows, and stores a feature matrix.

Feature vector:

- hybrid funding-rate z-score,
- log market cap,
- log FDV,
- circulating ratio,
- distance from ATH,
- log 24h volume,
- turnover ratio.

Retrieval:

- robust median/IQR scaling,
- Ledoit-Wolf covariance,
- Mahalanobis distance,
- dynamic KNN,
- distance-weighted and time-decayed outcome statistics,
- KMeans regime clusters,
- empirical nearest-neighbor OOD reference,
- chi-square OOD p-value,
- bootstrap confidence intervals.

Report output includes:

- top historical analogs,
- weighted win rate,
- weighted average profit,
- percentile distribution,
- effective sample size,
- distance summary,
- OOD flags,
- dataset-quality diagnostics,
- validation warnings.

Important caveat:

QMA reports are retrieval evidence, not trade guarantees. The current sample is small and outcome labels are based on peak-profit backtests. Treat confidence intervals as evidence-quality diagnostics until walk-forward validation and calibration tests are added.

## Known Caveats

### Payment caveats

- Circle settlement UUID appears before Arcscan tx.
- Arcscan tx may take minutes because Circle batches on-chain settlement.
- Seller Gateway available balance and pending batch balance are not the same as the seller wallet's normal on-chain USDC balance.
- Buyer must not be the same address as seller. Circle rejects self-transfer.
- `payment_ledger.json` is local file storage. Use a database for production.

### Quant caveats

- Joined clean sample can be small.
- Backtest outcomes may contain selection bias.
- Peak-profit labels can overstate tradability.
- Live MEXC metadata can fail or return partial fields.
- QMA should not be marketed as an alpha model until benchmark/calibration testing is complete.

### Engineering caveats

- Invoices are in memory and disappear on backend restart.
- Payment ledger persists locally, but pending invoices do not.
- CORS is open for local demo.
- Withdrawal flow is demo-level and should be hardened before production.
- Private keys and test wallets must stay out of git.

## Demo Checklist

1. Start backend and sidecar.
2. Confirm `/api/v1/health` and `http://127.0.0.1:3000/health`.
3. Use different buyer and seller wallets.
4. Keep `QMA_REQUIRE_COMPLETED_SETTLEMENT=false` for a smooth demo.
5. Open `http://127.0.0.1:8000`.
6. Connect buyer wallet.
7. Submit a live or manual token query.
8. If needed, approve and deposit into Circle Gateway.
9. Sign x402 authorization.
10. Show report unlock.
11. Show payment flow panel:
    - buyer wallet balance,
    - buyer Gateway balance,
    - Circle settlement id,
    - seller pending batch / available balance.
12. After Circle finalizes a batch, show Arcscan tx in Payment Activity.
13. Open wallet profile to show purchased signals and spend history.

## Troubleshooting

### "Payment verification failed: self_transfer"

The connected wallet is the seller wallet. Switch network to a buyer wallet or change `QMA_ARC_SELLER_ADDRESS` to a separate treasury wallet.

### Wallet USDC does not change after signing

Expected. Signing spends from Circle Gateway balance. Wallet USDC changes only during `deposit`.

### Payment stays `received`

Circle accepted the payment but has not yet produced the on-chain batch tx. Keep polling:

```text
GET /api/v1/payment/settlement/{settlement_id}
```

When status becomes `completed`, QMA backfills `transaction_hash` and `explorer_url` into `payment_ledger.json`.

### Seller has pending batch but no on-chain tx

This is normal while Circle is batching. The UI separates seller available balance and pending batch balance.

### MEXC live scanner fails

The scanner depends on external MEXC endpoints. The UI can still run manual queries if live anomaly scanning temporarily fails.

### Browser shows stale report/payment state

Reports and wallet events are cached in `localStorage`. Refresh or clear site data if testing many payment iterations.

## Production Roadmap

Highest-impact next steps:

1. Replace in-memory invoices and file ledger with Postgres.
2. Add durable background settlement polling.
3. Add authenticated admin dashboard.
4. Add walk-forward validation and calibration plots.
5. Add benchmark comparisons against naive funding strategies.
6. Harden withdrawal flow with durable accounting and automated tests.
7. Add structured logs and error tracing.
8. Add automated tests for payment state transitions.
9. Add replay protection and invoice id binding audits.
10. Package QMA as an API consumable by external agents.
