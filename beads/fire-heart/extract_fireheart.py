"""Extract the fire-heart PNG into color regions for a through-color charm.

The source is a black heart with warm (red→orange→yellow) flame wings behind
it. We separate by CHROMA, not k-means:

  * heart   = dark, low-chroma pixels → the central heart blob (black)
  * flames  = everything else in the foreground, split into
                flames_red    (warm, low green   → deep red base)
                flames_orange (warm, high green   → orange/yellow tips)

Outputs (beads/fire-heart/):
  silhouette.svg     - outer outline (heart + flames union), one closed path
  regions.json       - heart + flame polygons in a SHARED mm frame
                       (origin = silhouette bbox center, +X right, +Y up)
  extract_debug.png  - segmentation overlay; eyeball before building

Run:
    uv run python beads/fire-heart/extract_fireheart.py
"""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import measure

SRC = Path('beads/fire-heart/black-heart.png')
OUT = Path('beads/fire-heart')
TARGET_WIDTH_MM = 28.0          # overall bead width (heart+flames). Bigger than
                                # the 25mm default so the heart hosts the 10.5mm
                                # NFC pocket comfortably once flames eat width.

# ── Chroma thresholds (tuned per image; see extract_debug.png) ──────────
WARM_MIN     = 28      # (R - B) > this → warm/flame pixel
DARK_MAX     = 110     # max(R,G,B) <= this AND low chroma → heart-dark candidate
SPLIT_DIST_MM = 3.0    # flame within this distance of the heart = red base;
                       # beyond = orange tip (classic fire gradient)

# ── Flame thickening (user asked for chunky tongues >=1.5mm, won't snap) ─
# Thin pointy flame tongues at this scale (~0.07mm/px) print as fragile
# spikes. Dilate the flame mask to fatten every tongue, and close to merge
# adjacent tongues into bolder wing shapes. The heart stays crisp.
FLAME_DILATE_PX = 5    # ~0.35mm per side → +0.7mm tongue width
FLAME_CLOSE_PX  = 4    # merge near-adjacent tongues into chunkier wings

# ── Smoothing ───────────────────────────────────────────────────────────
FOURIER_HARM_BODY   = 20   # outer silhouette (keep flame tongues legible)
FOURIER_HARM_REGION = 18
SILHOUETTE_BLUR     = 1.5

# ── Load + foreground mask ──────────────────────────────────────────────
img = np.array(Image.open(SRC).convert('RGB'))
H, W, _ = img.shape
R = img[..., 0].astype(np.int16)
G = img[..., 1].astype(np.int16)
B = img[..., 2].astype(np.int16)
bg = (R > 235) & (G > 235) & (B > 235)
fg = ~bg

# ── Region masks ────────────────────────────────────────────────────────
warm = (R - B) > WARM_MIN
chroma = np.abs(R - B) + np.abs(R - G) + np.abs(G - B)
dark_lowchroma = (np.maximum(np.maximum(R, G), B) <= DARK_MAX) & (chroma < 60)

def clean(m, close=3, open_=1, fill=True):
    m = ndimage.binary_closing(m, iterations=close)
    m = ndimage.binary_opening(m, iterations=open_)
    if fill:
        m = ndimage.binary_fill_holes(m)
    return m

# Raw foreground silhouette (largest component) — used to derive the heart.
fg_outer = clean(fg, close=5, open_=1)
labeled, n = ndimage.label(fg_outer)
if n > 1:
    sizes = ndimage.sum(fg_outer, labeled, range(1, n + 1))
    fg_outer = labeled == (1 + int(np.argmax(sizes)))

# Detect the dark heart blob ONLY to locate + size the heart. The visible
# dark pixels are bitten into by flames drawn over the heart's upper lobes,
# so the raw blob has non-round lobes. We replace it with a clean parametric
# "traditional heart" fitted to the blob's bounding box — guaranteed round
# lobes + cleft + point. Being the proud (raised) layer, it occludes the
# fire across its full classic outline (user: lobes must read as round).
heart_seed = dark_lowchroma & fg & ~warm
heart_seed = ndimage.binary_opening(heart_seed, iterations=2)  # snap thin flame veins off
hl, hn = ndimage.label(heart_seed)
if hn == 0:
    raise SystemExit("No heart blob found — loosen DARK_MAX / chroma threshold")
