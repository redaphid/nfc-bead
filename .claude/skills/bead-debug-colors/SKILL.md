---
name: bead-debug-colors
description: Recolor an NFC bead's structural elements with distinct high-contrast colors and add wireframe overlays for hidden features (peg positions, NFC pocket, string hole). Use when the user is visually debugging the bead in Blender and wants to distinguish parts at a glance — triggers on "debug colors", "color the parts differently", "I can't tell which is which", "highlight the structure", "show me where the pegs are", or similar visual-disambiguation requests. Requires the Blender MCP to be connected.
---

# Bead Debug Colors

When the user is debugging the bead visually and the default red-everywhere coloring makes it hard to talk about what's where, apply distinct colors to each structural element and add wireframe overlays for features that are otherwise hidden inside the geometry.

## Two modes — debug (CAD) and production (true colors)

The skill ships two scripts so the user can flip between debug and final views without reloading the .blend or re-running the build:

| Goal | Script | Effect |
|---|---|---|
| Visually disambiguate parts during inspection | `recolor.py` | applies CAD palette, adds `DBG_*` overlays for hidden features |
| Return the scene to what the slicer would see | `restore.py` | wipes `DBG_*` overlays, repaints bodies with production colors |

Both scripts are idempotent. Switching back and forth is fast (no rebuild). When the user is done debugging or wants to compare against the "true" look, run `restore.py`.

## CAD palette (recolor.py — debug mode)

Engineering drawing convention: **positive features (added material) are solid warm; negative features (voids) are wireframe cool/red.** Bodies are muted blueprint tones so the brightly-colored features pop against them.

| Element | Color | Display | Meaning |
|---|---|---|---|
| `Bottom` half | blueprint blue-gray `(0.55, 0.68, 0.78)` | solid, flat-shaded | host body |
| `Top` body | blueprint sage `(0.62, 0.74, 0.70)` | solid, flat-shaded | host body (different tint to read separately) |
| Decoration (spiral / emboss / accent) | warm bronze `(0.82, 0.55, 0.20)` | solid, flat-shaded | raised relief |
| Pegs (`DBG_Peg*`) | **solid YELLOW** `(1.00, 0.82, 0.10)` | TEXTURED | **positive** — added material |
| Peg holes (`DBG_PegHole*`) | wireframe RED `(0.92, 0.15, 0.15)` | WIRE | **negative** — void |
| NFC pocket (`DBG_NFCPocket`) | wireframe MAGENTA `(0.88, 0.15, 0.78)` | WIRE | **negative** — void |
| String hole (`DBG_StringHole_*`) | wireframe ORANGE `(1.00, 0.50, 0.10)` | WIRE | **negative** — void (long cylinder along X) |

**Why the convention:** at a glance, anything in solid yellow is *real, printable, fused-on material*; anything in red/magenta/orange wireframe is *missing material* (a recess, a hole, a slot). Pegs and peg holes are clearly differentiated — yellow solid vs red wireframe — even though they live at almost the same X/Y positions on opposite halves.

## Production palette (restore.py — true colors)

Mirrors what the build script applies and what the slicer renders. Defaults match the rezz bead (red bodies, black spiral); update the CONFIG block at the top of `restore.py` for other beads.

| Element | Color | Notes |
|---|---|---|
| `Bottom` half | `(0.85, 0.10, 0.10)` | red — matches printed filament |
| `Top` body | `(0.85, 0.10, 0.10)` | red |
| Decoration | `(0.05, 0.05, 0.05)` | near-black — matches printed filament |

## Pattern

1. **Read the build script's CONFIG block** (`beads/<name>/build_<name>.py`) to find the actual peg positions, NFC center, hole position, and the print-layout X positions for the two halves (typically `±18 mm`).
2. **Repaint the three printable objects** with the solid colors. Replace existing materials, don't append.
3. **Remove any existing `DBG_*` overlays** from a prior debug pass before adding new ones, so the count stays correct.
4. **Use explicit world coordinates from the canonical print-layout**, not chained `matrix_world` lookups. The bottom is flipped + recentered, so its mesh-local frame meaning shifts after `transform_apply` — guessed local coords won't survive. The print-layout convention (BOTTOM_X = −18, TOP_X = +18, +Y mirrors to −Y on bottom) is stable.
5. **Solid display for positive features** (pegs), **wireframe display for negative features** (holes, pockets, slots) — that's what makes pegs vs peg holes readable at a glance even when they overlap.
6. **Don't union or boolean the overlays into anything** — they're throwaway visualization objects. Removed cleanly with the `DBG_*` prefix filter (`restore.py` does this for you).

## How to invoke

Both scripts use `execute_blender_code` with `exec(open(...).read())`:

```python
# Enter debug mode (CAD palette + overlays)
exec(open(r"<repo>/.claude/skills/bead-debug-colors/recolor.py").read())

# Return to production colors (wipes overlays)
exec(open(r"<repo>/.claude/skills/bead-debug-colors/restore.py").read())
```

Both have a CONFIG block at the top — adapt to the active bead. For `recolor.py`, pull peg / NFC / hole positions from `beads/<name>/build_<name>.py`. For `restore.py`, pull material colors from the build script's `make_material(...)` calls.

## When NOT to use

- If about to export STLs — debug colors don't carry through to STLs (no material info), but the overlay objects would clutter the `.blend` if exported. Run `restore.py` first if exporting from a debug-colored scene.
- If only ONE color question is being asked ("which one is the spiral?") — just answer it; don't recolor everything for one query.
