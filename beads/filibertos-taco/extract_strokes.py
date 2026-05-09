"""Extract STROKE-based SVGs from the taco JPG for a neon-sign / stencil look.

Outputs stroke geometry (thin closed rings, not filled blobs) so the bead
prints as line work on a dark body — synthwave / neon aesthetic.

Strokes generated:
  stroke_silhouette.svg  - outer perimeter ring of the whole taco
  stroke_lettuce_line.svg - boundary between lettuce (top) and shell (bottom)
  stroke_lettuce_veins.svg - interior boundaries inside the lettuce region
                             (where bright/dark green meet → leaf veins)

Each stroke is a closed-polygon ring of width STROKE_WIDTH_MM, output as
filled paths (the slicer treats them as thin filled regions, ~1 perimeter
of the chosen filament).

Run:
    uv run python beads/filibertos-taco/extract_strokes.py
"""
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import measure

SRC = Path('beads/filibertos-taco/just-taco.jpg')
OUT = Path('beads/filibertos-taco')
TARGET_WIDTH_MM = 25.0
STROKE_WIDTH_PX = 6        # stroke width in source-pixel space
                           # at our scale ~0.07 mm/px → ~0.42 mm wide stroke
                           # adjust to taste (4=thin, 8=bold)
FOURIER_HARM = 18

# ── Load ────────────────────────────────────────────────────────────
img = np.array(Image.open(SRC).convert('RGB'))
H, W, _ = img.shape
R, G, B = img[..., 0].astype(np.int16), img[..., 1].astype(np.int16), img[..., 2].astype(np.int16)
bg = (R > 235) & (G > 235) & (B > 235)
fg = ~bg

# ── Color masks (same predicates as the v3 extraction) ──────────────
shell = (R > 200) & (G > 130) & (B < 130) & fg              # yellows
lettuce_dark = (G > R) & (G > B) & (G < 100) & fg
lettuce_light = (G > R) & (G > B) & (G >= 100) & fg
outline_red = (R > 100) & (G < 60) & (B < 60) & fg

def clean(m, close=3, open_=1):
    m = ndimage.binary_closing(m, iterations=close)
    m = ndimage.binary_opening(m, iterations=open_)
    return ndimage.binary_fill_holes(m)

silhouette = clean(fg, close=4, open_=1)
labeled, n = ndimage.label(silhouette)
if n:
    sz = ndimage.sum(silhouette, labeled, range(1, n+1))
    silhouette = labeled == 1 + int(np.argmax(sz))

shell_m = clean(shell, close=2, open_=1) & silhouette
lettuce_full = clean(lettuce_dark | lettuce_light, close=3, open_=1) & silhouette
lettuce_light_m = clean(lettuce_light, close=2, open_=1) & silhouette
lettuce_dark_m  = clean(lettuce_dark,  close=2, open_=1) & silhouette

# ── Strokes via dilate-XOR ───────────────────────────────────────────
half = STROKE_WIDTH_PX // 2
def ring_stroke(mask, half_w):
    """A closed ring along the boundary of `mask`. Width = 2*half_w pixels."""
    inner = ndimage.binary_erosion(mask, iterations=half_w)
    outer = ndimage.binary_dilation(mask, iterations=half_w)
    return outer & ~inner

def boundary_stroke_between(a_mask, b_mask, half_w):
    """A stroke straddling the boundary between two adjacent masks. The
    ring sits half inside `a` and half inside `b`."""
    # boundary = pixels in `a` adjacent to `b`, plus pixels in `b` adjacent to `a`
    b_dilated = ndimage.binary_dilation(b_mask, iterations=half_w)
    a_dilated = ndimage.binary_dilation(a_mask, iterations=half_w)
    return (a_mask & b_dilated) | (b_mask & a_dilated)

silhouette_stroke = ring_stroke(silhouette, half)

# Lettuce-shell DIVIDING LINE: a single curve across the bead width
# tracing where the green filling sits on top of the yellow shell.
# Combined with the silhouette outline, this reads as "taco" (the
# silhouette is the half-circle bun, the line is the open-top split).
#
# Implementation: morph-close the lettuce blob to one shape, then take
# only its BOTTOM-EDGE pixels (where the row below is NOT lettuce).
# That's a thin polyline across the bead. Dilate it to stroke width.
def merge_blobs(mask, dilate_iters=14):
    closed = ndimage.binary_dilation(mask, iterations=dilate_iters)
    closed = ndimage.binary_erosion(closed, iterations=dilate_iters)
    closed = ndimage.binary_fill_holes(closed)
    labeled, n = ndimage.label(closed)
    if not n: return closed
    sizes = ndimage.sum(closed, labeled, range(1, n+1))
    return labeled == 1 + int(np.argmax(sizes))

lettuce_blob = merge_blobs(lettuce_full, dilate_iters=14) & silhouette

# Bottom edge of the lettuce blob: pixels in lettuce_blob whose pixel-down
# is NOT lettuce_blob. (Image Y axis: row+1 is "down" in image coords,
# which is "below" in original-image up-orientation. We're tracing the
# topological lower edge of the lettuce in image space — which IS the
# physical bottom of the lettuce on the printed bead since the source
# JPG has the lettuce on top and shell below.)
shifted_down = np.zeros_like(lettuce_blob)
shifted_down[1:, :] = lettuce_blob[:-1, :]
bottom_edge_pixels = lettuce_blob & ~shifted_down

