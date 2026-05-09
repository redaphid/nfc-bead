# Guide: SVG Logo to 3D-Printable Snap-Fit Charm

A step-by-step reference for turning any 2D logo SVG into a two-half 3D-printable charm with friction-fit pegs and an NFC pocket. Written from hard-won experience building the Wooli mammoth charm.

## Pipeline Overview

```
SVG silhouette
  → Import into Blender as 2D curve
  → Convert to mesh, scale to target size
  → Fill any interior gaps that interfere with features
  → Extrude to desired thickness
  → Boolean DIFFERENCE for string hole
  → Box-cut INTERSECT to split into halves
  → Boolean DIFFERENCE for NFC pocket (bottom)
  → Boolean DIFFERENCE for peg holes (top, POST-split)
  → Boolean UNION for pegs (bottom)
  → Flip bottom for printing, export STLs
```

## Step-by-Step

### 1. SVG Import and Scaling

```python
bpy.ops.import_curve.svg(filepath=SVG_PATH)
# Join all curves, set 2D fill
curve_obj.data.dimensions = '2D'
curve_obj.data.fill_mode = 'BOTH'
curve_obj.data.resolution_u = 64  # smooth curves
# Convert to mesh
bpy.ops.object.convert(target='MESH')
# Scale: SVG imports in meters, scale to target mm
```

**Key point**: `resolution_u = 64` gives smooth curves. Lower values produce visible faceting on curves.

### 2. Handling Interior Holes in the Silhouette

