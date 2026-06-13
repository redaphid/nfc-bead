"""Extract the single handstand gymnast as a centered mm polygon for use as a
RAISED RELIEF on a round NFC bead (the gymnast plays the role of the rezz
spiral). Black figure on white -> invert -> threshold -> keep largest blob ->
fourier-smooth -> scale longest side to FIGURE_MAX_MM -> center bbox at (0,0).

Output: beads/gymnast-medallion/figure.json  (+ figure_debug.png)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import measure

SRC            = Path(r"D:\Projects\paper-cranes\public\images\handstand.png")
OUT_DIR        = Path(__file__).resolve().parent
FIGURE_MAX_MM  = 21.0     # longest side of the relief; fits inside a 25mm circle w/ margin
RELIEF_MM      = 0.5      # raised height (matches rezz spiral)
BLUR_SIGMA     = 1.5
LUMA_THRESHOLD = 128      # luma < this == figure (dark on white)
FOURIER_HARM   = 56       # high to preserve thin limbs/toes/bun
CONTOUR_PTS    = 700
# Grow the silhouette so thin limbs print SOLID as a 0.5mm relief. At this size
# the raw limbs are < 2 extrusion widths, so the slicer single-lines them ->
# stringy/gappy fill. Dilation (in source px) fattens every feature relative to
# the figure; ~8px ≈ +0.4mm of width at the final ~13mm relief size. 0 = faithful.
THICKEN_PX     = 8


def luminance(rgb):
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def keep_largest(mask):
    lab, n = ndimage.label(mask, structure=ndimage.generate_binary_structure(2, 2))
    if n == 0:
        return mask
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    return lab == 1 + int(np.argmax(sizes))


def fourier_smooth(c, harm):
    z = c[:, 0] + 1j * c[:, 1]
    Z = np.fft.fft(z)
    m = np.zeros_like(Z, dtype=bool)
    m[0] = True; m[1:harm + 1] = True; m[-harm:] = True
    zs = np.fft.ifft(np.where(m, Z, 0))
    return np.column_stack((zs.real, zs.imag))


def main():
    rgb = np.array(Image.open(SRC).convert("RGB"))
    H, W = rgb.shape[:2]
    print(f"Loaded {SRC}: {W}x{H}")

    blur = ndimage.gaussian_filter(rgb.astype(np.float32), sigma=(BLUR_SIGMA, BLUR_SIGMA, 0))
    mask = luminance(blur) < LUMA_THRESHOLD
    mask = ndimage.binary_fill_holes(mask)
    mask = keep_largest(mask)
    if THICKEN_PX > 0:
        mask = ndimage.binary_dilation(
            mask, structure=ndimage.generate_binary_structure(2, 1), iterations=THICKEN_PX)
        mask = ndimage.binary_fill_holes(mask)   # close any thin gaps the growth pinched
    print(f"figure pixels: {int(mask.sum())}  (thicken={THICKEN_PX}px)")

    contours = measure.find_contours(mask.astype(np.uint8), 0.5)
    contours.sort(key=lambda c: -len(c))
    c = contours[0]
    if len(c) > CONTOUR_PTS:
        c = c[np.linspace(0, len(c) - 1, CONTOUR_PTS).astype(int)]
    sm = fourier_smooth(c, FOURIER_HARM)  # (row, col)

    rs, cs = sm[:, 0], sm[:, 1]
    bb_w = cs.max() - cs.min()
    bb_h = rs.max() - rs.min()
    px_per_mm = max(bb_w, bb_h) / FIGURE_MAX_MM
    # mm polygon, Y-up, centered on (0,0)
    xs_mm = (cs - (cs.min() + cs.max()) / 2) / px_per_mm
    ys_mm = -(rs - (rs.min() + rs.max()) / 2) / px_per_mm   # flip row -> Y-up
    poly = np.column_stack((xs_mm, ys_mm))

    out = {
        "source": str(SRC),
        "figure_max_mm": FIGURE_MAX_MM,
        "relief_mm": RELIEF_MM,
        "width_mm": round(bb_w / px_per_mm, 4),
        "height_mm": round(bb_h / px_per_mm, 4),
        "polygon": [[round(x, 4), round(y, 4)] for x, y in poly],
    }
    (OUT_DIR / "figure.json").write_text(json.dumps(out, indent=2))
    print(f"figure: {out['width_mm']} x {out['height_mm']} mm, {len(poly)} pts")
    print(f"Wrote {OUT_DIR / 'figure.json'}")

    # debug overlay
    overlay = rgb.copy()
    tint = np.zeros_like(rgb); tint[..., 1] = 120
    overlay = np.where(mask[..., None], (overlay * 0.55 + tint * 0.45).astype(np.uint8), overlay)
    rr = np.clip(c[:, 0].astype(int), 0, H - 1)
    cc = np.clip(c[:, 1].astype(int), 0, W - 1)
    overlay[rr, cc] = (255, 64, 64)
    Image.fromarray(overlay).save(OUT_DIR / "figure_debug.png")
    print(f"Wrote {OUT_DIR / 'figure_debug.png'}")


if __name__ == "__main__":
    main()
