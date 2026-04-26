---
name: bead-debug-colors
description: Recolor an NFC bead's structural elements with distinct high-contrast colors, add wireframe overlays for hidden features (peg positions, NFC pocket, string hole), or drape a cinematic 'architect' aesthetic over the canvas with parchment+ink+watercolor styling and slow keyframed camera animations. Use when the user is visually debugging the bead, watching the build on a projector, or wants the canvas to look beautiful while Claude is thinking. Requires the Blender MCP to be connected.
---

# Bead Debug Colors + Architect Aesthetic

Two layers of visual tooling for an NFC bead in Blender:

1. **Debug palette** (`recolor.py` ↔ `restore.py`) — CAD-style coloring + structural overlays so you can see the pegs, NFC pocket, and string hole at a glance.
2. **Architect aesthetic** (`architect_on.py` ↔ `architect_off.py` + `anim_*.py`) — drape a hand-drafted parchment-and-ink look over whatever's in the scene, with a library of cinematic camera animations.

The two layers are orthogonal: you can run them independently or stack them. The architect mode optionally re-tints any `DBG_*` overlays from the debug pass with a softer architect-aesthetic palette so they read as draftsman annotations rather than engineering CAD pins.

## Scripts

| Goal | Script | Effect |
|---|---|---|
| Disambiguate parts during inspection | `recolor.py` | applies CAD palette, adds `DBG_*` overlays for hidden features |
| Return to slicer-true colors | `restore.py` | wipes `DBG_*` overlays, repaints bodies with production colors |
| Apply architect aesthetic | `architect_on.py` | parchment world, watercolor washes, GP-line-art ink edges, warm key+cool fill lights, camera rig (no animation) |
| Strip architect aesthetic | `architect_off.py` | removes `MA_*` objects + materials, neutral-greys the world, kills camera animation |
| Slow Z-orbit + wobble + dolly | `anim_orbit.py` | the canonical Westworld-tempo orbit (default 90s/rev) |
| Locked side-profile (static) | `anim_locked_profile.py` | parks camera at eye-level, holds the silhouette |
| Top-down 'blueprint plate' (static) | `anim_top_down.py` | overhead view of the print-layout |
| Macro pull-in | `anim_macro_pull.py` | dolly + lens-zoom from wide to a focused half |
| Raking light | `anim_raking_light.py` | camera holds, key sun rotates around the bead |

All scripts are idempotent. Animation scripts clear any prior camera/sun animation before keying their own — switching between them is safe.

## CAD palette (`recolor.py` — debug mode)

Engineering convention: **positive features (added material) = solid warm; negative features (voids) = wireframe cool/red.** Bodies are muted blueprint tones.

| Element | Color | Display | Meaning |
|---|---|---|---|
| `Bottom` half | blueprint blue-gray `(0.55, 0.68, 0.78)` | solid, flat-shaded | host body |
| `Top` body | blueprint sage `(0.62, 0.74, 0.70)` | solid, flat-shaded | host body (different tint) |
| Decoration (spiral / emboss / accent) | warm bronze `(0.82, 0.55, 0.20)` | solid, flat-shaded | raised relief |
| Pegs (`DBG_Peg*`) | **solid YELLOW** `(1.00, 0.82, 0.10)` | TEXTURED | **positive** — added material |
| Peg holes (`DBG_PegHole*`) | wireframe RED `(0.92, 0.15, 0.15)` | WIRE | **negative** — void |
| NFC pocket (`DBG_NFCPocket`) | wireframe MAGENTA `(0.88, 0.15, 0.78)` | WIRE | **negative** — void |
| String hole (`DBG_StringHole_*`) | wireframe ORANGE `(1.00, 0.50, 0.10)` | WIRE | **negative** — void (X-axis cylinder) |

## Production palette (`restore.py` — true colors)

Mirrors what the build script applies. Defaults match rezz (red bodies, black spiral); update the CONFIG block at the top of `restore.py` for other beads.

| Element | Color | Notes |
|---|---|---|
| `Bottom` half | `(0.85, 0.10, 0.10)` | red — printed filament |
| `Top` body | `(0.85, 0.10, 0.10)` | red |
| Decoration | `(0.05, 0.05, 0.05)` | near-black — printed filament |

