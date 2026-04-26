---
name: bead-stl-export
description: Export the printable bead halves to STL files in a known-good state — strips any architect aesthetic, debug overlays, or visualization-only objects first so the export contains ONLY the geometry the slicer should see; flips Bottom 180° around X for print orientation; bed-flattens each part to z=0; preserves Top+Decoration stacking for slicer merge. Pairs with `tools/verify_stls.py` (alignment + manifold checks) and `tools/make_3mf.py` (slicer-ready 3MF with parts pre-merged). Use when the user wants to "export the STL", "send it to the slicer", "make it printable", "check it's printable", "make a 3MF", or similar. Requires the Blender MCP to be connected.
---

# Bead STL Export

A defensive STL exporter + companion verifier and 3MF packager. The exported geometry is the **pure printable form** — no aesthetic / debug overlays — and is print-oriented and bed-flat by default.

## Project-wide naming convention

Canonical Blender object names: **`Bottom`**, **`Top`**, **`Decoration`**. Build scripts MUST produce these names. There are no legacy-suffix fallbacks (per `feedback_canonical_names_only` in user memory).

## Three scripts

| Script | Runs in | What it does |
|---|---|---|
| `export.py` | Blender (via MCP or `tools/blender_send.py`) | Strips overlays, flips, bed-flattens, exports 3 STLs to `tmp/stl_export_<ts>/` AND mirrors to `tmp/latest/` |
| `tools/verify_stls.py` | host (uv) | Loads `tmp/latest/*.stl` via trimesh, runs 14+ structural checks, exits non-zero on any failure |
| `tools/make_3mf.py` | host (uv) | Bundles the 3 STLs into a slicer-ready `tmp/latest/rezz.3mf` with `Top` + `Decoration` pre-merged as a ComponentsObject |

Typical workflow:

```sh
# 1. (in Blender) export the STLs
exec(open(r"<repo>/.claude/skills/bead-stl-export/export.py").read())

# 2. (host shell) verify alignment + manifoldness
uv run python -m tools.verify_stls

# 3. (host shell) generate the slicer-ready 3MF
uv run python -m tools.make_3mf

# 4. drag tmp/latest/rezz.3mf into Elegoo Slicer
```

## What `export.py` does

1. **Drop into OBJECT mode** — `bpy.ops.object.*` polls fail in EDIT/sculpt/paint mode.
2. **Strip overlays** — removes `MA_*` (architect rig: GP, lights, materials) and `DBG_*` (debug widgets) so they can never sneak into an export.
3. **Locate canonical targets** — `Bottom`, `Top`, `Decoration` only.
4. **Per-part transform pipeline** (applied as a temporary edit, restored after the write):
   - **`EXPORT_FLIP_X_DEG`** — 180° around X for `Bottom` (silhouette face onto build plate, pegs point up); 0° for the others.
   - **Bed-flatten** — shift each part so its bbox min-Z = 0 and its X/Y center = 0. Each STL imports flush on the build plate.
   - **`EXPORT_SHARE_SHIFT_WITH`** — `Decoration` inherits `Top`'s X/Y/Z shift instead of computing its own. This preserves the spiral's position above Top's outer face when the user merges them in the slicer ("one object with parts").
5. **Export each part** with `bpy.ops.wm.stl_export(export_selected_objects=True)` to a timestamped archive (`tmp/stl_export_<ts>/`).
6. **Mirror to `tmp/latest/`** — wipes prior contents, copies the same files plus a `manifest.txt`. Always-current path so you don't have to find the most recent archive.

## What `verify_stls.py` does

Per part:
- **geometry** — vertex/face counts > 0
- **watertight** — manifold per `trimesh.is_watertight` (every edge has exactly 2 face uses)
- **bed-flat** — `Bottom` and `Top` start at z=0 (Decoration exempt — it lives in Top's frame)
- **diameter** — within tolerance of `EXPECTED_DIA_MM` (default 25 mm ±1.5)
- **thickness** — Bottom 4 mm ±0.5, Top 2.5 mm ±0.3, Decoration 0.5 mm ±0.2

Cross-part:
- **decoration on top** — gap between Top max-Z and Decoration min-Z is in `[-0.02, +0.10]` mm
- **decoration relief** — Decoration's z-extent above Top is in `[0.3, 1.0]` mm
- **decoration X/Y aligned** — Top center and Decoration center are within 1 mm X / 2 mm Y of each other

Returns 0 on full pass, 1 on any failure → suitable as a pre-print guard.

## What `make_3mf.py` does

Loads the 3 STLs via trimesh, builds a 3MF Consortium-format file via `lib3mf`:

- **`Bottom`** — added as a `MeshObject`, placed on the plate at `(-15, 0, 0)`
- **`Top` + `Decoration`** — added as separate `MeshObject`s, then bundled as a single `ComponentsObject` named `Top_with_Decoration`. Placed on the plate at `(+15, 0, 0)`.

The slicer reads this 3MF and the merge is **already done** — no manual "Combine into one object" step required. The user just assigns filaments per part (Filament 1 = body, Filament 2 = decoration on the Centauri Carbon 2 multi-filament feeder).

Filament assignments aren't baked in (per-part filament IDs are a slicer-vendor extension to 3MF, not part of the Consortium spec). One manual step in the slicer remains: assign filaments after import.

## When NOT to use

- Mid-build, before the bead geometry is finalized — partial geometry produces non-printable STLs.
- If `Top` and `Decoration` have been boolean-UNIONed in the live scene, `Decoration` is gone or hidden and `export.py` writes only `Top.stl` (single-color unified). Use this when you want a one-color print of the top half.
- If you genuinely want a debug overlay in your STL (almost never) — use `bpy.ops.wm.stl_export` directly.
