# CLAUDE.md — `theater-mode` worktree (aesthetics only)

This worktree exists for one reason: **make the Blender canvas beautiful enough that the user is entertained while Claude thinks.** The user runs this on a projector at home; long thinking turns should still look good. Nothing in this worktree changes the bead recipe, the build pipeline, or the STL outputs — that's all on `main` and the per-charm branches.

## The reference

The user keeps citing "Westworld intro" — that pre-credits sequence with the player piano, the slow precise machinery, the white-on-black stencil titles, the deliberate pacing. **Machined, perfected, clinical, sophisticated.** Steady camera moves that *lock* on a profile for ten or fifteen seconds before drifting on. Macro close-ups on a single mechanism. Limited but exact palette. Nothing is rushed; nothing is busy.

That is the bar. Every shot we set up should answer "would this look at home in a Netflix high-prestige opening sequence?" If the answer is no, it isn't done.

## Scope of this worktree

- `.claude/skills/bead-debug-colors/blueprint.py` — cyanotype-glass mode (cool blue paper, semi-transparent body shells, structural features visible through the glass).
- `.claude/skills/bead-debug-colors/master_architect.py` — parchment + GP-line-art mode (warm cream paper, dark sepia ink edges over matte body fills). **In progress — not yet hitting the bar.** See "Known issues" below.
- Future modes go in the same directory and follow the same pattern: one self-contained Python script, idempotent, named after the visual reference (`steel_lab.py`, `noir_macro.py`, `holographic_blueprint.py`, etc.).

The shared infrastructure across modes:
- World shader (background color)
- Cycles + OptiX viewport-rendered (the user has an RTX 4090 — RT cores accelerate both rays and the OptiX denoiser)
- Slow keyframed camera orbit (CameraPivot, CameraTarget, Camera with TRACK_TO constraint)
- Optional dolly breath (camera Y oscillates ±8 units across the orbit)
- A "scene-find" helper that locates `Bottom`/`Top` halves whether they're named canonically or prefixed (e.g. `daftpunk_Bottom`)

Each mode swaps the world shader, body materials, lighting, optional GP line-art object, and re-keyframes the camera if needed.

## The protocol — depth-first, screenshot-verified

This is the most important rule: **never declare a mode "done" without taking screenshots and reading them.** Beautiful is a visual property; it can only be verified visually. The temptation is to write the script, run it, see "Code executed successfully", and move on. Don't. Always:

1. `exec(open(...).read())` the mode script via the Blender MCP.
2. `mcp__blender__get_viewport_screenshot` at a chosen frame.
3. Read the image and write down what's actually wrong (washed-out colors, no ink lines, wrong camera angle, body blends into background, …).
4. Edit the script to fix the *biggest* issue.
5. Re-exec. Re-screenshot. Repeat.

Don't fan out across multiple modes until ONE mode looks the way it should. Iterating breadth-first across half-finished modes burns time and produces a portfolio of mediocre views. Pick one mode, hammer it until it would survive a Netflix title sequence cut, then move to the next.

You are an expert 3D modeling artist working on this. **Spend time.** The user has explicitly said the wait is the point — the longer you spend setting up a single shot perfectly, the more entertaining the on-screen result. Treat every screenshot iteration as a feedback loop, not as a step to skip past.

## Take your time — that's the point

The user has explicitly framed this as "spend forever thinking, just make the wait gorgeous." Lean into the long form. **Set up animations that take minutes**, not seconds. The orbit period defaults to 6000 frames at 24 fps — that's 4 minutes per revolution. That is *correct* for this context, not a bug. Locked side-profile shots that hold for 10–15 seconds before drifting are correct. Macro pulls into the NFC pocket that take 8 seconds are correct.

When you set up a camera move, think in terms of *shots* not poses:

- **Establishing wide** (8–12 s): both halves visible, slow orbit, the user sees the whole composition.
- **Locked side profile** (10–15 s): camera parks at exactly y=-50, z=2 — pure horizontal silhouette, nothing else. Pegs and peg-holes line up like clockwork teeth on a gear. *This is the most Westworld-feeling shot we have.* Use it often.
- **Macro into NFC pocket** (6–8 s): camera dollies from y=-50 to y=-15 along a straight line, lens shifts from 50mm to 80mm.
- **Top-down "blueprint plate"** (10 s): camera locks at z=+45 looking straight down, no orbit, just stillness.
- **Dramatic raking light** (continuous): the warm light comes in low and from the side; the bead casts a long shadow across the parchment.

Concrete tools for this:
- `cam.location` and `cam.data.lens` are keyframable. So is `target.location` (pan the eye-line).
- For a *locked* shot during an orbit, set the pivot's Z rotation to a constant via a single keyframe range (or just kill the orbit during that segment with `pivot.animation_data_clear()` then re-key after).
- For smooth dolly-in: keyframe `cam.location` at the start frame and end frame; let bezier interpolation handle the easing.
- For a lens zoom: keyframe `cam.data.lens` at start (50mm) and end (80mm). The camera "pushes in" optically without moving.

Don't be afraid of long shot durations. **15 seconds of a perfect locked profile is far better than 15 seconds of nothing-much-happening orbit.**

## Why this matters — the actual user value

Without this, a Claude turn that takes 60 seconds to think looks like a frozen Blender window for 60 seconds. Boring. With this, the same 60 seconds shows a slowly orbiting bead under museum lighting, the camera gently easing closer to the NFC pocket, the parchment background catching warm rim-light. The user is *entertained*. They can show their projector to a guest and the guest will lean in.

This isn't decoration. **It's the actual user experience during long-running work.** Treat it accordingly.

## Practical setup for a fresh session

