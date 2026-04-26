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
OUT_FACE_SVG = Path(r"D:\Projects\nfc-bead\beads\redaphid-portrait\face.svg")
OUT_DEBUG = Path(r"D:\Projects\nfc-bead\tmp\screenshots")

BLUR_SIGMA       = 3.0     # gaussian sigma, in source pixels
LUMA_THRESHOLD   = 22       # luma > this = figure pixel  (background ≈ 0–10)
MORPH_CLOSE_R    = 4        # close gaps in the glow ring (pixels)
FOURIER_HARMONICS = 24      # silhouette: keep low-freq descriptors only

# Face region: the visible head/face area inside the silhouette.
# Strategy is a euclidean distance transform on the silhouette mask: every
# interior pixel's value = its distance (in pixels) from the nearest
# outline pixel. The "face" is everything DEEP in the interior; "hair" is
# the shallow ring near the outline + the narrow ear/chin protrusions.
# A single distance threshold separates them naturally.
FACE_DIST_PX      = 110      # face = pixels with edge-distance > this (px).
                             # ~25 px/mm in our screenshot, so 110 px ≈ 4.25 mm
                             # of hair-ring — leaves enough hair above the face
                             # for a 2 mm string hole sandwiched between
                             # ≥ 1 mm walls on both sides.
FACE_MORPH_CLOSE  = 6        # round out the face boundary
FACE_FOURIER_HARM = 12       # smooth low-freq descriptors

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


def extract_face_mask(rgb: np.ndarray, silhouette_mask: np.ndarray) -> np.ndarray:
    """Inner 'face' region via euclidean distance transform of the silhouette.

    Pixels deep in the interior (far from the outline) form the face;
    pixels near the outline form the hair ring. The narrow ear/chin
    protrusions get pruned because their max edge-distance is small.
    """
    distances = ndimage.distance_transform_edt(silhouette_mask)
    face = distances > FACE_DIST_PX
    face = ndimage.binary_closing(face, iterations=FACE_MORPH_CLOSE)
    face = keep_largest_component(face)
    face = fill_holes(face)
    return face


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


def _path_d(pts_xy_mm: np.ndarray) -> str:
    d = "M " + f"{pts_xy_mm[0,0]:.3f},{pts_xy_mm[0,1]:.3f} "
    for x, y in pts_xy_mm[1:]:
        d += f"L {x:.3f},{y:.3f} "
    d += "Z"
    return d


def write_svg(silhouette_pts_xy_mm: np.ndarray, eyes_xy_r_mm, w_mm: float, h_mm: float, out_path: Path):
    """Emit an SVG with: <path> for silhouette + 2x <circle> for eyes."""
    d = _path_d(silhouette_pts_xy_mm)
    eyes_svg = "\n".join(
        f'  <circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" fill="black" stroke="none" />'
        for (cx, cy, r) in eyes_xy_r_mm
    )
    svg = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm:.3f}mm" height="{h_mm:.3f}mm" viewBox="0 0 {w_mm:.3f} {h_mm:.3f}">
  <path id="silhouette" d="{d}" fill="black" stroke="none" />
{eyes_svg}
</svg>
'''
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")


def write_face_svg(face_pts_xy_mm: np.ndarray, w_mm: float, h_mm: float, out_path: Path):
    d = _path_d(face_pts_xy_mm)
    svg = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm:.3f}mm" height="{h_mm:.3f}mm" viewBox="0 0 {w_mm:.3f} {h_mm:.3f}">
  <path id="face" d="{d}" fill="brown" stroke="none" />
</svg>
'''
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")


