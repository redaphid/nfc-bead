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

# bpy.ops.object.* operators require OBJECT mode. If the user (or a previous
# script) left an object in edit/sculpt/paint mode, ALL of our object ops fail
# their poll. Drop back to OBJECT mode unconditionally.
if bpy.context.mode != 'OBJECT':
    try:
        bpy.ops.object.mode_set(mode='OBJECT')
    except Exception:
        # If the active object is gone or can't change mode, force-clear it
        if bpy.context.view_layer.objects.active:
            bpy.context.view_layer.objects.active = None

# ─── Tunables (verified values) ─────────────────────────────────────────
PARCHMENT      = (0.93, 0.86, 0.72, 1.0)   # warm cream world
INK_GRAPHITE   = (0.08, 0.10, 0.14, 1.0)   # GP line-art ink
INK_RADIUS     = 0.05                      # Blender 5.0 GP modifier (NOT 'thickness')

# Canonical body colors — verified high-contrast palette in EEVEE.
# Each part is a different primary/secondary hue family so the three never
# blur together visually. Saturated enough to read as their hue under the
# warm key sun against the parchment world.
BOTTOM_FILL    = (0.16, 0.42, 0.88, 1.0)   # ultramarine blue   #296BE0
TOP_FILL       = (0.20, 0.68, 0.40, 1.0)   # emerald green      #33AD66
ACCENT_FILL    = (0.96, 0.38, 0.08, 1.0)   # vermilion / copper #F56115
BODY_ROUGH     = 0.85
BODY_METALLIC  = 0.0

# Architect-aesthetic highlight palette for any DBG_* overlays
# left in the scene by recolor.py. Same hue families as the CAD palette
# (yellow=peg, red=hole, magenta=NFC, orange=string) but tuned to read
# CLEARLY against parchment + warm light. Each is solid (with optional
# semi-transparency for the void-features) so they render visibly in
# Cycles instead of disappearing as wireframe-only.
PEG_ARCHITECT          = (0.95, 0.74, 0.18, 1.0)   # warm ochre (solid, opaque)
PEG_HOLE_ARCHITECT     = (0.78, 0.22, 0.20, 0.55)  # venetian red, semi-transparent
                                                   # (alpha < 1 so the hole reads as a "void" through the body)
NFC_ARCHITECT          = (0.78, 0.32, 0.62, 0.55) # bright rose, semi-transparent (void)
STRING_HOLE_ARCHITECT  = (0.95, 0.52, 0.18, 0.55) # bright rust, semi-transparent (void)

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

# Render: EEVEE always (faster than Cycles, more saturated/flat which suits
# the watercolor-ink architect aesthetic; no GPU/OptiX dependency)
RENDER_ENGINE  = "BLENDER_EEVEE"           # falls back if a newer Eevee variant is named
EEVEE_SAMPLES  = 32                         # TAA samples

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

# Bead-component naming convention (project-wide, NO legacy fallbacks):
#   "Bottom"     — bottom half (NFC pocket recess + pegs)
#   "Top"        — top half (peg holes; outer face may host the decoration)
#   "Decoration" — raised relief on top's outer face (spiral, emboss, etc.)
# Build scripts MUST produce these canonical names. If they're missing,
# this skill is a no-op for that part — that's a build-pipeline bug, not
# something to paper over with suffix matching.
def _assign(name, mat):
    obj = bpy.data.objects.get(name)
    if obj is None or obj.type != 'MESH':
        return
    obj.data.materials.clear()
    obj.data.materials.append(mat)

_assign("Bottom",     mat_blue)
_assign("Top",        mat_sage)
_assign("Decoration", mat_bronze)

