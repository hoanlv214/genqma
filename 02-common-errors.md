# ⚠️ GENLAYER — DEPLOYMENT & RUNTIME ERROR CHEATSHEET
**Version 2 — internal conflicts resolved, cross-checked against official docs 2026-07-26**

Before writing or modifying any GenLayer Intelligent Contract (`.py`), follow these rules. They are battle-tested lessons from real deployment failures on `https://studio.genlayer.com/run-debug` and from real simulator / `gltest` runs.

**Project network is locked to `studionet`** (see D1 in `00-read-me.md`). Every network reference below assumes studionet.

---

## 📖 HOW TO READ THIS FILE

Each rule is tagged with its **evidence level**, because v1 of this file contained rules that contradicted each other *and* rules that contradicted the official docs. Knowing where a rule comes from tells you what to do when it fails.

| Tag | Meaning | If the rule seems wrong at runtime |
|---|---|---|
| 📗 **DOCS** | Confirmed in official GenLayer documentation | Trust it. If it fails, you have a different bug. |
| 🔬 **FIELD** | Observed in a real Studio / gltest failure, not in the docs | Version-specific. Try the documented form; if it breaks, revert to the field rule. |
| ⚖️ **RESOLVED** | v1 had two rules in conflict; this is the adjudicated version | Follow as written. |

---

## ⚖️ CONFLICT RESOLUTION TABLE (what changed from v1 and why)

| v1 said | Reality | v2 ruling |
|---|---|---|
| R14: "`u256` is NOT a valid storage type, use `bigint`" | The error text is *"use bigint **or one of sized integers** please"* — sized ints **are** valid. Bare `int` is what's forbidden. Docs explicitly show `TreeMap[Address, u256]` as valid storage. | **Misdiagnosed.** The real rule: bare `int` is forbidden in storage. `bigint` and sized ints (`u8`..`u256`, `i8`..`i256`) are both valid. Prefer `bigint` for money. See **R14** below. |
| Rule #5 showed `TreeMap[str, u256]`, R14 said `u256` fails | Direct contradiction inside the same file | **Resolved by R14 above.** Both forms are legal; the `int` in the *other* field was the actual failure. |
| Rule #7: "ALL nondet calls MUST be inside `run_nondet_unsafe`" | `gl.eq_principle.*` also legally wraps nondet calls, and docs call `gl.vm.run_nondet` the *recommended* API — `run_nondet_unsafe` is explicitly the less-safe one. | **Overstated.** Rewritten as **Rule #7** below: nondet must be inside `eq_principle.*` **or** `run_nondet*`; prefer `run_nondet`. |
| Rule #6: "Class MUST be named `Contract`" | Official examples use `WizardOfCoin`, `LlmHelloWorld`, `PredictionMarket` — all deploy fine. Real constraint is *one* `gl.Contract` subclass per module. | **Downgraded** to a safe convention, not a hard requirement. See **Rule #6**. |
| Rule #2: "NEVER reassign `TreeMap()` in `__init__`" | Some docs/repos show `self.data = TreeMap()` working. | **Kept as FIELD rule** — it genuinely fails on the Studio build this project targets. Cheap to obey, expensive to debug. |
| R19: "TreeMap keys MUST be `str`" | Docs: *"Calldata format supports mappings only with `str` keys."* That's a **calldata** constraint, not a storage one. | **Scoped** — mandatory for anything crossing a public method / view boundary; `Address` keys are fine for internal-only storage. See **R19**. |

---

## 🛡️ THE 7 CORE RULES

### 1️⃣ 🔬 FIELD — Version pragma on line 1

```python
# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
```

**Without the version line:** Studio falls back to v0.1.0 → errors:
- `Contract Queues not found`
- `Contract IdlenessPhase not found`
- `Contract RevealingPhase not found`

> ⚠️ **Verification note:** official docs examples show only the `Depends` comment, not a `# v0.2.16` line. This pragma is Studio-build-specific. **Before writing your contract, open Studio's default template and copy whatever header it ships with** — that is the authoritative version for the build you are on. Hard-coding `v0.2.16` from this file may itself become the bug once Studio bumps.
>
> The `Depends` hash `1jb45aa8...` is the one used across current official examples. `py-genlayer:test` also appears in older docs; prefer the hash.

### 2️⃣ 🔬 FIELD — Do not reassign `TreeMap()` / `DynArray()` in `__init__`

