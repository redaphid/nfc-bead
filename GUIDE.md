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
