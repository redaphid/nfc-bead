"""Build ONE talisman bead to printable STLs. Test-print pathfinder.

Takes a polygon from talismans.py, extrudes it, and runs the standard bead
pipeline - but with the pocket, pegs and string hole placed by shapes.py's
solver rather than hardcoded, because every talisman has a different outline.

Single filament by default (strontium-aluminate glow PLA): output is exactly
Bottom.stl + Top.stl, which sidesteps recipe gotchas #9, #11, #25, #26, #27
and #28 - all multi-colour decoration bugs.

Set BEAD_GLYPH="<theme>:<name>" to build the TWO-COLOUR variant instead: a
glowing green body with a black figure raised on the show face. That adds
Decoration.stl and re-enters those gotchas deliberately - see deco.py, which
documents how each one is handled. Themes come from glyphs.py: star, groove,
sigil. The figure is raised rather than inlaid so the whole bead needs exactly
ONE filament change (all glow, then all black); deco.py has the reasoning.

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
import glyphs as GL         # noqa: E402
import deco as D            # noqa: E402


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
    """BEAD_SHAPE selects the source: "foil:quatrefoil", "shape:skull" or
    "talisman:<seed>".

    shapes.SHAPES are drawn at their final size in absolute mm, so BEAD_R does
    NOT apply to them - a skull is the size its author drew it.
    """
    spec = os.environ.get("BEAD_SHAPE", "talisman:" + SEED)
    kind, _, which = spec.partition(":")
    if kind == "foil":
        return _resample(FO.build(which, r=R_OUT))
    if kind == "shape":
        if which not in S.SHAPES:
            raise SystemExit("unknown shape %r - pick one of %s"
                             % (which, sorted(S.SHAPES)))
        return S.SHAPES[which]()
    return T.talisman(which or SEED, r_out=R_OUT)

# CONFIG ====================================================================
NAME   = os.environ.get("BEAD_NAME", "shield")   # which talisman to build
SEED   = os.environ.get("BEAD_SEED", "virginia")  # seeds the proportions
R_OUT  = float(os.environ.get("BEAD_R", "12.0"))   # circumscribed radius; 12 -> 24mm

BOTTOM_THICK = 1.5       # NFC pocket + peg bases
TOP_THICK    = 3.0       # sockets + string hole; thicker = brighter glow
BODY         = BOTTOM_THICK + TOP_THICK          # 4.5mm

NFC_DIAMETER = 10.5
NFC_DEPTH    = 0.8
PEG_DIAMETER = 2.6       # gotcha #29 - 2.0mm does NOT grip
PEG_HEIGHT   = 1.8       # gotcha #40 - funnel + tip chamfer eat 0.9mm of it
PEG_CLEAR    = 0.05      # radial
PEG_CHAMFER  = 0.35      # gotcha #30 - cone tip must OVERLAP the shaft
SOCKET_LEADIN = 0.4      # 45-deg funnel at the socket MOUTH - see below
HOLE_D       = 1.2       # medallion gauge

# TWO-COLOUR: "<theme>:<name>" from glyphs.py (star / groove / sigil).
# Empty -> single-filament bead with no Decoration.stl, the default.
GLYPH_SPEC  = os.environ.get("BEAD_GLYPH", "")
RELIEF      = float(os.environ.get("BEAD_RELIEF", "0.5"))

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
        c = cyl(hr, hi - lo, (gx, gy, (lo + hi) / 2.0), verts=64)
        boolean_op(top, c, 'DIFFERENCE', "PH%d" % i)
        # FUNNEL THE MOUTH. tz is the mating face, which is the face that goes
        # against the PLATE, so the socket opening is drawn in the very first
        # layers - the ones that get squished. A 2.7mm bore is already the
        # hardest thing on the layer to trace cleanly, and first-layer squish
        # then pushes material into it: the printed bores came out ovalised
        # with a curled rim of extrudate standing proud around them.
        # A 45-degree lead-in means the first layers trace a LARGER circle and
        # the squeeze-out has somewhere to go, and it doubles as the entry
        # taper for the peg - the counterpart to the chamfered peg tip in
        # gotcha #30. The cutter starts BELOW tz so its wide end is fully
        # outside the solid rather than coplanar with the mating face.
        d = SOCKET_LEADIN + 0.2
        bpy.ops.mesh.primitive_cone_add(
            vertices=64,
            radius1=hr + SOCKET_LEADIN + 0.2,     # wide end, below the face
            radius2=hr,                            # meets the bore
            depth=d,
            location=(gx, gy, tz - 0.2 + d / 2.0))
        boolean_op(top, bpy.context.active_object, 'DIFFERENCE', "PF%d" % i)
    clean_mesh(top)

    # pegs on Bottom (gotcha #14): shaft + OVERLAPPING chamfer cone (gotcha #30)
    bz = max(v.co.z for v in bottom.data.vertices)
    pr = PEG_DIAMETER / 2.0
    shaft = PEG_HEIGHT - PEG_CHAMFER
    for i, (gx, gy) in enumerate(pegs):
        c = cyl(pr, shaft, (gx, gy, bz + shaft / 2.0), verts=64)
        boolean_op(bottom, c, 'UNION', "Peg%d" % i)
        ov = 0.15
        bpy.ops.mesh.primitive_cone_add(
            vertices=64, radius1=pr, radius2=max(pr - PEG_CHAMFER, 0.2),
            depth=PEG_CHAMFER + ov,
            location=(gx, gy, bz + shaft - ov + (PEG_CHAMFER + ov) / 2.0))
        boolean_op(bottom, bpy.context.active_object, 'UNION', "Tip%d" % i)
    clean_mesh(bottom)

    # TWO-COLOUR: black figure raised on the glow show face (z_max).
    decoration = None
    if GLYPH_SPEC:
        theme, _, who = GLYPH_SPEC.partition(":")
        who = who or SEED
        glyph = GL.build(theme, who)
        raw = D.glyph_extent(glyph)
        # The envelope is the SMALLER of the hardware limit (clears the peg
        # sockets and the string hole) and how much room the silhouette
        # actually has at its centre. A fixed 6.2 overhangs any narrow or
        # concave shape and the crop then slices the figure into fragments.
        # WHERE the figure sits. Centring on the origin is wrong for a concave
        # shape: on `moon` the crescent bite reaches the origin, leaving 0.75mm
        # of room there, so an origin-centred glyph is sliced into fragments by
        # the crop. Keep the origin when it has room to spare - most shapes
        # look best centred - and otherwise fall back to the silhouette's
        # best interior point, which place_pocket already solves for.
        gx, gy = 0.0, 0.0
        if S.clearance(pts, 0.0, 0.0) < 5.0:
            gx, gy = px, py
        room = S.clearance(pts, gx, gy) - D.EDGE_INSET - 0.4

        # No GLYPH_R_MAX here. That 6.2mm cap exists for CARVED glyphs, which
        # cut 1.2mm into the show face and so had to clear the peg sockets and
        # the string hole underneath. A raised figure removes no material and
        # sits entirely above the show face, so the only real limit is the
        # silhouette itself.
        r_env = max(room, 2.0)
        glyph = D.fit_glyph(glyph, r_env * 0.92)
        ext = D.glyph_extent(glyph)
        print("  glyph     : %s/%s, %d primitives, extent r=%.2f -> %.2f "
              "(envelope %.2f at %+.1f,%+.1f)"
              % (theme, who, len(glyph), raw, ext, r_env, gx, gy))
        decoration = D.build_decoration(glyph, pts, z_max, relief=RELIEF,
                                        centre=(gx, gy))

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
    top_dz = min(v.co.z for v in top.data.vertices)
    top.location.z -= top_dz
    if decoration is not None:
        # The SAME shift as Top, never its own. Zeroing the decoration
        # independently would drop it onto the plate as a loose scab of black
        # instead of leaving it welded to the show face.
        decoration.location.z -= top_dz
    bpy.context.view_layer.update()

    exports = [(bottom, "Bottom.stl"), (top, "Top.stl")]
    if decoration is not None:
        exports.append((decoration, "Decoration.stl"))

    os.makedirs(PRINT_DIR, exist_ok=True)
    for obj, fn in exports:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True); bpy.context.view_layer.objects.active = obj
        bpy.ops.wm.stl_export(filepath=os.path.join(PRINT_DIR, fn),
                              export_selected_objects=True, ascii_format=False)
        print("  exported  : %s" % fn)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(PRINT_DIR, "%s.blend" % NAME))
    print("DONE -> %s" % PRINT_DIR)


if __name__ == "__main__":
    main()
