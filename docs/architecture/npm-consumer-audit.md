# NPM Consumer Developer Experience (DX) Audit

This audit evaluates `@qma/agents` strictly from the perspective of an external developer running `npm install @qma/agents` on day one.

---

## 1. package.json & ESM/CJS Compatibility
- **Issue**: The package is **ESM-only**. Consumers using standard CommonJS (`require('@qma/agents')`) will immediately crash with `ERR_REQUIRE_ESM`.
- **Severity**: P1
- **Evidence**: `"type": "module"` and `"main": "./dist/index.js"` with no fallback in `package.json`.
- **Proposed Patch**: Use a bundler like `tsup` or `rollup` to compile both `.mjs` and `.cjs` files, and update `"exports"`:
  ```json
  "exports": {
    "import": "./dist/index.mjs",
    "require": "./dist/index.cjs"
  }
  ```

## 2. tsconfig.json & Typings
- **Issue**: `tsconfig.json` correctly emits declarations now, but `moduleResolution: NodeNext` strictly forces `.js` extensions in local imports (`import { QmaAgent } from "./sdk/QmaAgent.js"`). If a consumer has a strict `Node` (CJS) config, their TS compiler might struggle to resolve the types.
- **Severity**: P2
- **Evidence**: `"moduleResolution": "NodeNext"` in `tsconfig.json`.
- **Proposed Patch**: Again, using a bundler like `tsup` abstracts the internal TS module resolution away from the final `.d.ts` rollout.

## 3. src/index.ts & Public Exports
- **Issue**: The types required to instantiate the `QmaAgent` facade are hidden. `QmaAgentConfig`, `QmaAgentRunOptions`, and `SessionDeps` are **not** exported. A TypeScript consumer will get implicit `any` or strict compiler errors when trying to type their configs.
- **Severity**: P0
- **Evidence**: `agents/src/index.ts` missing exports for the facade types.
- **Code**: 
  ```typescript
  // Missing from index.ts:
  export type { QmaAgentConfig, QmaAgentRunOptions } from "./sdk/QmaAgent.js";
  export type { SessionDeps } from "./session/loop.js";
  ```
- **Proposed Patch**: Explicitly export all configuration interfaces that a user must instantiate.

## 4. Tree-Shaking
- **Issue**: Modern bundlers (Webpack, Vite, Rollup) rely on the `sideEffects` flag to strip unused code (e.g., if a user imports `normalizeSessionPolicy` but not `QmaAgent`).
- **Severity**: P2
- **Evidence**: Missing `"sideEffects"` field in `package.json`.
- **Code**: `package.json`
- **Proposed Patch**: Add `"sideEffects": false` to `package.json`.

## 5. Examples & README (Authentication Leak)
- **Issue**: The `basic.ts` example and README show `const agent = new QmaAgent()`. However, `QmaClient` connects to a remote backend. There is zero mention of how an external developer authenticates (API keys, JWTs). The backend will almost certainly reject unauthenticated requests from external IP addresses with a `401 Unauthorized`.
- **Severity**: P1
- **Evidence**: `examples/basic.ts` line 4.
- **Proposed Patch**: Expose an `apiKey` field in `QmaAgentConfig` and document how to obtain an API key in the `README.md`.

---

## Conclusion

**Could a stranger successfully install the package and run an autonomous session within 5 minutes?**

**NO.**

### Blockers (Ranked by Importance)

1. **Hidden TypeScript Interfaces (P0):** A TS developer cannot write `const config: QmaAgentConfig = ...` because the type isn't exported from the root `index.ts`. It prevents strict-mode compilation.
2. **Missing Authentication DX (P1):** A developer running the example will likely get an immediate `401 Unauthorized` or `403 Forbidden` because the SDK examples don't explain how to pass an API key to the `QmaAgent` facade.
3. **CommonJS Crash (P1):** A developer using a legacy Node.js Express server (CommonJS) will crash on startup because the package is ESM-only.

### Estimated Effort to Fix
- Exporting types: **5 minutes**
- Adding `apiKey` to `QmaAgent` and documenting it: **10 minutes**
- Setting up `tsup` for ESM/CJS dual-publishing: **1 hour**

**Total effort to achieve perfect 5-minute Time-To-First-Value (TTFV): < 1.5 hours.**
