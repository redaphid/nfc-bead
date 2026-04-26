"""Master-architect color-illustration look for the Blender canvas.

Goal: the canvas reads as a hand-drafted architectural presentation
plate. Eggshell paper, distinct-but-tasteful colored fills per element
(taking cues from the recolor.py CAD palette — bottom-half cool blue-
gray, top-half sage, pegs warm ochre, etc. — but rendered as flat
watercolor washes), strong dark ink edges traced over every silhouette
and crease via Grease Pencil Line Art. Wireframe-forward: the lines do
most of the visual work; the colored fills are quiet washes underneath.

Camera work runs to a Westworld-intro tempo — slow, deliberate, locked
perspectives that hold for ten or fifteen seconds before drifting on.
The aesthetic is hand-drafted illustration; the camera is precision
machinery moving over it.

Layered on top of an existing scene with `Bottom`, `Top` (and optional
`*_Bottom` / `*_Top`) halves. Idempotent: re-running rebuilds the
Grease Pencil line-art object cleanly, replaces the world shader, and
re-paints body materials.

Usage:
    exec(open(r"<repo>/.claude/skills/bead-debug-colors/master_architect.py").read())

Requires Blender 4.x+ for Grease Pencil v3 line art (verified on 5.0.1).
"""
import bpy, math

# ─── Tunables ─────────────────────────────────────────────────────────
PERIOD          = 6000       # frames per Z revolution (24 fps → 250 s)
WOBBLE_DEG      = 35.0       # gentler vertical swing than blueprint mode
WOBBLE_SAMPLES  = 36
DOLLY_BREATH    = True
DOLLY_RANGE     = (-58, -42)

PIVOT_LOC       = (0, 0, 0)
TARGET_LOC      = (0, 0, 1.5)
CAM_BASE_LOC    = (0, -50, 18)
CAM_LENS_MM     = 50

# Architect color-illustration palette.
#
# Each element gets a distinct but tasteful colored wash — the recolor.py
# CAD logic (cool blue-gray for the host body half, sage for its mate,
# warm bronze for raised decorations) translated into flat, low-saturation
# watercolor fills that sit politely under heavy ink edges. Strictly NOT
# monochrome: the eye should read "bottom vs top vs decoration" instantly,
# but the colors are gentle enough that the dark ink lines remain the
# composition.
PAPER          = (0.93, 0.86, 0.72, 1.0)   # world background — warm cream parchment
INK_COLOR      = (0.08, 0.10, 0.14, 1.0)   # graphite, faintly cool
BOTTOM_FILL    = (0.62, 0.74, 0.82, 1.0)   # blueprint blue-gray wash
TOP_FILL       = (0.70, 0.80, 0.74, 1.0)   # sage wash (different from bottom)
ACCENT_FILL    = (0.85, 0.62, 0.32, 1.0)   # warm bronze (raised decorations)
GRID_MINOR     = (0.55, 0.66, 0.78, 1.0)   # faint blue-gray graph-paper minor line
GRID_MAJOR     = (0.36, 0.48, 0.62, 1.0)   # darker major line every 5 units
GRID_MINOR_OPACITY = 0.35                  # how strongly minor lines tint the paper
GRID_MAJOR_OPACITY = 0.55
GRID_UNIT_MM       = 1.0                   # one minor square = 1 mm of bead world
GRID_MAJOR_EVERY   = 5                     # major line every 5 minor squares

INK_THICKNESS  = 25      # GP line points (modifier wants int, not float)
INK_OPACITY    = 1.0

WORLD_STRENGTH = 1.0

RENDER_ENGINE   = 'CYCLES'
PREVIEW_SAMPLES = 24

# ─── World shader → eggshell paper ───────────────────────────────────
world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
nt = world.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputWorld"); out.location = (240, 0)
bg  = nt.nodes.new("ShaderNodeBackground");  bg.location  = (0, 0)
bg.inputs["Color"].default_value    = PAPER
bg.inputs["Strength"].default_value = WORLD_STRENGTH
nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

# ─── Cycles + OptiX (RTX denoiser) for the live raytraced viewport ──
if RENDER_ENGINE:
    scene = bpy.context.scene
    scene.render.engine = RENDER_ENGINE
    if RENDER_ENGINE == 'CYCLES':
        scene.cycles.device = 'GPU'
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
        scene.cycles.preview_samples = PREVIEW_SAMPLES
        scene.cycles.use_preview_denoising = True
        scene.cycles.preview_denoiser = 'OPTIX'

