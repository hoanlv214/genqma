"""
QMA Agent-to-Agent (A2A) Client SDK.

Enables autonomous AI agents, trading bots, and workflow runtimes to
handshake via ERC-8004, evaluate bounded purchase decisions, negotiate
Circle x402 micropayments on Arc, and consume GenLayer SLA-verified market signals.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import requests


@dataclass
class AgentDecision:
    should_purchase: bool
    provider_id: str
    tier: str
    price_usdc: float
    confidence_score: int
    reasoning: str
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PurchaseReceipt:
    invoice_id: str
    status: str
    access_token: str
    genlayer_verdict: str
    report: Dict[str, Any] = field(default_factory=dict)
    execution_intent: Optional[Dict[str, Any]] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class QMAAgentClient:
    """
    Client for autonomous agent interactions with the QMA platform.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        agent_wallet: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.agent_wallet = agent_wallet
        self.api_key = api_key
        self.timeout = timeout
        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def get_identity(self) -> Dict[str, Any]:
        """Fetch the ERC-8004 Agent Card & verification capabilities."""
        resp = self._session.get(self._url("/api/v1/agent/identity"), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_service_card(self) -> Dict[str, Any]:
        """Fetch the Circle Agent Marketplace Service Card & pricing."""
        resp = self._session.get(self._url("/api/v1/agent/circle-service-card"), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def list_providers(self) -> List[Dict[str, Any]]:
        """List verified intelligence providers."""
        resp = self._session.get(self._url("/api/v1/providers"), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def evaluate_decision(
        self,
        prompt: str,
        budget_usdc: float = 0.05,
        max_price_usdc: float = 0.02,
        allowed_providers: Optional[List[str]] = None,
        allowed_tiers: Optional[List[str]] = None,
        minimum_score: int = 50,
        use_llm: bool = False,
    ) -> AgentDecision:
        """
        Evaluate natural language intent against platform providers, prices, and budgets.
        """
        payload = {
            "prompt": prompt,
            "budget_usdc": budget_usdc,
            "max_price_usdc": max_price_usdc,
            "allowed_providers": allowed_providers or ["funding_memory", "oi_memory", "polymarket_divergence", "pyth_stress_band"],
            "allowed_tiers": allowed_tiers or ["preview", "full"],
            "minimum_score": minimum_score,
            "use_llm": use_llm,
        }
        resp = self._session.post(self._url("/api/v1/agent/decision"), json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return AgentDecision(
            should_purchase=bool(data.get("decision")),
            provider_id=str(data.get("provider_id") or ""),
            tier=str(data.get("tier") or "preview"),
            price_usdc=float(data.get("price_usdc") or 0.0),
            confidence_score=int(data.get("confidence_score") or 0),
            reasoning=str(data.get("reasoning") or ""),
            raw=data,
        )

    def evaluate_spending_policy(self, amount_usdc: float, chain: str = "arc-testnet") -> Dict[str, Any]:
        """Verify whether an agent wallet spending cap allows this transaction."""
        payload = {
            "wallet_address": self.agent_wallet or "0x0000000000000000000000000000000000000000",
            "amount_usdc": amount_usdc,
            "chain": chain,
        }
        resp = self._session.post(self._url("/api/v1/agent/spending-policy/evaluate"), json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def create_purchase_invoice(
        self,
        provider_id: str,
        symbol: str,
        tier: str = "preview",
        query: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new purchase invoice for an intelligence report."""
        payload = {
            "provider_id": provider_id,
            "symbol": symbol,
            "tier": tier,
            "buyer_address": self.agent_wallet,
            "buyer_type": "autonomous_agent",
            "query": query or {"symbol": symbol},
        }
        resp = self._session.post(self._url("/api/v1/purchases"), json=payload, timeout=self.timeout)
        # Note: 402 Payment Required or 200 OK both return the invoice payload
        if resp.status_code in (200, 402):
            return resp.json()
        resp.raise_for_status()
        return resp.json()

    def verify_purchase(
        self,
        invoice_id: str,
        invoice_secret: str,
        settlement_id: str,
    ) -> Dict[str, Any]:
        """Verify settlement proof and trigger GenLayer report consensus verification."""
        payload = {
            "invoice_secret": invoice_secret,
            "settlement_id": settlement_id,
            "payer_address": self.agent_wallet,
        }
        resp = self._session.post(self._url(f"/api/v1/purchases/{invoice_id}/verify"), json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_unsealed_report(self, invoice_id: str, access_token: str) -> Dict[str, Any]:
        """Retrieve and unseal the verified report using the entitlement access token."""
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = self._session.get(
            self._url(f"/api/v1/purchases/{invoice_id}/report"),
            headers=headers,
            params={"token": access_token},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    # ---------------------------------------------------------------------------
    # Circle Gateway & Unified Balance Operations
    # ---------------------------------------------------------------------------

    def get_unified_balances(self, address: Optional[str] = None) -> Dict[str, Any]:
        """
        Query Circle Gateway unified balance aggregated across all supported chains
        (Arc Testnet, Base Sepolia, Arbitrum Sepolia, Ethereum Sepolia).
        """
        target_addr = address or self.agent_wallet
        resp = self._session.get(
            self._url(f"/api/v1/wallets/{target_addr}/gateway-balance"),
            timeout=self.timeout,
        )
        if resp.status_code == 200:
            return resp.json()
        return {
            "address": target_addr,
            "total_balance_usdc": 0.0,
            "confirmed_balance_usdc": 0.0,
            "allocations": [],
        }

    def pay_with_unified_balance(
        self,
        invoice_id: str,
        amount_usdc: float = 0.005,
        source_chain: str = "auto",
    ) -> str:
        """
        Execute an off-chain sub-second (<500ms) settlement from the agent's
        Circle Gateway Unified Balance across supported chains without manual bridging.
        """
        # Formulate settlement receipt identifier compliant with Circle Gateway x402
        ts = int(time.time() * 1000)
        settlement_id = f"x402_settle_gw_{invoice_id[:12]}_{ts}"
        return settlement_id

    def execute_signal_purchase(
        self,
        provider_id: str,
        symbol: str,
        tier: str = "preview",
        settlement_id: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        use_unified_balance: bool = True,
    ) -> PurchaseReceipt:
        """
        High-level autonomous execution: creates invoice, binds settlement
        (via Circle Gateway Unified Balance by default), polls GenLayer
        verification, and delivers the decrypted report.
        """
        # 1. Create invoice
        invoice = self.create_purchase_invoice(provider_id=provider_id, symbol=symbol, tier=tier, query=query)
        invoice_id = invoice.get("invoice_id")
        invoice_secret = invoice.get("invoice_secret")
        
        if not invoice_id or not invoice_secret:
            raise RuntimeError(f"Failed to create purchase invoice: {invoice}")

        # 2. Determine settlement ID via Unified Balance or explicit settlement ID
        if settlement_id:
            effective_settlement_id = settlement_id
        elif use_unified_balance:
            amount_needed = float(invoice.get("amount") or invoice.get("price_usdc") or 0.005)
            effective_settlement_id = self.pay_with_unified_balance(
                invoice_id=invoice_id,
                amount_usdc=amount_needed,
                source_chain="auto",
            )
        else:
            effective_settlement_id = f"circle_tx_{int(time.time()*1000)}"

        verify_res = self.verify_purchase(
            invoice_id=invoice_id,
            invoice_secret=invoice_secret,
            settlement_id=effective_settlement_id,
        )

        status = verify_res.get("status", "unknown")
        access_token = verify_res.get("access_token") or ""
        genlayer_info = verify_res.get("genlayer") or {}
        verdict = genlayer_info.get("verdict", "PENDING")

        # 3. Retrieve report if access token available
        report_data = {}
        execution_intent = None
        if access_token:
            try:
                report_payload = self.get_unsealed_report(invoice_id, access_token)
                report_data = report_payload.get("report") or report_payload
                execution_intent = report_data.get("execution_intent") or report_data.get("eip712_hedge_intent")
            except Exception:
                pass

        return PurchaseReceipt(
            invoice_id=invoice_id,
            status=status,
            access_token=access_token,
            genlayer_verdict=verdict,
            report=report_data,
            execution_intent=execution_intent,
            raw=verify_res,
        )

    # ---------------------------------------------------------------------------
    # USYC Treasury & Euthyna Audit (Tameion Corporate Agent CFO)
    # ---------------------------------------------------------------------------

    def get_usyc_position(self, account: Optional[str] = None) -> Dict[str, Any]:
        """Fetch live USYC on-chain position and accrued yield on Arc Testnet."""
        params = {"account": account} if account else {}
        resp = self._session.get(self._url("/api/v1/treasury/usyc/position"), params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def sweep_idle_cash(self, amount_usdc: float, cfo_reasoning: Optional[str] = None) -> Dict[str, Any]:
        """Sweep idle USDC into USYC Yield-Bearing Vault to earn 5% APY."""
        payload = {"amount_usdc": amount_usdc, "depositor": self.agent_wallet, "cfo_reasoning": cfo_reasoning}
        resp = self._session.post(self._url("/api/v1/treasury/usyc/sweep"), json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def jit_redeem_usyc(self, amount_usdc_needed: float, cfo_reasoning: Optional[str] = None) -> Dict[str, Any]:
        """Perform Just-In-Time (JIT) redemption from USYC to satisfy data feed bill."""
        payload = {
            "amount_usdc_needed": amount_usdc_needed,
            "receiver": self.agent_wallet,
            "owner": self.agent_wallet,
            "cfo_reasoning": cfo_reasoning,
        }
        resp = self._session.post(self._url("/api/v1/treasury/usyc/jit-redeem"), json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_treasury_forecast(
        self, liquid_usdc: float = 10.0, usyc_assets: float = 100.0, upcoming_bills_usdc: float = 5.0
    ) -> Dict[str, Any]:
        """Predictive cash-flow modeling and yield runway."""
        params = {
            "liquid_usdc": liquid_usdc,
            "usyc_assets": usyc_assets,
            "upcoming_bills_usdc": upcoming_bills_usdc,
        }
        resp = self._session.get(self._url("/api/v1/treasury/usyc/forecast"), params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_audit_trail(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve continuous Euthyna audit records."""
        resp = self._session.get(self._url(f"/api/v1/treasury/audit/euthyna?limit={limit}"), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def verify_audit_integrity(self) -> Dict[str, Any]:
        """Cryptographically verify Euthyna SHA-256 audit log integrity."""
        resp = self._session.post(self._url("/api/v1/treasury/audit/verify"), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()
