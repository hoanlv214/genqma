# NPM Package Gap Analysis

## 1. What blocks npm publication?
- `package.json` has `"private": true`.
- Package is named `qma-agents` (unscoped) rather than `@qma/agents`.
- No entrypoints defined (`main`, `exports`, `types`).
- `tsconfig.json` lacks `"declaration": true`, so no `.d.ts` files are emitted.
- Missing `README.md` and `LICENSE`.

## 2. What exports are unsafe?
Currently `src/index.ts` uses `export *`. This blindly leaks internal state mutators:
- `recordObservation`, `recordFailure`, `recordAction`, `recordCandidateFailure`, `recordPurchase`
- `chooseCandidate`
- `defaultSleep`

If consumers access these, they can corrupt the state machine governing budgets and cooldowns.

## 3. Which APIs should be public?
- `runAutonomousSession`
- `createSessionState`
- `normalizeSessionPolicy`
- `QmaClient`
- `createPaymentExecutor`
- `createCircleAgentWalletSigner`
- Types: `SessionPolicy`, `SessionState`
- (New) `QmaAgent` (Facade API)

## 4. Which APIs should be internal?
- All `record*` functions in `state.ts`.
- `chooseCandidate` in `loop.ts`.
- Internal formatting helpers.

## 5. What typings are missing?
Since `.d.ts` isn't generated, consumers using TypeScript get `any` or strict import errors. The `tsconfig.json` needs `"declaration": true` and `"declarationMap": true`.

## 6. What examples are missing?
There is no `examples/` directory showing minimal, readable integration snippets. We need:
- `basic.ts`
- `circle-wallet.ts`
- `event-stream.ts`

## 7. What package fields are missing?
- `main`
- `types`
- `exports`
- `version` (needs proper SemVer tracking).
