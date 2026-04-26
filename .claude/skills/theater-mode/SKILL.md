---
name: theater-mode
description: The protocol and quality bar for making the Blender canvas beautiful enough to entertain the user during long Claude turns — the user runs this on a projector at home, so the wait is the point. Triggers on "theater mode", "Westworld mode", "make the wait look good", "I'm putting this on a projector", "is this good enough?", "spend more time on it", or whenever iterating on bead-architect-mode and you need the iteration protocol or the "done" criteria. Pairs with bead-architect-mode (the operational scripts) and bead-debug-overlays (the structural overlay layer it sometimes drapes over).
---

# Theater Mode

This skill is the *attitude* layer. The operational scripts live in `bead-architect-mode`; this skill is the protocol you follow when invoking them, and the bar you hold the result to.

## The reference

The user keeps citing "Westworld intro" — that pre-credits sequence with the player piano, the slow precise machinery, the white-on-black stencil titles, the deliberate pacing. **Machined, perfected, clinical, sophisticated.** Steady camera moves that *lock* on a profile for ten or fifteen seconds before drifting on. Macro close-ups on a single mechanism. Limited but exact palette. Nothing is rushed; nothing is busy.

That is the bar. Every shot you set up should answer "would this look at home in a Netflix high-prestige opening sequence?" If the answer is no, it isn't done.

## Why this matters — the actual user value

Without this, a Claude turn that takes 60 seconds to think looks like a frozen Blender window for 60 seconds. Boring. With this, the same 60 seconds shows a slowly orbiting bead under museum lighting, the camera gently easing closer to the NFC pocket, the parchment background catching warm rim-light. The user is *entertained*. They can show their projector to a guest and the guest will lean in.

This isn't decoration. **It's the actual user experience during long-running work.** Treat it accordingly.

## The protocol — depth-first, screenshot-verified

The most important rule: **never declare a shot or a mode "done" without taking screenshots and reading them.** Beautiful is a visual property; it can only be verified visually. The temptation is to exec the script, see "Code executed successfully", and move on. Don't. Always:

1. `exec(open(...).read())` the mode/anim script via the Blender MCP.
2. `mcp__blender__get_viewport_screenshot` at a chosen frame.
3. Read the image and write down what's actually wrong (washed-out colors, no ink lines, wrong camera angle, body blends into background, etc.).
4. Edit the script to fix the *biggest* issue.
5. Re-exec. Re-screenshot. Repeat.

Don't fan out across multiple shots until ONE shot looks the way it should. Iterating breadth-first across half-finished shots burns time and produces a portfolio of mediocre views. Pick one shot, hammer it until it would survive a Netflix title sequence cut, then move to the next.

You are an expert 3D-modeling artist working on this. **Spend time.** The user has explicitly said the wait is the point — the longer you spend setting up a single shot perfectly, the more entertaining the on-screen result. Treat every screenshot iteration as a feedback loop, not as a step to skip past.

## Take your time — that's the point

The user has explicitly framed this as "spend forever thinking, just make the wait gorgeous." Lean into the long form. **Set up animations that take minutes**, not seconds. Locked side-profile shots that hold for 10–15 seconds before drifting are correct. Macro pulls into the NFC pocket that take 8 seconds are correct. The default `anim_orbit.py` 90-second-per-revolution cadence is correct, not a bug.

Think in terms of *shots* not poses:

- **Establishing wide** (8–12 s): both halves visible, slow orbit, the user sees the whole composition.
- **Locked side profile** (10–15 s): camera parks at exactly y=-50, z=2 — pure horizontal silhouette, nothing else. Pegs and peg-holes line up like clockwork teeth on a gear. *This is the most Westworld-feeling shot we have.* Use it often.
- **Macro pull** (6–8 s): camera dollies from y=-50 to y=-15 along a straight line, lens shifts from 50mm to 80mm.
- **Top-down "blueprint plate"** (10 s): camera locks at z=+45 looking straight down, no orbit, just stillness.
- **Dramatic raking light** (continuous): the warm key light comes in low and from the side; the bead casts a long shadow across the parchment.

