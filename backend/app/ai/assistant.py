from __future__ import annotations

import logging

from app.ai import offline
from app.ai.providers import ProviderError, ask_gemini, ask_openai
from app.ai.tools import ToolContext
from app.ai.verify import verify_numbers
from app.core.config import Settings

log = logging.getLogger(__name__)


def resolve_provider(settings: Settings) -> str:
    p = settings.ai_provider.lower()
    if p == "auto":
        if settings.gemini_api_key:
            return "gemini"
        if settings.openai_api_key:
            return "openai"
        return "offline"
    if p == "gemini" and not settings.gemini_api_key:
        return "offline"
    if p == "openai" and not settings.openai_api_key:
        return "offline"
    return p


def ask(question: str, ctx: ToolContext, settings: Settings) -> dict:
    provider = resolve_provider(settings)
    fallback_reason = None
    try:
        if provider == "gemini":
            text, calls = ask_gemini(question, ctx, settings.gemini_api_key or "", settings.gemini_model)
        elif provider == "openai":
            text, calls = ask_openai(question, ctx, settings.openai_api_key or "", settings.openai_model)
        else:
            text, calls = offline.answer(question, ctx)
    except (ProviderError, Exception) as e:  # never leave the user without an answer
        log.warning("LLM provider failed, falling back to rule-based assistant: %s", e)
        fallback_reason = "LLM provider unavailable; answered by the rule-based engine."
        provider = "offline"
        text, calls = offline.answer(question, ctx)

    if not text:
        text, calls, provider = *offline.answer(question, ctx), "offline"

    unverified = verify_numbers(text, [c["result"] for c in calls], question)
    return {
        "answer": text,
        "provider": provider,
        "mode": "llm_tool_calling" if provider in ("gemini", "openai") else "rule_based",
        "tool_calls": calls,
        "numeric_claims_verified": not unverified,
        "unverified_values": unverified,
        "notice": fallback_reason,
        "label": "Numbers are MODEL-ESTIMATED by the ApexVision simulation, not CFD or real-car data.",
    }