```python
# ❌ WRONG — AssertionError: Is right the same storage type? TreeMap <- TreeMap
def __init__(self):
    self.projects = TreeMap()
    self.balances = TreeMap()

# ✅ CORRECT — GenVM auto-initializes TreeMap/DynArray to empty
def __init__(self):
    self.total_supply = bigint(0)
    self.token_symbol = "TOKEN"
    # TreeMap fields are already empty — do NOT touch them here
```

> Some official material shows `self.data = TreeMap()` in `__init__`. It is version-dependent. Leaving them untouched works on **every** build, so leave them untouched.

### 3️⃣ 📗 DOCS — No `float` in public method signatures

```python
# ❌ WRONG — schema parser rejects float
@gl.public.write
def submit(self, amount: float): ...

# ✅ CORRECT — use int (multiply by 100 for cents if needed)
@gl.public.write
def submit(self, amount: int): ...
```

### 4️⃣ 📗 DOCS — Allowed public-method (calldata) types

✅ `str`, `bool`, `bytes`, `int`, sized ints (`u8`..`u256`, `i8`..`i256`), `Address`, `DynArray[T]`, `TreeMap[str, V]`
❌ `float`, `list[T]`, `dict[K, V]`, non-instantiated generics, undecorated custom classes

> Note the asymmetry with storage: bare `int` is **allowed in method signatures** but **forbidden in storage** (R14).

### 5️⃣ ⚖️ RESOLVED — Storage uses `TreeMap` / `DynArray`, never `dict` / `list`; never bare `int`

```python
class Contract(gl.Contract):
    # ✅ CORRECT
    balances: TreeMap[str, bigint]      # bigint for money — unbounded
    scores:   TreeMap[str, u256]        # sized ints are ALSO valid storage
    posts:    DynArray[str]
    owner:    Address

    # ❌ WRONG
    users: dict[str, int]               # dict forbidden
    posts: list[str]                    # list forbidden
    total: int                          # bare `int` forbidden in storage
    b:     TreeMap                      # only fully-specialized generics allowed
```

Docs state plainly: *"`int` type isn't supported on purpose."* Use `bigint` (arbitrary precision) or a sized int.

### 6️⃣ ⚖️ RESOLVED — One `gl.Contract` subclass per module; naming it `Contract` is the safe convention

```python
# ✅ SAFEST — works on every build, Studio always finds the entry point
class Contract(gl.Contract):
    ...

# ⚠️ ALSO VALID per official docs — but if Studio reports a missing entry
#    point, rename to `Contract` before debugging anything else
class DisputeCourt(gl.Contract):
    ...
```

The genuine hard rule: **only one `gl.Contract` subclass is allowed per module.** The class auto-registers itself as the main contract. Naming it `Contract` costs nothing and removes an entire failure mode — do that.

### 7️⃣ ⚖️ RESOLVED — Every `gl.nondet.*` call must live inside a nondet wrapper

Legal wrappers, in order of preference:

```python
# ✅ BEST for custom semantic validation — sandboxes validator errors
result = gl.vm.run_nondet(leader_fn, validator_fn)

# ✅ BEST for simple/known-shape results
result = gl.eq_principle.strict_eq(fn)
result = gl.eq_principle.prompt_comparative(fn, principle="...")
result = gl.eq_principle.prompt_non_comparative(fn, task="...", criteria="...")

# ⚠️ LAST RESORT — no sandbox; a validator exception becomes an
#    indistinguishable Disagree. Use only if run_nondet is unavailable,
#    and say so in a comment.
result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
```

```python
# ❌ WRONG — direct call in deterministic code → CRASH
@gl.public.write
def verify(self):
    result = gl.nondet.exec_prompt("...")

# ✅ CORRECT
@gl.public.write
def verify(self):
    def leader_fn():
        return gl.nondet.exec_prompt("...", response_format="json")

    def validator_fn(leader_res) -> bool:
        if not isinstance(leader_res, gl.vm.Return):
            return False
        # compare MEANING, not shape
        return leader_fn()["verdict"] == leader_res.calldata["verdict"]

    return gl.vm.run_nondet(leader_fn, validator_fn)
```

> `gl.eq_principle.*` are convenience wrappers built **on top of** `run_nondet` — they auto-generate the `validator_fn`. They are not an alternative mechanism. This is the resolution of the v1 "Rule #7 vs `prompt_comparative`" contradiction.

---

## 🩺 DEPLOYMENT TROUBLESHOOTING

