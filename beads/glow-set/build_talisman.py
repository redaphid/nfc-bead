"""Build ONE talisman bead to printable STLs. Test-print pathfinder.

Takes a polygon from talismans.py, extrudes it, and runs the standard bead
pipeline - but with the pocket, pegs and string hole placed by shapes.py's
solver rather than hardcoded, because every talisman has a different outline.

Single filament (strontium-aluminate glow PLA), so there is no Decoration
object: output is exactly Bottom.stl + Top.stl. That sidesteps recipe gotchas
#9, #11, #25, #26, #27 and #28, which are all multi-colour decoration bugs.

Pipeline order matters (gotcha #1: peg holes AFTER the split):
    polygon -> extrude -> string hole -> split -> NFC pocket -> peg sockets
    -> pegs -> verify -> export

Run headless:
  "D:\\tools\\blender\\blender.exe" -b --python beads/glow-set/build_talisman.py
Live via MCP:
  exec(open(path).read(), {"__name__": "__main__"})      # gotcha #18
"""
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() \
       else r"D:\Projects\nfc-bead\beads\glow-set"
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import shapes as S          # noqa: E402
import talismans as T       # noqa: E402
import foils as FO          # noqa: E402


def _resample(pts, step_mm=0.35):
    """Foils are sampled at 600 points; at 32mm that is 0.17mm per segment,
    finer than the nozzle can resolve and just bloat in the STL. Drop points
    that are closer together than step_mm."""
    out = [pts[0]]
    for q in pts[1:]:
        if math.hypot(q[0] - out[-1][0], q[1] - out[-1][1]) >= step_mm:
            out.append(q)
    if math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < step_mm:
        out.pop()
    return out


def get_outline():
    """BEAD_SHAPE selects the source: "foil:quatrefoil" or "talisman:<seed>"."""
    spec = os.environ.get("BEAD_SHAPE", "talisman:" + SEED)
    kind, _, which = spec.partition(":")
    if kind == "foil":
        return _resample(FO.build(which, r=R_OUT))
    return T.talisman(which or SEED, r_out=R_OUT)

# CONFIG ====================================================================
NAME   = os.environ.get("BEAD_NAME", "shield")   # which talisman to build
SEED   = os.environ.get("BEAD_SEED", "virginia")  # seeds the proportions
R_OUT  = 16.0            # circumscribed radius -> ~32mm pendant

BOTTOM_THICK = 1.5       # NFC pocket + peg bases
TOP_THICK    = 3.0       # sockets + string hole; thicker = brighter glow
BODY         = BOTTOM_THICK + TOP_THICK          # 4.5mm

NFC_DIAMETER = 10.5
NFC_DEPTH    = 0.8
PEG_DIAMETER = 2.6       # gotcha #29 - 2.0mm does NOT grip
PEG_HEIGHT   = 1.2
PEG_CLEAR    = 0.05      # radial
PEG_CHAMFER  = 0.35      # gotcha #30 - cone tip must OVERLAP the shaft
HOLE_D       = 1.2       # medallion gauge

PRINT_DIR = os.path.join(HERE, "print", NAME)


# HELPERS ===================================================================
def clean_mesh(obj, threshold=0.005):        # gotcha #5
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=threshold)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def boolean_op(target, cutter, operation='DIFFERENCE', name="Bool"):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = target
    target.select_set(True)
    m = target.modifiers.new(name=name, type='BOOLEAN')
    m.operation = operation; m.object = cutter; m.solver = 'EXACT'   # gotcha #2
    bpy.ops.object.modifier_apply(modifier=name)
    bpy.ops.object.select_all(action='DESELECT')
    cutter.select_set(True); bpy.ops.object.delete()


