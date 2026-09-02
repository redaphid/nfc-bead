"""Render the adinkra set as glowing bodies on black - the night test.

The bead is single-colour strontium-aluminate PLA, so at 2am there is no
colour, no shading and no relief: the outline is the entire design. This sheet
is therefore the only honest review of the shapes. If a symbol is not
recognisable HERE it is not recognisable on someone's neck.

    uv run python beads/glow-set/preview_adinkra.py            # the set
    uv run python beads/glow-set/preview_adinkra.py --rejects  # the failures
"""
import os
import sys

import numpy as np
import imageio.v2 as imageio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adinkra as A
import preview_talismans as PT

COLS = 5
SIZE_MM = 38.0


def sheet(src, out, cols=COLS):
    tiles, names = [], []
    for nm in sorted(src):
        rings = src[nm]()
        pts = A.flatten(rings)
        tiles.append(PT.render_pts(pts, size_mm=SIZE_MM))
        names.append(nm)
    h, w = tiles[0].shape[:2]
    rows = (len(tiles) + cols - 1) // cols
    pad = 8
    img = np.full((rows * (h + pad) + pad, cols * (w + pad) + pad, 3), 10,
                  np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        img[pad + r * (h + pad):pad + r * (h + pad) + h,
            pad + c * (w + pad):pad + c * (w + pad) + w] = t
    imageio.imwrite(out, img)
    print("wrote %s  %dx%d" % (os.path.basename(out), img.shape[1], img.shape[0]))
    print("order (%d cols): %s" % (cols, ", ".join(names)))


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    if "--rejects" in sys.argv:
        sheet(A.REJECTED, os.path.join(here, "adinkra_rejects.png"))
    else:
        sheet(A.SYMBOLS, os.path.join(here, "adinkra_glow.png"))