hsizes = ndimage.sum(heart_seed, hl, range(1, hn + 1))
heart_blob = hl == (1 + int(np.argmax(hsizes)))
hy_idx, hx_idx = np.where(heart_blob)
chx0, chx1 = hx_idx.min(), hx_idx.max()
chy0, chy1 = hy_idx.min(), hy_idx.max()

# Parametric traditional heart curve; sample, then fit to the detected blob
# bbox (optionally fattened so the round lobes reclaim flame-bitten area).
HEART_FATTEN = 1.06          # >1 grows the heart to occlude fire over the lobes
tt = np.linspace(0, 2 * np.pi, 600)
hx = 16 * np.sin(tt) ** 3
hy = 13 * np.cos(tt) - 5 * np.cos(2 * tt) - 2 * np.cos(3 * tt) - np.cos(4 * tt)
# The cleft (t=0) is a sharp downward cusp — it reads as a vertical clip where
# the two lobes meet. Round ONLY that cusp: blend in a smoothed copy weighted
# near t=0, leaving the bottom point (t=π) sharp and the lobes untouched.
sm_x = ndimage.gaussian_filter1d(hx, sigma=9, mode='wrap')
sm_y = ndimage.gaussian_filter1d(hy, sigma=9, mode='wrap')
ang = np.minimum(tt, 2 * np.pi - tt)         # angular distance from the cleft
w = np.exp(-(ang / 0.30) ** 2)               # ≈1 at the cleft, →0 elsewhere
hx = (1 - w) * hx + w * sm_x
hy = (1 - w) * hy + w * sm_y
# Normalize param curve to [0,1], then map to the (fattened) blob bbox.
hx_n = (hx - hx.min()) / (hx.max() - hx.min())
hy_n = (hy - hy.min()) / (hy.max() - hy.min())
bw, bh = (chx1 - chx0), (chy1 - chy0)
cxp, cyp = (chx0 + chx1) / 2.0, (chy0 + chy1) / 2.0
px = cxp + (hx_n - 0.5) * bw * HEART_FATTEN
# param-y is high at lobes/cleft (top) → small pixel-y (image top): flip.
py = cyp - (hy_n - 0.5) * bh * HEART_FATTEN
from skimage.draw import polygon as _poly
heart = np.zeros((H, W), dtype=bool)
rr, cc = _poly(py, px, shape=heart.shape)
heart[rr, cc] = True

# Flames (raw) = foreground minus heart. Then THICKEN: merge adjacent tongues
# (close) and fatten every tongue (dilate) so none prints as a fragile spike.
flames_raw = fg_outer & ~heart
flames_raw = ndimage.binary_opening(flames_raw, iterations=1)
flames = ndimage.binary_closing(flames_raw, iterations=FLAME_CLOSE_PX)
flames = ndimage.binary_dilation(flames, iterations=FLAME_DILATE_PX)
flames = flames & ~heart                       # heart wins at the boundary

# Final outer silhouette = crisp heart ∪ thickened flames.
outer = heart | flames
outer = ndimage.binary_fill_holes(outer)

# ── Shared mm coordinate frame (origin = silhouette bbox center) ────────
ys_o, xs_o = np.where(outer)
bx0, bx1 = xs_o.min(), xs_o.max()
by0, by1 = ys_o.min(), ys_o.max()
SCALE = TARGET_WIDTH_MM / (bx1 - bx0)
cx_px = (bx0 + bx1) / 2.0
cy_px = (by0 + by1) / 2.0
HEIGHT_MM = (by1 - by0) * SCALE

# Split thickened flames by DISTANCE from the heart: a red base band hugging
# the heart, orange tips beyond. Distance transform measures how far each
# flame pixel is from the nearest heart pixel.
dist_from_heart = ndimage.distance_transform_edt(~heart)
split_px = SPLIT_DIST_MM / SCALE
flames_red    = flames & (dist_from_heart <= split_px)
flames_orange = flames & (dist_from_heart >  split_px)

print(f"image {W}x{H}  fg={fg.sum()}px")
print(f"  heart        {heart.sum():>7}px")
print(f"  flames_red   {flames_red.sum():>7}px")
print(f"  flames_orange{flames_orange.sum():>7}px")

# ── Debug overlay ───────────────────────────────────────────────────────
ov = img.astype(np.float32) * 0.35
ov[heart]         += np.array((40, 40, 255), np.float32) * 0.65   # blue = heart
ov[flames_red]    += np.array((255, 30, 30), np.float32) * 0.55   # red
ov[flames_orange] += np.array((255, 180, 0), np.float32) * 0.55   # orange
Image.fromarray(np.clip(ov, 0, 255).astype(np.uint8)).save(OUT / 'extract_debug.png')


