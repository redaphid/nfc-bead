"""Extract the cleaned 3-band rainbow PNG into 4 color regions + a FILLED outer
silhouette.

The source (`simplified_rainbow_1024.png`) is a 1024×1024 transparent canvas
with the rainbow centered. The bands are pure colors so extraction is direct
color-matching (with tolerance for Lanczos-resampled edge pixels), not HSV +
radial binning. The silhouette is still computed as the convex hull of the
figure to bridge the hollow under-arch into a closed body for the NFC pocket.

Pure source colors (from sampling):
    wings = (15, 15, 15)
    red   = (200, 24, 24)
    yellow= (230, 198, 30)
    blue  = (28, 95, 184)

Regions emitted to regions.json (shared mm-coordinate frame, origin = bead
center, +X right, +Y up):

    outer            - the filled silhouette (the bead body)
    rainbow_outer    - outermost rainbow ring  -> RED filament
    rainbow_mid      - middle rainbow ring     -> YELLOW filament
    rainbow_inner    - innermost rainbow ring  -> BLUE filament
    wings            - the black thorn shapes on each end

Run:
    uv run python beads/black-rainbow/extract_regions.py
"""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from skimage import measure
from scipy.spatial import ConvexHull

SRC = Path('beads/black-rainbow/simplified_rainbow_1024.png')
OUT = Path('beads/black-rainbow')
TARGET_WIDTH_MM = 25.0

# Color matching: per-region pure RGB + tolerance (Manhattan distance).
# Tolerance generous enough to swallow Lanczos edge blending, tight enough
# that band boundaries don't bleed into each other.
ALPHA_MIN     = 64
COLOR_TOL     = 50
WINGS_RGB     = (15, 15, 15)
RED_RGB       = (200, 24, 24)
YELLOW_RGB    = (230, 198, 30)
BLUE_RGB      = (28, 95, 184)
# Silhouette smoothing
FOURIER_HARM_SILH   = 36   # outer silhouette (high — preserve thorn detail)
FOURIER_HARM_REGION = 28   # color regions

# ── Load + per-color masks ───────────────────────────────────────────
img_rgba = np.array(Image.open(SRC).convert('RGBA'))
H, W, _ = img_rgba.shape
R, G, B, A = (img_rgba[..., i].astype(np.int16) for i in range(4))
fg = A >= ALPHA_MIN

def color_match(target):
    tr, tg, tb = target
    d = np.abs(R - tr) + np.abs(G - tg) + np.abs(B - tb)
    return fg & (d <= COLOR_TOL)

wings_raw   = color_match(WINGS_RGB)
red_raw     = color_match(RED_RGB)
yellow_raw  = color_match(YELLOW_RGB)
blue_raw    = color_match(BLUE_RGB)
rainbow_raw = red_raw | yellow_raw | blue_raw

# Light morphology: close pinholes from AA blends; do NOT open (would erode
# the band edges and leave gaps between bands).
def close_and_filter(mask, close_iters=1, min_area=500):
    m = ndimage.binary_closing(mask, iterations=close_iters)
    labeled, n = ndimage.label(m)
    if n == 0:
        return m
    out = np.zeros_like(m)
    for i in range(1, n + 1):
        comp = labeled == i
        if comp.sum() >= min_area:
            out |= comp
    return out

wings   = close_and_filter(wings_raw, close_iters=1, min_area=500)
rainbow = close_and_filter(rainbow_raw, close_iters=1, min_area=500)

# ── Filled silhouette: figure ∪ convex hull, restricted to bbox ─────
# Take the union of wings + rainbow as the "figure" — drops any incidental
# colored pixels in the background. Then compute convex hull to bridge the
# under-arch. Union the result with the original figure mask so wing thorns
# (which protrude OUTSIDE the convex hull's straight edges? no — convex
# hull contains them, but the hull's straight edges between thorns cut INTO
# the concavities between thorns) are preserved.
figure = wings | rainbow
figure = ndimage.binary_closing(figure, iterations=4)
figure = ndimage.binary_fill_holes(figure)

# Convex hull of the figure: gives us a filled blob bridging the under-arch
ys_f, xs_f = np.where(figure)
if len(ys_f) == 0:
    raise SystemExit("No figure pixels found — check BG_LUMA_MIN / source image.")
points = np.column_stack((xs_f, ys_f))
hull = ConvexHull(points)
hull_pts = points[hull.vertices]

# Rasterize the convex hull polygon
hull_img = Image.new('L', (W, H), 0)
ImageDraw.Draw(hull_img).polygon([tuple(p) for p in hull_pts], fill=255)
hull_mask = np.array(hull_img) > 0

# Filled silhouette: convex hull ∪ figure  (figure may extend slightly past
# the hull due to closing dilation; union ensures every figure pixel is in).
silhouette = hull_mask | figure
silhouette = ndimage.binary_fill_holes(silhouette)

