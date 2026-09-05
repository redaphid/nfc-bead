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

### 33. A 3MF without a printer profile silently loses the brim

The `shield` bead failed to print and the geometry was never the problem. Its 3MF was three files — geometry only, **no `Metadata/project_settings.config`** — so Elegoo Slicer fell back to whatever preset happened to be loaded, which had no brim. The medallion that printed clean carried a 34 KB `project_settings` with `auto_brim`/5 mm.

**The brim wins.** `print/PRINT_GUIDE.md` says no brim; the first-layer adhesion diagnosis says use one. Resolve it in favour of the brim: a bead is a small flat slab with little plate contact, and it lifts without one.

Related: the package must also *look* like the slicer's own output. Elegoo Slicer warns "the 3mf file you are importing may be incompatible" when the `Application` metadata names a tool it doesn't recognise, and a package it treats as foreign may **also ignore the embedded `project_settings`** — dropping the brim and reproducing the exact failure the template exists to prevent. `tools/build_3mf.py` adopts the template's own producer string and plate thumbnails for this reason.

### 34. Filament slot 2 is RED — a single-colour bead must say slot 1

`build_3mf.py` historically hardcoded every part to extruder 2, a leftover from the multi-colour redaphid recipe where the body was red and the decoration black. **A single-colour bead built to print black printed RED, silently.** Nothing caught it, because every check in the pipeline is a geometry check and this is not a geometry problem.

Pass `--body-extruder 1` for single-colour beads, and verify by reading the artifact back rather than trusting the log:

```
python -c "import zipfile,re; z=zipfile.ZipFile(P); print(re.findall(r'key=.extruder. value=.(\d+).', z.read('Metadata/model_settings.config').decode()))"
```

All `1` for a black/glow bead. Any `2` is this bug.

### 35. A `.3mf` is a project file, not a print job

The printer only runs sliced `.gcode`. A generated 3MF uploads happily and then sits inert — it lists with `layer: 0`, `print_time: 0`, `color_map: []`, against populated values on every file that has really printed. **Check those fields before starting a print.**

There is no slicer installed on the build machine, so **3MF → gcode cannot be done headlessly**. An agent can rebuild geometry and bundles unattended but cannot get a *new* design onto the plate; that step needs a human in Elegoo Slicer once. Only an already-sliced gcode can be started remotely.

### 36. Back the part cooling off for the first layers, or the edges curl

The stock profile ships `close_fan_the_first_x_layers=1` and `full_fan_speed_layer=0`, so cooling hits 100% from layer 2 — observed live at 232–250 of 255. On a small flat PLA slab that is a textbook edge-curl driver: the upper layers contract hard while the first layer is still pinned to the plate. These beads have no real overhangs, so the aggressive early cooling buys nothing; `overhang_fan_speed` still covers the string-hole bridge. `build_3mf.py` now holds the fan off 3 layers and ramps to full by 5.

**Also worth knowing before diagnosing a "hung" print:** there are ~12 minutes of preamble before layer 1 (preheat, home, a long dense bed-level mesh, nozzle wipe, second heat, filament load/purge). During the load the job clock ticks up while `remaining_time_sec` stays pinned and the head parks, and `filament_detected` reads 0 for the whole preamble, only flipping to 1 when loading finishes. None of that is a hang.

### 37. A settings patch that matches nothing exits 0

`build_3mf.py`'s patcher matched only scalar `"key": "value"`. The per-filament settings — cooling, temperatures — are **arrays**. Adding one to `patches` matched nothing, exited cleanly, and printed `patched project_settings: <key>` while shipping the template's value unchanged: a fix that existed only in the log. Array-valued keys now go through `array_patches`, and a scalar patch that matches nothing is a **hard failure**.

This is the general shape of the worst bugs in this repo. When you change something, **read the artifact back and prove it changed.** Never trust a log line.

---

## Print orientation

- **Bottom half**: rotate 180° around X so the silhouette face is on the build plate and the **pegs point up**. Prints flat, no supports.
- **Top half**: inner face (with peg holes) goes on the build plate. Prints flat, no supports.
- **Decoration** (raised spiral / emboss / etc.): flat side on the build plate.
- Settings: PLA or PETG, 0.12–0.16 mm layer height, 100% infill (these are tiny), no supports.

### 38. Blender 5.0 headless hangs unless you pass `--gpu-backend opengl`

`blender.exe -b --python build_<charm>.py` **hangs forever** in a headless/agent shell. Blender 5.0 defaults to the **Vulkan** backend and Vulkan context creation blocks when there is no desktop session. Always run:

```
blender.exe -b --gpu-backend opengl --python beads/<name>/build_<name>.py
```

The hang is easy to misread as a slow boolean solve. It isn't: the process sits at **~0.03 s CPU and ~18 MB working set** with **zero output**, having never reached your script. Check CPU time, not the log — Python's stdout is block-buffered when redirected, so a *working* run also shows an empty log for a long while. `blender --version` returns instantly even while `-b` hangs (it exits before app init), so a working `--version` proves nothing; probe with `-b --gpu-backend opengl --python-expr "print('OK')"`.

### 39. UNIONing decoration primitives: never let them share a face or a tangent

Building a raised decoration by UNIONing per-stroke solids (bars, end-caps, rings) is the natural approach and it *silently* produces non-manifold garbage — 1020 non-manifold edges on a 7-stroke sigil. The EXACT solver is fine with solids that cross transversally and bad at the two degenerate contacts, both of which this construction creates by default:

- **Coplanar faces.** If every bar and cap spans the same `z_lo..z_hi`, all their top and bottom faces are coplanar. Fix: union them **oversized in Z with a per-primitive jitter**, then let the final crop INTERSECT cut the exact slab. The cut planes then pass through solid material instead of lying tangent to a face.
- **Tangency.** A round end-cap of radius exactly `w/2` is precisely tangent to its bar's side faces — the same hazard as gotcha #9. Oversize the cap by ~2 µm so the surfaces cross.
- **Exact duplicates.** A connected stroke path (a sigil) shares endpoints, so consecutive segments each emit an *identical* cap at the joint. UNIONing a solid with a copy of itself is degenerate; emit each cap once.

Also drop the weld threshold for decorations: the pipeline's usual `remove_doubles` at **0.005 tears 0.8 mm strokes apart**. Boolean output is already welded — use `1e-5`.

Reference implementation with all four handled: `beads/glow-set/deco.py`.

**Build vs print orientation:** build scripts (`build_<charm>.py`) typically lay out the geometry in *build orientation* — the natural pose for boolean operations and inspection. The actual rotation to print orientation happens at export-time via `.claude/skills/bead-stl-export/export.py`, which has an `EXPORT_FLIP_X_DEG` dict that applies a deterministic per-part flip just before writing each STL. The live scene is unchanged; only the STL on disk is print-ready. This means the slicer should never need an auto-orient step.

### 40. The socket funnel and the peg chamfer both eat the ENGAGEMENT — measure it

A peg is not gripped along its whole height. `SOCKET_LEADIN` opens the socket
mouth into a 45-degree funnel, and `PEG_CHAMFER` tapers the peg tip; between
them they can consume most of a short peg. Measured on a real 1.2 mm peg with
`SOCKET_LEADIN = 0.4` and `PEG_CHAMFER = 0.35`, only **0.50 mm** ever sat at the
design clearance:

| depth into socket | socket r | peg r | radial gap |
|---|---|---|---|
| 0.0 mm (mating face) | 1.749 | — | — |
| 0.2 mm | 1.549 | 1.299 | 0.250 |
| 0.4 mm | 1.349 | 1.299 | **0.050** |
| 0.8 mm | 1.349 | 1.299 | **0.050** |
| 1.0 mm | 1.349 | 1.103 | 0.246 |

The bead read as "close, but too loose", and the instinct is to reach for
`PEG_CLEAR`. That is the wrong knob first: the clearance was fine, there was
just almost no length at which it applied. **`PEG_HEIGHT` is the first knob;
`PEG_CLEAR` is the second.**

**Solved on hardware, in two single-variable steps:**

| step | `PEG_HEIGHT` | `PEG_CLEAR` | engagement | result |
|---|---|---|---|---|
| start | 1.2 | 0.05 | 0.50 mm | plainly too loose |
| depth | **1.8** | 0.05 | **1.00 mm** | *snaps*, still won't hold |
| clearance | **1.8** | **0.02** | 1.00 mm | **perfect** |

**Use `PEG_HEIGHT = 1.8` and `PEG_CLEAR = 0.02`** alongside `SOCKET_LEADIN = 0.4`
and `PEG_CHAMFER = 0.35`.

The ordering is the whole lesson. At 0.50 mm engagement **no clearance value
would have rescued it**, because there was scarcely any length over which
clearance applied — so tuning `PEG_CLEAR` first is motion without information.
Move one at a time: had both changed together, the working fit would not have
said which change earned it, and the constants would not transfer to the next
silhouette.

