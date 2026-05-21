"""Robot Charm Builder.

A two-half snap-fit NFC charm shaped like a humanoid robot — antenna head,
boxy torso with arms outstretched, articulated legs. The show face on Top
has two raised eye dots in a contrasting filament (the only multi-color
region; everything else is body-color).

CONFIG-driven; edit values at the top and re-run via the Blender MCP:
    exec(open(r"D:\\Projects\\nfc-bead\\beads\\robot\\build_robot.py").read(),
         {"__name__": "__main__"})

Or headless:
    blender --background --python beads/robot/build_robot.py
"""
import bpy
import bmesh
import math
import json
import os
from mathutils import Vector

# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() \
       else r"D:\Projects\nfc-bead\beads\robot"

SVG_PATH = os.path.join(HERE, "robot.svg")
OUTPUT_DIR = os.path.join(HERE, "print")
OUTPUT_BLEND = os.path.join(OUTPUT_DIR, "robot_charm.blend")

TARGET_WIDTH = 25.0
THICKNESS    = 5.0

# String hole — head region, dropped down off the antenna into the wide head
# band so the wall above is solid silhouette, not the 2mm-wide antenna spike
# (gotcha: see prompts/nfc-bead/prompt.md "String-hole placement rules").
HOLE_DIAMETER = 2.0
HOLE_Y        = 4.0       # mm — wide head band (silhouette ≥ 12 mm wide here)
HOLE_Z_OFFSET = 1.25      # mm — THICKNESS/4 → hole sits entirely inside Top half
                          # (gotcha #23: better first-layer adhesion than split-plane).

# NFC pocket — torso center, just below the bead's geometric center so the
# perimeter clears the antenna mount and body-arm gaps (after fill).
NFC_DIAMETER = 10.5
NFC_DEPTH    = 0.8
NFC_POS      = (0.0, -1.5)

# Pegs — friction fit on Bottom (gotcha #14: pegs on Bottom because Top has
# raised eye decoration). Triangulated: two in the head shoulders, one in
# the right leg. All checked clean by the silhouette-probe pass.
PEG_DIAMETER  = 2.0
PEG_HEIGHT    = 1.5
PEG_CLEARANCE = 0.1

PEGS = [
    ( 0.0, +8.0),    # head top center — between antenna and string hole
    (-3.0, -10.5),   # left leg
    (+3.0, -10.5),   # right leg
]

# Eyes — two raised dots on Top's outer face, contrasting filament.
EYE_RADIUS    = 0.9      # mm — slightly under 1mm so eyes read as dots
EYE_HEIGHT    = 0.4      # mm — relief above the show face
EYE_LIFT      = 0.01     # mm — anti-Z-fighting lift (gotcha #11)
EYES = [
    (-2.5, +7.0),
    (+2.5, +7.0),
]

# Decoration cropper z-padding (mm) — extends the cropper above and below
# the eye disks so the INTERSECT boolean is unambiguously through-going.
CROPPER_Z_PAD = 0.2

# ═══════════════════════════════════════════════════════════
# BUILD
# ═══════════════════════════════════════════════════════════

os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_BOTTOM = os.path.join(OUTPUT_DIR, "robot_bottom.stl")
OUTPUT_TOP    = os.path.join(OUTPUT_DIR, "robot_top.stl")
OUTPUT_DECO   = os.path.join(OUTPUT_DIR, "robot_decoration.stl")


def clean_mesh(obj, threshold=0.005):
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=threshold)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def boolean_op(target, cutter, operation='DIFFERENCE', name="Bool"):
    bpy.context.view_layer.objects.active = target
    target.select_set(True)
    b = target.modifiers.new(name=name, type='BOOLEAN')
    b.operation = operation
    b.object = cutter
    b.solver = 'EXACT'
    bpy.ops.object.modifier_apply(modifier=name)
    bpy.ops.object.select_all(action='DESELECT')
    cutter.select_set(True)
    bpy.ops.object.delete()


def check_nonmanifold(obj):
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold()
    bm = bmesh.from_edit_mesh(obj.data)
    nm = sum(1 for e in bm.edges if e.select)
    bpy.ops.object.mode_set(mode='OBJECT')
    return nm


