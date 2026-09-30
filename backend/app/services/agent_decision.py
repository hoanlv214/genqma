"""Shared agent planning service for the React UI and external CLI clients.

The model produces a small plan only. Candidate data, prices, entitlements,
queries, and policy results are resolved deterministically from QMA data.
"""

import json
import logging
import os
import re
import time
from decimal import Decimal
from types import SimpleNamespace
from typing import Optional

import httpx
import requests

from backend.app.core.config import AGENT_MAX_DECISION_BUDGET_USDC
from backend.app.services.agent_security import (
    sanitize_financial_prompt,
    FinancialPromptInjectionError,
)
from backend.app.services.spend_guard import get_spend_limit_guard


logger = logging.getLogger("QMA-Agent")
MAX_REASON_LENGTH = 240
PLAN_KEYS = {
    "action",
    "candidate_id",
    "requested_tier",
    "budget_usdc",
    "max_price_usdc",
    "reason",
    "rejected_candidate_ids",
}


def _text(value) -> str:
    return str(value).strip() if value is not None else ""


def _number(value, fallback: float = 0.0) -> float:
    try:
        parsed = float(value)
        return parsed if parsed == parsed and parsed != float("inf") else fallback
    except (TypeError, ValueError):
        return fallback


def _prompt_policy(prompt: str, budget_override: Optional[float], max_price_override: Optional[float]):
    lowered = prompt.lower()
    match = re.search(r"(?:budget|under|limit|max|price|of)\s*\$?\s*([0-9.]+)", lowered)
    budget = budget_override if budget_override is not None else (_number(match.group(1), 0.01) if match else 0.01)
    budget = min(budget, AGENT_MAX_DECISION_BUDGET_USDC)
    max_price = max_price_override if max_price_override is not None else min(budget, 0.005)
    max_price = min(max_price, budget)
    provider_id = None
    if "oi_memory" in lowered or "open_interest" in lowered or re.search(r"\boi\b", lowered):
        provider_id = "oi_memory"
    elif "funding_memory" in lowered or "funding" in lowered:
        provider_id = "funding_memory"
    tier = "full" if "full" in lowered else "preview" if "preview" in lowered else None
    return max(0.0, budget), max(0.0, max_price), provider_id, tier


def _candidate_id(item: dict, index: int) -> str:
    explicit = _text(item.get("candidate_id")) or _text(item.get("id"))
    if explicit:
        return explicit
    provider = _text(item.get("provider_id")) or "funding_memory"
    symbol = _text(item.get("symbol")) or _text((item.get("query") or {}).get("symbol"))
    return f"qma:{provider}:{symbol.upper() or index}:{index}"


def _entitlement_symbol(item: dict) -> str:
    report = item.get("report") if isinstance(item.get("report"), dict) else {}
    query = item.get("query") if isinstance(item.get("query"), dict) else {}
    return (_text(item.get("symbol")) or _text(query.get("symbol")) or _text(report.get("query_symbol"))).upper()


def _entitlement_tier(item: dict) -> str:
    report = item.get("report") if isinstance(item.get("report"), dict) else {}
    return "full" if (_text(item.get("tier")) or _text(report.get("tier"))).lower() == "full" else "preview"


def _entitlement_provider(item: dict) -> str:
    report = item.get("report") if isinstance(item.get("report"), dict) else {}
    invoice = report.get("invoice") if isinstance(report.get("invoice"), dict) else {}
    return _text(item.get("provider_id") or report.get("provider_id") or invoice.get("provider_id") or "funding_memory")


def _has_entitlement(entitlements: list, symbol: str, tier: str, provider_id: Optional[str]) -> bool:
    normalized_provider = _text(provider_id)
    return any(
        _entitlement_symbol(item) == symbol.upper()
        and _entitlement_tier(item) == tier
        and _entitlement_provider(item) == normalized_provider
        for item in entitlements
    )


def _price_for(deps: SimpleNamespace, candidate: dict, tier: str) -> float:
    provider = deps.provider_registry.require(candidate["provider_id"])
    if hasattr(provider, "score"):
        return round(float(provider.score({"query": candidate.get("query") or {}, "tier": tier})["amount_usdc"]), 6)
    return round(float(provider.quote_price(candidate.get("query") or {}, tier)["amount_usdc"]), 6)


