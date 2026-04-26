"""Extract a clean SVG silhouette from the cartoon-portrait screenshot.

Pipeline (lifted from laser-cube-driver/shader-to-svg):
  load PNG
  → gaussian-blur          (denoise)
  → threshold on luminance (binary figure mask)
  → close holes            (the outline ring is hollow before this)
  → keep largest component (silhouette body)
  → moore-boundary trace   (ordered outline points)
  → fourier-smooth         (drop high-frequency wobble)
  → emit SVG path

Eyes are detected separately by orange chroma → connected components →
two largest blobs, emitted as <circle> elements.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import measure


# ── Tunables ───────────────────────────────────────────────────────────
SRC = r"C:\Users\hypnodroid\Pictures\Screenshots\Screenshot 2026-04-25 235837.png"
OUT_SVG = Path(r"D:\Projects\nfc-bead\beads\redaphid-portrait\silhouette.svg")
OUT_DEBUG = Path(r"D:\Projects\nfc-bead\tmp\screenshots")

BLUR_SIGMA       = 3.0     # gaussian sigma, in source pixels
LUMA_THRESHOLD   = 22       # luma > this = figure pixel  (background ≈ 0–10)
MORPH_CLOSE_R    = 4        # close gaps in the glow ring (pixels)
FOURIER_HARMONICS = 24      # silhouette: keep low-freq descriptors only

# Eye chroma: the eyes are warm (R-B large positive) while the pink outline
# has R-B near zero or negative, so a single warm-channel threshold separates
# them cleanly. Sampled actual peaks: eye R-B ≈ +60..70, outline R-B ≈ -10..0.
EYE_WARM_MIN  = 30          # pixel kept iff R - B > this
EYE_MIN_AREA  = 80          # pixels
EYE_MAX_AREA  = 8000

# SVG output sizing — scale the silhouette to roughly fit 25mm wide kandi bead
SVG_TARGET_W_MM = 25.0


def luminance(rgb: np.ndarray) -> np.ndarray:
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def gaussian_blur(img: np.ndarray, sigma: float) -> np.ndarray:
    return ndimage.gaussian_filter(img.astype(np.float32), sigma=sigma)


def keep_largest_component(mask: np.ndarray) -> np.ndarray:
    """Return mask containing only the largest 4-connected blob."""
    labeled, n = ndimage.label(mask)
    if n == 0:
        return mask
    sizes = ndimage.sum(mask, labeled, range(1, n + 1))
    biggest = 1 + int(np.argmax(sizes))
    return labeled == biggest


def fill_holes(mask: np.ndarray) -> np.ndarray:
    return ndimage.binary_fill_holes(mask)


def fourier_smooth(contour_xy: np.ndarray, harmonics: int) -> np.ndarray:
    """Smooth a closed 2D contour by truncating its FFT to `harmonics` modes.

    Input shape: (N, 2). Output shape: (N, 2). N preserved.
    """
    z = contour_xy[:, 0] + 1j * contour_xy[:, 1]
    Z = np.fft.fft(z)
    # Keep DC + first `harmonics` positive freqs and matching negative freqs
    mask = np.zeros_like(Z, dtype=bool)
    mask[0] = True
    mask[1:harmonics + 1] = True
    mask[-harmonics:] = True
    Z_smooth = np.where(mask, Z, 0)
    z_smooth = np.fft.ifft(Z_smooth)
    out = np.column_stack((z_smooth.real, z_smooth.imag))
    return out


def find_outer_contour(mask: np.ndarray):
    """Return the outermost closed contour as (N,2) (row,col) coords."""
    contours = measure.find_contours(mask.astype(np.uint8), level=0.5)
    if not contours:
        raise RuntimeError("No contour found")
    contours.sort(key=lambda c: -len(c))
    return contours[0]


def extract_eyes(rgb: np.ndarray):
    """Return list of (cx, cy, r) in image pixel coords for detected eye blobs."""
    R = rgb[..., 0].astype(np.int16)
    B = rgb[..., 2].astype(np.int16)
    warm = R - B
    eye_mask = warm > EYE_WARM_MIN
    eye_mask = ndimage.binary_opening(eye_mask, iterations=2)
    eye_mask = ndimage.binary_closing(eye_mask, iterations=2)

    labeled, n = ndimage.label(eye_mask)
    eyes = []
    for lab in range(1, n + 1):
        comp = labeled == lab
        area = int(comp.sum())
        if area < EYE_MIN_AREA or area > EYE_MAX_AREA:
            continue
        ys, xs = np.where(comp)
        cx, cy = float(xs.mean()), float(ys.mean())
        r = float(np.sqrt(area / np.pi))
        eyes.append((cx, cy, r, area))
    eyes.sort(key=lambda e: -e[3])
    eyes = [(cx, cy, r) for (cx, cy, r, _a) in eyes[:2]]
    # Force left-to-right order
    eyes.sort(key=lambda e: e[0])
    return eyes


def write_svg(silhouette_pts_xy_mm: np.ndarray, eyes_xy_r_mm, w_mm: float, h_mm: float, out_path: Path):
    """Emit an SVG with: <path> for silhouette + 2x <circle> for eyes."""
    # Move-to first point, line-to the rest, close path
    d = "M " + f"{silhouette_pts_xy_mm[0,0]:.3f},{silhouette_pts_xy_mm[0,1]:.3f} "
    for x, y in silhouette_pts_xy_mm[1:]:
        d += f"L {x:.3f},{y:.3f} "
    d += "Z"

    eyes_svg = "\n".join(
        f'  <circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" fill="black" stroke="none" />'
        for (cx, cy, r) in eyes_xy_r_mm
    )

    svg = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm:.3f}mm" height="{h_mm:.3f}mm" viewBox="0 0 {w_mm:.3f} {h_mm:.3f}">
  <path d="{d}" fill="black" stroke="none" />
{eyes_svg}
</svg>
'''
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")


def save_debug_overlay(rgb: np.ndarray, mask: np.ndarray, contour_rc: np.ndarray, eyes_pix, out_path: Path):
    """Save a debug PNG showing the original image with mask outline + eye markers."""
    overlay = rgb.copy()
    # Tint mask interior cyan-ish
    tint = np.zeros_like(rgb)
    tint[..., 1] = 80
    tint[..., 2] = 80
    overlay = np.where(mask[..., None], (overlay * 0.7 + tint * 0.3).astype(np.uint8), overlay)

    # Draw contour as red dots
    rr = np.clip(contour_rc[:, 0].astype(int), 0, rgb.shape[0] - 1)
    cc = np.clip(contour_rc[:, 1].astype(int), 0, rgb.shape[1] - 1)
    overlay[rr, cc] = (255, 64, 64)

    # Draw eye centers in green
    for cx, cy, r in eyes_pix:
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                y = int(cy + dy); x = int(cx + dx)
                if 0 <= y < rgb.shape[0] and 0 <= x < rgb.shape[1]:
                    overlay[y, x] = (0, 255, 0)

    Image.fromarray(overlay).save(out_path)


def main():
    img = Image.open(SRC).convert("RGB")
    rgb = np.array(img)
    H, W = rgb.shape[:2]
    print(f"Loaded {SRC}: {W}x{H}")

    # 1) gaussian-blur
    blurred = gaussian_blur(rgb, BLUR_SIGMA)

    # 2) luminance threshold
    L = luminance(blurred)
    figure = L > LUMA_THRESHOLD
    print(f"Figure pixels (raw threshold): {int(figure.sum())} / {W*H}")

    # 3) morphological close to bridge any thin gaps in the glow ring
    structure = ndimage.generate_binary_structure(2, 2)
    figure = ndimage.binary_closing(figure, structure=structure, iterations=MORPH_CLOSE_R)

    # 4) fill interior holes (background pixels surrounded by figure)
    figure = fill_holes(figure)

    # 5) keep the largest connected blob
    figure = keep_largest_component(figure)
    print(f"Figure pixels (post-clean):   {int(figure.sum())}")

    # 6) trace outer contour (skimage marching squares finds closed contours)
    contour_rc = find_outer_contour(figure)
    print(f"Contour points: {len(contour_rc)}")

    # 7) downsample to ~400 points before fourier smooth (otherwise N is huge)
    target_n = 400
    if len(contour_rc) > target_n:
        idx = np.linspace(0, len(contour_rc) - 1, target_n).astype(int)
        contour_rc = contour_rc[idx]

    # 8) fourier-smooth in image coords
    smoothed = fourier_smooth(contour_rc, FOURIER_HARMONICS)

    # 9) detect eyes
    eyes_pix = extract_eyes(rgb)
    print(f"Eyes found: {len(eyes_pix)}")
    for cx, cy, r in eyes_pix:
        print(f"  eye @ ({cx:.0f},{cy:.0f}) r={r:.1f} px")

    # 10) compute silhouette bbox in pixels, scale to target mm width
    rs, cs = smoothed[:, 0], smoothed[:, 1]
    bb_w_px = cs.max() - cs.min()
    bb_h_px = rs.max() - rs.min()
    px_per_mm = bb_w_px / SVG_TARGET_W_MM
    h_mm = bb_h_px / px_per_mm

    # Convert smoothed (row=y, col=x) → (x, y) in mm, with origin at top-left of bbox
    sx_mm = (cs - cs.min()) / px_per_mm
    sy_mm = (rs - rs.min()) / px_per_mm
    silhouette_xy_mm = np.column_stack((sx_mm, sy_mm))

    eyes_mm = []
    for cx_px, cy_px, r_px in eyes_pix:
        ex_mm = (cx_px - cs.min()) / px_per_mm
        ey_mm = (cy_px - rs.min()) / px_per_mm
        er_mm = r_px / px_per_mm
        eyes_mm.append((ex_mm, ey_mm, er_mm))

    print(f"SVG bbox: {SVG_TARGET_W_MM:.2f} x {h_mm:.2f} mm   ({px_per_mm:.2f} px/mm)")

    # 11) write SVG
    write_svg(silhouette_xy_mm, eyes_mm, SVG_TARGET_W_MM, h_mm, OUT_SVG)
    print(f"Wrote {OUT_SVG}")

    # 12) debug overlay
    OUT_DEBUG.mkdir(parents=True, exist_ok=True)
    save_debug_overlay(rgb, figure, contour_rc, eyes_pix, OUT_DEBUG / "extract_debug.png")
    print(f"Wrote {OUT_DEBUG / 'extract_debug.png'}")


if __name__ == "__main__":
    main()
