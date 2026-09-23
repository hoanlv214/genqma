"""Laya Non-Autoregressive System 1 Decision Engine for QMA Agents.

Provides sub-35ms neural classification and candidate routing over 100+ languages
using local encoder checkpoints (ModernBERT-large / mmBERT-base) trained with RLCD.
Zero text generation, zero hallucination, zero cloud token costs.
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("QMA-LayaDecision")

DEFAULT_EN_PATH = os.getenv("QMA_LAYA_MODEL_PATH_EN", os.path.expanduser(r"~/.cache/laya_models/english"))
DEFAULT_ML_PATH = os.getenv("QMA_LAYA_MODEL_PATH_ML", os.path.expanduser(r"~/.cache/laya_models/multilingual"))

# Decision Questions for QMA System 1
QMA_DECISION_QUESTIONS: Dict[str, Any] = {
    "action": {
        "type": "choice",
        "instructions": "Should the financial agent purchase a market intelligence report, skip, or clarify?",
        "criteria": {
            "purchase": "the user explicitly wants to buy, order, get, find, grab, or purchase market intelligence, signals, or reports",
            "skip": "the user explicitly declines, says no, cancels, stops, or requests not to buy anything",
            "clarify": "ambiguous request, general greeting, off-topic question, or unclear intent",
        },
    },
    "objective": {
        "type": "choice",
        "instructions": "What is the ranking objective of the user?",
        "criteria": {
            "highest_score": "the user prioritizes the highest score, best quality, most accurate, top signal, or maximum confidence",
            "value_density": "the user prioritizes low cost, affordability, best value for money, cheapest, or staying well below budget",
        },
    },
    "requested_tier": {
        "type": "choice",
        "instructions": "Which data tier is desired?",
        "criteria": {
            "preview": "the user specifically requests preview, summary, teaser, sneak peek, or low cost tier",
            "full": "the user specifically requests full, deep dive, comprehensive, or complete report tier",
            "auto": "no specific tier preference specified, auto selection",
        },
    },
}


class LayaDecisionEngine:
    """Manages loaded Laya model instances for instant inference."""

    _instance: Optional["LayaDecisionEngine"] = None

    def __init__(self) -> None:
        self._en_agent: Optional[Any] = None
        self._ml_agent: Optional[Any] = None
        self._laya_module: Optional[Any] = None
        self._available: Optional[bool] = None

    @classmethod
    def get_instance(cls) -> "LayaDecisionEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_available(self) -> bool:
        if os.getenv("QMA_DISABLE_LAYA", "").lower() in ("1", "true", "yes"):
            return False
        if self._available is not None:
            return self._available
        try:
            import laya  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
            logger.info("Laya package is not installed; System 1 neural router disabled.")
        return self._available

    def _get_laya(self) -> Any:
        if self._laya_module is None:
            import laya
            self._laya_module = laya
        return self._laya_module

    def _detect_multilingual(self, text: str) -> bool:
        """Sub-millisecond detection whether text requires multilingual checkpoint."""
        laya = self._get_laya()
        try:
            detection = laya.detect_language(text)
            # If not English or contains diacritics / non-latin, use multilingual checkpoint
            return not bool(detection.get("is_english", True)) or bool(detection.get("diacritic_rate", 0) > 0.02)
        except Exception:
            # Fallback heuristic
            has_non_ascii = any(ord(c) > 127 for c in text)
            return has_non_ascii

    def get_agent(self, text: str) -> Optional[Any]:
        if not self.is_available():
            return None
        laya = self._get_laya()
        needs_multilingual = self._detect_multilingual(text)

        if needs_multilingual:
            if self._ml_agent is None:
                path = DEFAULT_ML_PATH if os.path.isdir(DEFAULT_ML_PATH) else "convaiinnovations/laya"
                subfolder = None if os.path.isdir(DEFAULT_ML_PATH) else "multilingual"
                logger.info("Loading Laya Multilingual model from %s...", path)
                self._ml_agent = laya.load(path, subfolder=subfolder)
            return self._ml_agent
        else:
            if self._en_agent is None:
                path = DEFAULT_EN_PATH if os.path.isdir(DEFAULT_EN_PATH) else "convaiinnovations/laya"
                logger.info("Loading Laya English model from %s...", path)
                self._en_agent = laya.load(path)
            return self._en_agent

    def evaluate(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Run single forward-pass typed evaluation over user prompt."""
        try:
            agent = self.get_agent(prompt)
            if agent is None:
                return None
            state = {"task": prompt}
            res = agent.predict(state, QMA_DECISION_QUESTIONS)
            answers = res.get("answers", {})
            return {
                "action": answers.get("action", {}).get("choice", "clarify"),
                "action_confidence": answers.get("action", {}).get("confidence", 0.0),
                "action_probs": answers.get("action", {}).get("probabilities", {}),
                "objective": answers.get("objective", {}).get("choice", "value_density"),
                "objective_confidence": answers.get("objective", {}).get("confidence", 0.0),
                "tier": answers.get("requested_tier", {}).get("choice", "auto"),
                "tier_confidence": answers.get("requested_tier", {}).get("confidence", 0.0),
                "model": res.get("model", "laya-rl-agent"),
            }
        except Exception as exc:
            logger.warning("Laya evaluation failed; falling back to secondary tier: %s", exc)
            return None