def verify_hole(obj, origin, direction, label=""):
    dg = bpy.context.evaluated_depsgraph_get()
    eo = obj.evaluated_get(dg)
    r = eo.ray_cast(origin, direction)
    status = "OPEN" if not r[0] else f"hit z={r[1].z:+.3f}"
    print(f"  {label}: {status}")
    return not r[0]


def build_silhouette_cropper(svg_path, target_w_mm, z_lo, z_hi):
    """Gotcha #26: fresh silhouette extrusion, no peg/NFC/string-hole features."""
    pre = {o.name for o in bpy.context.scene.objects}
    bpy.ops.import_curve.svg(filepath=svg_path)
    curves = [o for o in bpy.context.scene.objects
              if o.type == 'CURVE' and o.name not in pre]
    bpy.ops.object.select_all(action='DESELECT')
    for o in curves: o.select_set(True)
    bpy.context.view_layer.objects.active = curves[0]
    if len(curves) > 1: bpy.ops.object.join()
    cv = bpy.context.active_object
    cv.data.dimensions = '2D'; cv.data.fill_mode = 'BOTH'; cv.data.resolution_u = 64
    bpy.ops.object.convert(target='MESH')
    m = bpy.context.active_object
    sf = (target_w_mm / 1000.0) / m.dimensions.x
    m.scale = (sf, sf, sf); bpy.ops.object.transform_apply(scale=True)
    m.scale = (1000, 1000, 1000); bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    m.location = (0, 0, z_lo)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.01)
    bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(5))
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.extrude_region_move(
        TRANSFORM_OT_translate={"value": (0, 0, z_hi - z_lo)})
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    m.name = "Cropper_tmp"
    return m


print("=" * 60)
print("Robot Charm Build")
print("=" * 60)

# ── Step 0: Clean scene ───────────────────────────────────
# Gotcha #17: don't use read_factory_settings — kills the MCP addon.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
for c in list(bpy.data.collections):
    if c.name != 'Scene Collection':
        bpy.data.collections.remove(c)
# Gotcha #20: nuke stale FullBead/cropper duplicates
for n in list(bpy.data.objects.keys()):
    if n.startswith(("FullBead", "Cropper_", "Cutter_")):
        bpy.data.objects.remove(bpy.data.objects[n], do_unlink=True)

# ── Step 1: Import + scale silhouette ─────────────────────
bpy.ops.import_curve.svg(filepath=SVG_PATH)
curves = [o for o in bpy.context.scene.objects if o.type == 'CURVE']
print(f"Imported {len(curves)} curve(s)")

bpy.ops.object.select_all(action='DESELECT')
for o in curves: o.select_set(True)
bpy.context.view_layer.objects.active = curves[0]
if len(curves) > 1: bpy.ops.object.join()

cv = bpy.context.active_object
cv.data.dimensions = '2D'; cv.data.fill_mode = 'BOTH'; cv.data.resolution_u = 64

bpy.ops.object.convert(target='MESH')
mesh_obj = bpy.context.active_object

cur_w = mesh_obj.dimensions.x
if cur_w > 0:
    sf = (TARGET_WIDTH / 1000.0) / cur_w
    mesh_obj.scale = (sf, sf, sf)
    bpy.ops.object.transform_apply(scale=True)
mesh_obj.scale = (1000, 1000, 1000)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
mesh_obj.location = (0, 0, 0)

bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.005)
bpy.ops.mesh.normals_make_consistent(inside=False)

# ── Step 2: Dedup + collapse to clean n-gons ──────────────
# The SVG importer triangulates the robot path into ~13.5K dense, partly
# overlapping triangles. `remove_doubles(0.01)` welds the obvious dupes,
# then `dissolve_limited` collapses all coplanar triangles into a small
# set of large n-gons — turning the messy triangulation into ~14 clean
# polygon faces (outer silhouette + each interior body-arm/leg/neck gap
# as its own filled n-gon). Extruding from these n-gons produces a
# manifold solid. Without this step, the post-extrude mesh has thousands
# of non-manifold edges that cascade through every boolean.
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.01)
bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(5))
bpy.ops.mesh.normals_make_consistent(inside=False)

