# NFC Bead / Charm — Technical Recipe

Use this as the technical scaffolding for any new two-half NFC charm. Drop it in at the start of a session, then describe the *creative* side — silhouette, theme, vibe, dimensions if non-default — and let the rest follow this recipe.

A working reference implementation lives at `build_charm.py` in this repo (built for the Wooli mammoth). Treat it as the canonical pipeline; copy and adapt the CONFIG block for new charms.

---

## What we're building

A **two-half snap-fit charm** for Kandi-style bracelets:

- A 2D silhouette (from SVG) extruded to a flat-ish 3D shape
- **Cut horizontally through the middle** into a top half and a bottom half
- **NFC sticker pocket** recessed into the inside face of the bottom half (so the sticker sits flush)
- **Friction-fit pegs** on the bottom half + matching holes on the top half (no glue — press fit)
- **String hole** through the head/top so it can hang off a bracelet or cord

Target NFC tag: NTAG215, 10mm diameter sticker (e.g. `https://www.amazon.com/dp/B0CH3XS569`). Pocket sizing assumes that.

---

## Default dimensions (override per-charm as needed)

| Feature | Value | Notes |
|---|---|---|
| Overall width | 25 mm | sized for Kandi bracelets; scale on import |
| Total thickness | 5 mm | split as 2.5 mm + 2.5 mm |
| String hole | 2 mm dia | runs along the X axis (lengthwise through the head/top) |
| NFC pocket | 10.5 mm dia × 0.8 mm deep | on the inside face of the bottom half only |
| Peg diameter | 2 mm | bumped up from 1.5 — stronger, less prone to snapping |
| Peg height | 1.5 mm | |
| Peg hole clearance | 0.1 mm per side | so hole radius = (peg_dia + 0.2) / 2 |
| Number of pegs | 3 | triangulated for stable alignment |

