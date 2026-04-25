"""Cinematic blueprint mode for live demos.

Turns the Blender canvas into a slowly-rotating drafting / blueprint diagram:

  - World background: deep blueprint blue (no environment HDRi noise)
  - Three printable bodies (Bottom, Top, decoration) repainted in
    semi-transparent blueprint tones so internal features show through
  - DBG_* widgets (run `recolor.py` first) keep their full opacity:
    solid YELLOW pegs and wireframe RED/MAGENTA/ORANGE voids pop against
    the glass bodies
  - MATERIAL preview viewport so alpha actually composites
  - Slow orbit camera (default ~4 min / revolution at 24 fps)
    + sine-wave vertical wobble (±55°)
    + optional gentle dolly-breath on camera distance

Usage (typical sequence):

    # 1) Apply the CAD palette + overlays
    exec(open(r"<repo>/.claude/skills/bead-debug-colors/recolor.py").read())
    # 2) Wrap the canvas in cinematic blueprint mode
    exec(open(r"<repo>/.claude/skills/bead-debug-colors/blueprint.py").read())

Idempotent: re-running clears the prior orbit keyframes, replaces the
background, re-paints the bodies. Switching back to the production look:
run `restore.py` (it leaves the blueprint background; clear it manually
or re-open the .blend if you want the default world back).

Tunable at the top of the file. The module-style globals make it cheap
to copy/paste this script into `execute_blender_code` and adjust one
value before re-running.
"""
import bpy, math

# ─── Tunables ─────────────────────────────────────────────────────────
PERIOD          = 6000        # frames per full Z revolution (24 fps → 250 s)
WOBBLE_DEG      = 55.0        # ± vertical sine swing on X rotation
WOBBLE_SAMPLES  = 36          # samples per cycle for the wobble
DOLLY_BREATH    = True        # slow zoom in/out on cam.location.y
DOLLY_RANGE     = (-58, -42)  # min/max y distance during the breath
BODY_ALPHA      = 0.30        # 0 = invisible, 1 = opaque; 0.30 reads as glass
PIVOT_LOC       = (0, 0, 0)
TARGET_LOC      = (0, 0, 1.5)
CAM_BASE_LOC    = (0, -50, 18)
CAM_LENS_MM     = 50

# Render engine: Cycles + OptiX is the right call for a 4090 — RT cores
# accelerate primary + bounce rays AND the OptiX denoiser, giving a
# clean responsive viewport during slow orbits. Eevee Next is faster
# but won't show the glass-through-glass refraction the blueprint look
# leans on. Set to None to leave the existing engine alone.
RENDER_ENGINE   = 'CYCLES'    # 'CYCLES' | 'BLENDER_EEVEE' (Eevee Next on 4.2+) | None
PREVIEW_SAMPLES = 32          # quick noise floor; raise for stills

# Blueprint blue — classical drafting paper. HSV ~210°/72%/35%.
BLUEPRINT_BG    = (0.06, 0.18, 0.34, 1.0)
# Slightly darker for the world AO/ambient so widgets read sharp
WORLD_STRENGTH  = 0.85

# ─── World background → solid blueprint blue ──────────────────────────
world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
nt = world.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputWorld"); out.location = (240, 0)
bg  = nt.nodes.new("ShaderNodeBackground");  bg.location  = (0, 0)
bg.inputs["Color"].default_value    = BLUEPRINT_BG
bg.inputs["Strength"].default_value = WORLD_STRENGTH
nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

# ─── Body materials → glass-tinted blueprint ───────────────────────────
def _glass_repaint(obj, rgba, name):
    if obj is None or not obj.data.materials:
        return
    m = obj.data.materials[0]
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        return
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value  = 0.55
    bsdf.inputs["Metallic"].default_value   = 0.0
    bsdf.inputs["Alpha"].default_value      = BODY_ALPHA
    m.blend_method = 'BLEND'
    if hasattr(m, 'surface_render_method'):
        m.surface_render_method = 'BLENDED'
    m.name = name

def _find_half(suffix):
    """Find an object named exactly `suffix` or anything ending in `_<suffix>`."""
    o = bpy.data.objects.get(suffix)
    if o is not None:
        return o
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.lower().endswith(f"_{suffix.lower()}"):
            return o
    return None

_glass_repaint(_find_half("Bottom"), (0.55, 0.68, 0.78, 1.0), "BP_Bottom_Glass")
_glass_repaint(_find_half("Top"),    (0.62, 0.74, 0.70, 1.0), "BP_Top_Glass")

# ─── Camera infrastructure (idempotent) ────────────────────────────────
def _ensure(name, factory):
    o = bpy.data.objects.get(name)
    if o is None:
        o = factory()
    return o

