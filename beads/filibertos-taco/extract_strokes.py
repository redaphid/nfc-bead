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
from skimage.morphology import skeletonize

SRC = Path('beads/filibertos-taco/just-taco.jpg')
OUT = Path('beads/filibertos-taco')
TARGET_WIDTH_MM = 25.0
STROKE_WIDTH_PX = 7        # ~0.50 mm wide neon line. Larger reads bolder
                           # but pushes the inner ring perilously close to
                           # the outer; >8 collapses the ring into a disc
                           # for thin strokes.
FOURIER_HARM = 18
STROKE_BLUR_SIGMA = 0.0    # NO mask pre-blur on stroke contours — blurring
                           # narrow rings can collapse them when the inner
                           # boundary crosses the outer (catastrophic non-
                           # manifold). Keep raw stair-step contour; rely on
                           # repair_manifold() in the build pipeline to
                           # clean small post-boolean artifacts.

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
def merge_blobs(mask, dilate_iters=14, smooth_sigma=2.0):
    """Merge fragmented blobs into one smooth shape: dilate to bridge gaps,
    erode back, fill holes, gaussian-smooth the boundary, keep the largest
    component. The post-merge gaussian gives the bottom-edge a clean curve
    instead of a stair-step row of pixels."""
    closed = ndimage.binary_dilation(mask, iterations=dilate_iters)
    closed = ndimage.binary_erosion(closed, iterations=dilate_iters)
    closed = ndimage.binary_fill_holes(closed)
    if smooth_sigma > 0:
        closed = ndimage.gaussian_filter(closed.astype(np.float32),
                                         sigma=smooth_sigma) > 0.5
    labeled, n = ndimage.label(closed)
    if not n: return closed
    sizes = ndimage.sum(closed, labeled, range(1, n+1))
    return labeled == 1 + int(np.argmax(sizes))

lettuce_blob = merge_blobs(lettuce_full, dilate_iters=14, smooth_sigma=2.0) & silhouette

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

def mask_to_paths(mask, smooth=True, harm=FOURIER_HARM, min_area=80,
                  pre_blur_sigma=STROKE_BLUR_SIGMA):
    """Trace contours of `mask`, gaussian-pre-blurring first.

    NO per-contour Fourier smoothing — for ring strokes, smoothing outer+inner
    edges independently makes them cross, producing self-intersecting volumes.
    Pre-blurring the binary mask (then re-threshold) rounds the stair-step
    pixel boundary at the SOURCE so both contours of a ring follow the same
    smooth curve and stay parallel."""
    if pre_blur_sigma > 0:
        mask = ndimage.gaussian_filter(mask.astype(np.float32), sigma=pre_blur_sigma) > 0.5
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

# ── Cheese / salsa accent strokes ──────────────────────────────────
# A few short curved strokes inside the filling region — readable as
# "stuff in the taco" (cheese drips, salsa squiggles). Each is a thin
# stroke ring in its own region so the slicer can paint it a 3rd filament
# (red or navy). Procedurally generated relative to the silhouette bbox
# so they stay inside the printable area.
y_top = ys_o.min()
y_bot = ys_o.max()
x_left = xs_o.min()
x_right = xs_o.max()
W_px = x_right - x_left
H_px = y_bot - y_top

# Centerline polylines (image-pixel coords, format [(y,x),...]) for 3 accents:
#   - 2 short vertical "cheese drips" hanging off the filling line
#   - 1 horizontal "salsa squiggle" higher up
def lin(p0, p1, n=20):
    return [(p0[0] + (p1[0]-p0[0])*t/(n-1), p0[1] + (p1[1]-p0[1])*t/(n-1)) for t in range(n)]
def arc(cy, cx, r, a0, a1, n=24):
    import math
    return [(cy + r*math.sin(a0 + (a1-a0)*t/(n-1)), cx + r*math.cos(a0 + (a1-a0)*t/(n-1))) for t in range(n)]

