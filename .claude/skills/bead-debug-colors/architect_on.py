"""Apply the verified 'architect' aesthetic to the current scene.

Drapes the master-architect look over whatever bead is in the scene:
parchment world, watercolor washes on the printable bodies, dark-ink
GP line-art tracing every silhouette and crease, warm key + faint cool
fill lights, Cycles+OptiX render setup, and a camera rig (CameraPivot
+ CameraTarget + Camera with TRACK_TO).

This script does NOT animate the camera. Pair it with one of the
`anim_*.py` scripts to set up movement.

Idempotent. Settings under the 'Tunables' block; everything below
that is mechanical setup.

Verified against the rezz bead in the theater-mode worktree
(see journals/architect-aesthetic/iter_02..04 for the screenshots
that locked these values in).

Companion: `architect_off.py` strips everything this adds.
"""
import bpy, math
from mathutils import Vector

# ─── Tunables (verified values) ─────────────────────────────────────────
PARCHMENT      = (0.93, 0.86, 0.72, 1.0)   # warm cream world
INK_GRAPHITE   = (0.08, 0.10, 0.14, 1.0)   # GP line-art ink
INK_RADIUS     = 0.05                      # Blender 5.0 GP modifier (NOT 'thickness')

# Watercolor washes for the printable bodies
BOTTOM_FILL    = (0.62, 0.74, 0.82, 1.0)   # blueprint blue-gray
TOP_FILL       = (0.70, 0.80, 0.74, 1.0)   # sage
ACCENT_FILL    = (0.85, 0.62, 0.32, 1.0)   # warm bronze (raised decorations)
BODY_ROUGH     = 0.85
BODY_METALLIC  = 0.0

# Architect-aesthetic highlight palette for any DBG_* overlays
# left in the scene by recolor.py. Same hue families as the CAD palette
# (yellow=peg, red=hole, magenta=NFC, orange=string) but desaturated to
# read as draftsman's marker annotations on parchment, not engineering CAD.
# ⚠ PROPOSED — verify visually before treating as canonical.
PEG_ARCHITECT          = (0.92, 0.78, 0.30, 1.0)   # bright muted ochre
PEG_HOLE_ARCHITECT     = (0.62, 0.22, 0.20, 1.0)   # venetian red
NFC_ARCHITECT          = (0.55, 0.30, 0.50, 1.0)   # dusty rose
STRING_HOLE_ARCHITECT  = (0.78, 0.45, 0.20, 1.0)   # drafted rust

# Light setup
KEY_COLOR      = (1.00, 0.92, 0.78)        # tungsten warm
KEY_ENERGY     = 3.5
KEY_LOC        = (12, -8, 22)
KEY_ROT_DEG    = (55, 0, -25)
USE_FILL       = True
FILL_COLOR     = (0.78, 0.86, 1.00)        # cool sky
FILL_ENERGY    = 0.4
FILL_LOC       = (-6, 12, -10)
FILL_ROT_DEG   = (-50, 0, 160)

# Camera rig (no animation here — anim_*.py scripts handle that)
PIVOT_LOC      = (0, 0, 0)
TARGET_LOC     = (0, 0, 1.5)
CAM_BASE_LOC   = (0, -50, 18)
CAM_LENS_MM    = 50

# Render
RENDER_SAMPLES = 64
USE_OPTIX      = True

# When set, will re-tint any DBG_* overlay objects (from recolor.py) with
# the architect palette above. STL export is unaffected — DBG_* objects
# aren't included in build_*.py's name-targeted exports.
RETINT_DBG_OVERLAYS = True

# ─── World shader → parchment cream ────────────────────────────────────
world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
nt = world.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputWorld"); out.location = (240, 0)
bg  = nt.nodes.new("ShaderNodeBackground");  bg.location  = (0, 0)
bg.inputs["Color"].default_value    = PARCHMENT
bg.inputs["Strength"].default_value = 1.0
nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

# ─── Watercolor body materials (idempotent, prefix MA_ for cleanup) ────
def _matte(name, rgba):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    if p:
        p.inputs["Base Color"].default_value = rgba
        p.inputs["Roughness"].default_value  = BODY_ROUGH
        p.inputs["Metallic"].default_value   = BODY_METALLIC
    return m

