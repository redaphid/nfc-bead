---
name: bead-debug-overlays
description: Apply or strip CAD-style debug coloring + wireframe overlays for an NFC bead's hidden features in Blender. Use when the user wants to visually disambiguate parts ("color the parts differently", "I can't tell which is which", "show me where the pegs are", "highlight the structure", "what's the NFC pocket", "where does the string hole go"). Adds throwaway DBG_* overlay objects (yellow pegs, red peg-hole wireframes, magenta NFC pocket, orange string hole) so internal features are visible from outside the bead. Requires the Blender MCP to be connected.
---

# Bead Debug Overlays

## Project-wide naming convention (do not deviate)

| Canonical name | Role |
|---|---|
| `Bottom` | bottom half — NFC pocket recess + pegs |
| `Top` | top half — peg holes; outer face hosts the decoration |
| `Decoration` | raised relief on `Top`'s outer face (spiral / emboss / etc.) |

Build scripts (`build_<charm>.py`) MUST produce in-Blender objects with exactly these names. On-disk STL filenames may still be bead-prefixed (e.g. `<charm>_bottom.stl`) since they distinguish across charm projects, but the in-scene names are non-negotiable — skills look these up by exact match with no fallback.

Two scripts that toggle the engineering-drawing visualization for an NFC bead:

| Script | Effect |
|---|---|
| `recolor.py` | Applies CAD palette to the printable bodies + adds throwaway `DBG_*` overlay objects for hidden features (peg cylinders, peg-hole wireframes, NFC pocket, string hole) |
| `restore.py` | Wipes all `DBG_*` overlays and repaints the bodies with production filament colors |

Both are idempotent. Switching back and forth is fast (no rebuild).

## CAD palette

Engineering convention: **positive features (added material) = solid warm; negative features (voids) = wireframe cool/red.**

| Element | Color | Display | Meaning |
|---|---|---|---|
| `Bottom` half | blueprint blue-gray `(0.55, 0.68, 0.78)` | solid, flat-shaded | host body |
| `Top` body | blueprint sage `(0.62, 0.74, 0.70)` | solid, flat-shaded | host body (different tint) |
| Decoration (spiral / emboss / accent) | warm bronze `(0.82, 0.55, 0.20)` | solid, flat-shaded | raised relief |
| Pegs (`DBG_Peg*`) | **solid YELLOW** `(1.00, 0.82, 0.10)` | TEXTURED | **positive** — added material |
| Peg holes (`DBG_PegHole*`) | wireframe RED `(0.92, 0.15, 0.15)` | WIRE | **negative** — void |
| NFC pocket (`DBG_NFCPocket`) | wireframe MAGENTA `(0.88, 0.15, 0.78)` | WIRE | **negative** — void |
| String hole (`DBG_StringHole_*`) | wireframe ORANGE `(1.00, 0.50, 0.10)` | WIRE | **negative** — void (X-axis cylinder) |

**Why this convention:** at a glance, anything in solid yellow is *real, printable, fused-on material*; anything in red/magenta/orange wireframe is *missing material* (a recess, a hole, a slot). Pegs and peg holes are clearly differentiated — yellow solid vs red wireframe — even though they live at almost the same X/Y on opposite halves.

## Production palette (`restore.py`)

Mirrors what the build script applied. Defaults are red bodies + black decoration (the most common two-color setup); override the CONFIG block at the top of `restore.py` per charm.

| Element | Color | Notes |
|---|---|---|
| `Bottom` half | `(0.85, 0.10, 0.10)` | red — printed filament |
| `Top` body | `(0.85, 0.10, 0.10)` | red |
| Decoration | `(0.05, 0.05, 0.05)` | near-black — printed filament |

## How to invoke

```python
# Debug mode: CAD palette + structural-feature overlays
exec(open(r"<repo>/.claude/skills/bead-debug-overlays/recolor.py").read())

# Production palette + wipe overlays
exec(open(r"<repo>/.claude/skills/bead-debug-overlays/restore.py").read())
```

`recolor.py` has a CONFIG block at the top — adapt to the active bead. Pull peg / NFC / hole positions from `beads/<name>/build_<name>.py`. `restore.py` likewise has CONFIG for production colors.

## Pairing with the architect aesthetic

When `bead-architect-mode/architect_on.py` is run AFTER `recolor.py`, it auto-detects the `DBG_*` overlays and re-tints them with a parchment-friendly muted palette so they read as draftsman annotations on cream paper rather than engineering CAD pins. The hue families (yellow=peg, red=hole, magenta=NFC, orange=string) are preserved — only saturation drops.

See `bead-architect-mode/SKILL.md` for the architect-aesthetic counterpart palette values.

## STL export safety

`DBG_*` overlay objects are NOT meant for export. They're throwaway viz objects.

- `restore.py` removes them cleanly via the `DBG_*` prefix filter.
- `bead-stl-export/SKILL.md` (the printable-export skill) defensively strips them before exporting.
- Build scripts like `build_<name>.py` should select export targets by name (`Bottom`, `Top`, decoration), so `DBG_*` is invisible to a name-targeted export anyway.

## Gotchas (verified the hard way)

### Inner-face Z must be computed from the actual mesh bbox

The bottom-half "inner face" (where pegs and the NFC pocket attach) is at different world Z depending on context:

- **Build-pipeline scene**: bottom is recentered after the 180° X-flip so the inner face sits at world `z = 0` and pegs stick down to `z = -PEG_HEIGHT`.
- **STL-imported scene** (the common one — what `tools/launch.ps1` produces): the bottom STL keeps its print-layout `z = 0..4`. Show face is at `z = 0` (touching the build plate), inner face is at `z = zmax - PEG_HEIGHT`, pegs occupy `z = zmax - PEG_HEIGHT..zmax`.

`recolor.py` reads `Bottom`'s actual world Z bbox and computes `_BOTTOM_INNER_Z` from it. **Do not assume `inner_z = 0`** — that bug placed all DBG widgets below the puck.

### `bpy.ops.object.*` requires OBJECT mode

If the user (or a previous script) left an object in EDIT/sculpt/paint mode, every `bpy.ops.object.*` poll fails. `recolor.py` doesn't have this guard yet — `architect_on.py` does. If the recolor errors out partway, drop into OBJECT mode first:

```python
if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
```

## When NOT to use

- If only ONE color question is being asked ("which one is the spiral?") — answer it; don't recolor everything for one query.
- If the user is about to export STLs from a debug-colored scene — run `restore.py` first OR rely on `bead-stl-export` to clean up automatically.
