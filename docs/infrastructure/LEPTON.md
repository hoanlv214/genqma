# Lepton Hackathon Reference For QMA

Source: https://lepton.thecanteenapp.com/

This file is a QMA-oriented summary of the Lepton Agents Hackathon page. It is not a full copy of the website. Use the source link above as the canonical reference.

## Submission Facts

- Event: Lepton Agents Hackathon by Canteen, Circle, and Arc.
- Format: online, three weeks.
- Submission deadline: July 6, 2026 at 11:59 PM ET.
- Required submission materials:
  - public GitHub repository
  - recorded video walkthrough under three minutes
- Strongly encouraged:
  - live deployed product link
  - real usage/traction during the event window
  - testnet USDC payments actually flowing on Arc

## Judging Rubric

The page says judges weigh agency and traction equally, with recommended weights:

| Area | Weight | What Judges Look For | QMA Status |
| --- | ---: | --- | --- |
| Agentic Sophistication | 30% | How much the agent actually decides instead of just automating clicks. Full autonomy beats UI-only automation. | Strong if the CLI live agent is shown. Browser Judge Mode alone is only medium. |
| Traction | 30% | Real users, real testnet payments, usage volume, creators/providers earning, people actually using the product. | Biggest risk area. QMA has metrics, but needs clear numbers and real tester activity. |
| Circle Tool Usage | 20% | Effective use of Wallets, Gateway/Nanopayments, App Kit, Contracts, x402, USDC. | Strong. QMA uses Arc Testnet USDC, Circle Gateway, x402-style payment, settlement tracking, Gateway balances, and wallet-bound access. |
| Innovation | 20% | Novel approach, research insight, emergent behavior, not just a polished clone. | Strong. Market-memory reports plus a creator/provider marketplace for paid data APIs is a differentiated use case. |

## Lepton Technical Themes

Lepton emphasizes:

- nanopayments small enough for machines and sub-cent use cases
- payments settled on Arc in USDC
- agents that earn, spend, and make economic decisions
- real products with usage, not only demos
- distribution and long-term usefulness after the hackathon

QMA should be presented as:

```text
Live signal discovery
  -> agent evaluates value/price
  -> funding readiness
  -> Circle Gateway balance
  -> x402 payment on Arc
  -> wallet-bound paid report
  -> payment/report history
```

## RFB Mapping

### RFB 01: Autonomous Paying Agents

Lepton theme: agents discover, evaluate, and pay for paywalled APIs/data/compute under a budget.

Fit: primary and strongest QMA category.

What QMA already has:

- `/api/v1/agent/recommendations` ranks live market opportunities.
- Browser Judge Mode shows a readable decision trace:
  - budget
  - max price per report
  - ranked candidates
  - selected signal
  - selected tier
  - invoice creation
- `examples/agent_buyer.mjs` is the real autonomous path:
  - reads recommendations
  - checks paid entitlements
  - avoids rebuying full reports
  - upgrades preview to full when appropriate
  - creates an invoice
  - ensures Circle Gateway balance
  - signs x402 payment with `AGENT_PRIVATE_KEY`
  - verifies settlement
  - fetches the paid JSON report

Gaps:

- Browser Judge Mode still requires wallet confirmation by design. This is good for safety, but it must be explained clearly.
- To maximize score, the video should show CLI live mode, not only dry-run.

Best demo line:

```text
Browser Judge Mode keeps private keys in the judge wallet. The same payment engine runs fully autonomously in the CLI agent using an isolated test wallet.
```

### RFB 02: Selling Agent Services via Nanopayments

Lepton theme: monetize an agent/service per call, with quality tiers, creator/provider economics, and potentially dynamic pricing.

Fit: good. This is QMA's strongest secondary category after RFB 01.

What QMA already has:

- QMA sells market intelligence per call.
- Users/agents can buy:
  - Preview report
  - Full report
- Each report is paid independently; there is no subscription.
- Providers/creators are modeled as paid intelligence services:
  - `funding_memory`
  - `oi_memory`
- `/marketplace` is a live paid provider marketplace:
  - users and agents select a provider
  - creators can apply with wallet, provider id, data source, schema/sample output, and revenue share
  - provider cards show preview/full pricing, sales, revenue, creator earnings, creator share, owner wallet, and top purchased symbols
  - admin review endpoints exist for provider applications
- Provider marketplace has provider metadata, schemas, pricing, owner wallet, and revenue share.
- Invoices are provider-bound and include provider owner wallet metadata.
- `paid_intelligence_kit` supports:
  - tier pricing
  - provider-bound invoices
  - query-bound access
  - complexity score
  - optional complexity uplift via `QMA_PRICE_COMPLEXITY_UPLIFT_MAX`

Gaps:

- Default pricing is fixed:
  - Preview: 0.001 USDC
  - Full: 0.005 USDC
