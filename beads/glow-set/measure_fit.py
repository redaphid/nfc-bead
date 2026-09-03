"""Measure the snap fit off the EXPORTED STLs, not off the CONFIG constants.

Recipe gotcha #40: the socket lead-in and the peg tip chamfer both eat into the
length over which the peg is actually held, and hand-estimating that from
PEG_HEIGHT / SOCKET_LEADIN / PEG_CHAMFER got it wrong by about 2x. So measure:
cross-section both halves at 0.1mm steps and compare the socket bore radius to
the peg radius at the same seated height.

ENGAGEMENT is the answer - the total height over which the gap is at or below
the design clearance. On this bead family ~1.0mm snaps and holds; 0.50mm was
audibly loose no matter what PEG_CLEAR said.

Peg positions are DISCOVERED, not assumed. An earlier version hardcoded one
silhouette's peg coordinates and then reported a confident 0.00mm on every
other shape, because it was probing empty plastic - a measurement tool that
returns a plausible number for the wrong place is worse than no tool. The pegs
are the only islands standing above the mating face, so they can simply be
found.

--gap-max IS NOT COSMETIC. "At or below the design clearance" was written into
this file as the literal 0.08, which is only meaningful while the design
clearance is one of the 0.4mm-nozzle values (0.01 - 0.05). Measuring a fit
LADDER breaks that assumption by construction: a rung built at PEG_CLEAR=0.10
has a uniform 0.100mm gap down the whole engaged length, every sample lands
above 0.08, and the tool reports engagement 0.00mm - "the peg is never gripped"
- for geometry that is exactly as engaged as the tight rungs. That is the same
class of error the docstring above already warns about: a confident number for
the wrong question. So the threshold is now an argument, defaulting to 0.08 so
every existing invocation is unchanged, and a ladder rung is measured against
its OWN design clearance plus a little slack.

Usage:
    python beads/glow-set/measure_fit.py <bead-dir-name> [...]
    python beads/glow-set/measure_fit.py n06-c010-yaxing --gap-max 0.13
"""
import argparse
import pathlib

import numpy as np
import trimesh
from shapely.geometry import Point, Polygon

REPO = pathlib.Path(__file__).resolve().parents[2]
PRINT = REPO / "beads" / "glow-set" / "print"
STEP = 0.1
MAX_H = 2.6
GAP_MAX = 0.08


def polys(mesh, z):
    s = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if s is None:
        return []
    p, _ = s.to_planar(to_2D=np.eye(4))
    return list(p.polygons_full)


def mating_face(bottom):
    """z of the face the pegs stand on: the highest z where the body is still
    a single large cross-section rather than a few peg islands."""
    lo, hi = bottom.bounds[0][2], bottom.bounds[1][2]
    for z in np.arange(hi - 0.02, lo, -0.05):
        if sum(p.area for p in polys(bottom, z)) > 60:
            return float(z)
    return None


def find_pegs(bottom, mate_z):
    """Peg centres, taken just above the mating face where only pegs remain."""
    out = []
    for p in polys(bottom, mate_z + 0.25):
        if p.area < 40:                       # an island, not the body
            c = p.centroid
            out.append((c.x, c.y))
    return out


def peg_radius(bottom, xy, z):
    for p in polys(bottom, z):
        if p.area < 40 and p.distance(Point(*xy)) < 1e-9:
            return (p.area / np.pi) ** 0.5
    return None


def socket_radius(top, xy, z):
    pt = Point(*xy)
    for p in polys(top, z):
        for ring in p.interiors:
            r = Polygon(ring)
            if r.contains(pt) or r.distance(pt) < 1.5:
                return (r.area / np.pi) ** 0.5
    return None


def report(name):
    d = PRINT / name
    bottom = trimesh.load(d / "Bottom.stl", process=False)
    top = trimesh.load(d / "Top.stl", process=False)
    mate_b = mating_face(bottom)
    mate_t = float(top.bounds[0][2])
    if mate_b is None:
        print(f"{name}: could not locate the mating face"); return None

    pegs = find_pegs(bottom, mate_b)
    if not pegs:
        print(f"{name}: found NO pegs above the mating face"); return None

    per_peg = []
    for xy in pegs:
        eng = 0.0
        gaps = []
        for h in np.arange(0.0, MAX_H, STEP):
            pr = peg_radius(bottom, xy, mate_b + h)
            sr = socket_radius(top, xy, mate_t + h)
            if pr is None or sr is None:
                continue
            gap = sr - pr
            gaps.append(gap)
            if gap <= GAP_MAX + 1e-9:
                eng += STEP
        per_peg.append((xy, eng, min(gaps) if gaps else float("nan")))

    worst = min(e for _, e, _ in per_peg)
    print(f"{name:<28} pegs={len(pegs)}  "
          f"engagement min={worst:.2f}mm "
          f"[{', '.join('%.2f' % e for _, e, _ in per_peg)}]  "
          f"gap={min(g for _, _, g in per_peg):.3f}mm")
    return worst


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="+", help="bead dir names under print/")
    ap.add_argument("--gap-max", type=float, default=GAP_MAX,
                    help="radial gap (mm) still counted as engaged. Default "
                         "0.08 suits the 0.4mm-nozzle clearances; on a fit "
                         "ladder pass the rung's own PEG_CLEAR plus ~0.03.")
    ap.add_argument("--min", type=float, default=0.9,
                    help="engagement (mm) below which this exits non-zero")
    a = ap.parse_args()
    GAP_MAX = a.gap_max

    worst = [report(n) for n in a.names]
    # 1e-6 slack: engagement is a sum of 0.1 steps, so an exact 0.9 arrives as
    # 0.8999999999999999 and a bare `< 0.9` failed a bead that passed.
    bad = [n for n, w in zip(a.names, worst)
           if w is None or w < a.min - 1e-6]
    if bad:
        raise SystemExit(f"\nFAIL: engagement under {a.min}mm on "
                         f"{', '.join(bad)}")
    print(f"\nFIT OK - every peg engages >= {a.min}mm "
          f"(gap <= {a.gap_max}mm)")
