"""Synthetic test circuit used for lap-time estimates.

The 'ApexVision Test Circuit' is an invented layout (not a real circuit) that
mixes slow, medium and fast corners so that aero, mechanical and power changes
all show up in the lap time. Segments: ("S", length_m, drs_zone) for straights,
("C", length_m, radius_m) for constant-radius corners.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

SEGMENTS: list[tuple] = [
    ("S", 820, True),
    ("C", 90, 60),
    ("S", 300, False),
    ("C", 250, 200),
    ("S", 450, False),
    ("C", 55, 22),
    ("S", 640, True),
    ("C", 180, 120),
    ("S", 200, False),
    ("C", 400, 350),
    ("S", 350, False),
    ("C", 80, 45),
    ("S", 250, False),
    ("C", 140, 90),
    ("S", 520, False),
    ("C", 300, 250),
    ("S", 160, False),
]

DX = 4.0  # m


@dataclass(frozen=True)
class Track:
    s: np.ndarray  # distance at each node [m]
    radius: np.ndarray  # corner radius, inf on straights [m]
    drs: np.ndarray  # bool: DRS zone
    length: float
    corner_radii: tuple[float, ...]


@lru_cache(maxsize=1)
def build_track() -> Track:
    radii, drs = [], []
    for seg in SEGMENTS:
        n = int(round(seg[1] / DX))
        if seg[0] == "S":
            radii += [np.inf] * n
            drs += [bool(seg[2])] * n
        else:
            radii += [float(seg[2])] * n
            drs += [False] * n
    r = np.array(radii)
    return Track(
        s=np.arange(len(r)) * DX,
        radius=r,
        drs=np.array(drs),
        length=len(r) * DX,
        corner_radii=tuple(float(seg[2]) for seg in SEGMENTS if seg[0] == "C"),
    )
