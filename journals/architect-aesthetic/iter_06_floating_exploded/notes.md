# Iter 06 — floating + exploded vertical layout (PRE-CORRECTION — alternative explored)

**Status: superseded by the canonical X=±18 print-layout floating in parchment void.**

After the iter-05 pivot to "no plate, eerily suspended," the first attempt was an EXPLODED VERTICAL stack — bottom puck below at z=-8, top body at z=0, spiral floating at z=+5. The user later corrected this: the bead halves should stay in their canonical X=±18 print-layout orientation, NOT be exploded vertically. The "floating" is achieved by removing the plate; the layout itself stays as it was at session start.

## Shots rendered (vertical-stack layout)

- `render_A_three_quarter.png` — first floating shot, no ink lines yet (GP radius 0.035 wasn't drawing strokes at this scene scale)
- `render_B_technical_3q.png` — radius bumped to 0.05; lines drew but framing was too tight (only saw a sliver of the top body)
- `render_D_canonical_layout_floating.png` — was supposed to be the X=±18 print-layout but wasn't rendered before the user interrupted

## Lessons captured

1. GP `radius` may need to be higher than 0.035 at certain scene scales — confirmed 0.05 reads cleanly. Made 0.05 the new default in `architect_on.py`.
2. Vertical-stack exploded layouts make the spiral hard to read at three-quarter angles (the spiral viewed from below is just a flat ribbon silhouette).
3. The print-layout (X=±18, both halves at low Z) is the right canvas — keep that, just remove the plate.

## Why kept on branch

Useful reference for the GP-radius scale-vs-distance interaction, and as documentation of the dead-end vertical-stack idea so it isn't tried again.
