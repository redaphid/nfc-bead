---
name: bead-printability-check
description: Pre-flight printability checks on the latest bead STLs in tmp/latest/. Detects the failure modes that bit us during physical printing — too-thin wall above the string hole, cantilevered bottoms (pegs touching the build plate while the body hangs above), peg edges poking past the silhouette boundary, and small bed-contact area. Run after `bead-stl-export` and before sending the 3MF to the slicer. Catches issues that `tools/verify_stls.py` (geometry-only) misses.
---

# Bead Printability Check

A second-pass validator that operates on the `tmp/latest/*.stl` set produced by `bead-stl-export`. Where `verify_stls.py` checks geometry hygiene (manifold, dimensions, alignment), this skill checks **whether the slicer will let you print without failure**.

## What it catches

Each check below corresponds to a specific failure mode we hit while iterating on `redaphid-portrait` — captured as a check so future charms surface the issue *before* hitting "print".

| Check | What it catches | Print-time symptom if missed |
|---|---|---|
| Wall above string hole | `HOLE_Y` placed too high — silhouette top minus hole top is too thin | Wall snaps off when you thread the cord; bead falls off the bracelet |
| Cantilever | Bottom prints with thin features (pegs) touching the build plate while the body hangs above | Slicer flags overhangs; pegs fail mid-print or the body sags |
| Peg edges inside silhouette | Peg cylinder's outer perimeter pokes past the silhouette boundary at its Y position | Visible bumps on the silhouette outline; weak peg with thin material backing |
| Bed contact area | Silhouette face area is too small for stable adhesion | Part lifts off the plate during print |

## Tunables

```python
MIN_WALL_ABOVE_HOLE   = 1.5    # mm — recipe recommends ≥ 2.5 mm; soft warning below 2.0 mm
MAX_CANTILEVER_RATIO  = 5.0    # area_at_z=2.5 / area_at_z=0.5 — above this is suspicious
PEG_EDGE_TOLERANCE    = 0.1    # mm — peg may protrude up to this past the silhouette before warning
MIN_BED_CONTACT_MM2   = 80     # mm² — Bottom's silhouette face contact area
```

## How to invoke

```sh
uv run nfc-printability-check                  # default: tmp/latest/
uv run nfc-printability-check --dir <stl-dir>  # alternate STL set
```

Returns 0 on full pass. Returns 1 on any check failing — suitable as a pre-print guard or CI step. Soft warnings (above floor but below recipe ideal) print but don't fail.

## Known limitations

- **Wall above string hole** uses a cross-section-diff heuristic that's noisy when the silhouette has slight Z-taper or peg-union edge artifacts. It currently warns when the diff is too large to be a real hole notch (sanity gate at 10% of silhouette area). For load-bearing checks, eyeball the wall in the build script's `HOLE_Y` config — `silhouette_top_y - HOLE_Y - HOLE_DIA/2` should be ≥ 2.5 mm.

## What this skill does NOT do

- It does not load the STLs into Blender. It works directly on the meshes via `trimesh`.
- It does not modify any files. Read-only.
- It does not check feature presence (string hole open, peg holes open) — that's the responsibility of the build script's raycast verifications and `verify_stls.py`.
- It does not validate slicer-specific concerns (filament assignments, layer height, bridges) — that's the slicer's job.

## When NOT to use

- Mid-build, before STLs are exported.
- For non-bead geometry. The checks assume the canonical Bottom/Top split with pegs and a horizontal string hole.