def _prepare_candidates(
    deps: SimpleNamespace,
    raw: list,
    entitlements: list,
    budget: float,
    max_price: float,
    provider_filter: Optional[str],
    tier_filter: Optional[str],
    allowed_providers: Optional[list[str]],
    allowed_tiers: Optional[list[str]],
    minimum_score: Optional[float],
):
    prepared = []
    for index, raw_item in enumerate(raw):
        item = dict(raw_item) if isinstance(raw_item, dict) else {}
        provider_id = _text(item.get("provider_id")) or "funding_memory"
        symbol = (_text(item.get("symbol")) or _text((item.get("query") or {}).get("symbol"))).upper()
        if provider_filter and provider_id != provider_filter:
            continue
        if allowed_providers and provider_id not in allowed_providers:
            continue

        suggested = "full" if _text(item.get("suggested_tier")).lower() == "full" else "preview"
        tier = tier_filter or (suggested if not allowed_tiers or suggested in allowed_tiers else allowed_tiers[0])
        if allowed_tiers and tier not in allowed_tiers:
            continue
        if minimum_score is not None and _number(item.get("score")) < minimum_score:
            item["agent_rejection"] = {"reason_code": "MINIMUM_SCORE", "reason": "Score is below the session minimum."}
            item["agent_tier"] = tier
            item["agent_price"] = 0.0
            item["agent_query"] = item.get("query") or {"symbol": symbol}
            item["candidate_id"] = _candidate_id(item, index)
            prepared.append(item)
            continue
        preview_paid = _has_entitlement(entitlements, symbol, "preview", provider_id)
        full_paid = _has_entitlement(entitlements, symbol, "full", provider_id)
        upgrade = not tier_filter and tier == "preview" and preview_paid and not full_paid
        if upgrade:
            tier = "full"

        rejection = None
        try:
            price = _price_for(deps, {"provider_id": provider_id, "query": item.get("query") or {}}, tier)
        except (KeyError, ValueError, TypeError):
            price = 0.0
            rejection = {"reason_code": "PROVIDER_NOT_ALLOWED", "reason": "Provider is not allowed."}

        if rejection is None and full_paid:
            rejection = {"reason_code": "ALREADY_OWNED", "reason": "Full Report already purchased."}
        elif rejection is None and _has_entitlement(entitlements, symbol, tier, provider_id):
            rejection = {"reason_code": "ALREADY_OWNED", "reason": f"{tier.title()} report already purchased."}
        elif rejection is None and price <= 0:
            rejection = {"reason_code": "POLICY_REJECTED", "reason": "No valid price was returned."}
        elif rejection is None and price > budget:
            rejection = {
                "reason_code": "PRICE_ABOVE_BUDGET",
                "reason": "Price is above the configured budget.",
                "observed_price_usdc": price,
                "limit_usdc": budget,
            }
        elif rejection is None and price > max_price:
            rejection = {
                "reason_code": "PRICE_ABOVE_MAX",
                "reason": "Price is above the configured maximum price.",
                "observed_price_usdc": price,
                "limit_usdc": max_price,
            }

        item.update({
            "candidate_id": _candidate_id(item, index),
            "agent_tier": tier,
            "agent_price": price,
            "agent_query": item.get("query") or {"symbol": symbol},
            "agent_upgrade_from_preview": upgrade,
            "agent_rejection": rejection,
            "agent_skipped_reason": rejection["reason"] if rejection else "",
        })
        prepared.append(item)
    return prepared


def _deterministic_rejections(candidates: list, selected: Optional[dict], objective: str) -> list[dict]:
    rejections = []
    for item in candidates:
        if item is selected:
            continue
        rejection = item.get("agent_rejection")
        if rejection:
            rejections.append({"candidate_id": item["candidate_id"], **rejection})
        else:
            rejections.append({
                "candidate_id": item["candidate_id"],
                "reason_code": "LOWER_VALUE_DENSITY" if objective != "highest_score" else "LOWER_SCORE",
                "reason": "Candidate ranked below the selected eligible candidate.",
            })
    return rejections


