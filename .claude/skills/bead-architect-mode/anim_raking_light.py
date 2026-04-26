"""Raking light: camera holds, the warm key sun rotates around the scene.

Strong stylistic move — the bead stays motionless while the light
slowly sweeps around it, so highlights and cast shadows shift across
the form. Pairs especially well with anim_locked_profile.py (locked
camera + moving light = pure 'Westworld machined object' tempo).

Idempotent.

Requires `architect_on.py` first (which creates `MA_Sun_Key`).
"""
import bpy, math

# ─── Tunables ─────────────────────────────────────────────────────────
PERIOD          = 1440        # frames per full sweep (24 fps → 60 s)
FPS             = 24
SUN_RADIUS      = 25          # how far out the sun orbits horizontally
SUN_ALTITUDE    = 22          # height above origin
SUN_TILT_DEG    = 55          # constant downward tilt

# ─── Locate the key sun ───────────────────────────────────────────────
sun = bpy.data.objects.get("MA_Sun_Key")
if sun is None:
    raise RuntimeError("MA_Sun_Key not found — run architect_on.py first.")

# ─── Kill prior anim on the sun ───────────────────────────────────────
if sun.animation_data:
    sun.animation_data_clear()

# ─── Frame range ──────────────────────────────────────────────────────
scn = bpy.context.scene
scn.render.fps = FPS
scn.frame_start = 1
scn.frame_end   = PERIOD

# ─── Keyframe sun.location around a circle, sun rotation tracking inward ──
SAMPLES = 36
for i in range(SAMPLES + 1):
    f = 1 + int(i * PERIOD / SAMPLES)
    theta = 2 * math.pi * (i / SAMPLES)
    sun.location = (SUN_RADIUS * math.cos(theta), SUN_RADIUS * math.sin(theta), SUN_ALTITUDE)
    # Sun's beam direction: point toward the origin from current position
    # Convert location to a tilt+azimuth so it shines inward & downward
    # azimuth = atan2(-y, -x); we want the sun's local Z to face inward
    az = math.atan2(-sun.location.y, -sun.location.x)
    sun.rotation_euler = (math.radians(SUN_TILT_DEG), 0, az + math.pi/2)
    sun.keyframe_insert(data_path="location",       frame=f)
    sun.keyframe_insert(data_path="rotation_euler", frame=f)

# Linear interp so the sweep is constant speed
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

if sun.animation_data and sun.animation_data.action:
    for fc in _iter_fcurves(sun.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

# ─── Play ─────────────────────────────────────────────────────────────
scn.frame_current = 1
if not bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_play()

print(f"[anim_raking_light] {PERIOD}f @ {FPS}fps = {PERIOD/FPS:.0f}s/sweep, "
      f"radius={SUN_RADIUS} altitude={SUN_ALTITUDE} tilt={SUN_TILT_DEG}deg")