# ── Step 3: Extrude to thickness ──────────────────────────
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.extrude_region_move(
    TRANSFORM_OT_translate={"value": (0, 0, THICKNESS)}
)
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.005)
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')

bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
mesh_obj.location = (0, 0, 0)
dims = mesh_obj.dimensions
print(f"Extruded silhouette: {dims.x:.2f} x {dims.y:.2f} x {dims.z:.2f} mm")

# ── Step 4: String hole (gotcha #13: real z_mid, gotcha #23: offset) ───
zs = [v.co.z for v in mesh_obj.data.vertices]
z_mid_live = (min(zs) + max(zs)) / 2.0
z_hole = z_mid_live + HOLE_Z_OFFSET
print(f"String hole: {HOLE_DIAMETER}mm at Y={HOLE_Y}, z={z_hole:+.2f} "
      f"(offset={HOLE_Z_OFFSET:+.2f})")
bpy.ops.mesh.primitive_cylinder_add(
    vertices=48, radius=HOLE_DIAMETER / 2.0,
    depth=dims.x * 4, location=(0, HOLE_Y, z_hole),
    rotation=(0, math.radians(90), 0),
)
boolean_op(mesh_obj, bpy.context.active_object, 'DIFFERENCE', "Hole")
clean_mesh(mesh_obj)

bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
mesh_obj.location = (0, 0, 0)
mesh_obj.name = "FullBead"

z_min = min(v.co.z for v in mesh_obj.data.vertices)
z_max = max(v.co.z for v in mesh_obj.data.vertices)
z_mid = (z_min + z_max) / 2.0
print(f"Z range: {z_min:+.2f} to {z_max:+.2f}  mid={z_mid:+.2f}")

# ── Step 5: Verify peg + NFC perimeters ───────────────────
print("\nPeg + NFC perimeter check:")
depsgraph = bpy.context.evaluated_depsgraph_get()
eval_full = mesh_obj.evaluated_get(depsgraph)
nfc_r = NFC_DIAMETER / 2.0
peg_r = PEG_DIAMETER / 2.0
perim8 = [(peg_r * math.cos(k * math.pi / 4.0),
           peg_r * math.sin(k * math.pi / 4.0)) for k in range(8)]
nfc_perim = [(nfc_r * math.cos(k * math.pi / 8.0),
              nfc_r * math.sin(k * math.pi / 8.0)) for k in range(16)]

nfc_misses = sum(1 for ox, oy in nfc_perim
                 if not eval_full.ray_cast(
                     Vector((NFC_POS[0]+ox, NFC_POS[1]+oy, z_max+5)),
                     Vector((0,0,-1)))[0])
print(f"  NFC ({NFC_POS[0]:+.1f},{NFC_POS[1]:+.1f}) r={nfc_r}: "
      f"perimeter inside silhouette = {16-nfc_misses}/16"
      + (f"  CLIPPING {nfc_misses}/16!" if nfc_misses else ""))

for i, (px, py) in enumerate(PEGS):
    center_hit = eval_full.ray_cast(Vector((px, py, z_max+5)), Vector((0,0,-1)))[0]
    edge_misses = sum(1 for ox, oy in perim8
                      if not eval_full.ray_cast(
                          Vector((px + ox, py + oy, z_max+5)),
                          Vector((0,0,-1)))[0])
    nfc_dist = math.sqrt((px - NFC_POS[0])**2 + (py - NFC_POS[1])**2)
    nfc_clear = nfc_dist - nfc_r - peg_r
    hole_dist = abs(py - HOLE_Y)
    flag = ""
    if not center_hit: flag += " NO_CENTER"
    if edge_misses: flag += f" EDGE_MISS_{edge_misses}/8"
    if nfc_clear < 0: flag += " NFC_CONFLICT"
    print(f"  Peg {i} ({px:+.1f},{py:+.1f}): center={'█' if center_hit else '·'}  "
          f"edge_miss={edge_misses}/8  NFC_clr={nfc_clear:+.2f}mm  "
          f"hole_dist={hole_dist:.1f}mm{flag}")