# Take the largest connected component (paranoia)
labeled_s, n_s = ndimage.label(silhouette)
sizes_s = ndimage.sum(silhouette, labeled_s, range(1, n_s + 1))
silhouette = labeled_s == (1 + int(np.argmax(sizes_s)))

# Restrict wings + rainbow to inside silhouette
wings = wings & silhouette
rainbow = rainbow & silhouette

# ── 3 rainbow bands directly from pure-color masks ──────────────────
# The new source has 3 discrete pure-color regions, so each band IS its
# color-match mask. No HSV/radial binning required. Snap each band to the
# silhouette so stray edge pixels outside it don't bleed in.
bands = [
    ('rainbow_outer', '#c81818', red_raw    & silhouette),
    ('rainbow_mid',   '#e6c61e', yellow_raw & silhouette),
    ('rainbow_inner', '#1c5fb8', blue_raw   & silhouette),
]
for name, hex_col, m in bands:
    print(f"  {name:14s} ({hex_col}): {int(m.sum())} px")
# (For the JSON manifest's arch_center_mm: still compute it for downstream use)
ys_r, xs_r = np.where(rainbow)
arch_cx = (xs_r.min() + xs_r.max()) / 2.0
arch_cy = float(ys_r.max())

# ── Preview PNG: render simplified rainbow with TRUE anti-aliased edges ──
# Per-region float alpha (smooth) instead of binary mask, then alpha-composite
# in order: white bg → bands → wings. Each region's alpha is derived from a
# subpixel-accurate boundary by:
#   1. extract polygon contours (skimage.find_contours, level=0.5)
#   2. render at 8× resolution with PIL polygon fill
#   3. downsample with Lanczos (smooth resampling kernel)
# This gives properly antialiased edges everywhere — no pixel-step.
SUPER = 8

def render_mask_aa(mask, smooth_harm=None):
    """Render `mask` at SUPER× target res via polygon fill, return uint8 alpha
    at native (H, W) resolution. Uses Fourier-smoothed contours when
    smooth_harm is given so the AA edge follows a smooth curve, not a
    pixel staircase."""
    contours = measure.find_contours(mask.astype(np.float32), level=0.5)
    big = Image.new('L', (W * SUPER, H * SUPER), 0)
    draw = ImageDraw.Draw(big)
    for c in contours:
        if len(c) < 3:
            continue
        if smooth_harm and len(c) > 10:
            z = c[:, 1] + 1j * c[:, 0]
            Z = np.fft.fft(z)
            msk = np.zeros_like(Z, dtype=bool)
            msk[0] = True
            msk[1:smooth_harm + 1] = True
            msk[-smooth_harm:] = True
            z2 = np.fft.ifft(np.where(msk, Z, 0))
            pts = [(float(z2[i].real) * SUPER, float(z2[i].imag) * SUPER)
                   for i in range(len(z2))]
        else:
            pts = [(float(c[i, 1]) * SUPER, float(c[i, 0]) * SUPER)
                   for i in range(len(c))]
        draw.polygon(pts, fill=255)
    return np.array(big.resize((W, H), Image.LANCZOS), dtype=np.float32) / 255.0

# Alphas (smooth, 0-1) per region. Smooth harmonics small enough to round
# pixel-step in the source, large enough to preserve thorn fingertips.
alpha_red    = render_mask_aa(bands[0][2], smooth_harm=24)
alpha_yellow = render_mask_aa(bands[1][2], smooth_harm=24)
alpha_blue   = render_mask_aa(bands[2][2], smooth_harm=24)
# Wings: no Fourier smoothing — preserve every thorn fingertip. The 8× polygon
# supersample alone still gives clean AA edges; smoothing rounds off the spikes.
alpha_wings  = render_mask_aa(wings,      smooth_harm=None)

