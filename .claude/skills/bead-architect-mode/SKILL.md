---
name: bead-architect-mode
description: Drape a hand-drafted parchment+ink+watercolor 'architect' aesthetic over an NFC bead in Blender, with seamless-loopable cinematic camera animations. Use when the user wants the canvas to look beautiful while Claude is thinking, when narrating a build live, or when showing the bead on a projector — triggers on "make it pretty", "Westworld mode", "architect aesthetic", "set up the orbit", "give me a slow camera move", "loop the macro pull", "rake the light", "tour the bead", or similar. Pairs with bead-debug-overlays — run that first to get DBG_* overlays, then this skill auto-tints them to a parchment-friendly palette. Requires the Blender MCP to be connected.
---

# Bead Architect Mode

## Project-wide naming convention

Same as `bead-debug-overlays`: canonical Blender object names are `Bottom`, `Top`, `Decoration`. `architect_on.py` paints these directly. **No legacy-suffix fallbacks** — if the canonical names aren't present, the script no-ops rather than guessing.

Two layers: the **look** (parchment + ink + watercolor) and the **animations** (5 seamless-loopable camera moves). All idempotent.

## Toggle scripts

| Script | Effect |
|---|---|
| `architect_on.py` | Apply the verified architect look: parchment world, watercolor washes, GP ink-line tracing, warm key + cool fill lights, Cycles+OptiX render setup, camera rig (no animation). Optionally re-tints `DBG_*` overlays from `bead-debug-overlays` to a parchment palette. |
| `architect_off.py` | Wipe everything `architect_on.py` adds: removes `MA_*` objects, drops `MA_*` materials from bodies, neutral-greys the world, kills camera animation. |

## Animation scripts

Each `anim_*.py` requires `architect_on.py` to have set up the camera rig. **All produce seamless continuous loops** when Blender's playback wraps from `frame_end` back to `frame_start` — kick one off, walk away, the viewport keeps moving forever.

| Script | Loop type | Default cadence | What it does |
|---|---|---|---|
| `anim_orbit.py` | rotational | 90 s/rev (`PERIOD=2160` @ 24fps) | Z-orbit + ±15° X-wobble + optional dolly breath |
| `anim_locked_profile.py` | trivial (static) | 1 frame, infinite | Eye-level horizontal silhouette, lens 60mm |
| `anim_top_down.py` | trivial (static) | 1 frame, infinite | Overhead 'blueprint plate', lens 60mm |
| `anim_macro_pull.py` | ping-pong | 12 s/cycle (6s each way) | Wide → close-up on `±X` half → wide |
| `anim_raking_light.py` | rotational | 60 s/sweep | Camera holds, key sun orbits horizontally |

Each script clears its own animation data before re-keying — switching between them is safe and live.

## How loop seamlessness is guaranteed

| Animation | Why it's seamless |
|---|---|
| `anim_orbit.py` | Z-rotation 0° == 360° visually; X-wobble samples include matched endpoints |
| `anim_raking_light.py` | Sun's location traces a full circle; first and last keyframes are the same `(R, 0, Z)` point |
| `anim_macro_pull.py` | Wide at frame 1, close at midpoint, wide again at end — bezier ease at both extremes; wrap is invisible |
| `anim_locked_profile.py` / `anim_top_down.py` | Static — every wrap is identical |

## Verified palette (Iters 02–04 in `journals/architect-aesthetic/`)

```python
PARCHMENT      = (0.93, 0.86, 0.72)   # warm cream world
INK_GRAPHITE   = (0.08, 0.10, 0.14)   # GP line-art ink
INK_RADIUS     = 0.05                 # Blender 5.0 GP modifier (NOT 'thickness')
BOTTOM_FILL    = (0.62, 0.74, 0.82)   # blueprint blue-gray wash
TOP_FILL       = (0.70, 0.80, 0.74)   # sage wash
ACCENT_FILL    = (0.85, 0.62, 0.32)   # warm bronze (raised decorations)
```

## Architect highlight palette (for `DBG_*` re-tinting)

When `RETINT_DBG_OVERLAYS = True` in `architect_on.py`, any overlays from `bead-debug-overlays/recolor.py` get re-tinted with this palette. Same hue families as the CAD palette (so memory of "yellow=peg, red=hole, magenta=NFC, orange=string" is preserved), but desaturated to read as draftsman annotations on parchment.

| Element | CAD color (recolor.py) | Architect color | Reading |
|---|---|---|---|
| Pegs | yellow `(1.00, 0.82, 0.10)` | bright muted ochre `(0.92, 0.78, 0.30)` | added material |
| Peg holes | red `(0.92, 0.15, 0.15)` | venetian red `(0.62, 0.22, 0.20)` | void |
| NFC pocket | magenta `(0.88, 0.15, 0.78)` | dusty rose `(0.55, 0.30, 0.50)` | void |
| String hole | orange `(1.00, 0.50, 0.10)` | drafted rust `(0.78, 0.45, 0.20)` | void |

## Blender 5.0 quirks (baked in, do not re-discover)

- The GP LineArt modifier no longer has a `thickness` attribute — it's `radius` (default `0.0025` is invisibly thin; need `~0.05`).
- `gp.show_in_front = True` does NOT composite for Cycles render — must be `False`.
- `bpy.ops.object.grease_pencil_add` poll fails if the user left an object in EDIT/sculpt/paint mode — `architect_on.py` drops to OBJECT mode at the top.
- Use `bpy.context.temp_override(area=VIEW_3D, region=WINDOW)` when the active area might not be a 3D viewport (e.g. when called via the BlenderMCP socket).

## How to invoke

```python
# Apply look + start orbit
exec(open(r"<repo>/.claude/skills/bead-architect-mode/architect_on.py").read())
exec(open(r"<repo>/.claude/skills/bead-architect-mode/anim_orbit.py").read())

# Switch to a different anim — clears prior animation automatically
exec(open(r"<repo>/.claude/skills/bead-architect-mode/anim_macro_pull.py").read())

# Strip the look entirely
exec(open(r"<repo>/.claude/skills/bead-architect-mode/architect_off.py").read())
```

## Layering with bead-debug-overlays

```python
# 1) Inspection mode: CAD overlays
exec(open(r"<repo>/.claude/skills/bead-debug-overlays/recolor.py").read())

# 2) Drape architect; auto re-tints DBG_* to parchment palette
exec(open(r"<repo>/.claude/skills/bead-architect-mode/architect_on.py").read())

# 3) Loop a tour animation
exec(open(r"<repo>/.claude/skills/bead-architect-mode/anim_tour.py").read())

# 4) Going to print? Use bead-stl-export — it strips everything safely
exec(open(r"<repo>/.claude/skills/bead-stl-export/export.py").read())
```

## Legacy

`legacy/master_architect.py` and `legacy/technical_diagram.py` are the original monolith versions. Superseded by the decomposed `architect_on.py` + `anim_*.py`. Kept on the branch for reference; do not invoke.