mat_blue   = _matte("MA_Body_BlueGray",  BOTTOM_FILL)
mat_sage   = _matte("MA_Body_Sage",      TOP_FILL)
mat_bronze = _matte("MA_Decor_Bronze",   ACCENT_FILL)

def _find_half(suffix):
    o = bpy.data.objects.get(suffix)
    if o is not None:
        return o
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.lower().endswith(f"_{suffix.lower()}"):
            return o
    return None

def _assign(obj, mat):
    if obj is None: return
    obj.data.materials.clear()
    obj.data.materials.append(mat)

_assign(_find_half("Bottom"), mat_blue)
_assign(_find_half("Top"),    mat_sage)

# Decoration: explicit names + any *_spiral / *_decor / *_accent fallback
_decor_seen = set()
for n in ("RezzSpiral", "Spiral", "Decoration", "Decor"):
    o = bpy.data.objects.get(n)
    if o:
        _assign(o, mat_bronze); _decor_seen.add(o.name)
for o in bpy.data.objects:
    if o.type != 'MESH' or o.name in _decor_seen:
        continue
    if o.name.lower().endswith(("_spiral", "_decor", "_accent")):
        _assign(o, mat_bronze)

# ─── DBG_* overlay re-tint to architect palette (optional) ─────────────
if RETINT_DBG_OVERLAYS:
    palette_map = (
        ("DBG_Peg",        PEG_ARCHITECT,         "MA_Overlay_Peg"),
        ("DBG_PegHole",    PEG_HOLE_ARCHITECT,    "MA_Overlay_PegHole"),
        ("DBG_NFC",        NFC_ARCHITECT,         "MA_Overlay_NFC"),
        ("DBG_StringHole", STRING_HOLE_ARCHITECT, "MA_Overlay_StringHole"),
    )
    for o in bpy.data.objects:
        if not o.name.startswith("DBG_"):
            continue
        for prefix, rgba, mat_name in palette_map:
            if o.name.startswith(prefix):
                m = _matte(mat_name, rgba)
                o.data.materials.clear()
                o.data.materials.append(m)
                break

# ─── Grease Pencil scene line-art (verified Blender 5.0 settings) ──────
old_gp = bpy.data.objects.get("MA_LineArt")
if old_gp:
    bpy.data.objects.remove(old_gp, do_unlink=True)

bpy.ops.object.grease_pencil_add(type='LINEART_SCENE')
gp = bpy.context.active_object
gp.name = "MA_LineArt"
gp.location = (0, 0, 0)
gp.show_in_front = False                           # ← critical for Cycles render

mod = next((m for m in gp.modifiers if m.type == 'LINEART'), None)
if mod is not None:
    mod.source_type = 'SCENE'
    mod.use_intersection = True
    mod.use_contour      = True
    mod.use_crease       = True
    if hasattr(mod, 'use_edge_mark'): mod.use_edge_mark = True
    if hasattr(mod, 'use_material'):  mod.use_material  = False
    mod.radius  = INK_RADIUS                       # ← 'thickness' was removed in 5.0
    mod.opacity = 1.0
    if mod.target_material and hasattr(mod.target_material, 'grease_pencil'):
        gpm = mod.target_material.grease_pencil
        if gpm:
            gpm.color = INK_GRAPHITE
            gpm.show_stroke = True
            if hasattr(gpm, 'show_fill'):
                gpm.show_fill = False

# ─── Lights: warm key sun + optional faint cool fill ──────────────────
# Wipe any existing lights first so re-running doesn't pile them up
for o in [x for x in bpy.data.objects if x.type == 'LIGHT' and x.name.startswith("MA_")]:
    bpy.data.objects.remove(o, do_unlink=True)

key_data = bpy.data.lights.new("MA_Sun_Key", type='SUN')
key_data.energy = KEY_ENERGY
key_data.color  = KEY_COLOR
if hasattr(key_data, 'angle'): key_data.angle = math.radians(2.0)
key = bpy.data.objects.new("MA_Sun_Key", key_data)
bpy.context.scene.collection.objects.link(key)
key.location = KEY_LOC
key.rotation_euler = tuple(math.radians(d) for d in KEY_ROT_DEG)