def composite(bg_rgb):
    out = np.full((H, W, 3), bg_rgb, dtype=np.float32)
    for alpha, hex_col in [
        (alpha_red,    '#c81818'),
        (alpha_yellow, '#e6c61e'),
        (alpha_blue,   '#1c5fb8'),
        (alpha_wings,  '#0f0f0f'),
    ]:
        rgb = np.array(
            [int(hex_col[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float32)
        a = alpha[..., None]
        out = out * (1 - a) + rgb * a
    return np.clip(out, 0, 255).astype(np.uint8)

# Solid white background
Image.fromarray(composite((255, 255, 255))).save(OUT / 'simplified_rainbow.png')
# Transparent background: union-alpha of all regions
combined_alpha = np.clip(alpha_red + alpha_yellow + alpha_blue + alpha_wings,
                         0, 1)
rgba = np.dstack([composite((0, 0, 0)), (combined_alpha * 255).astype(np.uint8)])
Image.fromarray(rgba, mode='RGBA').save(OUT / 'simplified_rainbow_transparent.png')
print(f"  wrote simplified_rainbow.png (white bg) + _transparent.png (alpha) — AA via polygon supersample")

# ── Debug overlay ────────────────────────────────────────────────────
overlay = img_rgba[..., :3].astype(np.float32) * 0.35
# Silhouette tint (background of silhouette but outside any region)
silh_only = silhouette & ~(wings | rainbow)
overlay[silh_only] += np.array((180, 180, 180), dtype=np.float32) * 0.5
# Wings
overlay[wings] += np.array((40, 40, 40), dtype=np.float32) * 0.8
# Rainbow bands
for name, hex_col, m in bands:
    rgb = tuple(int(hex_col[i:i + 2], 16) for i in (1, 3, 5))
    overlay[m] += np.array(rgb, dtype=np.float32) * 0.7
# Mark the arch center we used for radial binning
dbg = np.clip(overlay, 0, 255).astype(np.uint8)
dbg_img = Image.fromarray(dbg)
draw = ImageDraw.Draw(dbg_img)
draw.ellipse((arch_cx - 6, arch_cy - 6, arch_cx + 6, arch_cy + 6),
             outline=(255, 0, 255), width=3)
dbg_img.save(OUT / 'extract_debug.png')
print(f"  wrote extract_debug.png — review before importing into Blender")

# ── Polygon manifest in shared mm coords ─────────────────────────────
ys_s, xs_s = np.where(silhouette)
bx0, bx1 = xs_s.min(), xs_s.max()
by0, by1 = ys_s.min(), ys_s.max()
silh_w_px = bx1 - bx0
silh_h_px = by1 - by0
SCALE = TARGET_WIDTH_MM / silh_w_px
silh_cx_px = (bx0 + bx1) / 2.0
silh_cy_px = (by0 + by1) / 2.0


def fourier_smooth(contour, harm):
    z = contour[:, 0] + 1j * contour[:, 1]
    Z = np.fft.fft(z)
    msk = np.zeros_like(Z, dtype=bool)
    msk[0] = True
    msk[1:harm + 1] = True
    msk[-harm:] = True
    return np.fft.ifft(np.where(msk, Z, 0))


def downsample(contour, n_target=400):
    if len(contour) <= n_target:
        return contour
    idx = np.linspace(0, len(contour) - 1, n_target).astype(int)
    return contour[idx]


def mask_to_polygons_mm(mask, smooth=True, harm=FOURIER_HARM_REGION, min_area=200):
    polygons = []
    labeled, n = ndimage.label(mask)
    for k in range(1, n + 1):
        comp = labeled == k
        if comp.sum() < min_area:
            continue
        contours = measure.find_contours(comp.astype(np.uint8), level=0.5)
        if not contours:
            continue
        contours.sort(key=lambda c: -len(c))

        def transform(c):
            c = downsample(c, 400)
            if smooth and len(c) > 10:
                z = fourier_smooth(c, harm)
                c = np.column_stack((z.real, z.imag))
            ys, xs = c[:, 0], c[:, 1]
            x_mm = (xs - silh_cx_px) * SCALE
            y_mm = -(ys - silh_cy_px) * SCALE
            return list(zip(x_mm.tolist(), y_mm.tolist()))

        outer = transform(contours[0])
        holes = [transform(h) for h in contours[1:] if len(h) >= 8]
        polygons.append({'outer': outer, 'holes': holes})
    return polygons


regions_data = {
    'scale_mm_per_px': float(SCALE),
    'silhouette_bbox_mm': {
        'width': float(TARGET_WIDTH_MM),
        'height': float(silh_h_px * SCALE),
    },
    'arch_center_mm': {
        'x': float((arch_cx - silh_cx_px) * SCALE),
        'y': float(-(arch_cy - silh_cy_px) * SCALE),
    },
    'regions': {
        'outer': {
            'polygons': mask_to_polygons_mm(silhouette, smooth=True,
                                            harm=FOURIER_HARM_SILH, min_area=5000),
            'color_hex': '#000000',
        },
        'wings': {
            'polygons': mask_to_polygons_mm(wings, smooth=True,
                                            harm=FOURIER_HARM_REGION, min_area=400),
            'color_hex': '#0a0a0a',
        },
    },
}
for name, hex_col, m in bands:
    regions_data['regions'][name] = {
        'polygons': mask_to_polygons_mm(m, smooth=True,
                                        harm=FOURIER_HARM_REGION, min_area=200),
        'color_hex': hex_col,
    }

(OUT / 'regions.json').write_text(json.dumps(regions_data, indent=2), encoding='utf-8')

total = sum(len(r['polygons']) for r in regions_data['regions'].values())
print()
print(f"silhouette: {TARGET_WIDTH_MM:.2f}mm × {silh_h_px * SCALE:.2f}mm  "
      f"(scale {SCALE:.4f} mm/px)")
print(f"arch center at ({regions_data['arch_center_mm']['x']:+.2f}, "
      f"{regions_data['arch_center_mm']['y']:+.2f}) mm")
print(f"wrote regions.json — {total} polygons across "
      f"{len(regions_data['regions'])} regions:")
for name, r in regions_data['regions'].items():
    print(f"  {name:16s} {len(r['polygons'])} polygon(s)  color={r['color_hex']}")