- Complexity-based uplift exists in code, but defaults to zero, so judges may not notice dynamic pay-per-call pricing.
- The UI should not overclaim dynamic pricing unless `QMA_PRICE_COMPLEXITY_UPLIFT_MAX` is enabled and visible.
- Creator onboarding currently submits applications for review; it does not dynamically deploy third-party provider code yet.

Low-risk improvement:

- Set `QMA_PRICE_COMPLEXITY_UPLIFT_MAX=0.25` or similar in the demo environment.
- Show the quote fields:
  - base price
  - complexity score
  - final price
- Keep the base tier language, but say:

```text
QMA supports tiered pay-per-call pricing. Complexity-based uplift is configurable per deployment/provider.
```

Marketplace demo line:

```text
QMA is not only one report product; it is a paid intelligence marketplace. A data creator can apply as a provider, define a schema and revenue wallet, and sell preview/full reports to both humans and agents.
```

### RFB 03: Agent-to-Agent Nanopayment Networks

Lepton theme: agents pay other agents for specialized services, with discovery, reputation, routing, and potentially multi-hop workflows.

Fit: weak to partial.

What QMA has:

- External buyer agents can pay QMA/provider APIs.
- Provider marketplace creates the shape of a network:
  - buyers
  - providers
  - provider listings
  - provider owner wallets
  - revenue share
  - sales/payment history
  - creator applications for new paid data/backtest providers
- Wallet-bound receipts and provider stats can become basic reputation inputs.

Gaps:

- QMA is not yet a true agent-to-agent network.
- There is no onchain reputation, broker/slashing, multi-hop payment chain, or agent identity layer.
- The current buyer mostly routes to `funding_memory`; multi-provider routing is not yet meaningful.
- Provider applications are reviewed by QMA admin rather than trustlessly deployed by agents.

How to present:

```text
QMA is not claiming full RFB03 coverage. It is an early paid-intelligence network where autonomous buyers can pay provider-owned APIs. Reputation and multi-provider routing are future extensions.
```

High-impact improvement if time remains:

- Extend `/api/v1/agent/recommendations` to include provider comparison:
  - `funding_memory`
  - `oi_memory`
  - provider price
  - provider status
  - reason selected
- This would make the RFB03/RFB01 routing story stronger without building a full network.

### RFB 04: Streaming & Continuous Payments

Lepton theme: pay-per-second or continuous authorization for compute/data/media streams.

Fit: not a primary QMA fit.

What QMA has:

- QMA is pay-per-call, not streaming.
- Agents can run repeatedly, buying data as needed.
- Live Signals refresh every 30 seconds, but the payment unit is still a report call.

Gaps:

- No pay-per-second stream.
- No continuous authorization.
- No metering by duration, bytes, or updates.

How to explain:

```text
QMA intentionally uses discrete pay-per-call settlement because a market-memory report is a bounded data product. Continuous payments would apply to a future real-time data feed mode, not the current report product.
```

Possible future extension:

```text
Live Funding Feed Mode:
  agent approves a per-update budget
  QMA charges only when a new anomaly exceeds a threshold
  report snapshots become metered events
```

Do not force QMA into RFB04 for submission. It is better to say QMA is RFB01/RFB02/RFB05 with future RFB04 potential.

### RFB 05: Nanopayment Infrastructure & Tooling

Lepton theme: SDKs, middleware, dashboards, wallet fleet tools, simulators, and tooling that make nanopayment-enabled agents easier to build.

Fit: good secondary category.

What QMA has:

- `paid_intelligence_kit/` packages reusable paid API primitives:
  - query fingerprinting
  - invoice creation
  - access token signing
  - entitlement recording
  - tier access checks
- `examples/agent_buyer.mjs` is a reusable buyer-agent example.
- `arc_gateway/` sidecar wraps the x402/Gateway interaction.
- Dashboard shows:
  - platform payments
  - payer breakdown
  - Gateway available/pending balances
  - wallet history
  - local wallet actions
- Supabase persistence and repair scripts make payment history durable.

Gaps:

- QMA is still an application first, not a generic SDK product.
- The reusable kit is present but not packaged/published.
- No one-line install or framework plugin yet.

How to present:

```text
QMA includes a reusable Paid Intelligence API Kit and an autonomous buyer example. The hackathon product is the application, while the kit shows how other paid-data APIs can reuse the same pattern.
```

### RFB 06: Creator & Publisher Monetization

Lepton theme: monetize individual pieces of content without subscriptions, often for writers, media, songs, photos, or other creator work.

Fit: good for data creators, weaker for consumer media creators.

What QMA has:

- It monetizes individual data/report pieces.
- Intelligence providers can publish paid report APIs.
- Provider owner wallets and revenue share are tracked.
- Marketplace and creator application flow are present.
- Creator application captures:
  - creator wallet
  - provider id/name
  - contact
  - data source
  - optional API base URL
  - sample schema/response
  - creator revenue share