| Symptom | Cause → Fix |
|---|---|
| `Contract Queues not found` / `IdlenessPhase not found` / `RevealingPhase not found` | Rule #1 — missing/wrong version pragma on line 1 |
| `Could not load contract schema` | **R18** (struct not `@allow_storage @dataclass`) or **R19** (non-`str` TreeMap key crossing a public boundary). Distinct from `Queues not found`. |
| `AssertionError: TreeMap <- TreeMap` on FINALIZED tx | Rule #2 — `TreeMap` reassigned in `__init__` |
| `TypeError: use bigint or one of sized integers please` | **R14** — a stored field is typed bare `int`. Change to `bigint` (or a sized int). |
| Won't compile, schema error | Rules #3, #4, #5 — forbidden types |
| `AttributeError: module 'genlayer' has no attribute 'Contract'` | **R13** — you did `import genlayer` / `import genlayer as gl` instead of `from genlayer import *` |
| `AttributeError: module 'genlayer.gl' has no attribute 'eth'` | **R15** — `gl.eth` doesn't exist; use `gl.get_contract_at(addr).emit_transfer(value=...)` |
| `gltest` raises `TypeError` on `value=` / `account=` | **R16** — use `.connect(acct).method(args=[...]).transact(value=X)` |
| Test fails with a wrong-*state* error (`"... is not awaiting review"`) | **R17** — the nondet tx silently failed consensus because mocks weren't installed, so state never advanced |
| Sidebar says "Not deployed yet" but tx is FINALIZED | Click the tx → inspect the **Result** field. `FINALIZED` ≠ `SUCCESS`. Read the traceback. |
| Deploy worked yesterday, fails today | Studio → Settings → **Reset Storage** → Confirm → hard refresh (Cmd+Shift+R) |
| Live app deployed fine but every write fails | **R21–R24** — it's the wallet, not the code. Is the connected account funded *on studionet*? |

---

## 🔧 SDK & RUNTIME RULES (R13–R17)

### R13 — 📗 DOCS — Never alias-import genlayer
Use **only** `from genlayer import *`. Never `import genlayer` or `import genlayer as gl`. The GenVM sandbox injects a fully-configured global `gl` object when the star-import executes. Re-importing manually overrides it with an empty module → `AttributeError: module 'genlayer' has no attribute 'Contract'`.

### R14 — ⚖️ RESOLVED — Bare `int` is forbidden in storage; `bigint` and sized ints are both fine

**v1 of this file got this wrong.** It claimed `u256` was rejected. Read the error text literally:

> `TypeError: use bigint or one of sized integers please`

— sized integers are explicitly offered as valid. The rejected type is bare `int`. Official docs confirm: *"`int` type isn't supported on purpose"*, alongside a valid `TreeMap[Address, u256]` example.

```python
from dataclasses import dataclass

# ❌ WRONG — bare `int` as a persisted field
@allow_storage
@dataclass
class Appeal:
    fee: int
    confidence: int

# ✅ CORRECT
@allow_storage
@dataclass
class Appeal:
    fee: bigint          # money → bigint, no overflow ceiling to reason about
    confidence: u8       # 0–100 → a sized int is fine and cheaper
```

**Practical policy for this project:** `bigint` for any monetary value; sized ints where the range is genuinely bounded and you want the tighter type. Cast to `u256`/`int` only *temporarily in memory* when calling an external API (value transfer, JSON view).

### R15 — 🔬 FIELD — `gl.eth.send_value(...)` does not exist

```python
# ❌ WRONG → AttributeError: module 'genlayer.gl' has no attribute 'eth'
gl.eth.send_value(recipient_address, u256(amount))

# ✅ CORRECT
gl.get_contract_at(recipient_address).emit_transfer(value=u256(amount))
```

To *receive* native GEN, mark the method `@gl.public.write.payable` and read the amount via `gl.message.value`.

### R16 — 🔬 FIELD — `gltest` writes use the fluent client API, not kwargs

```python
# ❌ WRONG — raises TypeError
contract.file_appeal(args=[...], value=5000, account=creator)

# ✅ CORRECT — .connect() → .method(args=[...]) → .transact(value=X)
contract.connect(creator).file_appeal(
    args=["YouTube", "DEMONETIZATION", "https://...", "https://...", "quote", "statement"]
).transact(value=5000)

# Read-only views stay simple
contract.get_appeal(args=[0]).call()
```

