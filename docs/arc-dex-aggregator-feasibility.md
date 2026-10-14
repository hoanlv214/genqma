# DEX Aggregator on Arc Testnet — Feasibility & Ecosystem Analysis

> Generated: October 7, 2026 | Status: Research complete, build-ready

---

## TL;DR

Building a DEX aggregator on Arc is **highly feasible today**. The liquidity
infrastructure that makes aggregation meaningful went live with Arc mainnet
(September 16, 2026): Uniswap v2/v3/v4 is the flagship DEX, Aave v4 and Morpho
anchor credit markets, LI.FI is already wired into Circle's App Kit as the
primary aggregation layer, and multiple community AMMs (XyloNet, Lunex, ACTFUN)
are live on testnet. The recommended build path is a thin aggregator UI on top
of Circle's Swap Kit / App Kit (which calls LI.FI under the hood) augmented by
direct on-chain quotes from the Arc-deployed Uniswap pools for a best-rate
comparison.

---

## 1. Current Ecosystem State (Testnet + Mainnet)

### 1.1 Uniswap (flagship — mainnet + testnet)

Uniswap v2, v3, v4, and UniswapX are all live on Arc mainnet as of Sep 16, 2026
and are **the preferred Day 1 DEX**. An Arc-native Uniswap V2 deployment was
first community-deployed on **Arc Testnet** (chain ID 5042002) by the Arc Swap
project.

**Community Uniswap V2 contracts (Arc Testnet)**

| Contract | Address |
|---|---|
| UniswapV2Factory | `0x7483847d46db2920dd64efa676cf72dcf765814f` |
| UniswapV2Router02 | `0xe27d5d256b370604f1ff060fb489c6a8e3f8a6d9` |
| WETH9 | `0x6be2c68117ca58086bd6a14e525835584d7f721e` |
| USDC/EURC Pair | `0xb3685D16AAa06361ED28377b1319136650Fa9A13` |

Uniswap API supports Arc mainnet directly (chain ID `5042`). Full Uniswap v4
hooks are available.

### 1.2 XyloNet (testnet + mainnet)

A Curve StableSwap AMM purpose-built for stablecoin pairs on Arc, with routing
(XyloRouter), pool creation (XyloFactory), CCTP bridge integration (XyloBridge),
and ERC-4626 vaults (XyloVault). The frontend aggregates LI.FI for multi-chain
routes.

**XyloNet contracts (Arc Testnet)**

| Contract | Address |
|---|---|
| XyloStablePool (USDC/EURC) | `0x3DF3966F5138143dce7a9cFDdC2c0310ce083BB1` |
| LP token (XYLO-USDC-EURC) | same address (pool is also the LP token) |

### 1.3 Lunex (testnet)

A Curve-style StableSwap DEX + ERC-4626 yield vaults, USDC/EURC focused, 0.04%
fee. Community-built for Arc Testnet.

**Lunex contracts (Arc Testnet)**

| Contract | Address |
|---|---|
| LunexSwapPool | `0x181DA777C301Bc37B078DEf57569685678e59eD0` |
| lunex-UE-LP | `0x036e23424Cc23CA57b069188dDE9eDB6dB5fbBA6` |
| luneUSDC vault | `0x2cdFfC0dfe539cdC3019147383C458f0FBe82B04` |
| luneEURC vault | `0x458d09fb8b621c9968Fc52Aa7510d511862175A9` |

### 1.4 ArcLend (testnet)

Aave v2-style lending/borrowing protocol. Uses XyloRouter for swap routes and
Circle App Kit for FX. Supports EIP-3009 gasless supply flows.

**ArcLend contracts (Arc Testnet)**

| Contract | Address |
|---|---|
| LendingPool | `0x7e6Ab8b26223e3f622E25f44c1840e6BD85e3de2` |
| alvUSDC vault | `0x363C4eE3CfD814D3CC3bc72aCe4259453cF651EB` |
| alvEURC vault | `0xf9A7CD2c92CB6957ECeFffE2881c5Bd163a2CAeD` |
| GaslessRouter | `0xFE338289BA0f113933853759baD76B251932341a` |

### 1.5 ACTFUN / token launchpad (testnet)

Token launchpad with multi-AMM graduation supporting UNITFLOW V3 (a Uniswap V3
fork on Arc Testnet), Uniswap V2, and a Curve StableSwap. Tokens graduate into
permissionless liquidity pools across all three AMM types simultaneously.

