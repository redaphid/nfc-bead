"""Measure the wall above the string hole DIRECTLY from Top.stl.

WHY. printability_check.check_wall_above_hole hunts for a half-pipe notch on the
BOTTOM half's inner face. build_talisman puts the string hole entirely inside
the TOP half (recipe gotcha #23), so Bottom has no notch, the check latches onto
the NFC pocket instead - its 86.5mm^2 diff is exactly pi*5.25^2 - and skips with
a WARN. So the cord wall, the thing that snapped a bead off a bracelet before
and the entire reason HOLE_CROWN is 2.5mm, is NOT covered by the printability
run on this bead family. This covers it, on the real exported mesh.

METHOD. Do NOT use trimesh.contains here: without an embree backend it returned
"solid" for points that are demonstrably inside the cord tube, which reads as a
missing string hole on beads that have one. Cross-sections are exact. The hole
is a tube along X at x=0, so slicing the mesh with the x=0 plane cuts it
squarely and it shows up as an interior ring of the section, 1.2mm across.

In that YZ section, the crown is just how much further the silhouette reaches in
+Y beyond the top of the hole ring.

  .venv/Scripts/python.exe beads/glow-set/check_cord_wall.py <Top.stl>... [--min 2.5]
"""
import argparse
import sys

import numpy as np
import trimesh
from shapely.geometry import Polygon

ap = argparse.ArgumentParser()
ap.add_argument("tops", nargs="+")
ap.add_argument("--min", type=float, default=2.5, help="HOLE_CROWN")
ap.add_argument("--dia", type=float, default=1.2, help="HOLE_D")
a = ap.parse_args()

bad = 0
for path in a.tops:
    label = path.replace("\\", "/").split("/")
    label = label[-2] if len(label) > 1 else path
    m = trimesh.load(path)
    sec = m.section(plane_origin=[0, 0, 0], plane_normal=[1, 0, 0])
    if sec is None:
        print("FAIL %-14s no cross-section at x=0" % label)
        bad += 1
        continue

    # discrete closed polylines, projected to (y, z) - the section plane's own
    # axes, so no to_2D() frame ambiguity to reason about
    rings = [np.asarray(d)[:, [1, 2]] for d in sec.discrete]
    rings = [r for r in rings if len(r) >= 4]
    polys = [Polygon(r) for r in rings]
    polys = [p if p.is_valid else p.buffer(0) for p in polys]
    if not polys:
        print("FAIL %-14s empty section" % label)
        bad += 1
        continue
    outer = max(polys, key=lambda p: p.area)

    # the cord tube: an interior ring about HOLE_D across, and round-ish
    holes = []
    for p, r in zip(polys, rings):
        if p is outer:
            continue
        w = r[:, 0].max() - r[:, 0].min()
        h = r[:, 1].max() - r[:, 1].min()
        if abs(w - a.dia) < 0.3 and abs(h - a.dia) < 0.3:
            holes.append((r[:, 0].max(), w, h))
    if not holes:
        print("FAIL %-14s no %.1fmm hole ring in the x=0 section - "
              "NO STRING HOLE" % (label, a.dia))
        bad += 1
        continue

    y_hole_top, w, h = max(holes)                 # highest such ring
    y_outer_top = max(r[:, 0].max() for r in rings)
    crown = y_outer_top - y_hole_top
    okk = crown >= a.min
    bad += 0 if okk else 1
    print("%s %-14s hole %.2fx%.2fmm, top y=%.2f, silhouette y=%.2f  "
          "crown=%.2f mm (min %.2f)"
          % ("OK  " if okk else "FAIL", label, w, h, y_hole_top, y_outer_top,
             crown, a.min))

print("CORD WALL %s" % ("FAILED: %d" % bad if bad else "PASSED"))
sys.exit(1 if bad else 0)
