"""Slow Z-orbit animation with X-wobble + optional dolly breath.

The canonical 'Westworld-tempo' animation: camera orbits the scene
on a vertical axis, sinusoidal vertical swing (wobble), and optional
in/out breathing dolly.

Stores its keyframes in a named Action that persists with the .blend:
  BeadAnim_orbit_pivot
  BeadAnim_orbit_cam   (only when DOLLY_BREATH is on)

Switch to a different stored anim with `anim_switch.py`. Re-running this
script clears + re-keys the named actions but leaves OTHER anims' actions
untouched.

Defaults are 'semi-slow' (90 s/rev) — gentler than the master_architect
canonical 4-min orbit.

Requires `architect_on.py` to have set up the camera rig.
"""
import bpy
import math

# ─── Tunables ─────────────────────────────────────────────────────────
ANIM_NAME       = "orbit"

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


# ─── Named-action helper (used by every anim_*.py) ────────────────────
def _named_action(obj, role: str):
    """Get or recreate a named Action for this anim+role; assign it to obj.

    Naming: BeadAnim_<anim>_<role>; use_fake_user=True so the action
    persists in the .blend even when not currently assigned. Re-running
    fully recreates the action (the layered-Action API in Blender 5.0
    doesn't expose a single fcurves list to clear, so a fresh data
    block is the simplest correct path).
    """
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


# ─── Frame range ──────────────────────────────────────────────────────
scn = bpy.context.scene
scn.frame_start = 1
scn.frame_end   = PERIOD
scn.render.fps  = FPS

# ─── Z-orbit (linear) ─────────────────────────────────────────────────
_named_action(piv, "pivot")
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
    """Walk both legacy `action.fcurves` and Blender 5.0 layered actions."""
    if hasattr(action, "fcurves") and action.fcurves:
        yield from action.fcurves
    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                if hasattr(strip, "channelbags"):
                    for cb in strip.channelbags:
                        for fc in cb.fcurves:
                            yield fc

if piv.animation_data and piv.animation_data.action:
    for fc in _iter_fcurves(piv.animation_data.action):
        kind = 'LINEAR' if (fc.array_index == 2 and fc.data_path == "rotation_euler") else 'BEZIER'
        for kp in fc.keyframe_points:
            kp.interpolation = kind

# ─── Dolly breath (optional, on cam.location.y) ───────────────────────
if DOLLY_BREATH:
    _named_action(cam, "cam")
    base_x, _, base_z = cam.location[:]
    y_lo, y_hi = DOLLY_RANGE
    for i in range(BREATH_SAMPLES + 1):
        f = 1 + int(i * PERIOD / BREATH_SAMPLES)
        cam.location = (base_x,
                        y_lo + (y_hi - y_lo) * 0.5 * (1 + math.sin(2 * math.pi * (i / BREATH_SAMPLES))),
                        base_z)
        cam.keyframe_insert(data_path="location", index=1, frame=f)
elif cam.animation_data:
    # Disable any prior orbit-cam action without losing other anims' actions
    cam.animation_data.action = None

# ─── Start playback ───────────────────────────────────────────────────
scn.frame_current = 1
if not bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_play()

print(f"[anim_orbit] action 'BeadAnim_{ANIM_NAME}_pivot' written ({PERIOD}f @ {FPS}fps = {PERIOD/FPS:.0f}s/rev)"
      + (f", wobble +-{WOBBLE_DEG}deg" if WOBBLE_DEG > 0 else "")
      + (", dolly breath on" if DOLLY_BREATH else ""))
