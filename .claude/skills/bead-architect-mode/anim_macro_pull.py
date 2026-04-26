"""Macro pull: ping-pong dolly + lens-zoom (wide ↔ close-up).

Stores its keyframes in named actions:
  BeadAnim_macro_pull_cam    (cam.location + cam.data.lens)
  BeadAnim_macro_pull_tgt    (target.location)

Switch with `anim_switch.py`.

Loop is a PING-PONG: wide → close → wide. Total cycle = 2 * PULL_SEC.
Bezier ease at both extremes; the wrap from frame_end back to 1 is
seamless because the start and end frames hold the same wide pose.

Requires `architect_on.py` first.
"""
import bpy

# ─── Tunables ─────────────────────────────────────────────────────────
ANIM_NAME      = "macro_pull"

PULL_SEC       = 6            # one direction (full cycle = 12 s)
FPS            = 24

# Wide start (also wide return)
START_LOC      = (0, -55, 18)
START_LENS     = 50

# Close end — defaults focus on the +X half (Top + Decoration)
TARGET_X       = 18           # set to -18 to focus on the bottom half
END_LOC        = (TARGET_X, -18, 6)
END_LENS       = 90

TARGET_LOC_END   = (TARGET_X, 0, 2.5)
TARGET_LOC_START = (0, 0, 1.5)

# ─── Locate rig ───────────────────────────────────────────────────────
cam = bpy.data.objects.get("Camera")
tgt = bpy.data.objects.get("CameraTarget")
piv = bpy.data.objects.get("CameraPivot")
if not (cam and tgt and piv):
    raise RuntimeError("Camera rig missing — run architect_on.py first.")


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


if piv.animation_data:
    piv.animation_data.action = None
piv.location = (0, 0, 0)
piv.rotation_euler = (0, 0, 0)

_named_action(cam, "cam")
_named_action(tgt, "tgt")

# ─── Frame range ──────────────────────────────────────────────────────
scn = bpy.context.scene
half = max(2, int(PULL_SEC * FPS))
end_frame = 2 * half + 1
scn.render.fps  = FPS
scn.frame_start = 1
scn.frame_end   = 2 * half

# ─── Keyframe ─────────────────────────────────────────────────────────
def _key_wide(f):
    cam.location  = START_LOC
    cam.data.lens = START_LENS
    tgt.location  = TARGET_LOC_START
    cam.keyframe_insert(data_path="location",  frame=f)
    cam.data.keyframe_insert(data_path="lens", frame=f)
    tgt.keyframe_insert(data_path="location",  frame=f)

def _key_close(f):
    cam.location  = END_LOC
    cam.data.lens = END_LENS
    tgt.location  = TARGET_LOC_END
    cam.keyframe_insert(data_path="location",  frame=f)
    cam.data.keyframe_insert(data_path="lens", frame=f)
    tgt.keyframe_insert(data_path="location",  frame=f)

_key_wide(1)
_key_close(half + 1)
_key_wide(end_frame)   # past frame_end → seamless wrap

scn.frame_current = 1
if not bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_play()

print(f"[anim_macro_pull] actions 'BeadAnim_{ANIM_NAME}_cam' + '_tgt' written; "
      f"ping-pong {PULL_SEC}s each way ({2 * PULL_SEC}s cycle); "
      f"wide {START_LOC} lens {START_LENS} <-> close {END_LOC} lens {END_LENS}, target X={TARGET_X}.")
