"""Tour animation: camera visits each technical feature of the bead.

A 30-second seamless-loopable cinematic tour with stops at:
  A. wide establishing (both halves visible)
  B. bottom half — NFC pocket (looking down at the inner face)
  C. bottom half — pegs (low angle revealing the peg cluster)
  D. top half — spiral decoration (raking from the side)
  E. top half — string hole opening (down +X axis to the head)
  → returns to A for seamless wrap

Pairs naturally with `bead-debug-overlays/recolor.py` so each stop
features the corresponding DBG_* overlay (yellow pegs, magenta NFC
pocket, orange string hole) called out in CAD-then-architect colors.

Idempotent. Bezier ease at every stop gives a smooth glide.

Requires `architect_on.py` to have set up the camera rig.
"""
import bpy

# ─── Tunables ─────────────────────────────────────────────────────────
TOUR_SEC       = 30           # full cycle
FPS            = 24

# Stops (cam_loc, lens_mm, target_loc) — bead is at the canonical
# print-layout: bottom centered at X=-18, top body+spiral at X=+18.
STOPS = [
    # A: wide establishing
    {"cam": (0,   -55, 18), "lens": 50, "target": (0,    0,   1.5), "label": "wide"},
    # B: NFC pocket on the bottom half (top-of-bottom-puck angle)
    {"cam": (-18, -22, 14), "lens": 80, "target": (-18,  0,   2.0), "label": "NFC pocket"},
    # C: pegs cluster on the bottom inner face — lower angle, raking
    {"cam": (-18, -16,  9), "lens": 90, "target": (-18,  0,   3.5), "label": "pegs"},
    # D: spiral decoration on the top half — three-quarter side
    {"cam": (28,  -14,  8), "lens": 85, "target": (18,   0,   3.0), "label": "spiral"},
    # E: string hole opening on the +X face of top body, at Y=+9
    {"cam": (38,  -10,  4), "lens": 95, "target": (18,   9,   1.5), "label": "string hole"},
    # F = A again for seamless return (final keyframe is past frame_end)
]

# ─── Locate the rig ───────────────────────────────────────────────────
piv = bpy.data.objects.get("CameraPivot")
cam = bpy.data.objects.get("Camera")
tgt = bpy.data.objects.get("CameraTarget")
if not (piv and cam and tgt):
    raise RuntimeError("Camera rig missing — run architect_on.py first.")

# ─── Wipe prior animation ─────────────────────────────────────────────
for o in (piv, cam, tgt):
    if o.animation_data:
        o.animation_data_clear()
piv.location = (0, 0, 0)
piv.rotation_euler = (0, 0, 0)

# ─── Frame range ──────────────────────────────────────────────────────
scn = bpy.context.scene
total = max(2, int(TOUR_SEC * FPS))
scn.render.fps  = FPS
scn.frame_start = 1
scn.frame_end   = total

# ─── Keyframe each stop, then a return keyframe at frame total+1 ──────
n_stops = len(STOPS)
spacing = total / n_stops      # frames between stops

def _key(stop, frame):
    cam.location  = stop["cam"]
    cam.data.lens = stop["lens"]
    tgt.location  = stop["target"]
    cam.keyframe_insert(data_path="location",  frame=frame)
    cam.data.keyframe_insert(data_path="lens", frame=frame)
    tgt.keyframe_insert(data_path="location",  frame=frame)

for i, stop in enumerate(STOPS):
    f = 1 + int(i * spacing)
    _key(stop, f)

# Final keyframe back at A, just past frame_end so wrap is invisible
_key(STOPS[0], total + 1)

# Default Bezier interpolation gives a natural ease at each stop.

# ─── Start playback ───────────────────────────────────────────────────
scn.frame_current = 1
if not bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_play()

print(f"[anim_tour] {TOUR_SEC}s tour, {n_stops} stops: " + " → ".join(s["label"] for s in STOPS) + " → wide (loop)")
