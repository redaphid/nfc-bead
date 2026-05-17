# black-rainbow — print iteration log

Append-only record of each print attempt and what was learned. Newest entry at
the top. Each entry: date, version, what was actually printed (parameters),
failure mode (if any), parameter changes for the next attempt, lesson
captured.

See `README.md` for *why this charm exists* and the design decisions; this log
captures *what we learn by feeding plastic into the printer*.

---

## v1 — 2026-05-16 — NOT YET PHYSICALLY PRINTED

Geometry built and exported but no plastic yet. Recording the initial design as
the baseline.

**Build config** (`build_black_rainbow.py`):

- `TARGET_WIDTH = 25.0`, `THICKNESS = 5.0`
- `HOLE_Y = 5.5`, `HOLE_Z_OFFSET = -1.25` (string-hole tube entirely inside
  Bottom half, z ≈ [+0.25, +2.25] of Bottom's [-2.5, 0] range — solid wall
  above and below the tube)
- `NFC_POS = (0.0, -2.7)`, `NFC_DIAMETER = 10.5`, `NFC_DEPTH = 0.8`
- `PEGS = [(-7, -5), (+7, -5)]` (2 pegs, both in the under-arch corners)
- `PEG_DIAMETER = 2.6`, `PEG_HEIGHT = 1.5`, `PEG_CLEARANCE = 0.05`
- 4 decorations FLUSH inlay: rainbow_outer (red) → rainbow_mid (yellow) →
  rainbow_inner (blue) → wings (black, topmost). `DECO_RELIEF = 0.4 mm`.

**Build raycast verification** (all passed):

- NFC perimeter inside silhouette: 16/16
- Peg 0 (-7, -5): solid=True, NFC_clearance=+0.82 mm, hole_dy=10.5
- Peg 1 (+7, -5): solid=True, NFC_clearance=+0.82 mm, hole_dy=10.5

**Mesh manifold counts**:

- Bottom: 0 non-manifold edges
- Top: 0 after peg-hole cuts, **8 non-manifold edges after FLUSH pocket
  carving** — stray EXACT solver fragments from the near-silhouette-wide
  wings polygon. Typical for charms with a decoration footprint that
  approaches the silhouette extent. Slicer should auto-repair.
- All 4 decorations: 0 non-manifold edges each

**Expected failure modes to watch on first print**:

1. **String-hole wall above** is only 1.6 mm (below the recipe's 2.5 mm rule).
   If the bead snaps off the bracelet under load, the next iteration needs
   either a thicker bead or a different hanging strategy (offset hole into a
   wing tip, redesign as a non-hanging decorative charm).
2. **Torsional play around the 2-peg axis** (y = -5). With pegs in line, the
   halves can rotate around that line. Friction-fit at PEG_CLEARANCE=0.05
   (carried over from redaphid-portrait v6's well-tuned snap) should help,
   but watch for the halves spinning freely after assembly.
3. **8 non-manifold edges on Top** may cause local slicer artifacts. If the
   Top print has visible defects clustered in one region, the EXACT solver's
   leftovers are the suspect — try re-running with `repair_manifold(top)`
   called twice, or pre-shrink the wings polygon by 0.05 mm to avoid the
   silhouette-edge co-planar boolean.
4. **Black wings printing OVER white show-face base in a thin overlap zone**
   — the wings cut the rainbow at their footprint via FLUSH overlap-resolution,
   but the wings still cover small portions of the rainbow at the arch's
   bottom corners. If the slicer can't cleanly distinguish a 0.4 mm-deep
   filament-region at the wing/rainbow boundary, expect color-bleed there.

**Stl + 3MF outputs**:

- `print/Bottom.stl` (120 KB)
- `print/Top.stl` (364 KB)
- `print/DecorationRainbowOuter.stl` (77 KB)
- `print/DecorationRainbowMid.stl` (80 KB)
- `print/DecorationRainbowInner.stl` (79 KB)
- `print/DecorationWings.stl` (81 KB)
- `print/black-rainbow.3mf` (220 KB) — ComponentsObject pattern; in slicer,
  expand `Top_with_decorations` to assign one filament per part

**Next attempt**: print Bottom + Top assembly on the Centauri Carbon 2 with
PLA. 0.16 mm layer height, 100% infill (parts are tiny), no supports. Assign
filaments: Bottom = K, Top = W (show-face base), DecorationRainbowOuter = R,
DecorationRainbowMid = Y, DecorationRainbowInner = B, DecorationWings = K.

---
