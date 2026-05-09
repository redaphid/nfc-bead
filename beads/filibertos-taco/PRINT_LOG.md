# Filiberto's Taco — Print Log

Append-only, newest at the top. Every physical print of this charm gets one entry: what was printed, what failed, what changed for next time.

---

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