## Architect aesthetic — what it does

`architect_on.py` is the toggle for the cinematic look. Reach for it when the canvas is being **watched** for stretches of time (projector, large display, Claude is doing long-running work). Reference: Westworld pre-credits — machined, perfected, clinical, sophisticated.

It sets up:

- **Parchment world** — warm cream `(0.93, 0.86, 0.72)`. No HDRi noise.
- **Watercolor washes per element** — `Bottom` blue-gray, `Top` sage, decoration warm bronze. `Roughness=0.85, Metallic=0`, flat-shaded so the look reads as ink-and-fill, not photoreal. (The `recolor.py` CAD palette translated into quiet washes that sit politely under heavy ink edges.)
- **Grease Pencil scene line-art** — every silhouette / crease / intersection traced as a crisp dark-graphite stroke. **Verified Blender 5.0 settings**: `radius=0.05` (the modifier no longer has a `thickness` attribute) and `show_in_front=False` (`True` does NOT composite correctly in Cycles render).
- **Warm key sun + faint cool fill** — tungsten-warm raking key at `(12,-8,22)`, optional dusty-blue fill from below for shadow detail.
- **Cycles + OptiX** render and viewport — RTX denoiser keeps the live preview responsive.
- **Camera rig** — `CameraPivot` (orbit pivot), `CameraTarget` (aim point, hidden), `Camera` parented to pivot with a `TRACK_TO` constraint on the target. **No animation by default** — pair with one of the `anim_*.py` scripts.

Run `architect_off.py` to wipe everything `architect_on.py` adds and reset the world to neutral grey.

### Architect highlight palette (proposed — for `DBG_*` overlay re-tinting)

When `RETINT_DBG_OVERLAYS = True` in `architect_on.py`, any `DBG_*` overlay objects from a prior `recolor.py` pass get re-tinted with this palette: same hue families as the CAD palette so the visual rule is preserved (yellow=peg, red=hole, magenta=NFC, orange=string), but desaturated to read as draftsman's marker annotations on parchment rather than engineering CAD overlays.

| Element | CAD color (recolor.py) | Architect color | Reading |
|---|---|---|---|
| Pegs | yellow `(1.00, 0.82, 0.10)` | bright muted ochre `(0.92, 0.78, 0.30)` | added material — solid |
| Peg holes | red `(0.92, 0.15, 0.15)` | venetian red `(0.62, 0.22, 0.20)` | void — wireframe |
| NFC pocket | magenta `(0.88, 0.15, 0.78)` | dusty rose `(0.55, 0.30, 0.50)` | void — wireframe |
| String hole | orange `(1.00, 0.50, 0.10)` | drafted rust `(0.78, 0.45, 0.20)` | void — wireframe |

⚠ Status: PROPOSED. These values are tentative until rendered against the parchment+ink composition and verified visually. Adjust in the `architect_on.py` Tunables block.

## Animations — pairing with `architect_on.py`

Each `anim_*.py` requires `architect_on.py` to have set up the camera rig. **All animation scripts produce seamless continuous loops** when Blender's playback wraps from `frame_end` back to `frame_start`:

| Animation | Loop type | How it loops |
|---|---|---|
| `anim_orbit.py` | rotational | Z-orbit goes 0°→360° (visually identical at wrap); X-wobble samples include matched endpoints |
| `anim_raking_light.py` | rotational | sun's location traces a full circle; first and last keyframes are the same (R, 0, Z) point |
| `anim_macro_pull.py` | ping-pong | wide → close at midpoint → wide at end; bezier ease at both extremes; wrap is seamless |
| `anim_locked_profile.py` | trivial | static (single frame) — every wrap is identical |
| `anim_top_down.py` | trivial | static (single frame) — every wrap is identical |

This means: kick off any animation, walk away, the viewport keeps moving forever without a visible jolt.

### `anim_orbit.py` — the canonical Westworld-tempo orbit

