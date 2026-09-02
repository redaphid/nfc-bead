"""Raster preview of glow-medallion glyphs, with a physical glow model.

Rasterises each glyph analytically (signed distance per primitive) and shades it
the way the printed bead will actually look in the dark.

The glow model is the point of this file. Emission is NOT simply "less material
= darker" - glow PLA scatters, so brightness saturates after ~1-2mm and a wide
shallow pocket is invisible. What darkens a groove is APERTURE: the fraction of
the hemisphere that is not blocked by the groove walls. We approximate that with
depth/width, which is exactly the aspect ratio the build script enforces:

    occlusion = clamp(depth / (width + depth), 0, 1)

so a 0.8mm-wide 1.2mm-deep groove is strongly occluded (0.60) while a 3mm-wide
one barely registers (0.29). Wide strokes correctly look washed out here, which
is the whole reason to preview.

    uv run python beads/glow-set/preview_png.py
"""
import math
import os
import sys

import numpy as np
import imageio.v2 as imageio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glyphs as G

PX_PER_MM = 26
BEAD_R = 11.0
DEPTH = 1.2          # RECESS_DEPTH
COLS = 4


def _seg_dist(px, py, x1, y1, x2, y2):
    vx, vy = x2 - x1, y2 - y1
    L2 = vx * vx + vy * vy
    if L2 < 1e-12:
        return np.hypot(px - x1, py - y1)
    t = np.clip(((px - x1) * vx + (py - y1) * vy) / L2, 0.0, 1.0)
    return np.hypot(px - (x1 + t * vx), py - (y1 + t * vy))


def render_bead(glyph, px_per_mm=PX_PER_MM, night=True):
    n = int(BEAD_R * 2 * px_per_mm)
    ax = (np.arange(n) + 0.5) / px_per_mm - BEAD_R
    X, Y = np.meshgrid(ax, -ax)
    Rr = np.hypot(X, Y)

    # occlusion accumulates per primitive, keyed on that primitive's own width
    occ = np.zeros_like(X)

    def stamp(mask, width):
        a = DEPTH / (width + DEPTH)          # aperture darkening
        np.maximum(occ, mask * a, out=occ)

    for p in glyph:
        k = p[0]
        if k == "dot":
            _, x, y, r = p
            stamp((np.hypot(X - x, Y - y) <= r).astype(float), r * 2)
        elif k == "line":
            _, x1, y1, x2, y2, w = p
            stamp((_seg_dist(X, Y, x1, y1, x2, y2) <= w / 2).astype(float), w)
        elif k == "ring":
            ri, ro = p[1], p[2]
            stamp(((Rr >= ri) & (Rr <= ro)).astype(float), ro - ri)

    inside = Rr <= BEAD_R
    # string hole at y = +8mm
    hole = np.hypot(X, Y - 8.0) <= 0.6

    if night:
        base = 1.0 - 0.28 * (Rr / BEAD_R) ** 2      # gentle falloff to the rim
        lum = base * (1.0 - 0.82 * occ)
        rgb = np.stack([lum * 0.42, lum * 1.0, lum * 0.62], -1)
    else:
        # daylight: engraving reads as shadow, plus a lit edge on one side
        base = np.full_like(X, 0.80)
        lum = base * (1.0 - 0.55 * occ)
        rgb = np.stack([lum * 0.86, lum * 0.92, lum * 0.86], -1)

    bg = np.array([0.02, 0.03, 0.04]) if night else np.array([0.10, 0.11, 0.12])
    img = np.where(inside[..., None], rgb, bg)
    img = np.where(hole[..., None], bg, img)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def sheet(names, theme, night=True):
    tiles = [render_bead(G.build(theme, nm), night=night) for nm in names]
    h, w = tiles[0].shape[:2]
    rows = (len(tiles) + COLS - 1) // COLS
    pad = 10
    bg = 6 if night else 26
    out = np.full((rows * (h + pad) + pad, COLS * (w + pad) + pad, 3), bg, np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, COLS)
        y, x = pad + r * (h + pad), pad + c * (w + pad)
        out[y:y + h, x:x + w] = t
    return out


def main(names):
    here = os.path.dirname(os.path.abspath(__file__))
    paths = []
    for theme in ("star", "sigil", "groove"):
        for night, tag in ((True, "night"), (False, "day")):
            img = sheet(names, theme, night=night)
            p = os.path.join(here, "preview_%s_%s.png" % (theme, tag))
            imageio.imwrite(p, img)
            paths.append(p)
            print("wrote %s  %dx%d" % (os.path.basename(p), img.shape[1], img.shape[0]))
    return paths


if __name__ == "__main__":
    roster = sys.argv[1:] or ["sterling", "brycen", "fm__lou", "eddy_hart",
                              "elli", "redaphid", "jared", "virginia"]
    main(roster)
