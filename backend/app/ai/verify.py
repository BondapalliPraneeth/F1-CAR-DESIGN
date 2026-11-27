"""Numeric-claim verification: every number in an AI answer must be traceable
to a tool output (or to the user's question). Untraceable numbers are reported
back to the UI so fabricated values are visible, never silently accepted."""

from __future__ import annotations

import re
from typing import Any

_NUM = re.compile(r"(?<![\w.])[-+−]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])[-+−]?\d+(?:\.\d+)?")
# Thousands grouped with a thin / narrow no-break / no-break space ("11 963 N"), as some LLMs write them.
_SEPS = "".join(map(chr, (0x2009, 0x202F, 0x00A0)))  # thin, narrow no-break, no-break space
_SPACE_GROUP = re.compile(rf"(?<=\d)[{_SEPS}](?=\d{{3}}(?!\d))")


def _numbers(text: str) -> list[str]:
    return _NUM.findall(_SPACE_GROUP.sub("", text))


def _flatten_numbers(obj: Any, out: list[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _flatten_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _flatten_numbers(v, out)
    elif isinstance(obj, str):
        out.extend(_parse(obj))


def _parse(text: str) -> list[float]:
    vals = []
    for m in _numbers(text):
        try:
            vals.append(float(m.replace(",", "").replace("−", "-")))
        except ValueError:
            pass
    return vals


def _matches(x: float, refs: list[float]) -> bool:
    for y in refs:
        for cand in (y, abs(y), y * 100, y / 100):
            if abs(x - cand) <= max(0.051, 0.01 * abs(cand)):
                return True
            # tolerate rounding to fewer decimals (e.g. 11963 -> "12,000" or "12k")
            if abs(cand) >= 1000 and abs(x - cand) <= 0.02 * abs(cand):
                return True
    return False


def _model_constants() -> list[float]:
    """Fixed, documented reference points of the model (speed grid, reference speed,
    corner radii, severity thresholds) that answers may legitimately quote."""
    from app.simulation.vehicle import CORNER_RADII, REFERENCE_SPEED_KMH, SPEED_GRID

    return [float(REFERENCE_SPEED_KMH), *map(float, SPEED_GRID), *map(float, CORNER_RADII.values()),
            20.0, 45.0, 75.0, 100.0, 300.0]


def _rounded_match(token: str, x: float, refs: list[float]) -> bool:
    """Accept a value written to fewer decimals than the source, e.g. 0.638 quoted as "0.6" or "+0.64"."""
    if "." not in token:
        return False
    d = len(token.split(".")[1])
    return any(abs(x - round(y, d)) < 10 ** -(d + 3) for y in refs)


def verify_numbers(answer: str, tool_results: list[Any], question: str = "") -> list[str]:
    refs: list[float] = _model_constants()
    _flatten_numbers(tool_results, refs)
    refs += _parse(question)
    unverified = []
    for token in _numbers(answer):
        try:
            x = float(token.replace(",", "").replace("−", "-"))
        except ValueError:
            continue
        if abs(x) <= 10 and float(x).is_integer():
            continue  # list numbering, counts, "2 axles" etc.
        refs_abs = [abs(v) for v in refs]
        if not (_matches(abs(x), refs_abs) or _rounded_match(token, abs(x), refs_abs)):
            unverified.append(token)
    return sorted(set(unverified))
