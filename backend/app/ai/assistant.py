from __future__ import annotations

import logging

from app.ai import offline
from app.ai.providers import ProviderError, ask_gemini, ask_neon, ask_openai
from app.ai.tools import ToolContext
from app.ai.verify import verify_numbers
from app.core.config import Settings

log = logging.getLogger(__name__)

LLM_PROVIDERS = ("gemini", "openai", "neon")


def _configured(settings: Settings, provider: str) -> bool:
    if provider == "gemini":
        return bool(settings.gemini_api_key)
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider == "neon":
        return bool(settings.neon_ai_gateway_base_url and settings.neon_ai_gateway_token)
    return provider == "offline"


def resolve_provider(settings: Settings) -> str:
    p = settings.ai_provider.lower()
    if p == "auto":
        return next((x for x in LLM_PROVIDERS if _configured(settings, x)), "offline")
    return p if _configured(settings, p) else "offline"


def ask(question: str, ctx: ToolContext, settings: Settings) -> dict:
    provider = resolve_provider(settings)
    fallback_reason = None
    try:
        if provider == "gemini":
            text, calls = ask_gemini(question, ctx, settings.gemini_api_key or "", settings.gemini_model)
        elif provider == "openai":
            text, calls = ask_openai(question, ctx, settings.openai_api_key or "", settings.openai_model)
        elif provider == "neon":
            text, calls = ask_neon(question, ctx, settings.neon_ai_gateway_base_url or "",
                                   settings.neon_ai_gateway_token or "", settings.neon_ai_model)
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
        "mode": "llm_tool_calling" if provider in LLM_PROVIDERS else "rule_based",
        "tool_calls": calls,
        "numeric_claims_verified": not unverified,
        "unverified_values": unverified,
        "notice": fallback_reason,
        "label": "Numbers are MODEL-ESTIMATED by the ApexVision simulation, not CFD or real-car data.",
    }