def _compact_candidate(selected: Optional[dict]) -> Optional[dict]:
    if not selected:
        return None
    price = _number(selected.get("agent_price"))
    score = _number(selected.get("score"))
    return {
        "candidate_id": selected["candidate_id"],
        "provider_id": selected.get("provider_id"),
        "provider_name": selected.get("provider_name"),
        "symbol": selected.get("symbol"),
        "tier": selected.get("agent_tier"),
        "score": score,
        "price_usdc": price,
        "value_density": round(score / price, 6) if price > 0 else 0,
        "upgrade": bool(selected.get("agent_upgrade_from_preview")),
    }


def _evaluated_candidates(candidates: list, selected: Optional[dict], objective: str) -> list[dict]:
    rows = []
    for item in candidates:
        rejection = item.get("agent_rejection")
        price = _number(item.get("agent_price"))
        score = _number(item.get("score"))
        rows.append({
            "candidate_id": item["candidate_id"],
            "symbol": item.get("symbol"),
            "provider_id": item.get("provider_id"),
            "provider_name": item.get("provider_name"),
            "canonical_query": item.get("agent_query"),
            "tier": item.get("agent_tier"),
            "score": score,
            "price_usdc": price,
            "value_density": round(score / price, 6) if price > 0 else 0,
            "eligible": rejection is None,
            "upgrade": bool(item.get("agent_upgrade_from_preview")),
            "status": "selected" if item is selected else rejection.get("reason_code") if rejection else ("LOWER_SCORE" if objective == "highest_score" else "LOWER_VALUE_DENSITY"),
            "reason_code": rejection.get("reason_code") if rejection else None,
            "reason": rejection.get("reason") if rejection else None,
        })
    return rows


def _selection_basis(candidates: list, selected: Optional[dict], objective: str) -> dict:
    """Expose the deterministic routing rule without making it LLM-authored."""
    return {
        "objective": objective,
        "ranking": "upgrade_then_score" if objective == "highest_score" else "upgrade_then_value_density_then_score",
        "selected_candidate_id": selected.get("candidate_id") if selected else None,
        "selected_provider_id": selected.get("provider_id") if selected else None,
        "eligible_candidate_count": sum(1 for item in candidates if not item.get("agent_rejection")),
        "evaluated_provider_ids": sorted({item.get("provider_id") for item in candidates if item.get("provider_id")}),
    }


def _policy_check(deps: SimpleNamespace, selected: Optional[dict], entitlements: list, budget: float, max_price: float) -> dict:
    if not selected:
        return {
            "candidate_exists": False,
            "provider_matches": False,
            "tier_supported": False,
            "price_within_max": False,
            "price_within_budget": False,
            "entitlement_allowed": False,
            "query_resolved_from_canonical_candidate": False,
        }
    price = _number(selected.get("agent_price"))
    symbol = _text(selected.get("symbol"))
    tier = selected.get("agent_tier")
    provider_valid = False
    try:
        deps.provider_registry.require(selected["provider_id"])
        provider_valid = True
    except (KeyError, ValueError, TypeError):
        pass
    return {
        "candidate_exists": True,
        "provider_matches": provider_valid,
        "tier_supported": tier in ("preview", "full"),
        "price_within_max": price > 0 and price <= max_price,
        "price_within_budget": price > 0 and price <= budget,
        "entitlement_allowed": not _has_entitlement(entitlements, symbol, "full", selected.get("provider_id")) and not _has_entitlement(entitlements, symbol, tier, selected.get("provider_id")),
        "query_resolved_from_canonical_candidate": isinstance(selected.get("agent_query"), dict) and bool(selected.get("agent_query")),
    }


def _plan(action: str, candidate_id: Optional[str], requested_tier: str, budget: float, max_price: float, reason: str, rejected_ids: list[str]) -> dict:
    return {
        "action": action,
        "candidate_id": candidate_id,
        "requested_tier": requested_tier,
        "budget_usdc": budget,
        "max_price_usdc": max_price,
        "reason": _text(reason)[:MAX_REASON_LENGTH],
        "rejected_candidate_ids": rejected_ids,
    }


