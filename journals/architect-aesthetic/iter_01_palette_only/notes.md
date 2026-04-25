# Iter 01 — palette only (no ink lines, no graph paper, no plate)

## Hypothesis under test
The watercolor-wash palette from `master_architect.py` (blue-gray bottom `(0.62, 0.74, 0.82)`, sage top `(0.70, 0.80, 0.74)`, warm bronze spiral `(0.85, 0.62, 0.32)`) on a warm-cream parchment world `(0.93, 0.86, 0.72)` will read as a coherent, differentiated set of forms WITHOUT yet adding GP line art or a graph-paper plate. This is the bare-palette claim.

## What I changed (no script edits)
- Set world background to `(0.93, 0.86, 0.72)` parchment cream
- `rezz_bottom` → blue-gray wash (Roughness 0.85, Metallic 0)
- `rezz_top_body` → sage wash (same)
- `rezz_top_spiral` → warm bronze (same)
- Single warm Sun at `(8, -6, 30)`, energy 3.0, color `(1.0, 0.92, 0.78)`
- Killed the AREA fill light (energy 0)
- Camera at canonical `(0, -50, 18)`, lens 50mm
- Killed all camera/pivot animation for a clean still

Render: 1600×900, Cycles+OptiX, 64 samples, OptiX denoising.

## What I see in `render.png` (cold reading)
- Background reads correctly as warm cream parchment.
- **Bronze spiral is the standout** — clearly readable, distinctly raised, the strongest element on screen.
- Bottom half (left) reads as a pale blue-gray puck with a faint cast shadow. Legible silhouette.
- **Top body (right) is nearly invisible** — sage `(0.70, 0.80, 0.74)` is too close to parchment `(0.93, 0.86, 0.72)`; only the bronze spiral on top tells me it's there.
- Without ink lines, the body silhouettes are just gradient blobs against the paper. The spiral works because of color contrast; the bodies don't because their colors are too similar to parchment.
- Lighting is flat — the cast shadows are subtle, the bodies look like cardboard cutouts pasted on paper, not modeled forms.

## Verdict
- ✅ Parchment value is right
- ✅ Bronze spiral value is right
- ❌ Sage top-body is too close to parchment — needs more saturation OR a different hue
- ⚠️ Blue-gray bottom is borderline — readable but desaturated
- ⚠️ The whole composition is dependent on edge definition we don't have yet (no GP ink lines)

## Next iteration
**Iter 02**: add the Grease Pencil line-art object. Hypothesis: ink edges will rescue the under-saturated body washes by giving them sharp silhouettes and crease lines, and the watercolor washes will start reading as INTENDED watercolor — quiet fills under heavy ink. CLAUDE.md notes the GP modifier `thickness` should be int (~25 line points), and `show_in_front=True` may interact badly with Cycles RENDERED — I'll set both, screenshot, then if invisible try the listed hypotheses in order.
