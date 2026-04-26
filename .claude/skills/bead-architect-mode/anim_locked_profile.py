"""Locked side-profile shot: camera parks at eye-level horizontal.

The most Westworld-feeling shot in the vocabulary — the camera
doesn't move at all. Holds the bead's silhouette as a clean horizontal
profile against the parchment for as long as the user wants to look at
it.

Idempotent — clears any animation on the rig.

Tunables: aim Y distance and elevation. Defaults frame the canonical
print-layout (halves at X=±18) at eye level.

Requires `architect_on.py` first.
"""
import bpy

# ─── Tunables ─────────────────────────────────────────────────────────
CAM_Y          = -55          # how far in front of the bead
CAM_Z          = 2.5          # eye-level height
CAM_LENS_MM    = 60           # tighter than wide-orbit lens
TARGET_Z       = 2.5          # match cam Z to keep horizon truly horizontal

# ─── Locate the rig ───────────────────────────────────────────────────
piv = bpy.data.objects.get("CameraPivot")
cam = bpy.data.objects.get("Camera")
tgt = bpy.data.objects.get("CameraTarget")
if not (piv and cam and tgt):
    raise RuntimeError("Camera rig missing — run architect_on.py first.")

# ─── Kill any prior animation ─────────────────────────────────────────
if piv.animation_data: piv.animation_data_clear()
if cam.animation_data: cam.animation_data_clear()
piv.location = (0, 0, 0)
piv.rotation_euler = (0, 0, 0)

# ─── Park camera and target ───────────────────────────────────────────
tgt.location = (0, 0, TARGET_Z)
cam.location = (0, CAM_Y, CAM_Z)
cam.data.lens = CAM_LENS_MM

# ─── Single frame, no playback ────────────────────────────────────────
scn = bpy.context.scene
scn.frame_start = 1
scn.frame_end   = 1
scn.frame_current = 1
if bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_play()

print(f"[anim_locked_profile] cam=(0,{CAM_Y},{CAM_Z}) lens={CAM_LENS_MM} target_z={TARGET_Z}; "
      "static, no animation.")