def _decision_payload(
    deps: SimpleNamespace,
    selected: Optional[dict],
    candidates: list,
    entitlements: list,
    budget: float,
    max_price: float,
    objective: str,
    source: str,
    reason: Optional[str] = None,
    requested_tier: Optional[str] = None,
    action: Optional[str] = None,
) -> dict:
    deterministic_rejections = _deterministic_rejections(candidates, selected, objective)
    resolved_action = action or ("purchase" if selected else "skip")
    plan_tier = requested_tier or "auto"
    plan = _plan(
        resolved_action,
        selected.get("candidate_id") if selected and resolved_action == "purchase" else None,
        plan_tier,
        budget,
        max_price,
        reason or (f"Selected the highest-scoring eligible candidate under policy." if objective == "highest_score" else "Selected the best eligible candidate under policy." if selected else "No candidate met policy constraints."),
        [item["candidate_id"] for item in deterministic_rejections],
    )
    return {
        "plan": plan,
        "validation": {
            "valid": bool(selected) or resolved_action in ("skip", "clarify"),
            "errors": [],
            "warnings": [],
        },
        "resolved_candidate": _compact_candidate(selected),
        "canonical_query": selected.get("agent_query") if selected else None,
        "policy_check": _policy_check(deps, selected, entitlements, budget, max_price),
        "rejected_candidates": deterministic_rejections,
        "evaluated_candidates": _evaluated_candidates(candidates, selected, objective),
        "selection_basis": _selection_basis(candidates, selected, objective),
        "candidate_count": len(candidates),
        "decision_source": source,
        "idle_capital_strategy": _resolve_idle_capital_strategy() if not selected else None,
    }




def _resolve_idle_capital_strategy() -> dict:
    try:
        from backend.app.services.earn_kit import earn_kit_service
        opp = earn_kit_service.get_opportunity("morpho_steakhouse_usdc") or earn_kit_service.get_opportunity("morpho_arc_usdc_core")
        if opp:
            return {
                "action_recommended": "SWEEP_IDLE",
                "opportunity": opp["name"],
                "vault_id": opp["vault_id"],
                "vault_address": opp["vaultAddress"],
                "protocol": opp["protocol"],
                "net_apy": opp["currentApy"],
                "net_apy_percentage": f"{round(opp['currentApy'] * 100, 2)}%",
                "rationale": f"All market intelligence candidates evaluated. Deploying remaining idle capital into {opp['name']} on Arc for {round(opp['currentApy'] * 100, 2)}% APY.",
            }
    except Exception:
        pass
    return {
        "action_recommended": "SWEEP_IDLE",
        "opportunity": "Steakhouse USDC",
        "vault_id": "morpho_steakhouse_usdc",
        "vault_address": "0x4869c9B5F54f6c40A5a417537b03a4537cb90c91",
        "protocol": "Morpho",
        "net_apy": 0.065,
        "net_apy_percentage": "6.5%",
        "rationale": "All market intelligence candidates evaluated. Deploying remaining idle capital into Steakhouse USDC on Arc for 6.5% APY.",
    }

