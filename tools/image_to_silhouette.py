"""Extract a clean SVG bead silhouette from a raster image.

Generalized from `beads/redaphid-portrait/extract_silhouette.py` — same
laser-cube-driver pipeline (gaussian-blur -> luma threshold -> fill-holes
-> moore-boundary -> fourier-smooth) plus optional accent-region detectors
(eye warm-chroma blobs, geometric haircut from eye anchors).

Usage:
    uv run nfc-image-to-silhouette --src input.png --out beads/<charm>/
    uv run nfc-image-to-silhouette --src input.png --out . --detect-hair
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import measure


# ─── Tunables ────────────────────────────────────────────────────────────
DEFAULTS = dict(
    blur_sigma=3.0,
    luma_threshold=22,
    morph_close_r=4,
    fourier_harmonics=24,
    target_width_mm=25.0,

    # Eye chroma — warm dot inside cool body
    eye_warm_min=30,
    eye_min_area=80,
    eye_max_area=8000,

    # Hair geometric anchors (from eye centroid + eye spacing)
    hair_blur_sigma=4.0,
    hair_eyebrow_factor=0.55,
    hair_jawline_factor=1.4,
    hair_side_factor=1.2,
    hair_morph_close=5,
    hair_fourier_harm=14,
)


# ─── Pipeline primitives ─────────────────────────────────────────────────
def luminance(rgb: np.ndarray) -> np.ndarray:
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def keep_largest_component(mask: np.ndarray) -> np.ndarray:
    labeled, n = ndimage.label(mask)
    if n == 0:
        return mask
    sizes = ndimage.sum(mask, labeled, range(1, n + 1))
    return labeled == 1 + int(np.argmax(sizes))


def fourier_smooth(contour_xy: np.ndarray, harmonics: int) -> np.ndarray:
    """Smooth a closed 2D contour by truncating its FFT to `harmonics` modes."""
    z = contour_xy[:, 0] + 1j * contour_xy[:, 1]
    Z = np.fft.fft(z)
    mask = np.zeros_like(Z, dtype=bool)
    mask[0] = True
    mask[1:harmonics + 1] = True
    mask[-harmonics:] = True
    Z_smooth = np.where(mask, Z, 0)
    z_smooth = np.fft.ifft(Z_smooth)
    return np.column_stack((z_smooth.real, z_smooth.imag))


def find_outer_contour(mask: np.ndarray):
    contours = measure.find_contours(mask.astype(np.uint8), level=0.5)
    if not contours:
        raise RuntimeError("No contour found — silhouette mask empty?")
    contours.sort(key=lambda c: -len(c))
    return contours[0]


# ─── Region extractors ───────────────────────────────────────────────────
def extract_silhouette_mask(rgb: np.ndarray, params: dict) -> np.ndarray:
    blurred = ndimage.gaussian_filter(
        rgb.astype(np.float32),
        sigma=(params["blur_sigma"], params["blur_sigma"], 0),
    )
    fig = luminance(blurred) > params["luma_threshold"]
    structure = ndimage.generate_binary_structure(2, 2)
    fig = ndimage.binary_closing(fig, structure=structure, iterations=params["morph_close_r"])
    fig = ndimage.binary_fill_holes(fig)
    return keep_largest_component(fig)


def extract_eyes(rgb: np.ndarray, params: dict):
    R = rgb[..., 0].astype(np.int16)
    B = rgb[..., 2].astype(np.int16)
    eye_mask = (R - B) > params["eye_warm_min"]
    eye_mask = ndimage.binary_opening(eye_mask, iterations=2)
    eye_mask = ndimage.binary_closing(eye_mask, iterations=2)
    labeled, n = ndimage.label(eye_mask)

    eyes = []
    for lab in range(1, n + 1):
        comp = labeled == lab
        area = int(comp.sum())
        if not (params["eye_min_area"] <= area <= params["eye_max_area"]):
            continue
        ys, xs = np.where(comp)
        cx, cy = float(xs.mean()), float(ys.mean())
        r = float(np.sqrt(area / np.pi))
        eyes.append((cx, cy, r, area))

    eyes.sort(key=lambda e: -e[3])              # area desc
    eyes = [(cx, cy, r) for (cx, cy, r, _a) in eyes[:2]]
    eyes.sort(key=lambda e: e[0])               # left-to-right
    return eyes


def extract_hair_mask(silhouette_mask: np.ndarray, eyes_pix, params: dict) -> np.ndarray:
    if len(eyes_pix) < 2:
        return np.zeros_like(silhouette_mask)
    eye_l, eye_r = sorted(eyes_pix, key=lambda e: e[0])[0], sorted(eyes_pix, key=lambda e: e[0])[-1]
    eye_y = (eye_l[1] + eye_r[1]) / 2.0
    cx = (eye_l[0] + eye_r[0]) / 2.0
    eye_spacing = abs(eye_r[0] - eye_l[0])

    eyebrow_y = eye_y - eye_spacing * params["hair_eyebrow_factor"]
    jawline_y = eye_y + eye_spacing * params["hair_jawline_factor"]
    side_dx   = eye_spacing * params["hair_side_factor"]

    yy, xx = np.indices(silhouette_mask.shape)
    above_brow = silhouette_mask & (yy < eyebrow_y)
    side_flap  = silhouette_mask & (yy < jawline_y) & (np.abs(xx - cx) > side_dx)
    hair = above_brow | side_flap
    hair = ndimage.binary_closing(hair, iterations=params["hair_morph_close"])
    hair = keep_largest_component(hair)
    hair = ndimage.binary_fill_holes(hair)
    return hair


# ─── SVG output ──────────────────────────────────────────────────────────
def path_d(pts_xy_mm: np.ndarray) -> str:
    d = "M " + f"{pts_xy_mm[0,0]:.3f},{pts_xy_mm[0,1]:.3f} "
    for x, y in pts_xy_mm[1:]:
        d += f"L {x:.3f},{y:.3f} "
    d += "Z"
    return d


def write_silhouette_svg(path_xy_mm, eyes_xyr_mm, w_mm, h_mm, out_path: Path):
    d = path_d(path_xy_mm)
    eyes_svg = "\n".join(
        f'  <circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" fill="black" />'
        for (cx, cy, r) in eyes_xyr_mm
    )
    svg = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm:.3f}mm" height="{h_mm:.3f}mm" viewBox="0 0 {w_mm:.3f} {h_mm:.3f}">
  <path id="silhouette" d="{d}" fill="black" />
{eyes_svg}
</svg>
'''
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")


def write_hair_svg(path_xy_mm, w_mm, h_mm, out_path: Path):
    d = path_d(path_xy_mm)
    svg = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm:.3f}mm" height="{h_mm:.3f}mm" viewBox="0 0 {w_mm:.3f} {h_mm:.3f}">
  <path id="hair" d="{d}" fill="magenta" />
</svg>
'''
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")


def save_debug_overlay(rgb, sil_mask, sil_contour_rc, hair_mask, hair_contour_rc, eyes_pix, out_path: Path):
    overlay = rgb.copy()
    tint = np.zeros_like(rgb); tint[..., 1] = 80; tint[..., 2] = 80
    overlay = np.where(sil_mask[..., None], (overlay * 0.7 + tint * 0.3).astype(np.uint8), overlay)
    if hair_mask is not None:
        htint = np.zeros_like(rgb); htint[..., 0] = 200; htint[..., 2] = 200
        overlay = np.where(hair_mask[..., None], (overlay * 0.6 + htint * 0.4).astype(np.uint8), overlay)

    def stipple(contour, color):
        if contour is None or len(contour) == 0:
            return
        rr = np.clip(contour[:, 0].astype(int), 0, rgb.shape[0] - 1)
        cc = np.clip(contour[:, 1].astype(int), 0, rgb.shape[1] - 1)
        overlay[rr, cc] = color

    stipple(sil_contour_rc,  (255, 64, 64))
    stipple(hair_contour_rc, (255, 64, 200))
    for cx, cy, r in eyes_pix:
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                y, x = int(cy + dy), int(cx + dx)
                if 0 <= y < rgb.shape[0] and 0 <= x < rgb.shape[1]:
                    overlay[y, x] = (0, 255, 0)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(overlay).save(out_path)


# ─── Driver ──────────────────────────────────────────────────────────────
def run(src: Path, out_dir: Path, params: dict, detect_eyes: bool, detect_hair: bool, debug_dir: Path | None) -> int:
    rgb = np.array(Image.open(src).convert("RGB"))
    H, W = rgb.shape[:2]
    print(f"Loaded {src}: {W}x{H}")

    sil_mask = extract_silhouette_mask(rgb, params)
    print(f"Silhouette pixels: {int(sil_mask.sum())}")

    contour_rc = find_outer_contour(sil_mask)
    target_n = 400
    if len(contour_rc) > target_n:
        idx = np.linspace(0, len(contour_rc) - 1, target_n).astype(int)
        contour_rc = contour_rc[idx]
    smoothed = fourier_smooth(contour_rc, params["fourier_harmonics"])

    eyes_pix = extract_eyes(rgb, params) if detect_eyes else []
    print(f"Eyes found: {len(eyes_pix)}")
    for cx, cy, r in eyes_pix:
        print(f"  eye @ ({cx:.0f},{cy:.0f}) r={r:.1f} px")

    hair_mask = None
    hair_smoothed = None
    hair_contour_rc = None
    if detect_hair and len(eyes_pix) >= 2:
        hair_mask = extract_hair_mask(sil_mask, eyes_pix, params)
        if hair_mask.any():
            hair_contour_rc = find_outer_contour(hair_mask)
            if len(hair_contour_rc) > 300:
                idx = np.linspace(0, len(hair_contour_rc) - 1, 300).astype(int)
                hair_contour_rc = hair_contour_rc[idx]
            hair_smoothed = fourier_smooth(hair_contour_rc, params["hair_fourier_harm"])
            print(f"Hair contour: {len(hair_smoothed)} pts, area={int(hair_mask.sum())}px")

    # Scale silhouette to target_width_mm
    rs, cs = smoothed[:, 0], smoothed[:, 1]
    bb_w_px = cs.max() - cs.min()
    bb_h_px = rs.max() - rs.min()
    px_per_mm = bb_w_px / params["target_width_mm"]
    h_mm = bb_h_px / px_per_mm
    cmin, rmin = cs.min(), rs.min()

    def to_mm_xy(rc):
        return np.column_stack(((rc[:, 1] - cmin) / px_per_mm, (rc[:, 0] - rmin) / px_per_mm))

    sil_xy_mm = to_mm_xy(smoothed)
    hair_xy_mm = to_mm_xy(hair_smoothed) if hair_smoothed is not None else None
    eyes_mm = [
        ((cx - cmin) / px_per_mm, (cy - rmin) / px_per_mm, r / px_per_mm)
        for cx, cy, r in eyes_pix
    ]
    print(f"SVG bbox: {params['target_width_mm']:.2f} x {h_mm:.2f} mm   ({px_per_mm:.2f} px/mm)")

    write_silhouette_svg(sil_xy_mm, eyes_mm, params["target_width_mm"], h_mm,
                         out_dir / "silhouette.svg")
    print(f"Wrote {out_dir / 'silhouette.svg'}")
    if hair_xy_mm is not None:
        write_hair_svg(hair_xy_mm, params["target_width_mm"], h_mm,
                       out_dir / "hair.svg")
        print(f"Wrote {out_dir / 'hair.svg'}")

    if debug_dir is not None:
        debug_path = debug_dir / "extract_debug.png"
        save_debug_overlay(rgb, sil_mask, contour_rc, hair_mask, hair_contour_rc, eyes_pix, debug_path)
        print(f"Wrote {debug_path}")

    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--src", required=True, help="Input image path (PNG/JPG)")
    p.add_argument("--out", required=True, help="Output directory for silhouette.svg / hair.svg")
    p.add_argument("--target-width-mm", type=float, default=DEFAULTS["target_width_mm"])
    p.add_argument("--detect-eyes",  action="store_true", help="Detect eye blobs by R-B chroma")
    p.add_argument("--detect-hair",  action="store_true", help="Detect haircut shape (implies --detect-eyes)")
    p.add_argument("--luma-threshold",     type=int,   default=DEFAULTS["luma_threshold"])
    p.add_argument("--blur-sigma",         type=float, default=DEFAULTS["blur_sigma"])
    p.add_argument("--fourier-harmonics",  type=int,   default=DEFAULTS["fourier_harmonics"])
    p.add_argument("--eye-warm-min",       type=int,   default=DEFAULTS["eye_warm_min"])
    p.add_argument("--hair-side-factor",   type=float, default=DEFAULTS["hair_side_factor"])
    p.add_argument("--hair-eyebrow-factor",type=float, default=DEFAULTS["hair_eyebrow_factor"])
    p.add_argument("--hair-jawline-factor",type=float, default=DEFAULTS["hair_jawline_factor"])
    p.add_argument("--debug-dir", default=None, help="Write extract_debug.png here (default: tmp/screenshots/)")
    args = p.parse_args()

    params = dict(DEFAULTS)
    for k in ("target_width_mm", "luma_threshold", "blur_sigma",
              "fourier_harmonics", "eye_warm_min", "hair_side_factor",
              "hair_eyebrow_factor", "hair_jawline_factor"):
        cli_k = k.replace("_", "_")
        params[k] = getattr(args, cli_k)

    src = Path(args.src)
    out_dir = Path(args.out)
    if args.debug_dir:
        debug_dir = Path(args.debug_dir)
    else:
        # default: tmp/screenshots at repo root
        here = Path(__file__).resolve()
        for parent in here.parents:
            if (parent / "tmp").is_dir():
                debug_dir = parent / "tmp" / "screenshots"
                break
        else:
            debug_dir = Path.cwd() / "tmp" / "screenshots"

    detect_eyes = args.detect_eyes or args.detect_hair
    detect_hair = args.detect_hair

    return run(src, out_dir, params, detect_eyes, detect_hair, debug_dir)


if __name__ == "__main__":
    sys.exit(main())
