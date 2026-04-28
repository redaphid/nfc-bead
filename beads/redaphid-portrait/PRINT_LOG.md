# redaphid-portrait — print iteration log

Append-only record of each print attempt and what was learned. New entries go at the **top**. Each entry: date, version, what was actually printed (parameters), the failure mode (if any), and the parameter changes for the next attempt.

This sits next to `README.md` (which captures *why this charm exists*); the log captures *what we learned by feeding plastic into the printer*. Future charm builds can grep across PRINT_LOGs to predict their own failure modes.

---

## v3 — 2026-04-28 — printable

Geometry: TARGET_WIDTH=20, THICKNESS=5, PEG_HEIGHT=1.5, HOLE_DIA=1.5, HOLE_Y=5.5, NFC_POS=(0,-1), pegs at (±8,0) + (0,-8). SYMMETRIC_BACK=False. Wall above hole = 2.21 mm.

**Printed**: yes. Pegs grip; string hole holds the cord without snapping.

**Lessons captured**:
- `SYMMETRIC_BACK` forces a Bottom flip → pegs cantilever → slicer rejects unless supports are added. Default OFF; opt-in for symmetric-back charms understanding the cost.
- Sub-1 mm wall above the string hole snaps under cord load. The printability-check skill now warns; the recipe gotcha #13 documents the placement rule.

---

## v2 — 2026-04-27 — couldn't print

Geometry: TARGET_WIDTH=22, THICKNESS=5, PEG_HEIGHT=1.5, HOLE_DIA=2.0, HOLE_Y=6.6. **SYMMETRIC_BACK=True** (Bottom + HairBack + DecorationBack flipped to print silhouette-up). Pegs cantilevered hanging from Bottom's inner face.

**Failure**: Slicer flagged the entire Bottom assembly as overhang. Pegs touching the build plate at z=0..1.5 with a 2.5 mm body hanging above on three thin pillars. Rejected without supports configured.

**Fix in v3**: Disable SYMMETRIC_BACK by default. Bottom returns to canonical orientation (silhouette face DOWN to plate, pegs UP) — no cantilever.

**Lesson**: Raised back-decoration is fundamentally incompatible with peg-on-Bottom + no-supports printing. Three workable strategies if you want symmetric back: (a) print with supports, (b) engrave the back instead of raise it, (c) move to a 3-piece bead with separate peg cylinders. Documented as gotcha #14 in `prompts/nfc-bead/prompt.md`.

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
