"""Render the seeded talisman family as glowing bodies on black."""
import os
import sys

import numpy as np
import imageio.v2 as imageio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapes as S
import talismans as T
import preview_shapes as P


def render_pts(pts, size_mm=38.0):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    half = size_mm / 2
    n = int(size_mm * P.PX_PER_MM)
    ax = (np.arange(n) + 0.5) / P.PX_PER_MM - half
    X, Y = np.meshgrid(ax + cx, -ax + cy)

    m = P._mask(pts, X, Y)
    f = S.fit_report(pts)
    if f["hole"]:
        hy, _ = f["hole"]
        m &= ~(np.hypot(X, Y - hy) <= S.HOLE_R)

    d = m.astype(np.float32)
    acc = d.copy()
    for k in (1, 2, 3, 5, 8):
        acc[k:, :] += d[:-k, :]; acc[:-k, :] += d[k:, :]
        acc[:, k:] += d[:, :-k]; acc[:, :-k] += d[:, k:]
    acc = np.clip(acc / 11.0, 0, 1)
    lum = np.where(m, 0.55 + 0.45 * acc, 0.0)
    img = np.zeros(X.shape + (3,), np.float32)
    img[..., 0] = lum * 0.38; img[..., 1] = lum * 1.0; img[..., 2] = lum * 0.58
    img[~m] = (0.02, 0.03, 0.035)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def main(names, r_out=16.0):
    tiles = []
    for nm in names:
        pts = T.talisman(nm, r_out=r_out)
        f = S.fit_report(pts)
        if not f["ok"]:
            pts, r2, f = T.fitted(nm, lo=r_out, hi=r_out + 6)
            if pts is None:
                print("  %-10s NO FIT - skipped" % nm)
                continue
        tiles.append(render_pts(pts))
    h, w = tiles[0].shape[:2]
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    pad = 8
    out = np.full((rows * (h + pad) + pad, cols * (w + pad) + pad, 3), 10, np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        out[pad + r * (h + pad):pad + r * (h + pad) + h,
            pad + c * (w + pad):pad + c * (w + pad) + w] = t
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, "talismans_glow.png")
    imageio.imwrite(p, out)
    print("wrote %s  %dx%d" % (os.path.basename(p), out.shape[1], out.shape[0]))
    print("order: %s" % ", ".join(names))


if __name__ == "__main__":
    main(T.ROSTER)
