"""Procedural generator for the ApexVision AV-1 3D model (original, generic design).

Produces frontend/public/models/apexvision_av1.glb plus a parts manifest.

Conventions (see docs/3d_asset_guide.md):
  * units: metres; +X forward (nose), +Y up, +Z to the car's left
  * front axle x = +1.8, rear axle x = -1.8, wheel radius 0.36, track half-width 0.8
  * every mesh node is named  <component_id>__<part>  and parented to an empty
    group node named  <component_id>; the node origin is the part's pivot
    (hinge for flaps / DRS / endplates, hub for wheels) so the viewer can apply
    kinematic damage transforms in local space.

Run:  python assets/tools/generate_car.py
Requires numpy, scipy and trimesh (backend/requirements-dev.txt).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import trimesh
from scipy.interpolate import PchipInterpolator, make_interp_spline
from trimesh.visual import TextureVisuals
from trimesh.visual.material import PBRMaterial

ROOT = Path(__file__).resolve().parents[2]
OUT_GLB = ROOT / "frontend" / "public" / "models" / "apexvision_av1.glb"
OUT_MANIFEST = ROOT / "frontend" / "public" / "models" / "apexvision_av1.parts.json"

FRONT_X, REAR_X, WHEEL_R, TRACK = 1.8, -1.8, 0.36, 0.8
SIDES = (("l", 1.0), ("r", -1.0))

# ----------------------------------------------------------------------------- materials
MATERIALS = {
    "navy": dict(baseColorFactor=[0.035, 0.07, 0.15, 1], metallicFactor=0.35, roughnessFactor=0.32),
    "cyan": dict(baseColorFactor=[0.02, 0.72, 0.68, 1], metallicFactor=0.2, roughnessFactor=0.3),
    "white": dict(baseColorFactor=[0.9, 0.91, 0.93, 1], metallicFactor=0.05, roughnessFactor=0.35),
    "carbon": dict(baseColorFactor=[0.035, 0.037, 0.042, 1], metallicFactor=0.25, roughnessFactor=0.45),
    "rubber": dict(baseColorFactor=[0.025, 0.025, 0.027, 1], metallicFactor=0.0, roughnessFactor=0.92),
    "rim": dict(baseColorFactor=[0.62, 0.64, 0.67, 1], metallicFactor=1.0, roughnessFactor=0.28),
    "disc": dict(baseColorFactor=[0.22, 0.2, 0.19, 1], metallicFactor=0.55, roughnessFactor=0.65),
    "caliper": dict(baseColorFactor=[0.45, 0.47, 0.5, 1], metallicFactor=0.8, roughnessFactor=0.35),
    "radiator": dict(baseColorFactor=[0.55, 0.6, 0.66, 1], metallicFactor=0.85, roughnessFactor=0.45),
    "engine": dict(baseColorFactor=[0.32, 0.33, 0.36, 1], metallicFactor=0.9, roughnessFactor=0.4),
    "exhaust": dict(baseColorFactor=[0.45, 0.36, 0.28, 1], metallicFactor=0.9, roughnessFactor=0.35),
    "titanium": dict(baseColorFactor=[0.42, 0.44, 0.47, 1], metallicFactor=1.0, roughnessFactor=0.3),
    "cockpit": dict(baseColorFactor=[0.012, 0.012, 0.014, 1], metallicFactor=0.0, roughnessFactor=0.8),
    "rainlight": dict(baseColorFactor=[0.6, 0.02, 0.02, 1], metallicFactor=0.0, roughnessFactor=0.4,
                      emissiveFactor=[0.9, 0.05, 0.03]),
}


def material(key: str) -> PBRMaterial:
    return PBRMaterial(name=f"av1_{key}", doubleSided=True, **MATERIALS[key])


# ----------------------------------------------------------------------------- geometry helpers
def _cap(ring: np.ndarray, away: np.ndarray) -> trimesh.Trimesh:
    n = len(ring)
    v = np.vstack([ring, ring.mean(0)])
    f = np.c_[np.arange(n), (np.arange(n) + 1) % n, np.full(n, n)]
    normal = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]).sum(0)
    if np.dot(normal, away) < 0:
        f = f[:, ::-1]
    return trimesh.Trimesh(v, f, process=False)


def loft(rings, *, wrap: bool = False, caps: bool = True) -> trimesh.Trimesh:
    """Skin consecutive closed rings (same point count) into a surface; optional end caps.
    wrap=True closes the loft back onto the first ring (tori: tyres, rims, closed tubes)."""
    rings = [np.asarray(r, dtype=float) for r in rings]
    s_count, n = len(rings), len(rings[0])
    verts = np.vstack(rings)
    i, j = np.meshgrid(np.arange(s_count if wrap else s_count - 1), np.arange(n), indexing="ij")
    i, j = i.ravel(), j.ravel()
    i2, j2 = (i + 1) % s_count, (j + 1) % n
    a, b, c, d = i * n + j, i * n + j2, i2 * n + j2, i2 * n + j
    faces = np.vstack([np.c_[a, b, c], np.c_[a, c, d]])
    # orient side faces outward (relative to the local ring centroid)
    f0 = faces[0]
    nrm = np.cross(verts[f0[1]] - verts[f0[0]], verts[f0[2]] - verts[f0[0]])
    if np.dot(nrm, verts[f0].mean(0) - rings[0].mean(0)) < 0:
        faces = faces[:, ::-1]
    parts = [trimesh.Trimesh(verts, faces, process=False)]
    if caps and not wrap:
        parts.append(_cap(rings[0], rings[0].mean(0) - rings[1].mean(0)))
        parts.append(_cap(rings[-1], rings[-1].mean(0) - rings[-2].mean(0)))
    return trimesh.util.concatenate(parts)


def superellipse(n_pts: int, half_a: float, half_b: float, exponent: float = 2.0) -> np.ndarray:
    t = np.linspace(0, 2 * np.pi, n_pts, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    return np.c_[half_a * np.sign(c) * np.abs(c) ** (2 / exponent), half_b * np.sign(s) * np.abs(s) ** (2 / exponent)]


def body_x(stations, *, n_pts: int = 40, samples: int = 36, exponent: float = 2.6) -> trimesh.Trimesh:
    """Smooth fuselage-like loft along X. stations: (x, y_centre, z_centre, half_width_z, half_height_y)."""
    st = np.array(sorted(stations, key=lambda r: -r[0]), dtype=float)
    xs = np.linspace(st[0, 0], st[-1, 0], samples)
    interp = [PchipInterpolator(-st[:, 0], st[:, k]) for k in range(1, 5)]
    rings = []
    for x in xs:
        yc, zc, hw, hh = (f(-x) for f in interp)
        p = superellipse(n_pts, hw, hh, exponent)
        rings.append(np.c_[np.full(n_pts, x), yc + p[:, 1], zc + p[:, 0]])
    return loft(rings)


def airfoil(n: int = 22, thickness: float = 0.12, camber: float = 0.06, p: float = 0.4) -> np.ndarray:
    """NACA-4-style section, unit chord, returned as a closed ring (u along chord, v normal).
    Camber is negative (inverted) so the section generates downforce."""
    beta = np.linspace(0, np.pi, n)
    u = (1 - np.cos(beta)) / 2
    yt = 5 * thickness * (0.2969 * np.sqrt(u) - 0.126 * u - 0.3516 * u**2 + 0.2843 * u**3 - 0.1036 * u**4)
    yc = np.where(u < p, camber / p**2 * (2 * p * u - u**2), camber / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * u - u**2))
    yc = -yc
    upper = np.c_[u, yc + yt][::-1]  # TE -> LE
    lower = np.c_[u, yc - yt][1:-1]  # LE -> TE (exclusive)
    return np.vstack([upper, lower])


def wing(sections, *, thickness=0.12, camber=0.06) -> trimesh.Trimesh:
    """sections: (z, x_le, y_le, chord, angle_deg). Angle raises the trailing edge (rearward = -X)."""
    prof = airfoil(thickness=thickness, camber=camber)
    rings = []
    for z, x_le, y_le, chord, ang in sections:
        a = np.radians(ang)
        d = np.array([-np.cos(a), np.sin(a)])
        nrm = np.array([np.sin(a), np.cos(a)])
        pts = np.array([x_le, y_le]) + chord * (prof[:, :1] * d + prof[:, 1:] * nrm)
        rings.append(np.c_[pts[:, 0], pts[:, 1], np.full(len(pts), z)])
    return loft(rings)


def plate_xy(poly, z_centre: float, thickness: float) -> trimesh.Trimesh:
    """Flat plate: polygon in the XY plane, extruded symmetrically along Z."""
    p = np.asarray(poly, float)
    return loft([np.c_[p, np.full(len(p), z_centre - thickness / 2)], np.c_[p, np.full(len(p), z_centre + thickness / 2)]])


def plate_xz(poly, y0: float, y1: float) -> trimesh.Trimesh:
    """Flat plate: polygon in the XZ plane, extruded along Y."""
    p = np.asarray(poly, float)
    return loft([np.c_[p[:, 0], np.full(len(p), y0), p[:, 1]], np.c_[p[:, 0], np.full(len(p), y1), p[:, 1]]])


def box(extents, centre, rot_z_deg: float = 0.0, rot_x_deg: float = 0.0) -> trimesh.Trimesh:
    t = trimesh.transformations.rotation_matrix(np.radians(rot_z_deg), [0, 0, 1])
    t = t @ trimesh.transformations.rotation_matrix(np.radians(rot_x_deg), [1, 0, 0])
    t[:3, 3] = centre
    m = trimesh.creation.box(extents=extents, transform=t)
    m.unmerge_vertices()  # flat shading for hard-edged parts
    return m


def rod(p0, p1, r: float = 0.012) -> trimesh.Trimesh:
    return trimesh.creation.cylinder(radius=r, segment=[p0, p1], sections=12)


def disc_z(radius: float, width: float, centre) -> trimesh.Trimesh:
    t = np.eye(4)
    t[:3, 3] = centre
    return trimesh.creation.cylinder(radius=radius, height=width, sections=48, transform=t)


def tube(points, r: float, *, samples: int = 48, n_pts: int = 14) -> trimesh.Trimesh:
    """Circular tube swept along a smooth spline through `points` (parallel-transport frames)."""
    pts = np.asarray(points, float)
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    spl = make_interp_spline(s, pts, k=min(3, len(pts) - 1))
    path = spl(np.linspace(0, s[-1], samples))
    tang = np.gradient(path, axis=0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True)
    ref = np.array([0, 1, 0]) if abs(tang[0, 1]) < 0.9 else np.array([1, 0, 0])
    nrm = np.cross(tang[0], ref)
    nrm /= np.linalg.norm(nrm)
    t = np.linspace(0, 2 * np.pi, n_pts, endpoint=False)
    rings = []
    for k in range(samples):
        if k:
            nrm = nrm - np.dot(nrm, tang[k]) * tang[k]
            nrm /= np.linalg.norm(nrm)
        bin_ = np.cross(tang[k], nrm)
        rings.append(path[k] + r * (np.outer(np.cos(t), nrm) + np.outer(np.sin(t), bin_)))
    return loft(rings)


def ring_loop(centre, rx: float, rz: float, r: float, n_seg: int = 64, n_pts: int = 12) -> trimesh.Trimesh:
    """Closed tube following a horizontal ellipse (cockpit surround)."""
    th = np.linspace(0, 2 * np.pi, n_seg, endpoint=False)
    c = np.asarray(centre, float)
    rings = []
    t = np.linspace(0, 2 * np.pi, n_pts, endpoint=False)
    for a in th:
        p = c + np.array([rx * np.cos(a), 0, rz * np.sin(a)])
        outward = np.array([np.cos(a) / rx, 0, np.sin(a) / rz])
        outward /= np.linalg.norm(outward)
        up = np.array([0, 1, 0])
        rings.append(p + r * (np.outer(np.cos(t), outward) + np.outer(np.sin(t), up)))
    return loft(rings, wrap=True)


def revolve_z(profile_rz: np.ndarray, centre, sections: int = 72) -> trimesh.Trimesh:
    """Revolve a closed (radius, axial) profile about the Z axis (wheel axis)."""
    th = np.linspace(0, 2 * np.pi, sections, endpoint=False)
    rings = [np.c_[profile_rz[:, 0] * np.cos(a), profile_rz[:, 0] * np.sin(a), profile_rz[:, 1]] for a in th]
    m = loft(rings, wrap=True)
    m.apply_translation(centre)
    return m


# ----------------------------------------------------------------------------- part registry
PARTS: list[dict] = []


def add(component: str, part: str, mesh: trimesh.Trimesh, mat: str, pivot=None) -> None:
    PARTS.append({"component": component, "part": part, "mesh": mesh, "mat": mat,
                  "pivot": None if pivot is None else np.asarray(pivot, float)})


# ----------------------------------------------------------------------------- the car
def build() -> None:
    # Front wing ---------------------------------------------------------------
    zs = [-0.93, -0.55, -0.26, -0.16, 0.16, 0.26, 0.55, 0.93]
    main = [(z, 2.80, 0.16 if abs(z) < 0.2 else 0.085, 0.34, 4.0) for z in zs]
    add("front_wing", "mainplane", wing(main, camber=0.05), "carbon")
    for side, s in SIDES:
        f1 = [(s * z, 2.56, 0.13 + 0.02 * (z - 0.22), 0.24, 16 + 4 * (z - 0.22)) for z in (0.22, 0.55, 0.92)]
        f2 = [(s * z, 2.39, 0.19 + 0.03 * (z - 0.22), 0.18, 28 + 6 * (z - 0.22)) for z in (0.22, 0.55, 0.92)]
        add("front_wing", f"flap_1_{side}", wing(f1, camber=0.06), "carbon", pivot=(2.56, 0.13, s * 0.22))
        add("front_wing", f"flap_2_{side}", wing(f2, camber=0.07), "cyan", pivot=(2.39, 0.19, s * 0.22))
        endplate = [(2.83, 0.04), (2.83, 0.17), (2.58, 0.33), (2.20, 0.34), (2.20, 0.04)]
        add("front_wing", f"endplate_{side}", plate_xy(endplate, s * 0.937, 0.012), "white", pivot=(2.5, 0.32, s * 0.937))
        add("front_wing", f"pylon_{side}", box((0.10, 0.07, 0.014), (2.50, 0.205, s * 0.075)), "carbon")

    # Nose cone ----------------------------------------------------------------
    nose = [(2.74, 0.215, 0, 0.05, 0.04), (2.45, 0.245, 0, 0.10, 0.07), (2.05, 0.30, 0, 0.165, 0.12), (1.40, 0.36, 0, 0.22, 0.17)]
    add("nose_cone", "shell", body_x(nose, exponent=2.4), "navy")
    add("nose_cone", "tip", body_x([(2.76, 0.215, 0, 0.035, 0.03), (2.62, 0.225, 0, 0.075, 0.055)], samples=8), "cyan")

    # Monocoque / cockpit / halo ------------------------------------------------
    mono = [(1.40, 0.36, 0, 0.22, 0.17), (1.00, 0.38, 0, 0.26, 0.22), (0.50, 0.38, 0, 0.33, 0.29),
            (0.00, 0.37, 0, 0.37, 0.30), (-0.55, 0.36, 0, 0.34, 0.28)]
    add("monocoque", "tub", body_x(mono, exponent=3.0), "navy")
    for side, s in SIDES:
        stripe = [(1.2, 0.45, s * 0.215, 0.012, 0.025), (0.5, 0.47, s * 0.31, 0.012, 0.03), (0.1, 0.47, s * 0.345, 0.012, 0.03)]
        add("monocoque", f"stripe_{side}", body_x(stripe, samples=16, exponent=2), "cyan")

    opening = trimesh.creation.icosphere(subdivisions=3)
    opening.apply_scale([0.42, 0.025, 0.215])
    opening.apply_translation([0.08, 0.665, 0])
    add("cockpit", "opening", opening, "cockpit")
    add("cockpit", "surround", ring_loop((0.08, 0.675, 0), 0.43, 0.225, 0.022), "carbon")
    add("cockpit", "headrest", box((0.14, 0.09, 0.46), (-0.36, 0.69, 0)), "carbon")
    add("cockpit", "steering_wheel", box((0.03, 0.13, 0.27), (0.34, 0.63, 0), rot_z_deg=-20), "carbon")
    helmet = trimesh.creation.icosphere(subdivisions=3, radius=0.125)
    helmet.apply_translation([-0.16, 0.76, 0])
    add("cockpit", "helmet", helmet, "white")

    add("halo", "pillar", tube([(0.72, 0.60, 0), (0.66, 0.74, 0), (0.56, 0.855, 0)], 0.028), "titanium")
    for side, s in SIDES:
        hoop = [(0.56, 0.86, 0), (0.43, 0.88, s * 0.17), (0.12, 0.885, s * 0.265), (-0.2, 0.87, s * 0.26),
                (-0.36, 0.76, s * 0.255), (-0.40, 0.64, s * 0.25)]
        add("halo", f"hoop_{side}", tube(hoop, 0.026), "titanium")

    # Sidepods + radiators ------------------------------------------------------
    for side, s in SIDES:
        pod = [(0.46, 0.33, s * 0.50, 0.17, 0.15), (0.2, 0.34, s * 0.56, 0.22, 0.18), (-0.4, 0.32, s * 0.55, 0.20, 0.16),
               (-0.9, 0.27, s * 0.45, 0.14, 0.12), (-1.28, 0.22, s * 0.30, 0.07, 0.07)]
        add("sidepods", f"body_{side}", body_x(pod, exponent=3.2), "navy")
        inlet_ring = superellipse(40, 0.145, 0.125, 3.2)
        rings = [np.c_[np.full(40, x), 0.33 + inlet_ring[:, 1], s * 0.50 + inlet_ring[:, 0]] for x in (0.465, 0.47)]
        add("sidepods", f"inlet_{side}", loft(rings), "cockpit")
        add("sidepods", f"stripe_{side}", body_x([(0.40, 0.49, s * 0.52, 0.12, 0.012), (-0.6, 0.45, s * 0.50, 0.12, 0.012)],
                                                 samples=12, exponent=4), "cyan")
        add("radiators", f"core_{side}", box((0.07, 0.25, 0.30), (0.08, 0.33, s * 0.55), rot_z_deg=-28), "radiator")
        add("radiators", f"header_{side}", rod((0.02, 0.47, s * 0.42), (0.02, 0.47, s * 0.68), 0.018), "radiator")

    # Floor / venturi tunnels / diffuser --------------------------------------
    half = [(1.15, 0.30), (0.85, 0.55), (0.55, 0.80), (-0.6, 0.85), (-1.25, 0.80), (-1.5, 0.58)]
    outline = half + [(x, -z) for x, z in reversed(half)]
    add("floor", "plate", plate_xz(outline, 0.022, 0.036), "carbon")
    for side, s in SIDES:
        add("floor", f"edge_{side}", box((1.1, 0.045, 0.012), (-0.05, 0.058, s * 0.845)), "cyan")
        arch_o = np.array([(0.2 * np.cos(a), np.sin(a)) for a in np.linspace(0, np.pi, 16)])
        arch_i = np.array([(0.185 * np.cos(a), 0.9 * np.sin(a)) for a in np.linspace(np.pi, 0, 16)])
        rings = []
        for x, h in ((0.95, 0.11), (0.4, 0.085), (-0.2, 0.07), (-0.9, 0.09), (-1.45, 0.14)):
            prof = np.vstack([arch_o, arch_i])
            rings.append(np.c_[np.full(len(prof), x), 0.036 + prof[:, 1] * h, s * 0.36 + prof[:, 0]])
        add("venturi_tunnels", f"tunnel_{side}", loft(rings), "carbon")
        for k, z in enumerate((0.16, 0.36, 0.56), start=1):
            fence = [(1.12, 0.0), (1.12, 0.10), (0.92, 0.13), (0.72, 0.13), (0.72, 0.02)]
            add("venturi_tunnels", f"fence_{side}{k}", plate_xy(fence, s * z, 0.01), "white" if k == 2 else "carbon")
    ramp = []
    for x, y in ((-1.45, 0.045), (-1.7, 0.09), (-1.95, 0.17), (-2.18, 0.28)):
        p = superellipse(24, 0.55, 0.008, 6)
        ramp.append(np.c_[np.full(24, x), y + p[:, 1], p[:, 0]])
    add("diffuser", "ramp", loft(ramp), "carbon")
    for side, s in SIDES:
        add("diffuser", f"side_{side}", plate_xy([(-1.45, 0.03), (-2.18, 0.03), (-2.18, 0.30), (-1.45, 0.06)], s * 0.555, 0.012), "carbon")
        for k, z in enumerate((0.18, 0.38), start=1):
            add("diffuser", f"strake_{side}{k}", plate_xy([(-1.55, 0.04), (-2.16, 0.03), (-2.16, 0.26)], s * z, 0.008), "cyan")

    # Power unit (with engine cover bodywork) ----------------------------------
    cover = [(-0.45, 0.45, 0, 0.34, 0.25), (-0.9, 0.45, 0, 0.28, 0.24), (-1.4, 0.40, 0, 0.17, 0.18), (-1.95, 0.33, 0, 0.07, 0.08)]
    add("power_unit", "cover", body_x(cover, exponent=2.4), "navy")
    add("power_unit", "airbox", body_x([(-0.30, 0.92, 0, 0.075, 0.075), (-0.55, 0.86, 0, 0.11, 0.12), (-0.95, 0.66, 0, 0.12, 0.1)],
                                       exponent=2.8), "navy")
    add("power_unit", "fin", plate_xy([(-0.6, 0.95), (-1.7, 0.5), (-1.9, 0.5), (-1.1, 0.75)], 0.0, 0.008), "cyan")
    add("power_unit", "block", box((0.62, 0.32, 0.40), (-0.86, 0.33, 0)), "engine")
    add("power_unit", "turbo", disc_z(0.085, 0.16, (-0.48, 0.42, 0)), "exhaust")
    add("power_unit", "gearbox", box((0.55, 0.2, 0.22), (-1.58, 0.29, 0)), "engine")
    add("power_unit", "exhaust", rod((-1.5, 0.44, 0), (-2.2, 0.43, 0), 0.045), "exhaust")

    # Rear crash structure ------------------------------------------------------
    add("rear_crash_structure", "structure", body_x([(-1.85, 0.30, 0, 0.11, 0.09), (-2.45, 0.30, 0, 0.065, 0.055)], samples=10,
                                                   exponent=3), "carbon")
    add("rear_crash_structure", "rain_light", box((0.02, 0.05, 0.09), (-2.465, 0.30, 0)), "rainlight")

    # Rear wing + DRS ------------------------------------------------------------
    span = (-0.50, -0.2, 0.2, 0.50)
    add("rear_wing", "mainplane", wing([(z, -2.25, 0.80, 0.34, 10) for z in span], camber=0.07), "carbon")
    add("rear_wing", "beam_wing", wing([(z, -2.30, 0.47, 0.20, 8) for z in (-0.45, 0.45)], camber=0.05), "carbon")
    flap_te = (-2.53 - 0.22 * np.cos(np.radians(38)), 0.885 + 0.22 * np.sin(np.radians(38)), 0)
    add("drs", "flap", wing([(z, -2.53, 0.885, 0.22, 38) for z in span], camber=0.08), "cyan", pivot=flap_te)
    add("drs", "actuator", box((0.04, 0.09, 0.05), (-2.56, 0.85, 0)), "titanium")
    for side, s in SIDES:
        ep = [(-2.12, 0.62), (-2.20, 1.00), (-2.76, 1.06), (-2.78, 0.45), (-2.30, 0.45)]
        add("rear_wing", f"endplate_{side}", plate_xy(ep, s * 0.512, 0.014), "navy", pivot=(-2.45, 0.45, s * 0.512))
        add("rear_wing", f"pylon_{side}", plate_xy([(-2.10, 0.38), (-2.30, 0.38), (-2.42, 0.83), (-2.28, 0.86)], s * 0.08, 0.02), "carbon")

    # Wheels, brakes, suspension ---------------------------------------------------
    for axle, x, width in (("front", FRONT_X, 0.30), ("rear", REAR_X, 0.40)):
        tyre_prof = superellipse(28, 0.0625, width / 2, 4.0)
        tyre_prof = np.c_[0.2975 + tyre_prof[:, 0], tyre_prof[:, 1]]
        rim_prof = superellipse(16, 0.01, width / 2 * 0.95, 4.0)
        rim_prof = np.c_[0.225 + rim_prof[:, 0], rim_prof[:, 1]]
        for side, s in SIDES:
            hub = np.array([x, WHEEL_R, s * TRACK])
            add(f"{axle}_tyres", f"tyre_{side}", revolve_z(tyre_prof, hub), "rubber", pivot=hub)
            add(f"{axle}_tyres", f"rim_{side}", revolve_z(rim_prof, hub, 48), "rim", pivot=hub)
            add(f"{axle}_tyres", f"face_{side}", disc_z(0.22, 0.012, hub + [0, 0, s * width / 2 * 0.82]), "carbon", pivot=hub)
            add(f"{axle}_tyres", f"nut_{side}", disc_z(0.05, 0.03, hub + [0, 0, s * width / 2 * 0.9]), "cyan", pivot=hub)
            disc_z_off = 0.04 if axle == "front" else 0.07
            disc_c = hub - [0, 0, s * disc_z_off]
            add(f"{axle}_brakes", f"disc_{side}", disc_z(0.165, 0.032, disc_c), "disc", pivot=disc_c)
            add(f"{axle}_brakes", f"caliper_{side}", box((0.13, 0.08, 0.06), disc_c + [-0.06, 0.15, -s * 0.035], rot_z_deg=-25), "caliper")
            susp = f"{axle}_suspension"
            zi = 0.19 if axle == "front" else 0.13
            zo = 0.69 if axle == "front" else 0.65
            fwd, aft = (0.25, -0.25) if axle == "front" else (0.25, -0.22)
            add(susp, f"upright_{side}", box((0.09, 0.27, 0.05), (x, WHEEL_R, s * (zo + 0.01))), "titanium")
            arms = [((x + fwd, 0.44, s * zi), (x, 0.48, s * zo)), ((x + aft, 0.45, s * (zi + 0.02)), (x, 0.48, s * zo)),
                    ((x + fwd + 0.05, 0.22, s * zi), (x, 0.22, s * zo)), ((x + aft - 0.05, 0.20, s * (zi + 0.02)), (x, 0.22, s * zo))]
            for k, (p0, p1) in enumerate(arms):
                name = ("upper" if k < 2 else "lower") + ("_front" if k % 2 == 0 else "_rear")
                add(susp, f"{name}_{side}", rod(p0, p1, 0.013), "carbon")
            if axle == "front":
                add(susp, f"pushrod_{side}", rod((x, 0.23, s * (zo - 0.02)), (x - 0.08, 0.5, s * zi), 0.011), "titanium")
                add(susp, f"track_rod_{side}", rod((x + 0.14, 0.31, s * zi), (x + 0.14, 0.31, s * (zo - 0.01)), 0.009), "carbon")
            else:
                add(susp, f"pullrod_{side}", rod((x - 0.02, 0.47, s * (zo - 0.02)), (x + 0.1, 0.22, s * zi), 0.011), "titanium")
                add(susp, f"driveshaft_{side}", rod((x, 0.33, s * 0.12), (x, WHEEL_R, s * (zo - 0.03)), 0.022), "engine")


# ----------------------------------------------------------------------------- export
def export() -> dict:
    scene = trimesh.Scene(base_frame="apexvision_av1")
    components = sorted({p["component"] for p in PARTS})
    for comp in components:
        scene.graph.update(frame_from=scene.graph.base_frame, frame_to=comp, matrix=np.eye(4))
    manifest: dict = {"model": "ApexVision AV-1 (original procedural design)", "units": "m",
                      "axes": {"forward": "+X", "up": "+Y", "left": "+Z"}, "components": {}}
    for p in PARTS:
        mesh: trimesh.Trimesh = p["mesh"]
        name = f"{p['component']}__{p['part']}"
        pivot = p["pivot"] if p["pivot"] is not None else mesh.bounds.mean(0)
        lo, hi = mesh.bounds
        mesh = mesh.copy()
        mesh.apply_translation(-pivot)
        mesh.visual = TextureVisuals(material=material(p["mat"]))
        t = np.eye(4)
        t[:3, 3] = pivot
        scene.add_geometry(mesh, node_name=name, geom_name=name, parent_node_name=p["component"], transform=t)
        manifest["components"].setdefault(p["component"], []).append(
            {"node": name, "pivot": np.round(pivot, 4).tolist(), "bbox_min": np.round(lo, 4).tolist(),
             "bbox_max": np.round(hi, 4).tolist(), "triangles": int(len(mesh.faces)), "material": p["mat"]})
    OUT_GLB.parent.mkdir(parents=True, exist_ok=True)
    OUT_GLB.write_bytes(scene.export(file_type="glb", include_normals=True))
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=1))
    return manifest


if __name__ == "__main__":
    build()
    man = export()
    tris = sum(x["triangles"] for parts in man["components"].values() for x in parts)
    print(f"Wrote {OUT_GLB} ({OUT_GLB.stat().st_size / 1024:.0f} KiB), "
          f"{len(man['components'])} components, {len(PARTS)} parts, {tris} triangles")