def save_debug_overlay(rgb, silhouette_mask, sil_contour_rc, face_mask, face_contour_rc, eyes_pix, out_path: Path):
    """Save a debug PNG showing the original image with both masks + contours + eye markers."""
    overlay = rgb.copy()
    # Cyan tint on the silhouette region
    tint = np.zeros_like(rgb); tint[..., 1] = 80; tint[..., 2] = 80
    overlay = np.where(silhouette_mask[..., None], (overlay * 0.7 + tint * 0.3).astype(np.uint8), overlay)
    # Yellow tint on the face region (over the silhouette tint)
    if face_mask is not None:
        ftint = np.zeros_like(rgb); ftint[..., 0] = 130; ftint[..., 1] = 130
        overlay = np.where(face_mask[..., None], (overlay * 0.6 + ftint * 0.4).astype(np.uint8), overlay)

    def stipple(contour, color):
        if contour is None or len(contour) == 0:
            return
        rr = np.clip(contour[:, 0].astype(int), 0, rgb.shape[0] - 1)
        cc = np.clip(contour[:, 1].astype(int), 0, rgb.shape[1] - 1)
        overlay[rr, cc] = color

    stipple(sil_contour_rc,  (255, 64, 64))   # red — silhouette
    stipple(face_contour_rc, (0, 200, 255))   # cyan — face contour

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

    # 10) extract face contour (HSV-style: low saturation inside the silhouette)
    face_mask = extract_face_mask(rgb, figure)
    if face_mask.any():
        face_contour_rc = find_outer_contour(face_mask)
        if len(face_contour_rc) > 300:
            idx = np.linspace(0, len(face_contour_rc) - 1, 300).astype(int)
            face_contour_rc = face_contour_rc[idx]
        face_smoothed = fourier_smooth(face_contour_rc, FACE_FOURIER_HARM)
        print(f"Face contour points: {len(face_smoothed)}  area={int(face_mask.sum())}px")
    else:
        face_smoothed = None
        print("WARN: face mask empty — face contour skipped")

    # 11) compute silhouette bbox in pixels, scale to target mm width.
    # The face shares the silhouette's pixels-per-mm so it lands inside.
    rs, cs = smoothed[:, 0], smoothed[:, 1]
    bb_w_px = cs.max() - cs.min()
    bb_h_px = rs.max() - rs.min()
    px_per_mm = bb_w_px / SVG_TARGET_W_MM
    h_mm = bb_h_px / px_per_mm
    cmin = cs.min(); rmin = rs.min()

    def to_mm_xy(rc_pts):
        sx_mm = (rc_pts[:, 1] - cmin) / px_per_mm
        sy_mm = (rc_pts[:, 0] - rmin) / px_per_mm
        return np.column_stack((sx_mm, sy_mm))

    silhouette_xy_mm = to_mm_xy(smoothed)
    face_xy_mm = to_mm_xy(face_smoothed) if face_smoothed is not None else None

    eyes_mm = []
    for cx_px, cy_px, r_px in eyes_pix:
        ex_mm = (cx_px - cmin) / px_per_mm
        ey_mm = (cy_px - rmin) / px_per_mm
        er_mm = r_px / px_per_mm
        eyes_mm.append((ex_mm, ey_mm, er_mm))

    print(f"SVG bbox: {SVG_TARGET_W_MM:.2f} x {h_mm:.2f} mm   ({px_per_mm:.2f} px/mm)")
    if face_xy_mm is not None:
        fx_min, fx_max = face_xy_mm[:, 0].min(), face_xy_mm[:, 0].max()
        fy_min, fy_max = face_xy_mm[:, 1].min(), face_xy_mm[:, 1].max()
        print(f"  face bbox (mm): x={fx_min:.2f}..{fx_max:.2f}  y={fy_min:.2f}..{fy_max:.2f}")

    # 12) write SVGs (silhouette + eyes in one, face contour in its own)
    write_svg(silhouette_xy_mm, eyes_mm, SVG_TARGET_W_MM, h_mm, OUT_SVG)
    print(f"Wrote {OUT_SVG}")
    if face_xy_mm is not None:
        write_face_svg(face_xy_mm, SVG_TARGET_W_MM, h_mm, OUT_FACE_SVG)
        print(f"Wrote {OUT_FACE_SVG}")

    # 13) debug overlay
    OUT_DEBUG.mkdir(parents=True, exist_ok=True)
    save_debug_overlay(rgb, figure, contour_rc, face_mask if face_smoothed is not None else None,
                       face_contour_rc if face_smoothed is not None else None,
                       eyes_pix, OUT_DEBUG / "extract_debug.png")
    print(f"Wrote {OUT_DEBUG / 'extract_debug.png'}")


if __name__ == "__main__":
    main()
