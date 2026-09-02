"""Render the Chinese motif family as glowing bodies on black.

This is the only test that matters for these beads. The audit in chinese.py
proves a shape can be MADE; this proves whether it can be READ. A motif that
survives here at 2am on a dark porch has earned its slot and a motif that turns
into a blob has not, however good its provenance.

    uv run python beads/glow-set/preview_chinese.py
    uv run python beads/glow-set/preview_chinese.py ruyi hulu   # just these
"""
import os
import sys

import numpy as np
import imageio.v2 as imageio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapes as S
import chinese as C
import preview_shapes as P

PX_PER_MM = 13
COLS = 5
SIZE_MM = 34.0


def render(pts, voids, size_mm=SIZE_MM, hole=True):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    half = size_mm / 2
    n = int(size_mm * PX_PER_MM)
    ax = (np.arange(n) + 0.5) / PX_PER_MM - half
    X, Y = np.meshgrid(ax + cx, -ax + cy)

    m = P._mask(pts, X, Y)
    for v in voids:
        m &= ~P._mask(v, X, Y)
    if hole:
        f = S.fit_report(C.simplify(pts, 0.05))
        if f["hole"]:
            hy, _ = f["hole"]
            m &= ~(np.hypot(X, Y - hy) <= S.HOLE_R)

    d = m.astype(np.float32)
    acc = d.copy()
    for k in (1, 2, 3, 5, 8):
        acc[k:, :] += d[:-k, :]
        acc[:-k, :] += d[k:, :]
        acc[:, k:] += d[:, :-k]
        acc[:, :-k] += d[:, k:]
    acc = np.clip(acc / 11.0, 0, 1)
    lum = np.where(m, 0.55 + 0.45 * acc, 0.0)
    img = np.zeros(X.shape + (3,), np.float32)
    img[..., 0] = lum * 0.38
    img[..., 1] = lum * 1.00
    img[..., 2] = lum * 0.58
    img[~m] = (0.02, 0.03, 0.035)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def main(names):
    tiles = []
    for nm in names:
        m = C.build(nm)
        tiles.append(render(m.pts, m.voids))
        print("  %-13s %s" % (nm, m.note))
    h, w = tiles[0].shape[:2]
    rows = (len(tiles) + COLS - 1) // COLS
    pad = 8
    out = np.full((rows * (h + pad) + pad, COLS * (w + pad) + pad, 3), 10, np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, COLS)
        out[pad + r * (h + pad):pad + r * (h + pad) + h,
            pad + c * (w + pad):pad + c * (w + pad) + w] = t
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, "chinese_glow.png" if len(names) <= len(C.SHAPES)
                     else "chinese_glow_all.png")
    imageio.imwrite(p, out)
    print("\nwrote %s  %dx%d" % (os.path.basename(p), out.shape[1], out.shape[0]))
    print("order (%d cols): %s" % (COLS, ", ".join(names)))


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--all"]:
        args = list(C.ALL)
    main(args or list(C.SHAPES))