# Inflate the 1-pixel-thick edge into a stroke
filling_line = ndimage.binary_dilation(bottom_edge_pixels, iterations=half)
filling_line = filling_line & silhouette

# Drop tiny disconnected fragments per stroke
def keep_large(mask, min_px=80):
    labeled, n = ndimage.label(mask)
    if not n: return mask
    sizes = ndimage.sum(mask, labeled, range(1, n+1))
    keep = np.zeros_like(mask)
    for i, sz in enumerate(sizes, 1):
        if sz >= min_px: keep |= labeled == i
    return keep

silhouette_stroke = keep_large(silhouette_stroke, 200)
filling_line      = keep_large(filling_line,      200)

print(f"silhouette_stroke: {silhouette_stroke.sum()} px")
print(f"filling_line:      {filling_line.sum()} px")

# ── Outer bbox (shared coord frame with silhouette.svg) ─────────────
ys_o, xs_o = np.where(silhouette)
bx0, bx1 = xs_o.min(), xs_o.max(); by0, by1 = ys_o.min(), ys_o.max()
SCALE_PX_TO_MM = TARGET_WIDTH_MM / (bx1 - bx0)
Hmm = (by1 - by0) * SCALE_PX_TO_MM
print(f"scale: {SCALE_PX_TO_MM:.4f} mm/px (silhouette {TARGET_WIDTH_MM:.2f}mm × {Hmm:.2f}mm)")

# ── SVG export ──────────────────────────────────────────────────────
def fourier_smooth(contour, harm):
    z = contour[:, 0] + 1j * contour[:, 1]
    Z = np.fft.fft(z)
    msk = np.zeros_like(Z, dtype=bool); msk[0] = True; msk[1:harm+1] = True; msk[-harm:] = True
    return np.fft.ifft(np.where(msk, Z, 0))

def downsample(c, n=300):
    if len(c) <= n: return c
    idx = np.linspace(0, len(c)-1, n).astype(int)
    return c[idx]

def mask_to_paths(mask, smooth=True, harm=FOURIER_HARM, min_area=80):
    """Trace contours of `mask`. NO Fourier smoothing — for ring strokes,
    smoothing outer+inner edges independently makes them cross, producing
    self-intersecting volumes after extrusion → non-manifold STLs.
    Just downsample and use the raw stair-step pixel contours."""
    labeled, n = ndimage.label(mask)
    paths = []
    for k in range(1, n+1):
        comp = labeled == k
        if comp.sum() < min_area: continue
        contours = measure.find_contours(comp.astype(np.uint8), level=0.5)
        for c in contours:
            if len(c) < 16: continue
            c = downsample(c, 300)
            paths.append(c)
    return paths

def write_svg(filename, paths, fill='#000'):
    if not paths: print(f"  (skip {filename} — no paths)"); return False
    Wmm = TARGET_WIDTH_MM
    svg_w = Wmm * 100; svg_h = Hmm * 100
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}">']
    for c in paths:
        ys = c[:, 0]; xs = c[:, 1]
        x_mm = (xs - bx0) * SCALE_PX_TO_MM
        y_mm = (ys - by0) * SCALE_PX_TO_MM
        d = 'M ' + ' L '.join(f'{x*100:.2f},{y*100:.2f}' for x,y in zip(x_mm, y_mm)) + ' Z'
        parts.append(f'<path fill="{fill}" stroke="none" d="{d}"/>')
    parts.append('</svg>')
    open(filename, 'w', encoding='utf-8').write('\n'.join(parts))
    print(f"  wrote {filename} ({len(paths)} path(s))")
    return True

# Each stroke is exported as its own SVG so the build script can pick
# which ones to emboss as separate decoration objects (and assign filaments).
write_svg(OUT/'stroke_silhouette.svg',   mask_to_paths(silhouette_stroke, harm=FOURIER_HARM, min_area=400), '#5dd6ff')
write_svg(OUT/'stroke_filling_line.svg', mask_to_paths(filling_line,      harm=FOURIER_HARM, min_area=400), '#5dd6ff')

# Drop older strokes whose names changed across iterations
for old in ('stroke_lettuce_line.svg', 'stroke_lettuce_veins.svg',
            'stroke_lettuce.svg', 'stroke_shell.svg'):
    p = OUT / old
    if p.exists(): p.unlink()

# Debug overlay
overlay = img.astype(np.float32) * 0.25
def tint(mask, col, alpha=0.85):
    overlay[mask] = (1-alpha) * overlay[mask] + alpha * np.array(col, dtype=np.float32)
tint(silhouette_stroke, (93, 214, 255))
tint(filling_line,      (160, 230, 255))
np.clip(overlay, 0, 255, out=overlay)
Image.fromarray(overlay.astype(np.uint8)).save(OUT/'stroke_debug.png')
print(f"  wrote {OUT/'stroke_debug.png'}")
