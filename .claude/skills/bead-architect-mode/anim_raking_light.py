"""Raking light: camera holds, the warm key sun rotates around the scene.

Stores its keyframes in:
  BeadAnim_raking_light_sun

Camera and pivot get their actions cleared (so they hold their current
pose) but other anims' actions remain untouched in the .blend.

Pairs especially well with `anim_locked_profile` — locked silhouette
while highlights and shadows shift across the form.

Requires `architect_on.py` first (creates `MA_Sun_Key`).
"""
import bpy
import math

# ─── Tunables ─────────────────────────────────────────────────────────
ANIM_NAME       = "raking_light"

PERIOD          = 1440        # frames per full sweep (24 fps → 60 s)
FPS             = 24
SUN_RADIUS      = 25
SUN_ALTITUDE    = 22
SUN_TILT_DEG    = 55
SAMPLES         = 36

# ─── Locate the key sun ───────────────────────────────────────────────
sun = bpy.data.objects.get("MA_Sun_Key")
if sun is None:
    raise RuntimeError("MA_Sun_Key not found — run architect_on.py first.")


# ─── Named-action helper ──────────────────────────────────────────────
def _named_action(obj, role: str):
    name = f"BeadAnim_{ANIM_NAME}_{role}"
    old = bpy.data.actions.get(name)
    if old is not None:
        bpy.data.actions.remove(old)
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    if not obj.animation_data:
        obj.animation_data_create()
    obj.animation_data.action = action
    return action


_named_action(sun, "sun")

# Other rig objects: drop their action assignments without affecting their
# stored other-anim actions in bpy.data.actions.
for o_name in ("CameraPivot", "Camera", "CameraTarget"):
    o = bpy.data.objects.get(o_name)
    if o and o.animation_data:
        o.animation_data.action = None

# ─── Frame range ──────────────────────────────────────────────────────
scn = bpy.context.scene
scn.render.fps  = FPS
scn.frame_start = 1
scn.frame_end   = PERIOD

# ─── Keyframe sun.location around a circle, sun rotation tracking inward ──
for i in range(SAMPLES + 1):
    f = 1 + int(i * PERIOD / SAMPLES)
    theta = 2 * math.pi * (i / SAMPLES)
    sun.location = (SUN_RADIUS * math.cos(theta), SUN_RADIUS * math.sin(theta), SUN_ALTITUDE)
    az = math.atan2(-sun.location.y, -sun.location.x)
    sun.rotation_euler = (math.radians(SUN_TILT_DEG), 0, az + math.pi / 2)
    sun.keyframe_insert(data_path="location",       frame=f)
    sun.keyframe_insert(data_path="rotation_euler", frame=f)

# Linear interp so the sweep is constant speed
def _iter_fcurves(action):
    if hasattr(action, "fcurves") and action.fcurves:
        yield from action.fcurves
    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                if hasattr(strip, "channelbags"):
                    for cb in strip.channelbags:
                        for fc in cb.fcurves:
                            yield fc

if sun.animation_data and sun.animation_data.action:
    for fc in _iter_fcurves(sun.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

scn.frame_current = 1
if not bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_play()

print(f"[anim_raking_light] action 'BeadAnim_{ANIM_NAME}_sun' written; "
      f"{PERIOD}f @ {FPS}fps = {PERIOD / FPS:.0f}s/sweep, "
      f"radius={SUN_RADIUS} altitude={SUN_ALTITUDE} tilt={SUN_TILT_DEG}deg")