# Place accents relative to the lettuce_blob's bottom edge centroid
# rather than fixed bbox positions, so they track the actual filling.
import math
ys_bot, xs_bot = np.where(bottom_edge_pixels)
if len(ys_bot):
    cx_fill = int(np.mean(xs_bot))
    cy_fill = int(np.mean(ys_bot))
else:
    cx_fill = (x_left + x_right) // 2
    cy_fill = (y_top + y_bot) // 2

# Interior-detail strokes — the squiggly red lines visible INSIDE the
# lettuce in the source JPG (leaf veins / texture). These are the
# Filibertos depth cue: they suggest the taco has stuff in it.
#
# Extraction: take the red-outline color mask, subtract the outer perimeter
# stroke. What's left = interior red detail lines, which lie inside the
# lettuce region in the source image. Aggressively filter to keep only
# the longer fragments — short noise blobs would print as random dots.
# Source has many short curvy red squiggles INSIDE the lettuce (leaf
# veins / filling texture). Emulate with a handful of short S-curves
# placed in the lettuce blob — keeps the design clean (3-5 strokes,
# not 30) and prints reliably without skeleton-fragmentation issues.
ys_l, xs_l = np.where(lettuce_blob)
if len(ys_l):
    lx_min, lx_max = xs_l.min(), xs_l.max()
    ly_min, ly_max = ys_l.min(), ys_l.max()
else:
    lx_min, lx_max = x_left, x_right
    ly_min, ly_max = y_top, y_bot
lW = lx_max - lx_min; lH = ly_max - ly_min
lcx = (lx_min + lx_max) // 2; lcy = (ly_min + ly_max) // 2

def s_curve(start_yx, dy, dx, wobble=6, n=18):
    """A short S-curved stroke from start_yx, ending at +(dy, dx).
    `wobble` is perpendicular sway in px."""
    sy, sx = start_yx
    poly = []
    for t in range(n):
        u = t / (n - 1)
        # straight from start to end
        py = sy + dy * u
        px = sx + dx * u
        # perpendicular wobble (sin curve fading at endpoints)
        wob = wobble * math.sin(u * math.pi)
        # perpendicular direction
        L = math.hypot(dy, dx) + 1e-6
        py += wob * (-dx) / L
        px += wob * ( dy) / L
        poly.append((py, px))
    return poly

# 4 short veins inside the lettuce blob, varying angle + position so
# they look organic. Coordinates relative to lettuce bbox.
accents_polys = [
    s_curve((ly_min + lH*0.40, lx_min + lW*0.18), dy=lH*0.20, dx=lW*0.10, wobble=5),
    s_curve((ly_min + lH*0.55, lx_min + lW*0.45), dy=lH*0.15, dx=-lW*0.08, wobble=-4),
    s_curve((ly_min + lH*0.30, lx_min + lW*0.65), dy=lH*0.18, dx=lW*0.05, wobble=4),
    s_curve((ly_min + lH*0.50, lx_min + lW*0.80), dy=lH*0.20, dx=-lW*0.10, wobble=-5),
]

def polyline_to_mask(poly, h_w, shape):
    m = np.zeros(shape, dtype=bool)
    for y, x in poly:
        yi, xi = int(round(y)), int(round(x))
        if 0 <= yi < shape[0] and 0 <= xi < shape[1]:
            m[yi, xi] = True
    return ndimage.binary_dilation(m, iterations=h_w)

interior_detail = np.zeros_like(silhouette)
for p in accents_polys:
    interior_detail |= polyline_to_mask(p, max(2, half-1), silhouette.shape)
interior_detail &= lettuce_blob   # clip to inside lettuce so strokes stay
                                  # in the filling, not poking into the shell
print(f"interior_detail: {interior_detail.sum()} px in "
      f"{ndimage.label(interior_detail)[1]} stroke(s)")

write_svg(OUT/'stroke_accents.svg',
          mask_to_paths(interior_detail, harm=FOURIER_HARM, min_area=20),
          '#e63946')

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
# accents tinted above where they exist
np.clip(overlay, 0, 255, out=overlay)
Image.fromarray(overlay.astype(np.uint8)).save(OUT/'stroke_debug.png')
print(f"  wrote {OUT/'stroke_debug.png'}")