def _normalize_model_plan(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError("LLM plan must be an object.")
    unknown = set(value) - PLAN_KEYS
    if unknown:
        raise ValueError(f"LLM plan contains unsupported fields: {', '.join(sorted(unknown))}.")
    missing = PLAN_KEYS - set(value)
    if missing:
        raise ValueError(f"LLM plan is missing fields: {', '.join(sorted(missing))}.")
    action = value.get("action")
    if action not in ("purchase", "skip", "clarify"):
        raise ValueError("LLM plan action must be purchase, skip, or clarify.")
    candidate_id = value.get("candidate_id")
    if candidate_id is not None and (not isinstance(candidate_id, str) or not candidate_id.strip()):
        raise ValueError("LLM plan candidate_id must be a string or null.")
    requested_tier = value.get("requested_tier")
    if requested_tier not in ("preview", "full", "auto"):
        raise ValueError("LLM plan requested_tier must be preview, full, or auto.")
    budget = _number(value.get("budget_usdc"), -1)
    max_price = _number(value.get("max_price_usdc"), -1)
    if budget < 0 or max_price < 0:
        raise ValueError("LLM plan budget and max_price must be non-negative numbers.")
    reason = value.get("reason")
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > MAX_REASON_LENGTH:
        raise ValueError("LLM plan reason must be a non-empty string of at most 240 characters.")
    rejected_ids = value.get("rejected_candidate_ids")
    if not isinstance(rejected_ids, list) or len(rejected_ids) > 25 or any(not isinstance(item, str) or not item.strip() for item in rejected_ids):
        raise ValueError("LLM plan rejected_candidate_ids must contain only candidate ID strings.")
    if action == "purchase" and not candidate_id:
        raise ValueError("Purchase plan requires candidate_id.")
    if action in ("skip", "clarify") and candidate_id is not None:
        raise ValueError("Skip/clarify plans must not select a candidate_id.")
    return {
        "action": action,
        "candidate_id": candidate_id.strip() if isinstance(candidate_id, str) else None,
        "requested_tier": requested_tier,
        "budget_usdc": budget,
        "max_price_usdc": max_price,
        "reason": reason.strip(),
        "rejected_candidate_ids": [item.strip() for item in rejected_ids],
    }


def _llm_decision(
    prompt: str,
    budget: float,
    max_price: float,
    candidates: list,
    entitlements: list,
    objective: str,
) -> Optional[dict]:
    provider = os.getenv("QMA_LLM_PROVIDER", "openai").lower().strip()

    # Resolve API Key
    api_key = os.getenv("QMA_LLM_API_KEY", "").strip()
    if not api_key:
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
        elif provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", "")).strip()
        elif provider == "groq":
            api_key = os.getenv("GROQ_API_KEY", "").strip()
        elif provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY", os.getenv("OPENROUTER_API", "")).strip()

    if provider != "ollama" and not api_key:
        logger.warning("No API key configured for LLM provider: %s", provider)
        return None

    # Resolve Base URL
    base_url = os.getenv("QMA_LLM_BASE_URL", "").strip()
    if not base_url:
        if provider == "openai":
            base_url = "https://api.openai.com/v1"
        elif provider == "gemini":
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
        elif provider == "groq":
            base_url = "https://api.groq.com/openai/v1"
        elif provider == "openrouter":
            base_url = "https://openrouter.ai/api/v1"
        elif provider == "ollama":
            base_url = "http://localhost:11434/v1"
        else:
            base_url = "https://api.openai.com/v1"

    # Resolve Model
    model = os.getenv("QMA_LLM_MODEL", "").strip()
    if not model:
        if provider == "openai":
            model = "gpt-4o-mini"
        elif provider == "gemini":
            model = "gemini-2.5-flash"
        elif provider == "groq":
            model = "llama-3.3-70b-specdec"
        elif provider == "openrouter":
            model = "google/gemini-2.5-flash"
        elif provider == "ollama":
            model = "qwen2.5:7b"
        else:
            model = "gpt-4o-mini"

    context = {
        "task": prompt,
        "budget_usdc": budget,
        "max_price_usdc": max_price,
        "objective": objective,
        "candidates": [
            {
                "candidate_id": item.get("candidate_id"),
                "symbol": item.get("symbol"),
                "score": item.get("score"),
                "tier": item.get("agent_tier"),
                "price_usdc": item.get("agent_price"),
                "eligible": not bool(item.get("agent_rejection")),
                "ineligible_reason_code": (item.get("agent_rejection") or {}).get("reason_code"),
                "reasons": item.get("reasons"),
            }
            for item in candidates
        ],
        "entitlements": [{"symbol": _entitlement_symbol(item), "tier": _entitlement_tier(item)} for item in entitlements],
    }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {"type": "string", "enum": ["purchase", "skip", "clarify"]},
            "candidate_id": {"type": ["string", "null"]},
            "requested_tier": {"type": "string", "enum": ["preview", "full", "auto"]},
            "budget_usdc": {"type": "number", "minimum": 0},
            "max_price_usdc": {"type": "number", "minimum": 0},
            "reason": {"type": "string", "maxLength": MAX_REASON_LENGTH},
            "rejected_candidate_ids": {"type": "array", "maxItems": 25, "items": {"type": "string"}},
        },
        "required": sorted(PLAN_KEYS),
    }

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/hoanlv214/qma"
        headers["X-Title"] = "QMA Agent"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are the QMA purchase planner. Return only valid JSON matching this schema:\n"
                    "{\n"
                    '  "action": "purchase" | "skip" | "clarify",\n'
                    '  "candidate_id": string | null,\n'
                    '  "requested_tier": "preview" | "full" | "auto",\n'
                    '  "budget_usdc": number,\n'
                    '  "max_price_usdc": number,\n'
                    '  "reason": string (max 240 chars),\n'
                    '  "rejected_candidate_ids": [string]\n'
                    "}\n"
                    "Never return provider metadata, prices, scores, queries, entitlements, or invoice/payment data. "
                    "If objective is highest_score, choose the eligible candidate with the highest score."
                )
            },
            {"role": "user", "content": json.dumps(context, separators=(",", ":"))},
        ]
    }

    if provider in ("openai", "gemini", "groq"):
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "qma_agent_plan",
                "strict": True,
                "schema": schema
            }
        }
    else:
        payload["response_format"] = {"type": "json_object"}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        content = response.json().get("choices", [{}])[0].get("message", {}).get("content")
        return _normalize_model_plan(json.loads(content)) if content else None
    except Exception as exc:
        logger.warning("LLM plan unavailable or invalid; using deterministic fallback: %s", exc)
        return None


