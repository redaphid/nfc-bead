# Robot — print log

Append-only, newest at the top. One entry per physical print attempt.
Each entry: date, version, parameters, failure mode (if any), parameter
changes for the next attempt, lesson that should propagate to the recipe
or `bead-printability-check` if it generalizes.

---

## v1.1 — 2026-05-21 (not yet printed)

Shoulder-gap fill added so the NFC pocket isn't exposed through the
armpits. Two UNION'd boxes (2.5×4.5 mm) weld each arm to the body
across the body-arm gap. NFC perimeter check now passes 16/16 instead
of 15/16. Box height set exactly to bead THICKNESS so UNION caps
coincide with silhouette caps — bisect-trim variant introduced ~850
non-manifold edges per half. Visual: robot has "armored" shoulders
instead of stick-figure armpits.

## v1 — 2026-05-21 (not yet printed)

Initial design + STL/3MF generation. Geometry validated:

- Bottom + Top: 0 non-manifold edges
- Decoration (eyes): 0 non-manifold edges
- Watertight per trimesh
- Peg edges inside silhouette: 1 peg at (-3.0, -10.5) protrudes by 0.03 mm
  (well under the 0.5 mm cosmetic threshold from gotcha #21)
- NFC pocket: 15/16 perimeter points inside silhouette — the 1 missed
  point is at a body-arm gap edge. **Caught on review: this exposed
  the NFC cavity through the armpits — fixed in v1.1.**
- String hole: open through the head
- All 3 peg holes verified open (blind sockets, depth 1.8 mm)

Pending: first physical print on the Centauri Carbon 2.