**Peg placement rules** (pick 3 spots that satisfy all of these):
- Inside the silhouette (raycast-verify before committing)
- ≥ ~1 mm clear of the NFC pocket edge
- ≥ ~1 mm clear of the string hole
- Triangulated, not collinear (gives torsional stability)
- ≥ ~1 mm from the silhouette edge (so the wall around the peg hole isn't paper-thin)

**String-hole placement rules** — the hole hangs the bead off a bracelet, so the
wall around it is a load-bearing feature. Don't pick the obvious spot if it
leaves thin material:

- Y must sit on a *wide* part of the silhouette — not on a narrow tip, ear-
  flap, hair-ridge, or other protrusion. Aim for the band where the
  silhouette is at full width.
- ≥ 2.5 mm of solid silhouette **above** the hole (between hole top and the
  silhouette's top edge). With a 2 mm-dia hole that's ≥ 1.5 mm of wall above.
  Less than that, the bead snaps off the bracelet under load.
- ≥ 1.5 mm of solid silhouette to either side at the hole's Y. The hole runs
  along X, so the silhouette's X-extent at the chosen Y must comfortably
  exceed the bead's diameter at the hole.
- For shapes whose top is a narrow protrusion (mammoth tusk, shaggy hair
  bumps, animal ears), drop the hole *down* into the wider head/forehead
  body even if it costs aesthetic intent. The dangling bead doesn't notice
  where the cord exits, but the wall above does.

---

## Pipeline (in order — order matters)

```
SVG silhouette
  → Import into Blender as 2D curve, join, set fill_mode='BOTH', resolution_u=64
  → Convert to mesh, scale to TARGET_WIDTH (mm)
  → Fill any interior gaps that would conflict with features (NFC pocket, pegs)
  → Extrude flat profile to THICKNESS  (use Extrude, NOT Solidify)
  → Boolean DIFFERENCE for the string hole (full bead, before split)
  → Box-cut INTERSECT to split into top + bottom halves at z_mid
  → Boolean DIFFERENCE for NFC pocket on the bottom half
  → Boolean DIFFERENCE for peg holes on the top half  (POST-SPLIT — see gotcha)
  → Boolean UNION to add pegs onto the bottom half     (NOT mesh join)
  → Flip bottom 180° around X for printing; export both STLs
```

---

## Critical gotchas (these will bite you if ignored)

### 1. Cut peg holes AFTER splitting, never before
If you cut peg holes into the full bead first and then box-cut to split, the split plane is **coplanar** with the peg-hole bottom. The EXACT solver collapses the holes — they get sealed shut and disappear silently. Always split first, then cut peg holes into the top half with cutters that extend **1 mm below the inner face** so the cutter is unambiguously through-going:

```python
cutter_bottom = inner_face_z - 1.0          # extend past the inner face
cutter_top    = inner_face_z + PEG_HEIGHT + 0.3
```

### 2. Always use the EXACT boolean solver
`solver = 'EXACT'`. The FAST solver routinely produces non-manifold output on shapes like this. Set this on every modifier.

### 3. Add pegs with boolean UNION, not mesh join
`bpy.ops.object.join()` leaves overlapping coplanar faces where the peg cylinder meets the inner face → 1000+ non-manifold edges. Use a UNION boolean modifier instead. It welds the peg to the half cleanly.

### 4. Use Extrude, not Solidify, when the silhouette has interior holes
Solidify produces broken topology around interior boundaries (e.g., the gap between mammoth legs, the inside of an "O"). Plain extrude is clean.

### 5. Tight `remove_doubles` threshold
Use `0.005` mm. `0.02+` will collapse small features and ruin the geometry. Run `remove_doubles` + `normals_make_consistent(inside=False)` after every boolean.

### 6. Filling interior gaps cleanly
If the silhouette has an interior hole that overlaps a feature (e.g., an NFC pocket lands on the trunk-gap hole), don't try to patch it in the SVG with an overlapping rectangle — that creates a separate boundary that won't merge. Instead, in mesh edit mode, select the boundary edges of the unwanted hole by coordinate range and call `bpy.ops.mesh.fill()`. Other interior holes you want to keep (like the leg gap) are untouched.

### 7. Don't voxel-remesh
Voxel remesh seals small holes (string hole, peg holes) at any reasonable resolution. Skip it.

### 8. Verify everything with raycasts before exporting
After the build, raycast through where each hole should be:
```python
result = eval_obj.ray_cast(origin, direction)
# result[0] is True if it hit something — i.e. the hole is BLOCKED
```
Verify: string hole open through the head, each peg hole open through the top, each peg position lands on solid geometry inside the silhouette.

Note: peg holes are *blind* recesses (cutter depth = `PEG_HEIGHT + 0.3 mm`), not through-going. The raycast through a peg hole will *intentionally* report `BLOCKED at z=PEG_HEIGHT+0.3`. That's the right answer — they're sockets the pegs bottom into.

### 9. Build raised face decorations as flat ribbon meshes, not curve-bevel-then-clip
For any raised graphic on the show face (rezz spiral, embossed text, ridged pattern), the obvious workflow — build a curve, set `bevel_depth = arm_width / 2` for a tube cross-section, convert to mesh, then INTERSECT with a slab to flatten — **silently produces an empty mesh**. The EXACT solver doesn't reliably handle a tube tangent to a thin slab; it collapses the entire mesh. No error is raised; you'll see `dims: (0.0, 0.0, 0.0)` in the output and a missing object in the viewport.

Build the ribbon directly instead. Sample the centerline path, compute inner/outer offsets perpendicular to the tangent, build quads with `mesh.from_pydata`, extrude vertically. Reliable, manifold, fast.

Do **not** add an explicit "end-cap" face to close the open ends of an open ribbon. A face like `[inner_start, outer_start, outer_end, inner_end]` will draw one gigantic quad spanning from start of the ribbon to end, visible as a straight line cutting across the disc. Extrusion auto-creates side-wall faces along the boundary edges, which closes the ends as small rectangular walls — no explicit cap needed.

### 10. Don't `origin_set BOUNDS` on objects whose mesh-local origin is meaningful
If an object's mesh was built around a meaningful origin point (the centerline of a spiral, the centroid of a silhouette), running `bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')` before placing it will move the *bbox center* to that origin — but for an asymmetric mesh (e.g. a spiral with a notch trimmed out, an outline with a tail), the bbox center isn't where the meaningful origin was. The object lands subtly off-center.

`origin_set BOUNDS` is for objects whose origin doesn't matter (`Bottom`, `Top` halves — they were extruded from a centered silhouette and bbox center matches geometric center). Skip it for decorations whose mesh-local `(0,0,0)` is geometrically significant; place them via `obj.location` directly.

### 11. Lift overlapping decorations by ε to avoid Z-fighting
When a separately-printed decoration (raised spiral, embossed text) sits on the host face, both at the same Z, viewport rendering will Z-fight at the boundary. Lift the decoration by 0.01 mm (`spiral.location.z = host_top_z + 0.01`). Slicer tolerances absorb this — they print fused — and the viewport is artifact-free.

### 12. Don't cut decorative "clearance" against features the decoration never touches
A common reflex is to trim the show-face decoration around features like the string hole "for clearance." If the feature physically interacts with the decoration, yes — trim. But the string hole runs *horizontally through the bead body*; the decoration sits on the *outer face*; they never touch. Cutting a notch in the decoration to "clear" the hole's top opening just leaves a visible bite in the decoration that adds nothing functional. Question whether the cut is necessary before adding it.

### 13. Drill the string hole at the mesh's *actual* z-midpoint, never at `THICKNESS/2`
If your build pipeline centers the FullBead on the origin (so verts span `−THICKNESS/2..+THICKNESS/2`), hard-coding `location=(0, HOLE_Y, THICKNESS/2)` puts the hole at the **top face** of the bead — entirely inside the Top half after the box-cut split. Bottom ends up with no opening, and you can't thread a cord through. Compute `z_mid` from the live mesh:

```python
zs = [v.co.z for v in mesh.data.vertices]
z_mid = (min(zs) + max(zs)) / 2.0
location = (0, HOLE_Y, z_mid)
```

This is silent — the build runs to completion, the STL passes manifold checks, and you only notice when you try to thread a cord (or run a side-view raycast). The reference `build_charm.py.example` doesn't trip this because it leaves the silhouette at z=0..THICKNESS rather than centering it; centered-mesh builds need the live z_mid.

### 14. Pegs go on Bottom — multi-color decoration on Top precludes flipping it
The recipe's "pegs on Bottom + sockets on Top" assignment isn't arbitrary. With pegs on Top hanging *down* off the inner face, the slicer flags the Top assembly as a cantilever (the body is suspended on three thin pillars). The natural fix — flipping Top so pegs point *up* — doesn't work either, because the show-face decoration (Hair slab, raised eyes) would then point INTO the build plate. Pegs *must* live on Bottom for any charm with raised decoration on Top.

### 15. Importing a subset SVG into the silhouette's frame requires a viewBox-shift
When the build script imports a second SVG that's a *subset* of the silhouette (e.g. a `hair.svg` that traces only the haircut region of the same viewBox), Blender's `bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')` re-centers the imported curve on its own bbox, NOT on the viewBox. Two SVGs with the same viewBox end up overlapping their bbox centers at world (0,0) — which mis-aligns them, since the silhouette's bbox-center IS the viewBox-center but the subset's isn't.

Fix: parse the subset's path bounds and the viewBox dimensions out of the SVG, and shift the imported subset by `(subset_cx − viewBox_cx, viewBox_cy − subset_cy)` mm (Y-flip because Blender Y is up while SVG Y is down). Set `obj.location = (shift_x, shift_y, 0)` — don't *add* to the location after `origin_set`, since `origin_set` already moved the location to the world position of the bbox-center.

### 16. The build pipeline's print orientation may not match the export skill's flip dict
`bead-stl-export/export.py` defaults to flipping Bottom 180° around X — that assumes the live scene has Bottom *upside-down* (silhouette face UP, pegs DOWN), so the flip lands silhouette-on-plate-pegs-up for printing. A *centered-mesh* build pipeline (FullBead centered on origin) produces Bottom *already* in print orientation (silhouette DOWN, pegs UP); applying the flip un-orients it.

Override per build by setting `bpy.context.scene["nfc_export_flip_override"]` to a JSON dict before running the export skill:

```python
import json
bpy.context.scene["nfc_export_flip_override"] = json.dumps({
    "Bottom": 0.0, "Top": 0.0, "Hair": 0.0, "Decoration": 0.0,
})
```

Other beads using the canonical flipped-build pattern keep the default behavior.

### 17. `bpy.ops.read_factory_settings()` unloads the BlenderMCP addon
"Wiping the scene to a clean slate" via `bpy.ops.wm.read_factory_settings(use_empty=True)` also unregisters the BlenderMCP addon — silently dropping the MCP socket. Subsequent `mcp__blender__*` calls fail with "Could not connect to Blender." Either delete objects/collections explicitly instead of factory-resetting, or relaunch Blender via `tools/launch.ps1` (which re-installs the addon and restarts the socket).

### 18. `exec(open(script).read())` doesn't trigger `if __name__ == "__main__"`
When you run a build script through Blender MCP via `exec(open(...).read())`, the script's `__name__` is the *calling* module, not `"__main__"` — so any `if __name__ == "__main__": main()` at the bottom never fires. Pass an explicit namespace:

```python
ns = {"__name__": "__main__"}
exec(script, ns)
```

This is the same trap as running scripts via Blender's `--python` flag in some contexts; either pass the namespace or call `main()` directly.

### 19. `gaussian_filter` blurs the channel axis too — use per-axis sigma for color images
`scipy.ndimage.gaussian_filter(rgb, sigma=4.0)` smears RGB channels into each other along with spatial pixels — saturation collapses to ≈ 0 because the R/G/B values converge. For color-aware extraction (face vs outline by hue), use:

```python
ndimage.gaussian_filter(rgb.astype(np.float32), sigma=(BLUR, BLUR, 0))
```

The `(s, s, 0)` tuple blurs height/width but leaves channels untouched.

### 20. Stale `FullBead` (or other helper) duplicates accumulate across rebuilds
Re-running a build script that creates intermediate objects (`FullBead`, peg cylinders, cutters) without first wiping them produces `FullBead.001`, `.002`, etc., that pile up in the scene. They're hidden, but they cost memory, slow boolean operations, and confuse later raycasts that walk `bpy.data.objects`. Either clear them explicitly at the top of the build:

```python
for n in list(bpy.data.objects.keys()):
    if n.startswith("FullBead"):
        bpy.data.objects.remove(bpy.data.objects[n], do_unlink=True)
```

or wipe the whole scene at the start of the build (but mind gotcha #17 — don't `read_factory_settings`).

### 21. `verify_pegs` must raycast the peg PERIMETER, not just the center
A center-only raycast confirms the silhouette is solid at the peg's XY but does NOT confirm that the peg's full cylindrical footprint is inside the silhouette boundary — a peg whose center is 0.3 mm inside silhouette y-min still has 0.7 mm of its 1 mm-radius edge poking past the boundary, producing visible bumps on the silhouette outline AND a thin material backing where the peg meets the bead body. The recipe shipped with this bug for several charm revisions before it was caught visually on a printed bead.

The fix (implemented in `build_charm.py.example`): raycast the center plus 8 evenly-spaced perimeter points (`k * π / 4` for k in 0..7) at the peg radius. Any miss → reject the peg position. The build now refuses to proceed if any configured peg has perimeter clipping; tighten `PEG_CANDIDATES` until every peg passes.

Two layered guards:
- **Build-time**: the perimeter raycast above; rejects bad peg positions before any boolean is applied.
- **Post-export**: `bead-printability-check` skill's "peg edges inside silhouette" check re-validates against the final STL.

A peg edge protruding by ≤ 0.5 mm is usually cosmetic; protrusion by ≥ 1 mm means the peg has thin material around it and may break under press-fit pressure.

**Corollary**: don't assume `silhouette_y_min == -THICKNESS/2 == -h/2`. A portrait silhouette can be height 16.92 mm but extend asymmetrically (e.g. y ∈ [-8.44, +8.46]) once it's centered by the pipeline. *Measure* the silhouette extent against the live mesh when picking peg positions, don't compute from the silhouette dimensions alone.

### 22. Re-export after every Blender edit before slicing
The exported STLs and 3MF live separate from the .blend. When you make a tweak in Blender (move a peg, retune hair, fix a non-manifold) and save the .blend, the print bundle is **stale until you re-run `bead-stl-export`**. Importing the old 3MF into the slicer "to check the change" silently loads the un-tweaked bead — you debug the wrong artifact for half an hour before realizing.

The forward-only protocol: every Blender edit ends with `exec(...)` of the export skill. Build → export → make-3mf is a chain; running only one link leaves a stale tail.

### 23. Splitting the string hole across the seam costs first-layer adhesion
The recipe-default places the string hole on the Z midplane, so each half hosts an open half-circular groove on its inner face. When the half is printed inner-face-down (Top is printed face-up → inner face on bed; Bottom flipped silhouette-down → inner face is the *top* of the print), that 1.5–2 mm gap in the silhouette outline at `y=HOLE_Y` is right where the bed meets the part. Bed-contact area drops; mid-print the part can lift slightly at the hair band; multi-color swap purges that land near that region peel and the head drags them.

The fix is structural: set `HOLE_Z_OFFSET` to ~`THICKNESS/4` so the entire hole sits inside one half, with the inner face fully solid silhouette at `y=HOLE_Y`. The hole becomes a small interior tube that the slicer bridges twice (floor + ceiling, ~1.5 mm spans, easy bridges). Cost: tube wall thickness above + below shrinks to `(half_thickness - hole_dia) / 2` ≈ 0.5 mm at THICKNESS=5 — printable on a tuned printer, marginal on others. If the print still fails, bump `THICKNESS` rather than reverting to the split-plane hole.

### 24. NFC pocket needs the same perimeter raycast as pegs
Mirrors gotcha #21 but for the NFC pocket. Center-only validation passes if the pocket center is inside the silhouette, but a 5.25 mm-radius pocket centered 4 mm from the silhouette boundary clips past it on one side — leaving a paper-thin or open wall along that arc. The first time this happened the user had to look at the slicer's 3D view to spot it; the build script declared success.

The fix (implemented in `build_charm.py.example`): 16-point raycast (`k * π / 8` for k in 0..15) at the NFC radius. Any miss → reject the position; print the per-vertex misses so the user can pick a better `NFC_POS` or shrink `NFC_DIAMETER`. More samples than the peg check (16 vs 8) because the NFC radius is much larger and a single missed sample represents a wider arc.

### 25. Multi-region SVG round-trip silently breaks alignment between regions
For a multi-color charm with N region SVGs (filling, shell, outline, interior detail), Blender's `import_curve.svg` sizes each imported curve from the **path bbox**, not the SVG `viewBox`. Auto-fit-to-target-width then scales each region by its own path extent — so a region whose path covers 95% of the viewBox lands at scale ≈ 1.05× what a region covering 40% of the viewBox lands at. The two regions end up at different scales AND different positions even though their viewBoxes are identical.

You won't notice on the body silhouette (its path always covers the full viewBox). You will notice when an interior-detail SVG with fragments clustered in one corner gets auto-fit to 25 mm wide and stretches the fragments to fill that width — they end up at the wrong positions and the wrong size relative to silhouette + filling.

Two fixes, in order of cleanliness:
1. **Polygon manifest pipeline** (preferred for multi-region charms): emit each region's polygon vertices in shared mm coordinates to a single `regions.json`, then build Blender meshes via `bmesh.from_pydata`. No SVG round-trip. See `beads/filibertos-taco/extract_regions.py` for the reference.
2. **Bbox-anchor markers in SVG** (lighter touch): in your SVG writer, always emit two 1-pixel `<rect>` markers at the silhouette's bbox corners. Forces every SVG's path bbox to match the silhouette's, so per-SVG auto-fit gives consistent scale.

### 26. Decoration cropper must be a fresh silhouette extrusion, never a duplicate of Top
When you crop a decoration (e.g. multi-color slab) to the silhouette outer boundary via boolean INTERSECT, the natural reflex is to duplicate Top, raise its show-face vertices, and use that as the cropper. **This punches the peg-socket holes through the decoration**: Top has the peg sockets cut into its inner face, those holes become open through-tubes when the show face is raised, and the INTERSECT cuts matching holes in the decoration above each peg position. You see 3 visible bare-show-face circles on the decoration in the slicer.

Fix: build the cropper from a fresh re-import of `silhouette.svg` extruded tall — no peg sockets, no NFC pocket, no string hole. `build_charm.py.example` provides `_build_silhouette_cropper()` for exactly this. **Do this for every multi-color charm** — the bug is invisible until you slice.

### 27. Multi-color decoration layers need ≥0.16 mm Z-step or the slicer will Z-fight
When you stack multiple raised decoration objects on the show face — base color slab, accent color, outline ring — they need clear Z separation. A z-step less than the slicer's typical layer height (0.16 mm) leaves the slicer ambiguous about which filament wins on a given layer; the imported model looks like one decoration is missing or showing through the wrong one.

Recipe-default `DECO_LAYER_STEP = 0.10 mm` is below typical layer height for tightness BUT only safe when no two decorations overlap in XY. If they DO overlap (filling under a separator curve, separator under outline ring), bump to `0.20 mm` so each is unambiguously its own slice. The decoration relief is 0.4 mm tall, so 0.2 mm × 4 layers = 0.8 mm total height stack — still well within the bead's 5 mm thickness.

Stack order in the build's `BLOCK_GROUPS` dict matters: things at higher layer_idx get higher Z and OCCLUDE things below them in the slicer's view. Put the visually-dominant decoration last so it's never occluded.

### 28. Multi-decoration 3MF: bundle as a `ComponentsObject` with one build item
The 3MF you ship to the slicer for a multi-color charm should have ONE `<components>` object with all Top-frame meshes (Top + every Decoration*) referenced as components, and ONE `<build>` `<item>` placing that assembly on the plate. Adding each mesh as its own top-level `<object>` with its own `<item>` (5+ build items at the same XY) confuses every slicer we've tried — Bambu Studio reports "model is too small" and offers to scale 25×, Elegoo Slicer flips one half upside-down. The ComponentsObject keeps everything anchored together.

Trade-off: the slicer renames component children with a numeric suffix (`top_with_decorations_1` etc.). That's cosmetic — the user can rename in the slicer. The "fix" of removing the ComponentsObject for cleaner names breaks the 3MF.

`tools/make_3mf.py` already follows this pattern for the canonical Bottom + Top + Decoration + Hair set. For charms with more decoration layers, write a per-charm `bundle_3mf.py` (mirror of `make_3mf.py`'s structure but with the charm's full decoration list) — see `beads/filibertos-taco/bundle_3mf.py` for the reference.

### 29. Snap-fit peg tuning: 2.6 mm dia, 0.05 mm radial clearance
The recipe-default **2.0 mm pegs at 0.1 mm clearance don't grip** — they're too narrow and too loose; the halves fall apart ("pegs don't fit together"). redaphid-portrait v5/v6 nailed the actual snap-fit on the Centauri Carbon 2 at **2.6 mm dia + 0.05 mm radial clearance** (so `hole_r = (PEG_DIAMETER + 0.1) / 2`). `build_charm.py.example` ships these defaults. At a small bead (≤20 mm) check `peg_radius` clearance to the NFC pocket edge — 2.6 mm pegs need the peg ring at radius ≥ ~7.5 mm around a centered 10.5 mm pocket.

### 30. Chamfer the peg TIPS or they catch on the socket rim
Even at the correct clearance, **blunt (flat-top) pegs catch on the socket opening and have to be forced together** — the user literally had to bite down on a printed bead to seat them. The grip is fine; the *entry* is the problem. Add a lead-in taper to the tip: keep a full-diameter shaft of `PEG_HEIGHT − PEG_CHAMFER`, then a cone frustum from full radius down to `radius − PEG_CHAMFER` over `PEG_CHAMFER` (~0.35 mm). The narrow tip self-centers into the socket, then the chamfer guides the full shaft in. Do NOT loosen the clearance to fix entry — that costs grip. `build_charm.py.example` Step 10 builds this (shaft cylinder + cone tip, both UNIONed). **Gotcha within the gotcha:** the cone tip must OVERLAP the shaft (~0.15 mm), not butt against it coplanar — a coplanar UNION doesn't merge and the tip exports as a SEPARATE body (non-watertight, prints as a loose cone). Shift the cone back into the shaft by the overlap.

### 31. Slimming a bead: thin ONE half asymmetrically, and move the string hole to the thick half
To make a bead thinner than the default 2×2.5 mm, don't thin both halves equally — the deep features set a per-half floor. The **socket-host half must stay thick** (peg sockets are `PEG_HEIGHT + 0.3` deep, and pegs *must* live on Bottom so sockets are in Top — gotcha #14), so thin the OTHER half. The thin half can only host the shallow NFC pocket (0.8 mm) + peg bases (pegs rise *above* the inner face, so they don't consume that half's thickness). Two consequences:
- The **string hole must live in the thick half** (single-half hole, gotcha #23) — a 1.5 mm half can't host even a 1.2 mm hole with printable walls.
- Split at an **asymmetric seam** (`z_split = z_min + BOTTOM_THICK`), not the geometric mid-plane.

Reference: `beads/gymnast-medallion` runs Bottom 1.5 mm + Top 2.0 mm + 0.5 mm relief = 4.0 mm total (down from 5.5), with the hole in the 2.0 mm Top.

### 32. Round "medallion" beads: procedural cylinder base + a figure silhouette as the raised relief
For a round bead with a figure (not a spiral) raised on the show face — like `beads/gymnast-medallion`:
- **Build the round base as a `primitive_cylinder` (≥128 verts), not an SVG.** A circle doesn't need a traced outline, and the cylinder is exact + clean. Centre it on z=0 and run the same hole→split→NFC→pegs pipeline.
- **The decoration is a plain extruded silhouette polygon** (figure → ngon → extrude `RELIEF_HEIGHT`), placed on the Top show face + ε. The rezz "flat ribbon" workaround (gotcha #9) is only for tube-section curves; a *filled* figure extrudes cleanly. Thin limbs are fine on a relief — they sit on the solid show face.
- **Mass-center the relief on its area centroid, NOT its bbox center.** A figure with a long thin limb (an extended leg, a pointed toe) has a bbox center far from its visual mass; centering on the bbox leaves it looking shoved to one side. Use the shoelace area-centroid, then **scale by max radial extent** (`FIT_RADIUS / max_dist_from_centroid`) so the whole figure — including the sprawling limb — sits inside the circle with no clipped edges. Centering on the bbox or scaling by "longest side" both clip or off-center it.

---

## Print orientation

- **Bottom half**: rotate 180° around X so the silhouette face is on the build plate and the **pegs point up**. Prints flat, no supports.
- **Top half**: inner face (with peg holes) goes on the build plate. Prints flat, no supports.
- **Decoration** (raised spiral / emboss / etc.): flat side on the build plate.
- Settings: PLA or PETG, 0.12–0.16 mm layer height, 100% infill (these are tiny), no supports.

**Build vs print orientation:** build scripts (`build_<charm>.py`) typically lay out the geometry in *build orientation* — the natural pose for boolean operations and inspection. The actual rotation to print orientation happens at export-time via `.claude/skills/bead-stl-export/export.py`, which has an `EXPORT_FLIP_X_DEG` dict that applies a deterministic per-part flip just before writing each STL. The live scene is unchanged; only the STL on disk is print-ready. This means the slicer should never need an auto-orient step.

---

## What the user supplies per charm

When you (the user) start a new charm session, you only need to talk about:

1. **The silhouette** — an SVG path, or a description detailed enough to commission/sketch one. Must be roughly bead-shaped: compact, with enough internal area to host a 10.5 mm NFC pocket plus 3 pegs without crowding.
2. **Where the string hole goes** — usually through the head / top of the silhouette, along the longer axis. Specify Y position in mm if the silhouette has a clear "head" region offset from center.
3. **Any non-default dimensions** — if you want a bigger bead, thicker halves, taller pegs, etc.
4. **Aesthetic / theme** — for naming, color choices in the .blend, any stylistic flourishes (engraved details, embossed text, color-swap regions, etc.). These are creative additions on top of the recipe.

Everything else (peg placement, NFC pocket position, gap-fill regions) is a derived decision — Claude should propose values based on the silhouette and ask for confirmation before building.

## Per-charm documentation

Every charm branch must ship a `beads/<name>/README.md` that captures the *intent* — the technical recipe is generic; the README is the only place future-Claude (or future-you) can recover *why this charm was built this way*. At minimum:

- **Source** — what input the silhouette came from (SVG path, image, sketch). If image-derived, the absolute path so the extraction can be re-run.
- **Why this charm exists** — what it's exercising or commemorating. Some charms exist to stress-test the pipeline with a new input format; some are gifts; some are commissioned. Knowing this informs how aggressively to refactor the build script later.
- **Key creative decisions and their tradeoffs** — every charm makes choices that aren't obvious from the build script's CONFIG block (multi-color regions vs flat, thinner profile, asymmetric layout, etc.). One row per decision, with the cost it imposed.
- **What's transferable / what's specific** — call out which parts of the build script generalize to future charms vs. which are tuned to this one's proportions. Keeps later charms from cargo-culting tuning constants.
- **Files** — pointer table to silhouette.svg, build script, .blend, stages, print/.

`beads/redaphid-portrait/README.md` is the reference example. Charm-branch builds should produce a README before the first commit lands, and update it whenever a creative decision changes (a region split is added, a dimension default is overridden, etc.).

### Print iteration log

Every charm that gets *physically printed* must also ship a `beads/<name>/PRINT_LOG.md` — append-only, newest at the top. Each entry: date, version, what was actually printed (parameters), failure mode (if any), parameter changes for the next attempt, lesson captured (one-liner that should propagate to the recipe / printability-check skill if it generalizes beyond this charm).

The README captures *intent*; the PRINT_LOG captures *what we learned by feeding plastic into the printer*. Across charms these logs become a corpus future-Claude can grep when starting a new build — "has anyone seen this failure mode before?"

`beads/redaphid-portrait/PRINT_LOG.md` is the reference example.

---

## Reference files in this repo

- `build_charm.py` — full working pipeline, parameterized at the top. Copy this and edit the CONFIG block for a new charm.
- `GUIDE.md` — long-form walkthrough with code snippets and a lessons-learned table.
- `wooli_silhouette.svg` — example input SVG (the Wooli mammoth).
- `models/` — example output STLs from a previous build.

---

## Quick-start for Claude in a new session

When the user opens a session referencing this prompt and a new silhouette:

1. Read `build_charm.py` to refresh the exact API calls and CONFIG schema.
2. Ask the user for: SVG path (or silhouette description), string-hole Y position, any dimension overrides.
3. Propose peg positions and NFC pocket center based on the silhouette's bounding box and interior — show the user before building.
4. Copy `build_charm.py` to a new file (e.g. `build_<charm>.py`), update the CONFIG block, run via Blender background mode.
5. Verify with the built-in raycast checks; iterate on peg positions if any verification fails.
6. Export both STLs; render a quick preview if useful.