def _validate_llm_plan(deps: SimpleNamespace, plan: dict, candidates: list, entitlements: list, budget: float, max_price: float, objective: str, source: str = "llm") -> Optional[dict]:
    if plan["action"] == "clarify":
        return _decision_payload(deps, None, candidates, entitlements, budget, max_price, objective, source, plan["reason"], plan["requested_tier"], action="clarify")

    eligible = [item for item in candidates if not item.get("agent_rejection")]
    selected = next((item for item in candidates if item["candidate_id"] == plan["candidate_id"]), None)
    if objective == "highest_score" and eligible and plan["action"] == "purchase":
        authoritative = max(eligible, key=lambda item: _number(item.get("score")))
        if selected is not authoritative:
            selected = authoritative
            plan = dict(plan, action="purchase", candidate_id=authoritative["candidate_id"], reason="Policy selected the highest-scoring eligible candidate.")

    if plan["action"] == "skip":
        return _decision_payload(deps, None, candidates, entitlements, budget, max_price, objective, source, plan["reason"], plan["requested_tier"], action="skip")
    if not selected or selected.get("agent_rejection"):
        return None
    if plan["requested_tier"] not in ("auto", selected.get("agent_tier")):
        return None
    if plan["budget_usdc"] > budget or plan["max_price_usdc"] > max_price:
        return None
    return _decision_payload(deps, selected, candidates, entitlements, budget, max_price, objective, source, plan["reason"], plan["requested_tier"], action="purchase")


def _fallback_decision(deps: SimpleNamespace, candidates: list, entitlements: list, budget: float, max_price: float, objective: str, requested_tier: Optional[str]) -> dict:
    eligible = [item for item in candidates if not item.get("agent_rejection")]
    if objective == "highest_score":
        eligible.sort(key=lambda item: (bool(item.get("agent_upgrade_from_preview")), _number(item.get("score"))), reverse=True)
    else:
        eligible.sort(key=lambda item: (bool(item.get("agent_upgrade_from_preview")), _number(item.get("score")) / max(_number(item.get("agent_price")), 0.000001), _number(item.get("score"))), reverse=True)
    return _decision_payload(deps, eligible[0] if eligible else None, candidates, entitlements, budget, max_price, objective, "deterministic_policy", None, requested_tier)


