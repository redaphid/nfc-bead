# Iter 02 — add Grease Pencil ink edges

## Hypothesis under test
Adding GP line-art (LINEART_SCENE) over the iter 01 watercolor washes will rescue the under-saturated body silhouettes. Specifically: the sage top body that was nearly invisible against parchment will become legible because its silhouette will be defined by dark ink, not by the close-to-parchment fill color.

## What I changed (no script edits — direct MCP)
- Added a `MA_LineArt` GP object via `bpy.ops.object.grease_pencil_add(type='LINEART_SCENE')`
- LINEART modifier: `source_type='SCENE'`, `use_intersection=True`, `use_contour=True`, `use_crease=True`, `use_edge_mark=True`, `use_material=False`, `opacity=1.0`
- Target material: `Black.002` (auto-created, color `(0,0,0,1)`, `show_stroke=True`, `show_fill=False`)
- Layer not hidden, not locked, opacity 1.0

## Bug found and fixed: Blender 5.0 GP API
The CLAUDE.md hypothesis list was almost entirely correct, but one detail was wrong: in Blender 5.0 the GP LineArt modifier no longer has a `thickness` attribute. Setting `mod.thickness = 25` raises `AttributeError`. The actual stroke-thickness control is `mod.radius` (default `0.0025` — far too thin to render visibly).

Two attribute changes made the lines appear:
1. `mod.radius = 0.05` (20× default)
2. `gp.show_in_front = False` (was `True`; confirmed CLAUDE.md hypothesis #3 — `show_in_front=True` does NOT composite correctly in Cycles, even for final render not just viewport)

Saved as `render.png` (was `render_attemptB_radius0p05_notInFront.png`).

## What I see in `render.png` (cold reading)
- Both bodies now have **crisp dark silhouettes** — the bottom puck has a full outline including the notch cut by the string hole; the top body is fully outlined
- The bronze spiral has **clean traced curves** along every edge of the ribbon — reads as draftsman's pen, not a 3D model
- The boundary between spiral (raised) and top-body (host) is a clean ink crease
- Top body sage `(0.70, 0.80, 0.74)` is now legible against parchment — it doesn't matter that the colors are close because the ink does the work
- Bottom blue-gray reads cleanly as a colored wash inside its ink outline
- Composition reads as **a hand-drafted architectural plate** — pencil-and-watercolor on cream paper, exactly the master_architect goal
- Lighting is still flat (single sun, no rim) — bodies look like printed sheets pasted on paper, not modeled forms. That's actually FINE for this aesthetic — the goal is "ink-and-fill" not photoreal

## Verdict
- ✅ HYPOTHESIS VERIFIED: ink edges rescue under-saturated washes
- ✅ The sage top-body now reads against parchment (was nearly invisible in iter 01)
- ✅ GP line art works in Blender 5.0 + Cycles render — must use `radius` not `thickness`, must set `show_in_front=False`
- ✅ The watercolor + parchment + ink edges combination is producing the master-architect aesthetic the user described
- ⚠️ Pure black ink `(0,0,0)` works but might be too stark — the SKILL.md spec is graphite-cool `(0.08, 0.10, 0.14)`. Test in iter 03.
- ⚠️ Radius 0.05 looks right at this camera distance (y=-50, lens 50mm). May need to scale with camera distance for macro shots.

## Next iteration
**Iter 03**: tweak ink color to graphite `(0.08, 0.10, 0.14)` per SKILL.md and try `radius = 0.025` and `radius = 0.035` for comparison. Pick the combination that reads as drafter's pen (slightly soft), not pure machine line.

## Settings that worked (record for the eventual script update)
```python
gp.show_in_front = False      # critical for Cycles
mod.radius = 0.05             # in Blender 5.0; replaces the old `thickness`
mod.opacity = 1.0
mod.source_type = 'SCENE'
mod.use_intersection = True
mod.use_contour = True
mod.use_crease = True
# target_material auto-created as Black.002 with show_stroke=True, show_fill=False
```
