"""
Rezz NFC Bead Builder — round bead, raised black spiral on recessed red background.

Run headless:
    "D:\\tools\\blender\\blender.exe" --background --python build_rezz.py

Or via Blender MCP — exec the chunks one at a time so you can watch/steer.

Outputs (out/):
  rezz_bottom.stl     — RED — bottom half flipped 180° around X for printing
  rezz_top_body.stl   — RED — top half body, peg holes on inner face
  rezz_top_spiral.stl — BLACK — raised Archimedean spiral on outer face
  rezz_charm.blend    — workspace .blend for inspection

Multi-color assembly in Elegoo Slicer:
  1. Import all three STLs
  2. Right-click rezz_top_spiral.stl → "Add as part" of rezz_top_body.stl
  3. Assign the spiral part the second filament (BLACK)
"""
import bpy, bmesh, math, os
from mathutils import Vector

# Ensure os exists at config evaluation time (top of file)

# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════

# All paths resolve relative to this script so it works from any cwd
_HERE        = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else r"D:\Projects\nfc-bead\beads\rezz"
SVG_PATH     = os.path.join(_HERE, "silhouette.svg")
OUTPUT_DIR   = os.path.join(_HERE, "print")
STAGES_DIR   = os.path.join(_HERE, "stages")

# Sized for a Kandi bracelet bead — smallest comfortable diameter that
# encloses the NTAG215 sticker (10.5 mm dia), 3 friction-fit pegs, and a
# string hole sized for elastic Kandi cord (~1 mm). At 17 mm with NFC
# centered + a 1.2 mm string hole, the peg array fits at radius 6.75 mm
# (0.5 mm gap to NFC edge, 0.75 mm wall to bead edge), and the string
# hole at Y=7 leaves a 0.9 mm top wall.
# 16 mm requires sub-0.5 mm walls everywhere — fragile, not recommended.
TARGET_WIDTH  = 17.0    # mm — bead diameter (Kandi floor with 1.2 mm string hole)
THICKNESS     = 5.0     # mm — total split into 2 × 2.5 mm halves

# String hole — horizontal through top of bead so it lays face-forward on a
# wrist. 1.2 mm fits standard Kandi elastic cord (~1 mm dia) with margin.
HOLE_DIAMETER = 1.2
HOLE_Y        = 7.0     # mm — top wall = TARGET_WIDTH/2 - HOLE_Y - HOLE_DIAMETER/2 = 0.9 mm

# NFC pocket on bottom half inner face — fixed by NTAG215 sticker geometry.
# Centered (south offset would force awkward peg positions that don't fit
# below 18 mm).
NFC_DIAMETER  = 10.5
NFC_DEPTH     = 0.8
NFC_POS       = (0.0, 0.0)

# Pegs — friction fit
PEG_DIAMETER  = 2.0
PEG_HEIGHT    = 1.5
PEG_CLEARANCE = 0.1

# Peg positions — triangulated at radius 6.75 mm from origin (NFC center).
# East + west avoid the string-hole zone at +Y; the third peg sits south of
# the NFC pocket. Clearances:
#   to NFC edge:  6.75 - 5.25 (NFC radius) - 1 (peg radius) = 0.5 mm
#   to bead edge: TARGET_WIDTH/2 - 6.75 - 1 (peg radius) = 0.75 mm
PEGS = [(-6.75, 0.0), (6.75, 0.0), (0.0, -6.75)]

# Spiral — raised on outer face of top half. Tuned to match the chunky
# red-on-black reference image: 3 strong turns, thick arms, arm-dominant
# (arm wider than gap). The reference's "many turns" appearance is
# motion-blur ghosting in the post-processing, not actual extra arms.
SPIRAL_HEIGHT      = 0.5    # mm above outer face
SPIRAL_OUTER_R     = 6.5    # mm  (~76% of bead radius)
SPIRAL_TURNS       = 3.0    # 3 strong turns — matches the reference's actual
                            # turn count once the motion blur is stripped
SPIRAL_ARM_WIDTH   = 1.6    # mm — at 3 turns / 6.5 mm radius the gap is ~0.57 mm
                            # so the spiral arm is roughly 3× the gap (arm-dominant,
                            # matching the reference where the spiral color
                            # dominates over the background between turns)
SPIRAL_SAMPLES     = 720    # 3 turns of fewer revs needs fewer samples
SPIRAL_HOLE_GUARD  = 5.0    # trim spiral above this Y so it clears the string hole

