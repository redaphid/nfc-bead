"""Quick peg-perimeter check: at the new PEG_DIAMETER, do all pegs fit
fully inside the taco silhouette? Cast a ring of rays per peg position
and count misses."""
import bpy, math, sys
from mathutils import Vector

bpy.ops.wm.open_mainfile(filepath=r"D:\Projects\nfc-bead\beads\filibertos-taco\print\filibertos-taco_charm.blend")

PEG_DIAMETER = 2.6
PEG_RADIUS = PEG_DIAMETER/2.0
PEGS = [(7.5, -6.0), (-9.5, 0.0), (7.5, 2.5)]

top = bpy.data.objects['Top']

def inside(px, py):
    ev = top.evaluated_get(bpy.context.evaluated_depsgraph_get())
    r = ev.ray_cast(Vector((px, py, -10)), Vector((0,0,1)))
    return r[0]

print(f"Peg perimeter check at radius {PEG_RADIUS}mm (24 samples):")
for i, (cx, cy) in enumerate(PEGS):
    misses = []
    for k in range(24):
        a = k / 24 * 2 * math.pi
        px = cx + PEG_RADIUS * math.cos(a)
        py = cy + PEG_RADIUS * math.sin(a)
        if not inside(px, py):
            misses.append((math.degrees(a), px, py))
    if not misses:
        print(f"  Peg {i} ({cx:+.1f}, {cy:+.1f}): OK")
    else:
        print(f"  Peg {i} ({cx:+.1f}, {cy:+.1f}): {len(misses)} samples OUTSIDE")
        for a, px, py in misses[:6]:
            print(f"    angle={a:.0f}° at ({px:+.2f}, {py:+.2f})")