def _fast_parse_decision(
    prompt: str,
    candidates: list,
    budget: float,
    max_price: float,
    provider_filter: Optional[str],
    tier_filter: Optional[str],
    objective: str,
) -> Optional[dict]:
    lowered = prompt.lower().strip()

    # Conversational Indicators (less aggressive list to allow "find/search/show/best" structured command routes)
    conversational_indicators = [
        "want to", "should i", "please", "can you", "why ", "how ",
        "what is", "think about", "recommend", "suggest", "decent"
    ]
    if any(indicator in lowered for indicator in conversational_indicators):
        return None

    is_buy_command = bool(re.search(r"\b(?:buy|purchase|get|grab|order)\b", lowered))
    if not is_buy_command:
        return None

    # Try matching candidate symbols from prompt
    target_symbol = None
    for candidate in candidates:
        symbol = candidate.get("symbol", "").upper()
        if symbol and re.search(rf"\b{re.escape(symbol.lower())}\b", lowered):
            target_symbol = symbol
            break

    eligible = [c for c in candidates if not c.get("agent_rejection")]
    if not eligible:
        return {
            "action": "skip",
            "candidate_id": None,
            "requested_tier": tier_filter or "auto",
            "budget_usdc": budget,
            "max_price_usdc": max_price,
            "reason": "Fast parser: No eligible candidates found.",
            "rejected_candidate_ids": [c["candidate_id"] for c in candidates]
        }

    if not target_symbol:
        return {
            "action": "skip",
            "candidate_id": None,
            "requested_tier": tier_filter or "auto",
            "budget_usdc": budget,
            "max_price_usdc": max_price,
            "reason": "Fast parser: No candidate symbol matched the explicit purchase command.",
            "rejected_candidate_ids": [c["candidate_id"] for c in candidates]
        }

    matched = eligible
    matched = [c for c in matched if c.get("symbol", "").upper() == target_symbol]
    if provider_filter:
        matched = [c for c in matched if c.get("provider_id", "").lower() == provider_filter]

    if not matched:
        return {
            "action": "skip",
            "candidate_id": None,
            "requested_tier": tier_filter or "auto",
            "budget_usdc": budget,
            "max_price_usdc": max_price,
            "reason": f"Fast parser: No eligible candidates matched filter. (Symbol: {target_symbol}, Provider: {provider_filter})",
            "rejected_candidate_ids": [c["candidate_id"] for c in candidates]
        }


    if objective == "highest_score":
        matched.sort(key=lambda item: (bool(item.get("agent_upgrade_from_preview")), _number(item.get("score"))), reverse=True)
    else:
        matched.sort(key=lambda item: (bool(item.get("agent_upgrade_from_preview")), _number(item.get("score")) / max(_number(item.get("agent_price")), 0.000001), _number(item.get("score"))), reverse=True)

    selected = matched[0]
    return {
        "action": "purchase",
        "candidate_id": selected["candidate_id"],
        "requested_tier": tier_filter or "auto",
        "budget_usdc": budget,
        "max_price_usdc": max_price,
        "reason": f"Fast parser: Matched simple command (Symbol: {selected.get('symbol')}, Provider: {selected.get('provider_id')}).",
        "rejected_candidate_ids": [c["candidate_id"] for c in candidates if c["candidate_id"] != selected["candidate_id"]]
    }


