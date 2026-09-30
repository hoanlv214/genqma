"""Agent Financial Security & Prompt Injection Defense.

Adapted from ECC skill: llm-trading-agent-security.
Enforces that off-chain natural language inputs, webhooks, or social feeds
cannot manipulate autonomous agent wallets, bypass spending policies,
or execute unauthorized fund transfers.
"""

import re
from typing import Optional, Tuple


class FinancialPromptInjectionError(ValueError):
    """Raised when an adversarial or injection payload is detected in a financial prompt."""
    pass


# Specific patterns representing unauthorized financial or instruction hijacking
INJECTION_RULES = [
    # System / directive overrides
    (r"(?:ignore|disregard|forget)\s+(?:previous|all|prior)\s+(?:instructions?|directives?|prompts?|rules?)", "system_override"),
    (r"new\s+(?:directive|instruction|task|system\s+prompt)\s*:", "system_override"),
    (r"system\s*prompt\s*:\s*you\s+are", "system_override"),
    (r"act\s+as\s+(?:an?\s+evil|an?\s+unrestricted|a\s+jailbroken)\s+(?:bot|agent|assistant)", "jailbreak_attempt"),

    # Direct financial transfer / drain commands targeting EVM addresses
    (r"(?:send|transfer|withdraw)\s+.*?\s+(?:to|towards)\s+0x[0-9a-fA-F]{40}", "transfer_directive"),
    (r"(?:drain|empty|steal)\s+(?:the\s+)?(?:wallet|treasury|vault|balance|funds)", "drain_directive"),

    # Token approval tampering
    (r"approve\s+.*?\s+(?:for|to)\s+0x[0-9a-fA-F]{40}", "approval_directive"),

    # Spending policy and budget limit bypass attempts
    (r"(?:override|bypass|disable|ignore)\s+(?:the\s+)?(?:budget|limit|spending\s+policy|daily\s+cap|circuit\s+breaker)", "limit_tampering"),

    # Malicious HTML/Script injection
    (r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "malicious_markup"),
    (r"javascript\s*:\s*[^\s]+", "malicious_markup"),
]

# Control characters filter (preserve newlines, tabs, standard printable characters)
CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]|\x1b\[[0-9;]*[a-zA-Z]")
MAX_PROMPT_LENGTH = 2000


def detect_financial_prompt_injection(prompt: str) -> Tuple[bool, Optional[str]]:
    """Inspects a prompt for adversarial financial prompt injection patterns.

    Returns:
        (is_attack, rule_category) if detected, otherwise (False, None).
    """
    if not prompt or not isinstance(prompt, str):
        return False, None

    normalized = prompt.strip()
    for pattern, category in INJECTION_RULES:
        if re.search(pattern, normalized, re.IGNORECASE | re.DOTALL):
            return True, category

    return False, None


def sanitize_financial_prompt(prompt: str) -> str:
    """Sanitizes an incoming user or agent prompt string.

    1. Removes ANSI escape codes and ASCII control characters.
    2. Enforces maximum length bounds.
    3. Runs financial prompt injection detection.

    Raises:
        FinancialPromptInjectionError if adversarial injection is detected.
        ValueError if prompt exceeds maximum bounds.
    """
    if prompt is None:
        return ""

    if not isinstance(prompt, str):
        prompt = str(prompt)

    # 1. Clean control characters & ANSI sequences
    cleaned = CONTROL_CHAR_REGEX.sub("", prompt).strip()

    # 2. Length check
    if len(cleaned) > MAX_PROMPT_LENGTH:
        raise ValueError(f"Prompt length ({len(cleaned)}) exceeds maximum allowed ({MAX_PROMPT_LENGTH}).")

    # 3. Injection check
    is_attack, category = detect_financial_prompt_injection(cleaned)
    if is_attack:
        raise FinancialPromptInjectionError(
            f"Adversarial financial prompt injection detected (class: {category}). "
            f"Transaction planning rejected for safety."
        )

    return cleaned
