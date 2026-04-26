"""Auto-cycle: switch between animations every N seconds, forever.

Registers a `bpy.app.timers` ticker that exec's the next animation
script every CYCLE_SEC seconds. Continues until Blender closes or
the user runs this script again with a different anim list.

Idempotent: each run generates a unique generation ID; older
ticker closures see a mismatched generation and self-cancel, so
you don't get duplicate cycles competing.

Requires `architect_on.py` first.
"""
import bpy
import os
import random

# ─── Tunables ─────────────────────────────────────────────────────────
CYCLE_SEC = 30.0

# Repository path resolution so this script can be exec'd from anywhere
_THIS_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
            r"C:\Users\hypnodroid\Worktrees\nfc-bead\theater-mode\.claude\skills\bead-architect-mode"

ANIM_PATHS = [
    os.path.join(_THIS_DIR, "anim_orbit.py"),
    os.path.join(_THIS_DIR, "anim_macro_pull.py"),
    os.path.join(_THIS_DIR, "anim_raking_light.py"),
    os.path.join(_THIS_DIR, "anim_tour.py"),
]

# ─── Generation guard so older instances self-cancel ──────────────────
_GEN_ID = random.randint(1_000_000, 9_999_999)
bpy.context.scene["MA_cycle_gen"] = _GEN_ID
bpy.context.scene["MA_cycle_idx"] = 0

# ─── Ticker ───────────────────────────────────────────────────────────
def _tick():
    scn = bpy.context.scene
    if scn.get("MA_cycle_gen", 0) != _GEN_ID:
        return None  # superseded by a newer auto_cycle invocation
    idx = scn.get("MA_cycle_idx", 0)
    path = ANIM_PATHS[idx % len(ANIM_PATHS)]
    name = os.path.basename(path)
    scn["MA_cycle_idx"] = idx + 1
    print(f"[auto_cycle gen={_GEN_ID}] {idx % len(ANIM_PATHS) + 1}/{len(ANIM_PATHS)} -> {name}")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            code = fh.read()
        exec(code, {"__name__": "__main__", "__file__": path})
    except Exception as e:
        print(f"[auto_cycle] anim error: {e}")
    return CYCLE_SEC

# Register; first fire happens almost immediately.
bpy.app.timers.register(_tick, first_interval=0.5)
print(f"[auto_cycle] scheduled gen={_GEN_ID}, switching every {CYCLE_SEC}s; "
      f"sequence: {' -> '.join(os.path.basename(p) for p in ANIM_PATHS)}")
