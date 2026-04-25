---
name: bead-debug-colors
description: Recolor an NFC bead's structural elements with distinct high-contrast colors and add wireframe overlays for hidden features (peg positions, NFC pocket, string hole). Use when the user is visually debugging the bead in Blender and wants to distinguish parts at a glance — triggers on "debug colors", "color the parts differently", "I can't tell which is which", "highlight the structure", "show me where the pegs are", or similar visual-disambiguation requests. Requires the Blender MCP to be connected.
---

# Bead Debug Colors

When the user is debugging the bead visually and the default red-everywhere coloring makes it hard to talk about what's where, apply distinct colors to each structural element and add wireframe overlays for features that are otherwise hidden inside the geometry.

## Color palette (memorize these — they're the convention)

| Element | Color | RGBA |
|---|---|---|
| `Bottom` half | **CYAN** | `(0.10, 0.80, 0.95, 1)` |
| `Top` body | **BLUE** | `(0.20, 0.30, 0.95, 1)` |
| Decoration (spiral / emboss / accent) | **MAGENTA** | `(1.00, 0.10, 0.65, 1)` |
| Pegs (overlay) | **YELLOW** | `(0.95, 0.85, 0.10, 1)` |
| Peg holes (overlay) | **GREEN** | `(0.10, 0.95, 0.30, 1)` |
| NFC pocket (overlay) | **ORANGE** | `(1.00, 0.55, 0.10, 1)` |
| String hole (overlay) | **GREEN cylinder** | `(0.30, 1.00, 0.40, 1)` |

The printable parts (Bottom, Top, decoration) get **solid materials**. The hidden features (pegs, peg holes, NFC pocket, string hole) get **wireframe overlay objects** named `DBG_*` so they don't occlude the actual geometry but still mark where the features live.

## Pattern

1. **Read the build script's CONFIG block** (`beads/<name>/build_<name>.py`) to find the actual peg positions, NFC center, hole position, and the print-layout X positions for the two halves (typically `±18 mm`).
2. **Repaint the three printable objects** with the solid colors. Replace existing materials, don't append.
3. **Remove any existing `DBG_*` overlays** from a prior debug pass before adding new ones, so the count stays correct.
4. **Compute overlay world positions from each object's `matrix_world`**, not from guessed math. The bottom half is flipped 180° around X then translated, so its features end up at `bottom.matrix_world @ Vector(local_feature_pos)`. Don't try to flip-then-mirror in your head — read the matrix.
5. **Set each overlay's `display_type = 'WIRE'`** so it shows the feature outline without blocking the view of the actual geometry.
6. **Don't union or boolean the overlays into anything** — they're throwaway visualization objects. Removed cleanly with the `DBG_*` prefix filter.

## Snippet

A working implementation lives at `.claude/skills/bead-debug-colors/recolor.py`. Read it, adapt the CONFIG values to the current bead (positions usually come from `beads/<name>/build_<name>.py`), and run via the MCP `execute_blender_code`. The script is idempotent — running it twice produces the same scene state.

## When NOT to use

- If the user is in production mode (about to export STLs) — debug colors don't carry through to STL exports (STL has no material info), but the overlay objects would clutter the .blend if accidentally exported. Stick to debug colors during inspection only.
- If only ONE color question is being asked ("which one is the spiral?") — just answer the question; don't recolor everything for one query.

## Cleanup

To remove the debug coloring and overlays:
```python
# Remove all DBG_* overlay objects
for obj in list(bpy.data.objects):
    if obj.name.startswith("DBG_"):
        bpy.data.objects.remove(obj, do_unlink=True)
# Restore production materials by re-running the build script (which re-applies them)
exec(open(r"<repo>/beads/<name>/build_<name>.py").read())
```
