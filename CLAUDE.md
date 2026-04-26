# CLAUDE.md — `theater-mode` worktree (aesthetics only)

This worktree exists for one reason: **make the Blender canvas beautiful enough that the user is entertained while Claude thinks.** The user runs this on a projector at home; long thinking turns should still look good. Nothing in this worktree changes the bead recipe, the build pipeline, or the STL outputs — that's all on `main` and the per-charm branches.

## The reference

The user keeps citing "Westworld intro" — that pre-credits sequence with the player piano, the slow precise machinery, the white-on-black stencil titles, the deliberate pacing. **Machined, perfected, clinical, sophisticated.** Steady camera moves that *lock* on a profile for ten or fifteen seconds before drifting on. Macro close-ups on a single mechanism. Limited but exact palette. Nothing is rushed; nothing is busy.

That is the bar. Every shot we set up should answer "would this look at home in a Netflix high-prestige opening sequence?" If the answer is no, it isn't done.

## How the work is organized

Three skills carry the operational guidance — that's the source of truth, not this file:

| Skill | What |
|---|---|
| `.claude/skills/bead-architect-mode/` | The architect aesthetic (parchment + ink + watercolor) and 6 seamless-loopable camera animations. Toggle on with `architect_on.py`, off with `architect_off.py`. EEVEE renderer. |
| `.claude/skills/bead-debug-overlays/` | CAD-palette body coloring + `DBG_*` overlay widgets for hidden features (pegs, peg holes, NFC pocket, string hole). Pairs under the architect drape. |
| `.claude/skills/bead-stl-export/` | Defensive STL export — strips overlays, applies the deterministic per-part print-orientation flip (`EXPORT_FLIP_X_DEG`), bed-flattens to z=0. |

Plus four host-side CLI tools (run via uv, registered as `[project.scripts]` in `pyproject.toml`):