| Tunable | Default | Meaning |
|---|---|---|
| `PERIOD` | 2160 frames (90 s @ 24fps) | one full Z revolution |
| `WOBBLE_DEG` | 15.0 | sinusoidal X-tilt amplitude (0 = no wobble) |
| `WOBBLE_SAMPLES` | 36 | keyframe count for the wobble |
| `DOLLY_BREATH` | False | breath-in/out on `cam.location.y` |
| `DOLLY_RANGE` | (-58, -42) | y range when dolly is on |

The original `master_architect.py` used `PERIOD=6000` (4 min/rev) and wobble ±35°. The new `anim_orbit.py` defaults are gentler / faster — adjust to taste.

### `anim_locked_profile.py` — pure stillness

The single most Westworld-feeling shot in the vocabulary. Camera parks at `(0, -55, 2.5)`, lens 60mm, target Z matched to camera Z so the horizon is exactly horizontal. Holds indefinitely.

### `anim_top_down.py` — blueprint-plate stillness

Camera at `(0, 0, 50)` looking straight down, lens 60mm. Note: the `TARGET_LOC` has a tiny non-zero Y offset to avoid a degenerate `TRACK_TO` up-direction when looking exactly straight down.

### `anim_macro_pull.py` — wide → close-up dolly

Camera glides from a wide establishing position (`(0, -55, 18)`, lens 50mm) to a tight macro on one half (`(±18, -18, 6)`, lens 90mm) over `DURATION_SEC` (default 8s). Set `TARGET_X = -18` to focus on the bottom half instead of the top.

### `anim_raking_light.py` — moving light, static camera

The key sun (`MA_Sun_Key`) orbits horizontally around the scene at constant altitude/tilt. Pairs especially well with `anim_locked_profile.py` — locked silhouette while highlights and shadows shift slowly across the form.

## Layering: typical workflows

```python
# 1) Inspection mode — bright CAD colors + structural overlays
exec(open(r"<repo>/.claude/skills/bead-debug-colors/recolor.py").read())

# 2) Cinematic mode on its own — drape architect over whatever's in the scene
exec(open(r"<repo>/.claude/skills/bead-debug-colors/architect_on.py").read())
exec(open(r"<repo>/.claude/skills/bead-debug-colors/anim_orbit.py").read())

# 3) Stack: CAD overlays + architect drape + animation
exec(open(r"<repo>/.claude/skills/bead-debug-colors/recolor.py").read())
exec(open(r"<repo>/.claude/skills/bead-debug-colors/architect_on.py").read())   # auto re-tints DBG_* to architect palette
exec(open(r"<repo>/.claude/skills/bead-debug-colors/anim_locked_profile.py").read())

# 4) Switch animations live — each anim_*.py clears prior animation
exec(open(r"<repo>/.claude/skills/bead-debug-colors/anim_macro_pull.py").read())

# 5) Strip architect, keep DBG_* overlays
exec(open(r"<repo>/.claude/skills/bead-debug-colors/architect_off.py").read())

# 6) Strip everything debug-side, return to production
exec(open(r"<repo>/.claude/skills/bead-debug-colors/restore.py").read())
```

`recolor.py` and `restore.py` each have a CONFIG block — adapt to the active bead. `architect_on.py` and the animation scripts are bead-agnostic; tunables live at the top of each file.

## STL export safety

`architect_on.py` adds objects with the `MA_` prefix (line-art GP, lights, optionally a graph plate) and applies `MA_*` materials to the printable bodies. None of this affects STL export **as long as the build's export call selects objects by name** (which `build_*.py` scripts do — they target `Bottom`, `Top`, decoration explicitly).

Materials don't carry through to STLs anyway. So:

- `MA_LineArt` — GP object, not exportable as STL even if selected
- `MA_Sun_Key`, `MA_Sun_Fill` — non-mesh
- `CameraPivot`, `CameraTarget`, `Camera` — non-mesh
- `MA_*` materials on bodies — ignored by STL export

If you need to be doubly sure (e.g. debugging an export where everything is being included), run `architect_off.py` followed by `restore.py` before exporting.

## When NOT to use the architect mode

- If the user is mid-iteration on geometry and watching the viewport closely — the GP line-art recomputes on every frame change, which can slow viewport response on complex scenes.
- If only ONE color question is being asked ("which one is the spiral?") — answer it directly; don't drape the whole scene.