# ── Step 6: Split into halves via planar bisect ────────────
# `bisect` is purpose-built for cutting a mesh along a plane and capping
# the cut with a single n-gon — cleaner than INTERSECT'ing with a box,
# which leaves hundreds of boundary edges along the cut on this mesh
# (the SVG path dissolves into multiple disconnected n-gons, and the box
# boolean trips on the disconnected silhouette pieces at the cut plane).
def bisect_keep(obj, z_plane, keep_below: bool, new_name: str):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.duplicate()
    half = bpy.context.active_object
    half.name = new_name
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.bisect(
        plane_co=(0, 0, z_plane), plane_no=(0, 0, 1),
        use_fill=True,
        clear_inner=not keep_below,
        clear_outer=keep_below,
    )
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    return half

print("\n--- Bottom Half (bisect) ---")
bottom = bisect_keep(mesh_obj, z_mid, keep_below=True, new_name="Bottom")
print(f"Bottom non-manifold: {check_nonmanifold(bottom)}")

print("\n--- Top Half (bisect) ---")
top = bisect_keep(mesh_obj, z_mid, keep_below=False, new_name="Top")
print(f"Top non-manifold: {check_nonmanifold(top)}")

# ── Step 7: NFC pocket on bottom ──────────────────────────
b_z_max = max(v.co.z for v in bottom.data.vertices)
nfc_cutter_depth = NFC_DEPTH * 2 + 0.1
print(f"\nNFC pocket: {NFC_DIAMETER}mm × {NFC_DEPTH}mm at {NFC_POS}")
bpy.ops.mesh.primitive_cylinder_add(
    vertices=64, radius=NFC_DIAMETER / 2.0, depth=nfc_cutter_depth,
    location=(NFC_POS[0], NFC_POS[1], b_z_max - NFC_DEPTH + nfc_cutter_depth / 2.0),
)
boolean_op(bottom, bpy.context.active_object, 'DIFFERENCE', "NFC")
clean_mesh(bottom)

# ── Step 8: Peg holes on Top (gotcha #1: AFTER split) ────────────────
t_z_min = min(v.co.z for v in top.data.vertices)
hole_r = (PEG_DIAMETER + PEG_CLEARANCE * 2) / 2.0
print(f"\nPeg holes on Top (r={hole_r:.2f}mm)...")
for i, (px, py) in enumerate(PEGS):
    cutter_bottom = t_z_min - 1.0
    cutter_top = t_z_min + PEG_HEIGHT + 0.3
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32, radius=hole_r, depth=cutter_top - cutter_bottom,
        location=(px, py, (cutter_bottom + cutter_top) / 2.0),
    )
    boolean_op(top, bpy.context.active_object, 'DIFFERENCE', f"PH{i}")
clean_mesh(top)
print(f"Top after peg holes non-manifold: {check_nonmanifold(top)}")

print("Verifying peg holes are open:")
for i, (px, py) in enumerate(PEGS):
    verify_hole(top, Vector((px, py, t_z_min - 2)), Vector((0, 0, 1)), f"Peg {i}")

# ── Step 9: Pegs on Bottom (gotcha #3: boolean UNION, not join) ──────
b_z_max = max(v.co.z for v in bottom.data.vertices)
print(f"\nPegs on Bottom (d={PEG_DIAMETER}mm, h={PEG_HEIGHT}mm)...")
for i, (px, py) in enumerate(PEGS):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32, radius=PEG_DIAMETER / 2.0, depth=PEG_HEIGHT,
        location=(px, py, b_z_max + PEG_HEIGHT / 2.0),
    )
    boolean_op(bottom, bpy.context.active_object, 'UNION', f"Peg{i}")
clean_mesh(bottom)
print(f"Bottom after pegs non-manifold: {check_nonmanifold(bottom)}")

# ── Step 10: Eyes — raised dots on Top's show face ────────────────────
t_z_max = max(v.co.z for v in top.data.vertices)
eye_z = t_z_max + EYE_HEIGHT / 2.0 + EYE_LIFT
print(f"\nEyes: {len(EYES)} disks (r={EYE_RADIUS}mm, h={EYE_HEIGHT}mm) at z={eye_z:+.2f}")

