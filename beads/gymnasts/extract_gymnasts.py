"""Extract 6 gymnast silhouettes from a single multi-figure image.

Adapted from tools/image_to_silhouette.py for a SIMPLIFIED bead (no NFC pocket,
no split, no pegs — just an extruded outline with a through-thickness string
hole). Differences from the generic extractor:

  * The source image is BLACK figures on a WHITE background (inverted vs the
    glow-portrait pipeline), so the figure mask is `luma < threshold`.
  * There are MULTIPLE figures plus a border frame, so we label all components,
    drop the frame (spans the whole image) and specks, and keep the rest.
  * Each figure is emitted independently (its own bbox, scaled so its LONGEST
    side == TARGET_MAX_MM) into a shared regions.json the Blender build reads.
  * A string-hole position is auto-computed per figure via the Euclidean
    distance transform: the thickest interior point (preferring the upper body)
    so the hole always lands in load-bearing material.

Output: beads/gymnasts/regions.json + beads/gymnasts/extract_debug.png
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import measure

# ─── Tunables ────────────────────────────────────────────────────────────
SRC            = Path(r"C:\Users\hypnodroid\Downloads\handstand.png")
OUT_DIR        = Path(__file__).resolve().parent
TARGET_MAX_MM  = 17.5     # longest bbox side of each figure -> this many mm (~30% smaller than 25)
THICKNESS_MM   = 2.5      # NOT scaled with size — keeps parts sturdy + hole walls printable
BLUR_SIGMA     = 1.5
LUMA_THRESHOLD = 128      # luma < this == figure (dark on white)
MIN_AREA_PX    = 2000     # drop specks / antialias crumbs
FRAME_BBOX_FRAC = 0.85    # a component whose bbox spans > this of BOTH dims == frame
FOURIER_HARM   = 48       # contour smoothing; high to preserve thin limbs/toes
CONTOUR_PTS    = 600
# Hole scaled 0.7x with the figure (2.0/1.0 -> 1.4/0.7) so the SAME poses keep
# a hole at the smaller size — a fixed 2mm hole would be too big a fraction.
HOLE_DIA_MM    = 1.4
HOLE_WALL_MM   = 0.7      # min material between hole edge and silhouette boundary
HOLE_UPPER_FRAC = 0.45    # search top this fraction of the figure first for a hole


def luminance(rgb: np.ndarray) -> np.ndarray:
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def fourier_smooth(contour_xy: np.ndarray, harmonics: int) -> np.ndarray:
    z = contour_xy[:, 0] + 1j * contour_xy[:, 1]
    Z = np.fft.fft(z)
    mask = np.zeros_like(Z, dtype=bool)
    mask[0] = True
    mask[1:harmonics + 1] = True
    mask[-harmonics:] = True
    z_smooth = np.fft.ifft(np.where(mask, Z, 0))
    return np.column_stack((z_smooth.real, z_smooth.imag))


def find_figures(rgb: np.ndarray):
    """Return list of boolean masks, one per figure, in reading order."""
    blurred = ndimage.gaussian_filter(rgb.astype(np.float32), sigma=(BLUR_SIGMA, BLUR_SIGMA, 0))
    fig = luminance(blurred) < LUMA_THRESHOLD
    fig = ndimage.binary_fill_holes(fig)

    H, W = fig.shape
    labeled, n = ndimage.label(fig, structure=ndimage.generate_binary_structure(2, 2))
    figs = []
    for lab in range(1, n + 1):
        comp = labeled == lab
        area = int(comp.sum())
        if area < MIN_AREA_PX:
            continue
        ys, xs = np.where(comp)
        bw = xs.max() - xs.min()
        bh = ys.max() - ys.min()
        if bw > FRAME_BBOX_FRAC * W and bh > FRAME_BBOX_FRAC * H:
            continue  # the border frame
        figs.append((comp, area, ys.min(), xs.min()))
    # reading order: top-to-bottom by row-band, then left-to-right
    figs.sort(key=lambda f: (round(f[2] / (H * 0.33)), f[3]))
    return [f[0] for f in figs]


def outer_contour(mask: np.ndarray) -> np.ndarray:
    contours = measure.find_contours(mask.astype(np.uint8), level=0.5)
    contours.sort(key=lambda c: -len(c))
    return contours[0]  # (row, col)


def compute_hole(mask: np.ndarray, px_per_mm: float):
    """Pick the thickest interior point (preferring the upper body) for a
    through-thickness string hole. Returns (col, row) in pixel coords, or None."""
    dist = ndimage.distance_transform_edt(mask)  # px to nearest edge
    need_px = (HOLE_DIA_MM / 2 + HOLE_WALL_MM) * px_per_mm
    ys, xs = np.where(mask)
    rmin, rmax = ys.min(), ys.max()
    upper_cut = rmin + (rmax - rmin) * HOLE_UPPER_FRAC

    # candidates in the upper region that clear the wall requirement
    upper = mask.copy()
    upper[int(upper_cut):, :] = False
    upper_dist = dist * upper
    if upper_dist.max() >= need_px:
        r, c = np.unravel_index(np.argmax(upper_dist), dist.shape)
        return int(c), int(r)
    # fallback: global thickest point
    if dist.max() >= need_px:
        r, c = np.unravel_index(np.argmax(dist), dist.shape)
        return int(c), int(r)
    return None  # too thin anywhere — figure can't host a hole


def main() -> int:
    rgb = np.array(Image.open(SRC).convert("RGB"))
    H, W = rgb.shape[:2]
    print(f"Loaded {SRC}: {W}x{H}")

    figs = find_figures(rgb)
    print(f"Figures kept: {len(figs)}")

    overlay = rgb.copy()
    out = {"target_max_mm": TARGET_MAX_MM, "thickness_mm": THICKNESS_MM,
           "hole_dia_mm": HOLE_DIA_MM, "figures": []}

    for i, mask in enumerate(figs, 1):
        contour_rc = outer_contour(mask)
        if len(contour_rc) > CONTOUR_PTS:
            idx = np.linspace(0, len(contour_rc) - 1, CONTOUR_PTS).astype(int)
            contour_rc = contour_rc[idx]
        sm = fourier_smooth(contour_rc, FOURIER_HARM)  # (row, col)

        rs, cs = sm[:, 0], sm[:, 1]
        bb_w_px = cs.max() - cs.min()
        bb_h_px = rs.max() - rs.min()
        px_per_mm = max(bb_w_px, bb_h_px) / TARGET_MAX_MM
        cmin, rmin = cs.min(), rs.min()

        # mm polygon, Y-up (flip image row), origin at figure bbox min
        poly = np.column_stack(((cs - cmin) / px_per_mm,
                                (bb_h_px - (rs - rmin)) / px_per_mm))

        hole = compute_hole(mask, px_per_mm)
        hole_mm = None
        if hole is not None:
            hc, hr = hole
            hole_mm = {"x": (hc - cmin) / px_per_mm,
                       "y": (bb_h_px - (hr - rmin)) / px_per_mm,
                       "r": HOLE_DIA_MM / 2}

        out["figures"].append({
            "name": f"pose{i}",
            "width_mm": bb_w_px / px_per_mm,
            "height_mm": bb_h_px / px_per_mm,
            "polygon": [[round(x, 4), round(y, 4)] for x, y in poly],
            "hole": (None if hole_mm is None
                     else {k: round(v, 4) for k, v in hole_mm.items()}),
        })
        hole_desc = "none" if hole_mm is None else f"({hole_mm['x']:.1f},{hole_mm['y']:.1f})"
        print(f"  pose{i}: {bb_w_px/px_per_mm:5.1f} x {bb_h_px/px_per_mm:5.1f} mm  hole={hole_desc}")

        # debug overlay
        tint = np.zeros_like(rgb); tint[..., 1] = 120
        overlay = np.where(mask[..., None], (overlay * 0.55 + tint * 0.45).astype(np.uint8), overlay)
        rr = np.clip(contour_rc[:, 0].astype(int), 0, H - 1)
        cc = np.clip(contour_rc[:, 1].astype(int), 0, W - 1)
        overlay[rr, cc] = (255, 64, 64)
        if hole is not None:
            hc, hr = hole
            yy, xx = np.ogrid[:H, :W]
            ring = (xx - hc) ** 2 + (yy - hr) ** 2
            rpx = (HOLE_DIA_MM / 2) * px_per_mm
            overlay[np.abs(np.sqrt(ring) - rpx) < 1.5] = (0, 160, 255)

    (OUT_DIR / "regions.json").write_text(json.dumps(out, indent=2))
    print(f"Wrote {OUT_DIR / 'regions.json'}")
    Image.fromarray(overlay).save(OUT_DIR / "extract_debug.png")
    print(f"Wrote {OUT_DIR / 'extract_debug.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
