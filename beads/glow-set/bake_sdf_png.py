"""Bake motif silhouettes into SDF PNGs for the paper-cranes lattice.

WHY AN SDF AND NOT A SILHOUETTE. paper-cranes uploads the image buffer with
NEAREST filtering (src/Visualizer.js getTexture). A 1-bit silhouette magnified
across a lattice cell gives hard staircase edges and NO smoothstep can repair
them, because the data carries no gradient. A distance field degrades
gracefully -- quantised but still continuous and monotonic across the boundary
-- so the shader's existing smoothstep(gBorder + alias, gBorder, m) re-smooths
it into a clean line. This is the highest-leverage decision in the task.

WHY DISTANCE-TO-POLYGON AND NOT THE INTERNAL FIELD. Each MON generator builds
an exact primitive field `f`, contours it, and then applies fit_size() (and for
several mon a scale_x stretch). Those happen AFTER tracing, so the internal `f`
is NOT the shape that ships -- only the returned polygon is. We therefore
compute an exact signed distance to that final polygon.

CHANNEL LAYOUT (extends the existing taco-stencil convention, does not replace
it -- taco masks encode vec2(tex.a, tex.a * (1.0 - tex.r))):

    A  silhouette coverage, 1 inside      (existing convention)
    R  ink / interior detail              (existing convention)
    G  the SDF: 0.5 + d / (2*BEAD_RANGE)  (new; 0.5 == the boundary)
    B  spare

Usage:
    .venv/Scripts/python.exe beads/glow-set/bake_sdf_png.py --out <dir>
    .venv/Scripts/python.exe beads/glow-set/bake_sdf_png.py --out <dir> --only kiku,tomoe
"""
import argparse
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RES = 1024          # power-of-two: the lattice samples this with REPEAT wrap
MARGIN = 1.12       # bake the bleed margin INTO the image; with REPEAT wrap the
                    # shader must not reject edge texels the way taco shaders do

# G is normalised to the bake half-extent, NOT to millimetres.
#
# The brief (§6) specifies `0.5 + d / (2*BEAD_RANGE)` with BEAD_RANGE in mm. Baking mm
# would force a DIFFERENT shader constant per motif, because each mon has its own
# half-extent (kiku 16.8mm, tomoe 17.9mm, ...). Worse, the lattice compares this
# against hexDist, which is a NORM -- homogeneous of degree 1, so `hexDist(p) - r`
# is the hexagon of radius r for ANY r -- whereas a baked SDF is a distance at ONE
# fixed scale. Mixing a millimetre distance into a lattice-unit expression is
# dimensionally wrong and produces garbage at every radius except one.
#
# Normalising here means d_norm == +/-1 at the bake edge and 0 on the boundary, so
# ONE constant works for every motif and the shader can rescale to any cell radius
# by sampling at p/r and multiplying back by r. See beadDist() in the shader.
BEAD_RANGE = 1.0


def signed_distance_to_polygon(pts, X, Y):
    """Exact signed distance to a closed polygon. Negative inside.

    Unsigned distance is the min over segments of the point-to-segment
    distance; the sign comes from a separate even-odd crossing test. Doing the
    sign separately (rather than via winding on the same pass) keeps it correct
    for the non-convex mon -- katabami and matsukawa both have reflex vertices.
    """
    a = pts
    b = np.roll(pts, -1, axis=0)
    ab = b - a                                    # (N,2)
    seg2 = np.einsum('ij,ij->i', ab, ab)
    seg2 = np.where(seg2 < 1e-12, 1e-12, seg2)

    P = np.stack([X.ravel(), Y.ravel()], axis=1)  # (M,2)
    best = np.full(P.shape[0], np.inf)
    # chunk so a 1024^2 grid against ~400 segments doesn't allocate GBs at once
    CH = 65536
    for s in range(0, P.shape[0], CH):
        p = P[s:s + CH][:, None, :]               # (m,1,2)
        ap = p - a[None, :, :]                    # (m,N,2)
        t = np.einsum('mnj,nj->mn', ap, ab) / seg2
        np.clip(t, 0.0, 1.0, out=t)
        closest = a[None, :, :] + t[:, :, None] * ab[None, :, :]
        d = np.linalg.norm(p - closest, axis=2)   # (m,N)
        best[s:s + CH] = d.min(axis=1)
    dist = best.reshape(X.shape)

    # even-odd point-in-polygon, vectorised over the grid
    inside = np.zeros(X.shape, dtype=bool)
    for i in range(len(a)):
        x0, y0 = a[i]
        x1, y1 = b[i]
        if y0 == y1:
            continue
        crosses = (y0 > Y) != (y1 > Y)
        xint = x0 + (Y - y0) * (x1 - x0) / (y1 - y0)
        inside ^= crosses & (X < xint)

    return np.where(inside, -dist, dist)


def bake(name, pts, out_dir):
    pts = np.asarray(pts, dtype=np.float64)
    half = float(np.abs(pts).max()) * MARGIN

    ax = np.linspace(-half, half, RES)
    # The texture is uploaded with UNPACK_FLIP_Y_WEBGL=true, so row 0 of the PNG
    # becomes v=0 at the BOTTOM in GL. Building Y ascending here and writing the
    # array straight out therefore lands right-way-up in the shader. Harmless for
    # the radially symmetric mon; visible on tomoe and ogi, which is the check.
    X, Y = np.meshgrid(ax, ax)

    d = signed_distance_to_polygon(pts, X, Y)

    dn = d / half                      # normalised: 0 on the boundary, +/-1 at the bake edge
    inside = d < 0.0
    A = inside.astype(np.float32)
    # G: 0.5 at the boundary. Normalised (see BEAD_RANGE) so one shader constant
    # serves every motif. 8-bit over +/-half gives ~half/128 mm per step -- about
    # 0.13mm on a 30mm bead, far finer than any fillet.
    G = np.clip(0.5 + dn / (2.0 * BEAD_RANGE), 0.0, 1.0).astype(np.float32)
    # R: ink strength. The taco convention is vec2(a, a*(1-r)), i.e. r is
    # INVERTED ink, so a solid interior is r=0. Give a soft inward ramp so a
    # shader can pick out the rim without a second texture.
    R = np.where(inside, np.clip(-dn * 6.0, 0.0, 1.0), 0.0).astype(np.float32)
    B = np.zeros_like(A)

    rgba = (np.stack([R, G, B, A], axis=2) * 255.0).round().astype(np.uint8)
    path = os.path.join(out_dir, f"mon-{name}.png")
    Image.fromarray(rgba, mode="RGBA").save(path)
    return path, half, float(d.min()), float(d.max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--size", type=float, default=30.0)
    args = ap.parse_args()

    import japanese

    os.makedirs(args.out, exist_ok=True)
    wanted = [s for s in args.only.split(",") if s] or list(japanese.MON)

    print(f"RES={RES} BEAD_RANGE={BEAD_RANGE}mm MARGIN={MARGIN} -> {args.out}")
    for name in wanted:
        fn = japanese.MON.get(name)
        if fn is None:
            print(f"  !! unknown motif {name}")
            continue
        try:
            pts = fn(args.size) if name != "tomoe" else fn()
            path, half, dmin, dmax = bake(name, pts, args.out)
            print(f"  {name:10s} verts={len(pts):4d} half={half:6.2f}mm "
                  f"d=[{dmin:7.2f},{dmax:6.2f}] -> {os.path.basename(path)}")
        except Exception as e:  # a motif that fails should not kill the batch
            print(f"  !! {name}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
