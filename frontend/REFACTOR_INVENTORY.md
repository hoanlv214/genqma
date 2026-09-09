# AppPage Refactor Inventory — Phase 0

Scope: `src/components/reports/AppPage.tsx` on `frontend/vite-react-rebuild`.

This is an inventory only. No runtime code was changed in Phase 0. The current
file is 3008 lines. The reviewed inventory contains 90 `useState` calls,
8 `useEffect` calls, and 7 `useMemo` calls. Function totals are intentionally
not repeated here because the previous arrow-function count included nested
callbacks and did not match the named-function inventory below.

## Source-of-truth map

| Area | Current owner | Direct consumers |
|---|---|---|
| Route composition | `src/app/routes.tsx`, `src/app/App.tsx` | `AppPage` at the `app` route |
| Wallet identity/session | `AppPage.tsx`, `src/state/walletStore.tsx`, wallet services | `AppHeader`, paywall, profile, funding and provider earnings |
| Provider/query data | `AppPage.tsx`, `src/services/providers.ts` | `SignalSidebar`, report workspace, quote and agent flows |
| Payment/unlock | `AppPage.tsx`, `src/services/invoices.ts`, `src/services/x402.ts` | `PaywallPanel`, `DepositModal`, report workspace |
| Agent purchase | `AppPage.tsx` | `AgentBuyerModal`, `AgentBuyerModalContent` |
| Provider earnings | `AppPage.tsx` | `ProviderEarningsModal` |
| Quick profile | `AppPage.tsx` | `ProfileModal` |
| Arc funding | `AppPage.tsx` | `FundArcWalletModal`, `FundArcWalletModalContent` |
| Formatting/report display | `AppPage.tsx` | `ReportWorkspace`, payment tables |

## State inventory — 61 `useState` calls

### View, metrics, query and cache

| Line | State | Initial shape / role |
|---:|---|---|
| 94 | `viewMode` | `basic \| advanced`; persisted view mode |
| 97 | `mobileActiveView` | mobile sidebar/report tab |
| 100 | `metrics` | paid count, revenue, available USDC |
| 105 | `platformSummary` | platform summary response |
| 106 | `platformPayments` | payment rows |
| 107 | `platformPaymentsPage` | payment pagination |
| 108 | `platformPaymentsTotalPages` | payment pagination |
| 109 | `platformPaymentsTotal` | payment total |
| 110 | `platformPayers` | payer rows |
| 111 | `platformPayersPage` | payer pagination |
| 112 | `platformPayersTotalPages` | payer pagination |
| 113 | `platformPayersTotal` | payer total |
| 114 | `platformTablesLoading` | platform table loading flag |
| 115 | `platformTablesError` | platform table error |
| 117 | `cacheRevision` | invalidates cached report-derived UI |
| 120 | `selectedProviderId` | selected provider |
| 121 | `providers` | provider list |
| 122 | `activeQuery` | current signal/query payload |
| 133 | `showBasicFields` | query form field visibility |
| 136 | `quotedPrices` | provider/tier quote map |

### Payment, paywall and report

| Line | State | Role |
|---:|---|---|
| 139 | `paywallOpen` | paywall visibility |
| 140 | `currentInvoice` | active invoice |
| 141 | `paymentStep` | wallet/gateway/settlement/report step |
| 142 | `paymentStepStatus` | per-step status and copy |
| 148 | `payStatusText` | payment progress text |
| 149 | `payErrorText` | payment error text |
| 150 | `paymentSuccess` | final payment success flag |
| 151 | `paySubmitting` | payment submit flag |
| 152 | `paymentDetails` | buyer balance, settlement and tx details |
| 160 | `reportDetailsOpen` | advanced report details toggle |
| 163 | `showDepositModal` | deposit modal visibility |
| 164 | `depositAmountInput` | deposit amount input |
| 167 | `unlockedReport` | unlocked report payload |
| 168 | `reportCollapsed` | report collapsed/expanded state |

### Agent buyer

| Line | State | Role |
|---:|---|---|
| 171 | `agentPrompt` | agent instruction input |
| 172 | `agentTrace` | agent trace messages |
| 174 | `agentRunning` | agent execution flag |
| 175 | `showAgentBuyerModal` | agent modal visibility |
| 176 | `agentSessionStage` | agent state-machine stage |
| 177 | `agentSelectedPick` | selected candidate |
| 178 | `agentSessionInvoice` | agent invoice |
| 179 | `agentVerifyResult` | agent verification result |
| 180 | `agentStartTime` | session start timestamp |
| 181 | `agentElapsed` | elapsed timer label |
| 182 | `agentDecisionLatency` | decision duration label |
| 183 | `agentSelectReason` | selected-candidate rationale |
| 184 | `agentRejectedReasons` | rejected-candidate rationale list |
| 190 | `progressBarStyle` | dynamic stage progress geometry |