# ═══════════════════════════════════════════════════════════
# BUILD HELPERS
# ═══════════════════════════════════════════════════════════

OUT_BOTTOM = os.path.join(OUTPUT_DIR, "rezz_bottom.stl")
OUT_TOP    = os.path.join(OUTPUT_DIR, "rezz_top_body.stl")
OUT_SPIRAL = os.path.join(OUTPUT_DIR, "rezz_top_spiral.stl")
OUT_BLEND  = os.path.join(OUTPUT_DIR, "rezz_charm.blend")

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

def verify_open(obj, origin, direction, label):
    dg = bpy.context.evaluated_depsgraph_get()
    eo = obj.evaluated_get(dg)
    hit = eo.ray_cast(origin, direction)
    status = "OPEN" if not hit[0] else f"BLOCKED at z={hit[1].z:.3f}"
    print(f"  {label}: {status}")
    return not hit[0]

def make_material(obj, rgba, name):
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.45
    obj.data.materials.clear()
    obj.data.materials.append(m)

def save_stage(num, name):
    """Save .blend snapshot + viewport PNG into stages/ for git history."""
    os.makedirs(STAGES_DIR, exist_ok=True)
    base   = f"{num:02d}_{name}"
    blend  = os.path.join(STAGES_DIR, base + ".blend")
    png    = os.path.join(STAGES_DIR, base + ".png")
    # If we're in edit mode, briefly exit so the .blend reflects the latest mesh data
    was_edit = bpy.context.active_object is not None and bpy.context.active_object.mode == 'EDIT'
    if was_edit:
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True)
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    bpy.context.scene.render.filepath = png
    # Headless Blender (no OpenGL context) — skip the viewport screenshot.
    if bpy.app.background:
        if was_edit:
            bpy.ops.object.mode_set(mode='EDIT')
        print(f"  ▶ stage saved: {base} (headless: no PNG)")
        return
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            with bpy.context.temp_override(area=area):
                bpy.ops.render.opengl(write_still=True)
            break
    if was_edit:
        bpy.ops.object.mode_set(mode='EDIT')
    print(f"  ▶ stage saved: {base}")

# ═══════════════════════════════════════════════════════════
# PIPELINE
# ═══════════════════════════════════════════════════════════

print("=" * 60)
print("Rezz Bead Build")
print("=" * 60)

# Wipe previous build mesh/curve objects, keep camera infrastructure
for obj in list(bpy.data.objects):
    if obj.type in ('MESH','CURVE') and obj.name not in ("CameraPivot","CameraTarget"):
        bpy.data.objects.remove(obj, do_unlink=True)

# 1. Import SVG silhouette
bpy.ops.import_curve.svg(filepath=SVG_PATH)
curves = [o for o in bpy.context.scene.objects if o.type == 'CURVE']
bpy.ops.object.select_all(action='DESELECT')
for c in curves:
    c.select_set(True)
bpy.context.view_layer.objects.active = curves[0]
if len(curves) > 1:
    bpy.ops.object.join()
curve_obj = bpy.context.active_object
curve_obj.data.dimensions = '2D'
curve_obj.data.fill_mode = 'BOTH'
curve_obj.data.resolution_u = 64

# 2. Convert to mesh and scale to TARGET_WIDTH
bpy.ops.object.convert(target='MESH')
mesh_obj = bpy.context.active_object
w = mesh_obj.dimensions.x
if w > 0:
    sf = (TARGET_WIDTH / 1000.0) / w
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
save_stage(1, "silhouette_flat")

# 3. Extrude to thickness
bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": (0, 0, THICKNESS)})
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.005)
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')

bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
mesh_obj.location = (0, 0, 0)
print(f"Extruded: {mesh_obj.dimensions.x:.2f} × {mesh_obj.dimensions.y:.2f} × {mesh_obj.dimensions.z:.2f} mm")
save_stage(2, "extruded")

# 4. String hole — boolean DIFFERENCE before splitting
bpy.ops.mesh.primitive_cylinder_add(
    vertices=48, radius=HOLE_DIAMETER/2.0,
    depth=mesh_obj.dimensions.x * 4,
    location=(0, HOLE_Y, 0),
    rotation=(0, math.radians(90), 0),
)
boolean_op(mesh_obj, bpy.context.active_object, 'DIFFERENCE', "StringHole")
clean_mesh(mesh_obj)
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
mesh_obj.location = (0, 0, 0)
mesh_obj.name = "FullBead"