# ─── DBG_* overlay re-tint to architect palette (optional) ─────────────
if RETINT_DBG_OVERLAYS:
    # Order matters: longer prefixes FIRST, so DBG_PegHole doesn't match
    # DBG_Peg (which is a prefix of it).
    palette_map = (
        ("DBG_PegHole",    PEG_HOLE_ARCHITECT,    "MA_Overlay_PegHole",    True ),  # void = alpha
        ("DBG_Peg",        PEG_ARCHITECT,         "MA_Overlay_Peg",        False),  # solid
        ("DBG_NFCPocket",  NFC_ARCHITECT,         "MA_Overlay_NFCPocket",  True ),  # void
        ("DBG_NFC",        NFC_ARCHITECT,         "MA_Overlay_NFC",        True ),  # void (legacy name)
        ("DBG_StringHole", STRING_HOLE_ARCHITECT, "MA_Overlay_StringHole", True ),  # void
    )

    def _make_overlay_mat(name, rgba, transparent):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        p = m.node_tree.nodes.get("Principled BSDF")
        if p:
            p.inputs["Base Color"].default_value = (rgba[0], rgba[1], rgba[2], 1.0)
            p.inputs["Roughness"].default_value  = 0.55
            p.inputs["Metallic"].default_value   = 0.0
            if "Alpha" in p.inputs:
                p.inputs["Alpha"].default_value = rgba[3]
        m.blend_method = 'BLEND' if transparent else 'OPAQUE'
        return m

    for o in bpy.data.objects:
        if not o.name.startswith("DBG_"):
            continue
        for prefix, rgba, mat_name, is_void in palette_map:
            if o.name.startswith(prefix):
                m = _make_overlay_mat(mat_name, rgba, is_void)
                o.data.materials.clear()
                o.data.materials.append(m)
                # Solid display so colors render in Cycles (wireframe mode is
                # easy to miss in render). Voids are alpha-blended so the body
                # geometry shows through them as a true "see-into-the-hole".
                o.display_type = 'TEXTURED' if is_void else 'TEXTURED'
                break

# ─── Grease Pencil scene line-art (verified Blender 5.0 settings) ──────
old_gp = bpy.data.objects.get("MA_LineArt")
if old_gp:
    bpy.data.objects.remove(old_gp, do_unlink=True)

# bpy.ops.object.grease_pencil_add poll requires a 3D viewport context.
# When this script is run via the BlenderMCP socket (or any non-UI handler)
# the default context's area may be wrong. Find a VIEW_3D area and use
# temp_override so the operator polls cleanly.
def _add_lineart_gp():
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            region = next((r for r in area.regions if r.type == 'WINDOW'), area.regions[-1])
            with bpy.context.temp_override(area=area, region=region):
                bpy.ops.object.grease_pencil_add(type='LINEART_SCENE')
            return bpy.context.active_object
    # Fallback: no 3D viewport in the current screen — try without override
    bpy.ops.object.grease_pencil_add(type='LINEART_SCENE')
    return bpy.context.active_object

gp = _add_lineart_gp()
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

# ─── Render: EEVEE (always — fast, saturated, suits ink-and-fill) ────
scn = bpy.context.scene
# Try the requested engine name first, then fall back to anything Eevee-ish.
_engine_tried = []
for engine in (RENDER_ENGINE, "BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    if engine in _engine_tried:
        continue
    _engine_tried.append(engine)
    try:
        scn.render.engine = engine
        break
    except (TypeError, AttributeError):
        continue
else:
    print(f"[architect_on] WARN: none of {_engine_tried} accepted; engine remains {scn.render.engine}")

# Eevee tunables (only the attributes that exist on this Blender version)
if hasattr(scn, "eevee"):
    if hasattr(scn.eevee, "taa_samples"):           scn.eevee.taa_samples = EEVEE_SAMPLES
    if hasattr(scn.eevee, "taa_render_samples"):    scn.eevee.taa_render_samples = EEVEE_SAMPLES * 2
    if hasattr(scn.eevee, "use_gtao"):              scn.eevee.use_gtao = True
    if hasattr(scn.eevee, "use_bloom"):             scn.eevee.use_bloom = False
    if hasattr(scn.eevee, "use_ssr"):               scn.eevee.use_ssr   = False

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

print(f"[architect_on] applied. engine={scn.render.engine}  world={PARCHMENT[:3]}  "
      f"ink_radius={INK_RADIUS}  eevee_taa={EEVEE_SAMPLES}")
print("[architect_on] Pair with anim_orbit.py / anim_locked_profile.py / anim_top_down.py / "
      "anim_macro_pull.py / anim_raking_light.py for camera movement.")
