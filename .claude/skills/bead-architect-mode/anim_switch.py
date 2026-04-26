"""Switch the active animation by re-assigning stored Action data blocks.

Each `anim_*.py` writes its keyframes into named Action data blocks
following the convention `BeadAnim_<anim>_<role>` with `use_fake_user=True`,
so they all persist in the .blend after a `wm.save_mainfile`. This script
just looks up the matching Actions for `ANIM_NAME` and assigns them to
each rig component — instant switch, no re-keying required.

Usage:
    # Edit ANIM_NAME below, then exec:
    exec(open(r"<repo>/.claude/skills/bead-architect-mode/anim_switch.py").read())

    # Or to inspect what's available:
    ANIM_NAME = "_LIST"   # special value — prints all stored anims and exits
"""
import bpy

# ─── Tunable ──────────────────────────────────────────────────────────
# Set to one of: orbit | macro_pull | raking_light | tour | locked_profile | top_down
# (or any other anim with stored BeadAnim_<name>_<role> actions in this .blend).
# Special: "_LIST" prints all stored anims without changing anything.
#
# Caller may pre-set ANIM_NAME in the exec scope (e.g. `ANIM_NAME='tour'; exec(open(...))`)
# in which case we honor it instead of overwriting.
if "ANIM_NAME" not in globals():
    ANIM_NAME = "orbit"

# Maps role → object name. Each anim populates a subset of these.
RIG_ROLES = {
    "pivot": "CameraPivot",
    "cam":   "Camera",
    "tgt":   "CameraTarget",
    "sun":   "MA_Sun_Key",
}


def _list_stored_anims():
    """Group BeadAnim_<name>_<role> actions by name. Print + return the dict."""
    anims = {}
    for action in bpy.data.actions:
        if not action.name.startswith("BeadAnim_"):
            continue
        # BeadAnim_<name>_<role> — split on the LAST underscore so multi-word
        # anim names ("macro_pull") aren't broken up.
        rest = action.name[len("BeadAnim_"):]
        if "_" not in rest:
            continue
        name, role = rest.rsplit("_", 1)
        anims.setdefault(name, {})[role] = action
    print(f"Stored anims ({len(anims)}):")
    for name in sorted(anims):
        roles = ", ".join(sorted(anims[name].keys()))
        print(f"  {name:<20} roles: [{roles}]")
    return anims


def _switch_to(anim_name: str):
    """Assign each rig role's BeadAnim_<anim>_<role> action; clear if none."""
    applied = []
    cleared = []
    for role, obj_name in RIG_ROLES.items():
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            continue
        action = bpy.data.actions.get(f"BeadAnim_{anim_name}_{role}")
        if not obj.animation_data:
            obj.animation_data_create()
        if action is not None:
            obj.animation_data.action = action
            applied.append(role)
        else:
            obj.animation_data.action = None
            cleared.append(role)

    # Compute scene frame range from the union of assigned actions' ranges.
    rng_min = None
    rng_max = None
    for role, obj_name in RIG_ROLES.items():
        obj = bpy.data.objects.get(obj_name)
        if obj and obj.animation_data and obj.animation_data.action:
            a, b = obj.animation_data.action.frame_range
            rng_min = a if rng_min is None else min(rng_min, a)
            rng_max = b if rng_max is None else max(rng_max, b)

    scn = bpy.context.scene
    if rng_min is not None and rng_max is not None:
        scn.frame_start = int(rng_min)
        # If single-frame (static pose), keep frame_end = frame_start
        if int(rng_max) <= int(rng_min) + 1:
            scn.frame_end = int(rng_min)
        else:
            # Subtract 1 so the wrap doesn't show the duplicate end keyframe
            scn.frame_end = max(int(rng_min) + 1, int(rng_max) - 1)
        scn.frame_current = int(rng_min)
    return applied, cleared, (rng_min, rng_max)


# ─── Driver ───────────────────────────────────────────────────────────
if ANIM_NAME == "_LIST":
    _list_stored_anims()
else:
    applied, cleared, rng = _switch_to(ANIM_NAME)
    if not applied:
        print(f"[anim_switch] WARN: no BeadAnim_{ANIM_NAME}_* actions found. "
              f"Run anim_{ANIM_NAME}.py first to populate them.")
    else:
        rmin, rmax = rng
        is_static = (rmax is not None and rmin is not None and int(rmax) <= int(rmin) + 1)
        print(f"[anim_switch] -> {ANIM_NAME}: applied={applied}, cleared={cleared}, "
              f"frame range=[{rmin},{rmax}], static={is_static}")
        # Static: stop playback. Dynamic: start playback.
        playing = bpy.context.screen.is_animation_playing
        if is_static and playing:
            bpy.ops.screen.animation_play()
        elif not is_static and not playing:
            bpy.ops.screen.animation_play()