Run against studionet with `gltest --network studionet`. Note: `match_std_out` / `match_std_err` only work on `studionet` and `localnet`, not testnet.

### R17 — 🔬 FIELD — Mock LLM/web *before* running nondet test transactions

`run_nondet` / `run_nondet_unsafe` execute on the consensus leader. In tests without a real `OPENAI_API_KEY` or internet, live `web.render` / `exec_prompt` calls fail consensus and surface as confusing **state** errors (e.g. `"Appeal is not awaiting review"` — because the tx never finalized, so state never advanced).

The `params` dict **must not** be wrapped in an outer list (a list gets normalized to an int-indexed dict → 0 mocks registered).

```python
# ❌ WRONG — 0 mocks registered
client.provider.make_request(
    method="sim_installMocks",
    params=[{ "llm_mocks": { ... } }]
)

# ✅ CORRECT — bare dict
client.provider.make_request(
    method="sim_installMocks",
    params={
        "llm_mocks": {
            ".*": json.dumps({"verdict": "OVERTURNED", "confidence": 85,
                              "reason": "Justification..."})
        },
        "web_mocks": {
            ".*": {"status": 200, "body": "Mock page content"}
        }
    }
)
```

**Validator return type:** the simulator wraps the leader result in `gl.vm.Return`; extract the payload via `.calldata`.

```python
def validator_fn(leader_res: typing.Any) -> bool:
    if not isinstance(leader_res, gl.vm.Return):
        return False
    leader_data = leader_res.calldata   # JSON string or parsed dict/type
    ...
```

---

## 🧱 SCHEMA-LOADING ERRORS (R18–R20)

These surface at deploy time on Studio as one opaque message: **`Could not load contract schema`**. Studio could not generate the JSON schema for the contract's public interface — almost always an invalid storage type. Static Python parses fine; only the schema generator rejects it.

### R18 — 📗 DOCS — Custom storage structs must be `@allow_storage @dataclass`

There is no `Record` base class for storage structs. Subclassing a non-existent `Record` makes the schema generator unable to describe the type.

```python
from dataclasses import dataclass

# ❌ WRONG — "Record" is not the storage-struct mechanism
class Appeal(Record):
    fee: bigint

# ✅ CORRECT
@allow_storage
@dataclass
class Appeal:
    fee: bigint
    confidence: bigint
```

Construct them like normal dataclasses: `Appeal(fee=bigint(0), confidence=bigint(0))`.

**Exception — generic storage structs.** A dataclass that itself contains a `TreeMap[...]` / `DynArray[...]` field cannot be constructed with plain syntax, because storage types have a fixed memory layout and no type erasure:

```python
@allow_storage
@dataclass
class User:
    data: TreeMap[str, str]

User()                                        # ❌ error: `data` is absent
User(gl.storage.inmem_allocate(TreeMap[str, str]))   # ✅ works
```

`gl.storage.inmem_allocate(T, *args, **kwargs)` needs a **fully instantiated** type with no type variables. Required for generic storage classes only.

### R19 — ⚖️ RESOLVED — `str` keys are mandatory at the calldata boundary

Official docs: *"Calldata format supports mappings only with `str` keys, like JSON does."* That is a **calldata** constraint. Consequences:

- Any `TreeMap` that is **returned from a public view, or passed into a public method**, must be `str`-keyed. A `bigint`-keyed map here is a common cause of `Could not load contract schema`.
- A `TreeMap[Address, str]` used **purely as internal storage**, never crossing a public boundary, is legal and appears in official docs.

**Project policy: key every `TreeMap` by `str` anyway.** The cost is one conversion at the boundary; the benefit is that refactoring a private map into a public view later never breaks the schema.

```python
# ⚠️ Legal only if never exposed through a public method/view
balances: TreeMap[Address, u256]

# ✅ Safe everywhere
bounties: TreeMap[str, Bounty]      # store under str(bounty_id)
balances: TreeMap[str, bigint]      # store under _addr_str(addr) — see R20

self.bounties[str(bid)] = b
if str(bid) in self.bounties: ...
```

### R20 — 🔬 FIELD — Convert `Address` to a stable `str` defensively

`Address.as_hex` exists in current builds but attribute availability varies across versions. Wrap it:

```python
def _addr_str(addr: Address) -> str:
    try:
        return addr.as_hex
    except Exception:
        return str(addr)
```

Use `_addr_str(addr)` for TreeMap keys (R19) and when building JSON for a view.