### Configuration, wallet UI and modal state

| Line | State | Role |
|---:|---|---|
| 193 | `sellerAddress` | seller/treasury wallet |
| 194 | `adminAddress` | admin wallet |
| 195 | `arcGatewayUrl` | Gateway URL |
| 196 | `gatewayContractAddress` | Gateway contract |
| 197 | `gatewayMinterAddress` | Gateway minter |
| 198 | `arcUsdcAddress` | Arc USDC token |
| 199 | `paymentNetworkName` | payment network label |
| 200 | `creatorClaimConfig` | creator claim configuration |
| 201 | `withdrawMode` | configured withdraw mode |
| 204 | `copySuccess` | wallet copy feedback |
| 205 | `toast` | transient toast |
| 208 | `showProfileModal` | profile modal visibility |
| 209 | `showFundArcModal` | funding modal visibility |
| 210 | `showProviderEarningsModal` | earnings modal visibility |
| 211 | `providerEarningsLoading` | earnings loading flag |
| 212 | `providerEarningsError` | earnings error |
| 213 | `providerEarningsStats` | provider earnings rows |
| 214 | `selectedProviderEarningsIds` | earnings selection |
| 215 | `creatorClaimSubmitting` | creator claim submit flag |
| 216 | `providerWithdrawAmount` | withdraw amount input |
| 217 | `providerWithdrawSubmitting` | withdraw submit flag |

### Quick profile

| Line | State | Role |
|---:|---|---|
| 220 | `profileChainUsdc` | on-chain balance |
| 221 | `profileGatewayUsdc` | Gateway balance |
| 222 | `profileReportsCount` | purchased report count |
| 223 | `profileTotalSpent` | profile total spent |
| 224 | `profilePurchasedSymbols` | purchased symbols |
| 225 | `profileVerifiedPayments` | verified payment rows |
| 226 | `profileVerifiedPaymentsPage` | profile pagination |
| 227 | `profileVerifiedPaymentsTotalPages` | profile pagination |
| 228 | `profilePaymentsLoading` | profile loading flag |
| 229 | `profilePaymentsError` | profile error |

### Fund Arc wallet

| Line | State | Role |
|---:|---|---|
| 234 | `fundReadinessStatus` | funding status label |
| 235 | `fundReadinessTone` | funding status tone |
| 236 | `fundWalletStatus` | wallet readiness label |
| 237 | `fundProviderStatus` | wallet provider label |
| 238 | `fundChainStatus` | chain readiness label |
| 239 | `fundWalletUsdc` | wallet USDC display |
| 240 | `fundGatewayBalance` | Gateway balance display |
| 241 | `fundRequiredAmount` | required funding amount |
| 242 | `fundNextStep` | funding next-step copy |
| 243 | `fundPrimaryAction` | funding action descriptor |
| 244 | `fundShowAdvanced` | network detail toggle |

## Refs and derived values

- Refs: `agentChatLogRef` (172), `firstDotRef` (186), `lastDotRef` (187),
  `stageContainerRef` (188), and `quoteTimer` (495).
- `useMemo` values: `ownedProviders` (250), `activeProvider` (259),
  `walletRole` (263), `selectedProviderEarningsStats` (2466),
  `providerEarningsTotals` (2473), `providerGatewayWithdrawMax` (2511),
  and `providerWithdrawDisplayAmount` (2515).

## Effect inventory — 8 `useEffect` calls

| Lines | Purpose | Side effects / cleanup |
|---:|---|---|
| 274–278 | Sync `viewMode` to body classes and localStorage | body class and `qma_view_mode` write |
| 281–285 | Scroll agent trace to bottom | DOM scroll |
| 288–295 | Update agent elapsed time | 200ms interval cleanup |
| 298–332 | Measure agent progress bar | bounded interval and resize listener cleanup |
| 335–391 | Load config/metrics/providers and wallet account listener | fetches, accountsChanged listener cleanup |
| 394–398 | Refresh quote when query/provider changes | quote timer scheduling |
| 401–405 | Load quick profile when modal/page changes | async profile load |
| 2520–2533 | Suggest provider withdraw amount | provider withdraw input synchronization |

## Internal function inventory

The following named functions are declared in `AppPage.tsx`; nested helpers are
included where they are part of the same closure. Line numbers are current
declaration anchors.

### Shell, wallet, data loading and query

