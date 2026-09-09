# qma-cli

`qma-cli` is the ESM-only command-line client and TypeScript SDK for running
bounded QMA buyer agents. It evaluates market-intelligence candidates, enforces
hard spending policy, pays x402 invoices in USDC, and records session results.

Requirements:

- Node.js 20 or newer
- A reachable QMA backend
- For live payments, either an EVM private-key signer or a configured Circle
  Agent Wallet

The default mode is dry-run. Real funds are never used unless `--live` or
`executionMode: "live"` is explicitly selected.

## Install

CLI:

```bash
npm install --global qma-cli
qma --version
qma --help
```

SDK:

```bash
npm install qma-cli
```

The package is ESM-only:

```json
{
  "type": "module"
}
```

## CLI quick start

Run one dry-run cycle:

```bash
qma agent run \
  --task "buy the best affordable BTC report" \
  --budget 0.01 \
  --max-price 0.005 \
  --run-once
```

Run a bounded dry-run session:

```bash
qma agent run \
  --task "monitor affordable funding and open-interest reports" \
  --budget 0.05 \
  --max-price 0.005 \
  --duration 10m \
  --max-purchases 5 \
  --poll 30
```

The production API default is:

```text
https://qma-api-7o9v.onrender.com
```

Use `--api http://127.0.0.1:8000` or `QMA_API_URL` for a different backend.

## Live payment modes

### Circle Agent Wallet

Install and authenticate the Circle CLI first:

```bash
npm install --global @circle-fin/cli
circle wallet login you@example.com
circle wallet create
```

Fund the wallet and its Circle Gateway balance using the Circle CLI before
starting QMA. Circle Agent Wallet mode does not automatically move on-chain
USDC into Gateway.

```bash
qma agent run \
  --live \
  --executor circle-agent-wallet \
  --wallet 0xYOUR_AGENT_WALLET \
  --no-auto-deposit \
  --task "buy the best BTC preview" \
  --budget 0.01 \
  --max-price 0.005 \
  --max-purchases 1
```

The address can also be supplied through
`CIRCLE_AGENT_WALLET_ADDRESS`. QMA delegates each x402 payment to
`circle services pay` with a per-leg maximum amount.

### Local private key

Set the key through the environment. Do not put a private key in CLI arguments,
source files, shell history, or logs.

```bash
export AGENT_PRIVATE_KEY=0x...

qma agent run \
  --live \
  --executor local-private-key \
  --task "buy the best BTC preview" \
  --budget 0.01 \
  --max-price 0.005 \
  --max-purchases 1
```

Local-key mode enables per-invoice Gateway top-up by default. Use
`--no-auto-deposit` when Gateway is already funded. `--auto-deposit` is rejected
for Circle Agent Wallet mode.

## CLI reference

Core policy:

| Option | Meaning |
|---|---|
| `--live` | Enable real payments |
| `--dry-run` | Explicitly disable real payments |
| `--budget <USDC>` | Maximum session spend |
| `--max-price <USDC>` | Maximum price per report |
| `--task <prompt>` | Agent goal |
| `--api <URL>` | QMA backend |
| `--provider <ids>` | Comma-separated provider allowlist |
| `--tier <tiers>` | `preview`, `full`, or both |
| `--min-score <0-100>` | Minimum candidate score |
| `--allow-owned` | Permit already-owned candidates |

Session bounds:

| Option | Meaning |
|---|---|
| `--duration <30s\|10m\|2h\|1d>` | Maximum session duration |
| `--max-purchases <n>` | Successful purchase limit |
| `--max-attempts <n>` | Purchase-attempt limit |
| `--until-stopped` | Run until interrupted |
| `--run-once` | Run one observation cycle |
| `--poll <seconds>` | Poll interval |
| `--cooldown <seconds>` | Symbol cooldown |
| `--failure-cooldown <seconds>` | Failed-candidate cooldown |
| `--max-failures <n>` | Failure limit per candidate |

Payment and output:

| Option | Meaning |
|---|---|
| `--executor <type>` | `local-private-key` or `circle-agent-wallet` |
| `--wallet <address>` | Circle Agent Wallet address |
| `--auto-deposit` | Enable local-key Gateway top-up |
| `--no-auto-deposit` | Require a pre-funded Gateway balance |
| `--json` | Print only the final JSON report |
| `--verbose` | Stream detailed child-process logs |
| `--event-log <path>` | Append events as JSON Lines |
| `--report-file <path>` | Write purchased report JSON |
| `-h`, `--help` | Show help |
| `-V`, `--version` | Show package version |

Unknown commands, unknown options, missing values, conflicting execution modes,
and invalid durations exit non-zero before a session starts.

## Optional LLM policy parsing