Many logos have interior through-holes (e.g., the space inside a letter "O", or in our case, the gap between the mammoth's trunk and body). These can interfere with features like NFC pockets.

**To fill a specific hole** (while preserving others):
```python
# In edit mode, select boundary edges of the target hole by position
for e in bm.edges:
    if e.is_boundary:
        if (both verts within the hole's coordinate range):
            e.select = True
bpy.ops.mesh.fill()
```

**What NOT to do**:
- Don't add an overlapping rectangle in the SVG — it creates a separate boundary that doesn't merge with the hole
- Don't use `bpy.ops.mesh.fill()` on ALL boundary edges — it fills every hole including ones you want to keep
- Don't use Solidify modifier with interior holes — it creates topology issues. Use Extrude instead.

### 3. Extrude vs Solidify

**Use Extrude**, not Solidify, when your 2D profile has interior holes (like the leg gap):

```python
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.extrude_region_move(
    TRANSFORM_OT_translate={"value": (0, 0, THICKNESS)}
)
```

Solidify modifier can produce bad topology around interior boundaries. Extrude gives a clean result.

### 4. Boolean Operations — The EXACT Solver

Always use `solver = 'EXACT'` for boolean operations. The FAST solver produces non-manifold geometry.

After every boolean, clean up:
```python
bpy.ops.mesh.remove_doubles(threshold=0.005)  # tight threshold!
bpy.ops.mesh.normals_make_consistent(inside=False)
```

**Critical**: Use a tight `remove_doubles` threshold (0.005mm). Larger values (0.02+) can destroy small features or collapse geometry.

### 5. Splitting into Halves

Use a box-cut boolean INTERSECT at the midpoint:

```python
# Create a box covering the bottom half of the bead
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z_min + half_height/2))
box.scale = (200, 200, half_height)
# INTERSECT keeps only the overlap
b = obj.modifiers.new(name="Cut", type='BOOLEAN')
b.operation = 'INTERSECT'
b.object = box
b.solver = 'EXACT'
```

### 6. Peg Holes — The Coplanarity Trap

**CRITICAL**: Cut peg holes AFTER splitting, not before.

If you cut peg holes in the full bead before splitting, the box-cut INTERSECT boolean at the split plane (z=0) is coplanar with the peg hole bottoms. The EXACT solver loses the holes — they get sealed shut.

**Solution**: Split first, then cut peg holes into the top half with cutters that extend **1mm below the inner face**:

```python
cutter_bottom = inner_face_z - 1.0  # extend past the face
cutter_top = inner_face_z + PEG_HEIGHT + 0.3
```

This ensures the boolean cutter fully penetrates the inner face rather than being coplanar with it.

### 7. Adding Pegs — Boolean UNION, Not Mesh Join

**Use boolean UNION** to add pegs to the bottom half:

```python
b = bottom.modifiers.new(name="Peg", type='BOOLEAN')
b.operation = 'UNION'
b.object = peg_cylinder
b.solver = 'EXACT'
```

**Do NOT use mesh join** (`bpy.ops.object.join()`). Mesh join creates 1000+ non-manifold edges where the peg cylinder meets the flat inner face, because overlapping coplanar faces don't merge cleanly.

### 8. Verifying Features with Raycast

After building, verify holes are actually open:

```python
from mathutils import Vector
depsgraph = bpy.context.evaluated_depsgraph_get()
eval_obj = obj.evaluated_get(depsgraph)
# Cast ray through where the hole should be
result = eval_obj.ray_cast(origin, direction)
if result[0]:
    print(f"BLOCKED at z={result[1].z}")  # hole is sealed
else:
    print("OPEN")  # hole goes through
```

### 9. Print Orientation

- **Bottom half**: Flip 180° around X so the mammoth face is on the build plate and pegs face up
- **Top half**: Inner face (with peg holes) is already at the bottom — prints flat on build plate

## Lessons Learned

| Issue | Cause | Fix |
|-------|-------|-----|
| Voxel remesh seals small holes | Remesh resolution too coarse for 2mm holes | Don't use voxel remesh when holes must be preserved |
| Pre-split peg holes vanish | Boolean INTERSECT at coplanar split plane | Cut peg holes AFTER splitting |
| Peg hole cutters leave thin membrane | Cutter starts at z=0.05 (nearly coplanar) | Extend cutters 1mm BELOW inner face |
| Mesh join creates non-manifold pegs | Overlapping coplanar faces from join | Use boolean UNION instead |
| `remove_doubles(0.05)` destroys mesh | Threshold too large for small features | Use 0.005mm threshold |
| NFC pocket intersects trunk gap | Pocket placed over interior through-hole | Fill the gap in the mesh, or move the pocket |
| SVG rectangle doesn't fill hole | Separate path creates separate boundary | Select and fill the hole boundary in mesh edit mode |
| Solidify breaks interior holes | Solidify modifier produces bad topology | Use extrude instead |
| String hole splits a thin top wall | `HOLE_Y` placed in a narrow protrusion (hair ridge, ear, tip) | Drop hole down into the wider head/forehead — need ≥ 2.5 mm of solid silhouette above the hole |
| String hole only carves Top half (Bottom solid) | `location.z = THICKNESS/2` on a centered-mesh pipeline puts the cylinder at the TOP face, not the middle | Compute `z_mid = (min(zs)+max(zs))/2` from live verts and drill there. See prompt.md gotcha #13 |
| Slicer flags Top assembly as cantilever | Pegs hung off Top instead of Bottom; the body is suspended on three thin pillars | Pegs MUST be on Bottom for any charm with show-face decoration on Top — flipping Top to put pegs up would point the hair into the build plate. See gotcha #14 |
| Imported subset SVG (e.g. `hair.svg`) lands off-center | `origin_set BOUNDS` re-centers on the path bbox, not the viewBox center the silhouette is anchored to | Parse viewBox dims + path bbox, set `obj.location = (subset_cx − vbox_cx, vbox_cy − subset_cy, 0)` (Y-flipped). See gotcha #15 |
| Bottom STL lands silhouette-up after export | Export skill's default 180° X-flip on Bottom assumes a flipped-build live scene; centered-mesh builds are already in print orientation | Set `bpy.context.scene["nfc_export_flip_override"]` to `{"Bottom": 0, ...}` before running the export. See gotcha #16 |
| MCP socket dies after `read_factory_settings` | Factory reset unregisters the BlenderMCP addon | Don't factory-reset; delete objects explicitly. Or relaunch via `tools/launch.ps1`. See gotcha #17 |
| `if __name__ == "__main__"` block doesn't run | `exec(open(...).read())` keeps the calling module's `__name__` | Pass `ns = {"__name__": "__main__"}` to `exec(script, ns)`, or call `main()` directly. See gotcha #18 |
| Color extraction loses saturation under blur | `gaussian_filter(rgb, sigma=4)` blurs the channel axis too, collapsing chrominance | Use `sigma=(blur, blur, 0)` to leave channels untouched. See gotcha #19 |
| `FullBead.001..N` accumulating across rebuilds | Re-running the build doesn't clean intermediate objects | Wipe `FullBead*` at the top of the build, or `bpy.data.objects.remove` explicitly. See gotcha #20 |
| NFC pocket clips past silhouette boundary on one side | No perimeter check on the NFC — only its center was validated | Add 16-point raycast around the pocket boundary. See gotcha #24 |
| Multi-region SVGs land at different scales/positions | Each SVG auto-fit to its own path bbox; bboxes differ between regions | Use the polygon-manifest pipeline (`regions.json` + `polygons_to_mesh()`). See gotcha #25 |
| Decoration shows visible peg-socket circles | Cropper was made from a duplicate of Top; peg sockets propagate as holes through the decoration | Build cropper from a fresh `silhouette.svg` extrusion via `build_silhouette_cropper()`. See gotcha #26 |
| Multi-color decoration layer disappears or shows wrong filament in slicer | Z-step between decoration layers below slicer layer height (0.16mm); slicer can't disambiguate | Set `DECO_LAYER_STEP ≥ 0.16mm` (0.20mm for safety). See gotcha #27 |
| 3MF imports as "too small" / one half upside-down | Each part added as a separate top-level `<object>` with own `<item>` confuses the slicer | Wrap Top + decorations in a single `ComponentsObject` with one build item. See gotcha #28 |

## Multi-color decoration workflow

For charms with several colored regions on the show face (cartoon illustrations, logos, multi-filament block prints), follow this pipeline. It avoids the SVG-round-trip pitfalls and produces consistent inter-region alignment. Reference: `beads/filibertos-taco/`.

### 1. Source-image extraction (k-means clustering)

If your input is a colored bitmap (JPG/PNG illustration), use k-means on FG pixels to identify color clusters, then map clusters to named regions via predicate functions. See `beads/filibertos-taco/extract_regions.py`.

### 2. Polygon manifest (`regions.json`)

Emit each region's polygon vertices in **shared mm coordinates** (origin = silhouette bbox center, +Y up). Use the dict shape `{outer: [(x,y),...], holes: [[(x,y),...], ...]}` so ring polygons (e.g. silhouette outline) carry both the outer and inner contours.

For ring polygons specifically: build the outer + inner contours with **shapely's `.buffer(-N)`** of the silhouette polygon. This guarantees the outer edge of the ring matches the silhouette.svg used for the bead body.

### 3. Build → `polygons_to_mesh()`

Consume the manifest and call `polygons_to_mesh(polygons, name, z=...)` (provided in `build_charm.py.example`). It handles simple polygons, ring polygons (via `bridge_loops`), and multi-hole polygons (via `triangle_fill`).

### 4. Crop with `build_silhouette_cropper()`

Always build the decoration cropper from a fresh `silhouette.svg` import — not a duplicate of Top, which propagates peg-socket holes through the decoration. Helper in `build_charm.py.example`.

### 5. Z-stack with ≥0.16mm step

Each decoration layer needs `DECO_LAYER_STEP ≥ slicer layer height` so the slicer assigns each unambiguously to its own filament. Order matters in the build's iteration: things at higher Z OCCLUDE things below — put the visually dominant decoration last.

### 6. 3MF bundling

Wrap Top + every Decoration into a single `ComponentsObject` with **one build item**; Bottom on its own build item with a plate offset. See `tools/make_3mf.py` for the canonical Top + Hair + Decoration set; mirror its structure for charms with more decoration layers (e.g. `beads/filibertos-taco/bundle_3mf.py`).

## Dimensions Reference (Wooli Charm)

| Feature | Value |
|---------|-------|
| Overall width | 25mm |
| Overall height | ~19.7mm |
| Thickness | 5mm (2.5mm per half) |
| String hole | 2mm diameter, X-axis through head |
| NFC pocket | 10.5mm diameter, 0.8mm deep |
| Peg diameter | 1.5mm |
| Peg height | 1.5mm |
| Peg hole clearance | 0.1mm per side |
| Peg positions | (-4, 6), (7, -3), (5, -7) |