Concrete tools:
- `cam.location` and `cam.data.lens` are keyframable. So is `target.location` (pan the eye-line).
- For a *locked* shot during an orbit, set the pivot's Z rotation to a constant via a single keyframe range, or just kill the orbit during that segment with `pivot.animation_data_clear()` then re-key after.
- For smooth dolly-in: keyframe `cam.location` at start and end frames; let bezier interpolation handle the easing.
- For a lens zoom: keyframe `cam.data.lens` at start (50mm) and end (80mm). The camera "pushes in" optically without moving.

Don't be afraid of long shot durations. **15 seconds of a perfect locked profile is far better than 15 seconds of nothing-much-happening orbit.**

## Practical setup for a fresh session

1. **Verify the Blender MCP is connected.** Run `/mcp`. If not connected, the user probably already has Blender running with a scene loaded — ask them whether to launch fresh or to wait, don't launch unprompted.
2. **Check what's currently in the scene** (`mcp__blender__get_scene_info`). The user is probably already showing some bead halves on screen — your work continues from that scene state, not from a fresh empty scene. If the scene is empty (e.g. a fresh launch with no bead loaded), open `samples/rezz_sample.blend` — a tracked reference scene with canonical `Bottom`/`Top`/`Decoration` objects that lets you exercise the architect look immediately. `tools/launch.ps1` falls back to this sample automatically when no charm-specific `.blend` exists.
3. **Layer the look.** If structural overlays should read on parchment, run `bead-debug-overlays/recolor.py` first, then `bead-architect-mode/architect_on.py` (which auto-retints `DBG_*` overlays to a parchment-friendly palette).
4. **Pick ONE animation script to iterate** (`anim_orbit.py`, `anim_locked_profile.py`, `anim_macro_pull.py`, `anim_top_down.py`, `anim_raking_light.py`, `anim_tour.py` from `bead-architect-mode`). Don't try to ship two shots at once.
5. **Exec → screenshot → critique → edit → exec → screenshot.** That loop. Don't skip the screenshot step. Ever.
6. **Commit each genuine improvement.** Tiny commits are fine; they let the user roll back if a "fix" actually makes it worse.

## When a shot reaches "done"

A shot is done when:

1. A still screenshot taken at any frame in the loop could plausibly appear in a slick design portfolio.
2. The full loop (90 s for orbit, 12 s for macro pull, etc.) can play in the background without the user wanting to look away.
3. The shot survives running on at least three different bead silhouettes (deadmau5, Marshmello, Daft Punk hexagon, rezz, etc.) without visual artifacts unique to one shape.

Until those three pass: keep iterating. Take screenshots. Read them. Fix the biggest issue. Repeat.

## What this skill is NOT for

- Building new beads — that's the `nfc-bead` skill / per-charm branches.
- Editing the bead recipe (`prompts/nfc-bead/prompt.md`) — bead-recipe changes are independent of the cinematic look.
- Changing the build pipeline (`build_charm.py.example`) — same.
- The cinematic mode does NOT influence STL output in any way. `bead-stl-export` strips the architect aesthetic + debug overlays before writing STLs. If a theater-mode change ever affects an exported STL, something is wrong.

## Companion skills

| Skill | Role |
|---|---|
| `bead-architect-mode` | Operational scripts: `architect_on.py`, the `anim_*.py` family, `architect_off.py`. This is what you `exec()` to apply or animate the look. |
| `bead-debug-overlays` | Optional structural-feature overlay (`recolor.py`) that the architect mode will automatically re-tint to parchment colors when layered underneath. |
| `bead-stl-export` | Defensive export. Strips MA_* and DBG_* before writing STLs so the cinematic layer never contaminates the slicer. |
