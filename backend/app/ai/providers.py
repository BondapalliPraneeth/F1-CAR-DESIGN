"""LLM providers (Gemini, OpenAI) with native tool calling over plain HTTPS.

The model must call tools to obtain any number; the system prompt forbids
inventing values, and app.ai.verify independently checks every number.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.ai.tools import TOOLS, ToolContext, run_tool

SYSTEM_PROMPT = """You are the ApexVision 3D engineering assistant: a senior race-car vehicle-performance and aerodynamics engineer.
Rules (strict):
1. Any number you state (forces, temperatures, lap times, percentages, balances) MUST come from a tool result in this conversation. Call tools first. Never estimate, recall or invent numerical values.
2. All values are MODEL-ESTIMATED from a simplified engineering model, not CFD, and not data from any real F1 car. Say so when quoting numbers.
3. If a tool cannot answer, say what is unknown instead of guessing.
4. Explain mechanisms physically (pressure, load, balance, thermal), concisely, for an engineering audience. Use markdown, max ~220 words.
5. 'simulate_component_damage' is hypothetical and does not change the user's car. Make that clear.
Context: selected component = {selected}. Current damages = {damages}."""

MAX_STEPS = 5
TIMEOUT = httpx.Timeout(40.0)


def _system(ctx: ToolContext) -> str:
    dmg = [d.model_dump() for d in ctx.damages if d.severity > 0] or "none"
    return SYSTEM_PROMPT.format(selected=ctx.selected_component or "none", damages=dmg)


class ProviderError(RuntimeError):
    pass


def ask_gemini(question: str, ctx: ToolContext, api_key: str, model: str) -> tuple[str, list[dict]]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    tools = [{"functionDeclarations": [
        {"name": n, "description": d, **({"parameters": s} if s.get("properties") else {})} for n, (_, d, s) in TOOLS.items()
    ]}]
    contents: list[dict[str, Any]] = [{"role": "user", "parts": [{"text": question}]}]
    calls: list[dict] = []
    with httpx.Client(timeout=TIMEOUT) as client:
        for _ in range(MAX_STEPS):
            resp = client.post(url, headers={"x-goog-api-key": api_key}, json={
                "systemInstruction": {"parts": [{"text": _system(ctx)}]},
                "contents": contents, "tools": tools,
                "generationConfig": {"temperature": 0.2},
            })
            if resp.status_code != 200:
                raise ProviderError(f"Gemini HTTP {resp.status_code}: {resp.text[:300]}")
            cand = (resp.json().get("candidates") or [{}])[0]
            parts = cand.get("content", {}).get("parts", [])
            fcalls = [p["functionCall"] for p in parts if "functionCall" in p]
            if not fcalls:
                return "".join(p.get("text", "") for p in parts).strip(), calls
            contents.append({"role": "model", "parts": parts})
            responses = []
            for fc in fcalls:
                result = run_tool(ctx, fc["name"], fc.get("args") or {})
                calls.append({"tool": fc["name"], "args": fc.get("args") or {}, "result": result})
                responses.append({"functionResponse": {"name": fc["name"], "response": {"result": result}}})
            contents.append({"role": "user", "parts": responses})
    raise ProviderError("Gemini exceeded the tool-calling step limit")


def ask_openai(question: str, ctx: ToolContext, api_key: str, model: str) -> tuple[str, list[dict]]:
    tools = [{"type": "function", "function": {"name": n, "description": d, "parameters": s}} for n, (_, d, s) in TOOLS.items()]
    messages: list[dict[str, Any]] = [{"role": "system", "content": _system(ctx)}, {"role": "user", "content": question}]
    calls: list[dict] = []
    with httpx.Client(timeout=TIMEOUT) as client:
        for _ in range(MAX_STEPS):
            resp = client.post("https://api.openai.com/v1/chat/completions",
                               headers={"Authorization": f"Bearer {api_key}"},
                               json={"model": model, "messages": messages, "tools": tools, "temperature": 0.2})
            if resp.status_code != 200:
                raise ProviderError(f"OpenAI HTTP {resp.status_code}: {resp.text[:300]}")
            msg = resp.json()["choices"][0]["message"]
            tcs = msg.get("tool_calls") or []
            if not tcs:
                return (msg.get("content") or "").strip(), calls
            messages.append(msg)
            for tc in tcs:
                args = json.loads(tc["function"].get("arguments") or "{}")
                result = run_tool(ctx, tc["function"]["name"], args)
                calls.append({"tool": tc["function"]["name"], "args": args, "result": result})
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(result)})
    raise ProviderError("OpenAI exceeded the tool-calling step limit")
