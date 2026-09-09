# Technical Debt & Architecture Decision: Cross-Chain Arbiter vs. Native $GEN Settlement

> **Status:** Active Decision (Phase 2 Live Architecture)  
> **Target Upgrade:** Phase 4 (Native GenLayer $GEN Token Escrow)  
> **Hackathon Track:** GenLayer Agent Tank — Agentic Commerce Infrastructure  
> **Date:** September 2026  

---

## 1. Context & Design Rationale

During the development of **GenQMA Shield**, a key architectural choice was evaluated:
* **Option A (Current Live):** Settle micropayments in USDC on **Arc Network (Circle Gateway x402)**, while using **GenLayer Intelligent Contracts** as the decentralized, cross-chain on-chain SLA & Dispute Arbiter.
* **Option B (Future Native):** Settle all payments directly in native **`$GEN` tokens** within GenLayer contract storage using `@gl.public.write.payable` and `_Payee.emit_transfer`.

### Why Option A Was Chosen for the Primary Track:
1. **Alignment with GenLayer Hackathon Track Prompt:**
   GenLayer's *Agentic Commerce Infrastructure* track explicitly requests:
   > *"SLA and uptime enforcement. API escrow that releases against signed logs or decentralized monitoring."*  
   > *"Stablecoin payments with chargeback. One dispute API across cards, x402 and any chain."*
   
   Using GenLayer as the cross-chain dispute arbiter across Arc x402 directly satisfies this mandate.
2. **Stable Unit of Account for Quant Intelligence:**
   Autonomous agents purchasing market memory require deterministic, sub-cent pricing ($0.001 preview / $0.005 full report). Pricing directly in volatile tokens would require continuous oracle re-pegging.
3. **Circle Gateway Gasless User/Agent Experience:**
   Arc Network uses native USDC for gas abstraction. Agents do not need to manage gas tokens (e.g. ETH or native testnet gas), reducing friction for autonomous execution.
4. **Zero-Oracle Intelligent Adjudication on GenLayer:**
   The GenLayer Intelligent Contract (`0x0C2485e1918D3a41762E124a06c0Be33171508BD`) carries out the heavy decentralized consensus work:
   - Scrapes live exchange APIs (`gl.get_webpage`) without external oracles.
   - Executes 5/5 validator LLM reasoning (`gl.exec_prompt`) under strict equivalence (`gl.eq_principle.strict_eq`).
   - Determines the cryptographic verdict (`VALID` / `INVALID`) and triggers automated 80/20 release or 100% chargeback.

---

## 2. Technical Debt Recorded

| Item | Current Implementation (Cross-Chain Arbiter) | Impact / Trade-off |
|---|---|---|
| **Settlement Rail** | Arc Network x402 USDC micropayment rails. | Settlement is executed via Circle Gateway sidecar receipts coordinated by backend/frontend. |
| **Contract Balance** | GenLayer contract stores order metadata, SLA criteria, and validator consensus receipts, but does not hold native token custody. | Fund release or refund depends on the cross-chain coordination protocol rather than native contract internal balance transfers. |
| **Token Support** | Pure USDC on Arc. | Users holding only `$GEN` on GenLayer cannot currently purchase reports directly without bridging or holding USDC. |

---

## 3. Phase 4 Roadmap: Native `$GEN` Token Implementation Blueprint

When GenLayer Bradbury Mainnet launches and native `$GEN` token liquidity expands, GenQMA Shield will support **Dual-Rail Settlement** (USDC x402 + Native `$GEN`).

### Contract Upgrade Blueprint (`GenQMAShieldV2.py`):
Using the payable pattern demonstrated in projects like `DeathOfTheAuthor`:

```python
from genlayer import *
import json

class GenQMAShieldV2(gl.Contract):
    admin: Address
    treasury: Address
    platform_fee_bps: u256
    order_count: u256
    orders: TreeMap[u256, str]

    def __init__(self):
        self.admin = gl.message.sender_address
        self.treasury = gl.message.sender_address
        self.platform_fee_bps = u256(2000)  # 20%
        self.order_count = u256(0)

    @gl.public.write.payable
    def create_order_native(self, expected_anomaly: str, creator_address: str) -> u256:
        """
        Buyer locks native $GEN tokens directly into the contract escrow balance.
        """
        order_id = self.order_count + u256(1)
        self.order_count = order_id
        deposit_amount = gl.message.value

        order_data = {
            "order_id": int(order_id),
            "buyer": str(gl.message.sender_address),
            "creator": creator_address,
            "deposit_gen": str(deposit_amount),
            "expected_anomaly": expected_anomaly,
            "status": "ESCROWED",
            "verdict": "PENDING"
        }
        self.orders[order_id] = json.dumps(order_data)
        return order_id

    @gl.public.write
    def verify_and_settle_native(self, order_id: u256, report: str, evidence_url: str) -> str:
        """
        Executes multi-validator LLM consensus and transfers native $GEN:
        - VALID: 80% to creator, 20% to treasury.
        - INVALID: 100% refund to buyer.
        """
        order = json.loads(self.orders[order_id])
        assert order["status"] == "ESCROWED", "Order not in escrow"

        # 1. Non-deterministic web fetch & LLM consensus
        def verification_task():
            page_data = gl.nondet.get_webpage(evidence_url, mode="text")
            prompt = f"Verify report integrity against exchange data: {page_data}"
            return gl.nondet.exec_prompt(prompt)

        consensus = gl.eq_principle.strict_eq(verification_task)
        is_valid = "VALID" in consensus.upper()

        total_deposit = u256(int(order["deposit_gen"]))

        if is_valid:
            # 80/20 split
            platform_fee = (total_deposit * self.platform_fee_bps) // u256(10000)
            creator_payout = total_deposit - platform_fee

            # Native transfers on GenLayer
            _Payee.emit_transfer(Address(order["creator"]), creator_payout)
            _Payee.emit_transfer(self.treasury, platform_fee)
            order["status"] = "SETTLED"
        else:
            # Autonomous Chargeback (100% refund)
            _Payee.emit_transfer(Address(order["buyer"]), total_deposit)
            order["status"] = "REFUNDED"

        self.orders[order_id] = json.dumps(order)
        return json.dumps({"order_id": int(order_id), "status": order["status"]})
```

---

## 4. Summary & Action Plan

1. **Keep Arc as the live micropayment settlement rail** for the Hackathon submission to guarantee 100% reliable demo stability, stable pricing, and single-signature convenience.
2. **Present GenLayer as the Autonomous SLA Arbiter**, fulfilling the core challenge of resolving API disputes and providing zero-oracle intelligence validation.
3. **Reference this document in `GENLAYER_SUBMISSION.md` and `README.md`** as deliberate architectural sequencing.