| Command | What |
|---|---|
| `uv run nfc-blender-send` | Send Python to a running Blender via the BlenderMCP socket (works even when Claude Code's MCP layer is dropped) |
| `uv run nfc-verify-stls`  | Validate the `tmp/latest/` STL set via trimesh — manifold, dimensions, alignment |
| `uv run nfc-build-rezz-3mf` | Build slicer-ready Bambu/Elegoo 3MF for the rezz bead with extruder assignments + printer profile preserved |
| `uv run nfc-make-3mf` | Generic 3MF Consortium bundle (fallback when no slicer template is available) |

Each skill's `SKILL.md` and the host scripts' module docstrings are the sources of truth. Don't re-document those here.

## The protocol — depth-first, screenshot-verified

The most important rule: **never declare a look "done" without taking screenshots and reading them.** Beautiful is a visual property; it can only be verified visually. Always:

1. `exec(open(...).read())` the script via the Blender MCP (or `python tools/blender_send.py -f <path>` when MCP is disconnected).
2. `mcp__blender__get_viewport_screenshot` at a chosen frame.
3. Read the image and write down what's *actually* wrong.
4. Edit the script to fix the *biggest* issue.
5. Re-exec. Re-screenshot. Repeat.

Don't skip step 3. The temptation after "Code executed successfully" is to call it done; resist that.

## Take your time — that's the point

The user has explicitly framed this as "spend forever thinking, just make the wait gorgeous." Lean into the long form. **Set up animations that take minutes**, not seconds. Locked side-profile shots that hold for 10–15 seconds before drifting are correct. Macro pulls into the NFC pocket that take 6–8 seconds are correct.

Concrete tools when you need to go beyond the canned `anim_*.py`:
- `cam.location` and `cam.data.lens` are keyframable. So is `target.location` (pan the eye-line).
- For a *locked* shot during an orbit, set the pivot's Z rotation to a constant via a single keyframe range, or call `pivot.animation_data_clear()` then re-key after.
- For smooth dolly-in: keyframe `cam.location` at the start frame and end frame; let bezier interpolation handle the easing.
- For a lens zoom: keyframe `cam.data.lens` at start (50mm) and end (80–90mm). The camera "pushes in" optically without moving.

15 seconds of a perfect locked profile is far better than 15 seconds of nothing-much-happening orbit.

## Why this matters — the actual user value

Without this, a Claude turn that takes 60 seconds to think looks like a frozen Blender window for 60 seconds. Boring. With this, the same 60 seconds shows a slowly orbiting bead under museum lighting, the camera gently easing closer to the NFC pocket, the parchment background catching warm rim-light. The user is *entertained*. They can show their projector to a guest and the guest will lean in.

This isn't decoration. **It's the actual user experience during long-running work.** Treat it accordingly.

## The sample bead scene

`samples/rezz_sample.blend` is the canonical sample scene used to demo the architect mode and animations. It's the rezz bead in the canonical print-layout (Bottom at X=-18, Top at X=+18, Decoration on Top), with the architect rig + lights + materials + DBG_* feature overlays already applied. EEVEE engine, high-contrast palette, wireframe overlay enabled, camera frame fills the editor.

Use it as the **default scene for any aesthetic work** in this worktree:

- `tools\launch.ps1` (no args) opens it automatically when no per-charm `.blend` is found.
- When testing changes to `architect_on.py` / `anim_*.py` / `recolor.py`, run them against this scene to verify before declaring done.
- When updating it (new geometry, fixed widget, palette tweak), re-save in place (`bpy.ops.wm.save_as_mainfile`) and commit so future sessions inherit the fix.

## Practical setup for a fresh session

1. **Verify the Blender MCP is connected** — `/mcp`. If it's down but Blender is running, use `python tools/blender_send.py -f <script>` to talk to it via the addon socket directly.
2. **Check the scene** (`mcp__blender__get_scene_info`). If it's empty or wrong, launch fresh against the sample: `tools\launch.ps1` (defaults to `samples/rezz_sample.blend`).
3. **Apply the architect look** — `exec(open(r"<repo>/.claude/skills/bead-architect-mode/architect_on.py").read())`.
4. **Pick an animation** — `anim_orbit.py` for default, `anim_locked_profile.py` for a held silhouette, `anim_macro_pull.py` for a feature reveal, `anim_tour.py` for a 5-stop tour through the technical features, `anim_raking_light.py` for a moving-light still-camera shot, or `auto_cycle.py` to rotate through them every 30s.
5. **Exec → screenshot → critique → edit → exec → screenshot.** Don't skip the screenshot step. Ever.
6. **Commit each genuine improvement.** Tiny commits are fine; they let the user roll back if a "fix" actually makes it worse.

## Conventions

- **Canonical names**: `Bottom`, `Top`, `Decoration` (bead-agnostic). Build scripts produce these names; aesthetic scripts read them. Legacy bead-prefixed names like `rezz_top_body` are accepted as a suffix fallback.
- **Object prefixes**: `MA_*` for architect-mode additions (lights, GP line-art, materials, optional plate); `DBG_*` for debug overlay widgets. STL export filters both.
- **Idempotent**: every script can be re-run safely. Use `bpy.data.objects.get(name)` and replace, never blindly append.
- **OBJECT mode required**: `bpy.ops.object.*` poll fails when the user is in EDIT/sculpt/paint mode. `architect_on.py` drops to OBJECT at the top — copy that pattern in any new mode.

## What this worktree is NOT for

- Building new beads. That's per-charm branches off `main`.
- Editing the bead recipe (`prompts/nfc-bead/prompt.md`). That's a `main` change.
- Changing the build pipeline (`build_charm.py.example`). Same.
- The cinematic mode does not influence STL output. STL export ignores materials, the world shader, GP objects, and lights. If a change here affects exports, something is wrong.

## When a mode reaches "done"

1. A still screenshot taken at any frame in the orbit could plausibly appear in a slick design portfolio.
2. The default-cadence orbit can play in the background without the user wanting to look away.
3. The mode survives on at least three different bead silhouettes (deadmau5, Marshmello, Daft Punk hexagon, Rezz round) without visual artifacts unique to one shape.

Until those three pass: keep iterating. Take screenshots. Read them. Fix the biggest issue. Repeat.