def _make_pivot():
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=PIVOT_LOC)
    o = bpy.context.active_object; o.name = "CameraPivot"
    o.rotation_mode = 'XYZ'
    return o

def _make_target():
    bpy.ops.object.empty_add(type='SPHERE', location=TARGET_LOC, radius=0.5)
    o = bpy.context.active_object; o.name = "CameraTarget"
    o.hide_viewport = True; o.hide_render = True
    return o

def _make_camera():
    cd = bpy.data.cameras.new("Camera")
    o = bpy.data.objects.new("Camera", cd)
    bpy.context.scene.collection.objects.link(o)
    return o

pivot  = _ensure("CameraPivot",  _make_pivot)
target = _ensure("CameraTarget", _make_target)
cam    = _ensure("Camera",       _make_camera)

pivot.location  = PIVOT_LOC
target.location = TARGET_LOC
cam.parent      = pivot
cam.location    = CAM_BASE_LOC
cam.rotation_euler = (0, 0, 0)
cam.data.type      = 'PERSP'
cam.data.lens      = CAM_LENS_MM
cam.data.clip_start = 0.5
cam.data.clip_end   = 500.0
for c in list(cam.constraints):
    cam.constraints.remove(c)
con = cam.constraints.new(type='TRACK_TO')
con.target = target
con.track_axis = 'TRACK_NEGATIVE_Z'
con.up_axis    = 'UP_Y'
bpy.context.scene.camera = cam

# Sun — soft top-down for clean shading on the glass bodies
sun = _ensure("Sun", lambda: (
    bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", type='SUN')),
))
if not sun.users_collection:
    bpy.context.scene.collection.objects.link(sun)
sun.location = (0, 0, 30)
sun.data.energy = 2.5

# ─── Animation: slow Z-orbit + X-wobble + optional dolly breath ───────
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end   = PERIOD
scene.render.fps  = 24
scene.use_preview_range = False

if pivot.animation_data:
    pivot.animation_data_clear()

pivot.rotation_euler = (0, 0, 0)
pivot.keyframe_insert(data_path="rotation_euler", index=2, frame=1)
pivot.rotation_euler = (0, 0, math.radians(360))
pivot.keyframe_insert(data_path="rotation_euler", index=2, frame=PERIOD + 1)

for i in range(WOBBLE_SAMPLES + 1):
    f = 1 + int(i * PERIOD / WOBBLE_SAMPLES)
    pivot.rotation_euler = (math.radians(WOBBLE_DEG * math.sin(2 * math.pi * (i / WOBBLE_SAMPLES))), 0, 0)
    pivot.keyframe_insert(data_path="rotation_euler", index=0, frame=f)

if DOLLY_BREATH:
    if cam.animation_data:
        cam.animation_data_clear()
    y_lo, y_hi = DOLLY_RANGE
    BREATH = 12
    for i in range(BREATH + 1):
        f = 1 + int(i * PERIOD / BREATH)
        cam.location = (CAM_BASE_LOC[0],
                        y_lo + (y_hi - y_lo) * 0.5 * (1 + math.sin(2 * math.pi * (i / BREATH))),
                        CAM_BASE_LOC[2])
        cam.keyframe_insert(data_path="location", index=1, frame=f)

# Linear interp on the Z spin so it's a constant-rate rotation
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
    kind = 'LINEAR' if (fc.array_index == 2 and fc.data_path == "rotation_euler") else 'BEZIER'
    for kp in fc.keyframe_points:
        kp.interpolation = kind

# ─── Viewport: camera + MATERIAL preview using SCENE world (so the
#     blueprint-blue World shader actually shows up in the viewport
#     instead of the default studio HDRi) ────────────────────────────
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.region_3d.view_perspective = 'CAMERA'
                space.shading.type = 'MATERIAL'
                space.shading.use_scene_world  = True   # show blueprint bg
                space.shading.use_scene_lights = True   # use Sun, not built-in
                space.shading.show_xray = False
                space.shading.studiolight_background_alpha = 1.0
                space.overlay.show_overlays = True
                space.overlay.show_floor   = False
                space.overlay.show_axis_x  = False
                space.overlay.show_axis_y  = False

# Start playing
scene.frame_current = 1
if not bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_play()

print(f"[blueprint] orbit period {PERIOD}f ({PERIOD/24:.0f}s/rev), wobble ±{WOBBLE_DEG}°, "
      f"dolly_breath={DOLLY_BREATH}, body_alpha={BODY_ALPHA}, bg={BLUEPRINT_BG[:3]}")
