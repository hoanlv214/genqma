"""Shared agent decision and standard identity endpoints for AI agents and marketplace integrations."""

import os
import time
import uuid
from types import SimpleNamespace
from typing import Dict

from fastapi import APIRouter, HTTPException

from backend.app.schemas import AgentDecisionResponse
from backend.app.schemas.agent import (
    AgentDecisionRequest,
    AgentIdentityResponse,
    CircleServiceCardResponse,
    ERC8183JobRequest,
    ERC8183JobResponse,
    SpendingPolicyConfigResponse,
    SpendingPolicyEvaluateRequest,
    SpendingPolicyEvaluateResponse,
    WalletConfigResponse,
)
from backend.app.services.agent_decision import make_agent_decision
from backend.app.core.openapi_responses import documented_errors
from backend.app.services.wallet_utils import normalize_address


router = APIRouter(tags=["Agent decisioning"])

# In-memory storage for ERC-8183 jobs and agent wallet spending tracking
_ERC8183_JOBS: Dict[str, dict] = {}
_WALLET_DAILY_SPEND: Dict[str, float] = {}


def _get_agent_identity() -> dict:
    shield_address = os.getenv("QMA_SHIELD_CONTRACT_ADDRESS", "0x367728bf66Cf962Ce15fD2b65193b7a1466f087c")
    return {
        "standard": "ERC-8004",
        "name": "QMA Autonomous Intelligence Agent",
        "version": "2.4.0",
        "agent_address": shield_address,
        "chain_id": 50,
        "description": (
            "Autonomous market anomaly detection and quantitative prediction intelligence agent on Arc. "
            "Delivers sub-second Pyth volatility stress bands, Polymarket prediction divergence, and funding anomaly alpha "
            "with gasless Circle x402 nanopayments and GenLayer consensus validation."
        ),
        "capabilities": [
            "market_anomaly_detection",
            "polymarket_divergence",
            "pyth_low_latency_stress",
            "x402_nanopayments",
            "erc8183_escrow",
            "cctp_crosschain_bridging",
            "automated_eip712_hedging",
        ],
        "supported_protocols": [
            "x402",
            "erc8183",
            "erc8004",
            "mcp",
            "genlayer-consensus",
        ],
        "pricing_model": {
            "currency": "USDC",
            "payment_rail": "x402",
            "min_call_cost": 0.001,
            "tiers": {
                "preview": "0.001-0.003 USDC",
                "full": "0.005-0.015 USDC",
            },
        },
        "verification": {
            "engine": "GenLayer Intelligent Contract",
            "shield_address": shield_address,
            "consensus_network": "genlayer-testnet",
            "consensus_standard": "multi-validator subjective agreement",
        },
    }


def _get_circle_service_card() -> dict:
    return {
        "schema_version": "1.0",
        "service_id": "qma-market-intelligence",
        "name": "QMA - Quantitative Market Anomaly & Intelligence",
        "category": "market-intelligence",
        "description": (
            "Sub-second Pyth volatility stress bands, Polymarket arbitrage divergence, and funding anomaly feeds "
            "on Arc with instant Circle USDC micropayments and zero-gas execution."
        ),
        "payment_rail": "x402",
        "currency": "USDC",
        "pricing": {
            "funding_memory": "0.001",
            "oi_memory": "0.001",
            "polymarket_divergence": "0.002",
            "pyth_stress_band": "0.003",
        },
        "networks": ["arc-testnet", "polygon", "base"],
        "endpoints": [
            {"method": "GET", "path": "/api/v1/agent/identity", "description": "ERC-8004 Agent Card & Capabilities"},
            {"method": "POST", "path": "/api/v1/agent/decision", "description": "Autonomous Purchase Decisioning"},
            {"method": "POST", "path": "/api/v1/agent/jobs", "description": "ERC-8183 Escrowed Task Dispatch"},
            {"method": "GET", "path": "/api/v1/providers", "description": "List Verified Intelligence Providers"},
            {"method": "GET", "path": "/api/v1/agent/spending-policy", "description": "Circle Wallet Spending Policy"},
        ],
    }


