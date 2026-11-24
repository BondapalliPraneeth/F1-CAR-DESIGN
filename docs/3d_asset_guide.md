# 3D asset guide

The car is the **ApexVision AV-1**, an original, generic open-wheel concept that is built procedurally in code. It is not
a model of, scan of, or derivative of any real team's car, and it carries no real team or sponsor livery.

| File | Purpose |
|---|---|
| `assets/tools/generate_car.py` | Procedural generator. Single source of truth for the geometry |
| `frontend/public/models/apexvision_av1.glb` | Generated binary glTF (≈ 950 KiB: 20 components, 119 parts, ≈ 62k triangles) |
| `frontend/public/models/apexvision_av1.parts.json` | Generated parts manifest (nodes, pivots, bounding boxes, triangle counts, materials) |

The backend advertises the model path as `asset_url` in `GET /api/v1/car`. The viewer loads it with drei's `useGLTF`.

## Regenerating

```bash
cd backend && .venv/Scripts/python.exe ../assets/tools/generate_car.py   # Windows
cd backend && .venv/bin/python ../assets/tools/generate_car.py           # macOS/Linux
```

This needs `numpy`, `scipy` and `trimesh`, which are all in `backend/requirements-dev.txt`. The script overwrites both output files.

Geometry is built from lofted superellipse sections (body, sidepods, nose), cambered airfoil sections (wings), extruded
plates (endplates, fences), tubes (halo, suspension), and lathed wheels. Materials are glTF PBR metallic-roughness.

## Conventions

These conventions are a contract with the viewer. Any replacement model must follow them.

| Convention | Value |
|---|---|
| Units | metres |
| Axes | **+X forward** (towards the nose), **+Y up**, **+Z to the car's left** |
| Reference geometry | front axle x = +1.8, rear axle x = −1.8, wheel radius 0.36, track half-width 0.8 |
| Hierarchy | `apexvision_av1` → one empty group per component (`front_wing`, …) → mesh nodes |
| Mesh node name | `<component_id>__<part>`, with a double underscore. Example: `front_wing__endplate_l` |
| Sides | suffix `_l` (+Z) / `_r` (−Z) |
| Node origin | the part's **pivot**: hinge line for flaps, DRS and endplates; hub centre for wheels and discs; otherwise the bounding-box centre |

`componentOf(name)` in `frontend/src/lib/damageVisual.ts` takes the text before `__`. That is how a click on any mesh
selects its component. Meshes without `__` are not selectable.

The 20 `component_id`s must match `backend/app/domain/components.py`:

```
front_wing nose_cone monocoque halo cockpit sidepods radiators floor venturi_tunnels diffuser
rear_wing drs front_suspension rear_suspension front_tyres rear_tyres front_brakes rear_brakes
power_unit rear_crash_structure
```

## How the viewer uses the model

- **Selection and hover:** the viewer clones the materials of each mesh so it can highlight one component without
  affecting the others. Selection is shown with an emissive pulse.
- **Exploded view:** each component group is offset along a fixed direction (`EXPLODE_OFFSETS`), mirrored by side.
- **Isolate, hide and X-ray:** these change per-mesh visibility and opacity.
- **Damage visuals:** `computeDamageVisuals()` maps the current damage list to a per-node delta in position, rotation and scale,
  plus a hidden flag and a glow. It also computes a tint for each component (amber → red). The transforms are applied in each node's local space
  around its pivot, which is why the pivots matter. Examples:
  - **Front wing endplate:** `endplate_l` rotates outwards and is detached (hidden) at critical severity.
  - **Front suspension:** the corner rotates in camber about the hub and drops.
  - **Puncture:** the tyre is squashed vertically and the corner drops.
  - **Brakes and power unit overheating:** the disc or engine block glows with a heat colour and is not tinted.

> **The damage visuals are kinematic representations only.** Parts rotate, translate, scale, tint, glow and detach.
> There is **no** deformation, crash or fracture model behind them. The UI says this next to every damage control. The
> physical effect of damage on performance is computed separately by the backend models
> ([simulation_methodology.md](simulation_methodology.md)).

## Replacing or editing the model in Blender

1. Import the GLB: *File → Import → glTF 2.0*. Blender converts glTF's Y-up to Z-up on import and back again on export,
   so keep the default *+Y Up* export setting.
2. Keep **one empty per component**, named exactly with its `component_id`, and parent its meshes to it.
3. Name meshes `<component_id>__<part>`. Damage visuals look up specific part names. The current mappings are in
   `computeDamageVisuals()`. A part that the mapping expects but cannot find is silently skipped, so the viewer keeps working,
   but that visual will not appear.
4. Put each object's origin on its physical pivot (*Object → Set Origin*), for example the flap hinge or the wheel hub.
5. Apply scale (*Ctrl+A → Scale*) so that 1 unit = 1 m.
6. Export as **glTF Binary (.glb)** to `frontend/public/models/apexvision_av1.glb`, with *Apply Modifiers*, *Normals* and
   *+Y Up* enabled. Draco compression is optional. If you enable it, also configure a Draco decoder for `useGLTF`.
7. Keep the model original. Do not import or trace real team cars, scans or livery.
8. Check the result. Open the app and click every component. It should highlight, isolate and explode correctly. Run
   `npm run test:e2e`, whose first test checks that all 20 components are listed.

The parts manifest is informational, for documentation and tooling. The viewer reads pivots from the GLB node transforms, so
a hand-edited GLB does not need a regenerated manifest.