`sameAddress` (246), `updateProgressBar` (301), `handleAccountsChanged` (377),
`handleCopyAddress` (407), `showToast` (414), `loadProviders` (421),
`loadPlatformSummary` (432), `loadPlatformPayments` (445),
`loadPlatformPayers` (462), `refreshPlatformTables` (479),
`scheduleQuoteRefresh` (497), `connect` (529), `disconnect` (552),
`openQuickProfileModal` (558), `normalizeSignalPayload` (570),
`numberOrNull` (571), `signalFingerprint` (596), `signalCacheKey` (600),
`pendingInvoiceStoreKey` (612), `pendingInvoiceMatchKey` (616),
`readPendingInvoiceStore` (626), `writePendingInvoiceStore` (634),
`rememberPendingInvoice` (642), `clearPendingInvoice` (666),
`getCachedReport` (705), `getCachedReportsForSymbol` (725),
`paidBadgeText` (754), `entitlementBadgeForSignal` (759),
`openCachedReportEntry` (783), `loadAnomalyIntoQuery` (801),
`loadQuickProfileData` (839), `getOnChainUsdcBalance` (917),
`extractGatewayBalanceUsdc` (923), `refreshFundingReadiness` (943),
`handleProviderChange` (1156).

### Payment, gateway crypto and report access

`recommendationTierPrice` (1056), `recommendationTier` (1061),
`agentPendingInvoiceFor` (1066), `getLatestCachedReportForSymbolTier` (1073),
`openPaywall` (1169), `handleDepositToGateway` (1331),
`waitForTxReceipt` (1417), `saveLocalAction` (1434), `utf8ToHex` (1451),
`randomHexBytes` (1456), `randomHexNonce` (1466), `addressToBytes32` (1468),
`encodeGatewayMintCalldata` (1476), `toWord` (1484), `padTo32` (1485),
`buildCreatorClaimMessage` (1489), `buildGatewayWithdrawIntent` (1514),
`buildGatewayWithdrawTypedData` (1535), `signAndSettleX402` (1733),
`b64encode` (1950), `handleOpenUnlockedReport` (1954).

### Agent buyer

`agentPolicyPick` (1078), `handleAgentRetry` (1960),
`handleAgentCancelSession` (2023), and `handleAgentRun` (2042).

### Provider earnings

`fetchProviderEarningsStats` (1568), `providerIdsFromStats` (1593),
`syncProviderEarningsSelection` (1595), `toggleProviderEarningsSelection` (1605),
`openProviderEarningsModal` (1614), `refreshProviderEarningsModal` (1637),
`submitCreatorClaim` (1651), and `submitProviderGatewayWithdraw` (2535).

### Formatting and report rendering helpers

`formatPercentage` (2288), `formatRawPercent` (2293),
`formatCompactMoney` (2298), `normalizePercentPoint` (2307),
`formatCiRange` (2313), `reportAnalogs` (2324), `isPreviewReport` (2333),
`reportWinRateValue` (2335), `reportWinRateCiLabel` (2340),
`reportAvgProfitLabel` (2346), `reportAvgProfitCiLabel` (2351),
`reportPercentileRows` (2357), `formatDateTime` (2377), `formatUsdc` (2389),
`tierLabel` (2394), `gatewayStatusBadge` (2400),
`renderSettlementRef` (2411), `changePlatformPaymentsPage` (2442),
`changePlatformPayersPage` (2454).

## Cross-phase dependencies and extraction order

| Planned phase | Main boundary | Cross-phase dependencies |
|---:|---|---|
| 1 | pure format helpers | `normalizeTierForCache` and report data shapes need care |
| 2 | gateway crypto pure module | wallet/config addresses and payment signing callers |
| 3 | shared domain types | existing `src/types/qma.ts` already owns payment types |
| 4 | pending invoice/local cache hook | wallet, selected provider, active query and report state |
| 5 | wallet connection hook | `useWalletStore`, config, owned providers, provider selection |
| 6 | platform metrics hook | API base, paging and report/payment refresh coupling |
| 7 | providers hook | selected provider and active provider consumers |
| 8 | quote hook | active query, selected provider, timer cleanup |
| 9 | funding hook | wallet, gateway/config, connect and readiness refresh |
| 10 | quick profile hook | wallet, profile modal/page state and report reopen callback |
| 11 | provider earnings hook | wallet, crypto helpers, platform refresh and claim/withdraw UI |
| 12 | payment hook | cache hook, gateway crypto, wallet, report unlock and paywall |
| 13 | agent buyer hook | cache, providers, payment/unlock and agent modal content |
| 14 | AppPage composition | all previous hook return contracts and child props |

The highest-risk closure crossings are payment/agent/cache, provider earnings
with gateway signing, and funding readiness with wallet connection. These should
remain explicit hook parameters rather than being moved by text-only extraction.

## Phase 0 verification

- Read: root `AGENTS.md`, `frontend/AGENTS.md`, `MIGRATION_CHECKLIST.md`,
  `src/types/qma.ts`, `src/app/App.tsx`, and `src/app/routes.tsx`.
- Runtime code changed: none.
- Inventory created: `frontend/REFACTOR_INVENTORY.md`.
- Next action: wait for confirmation before Phase 1.
