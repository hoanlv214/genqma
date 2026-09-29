"""Shared agent decision and standard identity endpoints for AI agents and marketplace integrations."""

import os
import re
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException, Query, Security
from backend.app.core.security_schemes import qma_access_token_header
from backend.app.services.agent_jobs import create_job, deliver_job
from backend.app.services.spending_policy import (
    DEFAULT_MAX_PER_TX,
    DEFAULT_DAILY_CAP,
    DEFAULT_WEEKLY_CAP,
    DEFAULT_MONTHLY_CAP,
    build_circle_wallet_limit_command,
    evaluate_spending,
    get_active_spending_policy,
)

from backend.app.schemas import AgentDecisionResponse
from backend.app.schemas.agent import (
    AgentDecisionRequest,
    AgentDelegateStatusResponse,
    AgentIdentityResponse,
    AgentReputationResponse,
    CircleServiceCardResponse,
    ERC8183JobRequest,
    ERC8183JobResponse,
    SpendingPolicyCommandResponse,
    SpendingPolicyConfigResponse,
    SpendingPolicyEvaluateRequest,
    SpendingPolicyEvaluateResponse,
    WalletConfigResponse,
)
from backend.app.services.agent_decision import make_agent_decision
from backend.app.core.config import (
    ARC_CHAIN_ID,
    ARC_EXPLORER,
    ARC_GATEWAY_WALLET,
    ERC8004_AGENT_ID,
    ERC8004_IDENTITY_REGISTRY,
    ERC8004_REPUTATION_REGISTRY,
    ERC8004_VALIDATION_REGISTRY,
    IS_TESTNET,
    NETWORKS_DATA,
    PAYMENT_WALLET_ADDRESS,
    SHIELD_CONTRACT_ADDRESS,
)
from backend.app.services.erc8004_service import (
    get_onchain_identity,
    get_onchain_reputation_summary,
)
from backend.app.core.openapi_responses import documented_errors
from backend.app.services.wallet_utils import normalize_address


router = APIRouter(tags=["Agent decisioning"])



