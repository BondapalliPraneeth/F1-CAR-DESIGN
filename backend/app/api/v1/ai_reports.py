from __future__ import annotations

import html
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.assistant import ask
from app.ai.tools import ToolContext
from app.api.schemas import AskRequest, AskResponse
from app.core.config import get_settings
from app.db import repository as repo
from app.db.session import get_db
from app.domain.components import COMPONENTS_BY_ID

router = APIRouter(tags=["ai", "reports"])
_hits: dict[str, deque] = defaultdict(deque)
_global_hits: deque = deque()
_MAX_TRACKED_CLIENTS = 10_000


def _prune(q: deque, now: float) -> None:
    while q and now - q[0] > 60:
        q.popleft()


def _rate_limit(request: Request) -> None:
    """Sliding-window limits protecting the public demo's API key.

    The per-client limit keys on the first X-Forwarded-For entry, which a client can
    spoof, so it only provides fairness. The global limit bounds total LLM usage
    regardless of headers, and the client table is pruned so it cannot grow without bound.
    """
    s = get_settings()
    now = time.monotonic()
    _prune(_global_hits, now)
    if len(_global_hits) >= s.ai_global_rate_limit_per_minute:
        raise HTTPException(status_code=429, detail={"error": "rate_limited", "message": "The assistant is busy. Please try again in a minute."})
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()[:64]
    if len(_hits) > _MAX_TRACKED_CLIENTS:
        for key in [k for k, v in _hits.items() if not v or now - v[-1] > 60]:
            del _hits[key]
    q = _hits[ip]
    _prune(q, now)
    if len(q) >= s.ai_rate_limit_per_minute:
        raise HTTPException(status_code=429, detail={"error": "rate_limited", "message": f"Max {s.ai_rate_limit_per_minute} questions per minute."})
    q.append(now)
    _global_hits.append(now)


@router.post("/ai/ask", response_model=AskResponse)
def ai_ask(req: AskRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    _rate_limit(request)
    if req.selected_component and req.selected_component not in COMPONENTS_BY_ID:
        raise HTTPException(status_code=422, detail={"error": "unknown_component", "component_id": req.selected_component})
    ctx = ToolContext(assumptions=req.assumptions, damages=req.damages, selected_component=req.selected_component)
    out = ask(req.question, ctx, get_settings())
    try:
        repo.save_conversation(db, session_id=req.session_id, question=req.question, answer=out["answer"],
                               provider=out["provider"], tool_calls=[{"tool": c["tool"], "args": c["args"]} for c in out["tool_calls"]])
    except SQLAlchemyError:
        db.rollback()
    return out


@router.get("/reports/{report_id}")
def get_report(report_id: str, format: str = Query("json", pattern="^(json|md|html)$"), db: Session = Depends(get_db)):
    rep = repo.get_report(db, report_id)
    if not rep:
        raise HTTPException(status_code=404, detail={"error": "report_not_found", "report_id": report_id})
    if format == "md":
        return PlainTextResponse(rep.markdown, media_type="text/markdown",
                                 headers={"Content-Disposition": f'attachment; filename="apexvision-report-{rep.id[:8]}.md"'})
    if format == "html":
        return HTMLResponse(_md_to_html(rep.title, rep.markdown))
    return {"id": rep.id, "simulation_id": rep.simulation_id, "title": rep.title, "created_at": rep.created_at,
            "markdown": rep.markdown, "payload": rep.payload}


def _md_to_html(title: str, md: str) -> str:
    """Minimal, dependency-free Markdown rendering for printable reports (headings, lists, tables, bold)."""
    import re

    out, in_table, in_list = [], False, False
    for raw in md.splitlines():
        line = html.escape(raw)
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        line = re.sub(r"`(.+?)`", r"<code>\1</code>", line)
        if raw.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if not in_table:
                out.append("<table>")
                in_table = True
                out.append("<tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
        if raw.startswith("- ") or re.match(r"^\d+\. ", raw):
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = re.sub(r"^(- |\d+\. )", "", line)
            out.append(f"<li>{item}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if raw.startswith("### "):
            out.append(f"<h3>{line[4:]}</h3>")
        elif raw.startswith("## "):
            out.append(f"<h2>{line[3:]}</h2>")
        elif raw.startswith("# "):
            out.append(f"<h1>{line[2:]}</h1>")
        elif raw.startswith("&gt; "):
            out.append(f"<blockquote>{line[5:]}</blockquote>")
        elif raw.strip():
            out.append(f"<p>{line}</p>")
    if in_table:
        out.append("</table>")
    if in_list:
        out.append("</ul>")
    css = ("body{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#111;line-height:1.5}"
           "table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.9rem}td,th{border:1px solid #ccc;padding:.35rem .5rem;text-align:left}"
           "th{background:#f2f4f7}blockquote{border-left:4px solid #e11d48;margin:1rem 0;padding:.5rem 1rem;background:#fff5f6}"
           "h1{font-size:1.5rem}h2{margin-top:2rem;border-bottom:1px solid #ddd}@media print{body{margin:0}}")
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>{css}</style></head>"
            f"<body>{''.join(out)}<p><button onclick='window.print()'>Print / save as PDF</button></p></body></html>")