---

## 🌐 FRONTEND / dAPP / WALLET ERRORS (R21–R24)

These do **not** come from the contract. The contract can be perfectly deployed and its schema readable via `gen_getContractSchema`, yet the live app still can't transact. The root cause is almost always the **signing wallet**.

### ✅ THE CORRECT dAPP TEST FLOW (memorize this)

> **Connect a wallet that ALREADY HOLDS a GEN balance on studionet, and let that wallet sign.** Do not generate a random burner in the browser. Do not bake a private key into the frontend. **Fund first, connect second, sign third.**

The whole class of "transaction fails on the live app" bugs collapses to one question: *does the connected account have a balance on the network the app is pointed at?* If no → nothing else matters.

### R21 — 🔬 FIELD — A randomly generated burner has 0 balance and cannot transact

`createAccount()` (genlayer-js) mints a brand-new keypair. On hosted studionet that address starts at **`0x0` balance**, and the hosted RPC does **not** auto-fund random addresses nor expose a public `sim_fund_account` faucet. The first value-bearing write is rejected with `insufficient funds`.

**Rule:** never rely on an in-browser burner for a real demo. Require the user to connect an **already-funded** MetaMask wallet and sign with it. Use `createAccount()` only where you can immediately fund it (localnet), and fund it before the first write.

### R22 — 🔬 FIELD — Never put a private key in a `VITE_` env var

Anything prefixed `VITE_` is bundled into the shipped JS and is **publicly readable**. Tolerable only for a throwaway sandbox key with worthless tokens — and even then it's a smell, and a grader who opens DevTools will see it.

```js
// ✅ MetaMask signs; no secret in the bundle
import { createClient } from 'genlayer-js';
import { studionet } from 'genlayer-js/chains';

const client = createClient({ chain: studionet, account: userAddress });
```

`createClient` accepts either a full account object (SDK signs) or **just the address string** (MetaMask signs). Pass the address string.

### R23 — 🔬 FIELD — MetaMask `'from'` RPC error = wrong network or wrong active account

Symptom (viem): `An unknown RPC error occurred. Details: 'from'`. Not a code bug. MetaMask is on a different chain than the app, so it can't construct a valid tx — or the active MetaMask account differs from the address the dApp displays.

**Rule:** on connect, explicitly switch/add the GenLayer network before signing.

```js
import { studionet } from 'genlayer-js/chains';

// ✅ Read the id from the SDK rather than hardcoding it — if GenLayer
//    changes it, your app follows automatically.
const CHAIN_ID_HEX = "0x" + studionet.id.toString(16);   // studionet = 61999 = 0xF1EF

try {
  await window.ethereum.request({
    method: "wallet_switchEthereumChain",
    params: [{ chainId: CHAIN_ID_HEX }],
  });
} catch (err) {
  if (err.code === 4902 || err.code === -32603) {          // chain not added yet
    await window.ethereum.request({
      method: "wallet_addEthereumChain",
      params: [{
        chainId: CHAIN_ID_HEX,
        chainName: "Genlayer Studio Network",
        nativeCurrency: { name: "GEN Token", symbol: "GEN", decimals: 18 },
        rpcUrls: ["https://studio.genlayer.com/api"],
        blockExplorerUrls: ["https://genlayer-explorer.vercel.app"],
      }],
    });
  } else { throw err; }
}
```

> Network params observed from the genlayer-js `studionet` chain object: **chainId `61999`** (hex `0xF1EF`), RPC `https://studio.genlayer.com/api`, symbol `GEN`, 18 decimals. Older tooling has referenced `https://studio.genlayer.com:8443/api` — if the RPC 404s, try that variant. `localnet` uses `http://127.0.0.1:4000/api`; `testnetAsimov` is a different chain entirely.

### R24 — ⚖️ RESOLVED — studionet and testnet are separate universes

The public faucet at `testnet-faucet.genlayer.foundation` funds **testnet** (Asimov/Bradbury), **not** hosted studionet. A contract deployed on studionet lives only on studionet. Switching the frontend's network means the old contract address is dead — you must redeploy and update `VITE_CONTRACT_ADDRESS`.

**Project rule (D1): everything on studionet.** Contract, frontend `chain`, wallet balance, and funding source. Fund the demo wallet from the Studio **Accounts** panel by transferring GEN from a pre-funded Studio account. Do not send anyone to the testnet faucet, and do not write "testnet" in the README.

---