z_min = min(v.co.z for v in mesh_obj.data.vertices)
z_max = max(v.co.z for v in mesh_obj.data.vertices)
z_mid = (z_min + z_max) / 2.0
print(f"Z range: {z_min:.2f} .. {z_max:.2f}  (mid={z_mid:.2f})")
save_stage(3, "string_hole")

# 5. Split — duplicate full bead, INTERSECT with bottom-half cube and top-half cube
def cut_half(name, z_lo, z_hi):
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.duplicate()
    half = bpy.context.active_object
    half.name = name
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, (z_lo + z_hi)/2.0))
    box = bpy.context.active_object
    box.scale = (200, 200, z_hi - z_lo)
    bpy.ops.object.transform_apply(scale=True)
    boolean_op(half, box, 'INTERSECT', "Cut")
    clean_mesh(half, 0.01)
    return half

bottom = cut_half("Bottom", z_min, z_mid)
top    = cut_half("Top",    z_mid, z_max)
print(f"Bottom non-manifold: {check_nonmanifold(bottom)}")
print(f"Top    non-manifold: {check_nonmanifold(top)}")
# Pull halves apart slightly for the snapshot so the split is visible, restore after
_orig_bottom_loc = bottom.location.copy()
_orig_top_loc    = top.location.copy()
bottom.location.z -= 1.0
top.location.z    += 1.0
mesh_obj.hide_set(True)
save_stage(4, "split")
bottom.location = _orig_bottom_loc
top.location    = _orig_top_loc
mesh_obj.hide_set(False)

# 6. NFC pocket on bottom half inner face (top of the bottom half before flip)
b_z_max = max(v.co.z for v in bottom.data.vertices)
nfc_depth_cutter = NFC_DEPTH * 2 + 0.1
bpy.ops.mesh.primitive_cylinder_add(
    vertices=64, radius=NFC_DIAMETER/2.0, depth=nfc_depth_cutter,
    location=(NFC_POS[0], NFC_POS[1], b_z_max - NFC_DEPTH + nfc_depth_cutter/2.0),
)
boolean_op(bottom, bpy.context.active_object, 'DIFFERENCE', "NFC")
clean_mesh(bottom)
save_stage(5, "nfc_pocket")

# 7. Peg HOLES on top half inner face — POST split, cutters extend 1mm below inner face
t_z_min = min(v.co.z for v in top.data.vertices)
hole_r = (PEG_DIAMETER + PEG_CLEARANCE * 2) / 2.0
for i,(px,py) in enumerate(PEGS):
    cut_bot = t_z_min - 1.0
    cut_top = t_z_min + PEG_HEIGHT + 0.3
    cut_d   = cut_top - cut_bot
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32, radius=hole_r, depth=cut_d,
        location=(px, py, (cut_bot + cut_top) / 2.0),
    )
    boolean_op(top, bpy.context.active_object, 'DIFFERENCE', f"PH{i}")
clean_mesh(top)
print(f"Top post-peg-holes non-manifold: {check_nonmanifold(top)}")
for i,(px,py) in enumerate(PEGS):
    verify_open(top, Vector((px,py,t_z_min - 2)), Vector((0,0,1)), f"Peg hole {i}")
save_stage(6, "peg_holes")

# 8. PEGS on bottom half inner face — boolean UNION, NOT mesh join
b_z_max = max(v.co.z for v in bottom.data.vertices)
for i,(px,py) in enumerate(PEGS):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32, radius=PEG_DIAMETER/2.0, depth=PEG_HEIGHT,
        location=(px, py, b_z_max + PEG_HEIGHT/2.0),
    )
    boolean_op(bottom, bpy.context.active_object, 'UNION', f"Peg{i}")
clean_mesh(bottom)
print(f"Bottom post-pegs non-manifold: {check_nonmanifold(bottom)}")
save_stage(7, "pegs")

# 9. Spiral on outer face of TOP half — separate object, exports as separate STL
# Built directly as a flat ribbon mesh (avoids the curve-bevel-then-clip approach
# which silently produces an empty mesh on tangent geometry).
top_outer_z = max(v.co.z for v in top.data.vertices)
b_coeff = SPIRAL_OUTER_R / (SPIRAL_TURNS * 2 * math.pi)
W = SPIRAL_ARM_WIDTH / 2.0