- Marketplace displays creator economics:
  - sales
  - total revenue
  - creator earned
  - creator share
  - owner wallet
- This maps creator monetization to data/backtest providers instead of articles/music/media.

Gaps:

- QMA is not a consumer media creator product.
- It does not handle articles, music, photos, tips, royalties, or collaborative content splits.
- Provider revenue share exists, but no multi-party split graph.
- Creator applications do not yet auto-register live external APIs after approval; this is still an admin-reviewed onboarding path.

How to present:

```text
QMA applies the creator monetization idea to data creators and market-intelligence providers. A provider sells one report at a time instead of charging a subscription, and the marketplace tracks provider pricing, owner wallet, sales, and revenue share.
```

Do lead with RFB06 when talking about the marketplace, but be precise: QMA monetizes paid data/backtest/report providers, not general media creators.

## Best Submission Positioning

Primary:

```text
RFB 01: Autonomous Paying Agents
```

Secondary:

```text
RFB 02: Selling Agent Services via Nanopayments
RFB 05: Nanopayment Infrastructure & Tooling
RFB 06: Creator monetization for data/report providers
```

Supporting/future:

```text
RFB 03: Provider network and reputation can grow from payment history.
RFB 04: Future per-update live feed mode.
```

## Recommended Three-Minute Video Flow

1. Landing page:
   - show QMA thesis
   - show Platform Activity metrics
   - briefly mention QMA is also a provider marketplace
2. App:
   - show live signals
   - show Agent Picks
3. Browser Judge Mode:
   - set budget/max price
   - run agent decision
   - show trace and invoice
4. Payment:
   - show Funding Assistant if needed
   - pay Preview or Full
   - show Circle Gateway/x402 flow
   - unlock report
5. Wallet Profile:
   - show purchase history
   - show saved report snapshot
6. Marketplace:
   - show live providers, creator earnings, and creator application form
7. Terminal:
   - run `node examples/agent_buyer.mjs --live`
   - show autonomous payment and paid JSON report

## Traction Metrics To Report

Pull from QMA dashboard and Supabase/API:

- active wallets / unique payers
- reports unlocked
- preview count
- full report count
- autonomous agent purchases
- total USDC volume
- average payment size
- number of provider APIs
- top purchased symbols

For the Lepton form, write numbers plainly:

```text
During Lepton, QMA processed X paid reports across Y wallets, including Z autonomous CLI-agent purchases. Total testnet USDC volume was A USDC with an average payment size of B USDC.
```

## Current QMA Scorecard

| Category | Status | Notes |
| --- | --- | --- |
| Runs on Arc | Strong | Arc Testnet + USDC + Gateway + x402 flow. |
| Payments flowing | Strong technically, traction-dependent | Need real usage numbers in video/submission. |
| Agent decides | Strong with CLI live mode | Browser mode is safe demo; CLI is true autonomy. |
| Budget policy | Strong | Budget, max/report, skip/upgrade policy. |
| Pay-per-call service | Strong | Preview/full report endpoints. |
| Dynamic pricing | Partial | Complexity score exists; uplift disabled by default. |
| Multi-provider routing | Partial | Providers exist; recommendations mostly use Funding Memory. |
| Streaming/continuous payments | Weak | Not core to QMA. |
| Infrastructure/tooling | Good | Paid kit, gateway sidecar, examples, docs. |
| Creator monetization | Partial | Applies to data/report providers, not media creators. |

## Highest-ROI Improvements Before Submission

1. Record a live CLI agent purchase, not only dry-run.
2. Get several real test wallets to buy reports and increase traction metrics.
3. Add a short `docs/LEPTON_SUBMISSION.md` with:
   - live links
   - demo script
   - traction numbers
   - RFB mapping
4. Consider enabling a small complexity uplift in demo env:
   - `QMA_PRICE_COMPLEXITY_UPLIFT_MAX=0.25`
5. If coding time remains, add provider comparison to agent recommendations.
6. Fix any wallet copy that says "MetaMask required" when QMA supports EVM wallets like Rabby/OKX/MetaMask.

## What Not To Claim

- Do not claim QMA executes CCTP/App Kit bridging in-browser.
- Do not claim QMA is a streaming payment product.
- Do not claim RFB03 full agent-to-agent network unless provider routing/reputation is implemented.
- Do not claim fully autonomous browser payment; browser mode intentionally requires wallet confirmation.

## One-Sentence Submission Pitch

QMA is an Arc-native paid intelligence marketplace where humans and autonomous agents discover live market signals, decide whether a report is worth its price, pay per call through Circle Gateway/x402 in USDC, and receive wallet-bound historical market-memory reports.
