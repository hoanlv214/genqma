"""Shared agent decision endpoint for the React UI and external clients."""

from types import SimpleNamespace

from fastapi import APIRouter

from backend.app.schemas import AgentDecisionResponse
from backend.app.schemas.agent import AgentDecisionRequest
from backend.app.services.agent_decision import make_agent_decision
from backend.app.core.openapi_responses import documented_errors


router = APIRouter(tags=["Agent decisioning"])


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

    return migrated