`--llm-policy` asks a local OpenAI-compatible provider to translate the task
into bounded session-policy fields once. It cannot increase the explicit
`--budget` or `--max-price`.

```bash
export GEMINI_API_KEY=...

qma agent run \
  --llm-policy \
  --llm-provider gemini \
  --llm-model gemini-2.5-flash \
  --task "watch BTC for ten minutes and buy at most two previews" \
  --budget 0.01 \
  --max-price 0.005
```

Supported providers are `openai`, `gemini`, `groq`, `openrouter`, and `ollama`.
Use `--llm-base-url` for another compatible endpoint. API keys are accepted
through environment variables only:

```text
QMA_LLM_API_KEY
OPENAI_API_KEY
GEMINI_API_KEY
GOOGLE_API_KEY
GROQ_API_KEY
OPENROUTER_API_KEY
```

Hosted QMA decision endpoints remain under server-side model control. CLI model
options are not forwarded to the hosted decision API.

## SDK quick start

Create `agent.mjs`:

```javascript
import { QmaAgent } from "qma-cli";
import { createCircleAgentWalletSigner } from "qma-cli/circle-wallet";

const signer = createCircleAgentWalletSigner({
  address: "0xYOUR_AGENT_WALLET",
  chain: "ARC-TESTNET",
});

const agent = new QmaAgent({
  apiUrl: "https://qma-api-7o9v.onrender.com",
  signer,
});

agent.on("purchase_completed", console.log);
agent.on("purchase_failed", console.error);

const report = await agent.run({
  task: "buy the best affordable BTC preview",
  executionMode: "live",
  sessionBudgetUsdc: 0.01,
  maxPricePerReportUsdc: 0.005,
  maxPurchases: 1,
});

console.log(report);
```

Run it:

```bash
node agent.mjs
```

The SDK does not automatically deposit Circle Agent Wallet funds into Gateway.

### Local BYOK planner

```javascript
import {
  OpenAiCompatibleDecisionGenerator,
  QmaAgent,
} from "qma-cli";

const agent = new QmaAgent({
  signer,
  decisionGenerator: new OpenAiCompatibleDecisionGenerator({
    provider: "gemini",
    model: "gemini-2.5-flash",
    apiKey: process.env.GEMINI_API_KEY,
  }),
});
```

The local model can author only a minimal candidate decision. QMA reloads fresh
candidates, prices and entitlements, then validates the decision against the
session policy before creating an invoice. Planner errors fail the session
instead of silently polling forever.

## Payment safety

Before any signer is invoked, the SDK verifies:

- invoice amount is positive and finite;
- each split leg has a unique ID, payment URL, destination and positive amount;
- `amount_raw` matches six-decimal `amount_usdc`;
- split-leg totals match the invoice total;
- invoice total matches the selected candidate within the configured tolerance;
- invoice total does not exceed per-report or remaining-session limits;
- the payer is not also a payment recipient.

Split legs execute sequentially and are not blindly retried after an uncertain
transport result. The SDK checks the invoice status. If paid access is
confirmed, the purchase completes; otherwise the session stops with
`payment_outcome_uncertain` to prevent a duplicate payment.

`purchase_completed` means the invoice is paid and an access token was issued.
The SDK does not download report content automatically; consumers can use the
invoice/report APIs for that step.

## Resuming session state

`QmaAgent#getState()` returns the latest `SessionState`. Pass a non-terminal
state back through `initialState`:

```javascript
const saved = agent.getState();

await agent.run({
  task: "continue monitoring BTC",
  sessionBudgetUsdc: 0.05,
  maxPricePerReportUsdc: 0.005,
  durationSeconds: 600,
  initialState: saved,
});
```

Completed and failed sessions cannot be resumed.

## Low-level runtime

```javascript
import {
  createSessionState,
  normalizeSessionPolicy,
  runAutonomousSession,
} from "qma-cli";

const policy = normalizeSessionPolicy({
  task: "monitor affordable previews",
  sessionBudgetUsdc: 0.01,
  maxPricePerReportUsdc: 0.005,
  runOnce: true,
});

const initialState = createSessionState(policy);
const controller = new AbortController();

const result = await runAutonomousSession(
  policy,
  {
    observe: async () => ({ candidates: [] }),
    purchase: async () => ({ status: "skipped" }),
    sleep: async (seconds) => {
      await new Promise((resolve) => setTimeout(resolve, seconds * 1000));
    },
  },
  controller.signal,
  initialState,
);
```

Public payment types, session policy types, planner types and invoice validation
types are exported from `qma-cli`. Circle-specific constructors are exported
from `qma-cli/circle-wallet`.

## Development and release checks

```bash
npm test
npm pack --dry-run
```

`prepack` performs a clean build and runs the smoke suite so a clean checkout
cannot publish a package without `dist`.

## License

MIT
