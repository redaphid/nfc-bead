# Robot — NFC charm

A humanoid robot silhouette (antenna head, boxy torso, outstretched arms,
articulated legs) wrapped around an NTAG215 sticker. The show face on Top
carries two raised eye dots in a contrasting filament — the only multi-color
region; everything else is body filament.

## Source

`robot.svg` — a black-filled raster-traced robot silhouette in a 1086 × 1280
viewBox. One continuous SVG path with even-odd winding produces the body
gaps (between body and arms, between the two legs, around the neck/antenna
mount). The path was hand-supplied.

## Why this charm exists

Exercises the generic NFC bead pipeline against a silhouette with substantial
interior detail — separate legs, outstretched arms with gaps to the body,
a narrow protruding antenna with a complex neck-attachment shape, and an
asymmetric peg layout dictated by the leg gap. It's the first charm in this
repo to add a *contrasting accent decoration* (eye dots) on top of the canonical
single-region pipeline.

## Key creative decisions

| Decision | Tradeoff |
|---|---|
| `dissolve_limited(5°)` after SVG import | The SVG path triangulates into ~13.5K dense overlapping triangles that survive `remove_doubles`. Without `dissolve_limited` the post-extrude mesh has ~7800 boundary edges and every downstream boolean inherits the rot. Dissolve collapses the triangulation into ~14 clean n-gons (outer silhouette + each interior gap as its own filled n-gon) → manifold extrude. |
| `bisect` split, not box INTERSECT | The robot silhouette dissolves into multiple disjoint n-gons. INTERSECT with a box trips on the disconnected pieces at the cut plane → hundreds of boundary edges. `bisect(use_fill=True)` is purpose-built for planar cuts and caps the cut cleanly → 0 non-manifold. |
| Pegs at `(0,+8), (-3,-10.5), (+3,-10.5)` | Symmetric triangulation: one peg in the head top center, two in the legs. The leg gap blocks a center bottom peg, so the two-in-the-legs choice is the only symmetric option. |
| `HOLE_Y = 4.0`, `HOLE_Z_OFFSET = THICKNESS/4` | Hole dropped from the natural top (the 2 mm-wide antenna tip — would crack under load per the recipe's string-hole rules) into the wide head band. Z-offset = +1.25 mm puts the hole entirely inside Top so the inner face is solid silhouette at y=HOLE_Y for first-layer adhesion (gotcha #23). |
| `SHOULDER_FILLERS` UNION'd into the silhouette | The NFC pocket perimeter at (0, -1.5) r=5.25 clipped the body-arm gaps on both sides — 3/32 perimeter points exposed the cavity through the armpits. Two 2.5×4.5 mm boxes welded across the gaps make the body solid at the pocket footprint. Box height set *exactly* to bead THICKNESS so the UNION caps coincide with the silhouette caps — no bisect-trim needed (the trim variant introduced ~850 non-manifold edges per half). After fill, the perimeter check is 16/16 inside silhouette. Cosmetic side-effect: the robot now has "armored" shoulders instead of skinny stick-figure armpits — arguably an improvement. |
| `NFC_POS = (0, -1.5)` | Torso center, just below the bead's geometric center. With shoulder fills in place, all 16 perimeter points sit inside solid silhouette. |
| No decoration cropper for eyes | The fresh-silhouette cropper from `build_charm.py.example` (gotcha #26) is needed when a decoration spans the silhouette outline. Tiny eye dots at (-2.5, +7) and (+2.5, +7) sit ~5 mm inside the head boundary — no risk. Skipping the crop also avoids a separate failure mode: the robot SVG's disjoint n-gons make EXACT INTERSECT unreliable on the cropper (silently killed one eye on the first pass). |
| `origin_set BOUNDS` on Decoration after join | `bpy.ops.object.join` keeps the active object's origin — for two eye cylinders, that's the first eye's center, not the cluster's geometric center. Without re-origining, the export skill's share-shift with Top placed the eye cluster off-center by +2.5 mm in X. Gotcha #10 (don't `origin_set BOUNDS` on meshes with meaningful origins) doesn't apply here because the "natural origin" of the eye pair is the cluster centroid, not the first eye. |

## What's transferable / what's specific

**Transferable:**
- `dissolve_limited(5°)` after SVG import + dedup — should be the default for any silhouette whose SVG path is more complex than a single convex outline. Worth backporting into `build_charm.py.example`.
- `bisect` over box INTERSECT for the split — cleaner output for any multi-piece silhouette.
- The Decoration `origin_set BOUNDS` after join — applies to any decoration built from multiple primitives.

**Specific to robot:**
- `PEGS` triangulation: dictated by the leg gap. Other silhouettes won't have this constraint.
- `EYES` positions: tuned to the robot's face proportions.
- `INTERIOR_FILL_SIDES` was removed entirely — only needed it pre-dissolve, but `dissolve_limited` makes interior gaps fill themselves as n-gons.

## Files

| Path | What |
|---|---|
| `robot.svg` | Source silhouette (raster-traced; 1086 × 1280 viewBox) |
| `build_robot.py` | Blender build pipeline (CONFIG-driven) |
| `print/robot_charm.blend` | Saved Blender scene after last successful build |
| `print/Bottom.stl` | Bottom half, print-flipped (silhouette face on plate, pegs up) |
| `print/Top.stl` | Top half, inner face on plate, show face up |
| `print/Decoration.stl` | Two eye dots, sits on Top's show face |
| `print/robot.3mf` | Slicer-ready 3MF: Bottom on the left, Top+Decoration merged on the right |
| `PRINT_LOG.md` | Per-print iteration log (failures, parameter changes, lessons) |

## Print settings

- **Material**: PLA or PETG, body filament + contrasting accent for eyes
- **Layer height**: 0.12–0.16 mm
- **Infill**: 100% (parts are small)
- **No supports**, no brim, no raft
- **Bottom**: silhouette face on the build plate, pegs pointing up
- **Top**: inner face (peg sockets) on the build plate, show face up, eyes on top
- **Filament assignment** (Centauri Carbon 2 multi-filament):
  - Filament 1: body color (gunmetal / charcoal recommended)
  - Filament 2: eyes (bright orange / red / cyan — anything that pops on the body)

## Dimensions

| Part | X × Y × Z (mm) |
|---|---|
| Bottom | 25.00 × 29.40 × 4.00 |
| Top | 25.00 × 29.40 × 2.50 |
| Decoration (eyes) | 6.80 × 1.80 × 0.40 |

Assembled bead: 25.00 mm wide × 29.40 mm tall × ~5.4 mm thick (Top + Decoration relief).
