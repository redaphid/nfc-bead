"""Macro pull-in: slow dolly + lens push from wide to close-up.

Camera glides from a wide establishing position toward a tight macro
shot of one specific feature on the bead, with an optical zoom (lens
length increases) along the way.

Default target focus: the +X half (top-body / decoration). Override
TARGET_X to focus on the bottom half instead.

Idempotent.

Requires `architect_on.py` first.
"""
import bpy

# ─── Tunables ─────────────────────────────────────────────────────────
DURATION_SEC   = 8            # how long the pull takes
FPS            = 24

# Wide start
START_LOC      = (0, -55, 18)
START_LENS     = 50

# Close end — defaults focus on the +X half (top body + spiral)
TARGET_X       = 18           # set to -18 to focus on bottom half
END_LOC        = (TARGET_X, -18, 6)
END_LENS       = 90

# Aim point follows the same X
TARGET_LOC_END = (TARGET_X, 0, 2.5)

# ─── Locate the rig ───────────────────────────────────────────────────
piv = bpy.data.objects.get("CameraPivot")
cam = bpy.data.objects.get("Camera")
tgt = bpy.data.objects.get("CameraTarget")
if not (piv and cam and tgt):
    raise RuntimeError("Camera rig missing — run architect_on.py first.")

# ─── Kill prior animation ─────────────────────────────────────────────
if piv.animation_data: piv.animation_data_clear()
if cam.animation_data: cam.animation_data_clear()
if tgt.animation_data: tgt.animation_data_clear()
piv.location = (0, 0, 0)
piv.rotation_euler = (0, 0, 0)

# ─── Frame range ──────────────────────────────────────────────────────
scn = bpy.context.scene
total = max(2, int(DURATION_SEC * FPS))
scn.render.fps = FPS
scn.frame_start = 1
scn.frame_end   = total

# ─── Keyframe camera location + lens, target location ────────────────
cam.location = START_LOC
cam.data.lens = START_LENS
tgt.location = (0, 0, 1.5)        # start aim point — wide center
cam.keyframe_insert(data_path="location",       frame=1)
cam.data.keyframe_insert(data_path="lens",      frame=1)
tgt.keyframe_insert(data_path="location",       frame=1)

cam.location = END_LOC
cam.data.lens = END_LENS
tgt.location = TARGET_LOC_END
cam.keyframe_insert(data_path="location",       frame=total)
cam.data.keyframe_insert(data_path="lens",      frame=total)
tgt.keyframe_insert(data_path="location",       frame=total)

# Default Bezier interpolation on all keyframes — gives a natural ease.
# Leave it; don't force LINEAR.

# ─── Start playback ───────────────────────────────────────────────────
scn.frame_current = 1
if not bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_play()

print(f"[anim_macro_pull] {DURATION_SEC}s pull from cam={START_LOC} lens={START_LENS} "
      f"to cam={END_LOC} lens={END_LENS}, target X={TARGET_X}.")
