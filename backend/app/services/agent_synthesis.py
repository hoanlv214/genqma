"""
Hybrid Agent Synthesis Service for QMA Vestiarion.

Implements the BYO-Key (Bring Your Own Key) architecture:
- Scenario A (Default): Returns pure quantitative metrics with zero LLM inference cost on server.
- Scenario B (BYO-Key): When user provides an LLM key, specialized analyst sub-agents synthesize
  natural language executive briefings and actionable hedge commentary.
"""

import json
import logging
import os
from typing import Any, Dict, Optional
import requests

logger = logging.getLogger("QMA-AgentSynthesis")


def generate_agent_synthesis(
    *,
    provider_id: str,
    symbol: str,
    metrics: Dict[str, Any],
    api_key: Optional[str] = None,
    llm_provider: str = "auto",
) -> Optional[Dict[str, Any]]:
    """
    Synthesize an executive intelligence commentary using client-supplied API key.
    Fails closed gracefully: if the LLM call fails or times out, the report delivers
    pure quantitative metrics without blocking.
    """
    key = (api_key or os.getenv("USER_LLM_API_KEY", "")).strip()
    if not key:
        return None

    # Detect provider
    if llm_provider == "auto":
        if key.startswith("AIza"):
            llm_provider = "gemini"
        elif key.startswith("gsk_"):
            llm_provider = "groq"
        else:
            llm_provider = "openai"

    role_title = {
        "funding_memory": "Funding Arbitrage & Liquidity Squeeze Specialist",
        "polymarket_divergence": "Cross-Market Prediction & Basis Arbitrage Specialist",
        "pyth_stress_band": "Low-Latency Oracle Volatility & Risk Specialist",
    }.get(provider_id, "Quantitative Intelligence Specialist")

    compact_metrics = {
        k: v for k, v in metrics.items()
        if k not in ("invoice", "invoice_id", "tier", "provider_id", "upgrade_cta", "cctp_bridge_required")
    }

    prompt = (
        f"You are the {role_title} at QMA Vestiarion, an autonomous quant firm.\n"
        f"Analyze the following quantitative metrics for {symbol}:\n"
        f"{json.dumps(compact_metrics, default=str)}\n\n"
        "Provide a concise 2-3 sentence executive briefing for an autonomous trading desk: "
        "1. Identify the core market anomaly. 2. Assess directional bias and squeeze probability. 3. Recommend an actionable hedge."
    )

    try:
        if llm_provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(url, json=payload, timeout=4.0)
            if res.status_code == 200:
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return {
                    "analyst_role": role_title,
                    "executive_briefing": text,
                    "synthesis_engine": "Gemini 1.5 Flash (BYO-Key)",
                    "status": "ACTIVE_SYNTHESIS",
                }
        elif llm_provider == "groq":
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": f"You are the {role_title}."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 180,
                "temperature": 0.2,
            }
            res = requests.post(url, headers=headers, json=payload, timeout=4.0)
            if res.status_code == 200:
                data = res.json()
                text = data["choices"][0]["message"]["content"].strip()
                return {
                    "analyst_role": role_title,
                    "executive_briefing": text,
                    "synthesis_engine": "Llama 3.1 8B via Groq (BYO-Key)",
                    "status": "ACTIVE_SYNTHESIS",
                }
        else:
            # Default OpenAI
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": f"You are the {role_title}."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 180,
                "temperature": 0.2,
            }
            res = requests.post(url, headers=headers, json=payload, timeout=4.0)
            if res.status_code == 200:
                data = res.json()
                text = data["choices"][0]["message"]["content"].strip()
                return {
                    "analyst_role": role_title,
                    "executive_briefing": text,
                    "synthesis_engine": "GPT-4o-mini (BYO-Key)",
                    "status": "ACTIVE_SYNTHESIS",
                }
    except Exception as exc:
        logger.warning("BYO-Key synthesis failed: %s; falling back to pure metrics", exc)

    return None