### 1.6 Mainnet-only protocols (live Sep 16, 2026)

The following are **Arc mainnet only** — not yet on testnet at time of writing:

- **Aave v4** — primary lending market
- **Morpho** — curated credit vaults (Bitwise, Cumberland, Galaxy, Steakhouse)
- **1inch** — spot aggregator
- **LI.FI** — cross-chain routing aggregator (also powers App Kit swap)
- **fomo, Aero** — native AMMs
- **Doppler, Hibachi, edgeX** — structured products / perps / spot
- **Dinari, Bankr** — RWA and tokenized equity

### 1.7 Circle Arc contract addresses (Arc Testnet)

| Contract | Address |
|---|---|
| USDC (native ERC-20) | `0x3600000000000000000000000000000000000000` |
| EURC | `0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a` |
| USYC | `0xe9185F0c5F296Ed1797AaE4238D26CCaBEadb86C` |
| StableFX FxEscrow | `0xd68256f4D69C6BbEcB873D8588AE0Dc6B8E22E10` |
| CCTP TokenMessengerV2 | `0x8FE6B999Dc680CcFDD5Bf7EB0974218be2542DAA` |
| Gateway GatewayWallet | `0x0077777d7EBA4688BDeF3E311b846F25870A19B9` |

---

## 2. How LI.FI Interacts with Arc

LI.FI officially added **Arc Testnet** to its backend, solver, wallet, and order
services (Polymer bridge enabled for Arc Testnet ↔ OP Sepolia routes), and was
live on **Arc mainnet on Day 1** (Sep 16, 2026).

Circle's own Swap Kit / App Kit routes through LI.FI under the hood:
- `kit.swap()` and `kit.estimateSwap()` call LI.FI's routing engine.
- On testnet, only the USDC→EURC direction is confirmed to work via LI.FI
  (through LiFi Diamond → Curve StableSwap). The reverse direction
  (EURC→USDC) hits `ONCHAIN_SIMULATION_FAILED` due to limited liquidity in
  LI.FI's testnet routing — use on-chain pool quotes directly as a fallback.
- On mainnet, full bidirectional swap + cross-chain routing is available.

**Known LI.FI quirk on Arc Testnet:**
`kit.estimateSwap()` returns inaccurate rates on Arc Testnet (e.g. 17 EURC/USDC).
For a real aggregator UI, supplement or replace Kit estimates with direct
`getAmountsOut` calls to on-chain pool contracts (XyloRouter, Uniswap V2 Router).

---

## 3. Architecture for a DEX Aggregator on Arc

### 3.1 Recommended Stack

```
User Browser
    │
    ▼
React + wagmi v2 + viem (ConnectKit or RainbowKit for wallet)
    │
    ├─ Route A: Circle App Kit (kit.estimateSwap / kit.swap)
    │      └─ LI.FI routing engine
    │           └─ Uniswap v4 / v3 / v2 on Arc, cross-chain bridges
    │
    ├─ Route B: Direct on-chain quote (for Arc-native pools)
    │      ├─ UniswapV2Router02.getAmountsOut(...)
    │      ├─ XyloRouter.getAmountsOut(...) (StableSwap)
    │      └─ LunexSwapPool.get_dy(...)   (Curve invariant)
    │
    └─ Best-rate selector: compare Route A and Route B, display both,
       execute whichever the user picks
```

### 3.2 Why dual-route matters

On Arc Testnet, App Kit (LI.FI) has partial routing (USDC→EURC works; reverse
often fails). Direct AMM calls always work for pools with liquidity. On mainnet,
App Kit is more complete but direct AMM quotes are still faster (no API hop) and
give exact on-chain price impact. A good aggregator shows both and lets the user
choose.

### 3.3 Token pairs available on Arc Testnet

| Pair | Protocol | Type |
|---|---|---|
| USDC / EURC | Uniswap V2 (community) | Constant-product |
| USDC / EURC | XyloNet StableSwap | StableSwap (Curve) |
| USDC / EURC | Lunex | StableSwap (Curve) |
| USDC / EURC | LiFi Diamond | Via App Kit / LI.FI |
| USDC / cirBTC | Uniswap on mainnet | Constant-product |
| Any → USDC | LI.FI cross-chain | Bridge + swap |

---

## 4. Arc-Specific Engineering Gotchas

These are confirmed Arc Testnet findings from community builders — critical to
know before writing any aggregator contract interactions.

