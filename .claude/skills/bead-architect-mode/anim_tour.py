"""Tour: 30-second seamless-loopable cinematic tour of the bead's features.

Stops:
  A. wide establishing
  B. NFC pocket on the bottom half
  C. pegs cluster (low raking angle)
  D. spiral / decoration on the top half
  E. string hole (down the +X axis)
  → returns to A for seamless wrap

Pairs with `bead-debug-overlays/recolor.py` so each stop highlights
the corresponding DBG_* overlay (yellow pegs, magenta NFC pocket,
orange string hole) called out in CAD-then-architect colors.

Stores in actions:
  BeadAnim_tour_cam
  BeadAnim_tour_tgt

Requires `architect_on.py` first.
"""
import bpy

# ─── Tunables ─────────────────────────────────────────────────────────
ANIM_NAME      = "tour"
TOUR_SEC       = 30
FPS            = 24

# Stops (cam_loc, lens_mm, target_loc) — bead canonical print-layout
# (Bottom at X=-18, Top + Decoration at X=+18).
STOPS = [
    {"cam": (0,   -55, 18), "lens": 50, "target": (0,    0,   1.5), "label": "wide"},
    {"cam": (-18, -22, 14), "lens": 80, "target": (-18,  0,   2.0), "label": "NFC pocket"},
    {"cam": (-18, -16,  9), "lens": 90, "target": (-18,  0,   3.5), "label": "pegs"},
    {"cam": (28,  -14,  8), "lens": 85, "target": (18,   0,   3.0), "label": "spiral"},
    {"cam": (38,  -10,  4), "lens": 95, "target": (18,   9,   1.5), "label": "string hole"},
]

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


# Pivot is not animated by tour — drop its action so it holds (0,0,0)
if piv.animation_data:
    piv.animation_data.action = None
piv.location = (0, 0, 0)
piv.rotation_euler = (0, 0, 0)

_named_action(cam, "cam")
_named_action(tgt, "tgt")

# ─── Frame range ──────────────────────────────────────────────────────
scn = bpy.context.scene
total = max(2, int(TOUR_SEC * FPS))
scn.render.fps  = FPS
scn.frame_start = 1
scn.frame_end   = total

# ─── Keyframe each stop, then a return keyframe at frame total+1 ──────
n_stops = len(STOPS)
spacing = total / n_stops

def _key(stop, frame):
    cam.location  = stop["cam"]
    cam.data.lens = stop["lens"]
    tgt.location  = stop["target"]
    cam.keyframe_insert(data_path="location",       frame=frame)
    cam.data.keyframe_insert(data_path="lens",      frame=frame)
    tgt.keyframe_insert(data_path="location",       frame=frame)

for i, stop in enumerate(STOPS):
    f = 1 + int(i * spacing)
    _key(stop, f)

# Return to first stop just past frame_end so wrap is seamless
_key(STOPS[0], total + 1)

# Default Bezier interpolation gives a natural ease at each stop.

# ─── Start playback ───────────────────────────────────────────────────
scn.frame_current = 1
if not bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_play()

print(f"[anim_tour] actions 'BeadAnim_{ANIM_NAME}_cam' + '_tgt' written; "
      f"{TOUR_SEC}s tour, {n_stops} stops: " + " -> ".join(s["label"] for s in STOPS) + " -> wide (loop)")
