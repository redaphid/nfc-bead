# redaphid-portrait — cartoon self-portrait NFC charm

A two-half snap-fit NFC bead built from a glowy, neon-outlined screenshot of a cartoon self-portrait. **First charm in this repo built from a raster image instead of a hand-drawn SVG.**

## Source

`C:\Users\hypnodroid\Pictures\Screenshots\Screenshot 2026-04-25 235837.png` — a soft pink-glow portrait with a bumpy crown of hair, two drooping ear-flaps on the sides, a chin/neck protrusion, and two warm-orange glowing eyes inside a dark plum head. The user described it as "a cartoonish version of me".

## Why this charm exists

To stress-test the generic NFC bead pipeline with a SOURCE FORMAT it hadn't supported before — a raster screenshot with no clean vector input. Earlier charms in this repo (Wooli mammoth, Rezz spiral) all started from SVG paths the user could hand-tune. This one tested whether the recipe could absorb an image-derived silhouette + a multi-color region split, end-to-end.

The pipeline that came out of this iteration is the contribution. The charm itself is a side-effect.

## The pipeline that came out of this

`extract_silhouette.py` is a host-side Python script that does, in order:

1. **Gaussian blur** the screenshot to denoise.
2. **Luminance-threshold** to a binary figure mask (background ≈ 0, figure ≈ 25+).
3. **Fill holes + keep largest component** to recover the silhouette mask.
4. **Marching-squares contour trace** on the silhouette mask.
5. **Fourier-descriptor smoothing** to drop high-freq wobble — emits a clean polygon as `silhouette.svg`.
6. **Eye detection** by `R − B` chroma channel — pink outline has high B (cancels out), warm orange eyes are R-dominant. Centroid + radius per blob → `<circle>` elements in `silhouette.svg`.
7. **Hair-shape detection** geometrically: above an eyebrow line (anchored to eye Y) + far from the central column (anchored to eye spacing). Emits `hair.svg`. Chin/neck below the jawline stays out → it's automatically face/skin.

Pipeline borrowed and stripped down from [`laser-cube-driver`](D:\Projects\laser-cube-driver) — the same Sobel + flood-fill + Moore-boundary + Fourier-smooth chain it uses to feed a LaserCube projector. That repo (`shader-to-laser-path` / `ContourTracer.js`) was the reference; this script is the host-Python translation.

Then `build_redaphid.py` imports both SVGs into Blender and runs the canonical NFC-bead recipe: scale to 25 mm wide, extrude to 4 mm, drill the string hole, box-cut split, NFC pocket on Bottom, peg/socket pair, hair slab on top of Top, eye dots on top of that.

## Key creative decisions (and tradeoffs)

| Decision | Why | Cost |
|---|---|---|
| Thinner than default (4 mm vs 5 mm) | Charm reads less chunky on a kandi bracelet | `PEG_HEIGHT` drops to 1.0 mm to keep ≥ 0.5 mm wall above sockets |
| Multi-color regions: body / hair / eyes | Centauri Carbon 2 has multi-filament; flatness is a waste of it | Adds a `Hair` STL on top of the canonical 3 — required updating the export skill + 3MF builder |
| Real face/hair contour, not an ellipse | An ellipse-cutout face looked like a Picasso decomposition; the user wanted the haircut to read as hair | Extra extraction stage; needs eye positions as anchors |
| Hair sits ON TOP of full-silhouette show face (additive) instead of cutting the face out (subtractive) | "Hair drapes over the face" is the right mental model; chin/neck stays as skin automatically | Requires the SVG-frame fix (gotcha #15) |
| String hole y=7.5 (low in hair band, not at top) | Load-bearing wall ≥ 2 mm; the bead hangs off a bracelet | Hair extraction has to leave a wider hair band for the hole to fit cleanly |
| Pegs on Bottom (recipe default), not Top | Pegs on Top + show-face decoration is unprintable (cantilever, can't flip) | None — this was a wrong turn we backed out of (gotcha #14) |

## What's transferable to future charms

- **The `extract_silhouette.py` pipeline** is mostly reusable for any glowy-outlined source image. The eye-detection step is specific to "warm dot inside a cool body"; the hair-detection step is specific to characters where eye position is a useful anchor. Other characters may need different region-extractors (a halo? a hat? an animal's ear vs leg?).
- **The "Hair as additive overlay on full show face"** pattern generalizes — anywhere you want a multi-color charm where one color is "the body" and another is a draped/raised region.
- **Gotchas #13–#20** in `prompts/nfc-bead/prompt.md` are all generic — they applied here but will trip up any charm with a centered-mesh build pipeline.

## What's specific to this charm

- The HAIR_*_FACTOR knobs in `extract_silhouette.py` are tuned for THIS portrait's proportions (eye spacing, head height). Other portraits with different proportions will need re-tuning.
- The eye R-B threshold of 30 was set by sampling pixels in this specific screenshot. A different rendering style (cooler eyes, or eyes that aren't warm-dominant) would miss.
- `silhouette.svg` and `hair.svg` are committed because they're the actual derived geometry — they're the contract between the extraction script and the build script. If the source image changes, regenerate them.

## Print notes (v2 onward)

Bottom prints with **silhouette face UP** so the back-decoration (HairBack +
DecorationBack) lands raised on top, mirroring the front. Pegs hang
DOWN as a consequence — **they cantilever onto the build plate**. The
slicer (Elegoo Slicer for the Centauri Carbon 2) will flag this and
ask for supports.

Decision (after v1's failed-grip print):

- **Slicer supports under the pegs.** Use tree supports or normal
  supports limited to the peg region only — no need to support the
  body itself. Supports leave small marks on the silhouette face
  underside; acceptable for the back of a portrait charm.
- *Alternative considered:* 3-piece bead with separate peg cylinders
  and sockets on both halves. Cleaner print, more assembly. Skipped
  for now in favor of fewer parts.

Other v2 settings carried over from the recipe defaults: PLA or PETG,
0.12–0.16 mm layer height, 100 % infill (parts are tiny). Filament
assignments after import: body filament for `Bottom` + `Top`, hair
filament for `Hair` + `HairBack`, eye-glow filament for `Decoration`
+ `DecorationBack`.

## Files

- `silhouette.svg` — outer-outline contour + eye `<circle>` elements
- `hair.svg` — haircut-shape contour (top hair + side ear-flaps)
- `extract_silhouette.py` — screenshot → SVGs (uses scipy + skimage)
- `build_redaphid.py` — SVGs → Blender → STLs (CONFIG block at top)
- `redaphid-portrait.blend` — working scene snapshot, refreshed on every successful build
- `stages/` — milestone `.blend` snapshots
- `print/` — STLs + 3MF (drag `redaphid-portrait.3mf` into Elegoo Slicer)