1. **Verify the Blender MCP is connected.** Run `/mcp`. If not connected, the user already has Blender running with a scene loaded — ask them whether to launch fresh or to wait, don't try to launch unprompted.
2. **Check what's currently in the scene** (`mcp__blender__get_scene_info`). The user is probably already showing some bead halves on screen — your work continues from that scene state, not from a fresh empty scene.
3. **Pick ONE mode to iterate** (`master_architect.py` or `blueprint.py`) based on what the user is asking for, or what looks closest to the reference they cite. Don't try to ship two modes at once.
4. **Exec → screenshot → critique → edit → exec → screenshot.** That loop. Don't skip the screenshot step. Ever.
5. **Commit each genuine improvement.** Tiny commits are fine; they let the user roll back if a "fix" actually makes it worse.

## File conventions

- Mode scripts live at `.claude/skills/bead-debug-colors/<name>.py`. The skill's `SKILL.md` indexes them.
- Each script has a tunable block at the very top. Defaults should produce the canonical look; users adjust from there.
- All scripts must be idempotent — re-running rebuilds the world/GP/camera state cleanly without leaking duplicate objects (use `bpy.data.objects.get(name)` and replace, not append).
- Half-finder helper: search for an object literally named `Bottom`/`Top`, then fall back to anything ending in `_Bottom`/`_Top`. Beads built on charm branches use prefixed names (`daftpunk_Bottom`).
- Cycles + OptiX setup is shared — copy/paste from `blueprint.py` or `master_architect.py` rather than re-deriving.

## What this worktree is NOT for

- Building new beads. That's per-charm branches off `main`.
- Editing the bead recipe (`prompts/nfc-bead/prompt.md`). That's a `main` change.
- Changing the build pipeline (`build_charm.py.example`). Same.
- The cinematic mode does not influence the STL output in any way. STL export ignores materials and ignores the world shader. If a change here affects exports, something is wrong.

## When a mode reaches "done"

A mode is done when:
1. A still screenshot taken at any frame in the orbit could plausibly appear in a slick design portfolio.
2. The 4-minute orbit can play in the background without the user wanting to look away.
3. The mode survives running on at least three different bead silhouettes (deadmau5, Marshmello, Daft Punk hexagon) without visual artifacts unique to one shape.

Until those three pass: keep iterating. Take screenshots. Read them. Fix the biggest issue. Repeat.

## Known issues to pick up

These are open problems left for the next session — start here.

### `master_architect.py` — ink lines aren't reading

Last test on the Daft Punk hexagons (chrome bottom + gold top, at world ±18) produced a screenshot of beige-on-beige soup with faint orange specks at the edges. The Grease Pencil object (`MA_LineArt`) is created and configured correctly per inspection:
- Modifier: `LINEART`, source_type=`SCENE`, use_intersection=True, use_contour=True
- Material: `Black.001` with sepia color (0.10, 0.06, 0.04), show_stroke=True, show_fill=False

But the actual line strokes aren't visibly drawing on the rendered viewport. Hypotheses to test, in order:

1. **Selection highlights, not strokes.** The orange specks I saw might just be Blender's selection outline color on the GP object. Run `bpy.ops.object.select_all(action='DESELECT')` then re-screenshot. If the specks vanish entirely, the strokes aren't drawing at all and we have a real config bug.
2. **Line thickness.** The modifier's `thickness` attribute didn't accept the float `2.4` (printed as `'?'` in the inspect output). The modifier may want an integer in *line points*, not viewport pixels — try `lineart_mod.thickness = 25` (the GP default).
3. **show_in_front interaction with Cycles RENDERED.** GP objects with `show_in_front=True` may not composite properly in Cycles RENDERED viewport mode. Try toggling `gp.show_in_front = False`. If the strokes appear but get occluded by the bodies, that's the problem and we need a different overlay strategy (post-render compositor, or switch viewport to Workbench for the line pass).
4. **Layer needs to be unlocked / visible.** Check `gp.data.layers["Layer"].lock` and `.hide`.
5. **Cache miss.** GP line art caches per scene state — sometimes needs a frame change to re-evaluate. After config, try `bpy.context.scene.frame_set(bpy.context.scene.frame_current)` to force a re-eval.

### Camera framing on test shots

The dolly breath is putting the camera at y=-43 mid-cycle, which is too close for the 4-minute wide-orbit shot. Either widen the breath range to (-65, -55) so we stay further out, or disable `DOLLY_BREATH` for the establishing shot and reserve breathing for macro shots.

### Body color contrast

Body fill `(0.88, 0.81, 0.66)` is too close to parchment `(0.93, 0.86, 0.72)` — they read as the same warm cream. Either darken bodies to a slate gray for contrast, or lighten parchment to near-white and keep bodies cream. The Westworld reference would suggest *high contrast* — near-white paper + dark slate or charcoal bodies + crisp ink lines.

## Reference: existing modes

### `blueprint.py`
Cyanotype glass: blueprint-blue world, semi-transparent body materials (alpha=0.30), structural features visible through. Works on Daft Punk halves; produces "glass overlay on blue paper" look. Camera orbits + dolly breaths. Not yet polished to the Westworld bar.

### `master_architect.py`
Parchment + ink: warm cream world, GP line art for crisp edges, matte body fills. Currently has the ink-line bug above. When it works, this is the closest to the user's stated "master architect" reference.

### `recolor.py` (existing — for reference)
Adds `DBG_*` overlay objects (yellow pegs, red wireframe peg holes, magenta NFC pocket, orange string-hole tube). Layer this *under* a cinematic mode if you want the structural features called out — `recolor.py` first, then `blueprint.py` or `master_architect.py` on top.

### `restore.py` (existing — for reference)
Wipes `DBG_*` overlays and repaints bodies in production filament colors. Run after any cinematic-mode session if you want the canvas back to its slicer-true look.
