# Filiberto's Taco — Print Log

Append-only, newest at the top. Every physical print of this charm gets one entry: what was printed, what failed, what changed for next time.

---

## v4c-neon — 2026-05-08 — not yet printed (cleanest taco read)

User feedback on v4b: "not 'obviously taco' enough, drop the bottom shell line".

Two design changes:
1. **Removed `DecorationShell`** — a ring around the lower half made the
   silhouette look double-lined and busy.
2. **Replaced `DecorationLettuce` (closed contour) with `DecorationFillingLine`**
   — a single curve tracing only the BOTTOM EDGE of the lettuce blob (where
   filling meets shell). Now the bead silhouette + this dividing line reads
   as a textbook taco: cradle-shaped bun split by a horizontal filling line.

Two manifold issues got fixed along the way:
- **Mask-blur smoothing made things worse** (50+ non-manifold edges per
  decoration). Cause: smoothing each contour independently diverged the
  outer/inner ring offsets so they cross. Reverted to no smoothing on
  ring-stroke contours.
- **EXACT solver leaves coplanar fragments** at ring boundaries after
  INTERSECT with the silhouette cropper. Added `repair_manifold()` to the
  build pipeline: dissolve degenerate edges, delete loose, fill_holes(8),
  remove doubles, reconcile normals. Now every decoration STL is
  watertight (verified via trimesh: `is_watertight=True`, euler=0 for
  ring shapes, euler=2 for solid).

Filaments now reduced to 2: black body + light blue strokes.

`build_filibertos_taco.py` `repair_manifold()` will help every future
ring-stroke decoration in this charm — and is general enough to backport
to the recipe if other charms hit the same EXACT-solver issue.

## v4b-neon — 2026-05-08 — not yet printed (continuous-stroke neon)

Refined v4-neon. Original strokes used boundary-between-mask which produced
fragmented blobs (one ring per leaf). Replaced with merged-blob outlines:
the lettuce mask is morphologically closed (dilate 14 / erode 14 / fill /
keep largest component) before ring-stroking, so all the leaf shapes merge
into ONE blob whose outer contour traces the lettuce as a single line.
Same for the shell.

Result: 3 continuous neon-line strokes instead of ~30 fragments.

| Stroke | Suggested filament | Notes |
|---|---|---|
| `DecorationSilhouette` | light blue | Outer perimeter of the bead |
| `DecorationLettuce` | light blue | Single curve tracing the filling/lettuce blob |
| `DecorationShell` | red or navy | Single curve tracing the shell (taco hard-shell underside) |

Ring stroke width = 0.42 mm (`STROKE_WIDTH_PX = 6` × `0.0708 mm/px`).
Tune via `STROKE_WIDTH_PX` in `extract_strokes.py` (4 for thin, 8 for bold).

## v4-neon — 2026-05-08 — not yet printed (synthwave / stencil look)

A second stylistic variant for the same bead body. Identical Bottom + Top
geometry, but the show-face decoration is **stroke-based** instead of
filled-region:

| Decoration | Source | Suggested filament |
|---|---|---|
| `DecorationSilhouette.stl` | outer perimeter ring of the bead | light blue |
| `DecorationLettuceLine.stl` | boundary stroke between filling and shell | light blue (same as silhouette) |
| `DecorationLettuceVeins.stl` | interior boundaries inside lettuce | red or navy |

Body filament: black (matches the negative-space areas around strokes — looks
like a neon sign on a dark plate).

Build pipeline supports both via `STYLE` (env var `FILIBERTOS_TACO_STYLE`
or scene custom prop `nfc_taco_style`):

```
bpy.context.scene["nfc_taco_style"] = "neon"
exec(open("build_filibertos_taco.py").read(), {"__name__":"__main__"})
```

The STYLE flag toggles which directory of SVGs (`region_*.svg` or
`stroke_*.svg`) gets discovered into `SVG_REGIONS`. Adding more strokes:
just drop another `stroke_*.svg` next to the others and re-run.

Stroke generation lives in `extract_strokes.py` — uses morphological
dilate-XOR on the color masks to derive ring/boundary geometry, then
Fourier-smooths the contours.

Output: `print/neon/filibertos-taco-neon.3mf` (205 KB) plus per-stroke
STLs for filament assignment in the slicer.

## v3 — 2026-05-08 — not yet printed (4-color decoration)

Re-extracted color regions from the JPG using k-means (k=7) instead of hand-coded thresholds. Now produces 4 distinct decoration layers (was 3 in v1):

| Region | px | Notes |
|---|---|---|
| `outline` (#921209) | 45,594 | Red — biggest region; covers most of the silhouette |
| `shell_dark` (#d68a00) | 18,199 | Yellow — small visible band along the lower curve |
| `lettuce_light` (#5fa520) | 10,711 | Bright green highlights |
| `lettuce_dark` (#374806) | 9,583 | Deep green shadows inside the lettuce |
| `shell_light` | (empty) | Pale-yellow cluster collapsed into shell_dark; no separate region |

Build script now auto-discovers `region_*.svg` files via `_discover_regions()` and emits one `Decoration<Camel>` object per region. Adding more regions is now zero-code: drop a new `region_<name>.svg` and re-run.

Visual result captured in `stages/02_v3_4color.blend`. Bare-show-face patches at the peg-socket XYs persist (peg sockets sit in regions that no color cluster covered) — cosmetic only, no geometric change. Same 4 printability checks PASS as v1.

**Open**: shell yellow ended up only as a thin sliver along the bottom edge — most of the lower-curve area got claimed by red outline. Next iteration should re-tune cluster mapping so shell wins where it competes with outline in the lower band.

## v1 — 2026-05-08 — not yet printed

First export. Build completed cleanly:

- 0 non-manifold edges on Bottom and Top.
- 3 pegs validated with center + 8-perimeter raycast (recipe gotcha #21) — all in solid silhouette, ≥1.5 mm NFC clearance.
- String hole tube entirely inside Top half via `HOLE_Z_OFFSET=1.25` (recipe gotcha #23) — bridged twice by slicer, no inner-face notch.
- All 3 decorations cropped to silhouette via INTERSECT with extruded Top duplicate.
- `nfc-printability-check` PASS on cantilever ratios + bed contact + peg edges.
- `nfc-make-3mf` produced `print/filibertos-taco.3mf` from concatenated `Decoration.stl`.

Caught one issue during export iteration: `bead-stl-export` default applied a 180° X-flip to Bottom, but my centered-mesh pipeline produces Bottom already in print orientation. Recipe gotcha #16 — overridden via `bpy.context.scene["nfc_export_flip_override"]` set inside `build_filibertos_taco.py`.

**Open questions for first print:**
- Slicer filament assignments: Bottom in brown PETG? Top in yellow + 3 decoration filaments? Need to set up in slicer before slicing.
- Does the 0.4 mm raised relief read clearly at 25 mm scale, or does it look stamped?
- First-layer adhesion on the Top half — 246 mm² bed contact, plenty of margin.

**Pre-print checklist:**
- Open `print/filibertos-taco.3mf` in Elegoo Slicer.
- Assign 3 filaments to the Decoration components (yellow shell, green lettuce, red outline).
- Layer height 0.16 mm, 100% infill (parts are tiny), no supports.
