# Iter 03 — ink color + radius tuning

## Hypothesis under test
1. Graphite ink `(0.08, 0.10, 0.14)` per SKILL.md will read as drafting pen, slightly softer than pure black.
2. Some radius value between 0.025 and 0.05 will be the sweet spot — thin enough to feel like a pen, thick enough to read cleanly without aliasing.

## What I changed (no script edits)
- `target_material` (`Black.002`) GP color: `(0,0,0,1)` → `(0.08, 0.10, 0.14, 1.0)` graphite
- Rendered 3 variants of `mod.radius`: 0.025, 0.035, 0.050

## What I see in the three renders
- **A `radius=0.025`**: Ink reads thin, feels like a pencil sketch — but the outlines are weak; bottom puck outline is barely there at this camera distance. Spiral inner curves are present but anemic.
- **B `radius=0.035`**: Crisp drafting-pen feel. All outlines read cleanly. Spiral curves fully visible without crowding. **Winner.**
- **C `radius=0.050`**: Bold, almost felt-tip. The spiral's tightest inner ring starts to blend with its neighbor (ink gets too thick relative to gap width). Loses detail.

The graphite vs pure-black difference is hard to see at viewing size — `(0.08, 0.10, 0.14)` is so dark it reads as black anyway. Cool tint registers only on close inspection. Acceptable per spec; not a forcing function.

## Verdict
- ✅ HYPOTHESIS VERIFIED: 0.035 is the radius sweet spot for the canonical wide shot (camera y=-50, lens 50mm, scene scale ~25mm bead halves at ±18 mm)
- ✅ Graphite ink color works (effectively reads as black at this saturation; adds nothing visible vs pure black, but stays inside SKILL.md spec)
- ⚠️ Radius will need to scale with camera distance — at macro pull-in (cam y=-15) the same 0.035 will look thick; at top-down plate (cam z=+45) it may look thin. Document a heuristic in iter 04+.

## Settings that worked
```python
mod.radius = 0.035
target_material.grease_pencil.color = (0.08, 0.10, 0.14, 1.0)  # graphite
gp.show_in_front = False
```

## Next iteration
**Iter 04**: add the graph-paper plate beneath the bead. This is the biggest remaining piece of the master_architect aesthetic — the parchment world should read as actual drafting paper with a faint grid. Plan: a 200×200 plane at z just below the bead's lowest face, with a procedural shader that mixes parchment base with thin blue minor lines (every 1 unit) and slightly darker major lines (every 5 units). Test whether the grid reads as "graph paper" or as "noisy distraction."