# Start at theta where centre radius >= W so inner offset stays positive
theta_start = (W * 1.05) / b_coeff
theta_end   = SPIRAL_TURNS * 2 * math.pi

# Sample centerline
center = []
for i in range(SPIRAL_SAMPLES):
    t     = i / (SPIRAL_SAMPLES - 1)
    theta = theta_start + t * (theta_end - theta_start)
    r     = b_coeff * theta
    center.append((r * math.cos(theta), r * math.sin(theta)))

# For each centerline point, compute inner/outer offsets perpendicular to tangent
inner_pts, outer_pts = [], []
for i, (cx, cy) in enumerate(center):
    if i == 0:
        tx, ty = center[1][0] - cx, center[1][1] - cy
    elif i == len(center) - 1:
        tx, ty = cx - center[-2][0], cy - center[-2][1]
    else:
        tx = center[i+1][0] - center[i-1][0]
        ty = center[i+1][1] - center[i-1][1]
    tlen = math.hypot(tx, ty) or 1.0
    tx, ty = tx / tlen, ty / tlen
    nx, ny = -ty, tx       # perpendicular, rotated 90° CCW
    inner_pts.append((cx - nx * W, cy - ny * W, top_outer_z))
    outer_pts.append((cx + nx * W, cy + ny * W, top_outer_z))

# Build flat ribbon mesh: inner row + outer row, quads between consecutive samples
# (No end-caps! The ribbon is OPEN at start and end — extrusion will close those edges
# automatically as side walls. An explicit end-cap quad here would span from start-of-
# spiral all the way to end-of-spiral, drawing a visible straight line across the disc.)
N = len(center)
verts = inner_pts + outer_pts                       # [0..N-1] inner, [N..2N-1] outer
faces = [[i, N + i, N + i + 1, i + 1] for i in range(N - 1)]
mesh = bpy.data.meshes.new("RezzSpiralMesh")
mesh.from_pydata(verts, [], faces)
mesh.update()
spiral = bpy.data.objects.new("RezzSpiral", mesh)
bpy.context.scene.collection.objects.link(spiral)

# Extrude flat ribbon up to SPIRAL_HEIGHT thickness
bpy.ops.object.select_all(action='DESELECT')
spiral.select_set(True)
bpy.context.view_layer.objects.active = spiral
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": (0, 0, SPIRAL_HEIGHT)})
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')

# No string-hole trim. The horizontal string hole runs through the bead body, not
# through the top face — the spiral above can canopy the hole opening without
# blocking threading. Earlier versions cut a notch here, but it looked like an
# obvious bite-out of the spiral and added no functional benefit.
clean_mesh(spiral)
print(f"Spiral non-manifold: {check_nonmanifold(spiral)}, dims: {spiral.dimensions[:]}")
save_stage(8, "spiral")

# 10. Position halves for printing (bottom flipped 180° around X), pegs face up
mesh_obj.hide_set(True)
mesh_obj.hide_render = True

bpy.ops.object.select_all(action='DESELECT')
bottom.select_set(True)
bpy.context.view_layer.objects.active = bottom
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
bottom.rotation_euler = (math.radians(180), 0, 0)
bpy.ops.object.transform_apply(rotation=True)
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
bottom.location = (-18, 0, bottom.dimensions.z / 2.0)

bpy.ops.object.select_all(action='DESELECT')
top.select_set(True)
bpy.context.view_layer.objects.active = top
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
top.location = (18, 0, top.dimensions.z / 2.0)

# Spiral follows the top half — keep mesh-local origin (= true bead center), do NOT
# origin_set BOUNDS (which would shift the asymmetrically-trimmed spiral off-center).
# Spiral mesh Z is already at top_outer_z..top_outer_z+SPIRAL_HEIGHT in local coords;
# lift +0.01 mm to avoid Z-fighting at the boundary with the top body.
bpy.ops.object.select_all(action='DESELECT')
spiral.select_set(True)
bpy.context.view_layer.objects.active = spiral
spiral.location = (18, 0, 0.01)

# Materials: red body, black spiral
make_material(bottom, (0.85, 0.10, 0.10, 1), "RedMat_Bottom")
make_material(top,    (0.85, 0.10, 0.10, 1), "RedMat_Top")
make_material(spiral, (0.05, 0.05, 0.05, 1), "BlackMat_Spiral")
for o in (bottom, top, spiral):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.shade_flat()
save_stage(9, "positioned")

