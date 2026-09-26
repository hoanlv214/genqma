# QMA CLI (`qma-cli`) NPM Packaging & Release Guide

This document standardizes the packaging, verification, and release process for the canonical QMA agent CLI and SDK (`agents/`).

---

## 1. Package Identity & Contract

- **Package Name:** `qma-cli` (canonical published name)
- **Module System:** Pure ESM (`"type": "module"`)
- **Node Engine:** `>=20`
- **Primary Binary:** `bin/qma.js` -> `$ qma agent run [options]` or `npx qma-cli agent run`
- **Main Export:** `./dist/index.js` (types: `./dist/index.d.ts`)
- **Subpath Export:** `./circle-wallet` -> `./dist/wallets/circleSigner.js` (types: `./dist/wallets/circleSigner.d.ts`)
- **Tarball Whitelist (`files`):**
  - `dist` (Compiled JavaScript & type definitions)
  - `bin` (Executable CLI wrapper)
  - `README.md`
  - `CHANGELOG.md`
  - `LICENSE`

---

## 2. Local Verification & Build Pipeline

All commands are executed from the `agents/` workspace:

```powershell
cd agents

# 1. Typecheck TypeScript source
bun run typecheck
# or: npm run typecheck

# 2. Compile to dist/
bun run build
# or: npm run build

# 3. Run comprehensive test suite (builds and executes 8 smoke harnesses)
bun run test
# or: npm test
```

### Verified Test Harnesses Included in `npm test`:
1. `scripts/cli_smoke.mjs` (CLI argument parsing and dry-run flag verification)
2. `scripts/fast_parser_smoke.mjs` (Fast natural language policy parser)
3. `scripts/qma_agent_planner_smoke.mjs` (Candidate scoring & planner behavior)
4. `scripts/session_smoke.mjs` (Session state initialization, transition & budget accounting)
5. `scripts/worker_concurrency_smoke.mjs` (Queue worker lease claiming & heartbeat behavior)
6. `scripts/payment_executor_smoke.mjs` (x402 payment signing & settlement dispatch)
7. `scripts/qma_agent_payment_smoke.mjs` (Autonomous decision & purchase execution)
8. `scripts/durable_tick_smoke.mjs` (Crash recovery & durable tick state machine)

---

## 3. Pre-Publication Dry-Run (`pack`)

Before publishing to the public registry, create and inspect the npm tarball locally to ensure no secrets or unnecessary files are packaged:

```powershell
cd agents

# Clean prior builds and pack tarball
npm pack --dry-run
```

Verify that:
- Total unpacked size is under 500 KB.
- No source `.ts` files, test files, or `.env` files are included in the tarball.
- `dist/index.js` and `bin/qma.js` are present and executable.

---

## 4. Release & Publication Flow

### A. Semantic Versioning Rules
- **PATCH (`x.y.Z`)**: Backwards-compatible bug fixes (e.g. parser fixes, error handling).
- **MINOR (`x.Y.z`)**: New backwards-compatible capabilities (e.g. new wallet signer adapter, new CLI flags).
- **MAJOR (`X.y.z`)**: Breaking API or CLI changes (e.g. changing option signatures, removing exports).

### B. Publishing Step
Ensure you are logged into the appropriate npm registry account:

```powershell
cd agents

# Verify npm auth
npm whoami

# Publish with public access
npm publish --access public
```

### C. Post-Publish Verification
Verify that the published package can be invoked cleanly by external consumers:

```powershell
# Verify version
npx qma-cli --version

# Verify help output
npx qma-cli agent run --help
```