def nonmanifold(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold()
    bm = bmesh.from_edit_mesh(obj.data)
    n = sum(1 for e in bm.edges if e.select)
    bpy.ops.object.mode_set(mode='OBJECT')
    return n


def cyl(r, d, loc, rot=(0, 0, 0), verts=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d,
                                        location=loc, rotation=rot)
    return bpy.context.active_object


def extrude_polygon(pts, height, name="FullBead"):
    """Polygon -> solid. Extrude, not Solidify (gotcha #4)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, y, -height / 2.0) for x, y in pts], [],
                   [list(range(len(pts)))])
    me.update()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active = obj

    bm = bmesh.new(); bm.from_mesh(me)
    face = bm.faces[:][0]
    r = bmesh.ops.extrude_face_region(bm, geom=[face])
    verts = [v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=Vector((0, 0, height)), verts=verts)
    bm.to_mesh(me); bm.free()
    clean_mesh(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    return obj


def wipe():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)


# BUILD =====================================================================
def main():
    print("=" * 64)
    print("glow-set talisman: %s (seed %r)" % (NAME, SEED))
    print("=" * 64)
    wipe()

    pts = get_outline()
    fit = S.fit_report(pts)
    if not fit["ok"]:
        raise RuntimeError("%s: silhouette does not fit the hardware" % NAME)
    px, py, pclear = fit["pocket"]
    pegs = fit["pegs"]
    hole_y, crown = fit["hole"]
    w, h = fit["w"], fit["h"]
    print("  outline   : %d verts, %.1f x %.1f mm" % (len(pts), w, h))
    print("  pocket    : (%.2f, %.2f) clearance %.2f mm" % (px, py, pclear))
    print("  string    : y=%.2f crown %.2f mm" % (hole_y, crown))
    for i, (gx, gy) in enumerate(pegs):
        print("  peg %d     : (%+.2f, %+.2f) clearance %.2f"
              % (i, gx, gy, S.clearance(pts, gx, gy)))

    full = extrude_polygon(pts, BODY)
    print("  extruded  : non-manifold=%d" % nonmanifold(full))

    z_min, z_max = -BODY / 2.0, BODY / 2.0
    z_split = z_min + BOTTOM_THICK                  # asymmetric seam, gotcha #31
    z_hole = (z_split + z_max) / 2.0                # hole INSIDE the thick Top

    # string hole, X axis, entirely within the Top half (gotcha #23)
    c = cyl(HOLE_D / 2.0, max(w, h) * 3, (0, hole_y, z_hole),
            rot=(0, math.radians(90), 0), verts=48)
    boolean_op(full, c, 'DIFFERENCE', "Hole")
    clean_mesh(full)

    # split
    def half(nm, zlo, zhi):
        bpy.ops.object.select_all(action='DESELECT')
        full.select_set(True); bpy.context.view_layer.objects.active = full
        bpy.ops.object.duplicate()
        o = bpy.context.active_object; o.name = nm
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, (zlo + zhi) / 2.0))
        b = bpy.context.active_object
        b.scale = (max(w, h) * 4, max(w, h) * 4, zhi - zlo)
        bpy.ops.object.transform_apply(scale=True)
        boolean_op(o, b, 'INTERSECT', "Cut")
        clean_mesh(o, 0.01)
        return o

    bottom = half("Bottom", z_min, z_split)
    top    = half("Top",    z_split, z_max)

    # NFC pocket on Bottom inner face
    bz = max(v.co.z for v in bottom.data.vertices)
    d = NFC_DEPTH * 2 + 0.1
    c = cyl(NFC_DIAMETER / 2.0, d, (px, py, bz - NFC_DEPTH + d / 2.0), verts=64)
    boolean_op(bottom, c, 'DIFFERENCE', "NFC")
    clean_mesh(bottom)

    # peg sockets on Top, AFTER the split (gotcha #1)
    tz = min(v.co.z for v in top.data.vertices)
    hr = (PEG_DIAMETER + PEG_CLEAR * 2) / 2.0
    for i, (gx, gy) in enumerate(pegs):
        lo, hi = tz - 1.0, tz + PEG_HEIGHT + 0.3
        c = cyl(hr, hi - lo, (gx, gy, (lo + hi) / 2.0), verts=32)
        boolean_op(top, c, 'DIFFERENCE', "PH%d" % i)
    clean_mesh(top)

    # pegs on Bottom (gotcha #14): shaft + OVERLAPPING chamfer cone (gotcha #30)
    bz = max(v.co.z for v in bottom.data.vertices)
    pr = PEG_DIAMETER / 2.0
    shaft = PEG_HEIGHT - PEG_CHAMFER
    for i, (gx, gy) in enumerate(pegs):
        c = cyl(pr, shaft, (gx, gy, bz + shaft / 2.0), verts=32)
        boolean_op(bottom, c, 'UNION', "Peg%d" % i)
        ov = 0.15
        bpy.ops.mesh.primitive_cone_add(
            vertices=32, radius1=pr, radius2=max(pr - PEG_CHAMFER, 0.2),
            depth=PEG_CHAMFER + ov,
            location=(gx, gy, bz + shaft - ov + (PEG_CHAMFER + ov) / 2.0))
        boolean_op(bottom, bpy.context.active_object, 'UNION', "Tip%d" % i)
    clean_mesh(bottom)

    # verify (gotcha #8)
    nb, nt = nonmanifold(bottom), nonmanifold(top)
    print("  non-manifold: Bottom=%d Top=%d" % (nb, nt))
    deps = bpy.context.evaluated_depsgraph_get()
    hit = top.evaluated_get(deps).ray_cast(
        Vector((-w, hole_y, z_hole)), Vector((1, 0, 0)))
    print("  string hole : %s" % ("OPEN" if not hit[0] else "BLOCKED"))
    for i, (gx, gy) in enumerate(pegs):
        r2 = top.evaluated_get(deps).ray_cast(
            Vector((gx, gy, tz - 2)), Vector((0, 0, 1)))
        # sockets are BLIND recesses - a hit at the socket floor is CORRECT
        print("  socket %d    : %s" % (i, "floor z=%.2f" % r2[1].z if r2[0] else "THROUGH (bad)"))
    if nb or nt:
        raise RuntimeError("non-manifold geometry - do not print")

    # print orientation: this pipeline is already print-ready (gotcha #16)
    bottom.location.z -= min(v.co.z for v in bottom.data.vertices)
    top.location.z    -= min(v.co.z for v in top.data.vertices)
    bpy.context.view_layer.update()

    os.makedirs(PRINT_DIR, exist_ok=True)
    for obj, fn in ((bottom, "Bottom.stl"), (top, "Top.stl")):
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True); bpy.context.view_layer.objects.active = obj
        bpy.ops.wm.stl_export(filepath=os.path.join(PRINT_DIR, fn),
                              export_selected_objects=True, ascii_format=False)
        print("  exported  : %s" % fn)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(PRINT_DIR, "%s.blend" % NAME))
    print("DONE -> %s" % PRINT_DIR)


if __name__ == "__main__":
    main()
