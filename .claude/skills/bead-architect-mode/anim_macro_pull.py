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
# Loop is a PING-PONG: wide → close → wide. Total cycle = 2 * PULL_SEC.
# Bezier interpolation gives natural ease-in/ease-out at both ends.
PULL_SEC       = 6            # one direction of the pull (so cycle = 12 s)
FPS            = 24

# Wide start (also wide return)
START_LOC      = (0, -55, 18)
START_LENS     = 50

# Close end — defaults focus on the +X half (top body + spiral)
TARGET_X       = 18           # set to -18 to focus on bottom half
END_LOC        = (TARGET_X, -18, 6)
END_LENS       = 90

# Aim point at the close end follows the same X
TARGET_LOC_END = (TARGET_X, 0, 2.5)
TARGET_LOC_START = (0, 0, 1.5)

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
# Ping-pong: wide at frame 1, close at frame mid, wide again at frame end.
# scn.frame_end = end - 1 so playback wraps cleanly without showing the
# duplicate "wide" keyframe twice in a row.
scn = bpy.context.scene
half = max(2, int(PULL_SEC * FPS))
end_frame = 2 * half + 1
scn.render.fps = FPS
scn.frame_start = 1
scn.frame_end   = 2 * half        # last visible frame is just before the duplicate

# ─── Keyframe camera location + lens, target location ────────────────
def _key_wide(f):
    cam.location  = START_LOC
    cam.data.lens = START_LENS
    tgt.location  = TARGET_LOC_START
    cam.keyframe_insert(data_path="location",      frame=f)
    cam.data.keyframe_insert(data_path="lens",     frame=f)
    tgt.keyframe_insert(data_path="location",      frame=f)

def _key_close(f):
    cam.location  = END_LOC
    cam.data.lens = END_LENS
    tgt.location  = TARGET_LOC_END
    cam.keyframe_insert(data_path="location",      frame=f)
    cam.data.keyframe_insert(data_path="lens",     frame=f)
    tgt.keyframe_insert(data_path="location",      frame=f)

_key_wide(1)              # frame 1: wide
_key_close(half + 1)      # midpoint: full close-up
_key_wide(end_frame)      # final keyframe (just past frame_end): wide again
                          # → playback at frame_end interpolates almost-back-to-wide
                          #   and wraps to frame 1 (exactly wide) seamlessly

# Default Bezier interpolation on all keyframes — gives a natural ease at
# both ends and a smooth peak at the close-up. Don't force LINEAR.

# ─── Start playback ───────────────────────────────────────────────────
scn.frame_current = 1
if not bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_play()

print(f"[anim_macro_pull] ping-pong, {PULL_SEC}s each way ({2*PULL_SEC}s cycle); "
      f"wide {START_LOC} lens {START_LENS} <-> close {END_LOC} lens {END_LENS}, "
      f"target X={TARGET_X}.")