if USE_FILL:
    fill_data = bpy.data.lights.new("MA_Sun_Fill", type='SUN')
    fill_data.energy = FILL_ENERGY
    fill_data.color  = FILL_COLOR
    if hasattr(fill_data, 'angle'): fill_data.angle = math.radians(20)
    fill = bpy.data.objects.new("MA_Sun_Fill", fill_data)
    bpy.context.scene.collection.objects.link(fill)
    fill.location = FILL_LOC
    fill.rotation_euler = tuple(math.radians(d) for d in FILL_ROT_DEG)

# ─── Camera rig (no animation — anim_*.py adds that) ──────────────────
def _ensure_empty(name, loc, etype='PLAIN_AXES'):
    o = bpy.data.objects.get(name)
    if not o:
        bpy.ops.object.empty_add(type=etype, location=loc)
        o = bpy.context.active_object; o.name = name
    o.location = loc
    return o

pivot  = _ensure_empty("CameraPivot",  PIVOT_LOC)
pivot.rotation_mode = 'XYZ'
pivot.rotation_euler = (0, 0, 0)
target = _ensure_empty("CameraTarget", TARGET_LOC, etype='SPHERE')
target.hide_viewport = True
target.hide_render   = True

cam_obj = bpy.data.objects.get("Camera")
if not cam_obj:
    cd = bpy.data.cameras.new("Camera")
    cam_obj = bpy.data.objects.new("Camera", cd)
    bpy.context.scene.collection.objects.link(cam_obj)
cam_obj.parent = pivot
cam_obj.location = CAM_BASE_LOC
cam_obj.rotation_euler = (0, 0, 0)
cam_obj.data.type = 'PERSP'
cam_obj.data.lens = CAM_LENS_MM
cam_obj.data.clip_start = 0.5
cam_obj.data.clip_end   = 500.0
for c in list(cam_obj.constraints):
    cam_obj.constraints.remove(c)
trk = cam_obj.constraints.new(type='TRACK_TO')
trk.target = target
trk.track_axis = 'TRACK_NEGATIVE_Z'
trk.up_axis    = 'UP_Y'
bpy.context.scene.camera = cam_obj

# ─── Render: Cycles + OptiX (RTX denoiser) ────────────────────────────
scn = bpy.context.scene
scn.render.engine = 'CYCLES'
scn.cycles.device = 'GPU'
if USE_OPTIX:
    try:
        cprefs = bpy.context.preferences.addons['cycles'].preferences
        for backend in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL'):
            try:
                cprefs.compute_device_type = backend
                cprefs.refresh_devices()
                break
            except (TypeError, AttributeError):
                continue
        for d in cprefs.devices:
            d.use = (d.type != 'CPU')
        scn.cycles.use_denoising = True
        scn.cycles.denoiser = 'OPTIX'
        scn.cycles.use_preview_denoising = True
        scn.cycles.preview_denoiser = 'OPTIX'
    except Exception as e:
        print(f"[architect_on] OptiX setup warning: {e}")
scn.cycles.samples = RENDER_SAMPLES
scn.cycles.preview_samples = max(24, RENDER_SAMPLES // 2)

# Viewport: camera + RENDERED so the live preview matches the render
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.region_3d.view_perspective = 'CAMERA'
                space.shading.type = 'RENDERED'
                space.overlay.show_floor    = False
                space.overlay.show_axis_x   = False
                space.overlay.show_axis_y   = False

# Force a frame re-eval so GP line-art draws strokes on first render
scn.frame_set(scn.frame_current)

print(f"[architect_on] applied. World={PARCHMENT[:3]}  ink_radius={INK_RADIUS}  "
      f"samples={RENDER_SAMPLES}")
print("[architect_on] Pair with anim_orbit.py / anim_locked_profile.py / anim_top_down.py / "
      "anim_macro_pull.py / anim_raking_light.py for camera movement.")