# 10b. Orbit camera setup (idempotent — survives rebuilds, saved into the .blend)
def _setup_orbit_camera():
    pivot = bpy.data.objects.get("CameraPivot")
    if pivot is None:
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0,0,0))
        pivot = bpy.context.active_object
        pivot.name = "CameraPivot"
        pivot.rotation_mode = 'XYZ'

    target = bpy.data.objects.get("CameraTarget")
    if target is None:
        bpy.ops.object.empty_add(type='SPHERE', location=(0,0,1.5), radius=0.5)
        target = bpy.context.active_object
        target.name = "CameraTarget"
        target.hide_viewport = True
        target.hide_render = True

    cam = bpy.data.objects.get("Camera")
    if cam is None:
        cam_data = bpy.data.cameras.new("Camera")
        cam = bpy.data.objects.new("Camera", cam_data)
        bpy.context.scene.collection.objects.link(cam)

    # Reset pivot to origin in case a prior inspection run moved it
    pivot.location = (0, 0, 0)
    cam.parent = pivot
    cam.location = (0, -42, 18)
    cam.rotation_euler = (0, 0, 0)
    cam.data.type = 'PERSP'
    cam.data.lens = 50
    cam.data.clip_start = 0.5
    cam.data.clip_end = 500.0
    for c in list(cam.constraints):
        cam.constraints.remove(c)
    con = cam.constraints.new(type='TRACK_TO')
    con.target = target
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    bpy.context.scene.camera = cam

    # Sun light
    sun = bpy.data.objects.get("Sun")
    if sun is None:
        sun_data = bpy.data.lights.new("Sun", type='SUN')
        sun_data.energy = 3.0
        sun = bpy.data.objects.new("Sun", sun_data)
        sun.location = (0, 0, 30)
        bpy.context.scene.collection.objects.link(sun)

    # 90s orbit, ±55° vertical swing, 1 cycle per orbit
    PERIOD = 2160
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = PERIOD
    bpy.context.scene.render.fps = 24
    bpy.context.scene.use_preview_range = False

    if pivot.animation_data:
        pivot.animation_data_clear()
    pivot.rotation_euler = (0, 0, 0)
    pivot.keyframe_insert(data_path="rotation_euler", index=2, frame=1)
    pivot.rotation_euler = (0, 0, math.radians(360))
    pivot.keyframe_insert(data_path="rotation_euler", index=2, frame=PERIOD + 1)
    SAMPLES, AMP = 24, 55.0
    for i in range(SAMPLES + 1):
        f = 1 + int(i * PERIOD / SAMPLES)
        pivot.rotation_euler = (math.radians(AMP * math.sin(2 * math.pi * (i / SAMPLES))), 0, 0)
        pivot.keyframe_insert(data_path="rotation_euler", index=0, frame=f)

    def _iter_fcurves(action):
        if hasattr(action, 'fcurves') and action.fcurves:
            yield from action.fcurves
        if hasattr(action, 'layers'):
            for layer in action.layers:
                for strip in layer.strips:
                    if hasattr(strip, 'channelbags'):
                        for cb in strip.channelbags:
                            for fc in cb.fcurves:
                                yield fc

    for fc in _iter_fcurves(pivot.animation_data.action):
        kind = 'LINEAR' if fc.array_index == 2 else 'BEZIER'
        for kp in fc.keyframe_points:
            kp.interpolation = kind

    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.region_3d.view_perspective = 'CAMERA'
                    space.shading.type = 'MATERIAL'
    bpy.context.scene.frame_current = 1

_setup_orbit_camera()

# 11. Export STLs and .blend
os.makedirs(OUTPUT_DIR, exist_ok=True)
for obj, path in [(bottom, OUT_BOTTOM), (top, OUT_TOP), (spiral, OUT_SPIRAL)]:
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, ascii_format=False)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)

print("\n" + "=" * 60)
for obj, label in [(bottom,"bottom"),(top,"top body"),(spiral,"spiral")]:
    d = obj.dimensions
    print(f"  {label:10s}: {d.x:.2f} × {d.y:.2f} × {d.z:.2f} mm")
print(f"\nSTLs: {OUT_BOTTOM}\n      {OUT_TOP}\n      {OUT_SPIRAL}")
print(f"Blend: {OUT_BLEND}")
print("Done.")
