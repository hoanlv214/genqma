"""Shared agent decision and standard identity endpoints for AI agents and marketplace integrations."""

import os
import re
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException, Security
from backend.app.core.security_schemes import qma_access_token_header
from backend.app.services.agent_jobs import create_job, deliver_job
from backend.app.services.spending_policy import evaluate_spending

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
            "collateral_risk_underwriting",
            "stablefx_conversion",
        ],
        "supported_protocols": [
            "x402",
            "erc8183",
            "erc8004",
            "mcp",
            "genlayer-consensus",
            "circle-stablefx",
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
        "arc_rfb_alignment": {
            "frontiers": [
                "the_agentic_economy",
                "the_intelligent_account",
                "onchain_credit_and_collateral",
                "global_money_and_embedded_finance",
            ],
            "archetype": "Autonomous Business (Zero-Person Company) & Two-Sided Outcome Marketplace",
            "settlement_rail": "Arc L1 Deterministic Finality (USDC native gas)",
            "treasury_management": "Vestiarion AI CFO with ERC-4626 USYC Yield Sweep",
            "sla_verification": "GenLayer Optimistic Consensus Shield",
            "spending_guardrails": "Deterministic Spending Policy Engine (Money with a Mandate)",
            "stablefx_status": "Enabled (EURC/USDC corridor support)",
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
            {"method": "GET", "path": "/api/v1/market/credit-risk-score", "description": "Collateral Risk & Analogs Underwriting (Frontier 3)"},
            {"method": "GET", "path": "/api/v1/stablefx/quote", "description": "Institutional Stablecoin FX Quote (USDC/EURC)"},
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
            use_laya=request.use_laya,
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
        summary="Deliver an invoice-backed intelligence job",
        description="""ERC-8183-shaped adapter over QMA invoices, not an independent on-chain escrow. Without invoice_id, returns HTTP 402 with a real invoice and payment requirement. Pay and verify that invoice, then retry with the exact query, invoice_id and X-QMA-Access-Token. Completion includes only the finalized GenLayer receipt and cached report; no reputation points are fabricated.""",
        response_model=ERC8183JobResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(400, 402, 403, 404, 409, 429, 500, 503),
    )
    def create_erc8183_job(request: ERC8183JobRequest, token: str | None = Security(qma_access_token_header)):
        return create_job(deps, request, token)

    @migrated.get(
        "/api/v1/agent/jobs/{job_id}",
        summary="Read an owned invoice-backed job",
        description="""Requires X-QMA-Access-Token for the invoice encoded by job_id. Reconstructs the job from durable invoice state, with the real GenLayer receipt and verified report. Unpaid, rejected and mismatched-token jobs remain inaccessible.""",
        response_model=ERC8183JobResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(400, 402, 403, 404, 409, 429, 500, 503),
    )
    def get_erc8183_job(job_id: str, token: str | None = Security(qma_access_token_header)):
        if not job_id.startswith("job_inv_"):
            raise HTTPException(status_code=404, detail="Job not found.")
        return deliver_job(deps, job_id.removeprefix("job_"), token)

    @migrated.get(
        "/api/v1/agent/spending-policy",
        summary="Read Circle agent wallet spending policy caps",
        description="""Inspect QMA advisory spending thresholds (per transaction, UTC calendar day and UTC calendar week). enforce_strict is false: this route does not configure Circle or authorize transfers; payment executors enforce wallet limits.

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
            "enforce_strict": False,
        }

    @migrated.post(
        "/api/v1/agent/spending-policy/evaluate",
        summary="Evaluate proposed purchase against agent spending policy",
        description="""Read-only evaluation against authoritative settlement history using UTC calendar days and weeks. Evaluations never consume budget. Duplicate settlements count once, confirmed refunds are excluded, and storage failures return 503 rather than an approval. This does not reserve funds or configure Circle spending limits.

**Authentication:** Public route.""",
        response_model=SpendingPolicyEvaluateResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(400, 429, 500, 503),
    )
    def evaluate_spending_policy(request: SpendingPolicyEvaluateRequest):
        wallet = normalize_address(request.wallet_address)
        if not re.fullmatch(r"0x[0-9a-f]{40}", wallet):
            raise HTTPException(status_code=400, detail="A valid EVM wallet address is required.")
        try:
            events = deps.load_spending_events(wallet)
            return evaluate_spending(events, request.amount_usdc)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Spending ledger is unavailable; no approval was issued.") from exc

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
