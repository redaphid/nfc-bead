# Stage 01 — Initial Build

**Snapshot**: `01_initial_build.blend`
**Preview**: `01_initial_build.png`
**Source**: `../build_rezz.py` (executed end-to-end)

## What this stage represents

First end-to-end build of the Rezz bead: silhouette → extrude → string hole → split → NFC pocket → peg holes → pegs → spiral → exports. All mechanical features verified non-manifold-free.

## Geometry

| Object | Dimensions (mm) | Color | Notes |
|---|---|---|---|
| Bottom | 25.00 × 24.99 × 4.00 | RED | 2.5 mm half + 1.5 mm pegs (flipped 180° so pegs face down for printing) |
| Top body | 25.00 × 24.99 × 2.50 | RED | Peg holes on inner face, smooth outer face (the spiral target surface) |
| Spiral | 19.98 × 15.57 × 0.50 | BLACK | Flat ribbon, ~3.5 turns Archimedean, 1.4 mm arm width, trimmed above Y=+7 to clear string hole |

All three exported to `../print/` as STL.

## What worked

- The flat-ribbon spiral construction (manual perpendicular offset, then extrude) — the previous tube-then-slab approach silently produced an empty mesh because the EXACT solver collapsed the tangent geometry.
- All boolean operations on the half-bodies (string hole, NFC pocket, peg holes, pegs union) finished with 0 non-manifold edges.
- Peg-hole verification reports "BLOCKED at z=1.800" — that's the **expected** outcome: the holes are blind 1.8 mm recesses (1.5 mm peg + 0.3 mm bottoming margin), not through-holes. The raycast hits the closed bottom of the recess.

## Key insight

The classic "build curve, set bevel_depth, convert to mesh, intersect with slab" workflow looks elegant but is fragile: the EXACT boolean solver doesn't reliably handle a tube tangent to a thin slab. **For flat ribbons of arbitrary 2D paths, build the mesh directly with bmesh / `mesh.from_pydata` using inner/outer offsets perpendicular to the path tangent.** It's also faster and produces predictable, manifold geometry.

## Open issues / next refinements

- Spiral mesh's bbox-center origin reset (in the original positioning code) shifted the spiral ~1.5 mm "south" of true center. In this snapshot the spiral.location compensates, but the cleaner fix is to skip `origin_set` on the spiral entirely and let its mesh-local origin (= bead center) follow the top half's translation directly.
- Spiral inner end starts at θ where r ≥ W (~88° from center) to avoid the central singularity. The very innermost ~1.5 mm of the bead face has no spiral. Could close the inner end with a small disc cap if a tighter, hypno-eye look is wanted.
- Bottom half's peg overhang past the bead silhouette wasn't checked visually — verify in viewport.
