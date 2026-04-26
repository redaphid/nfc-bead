"""Slow Z-orbit animation with optional X-wobble and dolly breath.

The canonical 'Westworld-tempo' animation: camera orbits the scene
on a vertical axis, optional sinusoidal vertical swing (wobble), and
optional in/out breathing dolly.

Idempotent — clears any prior animation on `CameraPivot` and
`Camera`, then re-keys.

Tunables at the top. Defaults are 'semi-slow' (90s/rev) — gentler
than the master_architect canonical 4-min orbit.

Requires `architect_on.py` to have set up the camera rig
(CameraPivot + CameraTarget + Camera w/ TRACK_TO).
"""
import bpy, math

# ─── Tunables ─────────────────────────────────────────────────────────
PERIOD          = 2160        # frames per Z revolution (24 fps → 90 s)
FPS             = 24

WOBBLE_DEG      = 15.0        # ±deg sinusoidal swing of pivot.X (0 = no wobble)
WOBBLE_SAMPLES  = 36

DOLLY_BREATH    = False
DOLLY_RANGE     = (-58, -42)  # cam.location.y oscillation range
BREATH_SAMPLES  = 12

# ─── Locate the rig ───────────────────────────────────────────────────
piv = bpy.data.objects.get("CameraPivot")
cam = bpy.data.objects.get("Camera")
if not piv or not cam:
    raise RuntimeError("CameraPivot or Camera missing — run architect_on.py first.")

# ─── Wipe prior animation ─────────────────────────────────────────────
if piv.animation_data: piv.animation_data_clear()
if cam.animation_data: cam.animation_data_clear()

# ─── Frame range ──────────────────────────────────────────────────────
scn = bpy.context.scene
scn.frame_start = 1
scn.frame_end   = PERIOD
scn.render.fps  = FPS

# ─── Z-orbit (linear) ─────────────────────────────────────────────────
piv.rotation_euler = (0, 0, 0)
piv.keyframe_insert(data_path="rotation_euler", index=2, frame=1)
piv.rotation_euler = (0, 0, math.radians(360))
piv.keyframe_insert(data_path="rotation_euler", index=2, frame=PERIOD + 1)

# ─── X-wobble (bezier) ────────────────────────────────────────────────
if WOBBLE_DEG > 0:
    for i in range(WOBBLE_SAMPLES + 1):
        f = 1 + int(i * PERIOD / WOBBLE_SAMPLES)
        piv.rotation_euler = (
            math.radians(WOBBLE_DEG * math.sin(2 * math.pi * (i / WOBBLE_SAMPLES))),
            0, 0)
        piv.keyframe_insert(data_path="rotation_euler", index=0, frame=f)

# ─── Set interpolation: LINEAR for Z, BEZIER for wobble ───────────────
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

if piv.animation_data and piv.animation_data.action:
    for fc in _iter_fcurves(piv.animation_data.action):
        kind = 'LINEAR' if (fc.array_index == 2 and fc.data_path == "rotation_euler") else 'BEZIER'
        for kp in fc.keyframe_points:
            kp.interpolation = kind

# ─── Dolly breath (optional, on the camera object's own Y) ────────────
if DOLLY_BREATH:
    base_x, _, base_z = cam.location[:]
    y_lo, y_hi = DOLLY_RANGE
    for i in range(BREATH_SAMPLES + 1):
        f = 1 + int(i * PERIOD / BREATH_SAMPLES)
        cam.location = (base_x,
                        y_lo + (y_hi - y_lo) * 0.5 * (1 + math.sin(2 * math.pi * (i / BREATH_SAMPLES))),
                        base_z)
        cam.keyframe_insert(data_path="location", index=1, frame=f)

# ─── Start playback ───────────────────────────────────────────────────
scn.frame_current = 1
if not bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_play()

print(f"[anim_orbit] Z-orbit {PERIOD}f @ {FPS}fps = {PERIOD/FPS:.0f}s/rev"
      + (f", wobble +-{WOBBLE_DEG}deg ({WOBBLE_SAMPLES} samples)" if WOBBLE_DEG > 0 else "")
      + (f", dolly breath y={DOLLY_RANGE}" if DOLLY_BREATH else ""))
