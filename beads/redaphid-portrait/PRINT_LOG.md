# redaphid-portrait — print iteration log

Append-only record of each print attempt and what was learned. New entries go at the **top**. Each entry: date, version, what was actually printed (parameters), the failure mode (if any), and the parameter changes for the next attempt.

This sits next to `README.md` (which captures *why this charm exists*); the log captures *what we learned by feeding plastic into the printer*. Future charm builds can grep across PRINT_LOGs to predict their own failure modes.

---

## v6 — 2026-04-29 — printable AND assembles with proper snap-fit

Geometry: as v5c except `PEG_CLEARANCE=0.1 → 0.05` mm. Halves radial gap is now 0.05 mm per side (0.1 mm diametric) instead of 0.1 mm per side (0.2 mm diametric). Only Top STL changes — sockets are in Top; Bottom (with pegs) is unchanged.

**Printed**: yes — and the halves snap together with friction grip for the first time across all six print iterations on this charm. Prior versions all assembled but the halves slid apart easily, which we'd been calling "printable" without checking the snap-fit.

**Lesson captured**: the recipe default `PEG_CLEARANCE=0.1` is conservative for a Centauri Carbon 2. On a well-calibrated FDM printer, that's enough slop for the peg to slide in with no friction at all. **0.05 mm radial / 0.1 mm diametric is a better default** for the CC2 specifically; the recipe-level value is worth revisiting once another charm prints on a different printer to confirm.

Open follow-ups (not blocking):
- v6b: chin peg diameter bumped 1.4 → 1.7 mm (the math limit at this position) for additional grip on the centerline. STLs and `top-v6b.3mf` queued in `print/` but not yet printed. Skip unless v6 grip is insufficient over time.

---

## v5c — 2026-04-29 — printable (after slicer Z-seam fix)

Geometry: TARGET_WIDTH=20, THICKNESS=5, **hole moved entirely into Top** via `HOLE_Z_OFFSET=+1.25` (string-hole tube z=[+0.50, +2.00] inside Top's [0, +2.5] half — solid material above and below, no half-circle groove on either inner face). Three pegs: side ear pegs at (±7, 0) at PEG_DIAMETER=**2.6** mm, single centered chin peg at (0, -7.3) at PEG_DIAMETER=**1.4** mm via per-peg diameter override.

**Printed**: yes — but only after switching Z-seam to Random.

**First attempt (Z-seam = Aligned, slicer default)**: right-ear region of the printed Top half accumulated dragged/oozed plastic into a visible stringy mass localized to that one socket. Left ear printed clean, despite essentially symmetric geometry. Photo evidence ruled out the wall-thickness theory (left wall 0.95 mm and right wall 0.65 mm both within recipe tolerance). Diagnosed as the slicer placing the Z-seam on the right edge each layer, compounding tiny seam artifacts over ~20 layers × 3+ color swaps per layer into one visible blob.

**Fix that worked**: Quality → Layers → Z-seam position = **Random**. The seam artifacts are now spread evenly around the perimeter; no single XY accumulates damage. Same multi-filament setup, same prime-tower position — only Z-seam changed.

**Lessons captured**:
- Small multi-color charms (≤25 mm) are highly sensitive to Z-seam placement. **Default Z-seam to Random for any multi-filament bead.** Documented in `print/FILAMENTS.md`.
- The original `verify_pegs` checked only the peg center via raycast; this missed cases where the peg's *perimeter* poked outside the silhouette. Replaced with an 8-point socket-radius perimeter check in v5b. Still an open improvement: add an explicit wall-thickness margin (≥0.5 mm clear between socket edge and silhouette boundary) so geometry that "barely fits" doesn't make it through.
- Centerline chin pegs at PEG_DIAMETER ≥ 1.84 are mathematically infeasible on this silhouette — NFC bottom (y=-6) and silhouette y_min near x=0 (-8.44) inequalities have no overlap once the peg radius is added. Thinner peg only on that one position, via per-peg diameter override, was the correct fix. Adding `(x, y, dia)` 3-tuples to PEG_CANDIDATES is now part of the build script.

---

## v5b — 2026-04-28 — printable but jaw pegs poked through silhouette

Geometry: as v5c except **4 pegs** in a quadrilateral at (±7, 0) + (±4.3, -7.1), all at uniform PEG_DIAMETER=**2.6** mm.

**Printed**: yes, but the two jaw pegs at (±4.3, -7.1) had their sockets visibly carved through the silhouette boundary on the printed Top half. The 8-point perimeter check passed at build time — but the wall thickness from socket edge to silhouette was paper-thin in places, and FDM layer-by-layer printing exposed the failure.

**Fix in v5c**: dropped the jaw pair, restored a single centered chin peg at (0, -7.3) at smaller PEG_DIAMETER=1.4 (centerline at 2.6 mm is mathematically infeasible — see v5c lesson). Added per-peg diameter override to PEG_CANDIDATES.

**Lesson captured**: an 8-point perimeter raycast against the silhouette is necessary but not sufficient. A peg can pass the check while still leaving a wall thinner than one perimeter width, which prints as voids or stringing around the socket. Future verifier upgrade: enforce a wall-thickness margin (e.g., socket edge to silhouette boundary ≥ 0.5 mm at all 8 perimeter points), not just "socket inside silhouette."

---

## v3 — 2026-04-28 — printable

Geometry: TARGET_WIDTH=20, THICKNESS=5, PEG_HEIGHT=1.5, HOLE_DIA=1.5, HOLE_Y=5.5, NFC_POS=(0,-1), pegs at (±8,0) + (0,-8). Wall above hole = 2.21 mm.

**Printed**: yes. Pegs grip; string hole holds the cord without snapping.

**Lesson captured**: sub-1 mm wall above the string hole snaps under cord load. The printability-check skill now warns; the recipe gotcha #13 documents the placement rule.

---

## v2 — 2026-04-27 — couldn't print

An attempt at a symmetric front/back portrait (raised decoration on both faces) created cantilever geometry the slicer rejected. Approach abandoned; the path-not-taken was removed from the build script in v3.

**Fix in v3**: drop the symmetric-back attempt. Bottom prints in canonical orientation (silhouette face DOWN to plate, pegs UP) — no cantilever, no supports needed.

---

## v1 — 2026-04-26 — printed but pegs too short to grip

Geometry: TARGET_WIDTH=25, THICKNESS=4 (halves 2.0 each), PEG_HEIGHT=1.0, HOLE_DIA=2.0, HOLE_Y=8.5.

**Failure**: Halves snapped together but the friction fit was loose — pegs at 1.0 mm height didn't grip enough to keep the bead closed. Also wall above the hole was only 1.07 mm and bent under cord tension.

**Fix in v2**: PEG_HEIGHT 1.0 → 1.5 mm (recipe default). THICKNESS 4 → 5 mm so the thinner halves still have ≥ 0.7 mm wall above the sockets. HOLE_Y 8.5 → 6.6 mm to thicken the wall above the hole.

**Lesson**: Don't drop PEG_HEIGHT below the recipe default 1.5 mm to "save space" — 1.0 mm pegs don't grip. If thickness is constrained, thicken the bead instead.

---

## How to read this log

- **Top entry = current state**. Cross-reference with `redaphid-portrait.blend` (latest geometry) and `print/redaphid-portrait.3mf` (latest slicer-ready bundle).
- Each entry's "lesson captured" is the one-liner that should propagate to the recipe / GUIDE / printability-check skill if it generalizes beyond this charm.
- Bug fixes that don't change print parameters (build script refactors, skill updates, etc.) belong in commit messages, not here.