| Issue | Detail |
|---|---|
| `eth_estimateGas` unreliable | Every `writeContract` needs an explicit `gas:` override. `createPair` needs ~5M gas; `swapExactTokensForTokens` ~300k; `addLiquidity` ~3M. |
| `waitForTransactionReceipt` doesn't throw on revert | Check `receipt.status === "reverted"` manually — silent failures are a critical footgun. |
| No EIP-2612 `permit` on USDC | USDC on Arc uses EIP-3009 `ReceiveWithAuthorization`, not EIP-2612 `permit()`. Permit-based gasless flows revert silently. |
| No Chainlink/Pyth oracle on testnet | Price feeds are not available; use mock oracles or pool TWAPs for testnet. |
| Dual USDC event emission | Each USDC ERC-20 transfer emits two Transfer events (from `0xffff...` native mirror + from `0x3600...`). Only the `0x3600...` log is the canonical ERC20 event. |
| `getAmountsOut` returns 0 on low-liquidity pools | Check for zero-output quote explicitly; don't display 0 as a valid rate. |
| OZ 5.1+ requires `evmVersion: cancun` | Use `cancun` in `foundry.toml` / solc config to avoid `mcopy` opcode issues. |
| App Kit estimate rates unreliable on testnet | Use Frankfurter (ECB forex) or on-chain `getAmountsOut` for display rates; App Kit rates for testnet routing only. |

---

## 5. Feasibility Verdict

| Dimension | Status |
|---|---|
| Liquidity infrastructure | **Ready** — Uniswap v2/v3/v4 on mainnet, 3+ AMMs on testnet |
| Aggregation layer | **Ready** — LI.FI integrated into App Kit, supports Arc Testnet + Mainnet |
| Token pairs | **Limited on testnet** — USDC/EURC, limited cirBTC; mainnet adds USYC, BUIDL, cirBTC, WETH, etc. |
| Price oracles | **Testnet gap** — no Chainlink/Pyth yet; use pool prices or mock oracles |
| Cross-chain routing | **Ready** — LI.FI + CCTP v2 (Polymer bridge for testnet) |
| EVM tooling | **Ready** — standard wagmi/viem works; gas overrides required |
| Circle App Kit swap | **Partially working on testnet** (USDC→EURC works); full on mainnet |

### Bottom line

You can build and demo a meaningful DEX aggregator on Arc Testnet **today** with
USDC/EURC as the core pair and LI.FI + direct AMM quotes as dual routing. For
production breadth — multiple token pairs, reliable oracle pricing, deep
liquidity — Arc mainnet (post Sep 16, 2026) is the right target with Uniswap
v4 as the anchor DEX and LI.FI as the routing backbone. The main testnet
limitation is token variety (only USDC/EURC/cirBTC are real) and partial LI.FI
routing coverage.

---

## 6. Recommended Build Plan

1. **Phase 1 (Testnet)** — Swap aggregator comparing Circle App Kit (LI.FI)
   vs. direct Uniswap V2 `getAmountsOut` for USDC↔EURC. Shows best rate, executes
   via the winning route. Addresses all gas-override and receipt-status gotchas.

2. **Phase 2 (Testnet++)** — Add XyloNet StableSwap and Lunex as additional
   quote sources. Three-way comparison UI (App Kit / Uniswap V2 / StableSwap).
   Add LP position management and pool stats.

3. **Phase 3 (Mainnet)** — Wire Uniswap v4 pools via Uniswap API (chain ID 5042).
   Expand token list to cirBTC, USYC, BUIDL. Add Aave V4 and Morpho vault
   yield routes via Circle's EarnKit.

---

## 7. Key References

- [Arc contract addresses](https://docs.arc.io/arc/references/contract-addresses.md)
- [Uniswap live on Arc blog](https://blog.uniswap.org/uniswap-is-live-on-arc)
- [LI.FI × Arc integration](https://community.arc.io/en/public/blogs/arc-x-lifi-crosschain-routing-and-liquidity-access-for-arc-builders)
- [Arc EVM differences](https://docs.arc.io/arc/references/evm-differences.md)
- [Arc Swap reference app (community)](https://github.com/osr21/arc-swap)
- [XyloNet docs](https://www.xylonet.xyz/docs)
- Circle Swap Kit / App Kit: `@circle-fin/app-kit`, `@circle-fin/swap-kit`