def fourier_smooth(contour, harm):
    z = contour[:, 0] + 1j * contour[:, 1]
    Z = np.fft.fft(z)
    msk = np.zeros_like(Z, dtype=bool)
    msk[0] = True
    msk[1:harm + 1] = True
    msk[-harm:] = True
    return np.fft.ifft(np.where(msk, Z, 0))


def downsample(contour, n=400):
    if len(contour) <= n:
        return contour
    idx = np.linspace(0, len(contour) - 1, n).astype(int)
    return contour[idx]


def mask_to_polygons_mm(mask, smooth=True, harm=FOURIER_HARM_REGION, min_area=150,
                        pre_blur=0.0):
    if pre_blur > 0:
        mask = ndimage.gaussian_filter(mask.astype(np.float32), sigma=pre_blur) > 0.5
    labeled, n = ndimage.label(mask)
    polys = []
    for k in range(1, n + 1):
        comp = labeled == k
        if comp.sum() < min_area:
            continue
        contours = measure.find_contours(comp.astype(np.uint8), 0.5)
        if not contours:
            continue
        contours.sort(key=lambda c: -len(c))

        def tx(c):
            c = downsample(c, 400)
            if smooth and len(c) > 10:
                z = fourier_smooth(c, harm)
                c = np.column_stack((z.real, z.imag))
            ys, xs = c[:, 0], c[:, 1]
            x_mm = (xs - cx_px) * SCALE
            y_mm = -(ys - cy_px) * SCALE
            return list(zip(x_mm.tolist(), y_mm.tolist()))

        outer_loop = tx(contours[0])
        holes = [tx(h) for h in contours[1:] if len(h) >= 8]
        polys.append({'outer': outer_loop, 'holes': holes})
    return polys


# ── silhouette.svg (body + cropper) ─────────────────────────────────────
def write_silhouette_svg(path, polys):
    Wmm = TARGET_WIDTH_MM
    Hmm = HEIGHT_MM
    svg_w, svg_h = Wmm * 100, Hmm * 100
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" '
             f'height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}">']
    for poly in polys:
        # mm (center origin, +Y up) → SVG units (top-left origin, +Y down)
        loop = poly['outer']
        d = 'M ' + ' L '.join(
            f'{(x + Wmm / 2) * 100:.2f},{(Hmm / 2 - y) * 100:.2f}' for x, y in loop) + ' Z'
        parts.append(f'<path fill="#000" stroke="none" d="{d}"/>')
    parts.append('</svg>')
    path.write_text('\n'.join(parts), encoding='utf-8')


silh_polys = mask_to_polygons_mm(outer, smooth=True, harm=FOURIER_HARM_BODY,
                                 min_area=2000, pre_blur=SILHOUETTE_BLUR)
write_silhouette_svg(OUT / 'silhouette.svg', silh_polys)

# ── regions.json ────────────────────────────────────────────────────────
regions_data = {
    'scale_mm_per_px': float(SCALE),
    'target_width_mm': float(TARGET_WIDTH_MM),
    'silhouette_bbox_mm': {'width': float(TARGET_WIDTH_MM), 'height': float(HEIGHT_MM)},
    'regions': {
        'heart': {
            'polygons': mask_to_polygons_mm(heart, smooth=True, harm=FOURIER_HARM_REGION, min_area=400),
            'color_hex': '#111111',
        },
        'flames_red': {
            'polygons': mask_to_polygons_mm(flames_red, smooth=True, harm=FOURIER_HARM_REGION, min_area=150),
            'color_hex': '#d41212',
        },
        'flames_orange': {
            'polygons': mask_to_polygons_mm(flames_orange, smooth=True, harm=FOURIER_HARM_REGION, min_area=150),
            'color_hex': '#ff8c00',
        },
    },
}
(OUT / 'regions.json').write_text(json.dumps(regions_data, indent=2), encoding='utf-8')
total = sum(len(r['polygons']) for r in regions_data['regions'].values())
print(f"\nwrote silhouette.svg ({len(silh_polys)} path) + regions.json "
      f"({total} polygons across {len(regions_data['regions'])} regions)")
print(f"scale {SCALE:.4f} mm/px  bead {TARGET_WIDTH_MM} x {HEIGHT_MM:.2f} mm")
