---
name: image-to-silhouette
description: Extract a clean SVG silhouette from a raster image (PNG/JPG screenshot, render, photo) ready to feed into the NFC bead recipe. Runs the laser-cube-driver pipeline (gaussian-blur → luminance threshold → fill-holes → moore-boundary → fourier-smooth) plus optional accent-region detectors (warm chroma for eyes, geometric haircut from eye anchors). Use when the user has an image they want to turn into a charm — not a hand-drawn SVG. Triggers on "extract silhouette from image", "make a charm from this picture", "trace this screenshot", or similar.
---

# Image to Silhouette

A host-side Python pipeline that turns a raster image into an SVG bead silhouette. Translation of the contour pipeline from `D:\Projects\laser-cube-driver` (Sobel + flood-fill + Moore-boundary + Fourier-smooth) — but for static images, scaled to mm dimensions, and with optional accent-region detectors.

This skill is the contribution that came out of building `redaphid-portrait`. The silhouette + accent extraction was charm-specific by accident there; this packages it so the next image-derived charm is one prompt instead of three days.

## When to use

- The user has a screenshot, render, or photo and wants to turn it into a 3D-printed charm.
- The image has a clean figure on a dark or transparent background.
- You want a charm-bound SVG (sized to mm, fits a 25 mm bead bbox by default).

Not for hand-drawn SVGs (use them directly via the nfc-bead recipe).

## What it produces

| File | Always | Description |
|---|---|---|
| `silhouette.svg` | yes | Outer outline as a closed `<path>`, fourier-smoothed. Eye `<circle>` elements appended if `--detect-eyes` and the warm-chroma mask finds blobs. |
| `hair.svg` | optional | Geometric haircut shape (silhouette above the eyebrow line + side flaps far from center, bounded above the jawline). Requires `--detect-eyes` since eye positions anchor the haircut zones. |
| `extract_debug.png` | yes | Source image with overlays — silhouette mask tinted, contour stippled, eye markers, hair mask tinted. Sanity-check before importing into Blender. |

## How to invoke

```sh
uv run nfc-image-to-silhouette \
    --src C:/path/to/image.png \
    --out beads/<charm>/ \
    --target-width-mm 25 \
    --detect-eyes \
    --detect-hair          # implies --detect-eyes
```

## Key tunables

```python
LUMA_THRESHOLD       = 22       # luma > this = figure pixel; tune per image
EYE_WARM_MIN         = 30       # R-B threshold for eye chroma
HAIR_EYEBROW_FACTOR  = 0.55     # eyebrow line at eye_y - eye_spacing * this
HAIR_JAWLINE_FACTOR  = 1.4      # jawline at eye_y + eye_spacing * this
HAIR_SIDE_FACTOR     = 1.2      # side hair starts |x-cx| > eye_spacing * this
FOURIER_HARMONICS    = 24       # silhouette smoothing
HAIR_FOURIER_HARM    = 14       # hair contour smoothing (lower = smoother)
```

All overridable on the CLI; sensible defaults match the redaphid-portrait tuning.

## Source-image requirements

- **Background must be distinguishable from figure** — a pure black or transparent background works best. The luma threshold separates background (low luma) from figure (any luma above threshold). If your background is light, invert the image first.
- **Figure should be roughly bead-shaped** — a tall rectangle silhouette works fine; an entire room scene with multiple figures will not.
- **For eye detection**: eyes need to be warm (R > B) while the rest of the figure is cool (R-B near 0 or negative). For a glow-outline portrait this is automatic. For a photograph, eye detection probably won't work — use a different accent-detector or pass eye positions manually.

## Per-image tuning workflow

1. Run with defaults; open `extract_debug.png`.
2. If silhouette mask is too small / leaks: bump or drop `LUMA_THRESHOLD`.
3. If eyes weren't detected: lower `EYE_WARM_MIN` or sample pixel values manually (`uv run python -c "from PIL import Image; ..."`) to find the right channel discriminator for your image.
4. If hair contour is too inward (overlaps eyes): bump `HAIR_SIDE_FACTOR`.
5. If hair drops too low and covers cheeks: drop `HAIR_JAWLINE_FACTOR`.

Each parameter's effect is captured in a known-good example: `beads/redaphid-portrait/extract_silhouette.py` (the original), and the gotcha catalog in `prompts/nfc-bead/prompt.md`.

## Pipeline reference

The exact algorithm chain, lifted from `laser-cube-driver/src/points/ContourTracer.js`:

```
load image
  -> gaussian-blur            (denoise)
  -> luma threshold           (binary figure mask)
  -> morphological close      (bridge gaps in glow-ring sources)
  -> fill holes               (recover interior)
  -> keep largest component   (silhouette body)
  -> marching-squares contour (boundary points, ordered)
  -> downsample to 400 pts    (Fourier overhead)
  -> Fourier truncate to N    (smooth low-freq descriptors)
  -> emit SVG path
```

Eye detection runs in parallel from the raw pixel buffer:
```
  R - B > threshold           (warm-chroma mask)
  -> binary open + close      (denoise blobs)
  -> connected components     (one blob per eye)
  -> centroid + sqrt(area/pi) (cx, cy, r per blob)
  -> emit <circle> elements
```

Hair detection uses eye positions as anchors:
```
eyebrow_y = eye_y - eye_spacing * EYEBROW_FACTOR
jawline_y = eye_y + eye_spacing * JAWLINE_FACTOR
side_dx   = eye_spacing * SIDE_FACTOR

hair_mask = silhouette ∩ (
    (y < eyebrow_y) OR
    (y < jawline_y AND |x - cx| > side_dx)
)
```

## What this skill does NOT do

- It does not import into Blender. After this produces `silhouette.svg`, hand off to the `nfc-bead` skill / build script which knows how to turn an SVG into a printable charm.
- It does not pick a target diameter for you — the user (or build script) decides per-charm. Default 25 mm just normalizes the SVG bbox.
- It does not handle multi-figure compositions. Single connected silhouette only.
