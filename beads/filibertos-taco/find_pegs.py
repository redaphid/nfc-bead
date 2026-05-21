"""Scan candidate peg positions against the CLEAN silhouette polygon
(silhouette.svg → shapely), independent of the broken Top mesh."""
import os, math, sys, re

BEAD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BEAD, '..', '..'))

from shapely.geometry import Point, Polygon
import xml.etree.ElementTree as ET

PEG_DIAMETER = 2.6
PEG_RADIUS   = PEG_DIAMETER/2.0
PEG_CLEARANCE = 0.05
peg_r = PEG_RADIUS + PEG_CLEARANCE  # outer footprint radius

NFC_DIAMETER = 10.5
NFC_POS = (0.0, 1.5)
NFC_BUFFER = 0.5

HOLE_DIA = 2.0
HOLE_Y = 5.0
HOLE_BUFFER = 0.5
TARGET_WIDTH = 25.0

# Read silhouette.svg → polygon in mm coords, centered to bbox
ns = {"svg": "http://www.w3.org/2000/svg"}
tree = ET.parse(os.path.join(BEAD, 'silhouette.svg'))
root = tree.getroot()

# parse first <path d="...">
path_el = root.find('.//svg:path', ns)
d = path_el.attrib['d']
# Parse simple M/L/Z paths (silhouette is a single closed path)
nums = re.findall(r'-?\d+\.?\d*', d)
pts = [(float(nums[i]), float(nums[i+1])) for i in range(0, len(nums)-1, 2)]

# bbox & scale to TARGET_WIDTH centered
xs, ys = zip(*pts)
xmin, xmax = min(xs), max(xs); ymin, ymax = min(ys), max(ys)
w = xmax - xmin
scale = TARGET_WIDTH / w
cx = (xmin + xmax)/2; cy = (ymin + ymax)/2
# SVG y is down; Blender y is up — flip y
mm_pts = [((p[0] - cx)*scale, -(p[1] - cy)*scale) for p in pts]
silh = Polygon(mm_pts)
if not silh.is_valid:
    silh = silh.buffer(0)
print(f"Silhouette bbox: x [{min(p[0] for p in mm_pts):.2f}, {max(p[0] for p in mm_pts):.2f}]  y [{min(p[1] for p in mm_pts):.2f}, {max(p[1] for p in mm_pts):.2f}]")

# A peg fits if a disk at (cx, cy) radius=peg_r is fully inside silh
# == silh.contains(disk) == silh.contains(Point(cx,cy).buffer(peg_r))
def perimeter_inside(cx, cy, r):
    disk = Point(cx, cy).buffer(r, quad_segs=24)
    return silh.contains(disk)

def nfc_clear(cx, cy, r):
    d = math.hypot(cx - NFC_POS[0], cy - NFC_POS[1])
    return d >= NFC_DIAMETER/2 + r + NFC_BUFFER

def hole_clear(cx, cy, r):
    return abs(cy - HOLE_Y) >= HOLE_DIA/2 + r + HOLE_BUFFER

candidates = []
for cy_h in range(-18, 19):
    for cx_h in range(-26, 27):
        cx_f, cy_f = cx_h/2.0, cy_h/2.0
        if (perimeter_inside(cx_f, cy_f, peg_r) and
            nfc_clear(cx_f, cy_f, peg_r) and
            hole_clear(cx_f, cy_f, peg_r)):
            candidates.append((cx_f, cy_f))

print(f"\n{len(candidates)} valid positions:")
for cx, cy in sorted(candidates, key=lambda p: (-p[1], p[0])):
    print(f"  ({cx:+5.1f}, {cy:+5.1f})")
