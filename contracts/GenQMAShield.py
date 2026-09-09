# { "Depends": "py-genlayer:test" }
from genlayer import *
import json

class GenQMAShield(gl.Contract):
    """
    GenQMA Shield: Autonomous SLA Enforcement & Dispute Resolution for Agentic Commerce.
    
    Acts as an on-chain Intelligent Arbiter for x402 micropayments.
    When an AI Agent purchases quantitative market memory / analytics:
    1. The buyer locks funds or anchors an SLA escrow.
    2. The seller submits the report summary and live exchange evidence URL.
    3. The Intelligent Contract fetches live market data via gl.get_webpage()
       and runs LLM consensus via gl.exec_prompt() to verify that the reported
       anomaly is factual, non-hallucinated, and meets SLA quality metrics.
    4. Upon consensus:
       - If VALID: Settles 80% to Provider, 20% to Platform Treasury.
       - If INVALID: Triggers autonomous chargeback/refund to the Buyer Agent.
    """
    admin: Address
    treasury: Address
    platform_fee_bps: u256  # 2000 = 20%
    order_count: u256
    orders: TreeMap[u256, str]  # Serialized Order JSON

    def __init__(self, treasury: Address):
        self.admin = gl.message.sender
        self.treasury = treasury
        self.platform_fee_bps = u256(2000)
        self.order_count = u256(0)

    @gl.public.view
    def get_order(self, order_id: u256) -> str:
        """View order status and details."""
        if order_id not in self.orders:
            return json.dumps({"error": "Order not found"})
        return self.orders[order_id]

    @gl.public.view
    def get_order_count(self) -> u256:
        """Returns total orders created."""
        return self.order_count

    @gl.public.write.payable
    def create_order(
        self,
        provider: Address,
        symbol: str,
        expected_anomaly: str,
        max_budget_raw: u256
    ) -> u256:
        """
        Creates an SLA-backed order for market intelligence.
        The buyer deposits native value (or anchors invoice stake).
        """
        self.order_count += u256(1)
        order_id = self.order_count

        order_data = {
            "order_id": int(order_id),
            "buyer": str(gl.message.sender),
            "provider": str(provider),
            "symbol": symbol,
            "expected_anomaly": expected_anomaly,
            "deposit_amount": int(gl.message.value),
            "max_budget_raw": int(max_budget_raw),
            "status": "ESCROWED",  # ESCROWED -> VERIFYING -> SETTLED / REFUNDED
            "verdict": "PENDING",
            "confidence": 0,
            "reasoning": "",
            "evidence_url": ""
        }
        self.orders[order_id] = json.dumps(order_data)
        return order_id

    @gl.public.write
    def verify_and_settle(
        self,
        order_id: u256,
        report_summary: str,
        evidence_url: str
    ) -> str:
        """
        Executes decentralized LLM validation over real-world data to enforce SLA.
        Uses GenLayer's Equivalence Principle (strict_eq) across validators.
        """
        if order_id not in self.orders:
            return json.dumps({"status": "ERROR", "message": "Order not found"})

        order = json.loads(self.orders[order_id])
        if order["status"] != "ESCROWED":
            return json.dumps({"status": "ERROR", "message": f"Order already in state {order['status']}"})

        # Non-deterministic verification task wrapped in GenLayer Equivalence Principle
        def verification_task():
            # 1. Fetch live market data directly from external exchange / radar
            market_data = ""
            try:
                market_data = gl.get_webpage(evidence_url, mode="text")
            except Exception as e:
                market_data = f"Failed to fetch {evidence_url}: {str(e)}"

            # 2. Reason over live data vs report using validator LLMs
            prompt = f"""
            You are an autonomous on-chain quantitative arbitrator in GenLayer.
            Your task: Evaluate whether the delivered Market Memory Report satisfies the buyer's SLA.
            
            [Order Details]
            Symbol: {order['symbol']}
            Expected Anomaly: {order['expected_anomaly']}
            
            [Live Market Evidence from URL: {evidence_url}]
            {market_data[:1800]}
            
            [Delivered Quantitative Report Summary]
            {report_summary}
            
            [Evaluation Rubric]
            1. Truthfulness: Does the live market data show the funding rate / open interest anomaly referenced?
            2. Soundness: Does the analog outcome distribution contain valid statistical metrics (no pure hallucination)?
            3. SLA Compliance: Did the report accurately address the symbol and regime?
            
            Return ONLY a valid JSON object without markdown formatting:
            {{"verdict": "VALID", "confidence": 95, "reasoning": "Live data confirms severe funding divergence and regime analogs align."}}
            OR if hallucinated / fraudulent:
            {{"verdict": "INVALID", "confidence": 90, "reasoning": "Funding anomaly does not exist in live exchange feed."}}
            """
            return gl.exec_prompt(prompt).strip()

        # Execute consensus among validators
        consensus_response = gl.eq_principle.strict_eq(verification_task)

        # Parse consensus JSON safely
        verdict = "VALID"
        confidence = 100
        reasoning = "Validator consensus approved"
        try:
            clean_json = consensus_response
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()
            parsed = json.loads(clean_json)
            verdict = parsed.get("verdict", "VALID").upper()
            confidence = int(parsed.get("confidence", 90))
            reasoning = str(parsed.get("reasoning", ""))
        except Exception:
            # Fallback if string contains keyword
            if "INVALID" in consensus_response.upper():
                verdict = "INVALID"
            reasoning = consensus_response[:200]

        # Update order state
        order["evidence_url"] = evidence_url
        order["verdict"] = verdict
        order["confidence"] = confidence
        order["reasoning"] = reasoning

        deposit = order["deposit_amount"]

        if verdict == "VALID" and confidence >= 70:
            order["status"] = "SETTLED"
            # 2-Leg Split: 80% to Provider, 20% to Treasury
            if deposit > 0:
                treasury_fee = (deposit * int(self.platform_fee_bps)) // 10000
                provider_amount = deposit - treasury_fee
                # Transfer native value
                gl.message.send(Address(order["provider"]), provider_amount)
                gl.message.send(self.treasury, treasury_fee)
        else:
            order["status"] = "REFUNDED"
            # Autonomous Chargeback / Refund to Buyer Agent
            if deposit > 0:
                gl.message.send(Address(order["buyer"]), deposit)

        self.orders[order_id] = json.dumps(order)
        return json.dumps({
            "order_id": int(order_id),
            "status": order["status"],
            "verdict": verdict,
            "confidence": confidence,
            "reasoning": reasoning
        })
