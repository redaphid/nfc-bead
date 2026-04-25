# Iter 05 — DIRECTION PIVOT: eerily suspended, perfect forms

## What changed
After iter 04 verified the graph-paper plate as a "drafting plate" with the bead resting on it, the user redirected: **the bead should NOT appear to rest on anything. Eerily suspended, perfect forms.**

## What this means for the aesthetic
- No plate beneath the bead — kill the floor.
- No cast shadow grounding the bead to a surface.
- The bead floats in space.
- Graph paper still has a role (user emphasized graph-paper focus in an earlier message), but it can NOT be a floor. Options to test:
  1. **Backdrop wall**: a vertical graph-paper plane positioned behind the bead (e.g. at world Y=+30, rotated 90° around X), so the bead floats *in front of* drafting paper.
  2. **World shader graph-paper**: bake the grid into the world background itself — bead floats in an infinite drafting-paper environment.
  3. **No graph paper at all**: bead floats in pure parchment void; reserve graph paper for the static background of OTHER shots if needed.
- Lighting must still create form on the bead (no anchoring shadow on a ground = the bead's self-shading carries all the volumetric reading).
- The "Westworld-intro" reference reinforces this: the player piano, the bull, the bartender's hand — those Westworld pre-credit hero shots are objects suspended in dramatic backlight against simple vignettes, not objects sitting on tables.

## Verified findings still in effect (don't re-verify)
From iters 02–04, these still hold:
- Watercolor washes work: blue-gray bottom, sage top, warm bronze spiral
- Parchment world `(0.93, 0.86, 0.72)` is the right paper color
- GP LineArt with `radius=0.035`, `show_in_front=False`, ink graphite `(0.08, 0.10, 0.14)` reads as drafting pen
- Cycles + OptiX denoiser at 64 samples renders cleanly

## Plan for verification (when Blender MCP reconnects)
1. **Iter 05** (this entry): kill plate, render bead floating in parchment void. Verify the float reads as "eerily suspended."
2. **Iter 06**: graph-paper as backdrop wall behind the bead (vertical plane at Y=+30 or so). Test whether the grid-as-backdrop works.
3. **Iter 07**: try graph-paper baked into the world shader (no plane at all). Compare to iter 06.
4. **Iter 08**: dramatic raking light test — strong rim from above-side, fainter front, deep falloff. Eerie hero-shot lighting.
5. **Iter 09**: camera shot vocabulary on the verified floating scene — wide establishing, locked side profile, top-down (now showing graph paper backdrop, not a "ground"), macro pull-ins to spiral and bottom NFC pocket area.
6. **Iter 10**: stitch the camera shots into a full keyframed sequence (~50s total: wide 10s → side profile 12s → macro spiral 8s → top-down 10s → macro bottom 8s).
7. **Iter 11**: render the full sequence as an MP4. Open the folder in Explorer when done.

## Status
- Blender MCP disconnected; cannot iterate visually right now.
- ScheduleWakeup queued to retry connection.
- All journal entries through iter 04 are committed and pushed.
- This pivot entry is being committed now so the remote view of progress includes the direction change.