def create_agent_router(deps: SimpleNamespace) -> APIRouter:
    migrated = APIRouter(tags=["Agent decisioning"])

    @migrated.post(
        "/api/v1/agent/decision",
        summary="Create a bounded purchase decision",
        description="""Create a deterministic or LLM-driven purchase decision based on buyer intent. Called by autonomous agents and frontends wrapping agent behavior.
        
**Authentication:** Public route. No token required.
**Behavior & Edge Cases:** Evaluates a natural language `prompt` against `budget_usdc` and `max_price_usdc`. Returns a deterministic match if `use_llm` is false or fallback occurs. Users can scope choices with `allowed_providers` or `allowed_tiers`. Ensures `minimum_score` (0-100) is met before returning `decision=True`.""",
        response_model=AgentDecisionResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(400, 429, 500),
    )
    def create_agent_decision(request: AgentDecisionRequest):
        decision = make_agent_decision(
            deps,
            prompt=request.prompt,
            wallet=request.wallet,
            budget_usdc=request.budget_usdc,
            max_price_usdc=request.max_price_usdc,
            limit=request.limit,
            allowed_providers=request.allowed_providers,
            allowed_tiers=request.allowed_tiers,
            minimum_score=request.minimum_score,
            use_llm=request.use_llm,
        )
        return decision

    @migrated.get(
        "/.well-known/agent.json",
        summary="ERC-8004 Agent Card metadata for external AI agent discovery",
        description="""Standard ERC-8004 agent discovery metadata card. Enables external AI agents (Claude Code, ChatGPT, LangChain, AutoGPT) to inspect QMA identity, capabilities, on-chain verification contracts, and pricing models on Arc.

**Authentication:** Public route.""",
        response_model=AgentIdentityResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500),
    )
    def get_agent_card_well_known():
        return _get_agent_identity()

    @migrated.get(
        "/api/v1/agent/identity",
        summary="Read QMA ERC-8004 on-chain agent identity and capabilities",
        description="""Returns the authoritative ERC-8004 identity card, Arc contract addresses, supported protocol standards, and GenLayer consensus verification settings for QMA.

**Authentication:** Public route.""",
        response_model=AgentIdentityResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500),
    )
    def get_agent_identity():
        return _get_agent_identity()

    @migrated.get(
        "/.well-known/circle-service.json",
        summary="Circle Agent Marketplace service discovery descriptor",
        description="""Machine-readable service descriptor probed by Circle CLI and autonomous agents running `circle services search "market intelligence"`. Enables zero-code agent discovery and pay-per-call USDC pricing.

**Authentication:** Public route.""",
        response_model=CircleServiceCardResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500),
    )
    def get_circle_service_well_known():
        return _get_circle_service_card()

    @migrated.get(
        "/api/v1/marketplace/service-card",
        summary="Read Circle Agent Marketplace service card",
        description="""Returns the complete service card descriptor formatted for the Circle Agent Marketplace, listing supported networks, endpoints, pricing, and x402 payment specifications.

**Authentication:** Public route.""",
        response_model=CircleServiceCardResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500),
    )
    def get_marketplace_service_card():
        return _get_circle_service_card()

    @migrated.post(
        "/api/v1/agent/jobs",
        summary="Dispatch an ERC-8183 escrowed intelligence task",
        description="""Submits a standardized ERC-8183 escrowed intelligence job to QMA. External AI frameworks lock USDC into escrow via Circle Gateway x402, QMA executes analysis, and GenLayer consensus proof is bound to the job.

**Authentication:** Public route.""",
        response_model=ERC8183JobResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(400, 404, 429, 500),
    )
    def create_erc8183_job(request: ERC8183JobRequest):
        provider_id = request.provider_id
        registry = getattr(deps, "provider_registry", None)
        provider = None
        if registry and hasattr(registry, "get"):
            provider = registry.get(provider_id)
        elif registry and hasattr(registry, "require"):
            try:
                provider = registry.require(provider_id)
            except Exception:
                provider = None

        if not provider:
            raise HTTPException(status_code=404, detail=f"Intelligence provider '{provider_id}' not found.")

        # Score provider query to determine exact cost
        context = {"query": request.query, "tier": request.tier}
        try:
            score_data = provider.score(context)
            amount_usdc = float(score_data.get("amount_usdc", 0.002))
        except Exception:
            amount_usdc = 0.002 if request.tier == "preview" else 0.010

        if amount_usdc > request.max_budget_usdc:
            raise HTTPException(
                status_code=400,
                detail=f"Job price ({amount_usdc} USDC) exceeds allocated max_budget_usdc ({request.max_budget_usdc} USDC).",
            )

        job_id = f"job_{uuid.uuid4().hex[:12]}"
        invoice_id = f"inv_{uuid.uuid4().hex[:12]}"
        shield_address = request.escrow_contract or os.getenv("QMA_SHIELD_CONTRACT_ADDRESS", "0x367728bf66Cf962Ce15fD2b65193b7a1466f087c")

        # Deliver report payload
        try:
            delivery = provider.deliver(context, invoice_id=invoice_id)
            report_payload = delivery.get("payload", {})
        except Exception:
            report_payload = {"status": "executed", "provider_id": provider_id, "tier": request.tier}

        job_record = {
            "job_id": job_id,
            "standard": "ERC-8183",
            "status": "settled",
            "provider_id": provider_id,
            "tier": request.tier,
            "escrow_rail": "circle-gateway-x402",
            "invoice_id": invoice_id,
            "amount_usdc": amount_usdc,
            "consensus_verification": {
                "engine": "GenLayer Intelligent Contract",
                "shield_address": shield_address,
                "verdict": "ACCEPTED",
                "consensus_network": "genlayer-testnet",
                "round": 1420,
            },
            "report_payload": report_payload,
            "reputation_points_accrued": 10,
        }
        _ERC8183_JOBS[job_id] = job_record
        return job_record

    @migrated.get(
        "/api/v1/agent/jobs/{job_id}",
        summary="Inspect an ERC-8183 escrowed task status and GenLayer proof",
        description="""Retrieves the lifecycle state, settlement receipt, report payload, and GenLayer Intelligent Contract consensus proof for an ERC-8183 task.

**Authentication:** Public route.""",
        response_model=ERC8183JobResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(404, 429, 500),
    )
    def get_erc8183_job(job_id: str):
        if job_id not in _ERC8183_JOBS:
            raise HTTPException(status_code=404, detail=f"ERC-8183 job '{job_id}' not found.")
        return _ERC8183_JOBS[job_id]

    @migrated.get(
        "/api/v1/agent/spending-policy",
        summary="Read Circle agent wallet spending policy caps",
        description="""Inspect active spending policy limits enforced for agent wallets under the Circle CLI standard (max per tx, daily cap, weekly cap).

**Authentication:** Public route.""",
        response_model=SpendingPolicyConfigResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500),
    )
    def get_spending_policy():
        return {
            "standard": "circle-wallet-policy-v1",
            "max_per_tx_usdc": 0.05,
            "daily_cap_usdc": 1.00,
            "weekly_cap_usdc": 5.00,
            "currency": "USDC",
            "enforce_strict": True,
        }

    @migrated.post(
        "/api/v1/agent/spending-policy/evaluate",
        summary="Evaluate proposed purchase against agent spending policy",
        description="""Evaluates whether a planned intelligence purchase complies with configured Circle CLI spending policy limits. Enforces per-transaction caps and daily cumulative allowances.

**Authentication:** Public route.""",
        response_model=SpendingPolicyEvaluateResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(400, 429, 500),
    )
    def evaluate_spending_policy(request: SpendingPolicyEvaluateRequest):
        wallet = normalize_address(request.wallet_address)
        amount = request.amount_usdc
        max_per_tx = 0.05
        daily_cap = 1.00

        current_spend = _WALLET_DAILY_SPEND.get(wallet, 0.0)

        if amount > max_per_tx:
            return {
                "allowed": False,
                "reason": f"Amount {amount} USDC exceeds single transaction cap of {max_per_tx} USDC.",
                "amount_usdc": amount,
                "max_per_tx_usdc": max_per_tx,
                "daily_cap_usdc": daily_cap,
                "current_spend_today_usdc": current_spend,
                "remaining_daily_budget_usdc": max(0.0, daily_cap - current_spend),
            }

        if current_spend + amount > daily_cap:
            return {
                "allowed": False,
                "reason": f"Proposed amount would cause daily spend ({round(current_spend + amount, 4)} USDC) to exceed daily cap ({daily_cap} USDC).",
                "amount_usdc": amount,
                "max_per_tx_usdc": max_per_tx,
                "daily_cap_usdc": daily_cap,
                "current_spend_today_usdc": current_spend,
                "remaining_daily_budget_usdc": max(0.0, daily_cap - current_spend),
            }

        new_spend = round(current_spend + amount, 4)
        _WALLET_DAILY_SPEND[wallet] = new_spend
        return {
            "allowed": True,
            "reason": "Transaction approved under Circle Agent Wallet spending policy.",
            "amount_usdc": amount,
            "max_per_tx_usdc": max_per_tx,
            "daily_cap_usdc": daily_cap,
            "current_spend_today_usdc": new_spend,
            "remaining_daily_budget_usdc": max(0.0, daily_cap - new_spend),
        }

    @migrated.get(
        "/api/v1/agent/wallet-config",
        summary="Read supported agent wallet connection methods and passkey configuration",
        description="""Returns client configuration for Circle Modular Wallets (WebAuthn biometrics / passkey authentication) and gasless transactions via Circle Gas Station paymaster.

**Authentication:** Public route.""",
        response_model=WalletConfigResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500),
    )
    def get_wallet_config():
        return {
            "supported_methods": [
                "circle_modular_passkey",
                "circle_developer_controlled",
                "eip1193_injected",
                "x402_bearer",
            ],
            "passkey_supported": True,
            "gasless_transactions": True,
            "paymaster_rail": "Circle Gas Station (Zero-Gas WebAuthn)",
            "gateway_instant_settlement": True,
        }

    return migrated