**Target roughly 1.0 mm of full-diameter engagement.** Derive `PEG_HEIGHT` from
that rather than copying 1.8 — it must cover the engagement you want *plus*
`SOCKET_LEADIN` plus the chamfer's effective loss. A build with no socket
lead-in loses only the chamfer and reaches 1.0 mm at a shorter peg.

Never estimate this from the constants — the interaction is easy to get wrong by
2x. Cross-section both exported STLs and compare bore radius to peg radius at
the same seated height. `beads/glow-set/measure_fit.py` does exactly that and
prints the table above; run it after any change to peg or socket geometry, and
treat the printed **ENGAGEMENT** figure as the number that matters.

Deepening the peg has a second benefit: it moves the gripping band up out of the
first two squished layers, where the bore is least round (see #42).

### 41. `task_status: 1` means the GCODE RAN — it is not evidence a part exists

The printer will happily execute an entire job with a dry extruder and report
success: `task_status: 1`, `CurrentTicks == TotalTicks`, empty
`exception_status`. **Every check the SDCP API exposes is a check on the JOB,
and they all stay green when nothing comes out of the nozzle.** This has
produced phantom "successful" prints more than once.

**The check that actually decides it:** `raw._cc2.filament_detected` must read
**1 once layers are advancing** (`PrintInfo.CurrentLayer >= 1`). If layers are
climbing and that flag is 0, the extruder is dry — call `stop_print` rather than
let it paint air for the rest of the job.

**Do NOT gate on the idle reading.** An earlier version of this gotcha said to
require 1 while idle, and that rule is wrong: run `21da0e21` sat at idle
`filament_detected: 0`, loaded normally once the nozzle hit 210, and printed a
real part. Blocking on the idle value produces false negatives, because 0 at
idle just means nothing is parked at the sensor between jobs.

**The real discriminator is the SLOT.** Sorted that way the record is blunt:

| slot | runs | outcome |
|---|---|---|
| `T0` (black, FIRST slot) | `5e5a8e33`, `21da0e21` | 2/2 produced parts |
| `T1` (red, SECOND slot) | `17e2cd47`, `86fbb0e6` | printed nothing |
| `T1` (red) | `c0aa169a` | parts, but only after a hand-load |

`T1`'s auto-load is what fails. Every `T1` failure also happened to show idle-0,
which is how the idle flag looked causal when it was only riding along — a
correlation drawn from three runs that a fourth broke. **Prefer `T0` for
single-colour jobs**, and if a job must draw from `T1`, have the user hand-feed
that spool first.

The gcode is not the variable either: the *same file* both failed and succeeded,
and it carries a real load macro (`M6211 A1 L200 T<n>`). A file asking for
filament proves nothing, because that macro can fail silently.

**Confirming a print afterwards needs a human**, because the chamber camera
looks across the front lip and cannot see the plate centre — it reads empty
before and after a successful print. Ask specifically about the **purge line**:
no purge line means filament never reached the nozzle; a purge line with no part
means adhesion. See also #34 (slot numbering) and #35 (a `.3mf` is not a job).

### 42. The mating face is a tolerance surface — don't print it as layer 1

**Status: observed and diagnosed, not yet proven by a comparison print.**

The Top half currently prints mating-face-down, so the socket mouths — the one
set of features that has to hold a fit — are drawn in the first, most-squished
layers. The consequences show up under magnification and both hurt the snap fit:

- **The bore goes out of round.** The funnel's concentric steps form cleanly on
  one side while extrudate encroaches from the other, so clearance stops being
  uniform. A peg can be loose overall and still bind on one axis.
- **The face goes ridged**, with valleys between adjacent beads. Two halves then
  rest on high spots and never fully seat, stealing engagement on top of what
  #40 already spent.

The proof is available in any single print: the *Bottom* half's mating face is a
**top surface** and comes out visibly smoother than the Top's, same filament,
same run. Glitter-loaded filaments make it worse — they resolve small features
noticeably less well than plain PLA.

**Candidate fix:** flip the Top in `EXPORT_FLIP_X_DEG` so its mating face prints
as a top surface. The Top's outer face is the *back* of the bead, so nothing
cosmetic is lost by putting that against the plate, and the sockets become blind
holes drilled down from a smooth surface — which also removes the reason
`SOCKET_LEADIN` exists. This changes print orientation for every bead in a set,
so prove it on one part before adopting it.

**A FOURTH consequence, found 2026-09-04 and worth more than the other three.**
Holes-down means each socket is a hole rising from the plate that has to **close
over** at `PEG_HEIGHT + 0.3`: the slicer bridges a 2.6mm circular ceiling across
open air, three times per bead. A bridge that sags droops *into* the bore — so
the same orientation that squeezes the mouth also deforms the roof. **Holes-up
has no bridge anywhere**: the part starts solid on the plate and the sockets are
simply pits opening at the top face. That is strictly easier to print, and it is
the argument that finally moved this from "candidate" to "do it".

**Also note what holes-down does to the FIRST LAYER, not just the bores.** Three
2.6mm mouths plus their funnels sit ~2.2mm in from the edge, so the layer that
must grip the plate is a thin interrupted ring. On 2026-09-04 that half lifted
and warped repeatedly while the solid-faced Bottom never did once — same
filament, same plate, same run. Holes-up makes the first layer a solid
uninterrupted outline.

**Acted on 2026-09-04, still unproven.** `beads/glow-set/print/GLOW/
*_Top_HOLESUP.stl` are the flipped meshes (rotated 180° about X, re-seated on
z=0, verified per shape against that shape's own peg coordinates). Flipping in
post like this works on any exported Top and needs no rebuild; `EXPORT_FLIP_X_DEG`
is the cleaner route once it is proven. **Predictions:** round bores with
`xy_hole_compensation` at 0, halves that close flush, and possibly a fit that
reads LOOSE for the first time — because the bores were previously undersized by
squish, so an accurate bore exposes the true `PEG_CLEAR`. Loose is a one-number
fix, not a reason to revert.

### 43. Ganged plates fail where singles succeed — the nozzle clips parts in transit

**Status: mechanism identified from a 0/5 vs 7/7 split plus owner reports; the
corrective print was still on the bed when this was written.**

Single beads printed **7/7**. Every multi-bead tray failed — **0/5** — and the
failures looked like contamination: smeared tops, a wad of curled filament cooked
onto the nozzle, eventually a blob that levered the magnetic toolhead cover off
and tripped `ErrorCode 707`.

**None of that is the cause. The nozzle is physically clipping an already-printed
part while travelling to the next one**, tearing it off the plate and winding it
on. Inter-object travel *only exists on a multi-part plate*, which is the entire
singles-vs-trays split stated as a mechanism instead of a correlation.

Everything else is downstream, and chasing it wastes evenings:

    ??? the collision  ->  print fails  ->  nozzle extrudes into open air
                       ->  blob forms on the toolhead
                       ->  blob props the magnetic cover  ->  ErrorCode 707

The tell in the debris is a **strand arcing from one part to its neighbour** and
**curled** (not blobby) filament — that is peeled part-top, not ooze. An isolated
part on a crowded plate surviving while its neighbours die is the same evidence.
Beware: Elegoo's own docs describe *"waste piles up, props the toolhead, knocks
the cover off"* — that is the same downstream chain from the machine's point of
view, not a diagnosis.

**The fix is `print_sequence = by object`**, which finishes each bead before
starting the next so nothing is ever travelled over. Beads are only ~4 mm tall,
far below any gantry-clearance limit, so sequential printing is always available
to us.

**But `tools/make_plate.py` CONCATENATES the beads** (`trimesh.util.concatenate`)
into one `Bottom` mesh and one `Top` mesh. The slicer then sees **2 objects, not
2N**, and by-object faithfully prints "all bottoms, then all tops" — the travel
we care about is *inside* one object, where sequential printing cannot reach it.
The estimate moved 14m54s -> 14m56s and nothing changed.

**So a ganged plate needs the meshes split into real objects.** In the slicer:
select each -> right-click -> **Split -> to objects**. Until `make_plate.py`
grows a no-merge mode (and `build_3mf.py` learns to emit one parent object per
bead — it is currently built around exactly two parents), **this GUI step is
mandatory for any ganged plate.**

**Verify it structurally in the GCODE, never from the settings panel.** Count
downward Z resets: sequential printing drops back to layer 1 once per object, so
N beads give N-1 big drops.

    grep -oE '^G[01] Z[0-9.]+' out.gcode      # then look for Z falling by >1mm

Merged: 1 reset. Split into six: 5 resets, `(3.8 -> 0.2) x3` then `(4.0 -> 0.2) x2`.

**The panel lies often enough that this is a rule, not a precaution.** In one
evening `reduce_crossing_wall` was set and read back `0` in the gcode (it needs a
string `"1"`, not an int), and `z_hop_types = Auto Lift` — which *sounds* like
Z-hop is on — produced **2 standalone `G1 Z` moves in 33,000**. Use `Normal Lift`
if you want lift, and confirm by counting.

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
