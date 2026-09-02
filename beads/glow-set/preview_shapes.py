"""Render the silhouette family: how they glow, and whether they fit.

Two sheets:
  shapes_glow.png  - the shape as a glowing body on black. This is the honest
                     night test: the OUTLINE is the whole design, so if a shape
                     is not recognisable here it is not recognisable at 2am.
  shapes_fit.png   - the same shapes with the solver's chosen NFC pocket, pegs
                     and string hole drawn on, so the engineering is visible.

    uv run python beads/glow-set/preview_shapes.py
"""
import math
import os
import sys

import numpy as np
import imageio.v2 as imageio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapes as S

PX_PER_MM = 13
COLS = 5
MARGIN = 3.0          # mm of dark around each shape


def _mask(pts, X, Y):
    """Even-odd fill, vectorised."""
    inside = np.zeros(X.shape, bool)
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if y1 == y2:
            continue
        cond = ((y1 > Y) != (y2 > Y))
        xin = x1 + (Y - y1) * (x2 - x1) / (y2 - y1)
        inside ^= cond & (X < xin)
    return inside


def render(name, fit=False, size_mm=34.0):
    pts = S.SHAPES[name]()
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    half = size_mm / 2
    n = int(size_mm * PX_PER_MM)
    ax = (np.arange(n) + 0.5) / PX_PER_MM - half
    X, Y = np.meshgrid(ax + cx, -ax + cy)

    m = _mask(pts, X, Y)
    f = S.fit_report(pts)

    # string hole is a real void through the body
    if f["hole"]:
        hy, _ = f["hole"]
        m &= ~(np.hypot(X - 0.0, Y - hy) <= S.HOLE_R)

    img = np.zeros(X.shape + (3,), np.float32)
    if fit:
        img[m] = (0.16, 0.20, 0.17)
        px, py, _ = f["pocket"]
        img[m & (np.hypot(X - px, Y - py) <= S.POCKET_R)] = (0.55, 0.15, 0.55)
        for (gx, gy) in (f["pegs"] or []):
            img[m & (np.hypot(X - gx, Y - gy) <= S.PEG_R)] = (0.95, 0.80, 0.15)
        edge = m & ~(
            _mask([(x - 0.35, y) for x, y in pts], X, Y) &
            _mask([(x + 0.35, y) for x, y in pts], X, Y))
        img[edge] = (0.45, 0.85, 0.55)
    else:
        # glowing body: bright core, softer toward the rim
        d = np.zeros(X.shape, np.float32)
        d[m] = 1.0
        # cheap inward falloff via successive erosion-ish blur
        acc = d.copy()
        for k in (1, 2, 3, 5, 8):
            acc[k:, :] += d[:-k, :]; acc[:-k, :] += d[k:, :]
            acc[:, k:] += d[:, :-k]; acc[:, :-k] += d[:, k:]
        acc = np.clip(acc / 11.0, 0, 1)
        lum = np.where(m, 0.55 + 0.45 * acc, 0.0)
        img[..., 0] = lum * 0.38
        img[..., 1] = lum * 1.00
        img[..., 2] = lum * 0.58
        img[~m] = (0.02, 0.03, 0.035)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8), f


def sheet(names, fit=False):
    tiles, fits = [], []
    for nm in names:
        t, f = render(nm, fit=fit)
        tiles.append(t); fits.append((nm, f))
    h, w = tiles[0].shape[:2]
    rows = (len(tiles) + COLS - 1) // COLS
    pad = 8
    out = np.full((rows * (h + pad) + pad, COLS * (w + pad) + pad, 3),
                  10 if not fit else 18, np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, COLS)
        y, x = pad + r * (h + pad), pad + c * (w + pad)
        out[y:y + h, x:x + w] = t
    return out, fits


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    names = sorted(S.SHAPES)
    for fit, tag in ((False, "glow"), (True, "fit")):
        img, fits = sheet(names, fit=fit)
        p = os.path.join(here, "shapes_%s.png" % tag)
        imageio.imwrite(p, img)
        print("wrote %s  %dx%d" % (os.path.basename(p), img.shape[1], img.shape[0]))
    print()
    print("order (%d cols): %s" % (COLS, ", ".join(names)))


if __name__ == "__main__":
    main()