def _get_agent_identity() -> dict:
    shield_address = SHIELD_CONTRACT_ADDRESS
    return {
        "standard": "ERC-8004",
        "name": "QMA Autonomous Intelligence Agent",
        "version": "2.4.0",
        "agent_address": shield_address,
        "chain_id": ARC_CHAIN_ID,
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
            "arc_earn_kit_morpho_lending",
        ],
        "supported_protocols": [
            "x402",
            "erc8183",
            "erc8004",
            "mcp",
            "genlayer-consensus",
            "circle-stablefx",
            "arc-earn-kit",
            "morpho-lending",
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
        "erc8004": {
            "agent_id": ERC8004_AGENT_ID,
            "identity_registry": ERC8004_IDENTITY_REGISTRY,
            "reputation_registry": ERC8004_REPUTATION_REGISTRY,
            "validation_registry": ERC8004_VALIDATION_REGISTRY,
            "explorer_url": f"{ARC_EXPLORER.rstrip('/')}/token/{ERC8004_IDENTITY_REGISTRY}?a={ERC8004_AGENT_ID}",
            "onchain_verified": True,
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
    profile = NETWORKS_DATA.get("testnet" if IS_TESTNET else "mainnet", {})
    cross_chains = profile.get("crossChains", [])
    networks = [c.get("id", "").replace("_", "-") for c in cross_chains] if cross_chains else ["arc-testnet", "base-sepolia", "arbitrum-sepolia", "ethereum-sepolia"]
    networks.sort(key=lambda x: 0 if "arc" in x else 1)

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
            "preview_report": "0.002",
            "full_report": "0.005",
        },
        "networks": networks,
        "endpoints": [
            {"method": "GET", "path": "/.well-known/circle-service.json", "description": "Circle Service Discovery Descriptor"},
            {"method": "GET", "path": "/api/v1/agent/identity", "description": "ERC-8004 Agent Card & Capabilities"},
            {"method": "POST", "path": "/api/v1/providers/{provider_id}/preview", "description": "x402 Paid Preview Intelligence Report ($0.002 USDC)"},
            {"method": "POST", "path": "/api/v1/providers/{provider_id}/full-report", "description": "x402 Paid Full Quantitative Report ($0.005 USDC)"},
            {"method": "POST", "path": "/api/v1/agent/decision", "description": "Autonomous Purchase Decisioning"},
            {"method": "POST", "path": "/api/v1/agent/jobs", "description": "ERC-8183 Escrowed Task Dispatch ($0.010 USDC)"},
            {"method": "GET", "path": "/api/v1/providers", "description": "List Verified Intelligence Providers"},
            {"method": "GET", "path": "/api/v1/agent/spending-policy", "description": "Circle Wallet Spending Policy Caps"},
            {"method": "GET", "path": "/api/v1/market/credit-risk-score", "description": "Collateral Risk & Analogs Underwriting"},
            {"method": "GET", "path": "/api/v1/stablefx/quote", "description": "Institutional Stablecoin FX Quote (USDC/EURC)"},
        ],
        "provider": {
            "name": "GenQMA Labs",
            "url": "https://genqma.vercel.app",
            "support_url": "https://genqma.vercel.app/docs",
            "documentation_url": "https://genqma.vercel.app/docs",
            "health_check_url": "https://qma-api.onrender.com/healthz",
        },
        "example_prompts": [
            "Search funding rate arbitrage anomalies for BTC and ETH",
            "Inspect quantitative analogs and win-rate diagnostics for MBOX",
            "Get Polymarket event divergence signal vs perpetual futures",
            "Underwrite collateral credit risk score on Arc",
        ],
        "x402_specification": {
            "version": 2,
            "scheme": "exact",
            "payment_rail": "Circle Gateway Nanopayments (x402)",
            "settlement_verification": "GenLayer Intelligent Contract Consensus",
            "seller_address": PAYMENT_WALLET_ADDRESS,
        },
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
        "/.well-known/agent-card.json",
        summary="Standard Agent Card metadata for external AI agent discovery",
        description="""Standard agent discovery metadata card. Enables external AI agents (Circle CLI, Claude, ChatGPT, LangChain) to inspect QMA identity, capabilities, on-chain verification contracts, and pricing models on Arc.

**Authentication:** Public route.""",
        response_model=AgentIdentityResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500),
    )
    def get_agent_card_json_well_known():
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
        "/api/v1/agent/reputation",
        summary="Read QMA ERC-8004 on-chain reputation and verified credentials",
        description="""Returns the authoritative ERC-8004 on-chain reputation score, verified tags, and attestations on Arc Testnet.

**Authentication:** Public route.""",
        response_model=AgentReputationResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500),
    )
    def get_agent_reputation():
        return get_onchain_reputation_summary()

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
        description="""Inspect QMA advisory spending thresholds (per transaction, UTC calendar day, week, and month). enforce_strict is false: this route does not configure Circle or authorize transfers; payment executors enforce wallet limits.

**Authentication:** Public route.""",
        response_model=SpendingPolicyConfigResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500),
    )
    def get_spending_policy(
        wallet_address: str | None = Query(None, description="Optional EVM wallet address to query live Circle CLI limits"),
    ):
        if wallet_address:
            wallet = normalize_address(wallet_address)
            return get_active_spending_policy(wallet)
        return get_active_spending_policy()

    @migrated.post(
        "/api/v1/agent/spending-policy/evaluate",
        summary="Evaluate proposed purchase against agent spending policy",
        description="""Read-only evaluation against authoritative settlement history using UTC calendar days, weeks, and months. Evaluations never consume budget. Duplicate settlements count once, confirmed refunds are excluded, and storage failures return 503 rather than an approval. This does not reserve funds or configure Circle spending limits.

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
            kwargs = {}
            if request.max_per_tx_usdc is not None:
                kwargs["max_per_tx_usdc"] = request.max_per_tx_usdc
            if request.daily_cap_usdc is not None:
                kwargs["daily_cap_usdc"] = request.daily_cap_usdc
            if request.weekly_cap_usdc is not None:
                kwargs["weekly_cap_usdc"] = request.weekly_cap_usdc
            if request.monthly_cap_usdc is not None:
                kwargs["monthly_cap_usdc"] = request.monthly_cap_usdc

            return evaluate_spending(
                events,
                request.amount_usdc,
                **kwargs,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Spending ledger is unavailable; no approval was issued.") from exc

    @migrated.get(
        "/api/v1/agent/spending-policy/command",
        summary="Generate Circle CLI wallet limit command with OTP instructions",
        description="""Generates verbatim `circle wallet limit set` CLI command for user terminal execution. Mainnet agent spending limits require email OTP confirmation in an interactive terminal session and must never be handled or stored by the agent server.

**Authentication:** Public route.""",
        response_model=SpendingPolicyCommandResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(400, 429, 500),
    )
    def get_spending_policy_command(
        wallet_address: str = Query(..., description="EVM wallet address of the agent"),
        max_per_tx: float | None = Query(None, description="Per-transaction cap in USDC"),
        daily: float | None = Query(None, description="Daily cap in USDC"),
        weekly: float | None = Query(None, description="Weekly cap in USDC"),
        monthly: float | None = Query(None, description="Monthly cap in USDC"),
    ):
        wallet = normalize_address(wallet_address)
        if not re.fullmatch(r"0x[0-9a-f]{40}", wallet):
            raise HTTPException(status_code=400, detail="A valid EVM wallet address is required.")
        try:
            kwargs = {}
            if max_per_tx is not None:
                kwargs["per_tx"] = max_per_tx
            if daily is not None:
                kwargs["daily"] = daily
            if weekly is not None:
                kwargs["weekly"] = weekly
            if monthly is not None:
                kwargs["monthly"] = monthly

            return build_circle_wallet_limit_command(
                wallet,
                **kwargs,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @migrated.get(
        "/api/v1/agent/delegate-status",
        summary="Read Circle Gateway Unified Balance delegation status",
        description="""Returns the active Gateway Wallet contract and supported chains for Circle Gateway Unified Balance addDelegate authorization. Allows the autonomous agent to spend unified balances across chains without per-action popups once authorized by the user.

**Authentication:** Public route.""",
        response_model=AgentDelegateStatusResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500),
    )
    def get_delegate_status(owner_address: str | None = Query(None, description="Optional account owner wallet address")):
        profile = NETWORKS_DATA.get("testnet" if IS_TESTNET else "mainnet", {})
        cross_chains = profile.get("crossChains", [])
        networks = [c.get("id", "").replace("_", "-") for c in cross_chains] if cross_chains else ["arc-testnet", "base-sepolia", "arbitrum-sepolia", "ethereum-sepolia"]
        networks.sort(key=lambda x: 0 if "arc" in x else 1)
        normalized_owner = normalize_address(owner_address) if owner_address else None
        return {
            "owner_address": normalized_owner,
            "delegate_address": SHIELD_CONTRACT_ADDRESS,
            "status": "ready",
            "is_authorized": True,
            "gateway_wallet_contract": ARC_GATEWAY_WALLET,
            "supported_chains": networks,
            "spending_policy": {
                "standard": "circle-wallet-policy-v1",
                "max_per_tx_usdc": DEFAULT_MAX_PER_TX,
                "daily_cap_usdc": DEFAULT_DAILY_CAP,
                "weekly_cap_usdc": DEFAULT_WEEKLY_CAP,
                "monthly_cap_usdc": DEFAULT_MONTHLY_CAP,
                "currency": "USDC",
                "enforce_strict": False,
            },
            "instructions": (
                "Call addDelegate(delegateAddress) on Circle Gateway Wallet contract or via "
                "kit.unifiedBalance.addDelegate() to permit the Autonomous Agent to spend from Unified Balance without interactive popups."
            ),
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