def make_agent_decision(
    deps: SimpleNamespace,
    *,
    prompt: str,
    wallet: Optional[str],
    budget_usdc: Optional[float],
    max_price_usdc: Optional[float],
    limit: int,
    allowed_providers: Optional[list[str]] = None,
    allowed_tiers: Optional[list[str]] = None,
    minimum_score: Optional[float] = None,
    use_llm: bool = True,
    use_laya: Optional[bool] = None,
) -> dict:
    """
    Evaluates buyer agent intent and ranks candidate purchase items using a 4-Tier Cascade:

    [Incoming Buyer Prompt]
             │
             ▼
     ┌───────────────┐
     │ Tier 0: Regex │  --> <1ms: Fast regex pattern matching for deterministic requests.
     └───────┬───────┘
             │ (If prompt requires natural language comprehension)
             ▼
     ┌───────────────┐
     │ Tier 1: LAYA  │  --> Sub-35ms: Local Non-autoregressive Neural Router (convaiinnovations/laya).
     └───────┬───────┘      Predicts intent (purchase / skip / clarify) & ranks candidates without Cloud LLM latency.
             │ (If Laya is disabled, package not installed, or confidence < 0.65)
             ▼
     ┌───────────────┐
     │ Tier 2: LLM   │  --> 1-3s: Autoregressive Cloud LLM (OpenAI / Gemini / Groq).
     └───────┬───────┘      Handles complex multi-variable reasoning and nuanced semantic instructions.
             │ (If LLM times out, errors, or produces invalid schema)
             ▼
     ┌───────────────┐
     │ Tier 3: Greedy│  --> <1ms: Deterministic mathematical ranking (highest win-rate / value-density).
     └───────────────┘      Guaranteed safe fallback to ensure the agent never crashes or deadlocks.
    """
    # 0. Prompt Injection Sanitization (ECC llm-trading-agent-security)
    try:
        clean_prompt = sanitize_financial_prompt(prompt)
    except FinancialPromptInjectionError as inject_err:
        logger.warning("Adversarial financial prompt injection rejected: %s", inject_err)
        return {
            "action": "skip",
            "candidate_id": None,
            "requested_tier": "auto",
            "budget_usdc": 0.0,
            "max_price_usdc": 0.0,
            "reason": f"Security alert: {inject_err}",
            "rejected_candidate_ids": [],
            "candidates": [],
            "decision_source": "security_sanitizer",
            "objective": "security_reject",
        }

    budget, max_price, provider_filter, tier_filter = _prompt_policy(clean_prompt, budget_usdc, max_price_usdc)
    lowered_prompt = clean_prompt.lower()
    objective = "highest_score" if any(term in lowered_prompt for term in ("best", "highest", "strongest", "top")) else "value_density"
    recommendation_data = deps.get_agent_recommendations(limit)
    entitlements = deps.load_wallet_entitlements(wallet) if wallet else []
    candidates = _prepare_candidates(
        deps,
        recommendation_data.get("recommendations", []),
        entitlements,
        budget,
        max_price,
        provider_filter,
        tier_filter,
        allowed_providers,
        allowed_tiers,
        minimum_score,
    )

    def _guard_check(decision: dict) -> dict:
        if decision.get("action") == "purchase":
            price_val = Decimal(str(decision.get("max_price_usdc") or "0.005"))
            allowed, spend_reason = get_spend_limit_guard().can_spend(wallet, price_val)
            if not allowed:
                logger.warning("SpendLimitGuard blocked autonomous purchase: %s", spend_reason)
                decision["action"] = "skip"
                decision["reason"] = f"Spend Guard: {spend_reason}"
                decision["agent_rejection"] = "spend_policy_exceeded"
        return decision

    # Try Fast Parser first (Tier 0: <1ms regex)
    fast_plan = _fast_parse_decision(clean_prompt, candidates, budget, max_price, provider_filter, tier_filter, objective)
    if fast_plan:
        validated = _validate_llm_plan(deps, fast_plan, candidates, entitlements, budget, max_price, objective, source="fast_parser")
        if validated is not None:
            return _guard_check(validated)

    # Try Laya System 1 Decision Engine (Tier 1: Local Non-autoregressive Neural Router, sub-35ms)
    laya_active = use_laya is True or (
        use_laya is None and (
            os.getenv("QMA_USE_LAYA", "").lower() in ("1", "true", "yes")
            or os.getenv("QMA_LLM_PROVIDER", "").lower() == "laya"
        )
    )
    if laya_active:
        try:
            from backend.app.services.laya_decision import predict_laya_plan
            laya_plan = predict_laya_plan(
                prompt=clean_prompt,
                budget=budget,
                max_price=max_price,
                candidates=candidates,
                entitlements=entitlements,
                fallback_objective=objective,
                provider_filter=provider_filter,
                tier_filter=tier_filter,
            )
            if laya_plan:
                validated = _validate_llm_plan(deps, laya_plan, candidates, entitlements, budget, max_price, objective, source="laya_system_one")
                if validated is not None:
                    return _guard_check(validated)
        except Exception as laya_err:
            logger.warning("Laya decision router skipped: %s", laya_err)

    # Try LLM Plan (Tier 2: Autoregressive Cloud LLM via OpenAI/Gemini/Groq)
    llm_plan = _llm_decision(clean_prompt, budget, max_price, candidates, entitlements, objective) if use_llm else None
    if llm_plan:
        validated = _validate_llm_plan(deps, llm_plan, candidates, entitlements, budget, max_price, objective)
        if validated is not None:
            return _guard_check(validated)
        logger.warning("Rejected invalid LLM plan; using deterministic fallback.")
    fallback_res = _fallback_decision(deps, candidates, entitlements, budget, max_price, objective, tier_filter)
    return _guard_check(fallback_res)
