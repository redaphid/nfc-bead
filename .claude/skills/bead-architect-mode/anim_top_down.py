"""Top-down 'blueprint plate' shot: camera locked overhead, no motion.

The bead viewed straight down as if on a drafting table. The whole
print layout is visible at once — bottom-half on the left, top-half
+ decoration on the right.

Idempotent — clears any animation on the rig.

Requires `architect_on.py` first.
"""
import bpy

# ─── Tunables ─────────────────────────────────────────────────────────
CAM_Z          = 50           # height above origin
CAM_LENS_MM    = 60
TARGET         = (0, 0.001, 0)
# ↑ tiny non-zero Y offset on the target avoids a degenerate TRACK_TO
#   "up" direction when looking straight down (the constraint's UP_Y
#   axis becomes ambiguous when target is exactly under the camera).

# ─── Locate the rig ───────────────────────────────────────────────────
piv = bpy.data.objects.get("CameraPivot")
cam = bpy.data.objects.get("Camera")
tgt = bpy.data.objects.get("CameraTarget")
if not (piv and cam and tgt):
    raise RuntimeError("Camera rig missing — run architect_on.py first.")

# ─── Kill prior animation ─────────────────────────────────────────────
if piv.animation_data: piv.animation_data_clear()
if cam.animation_data: cam.animation_data_clear()
piv.location = (0, 0, 0)
piv.rotation_euler = (0, 0, 0)

# ─── Park ─────────────────────────────────────────────────────────────
tgt.location = TARGET
cam.location = (0, 0, CAM_Z)
cam.data.lens = CAM_LENS_MM

# ─── Single frame ─────────────────────────────────────────────────────
scn = bpy.context.scene
scn.frame_start = 1
scn.frame_end   = 1
scn.frame_current = 1
if bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_play()

print(f"[anim_top_down] cam=(0,0,{CAM_Z}) lens={CAM_LENS_MM}; "
      "static blueprint-plate shot.")
