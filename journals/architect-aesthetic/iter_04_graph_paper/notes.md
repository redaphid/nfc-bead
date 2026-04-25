# Iter 04 — graph-paper plate underneath the bead

## Hypothesis under test
A horizontal plane beneath the bead with a procedural blue-line grid pattern (1-unit minor + 5-unit major) will transform the composition from "floating geometry on parchment" to "architectural elements arranged on drafting paper." The grid should read as graph paper, not as visual noise.

## What I changed (no script edits)
- Created `MA_GraphPaper`: a 100×100 mm `Plane` at world Z = -0.1
- Procedural shader chain (~14 nodes):
  - `TexCoord.Object` → `SeparateXYZ` for X and Y in world units
  - For each axis: `WRAP(0,1)` (frac) → `MIN(frac, 1-frac)` (distance to nearest integer line) → `LESS_THAN(0.06)` (line mask)
  - Repeat with X/5 and Y/5 for major lines
  - `MAX(line_x, line_y)` → minor mask, then major mask
  - `Mix(PAPER, MINOR_COL, minor_mask)` → `Mix(prev, MAJOR_COL, major_mask)` → `Principled BSDF.BaseColor`
- Colors: `PAPER (0.93, 0.86, 0.72)`, minor `(0.55, 0.66, 0.78)`, major `(0.36, 0.48, 0.62)`
- Plate roughness 0.92, metallic 0 (matte, no reflections)

## What I see in `render.png` (cold reading)
- Both bead halves now sit clearly on a **parchment-cream plate with blue grid lines**
- Grid recedes into perspective toward the upper part of the frame — adds depth
- **Major lines (every 5 mm) read as darker blue; minor lines (every 1 mm) read as fainter blue** — hierarchy works
- **Cast shadows** under each puck anchor them to the paper (Sun at (8,-6,30) drops shadows lower-left)
- Composition reads as **drafting plate viewed at perspective** — exactly the master-architect goal
- Bronze spiral pops against parchment + blue grid; bodies' watercolor washes still read cleanly
- Plate edges are off-screen (100mm extent vs ~38mm visible window) — no horizon-edge artifact

## Verdict
- ✅ HYPOTHESIS VERIFIED: graph paper transforms the composition radically
- ✅ Procedural shader chain works first try in Cycles 5.0
- ✅ Two-tier grid (minor+major) creates natural visual hierarchy
- ✅ Anchoring shadows make the bodies feel grounded, not floating
- ⚠️ Slight grid aliasing at the horizon distance — high-frequency lines with non-AA threshold; not critical now
- ⚠️ Grid blue saturation might be a hair too vivid — could desaturate to look more like reproduced print blue

## Settings that worked
```python
plate_size = 100               # ±50 mm; covers wide-orbit camera frame
plate_z    = -0.1              # just below bead bottom
threshold  = 0.06              # line half-width in grid units (0.06 mm at 1mm grid)
PAPER      = (0.93, 0.86, 0.72, 1.0)
MINOR_COL  = (0.55, 0.66, 0.78, 1.0)   # graph-blue
MAJOR_COL  = (0.36, 0.48, 0.62, 1.0)   # darker graph-blue
divisor_minor = 1.0   # every 1 unit
divisor_major = 5.0   # every 5 units
```

## Stopping point
After 4 iterations the **bare aesthetic is verified**. Watercolor washes + parchment + ink edges + graph paper plate is producing the master-architect look the user described. Time to test camera vocabulary on this scene.

## Next iteration
**Iter 05**: camera vocabulary tests. Same scene, multiple shot framings:
1. Locked side profile (cam y=-50, z=2 — eye-level horizontal silhouette)
2. Top-down plate (cam z=+45 looking straight down)
3. Macro pull-in to spiral (cam y=-15, lens 80mm)
4. Macro pull-in to bottom-half NFC pocket (cam x=-18, y=-15, lens 80mm)
Render each, evaluate which framings best deliver the "Westworld locked-perspective" feel.