def predict_laya_plan(
    *,
    prompt: str,
    budget: float,
    max_price: float,
    candidates: List[Dict[str, Any]],
    entitlements: List[Dict[str, Any]],
    fallback_objective: str,
    provider_filter: Optional[str] = None,
    tier_filter: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Construct a validated QMA purchase plan using Laya System 1 decision engine.
    Returns None if Laya is unavailable or predicts clarification is needed.
    """
    engine = LayaDecisionEngine.get_instance()
    if not engine.is_available():
        return None

    evaluation = engine.evaluate(prompt)
    if not evaluation:
        return None

    action = evaluation["action"]
    objective = evaluation["objective"] or fallback_objective
    requested_tier = tier_filter or evaluation["tier"]
    confidence = evaluation.get("action_confidence", 0.0)

    # If ambiguous/clarify, let caller handle clarification or fallback
    if action == "clarify":
        return {
            "action": "clarify",
            "candidate_id": None,
            "requested_tier": requested_tier if requested_tier in ("preview", "full", "auto") else "auto",
            "budget_usdc": budget,
            "max_price_usdc": max_price,
            "reason": f"Laya System 1: Ambiguous prompt requiring user clarification (confidence: {confidence:.2f}).",
            "rejected_candidate_ids": [c["candidate_id"] for c in candidates if "candidate_id" in c],
        }

    # If explicit skip / decline
    if action == "skip":
        return {
            "action": "skip",
            "candidate_id": None,
            "requested_tier": requested_tier if requested_tier in ("preview", "full", "auto") else "auto",
            "budget_usdc": budget,
            "max_price_usdc": max_price,
            "reason": f"Laya System 1: User requested to skip/cancel (confidence: {confidence:.2f}).",
            "rejected_candidate_ids": [c["candidate_id"] for c in candidates if "candidate_id" in c],
        }

    # Action == "purchase"
    eligible = [c for c in candidates if not c.get("agent_rejection")]
    if not eligible:
        return {
            "action": "skip",
            "candidate_id": None,
            "requested_tier": requested_tier if requested_tier in ("preview", "full", "auto") else "auto",
            "budget_usdc": budget,
            "max_price_usdc": max_price,
            "reason": "Laya System 1: No candidates met policy constraints.",
            "rejected_candidate_ids": [c["candidate_id"] for c in candidates if "candidate_id" in c],
        }

    # Match target symbol from prompt if present
    lowered_prompt = prompt.lower()
    matched = list(eligible)
    target_symbol = None
    for candidate in candidates:
        sym = (candidate.get("symbol") or "").upper()
        if sym and re.search(rf"\b{re.escape(sym.lower())}\b", lowered_prompt):
            target_symbol = sym
            break

    if target_symbol:
        matched = [c for c in matched if (c.get("symbol") or "").upper() == target_symbol]

    # Filter provider if requested
    if provider_filter:
        matched = [c for c in matched if (c.get("provider_id") or "").lower() == provider_filter.lower()]

    if not matched:
        return {
            "action": "skip",
            "candidate_id": None,
            "requested_tier": requested_tier if requested_tier in ("preview", "full", "auto") else "auto",
            "budget_usdc": budget,
            "max_price_usdc": max_price,
            "reason": f"Laya System 1: No eligible candidates matched filter (symbol={target_symbol}, provider={provider_filter}).",
            "rejected_candidate_ids": [c["candidate_id"] for c in candidates if "candidate_id" in c],
        }

    # Rank matched candidates based on Laya's evaluated objective
    def _cand_score(item: Dict[str, Any]) -> float:
        try:
            return float(item.get("score") or 0.0)
        except (ValueError, TypeError):
            return 0.0

    def _cand_price(item: Dict[str, Any]) -> float:
        try:
            p = float(item.get("agent_price") or 0.0)
            return p if p > 0 else 0.000001
        except (ValueError, TypeError):
            return 0.000001

    if objective == "highest_score":
        matched.sort(
            key=lambda item: (bool(item.get("agent_upgrade_from_preview")), _cand_score(item)),
            reverse=True,
        )
    else:
        matched.sort(
            key=lambda item: (
                bool(item.get("agent_upgrade_from_preview")),
                _cand_score(item) / _cand_price(item),
                _cand_score(item),
            ),
            reverse=True,
        )

    selected = matched[0]
    return {
        "action": "purchase",
        "candidate_id": selected["candidate_id"],
        "requested_tier": requested_tier if requested_tier in ("preview", "full", "auto") else "auto",
        "budget_usdc": budget,
        "max_price_usdc": max_price,
        "reason": (
            f"Laya System 1: Selected candidate {selected.get('symbol')} "
            f"from {selected.get('provider_id')} (objective={objective}, conf={confidence:.2f})."
        )[:240],
        "rejected_candidate_ids": [
            c["candidate_id"] for c in candidates
            if "candidate_id" in c and c["candidate_id"] != selected["candidate_id"]
        ],
    }
