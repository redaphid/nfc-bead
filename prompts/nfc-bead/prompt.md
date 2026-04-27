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