eye_objs = []
for i, (ex, ey) in enumerate(EYES):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32, radius=EYE_RADIUS, depth=EYE_HEIGHT,
        location=(ex, ey, eye_z),
    )
    eye = bpy.context.active_object
    eye.name = f"Eye{i}_tmp"
    eye_objs.append(eye)

# Join into a single Decoration object
bpy.ops.object.select_all(action='DESELECT')
for e in eye_objs: e.select_set(True)
bpy.context.view_layer.objects.active = eye_objs[0]
bpy.ops.object.join()
deco = bpy.context.active_object
deco.name = "Decoration"
clean_mesh(deco)

# Re-origin to bbox center so the export skill's share-shift with Top
# preserves the eye cluster's offset from the silhouette center. Without
# this, Decoration's local origin sits at the first eye's center (a side
# effect of bpy.ops.object.join keeping the active object's origin) and
# the eyes land off-center in the exported STL.
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
print(f"Decoration: bbox-centered origin at world {tuple(deco.location)}")
print(f"Decoration non-manifold: {check_nonmanifold(deco)}")

# Skip crop: eye dots (r=0.9mm) at (±2.5, +7) sit ~5mm inside the silhouette
# head boundary — no risk of extending past. The fresh-silhouette cropper
# (gotcha #26) is needed for decorations that span the silhouette outline;
# tiny dots well inside the head don't need it. The robot SVG's path also
# dissolves into multiple disjoint n-gons, which makes the EXACT solver
# unreliable here — INTERSECT with the cropper silently killed one eye on
# the first pass.

# ── Step 11: Position for display + flip Bottom ───────────────────────
mesh_obj.hide_set(True); mesh_obj.hide_render = True

bpy.ops.object.select_all(action='DESELECT')
bottom.select_set(True); bpy.context.view_layer.objects.active = bottom
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
bottom.rotation_euler = (math.radians(180), 0, 0)
bpy.ops.object.transform_apply(rotation=True)
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
bottom.location = (-18, 0, bottom.dimensions.z / 2.0)

bpy.ops.object.select_all(action='DESELECT')
top.select_set(True); bpy.context.view_layer.objects.active = top
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
top.location = (18, 0, top.dimensions.z / 2.0)

# Decoration share's Top's display position PLUS the eye-cluster offset
# (eyes sit at y=+7 on the head). Decoration's origin is already bbox-
# centered, so location = (18, +7, z) places the eye cluster's centroid
# at world (18, +7). The export skill's share-shift with Top (-18, 0)
# then lands the decoration at (0, +7) in the slicer, preserving the
# eye-on-face relationship.
EYE_CLUSTER_Y = (EYES[0][1] + EYES[1][1]) / 2.0
deco.location = (18, EYE_CLUSTER_Y,
                 top.dimensions.z + deco.dimensions.z / 2.0 + EYE_LIFT)

# ── Step 12: Materials (display only — slicer filaments override) ────
for obj, color, name in [
    (bottom, (0.20, 0.22, 0.25, 1.0), "BodyMat"),    # gunmetal
    (top,    (0.20, 0.22, 0.25, 1.0), "BodyMat2"),   # same
    (deco,   (1.00, 0.25, 0.10, 1.0), "EyesMat"),    # bright orange
]:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.4
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_flat()

# ── Step 12.5: Export-flip override (gotcha #16) ──────────────────────
# Display layout above ALREADY flipped Bottom 180° around X so the user
# sees the silhouette face up on both halves. The bead-stl-export skill
# then re-applies its default 180° X-flip on Bottom → silhouette lands
# on the build plate with pegs pointing up. Top stays unflipped → inner
# face (peg-hole side) on plate, eyes facing up. Default behavior is
# correct; no override needed.

# ── Step 13: Save .blend ──────────────────────────────────────────────
bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_BLEND)

print("\n" + "=" * 60)
for obj, label in [(bottom, "Bottom"), (top, "Top"), (deco, "Decoration")]:
    d = obj.dimensions
    print(f"{label}: {d.x:.2f} x {d.y:.2f} x {d.z:.2f} mm")
print(f"\nSaved .blend: {OUTPUT_BLEND}")
print("Run bead-stl-export skill to write the STLs, then `uv run nfc-build-3mf`.")
print("Done!")