# ─── Body materials → matte cream parchment fill ─────────────────────
def _matte_repaint(obj, rgba, name):
    if obj is None:
        return
    obj.data.materials.clear()
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value  = 0.85
    bsdf.inputs["Metallic"].default_value   = 0.0
    bsdf.inputs["Alpha"].default_value      = 1.0
    m.blend_method = 'OPAQUE'
    obj.data.materials.append(m)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_flat()

def _find_half(suffix):
    o = bpy.data.objects.get(suffix)
    if o is not None:
        return o
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.lower().endswith(f"_{suffix.lower()}"):
            return o
    return None

bottom = _find_half("Bottom")
top    = _find_half("Top")
_matte_repaint(bottom, BOTTOM_FILL, "MA_Body_BlueGray_B")
_matte_repaint(top,    TOP_FILL,    "MA_Body_Sage_T")

# Optional decoration (rezz spiral and friends) gets the warm bronze accent
for n in ("RezzSpiral", "Spiral", "Decoration", "Decor"):
    o = bpy.data.objects.get(n)
    if o:
        _matte_repaint(o, ACCENT_FILL, "MA_Accent_Bronze")

# ─── Grease Pencil Line Art — crisp ink edges over all scene meshes ──
old = bpy.data.objects.get("MA_LineArt")
if old:
    bpy.data.objects.remove(old, do_unlink=True)

bpy.ops.object.grease_pencil_add(type='LINEART_SCENE')
gp = bpy.context.active_object
gp.name = "MA_LineArt"

# Make the strokes draw on top of everything (no stroke depth offset weirdness)
gp.show_in_front = True
gp.location = (0, 0, 0)

# Configure the auto-created LINEART modifier
lineart_mod = next((m for m in gp.modifiers if m.type == 'LINEART'), None)
if lineart_mod is not None:
    lineart_mod.source_type = 'SCENE'
    lineart_mod.use_intersection = True
    lineart_mod.use_crease       = True
    lineart_mod.use_contour      = True
    if hasattr(lineart_mod, 'use_edge_mark'):
        lineart_mod.use_edge_mark = True
    if hasattr(lineart_mod, 'use_material'):
        lineart_mod.use_material = False
    # Make occluded lines softer (hidden-line)
    if hasattr(lineart_mod, 'use_overlap_edge_type'):
        lineart_mod.use_overlap_edge_type = True
    # The thickness multiplier shows up via the GP material; modifier just sets base
    if hasattr(lineart_mod, 'thickness'):
        lineart_mod.thickness = int(INK_THICKNESS)
    if hasattr(lineart_mod, 'opacity'):
        lineart_mod.opacity = INK_OPACITY

# Ink color — set on the GP material that was auto-created with the object
if gp.data.materials:
    mat = gp.data.materials[0]
    if hasattr(mat, 'grease_pencil') and mat.grease_pencil:
        gp_mat = mat.grease_pencil
        gp_mat.color = INK_COLOR
        gp_mat.show_stroke = True
        if hasattr(gp_mat, 'show_fill'):
            gp_mat.show_fill = False

# ─── Camera infrastructure (idempotent) ──────────────────────────────
def _ensure(name, factory):
    o = bpy.data.objects.get(name)
    return o if o else factory()

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

# Warm "drafting lamp" light from above, slightly off-axis
sun = _ensure("Sun", lambda: (
    bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", type='SUN')),
))
if not sun.users_collection:
    bpy.context.scene.collection.objects.link(sun)
sun.location = (8, -6, 30)
sun.data.energy = 3.0
sun.data.color  = (1.0, 0.92, 0.78)   # tungsten warm

# ─── Animation: slow Z-orbit + gentle X-wobble + dolly breath ───────
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

# ─── Viewport: camera + RENDERED so we see Cycles + ink on top ──────
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.region_3d.view_perspective = 'CAMERA'
                space.shading.type = 'RENDERED'
                space.shading.use_scene_world_render  = True
                space.shading.use_scene_lights_render = True
                space.overlay.show_overlays = True
                space.overlay.show_floor    = False
                space.overlay.show_axis_x   = False
                space.overlay.show_axis_y   = False

# Jump to a frame partway through the orbit so the wobble has lifted
scene.frame_current = max(1, PERIOD // 8)
if not bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_play()

print(f"[master_architect] parchment={PARCHMENT[:3]}  ink={INK_COLOR[:3]}  "
      f"orbit={PERIOD}f  wobble±{WOBBLE_DEG}°  jumped to frame {scene.frame_current}")