## ✅ MASTER PRE-DEPLOY CHECKLIST

**Contract file**
- [ ] Line 1 matches whatever version pragma Studio's current default template ships (Rule #1)
- [ ] `Depends` comment present with the current hash
- [ ] `from genlayer import *` only — no alias imports (R13)
- [ ] Exactly one `gl.Contract` subclass, named `Contract` (Rule #6)
- [ ] `__init__` has no `TreeMap()` / `DynArray()` assignments (Rule #2)

**Types**
- [ ] No `float` in public method signatures (Rule #3)
- [ ] Public methods use only allowed calldata types (Rule #4)
- [ ] Storage uses `TreeMap` / `DynArray`, never `dict` / `list` (Rule #5)
- [ ] **No bare `int` in storage — `bigint` for money, sized ints where bounded (R14)**
- [ ] **Every custom storage struct is `@allow_storage @dataclass`, not `Record` (R18)**
- [ ] **Generic storage structs constructed via `gl.storage.inmem_allocate(...)` (R18)**
- [ ] **All `TreeMap` keys are `str`; ids/Addresses converted via `str(...)` / `_addr_str(...)` (R19, R20)**

**Non-determinism**
- [ ] Every `gl.nondet.*` call is inside `gl.eq_principle.*` or `gl.vm.run_nondet*` (Rule #7)
- [ ] Custom validators use `gl.vm.run_nondet`, not `run_nondet_unsafe` — or the fallback is documented (Rule #7)
- [ ] `validator_fn` compares **meaning** (the verdict), not schema shape
- [ ] `validator_fn` returns `False` when `leader_res` isn't a `gl.vm.Return`
- [ ] No storage reads inside the nondet block — read state before, pass via closure
- [ ] No `gl.eth.send_value` — use `gl.get_contract_at(addr).emit_transfer(value=...)` (R15)

**Tests**
- [ ] `.connect(acct).method(args=[...]).transact(value=X)`, not kwargs (R16)
- [ ] `sim_installMocks` installed before nondet test txs, `params` a **bare dict** (R17)
- [ ] Happy path + edge cases (web fail, bad JSON, zero value, double-claim)

**Frontend / demo**
- [ ] Connected wallet is **already funded on studionet** before the first write (R21, R24)
- [ ] No private key in any `VITE_` env var; MetaMask signs (R22)
- [ ] `wallet_switchEthereumChain` / `wallet_addEthereumChain` on connect (R23)
- [ ] Chain id read from `studionet.id`, not hardcoded (R23)
- [ ] Contract network, frontend `chain`, wallet balance, and funding source are all studionet (R24)
- [ ] If you ever switch networks: redeploy and update `VITE_CONTRACT_ADDRESS` (R24)

---

## 🚀 RECOMMENDED DEPLOY PROCEDURE

1. Open `https://studio.genlayer.com/run-debug`
2. **Settings → Reset Storage → Confirm**
3. **Hard refresh** (Cmd+Shift+R / Ctrl+Shift+F5)
4. Deploy a minimal `storage_test.py` **first** — verify the environment works before blaming your contract
5. If that succeeds → deploy the main contract
6. After deploy, **click the transaction** in the sidebar and verify `Result: SUCCESS` — not just `Status: FINALIZED`
7. If `Result: ERROR` → read the traceback and map it to the troubleshooting table above
8. Fund your MetaMask address from the **Accounts** panel *before* testing the frontend

---

## 🆘 WHEN A RULE HERE CONFLICTS WITH REALITY

Escalation order:
1. **`https://sdk.genlayer.com/main/_static/ai/api.txt`** — full SDK reference in one file. Fastest ground truth for signatures.
2. **`https://docs.genlayer.com/full-documentation.txt`** — full docs in one file.
3. Studio's own default contract template — authoritative for the version pragma and `Depends` hash on the build you're actually on.
4. Studio logs: Run & Debug tab → filter by execution layer (RPC Server / GenVM / Consensus) and transaction hash.

When docs and this file disagree on a **type or API signature**, docs win. When they disagree on a **Studio deploy behaviour**, this file's FIELD rules win — they came from real failures on the exact environment this project targets.

---

*Version 2 — 26/07/2026. Cross-checked against sdk.genlayer.com, docs.genlayer.com/developers/intelligent-contracts/storage, genlayer-js, and genlayer-test. Companion files: `00-read-me.md` (context + locked decisions), `01-how-to-score.md` (grading rubric).*
