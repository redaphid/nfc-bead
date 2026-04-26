"""Top-down 'blueprint plate' shot: camera locked overhead, no motion.

Stores the static pose in named actions:
  BeadAnim_top_down_cam
  BeadAnim_top_down_tgt

Requires `architect_on.py` first.
"""
import bpy

# ─── Tunables ─────────────────────────────────────────────────────────
ANIM_NAME       = "top_down"

CAM_Z           = 50
CAM_LENS_MM     = 60
TARGET          = (0, 0.001, 0)
# ↑ tiny non-zero Y on the target avoids a degenerate TRACK_TO 'up' axis when
#   the camera looks straight down (UP_Y becomes ambiguous co-linear with -Z).

# ─── Locate rig ───────────────────────────────────────────────────────
piv = bpy.data.objects.get("CameraPivot")
cam = bpy.data.objects.get("Camera")
tgt = bpy.data.objects.get("CameraTarget")
if not (piv and cam and tgt):
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

cam.location  = (0, 0, CAM_Z)
cam.data.lens = CAM_LENS_MM
tgt.location  = TARGET
cam.keyframe_insert(data_path="location",  frame=1)
cam.data.keyframe_insert(data_path="lens", frame=1)
tgt.keyframe_insert(data_path="location",  frame=1)

scn = bpy.context.scene
scn.frame_start = 1
scn.frame_end   = 1
scn.frame_current = 1
if bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_play()

print(f"[anim_top_down] actions 'BeadAnim_{ANIM_NAME}_cam' + '_tgt' written; "
      f"static overhead cam=(0,0,{CAM_Z}) lens={CAM_LENS_MM}")
