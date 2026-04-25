# Rezz bead debugging log — spiral

The spiral on the top face went through several rounds. Captured here so the next charm doesn't repeat them.

## What worked

- **Procedural construction in Python** via `mesh.from_pydata`. No SVG involvement for the spiral itself — only the bead's outer circle silhouette uses SVG. The spiral is generated from `r = b·θ` sampling 720 points, then offset perpendicular to the tangent by `±arm_width/2` to form a flat ribbon, then extruded vertically by `spiral_height`.
- **Distinct debug colors per structural element** (cyan bottom / blue top body / magenta spiral, plus wireframe overlays for pegs / NFC pocket / string hole) made it possible to talk about the geometry concretely instead of "the thing on the thing."

## Pitfalls hit (in order)

### 1. Wrong assumption that the spiral came from an SVG
The user initially believed the spiral was a traced SVG. It was always Python-generated. Lesson: when the user asks me to "make X procedural", first verify whether X is *already* procedural — they may be reacting to a visual artifact, not the construction method.

### 2. Curve-bevel-then-clip silently produced an empty mesh
First implementation: build the spiral as a Bezier curve, set `bevel_depth = arm_width/2` to give it a tube cross-section, convert to mesh, then INTERSECT with a thin slab to flatten it.

The boolean INTERSECT collapsed the entire mesh to zero vertices. The EXACT solver doesn't reliably handle a tube tangent to a thin slab — the surfaces are too coplanar. **No error was reported** — the script just printed `Spiral non-manifold: 0, dims: (0.0, 0.0, 0.0)` and moved on.

**Fix:** build the flat ribbon directly. Sample the centerline, compute inner/outer offsets perpendicular to the tangent, build quads with `mesh.from_pydata`, extrude in Z. No booleans needed for the basic shape.

**Generic recipe insight:** for any raised decoration on a charm face, prefer direct mesh construction over curve-bevel-then-clip.

### 3. Spurious end-cap quad spanned the entire spiral
After fixing the empty-mesh issue, a `face = [0, N, 2*N-1, N-1]` was appended "to close the ribbon's ends." That quad's four vertices are: inner-start (near center), outer-start (near center), outer-end (at outer radius), inner-end (at outer radius). It drew **a single huge quad spanning from the spiral's center to its outer terminus** — visible as a clean straight line cutting across the disc.

The ribbon's open ends don't need an explicit cap face. Once you extrude in Z, Blender automatically creates side-wall faces along the boundary edges, which closes the start and end of the ribbon as small rectangular walls.

**Fix:** delete the end-cap face. Trust the extrusion to seal the boundary.

### 4. `origin_set BOUNDS` shifted the asymmetric spiral
Once the spiral was being trimmed (to clear the string hole), the mesh became asymmetric. Calling `bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')` then reassigning `spiral.location = (top_x, 0, ...)` placed the spiral's *bbox center* over the top body's center — but the spiral's *true center* (where the spiral starts winding) was offset from the bbox center, so the spiral visually sat off-center.

**Fix:** skip origin_set entirely. The spiral mesh is built around `(0, 0, 0)` in mesh-local coords (which is the meaningful spiral center). Setting `spiral.location = (top_x, 0, 0)` then preserves true centering regardless of any trimming.

**Generic recipe insight:** when an object's mesh-local origin is geometrically meaningful (the spiral start, the silhouette centroid, etc.), do not blindly run `origin_set BOUNDS` before placing it. Bounds-recentering is for objects whose origin doesn't matter; for those whose origin *does* matter, it silently moves the part.

### 5. Z-fighting at the spiral/top-body boundary
With the spiral built at `top_outer_z` (= the top body's outer face z), the spiral's bottom face and the top body's top face shared the same Z plane. From certain camera angles this caused flickering "clipped into the front of the bead" visual artifacts.

**Fix:** lift the spiral by 0.01 mm (`spiral.location = (top_x, 0, 0.01)`). Slicer tolerances absorb this — the spiral still prints fused to the top body — but the visual gap eliminates Z-fighting.

### 6. The string-hole "clearance notch" looked worse than no notch
Iteration 1: trim everything above `Y = +7` so the spiral didn't canopy the string hole's top opening — left a flat horizontal bite-out across the disc that read as obvious damage.

Iteration 2: replace half-plane trim with a 2.5 mm circular cutout centered on `(0, +9)` — cleaner shape, but still obviously a circular hole punched into the spiral.

Iteration 3 (current): no trim. The spiral canopies the hole's top opening from above. Functionally fine — the string threads horizontally through the bead body, never touches the top face. Visually clean — the spiral is uninterrupted.

**Generic recipe insight:** a "clearance" cut against a surface that the relevant feature never actually touches is decorative noise. Question whether the feature being cleared physically interacts with the part being cut, and skip the cut if it doesn't.

## Workflow lessons

- **Position camera + screenshot before arguing about a visual.** Several rounds were spent text-debating whether the spiral was centered when a top-down screenshot would have settled it in one shot. Now codified in memory `feedback_visual_debugging.md`.
- **Per-stage `.blend` snapshots cost nothing and earn a lot.** The `stages/NN_*.blend` set let me re-open intermediate state when something looked wrong, instead of regenerating from scratch each time.
- **Distinct debug colors per element** (one solid color per structural part, wireframe overlays for hidden features) make verbal communication unambiguous.
