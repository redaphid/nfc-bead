# Rezz NFC Bead

Round 25 mm bead with a raised black hypno-spiral on a recessed red background. Designed for the Centauri Carbon 2 with the ACE Pro multi-color (filament-swap) workflow.

## Files

| Path | Purpose |
|---|---|
| `silhouette.svg` | Input — plain 25 mm circle. The spiral is procedural (not in the SVG). |
| `build_rezz.py` | End-to-end Blender pipeline. Live-MCP-friendly (chunkable) or headless. |
| `print/` | Final STL exports + the workspace `.blend`. Load these into Elegoo Slicer. |
| `stages/NN_*.blend` | Snapshot saves at each meaningful build step. Each has a sibling `NN_*.md` describing the stage and any insights. |
| `stages/NN_*.png` | Viewport preview saved alongside each stage snapshot. |

## Design summary

| Feature | Value | Why |
|---|---|---|
| Silhouette | 25 mm circle | Standard Kandi bead size |
| Total thickness | 5.5 mm | 2.5 mm bottom + 2.5 mm top body + 0.5 mm raised spiral |
| String hole | 2 mm dia, X axis, Y = +9 mm | Bead lays face-forward when threaded on a wrist |
| NFC pocket | 10.5 mm dia × 0.8 mm deep, centered (0, −1) | NTAG215 sticker, slight south shift to clear string hole |
| Pegs | 3 × 2 mm dia × 1.5 mm | Triangulated: (−7.5, +3), (+7.5, +3), (0, −10) |
| Spiral | 3.5-turn Archimedean, 10 mm outer radius, 1.4 mm arm width | Recognizable hypno-spiral, trimmed above Y = +7 to clear string hole |

## Multi-color print assembly (Elegoo Slicer)

1. Open Elegoo Slicer, load `print/rezz_bottom.stl`, `print/rezz_top_body.stl`, `print/rezz_top_spiral.stl`
2. Right-click `rezz_top_spiral` → **Add as part** of `rezz_top_body` — they merge into one print object with shared filaments
3. Assign filaments:
   - `rezz_bottom` → RED
   - `rezz_top_body` → RED
   - `rezz_top_spiral` (the part) → BLACK
4. Slice; the printer swaps to BLACK only on the very top 0.5 mm of the top half

## Build commands

Headless rebuild from scratch:

```powershell
"D:\tools\blender\blender.exe" --background --python beads/rezz/build_rezz.py
```

Live-MCP rebuild (in a Claude Code session with Blender MCP connected):

```python
exec(open(r"D:\Projects\nfc-bead\beads\rezz\build_rezz.py").read())
```

## Branch convention

This work lives on the `rezz` branch. The generic recipe is on `main`. Per-charm pipeline tweaks that are useful to all charms get cherry-picked to `main`; the rest stay branch-local.
