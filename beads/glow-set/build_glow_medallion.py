"""Glow Medallion - single-filament NFC bead with a RECESSED glyph.

Design language differs from every other bead in this repo, and deliberately.
All prior charms raise a motif in a CONTRASTING FILAMENT. This one is printed in
ONE material (strontium-aluminate glow PLA), so colour contrast does not exist.
In the dark the bead emits from its bulk; a raised same-material motif is nearly
invisible, because there is neither colour contrast nor much shadow.

What does NOT work either, and this was the first wrong guess: "recessed = less
material = dimmer". Glow PLA scatters heavily, so surface brightness saturates
after roughly 1-2mm. A wide shallow pocket in a 3mm face is still saturated and
looks identical to the face beside it.

What DOES work is APERTURE. A groove that is narrow relative to its depth
self-shadows - less of the emitted light escapes - so it reads as a dark line.
Hence the motif is ENGRAVED LINE ART: narrow deep grooves, aspect >= 1, never
broad filled pockets. This also happens to read in daylight as shadow lines, so
the same bead works when traded at noon and when glowing at 2am.

Consequences, all good:
  * No Decoration objects at all -> 2 STLs (Bottom, Top). This sidesteps
    gotchas #9, #11, #25, #26, #27 and #28 outright (they are all about
    multi-colour decoration objects).
  * The recess prints as an open pocket, show-face UP: flat floor, vertical
    walls, no bridging, no supports. Strictly easier than raised relief.
  * TOP_THICK 2.0 -> 3.0 gives room for the recess AND more phosphor (brighter,
    longer glow) AND retires the "~0.4mm string-hole wall, marginal" risk noted
    in beads/eye-medallion/PRINT_LOG.md.

Geometry envelope (derived, do not exceed without re-checking):
  * Peg sockets are PEG_HEIGHT+0.3 = 1.5mm deep at r=7.8, leaving 1.5mm of Top
    above them. A 1.2mm groove there would leave 0.3mm, so GLYPH_R_MAX keeps the
    glyph entirely inboard of the sockets - and of the string hole at y=8.0.
  * Strokes 0.8-2.2mm. Under 0.8 will not print in 2 perimeters; over 2.2 stops
    self-shadowing and vanishes at night.

Run headless:
  blender.exe -b --python beads/glow-set/build_glow_medallion.py
Live via MCP: exec(open(path).read(), {"__name__": "__main__"})   # gotcha #18
"""
import bpy, bmesh, math, os
from mathutils import Vector

# CONFIG ====================================================================
HERE      = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() \
            else r"D:\Projects\nfc-bead\beads\glow-set"
PRINT_DIR = os.path.join(HERE, "print")

TARGET_WIDTH = 22.0      # mm - slightly larger than the 20mm medallion: buys
CIRCLE_VERTS = 160       # glyph room (r<=7) without crowding the pegs.

BOTTOM_THICK = 1.5       # NFC pocket + peg bases
TOP_THICK    = 3.0       # sockets + string hole + the carved glyph
BODY         = TOP_THICK + BOTTOM_THICK      # 4.5mm

HOLE_DIAMETER = 1.2      # Kandi elastic
HOLE_Y        = 8.0      # in the THICK Top half; walls ~0.9mm (was ~0.4mm)

NFC_DIAMETER = 10.5      # NTAG215 sticker pocket
NFC_DEPTH    = 0.8
NFC_POS      = (0.0, 0.0)

PEG_DIAMETER  = 2.6      # gotcha #29 - 2.0mm does NOT grip
PEG_HEIGHT    = 1.2
PEG_CLEARANCE = 0.05     # radial
PEG_CHAMFER   = 0.35     # gotcha #30 - tip taper, cone OVERLAPS shaft
PEGS = [(-7.8, 0.0), (7.8, 0.0), (0.0, -7.8)]

# the recessed glyph
# Grooves must SELF-SHADOW to read at night. Glow PLA scatters heavily, so
# surface brightness saturates after ~1-2mm of material: a WIDE SHALLOW recess
# looks the same as the face beside it and is invisible in the dark. What reads
# is aperture - a groove narrow relative to its depth lets less light escape.
# Hence engraved LINE ART, aspect ratio depth/width >= 1, not filled pockets.
# Bonus: line art also reads in daylight as shadow lines, so the bead works both
# when traded at noon and when glowing at 2am.
RECESS_DEPTH = 1.2       # mm - deep enough to self-shadow (leaves 1.8mm floor)
MIN_STROKE   = 0.8       # mm - 2 perimeters at a 0.4mm nozzle
MAX_STROKE   = 2.2       # mm - wider than this stops self-shadowing at night
MIN_ASPECT   = 1.0       # depth/width; below this the groove washes out

# Sockets are 1.5mm deep at r=7.8 (peg r 1.3 + clearance -> outer edge 6.45 on
# the inboard side). A 1.2mm recess would leave only 0.3mm over a socket, so the
# glyph must stay inboard of it entirely.
GLYPH_R_MAX  = 6.2       # mm - hard envelope; clears sockets AND the string hole

BODY_COLOR = (0.72, 0.95, 0.75, 1.0)   # unlit strontium-aluminate: pale mint


# HELPERS (lifted from the proven eye-medallion build) ======================
def clean_mesh(obj, threshold=0.005):        # gotcha #5 - 0.02+ ruins detail
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
    b = target.modifiers.new(name=name, type='BOOLEAN')
    b.operation = operation; b.object = cutter; b.solver = 'EXACT'   # gotcha #2
    bpy.ops.object.modifier_apply(modifier=name)
    bpy.ops.object.select_all(action='DESELECT')
    cutter.select_set(True); bpy.ops.object.delete()


def check_nonmanifold(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold()
    bm = bmesh.from_edit_mesh(obj.data)
    nm = sum(1 for e in bm.edges if e.select)
    bpy.ops.object.mode_set(mode='OBJECT')
    return nm


def add_cylinder(radius, depth, location, rotation=(0, 0, 0), verts=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth,
                                        location=location, rotation=rotation)
    return bpy.context.active_object


def verify_hole(obj, origin, direction, label=""):
    deps = bpy.context.evaluated_depsgraph_get()
    res = obj.evaluated_get(deps).ray_cast(origin, direction)
    status = "OPEN" if not res[0] else "BLOCKED at z=%.2f" % res[1].z
    print("  %s: %s" % (label, status))
    return not res[0]


def wipe():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
    for m in list(bpy.data.meshes): bpy.data.meshes.remove(m)


# GLYPH PRIMITIVES ==========================================================
# A glyph is a list of primitives in mm, centred on the bead axis. Every theme
# under consideration decomposes into these:
#     ("dot",  x, y, r)                          star chart, punctuation
#     ("line", x1, y1, x2, y2, w)                constellation links, strokes
#     ("ring", r_inner, r_outer)                 vinyl grooves, frame
#     ("arc",  r_inner, r_outer, a0deg, a1deg)   partial grooves
# Each becomes a cutter DIFFERENCEd out of the Top show face.

def glyph_extent(glyph):
    """Max radius the glyph touches - checked against GLYPH_R_MAX."""
    m = 0.0
    for p in glyph:
        k = p[0]
        if k == "dot":
            m = max(m, math.hypot(p[1], p[2]) + p[3])
        elif k == "line":
            w = p[5] / 2.0
            m = max(m, math.hypot(p[1], p[2]) + w, math.hypot(p[3], p[4]) + w)
        elif k in ("ring", "arc"):
            m = max(m, p[2])
    return m


def glyph_min_stroke(glyph):
    w = []
    for p in glyph:
        k = p[0]
        if k == "dot":              w.append(p[3] * 2)
        elif k == "line":           w.append(p[5])
        elif k in ("ring", "arc"):  w.append(p[2] - p[1])
    return min(w) if w else 0.0


def _wedge(radius, depth, a0, a1, z_c):
    """Pie wedge a0..a1 radians, used as an INTERSECT mask for arcs."""
    span = a1 - a0
    steps = max(4, int(abs(span) / math.radians(6)))
    verts = [(0.0, 0.0, -depth / 2), (0.0, 0.0, depth / 2)]
    for s in range(steps + 1):
        a = a0 + span * s / steps
        verts.append((radius * math.cos(a), radius * math.sin(a), -depth / 2))
        verts.append((radius * math.cos(a), radius * math.sin(a),  depth / 2))
    faces = []
    for s in range(steps):
        b = 2 + s * 2
        faces.append((0, b, b + 2))
        faces.append((1, b + 3, b + 1))
        faces.append((b, b + 1, b + 3, b + 2))
    faces.append((0, 1, 3, 2))
    last = 2 + steps * 2
    faces.append((0, last, last + 1, 1))
    me = bpy.data.meshes.new("Wedge")
    me.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new("Wedge", me)
    bpy.context.scene.collection.objects.link(obj)
    obj.location.z = z_c
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    clean_mesh(obj)
    return obj


def carve_glyph(top, glyph, show_z):
    """DIFFERENCE each primitive out of the Top show face."""
    depth = RECESS_DEPTH + 0.4                 # overshoot above the show face
    z_c = show_z - RECESS_DEPTH + depth / 2.0  # cutter spans the recess + air
    for i, p in enumerate(glyph):
        k = p[0]
        if k == "dot":
            _, x, y, r = p
            cut = add_cylinder(r, depth, (x, y, z_c), verts=48)
        elif k == "line":
            _, x1, y1, x2, y2, w = p
            dx, dy = x2 - x1, y2 - y1
            ln = math.hypot(dx, dy)
            ang = math.atan2(dy, dx)
            bpy.ops.mesh.primitive_cube_add(size=1,
                                            location=((x1 + x2) / 2, (y1 + y2) / 2, z_c))
            cut = bpy.context.active_object
            cut.scale = (ln, w, depth)
            cut.rotation_euler = (0, 0, ang)
            bpy.ops.object.transform_apply(scale=True, rotation=True)
            boolean_op(top, cut, 'DIFFERENCE', "G%da" % i)
            # round caps so strokes join cleanly instead of leaving notches
            for (cx, cy) in ((x1, y1), (x2, y2)):
                cap = add_cylinder(w / 2.0, depth, (cx, cy, z_c), verts=24)
                boolean_op(top, cap, 'DIFFERENCE', "G%dc" % i)
            continue
        elif k in ("ring", "arc"):
            ri, ro = p[1], p[2]
            cut = add_cylinder(ro, depth, (0, 0, z_c), verts=128)
            if ri > 1e-6:
                inner = add_cylinder(ri, depth * 3, (0, 0, z_c), verts=128)
                boolean_op(cut, inner, 'DIFFERENCE', "Hollow")
            if k == "arc":
                keep = _wedge(ro * 1.5, depth * 3,
                              math.radians(p[3]), math.radians(p[4]), z_c)
                boolean_op(cut, keep, 'INTERSECT', "Wedge")
        else:
            raise ValueError("unknown glyph primitive %r" % (k,))
        boolean_op(top, cut, 'DIFFERENCE', "G%d" % i)
    clean_mesh(top)
    return top


# BUILD =====================================================================
def build_bead(name, glyph, verbose=True):
    """Build one bead. Returns (bottom, top). Exports to print/<name>/."""
    wipe()
    R = TARGET_WIDTH / 2.0

    ext, ms = glyph_extent(glyph), glyph_min_stroke(glyph)
    if verbose:
        print("=" * 62)
        print("glow-medallion: %s" % name)
        print("  glyph: %d primitives, extent r=%.2f (max %.1f), min stroke %.2f (floor %.1f)"
              % (len(glyph), ext, GLYPH_R_MAX, ms, MIN_STROKE))
    if ext > GLYPH_R_MAX:
        raise ValueError("%s: glyph extent %.2f exceeds GLYPH_R_MAX %.2f - it would "
                         "collide with the pegs or the string hole" % (name, ext, GLYPH_R_MAX))
    if ms < MIN_STROKE:
        raise ValueError("%s: min stroke %.2fmm is under the %.1fmm printable "
                         "floor (2 perimeters at 0.4mm)" % (name, ms, MIN_STROKE))
    aspect = RECESS_DEPTH / ms if ms else 0.0
    if aspect < MIN_ASPECT:
        print("  WARNING: widest-groove aspect %.2f is under %.1f - those strokes "
              "will wash out in the dark." % (aspect, MIN_ASPECT))
    wide = [p for p in glyph if (p[0] == "line" and p[5] > MAX_STROKE)
            or (p[0] in ("ring", "arc") and p[2] - p[1] > MAX_STROKE)]
    if wide:
        print("  WARNING: %d stroke(s) wider than MAX_STROKE %.1fmm - they will "
              "read in daylight but not at night." % (len(wide), MAX_STROKE))

    # round base, centred on z=0
    full = add_cylinder(R, BODY, (0, 0, 0), verts=CIRCLE_VERTS)
    full.name = "FullBead"
    clean_mesh(full)
    z_min, z_max = -BODY / 2.0, BODY / 2.0
    z_split = z_min + BOTTOM_THICK          # asymmetric seam (gotcha #31)
    top_mid = (z_split + z_max) / 2.0

    # string hole (X axis) entirely inside the THICK Top half (gotcha #23)
    z_hole = top_mid
    cut = add_cylinder(HOLE_DIAMETER / 2.0, TARGET_WIDTH * 2,
                       (0, HOLE_Y, z_hole), rotation=(0, math.radians(90), 0), verts=48)
    boolean_op(full, cut, 'DIFFERENCE', "Hole")
    clean_mesh(full)
    if verbose:
        print("  string hole d=%.1f at y=%.1f, walls ~%.2fmm"
              % (HOLE_DIAMETER, HOLE_Y, (TOP_THICK - HOLE_DIAMETER) / 2))

    # peg / NFC clearance report (gotchas #21, #24)
    nfc_r, peg_r = NFC_DIAMETER / 2.0, PEG_DIAMETER / 2.0
    for (px, py) in PEGS:
        nfc_clear = math.hypot(px - NFC_POS[0], py - NFC_POS[1]) - nfc_r - peg_r
        rim_clear = R - math.hypot(px, py) - peg_r
        flag = "  <-- CHECK" if (nfc_clear < 0 or rim_clear < 0) else ""
        if verbose:
            print("  peg (%+.1f,%+.1f): NFCclr=%.2f rimclr=%.2f%s"
                  % (px, py, nfc_clear, rim_clear, flag))

    # split into halves
    def half(hname, zlo, zhi):
        bpy.ops.object.select_all(action='DESELECT')
        full.select_set(True); bpy.context.view_layer.objects.active = full
        bpy.ops.object.duplicate()
        h = bpy.context.active_object; h.name = hname
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, (zlo + zhi) / 2.0))
        b = bpy.context.active_object
        b.scale = (TARGET_WIDTH * 4, TARGET_WIDTH * 4, (zhi - zlo))
        bpy.ops.object.transform_apply(scale=True)
        boolean_op(h, b, 'INTERSECT', "Cut")
        clean_mesh(h, 0.01)
        return h

    bottom = half("Bottom", z_min, z_split)
    top    = half("Top",    z_split, z_max)

    # NFC pocket on Bottom inner face
    b_z_max = max(v.co.z for v in bottom.data.vertices)
    d = NFC_DEPTH * 2 + 0.1
    cut = add_cylinder(NFC_DIAMETER / 2.0, d,
                       (NFC_POS[0], NFC_POS[1], b_z_max - NFC_DEPTH + d / 2.0), verts=64)
    boolean_op(bottom, cut, 'DIFFERENCE', "NFC")
    clean_mesh(bottom)

    # peg sockets on Top inner face, AFTER the split (gotcha #1)
    t_z_min = min(v.co.z for v in top.data.vertices)
    hole_r = (PEG_DIAMETER + PEG_CLEARANCE * 2) / 2.0
    for i, (px, py) in enumerate(PEGS):
        cb, ct = t_z_min - 1.0, t_z_min + PEG_HEIGHT + 0.3
        cut = add_cylinder(hole_r, ct - cb, (px, py, (cb + ct) / 2.0), verts=32)
        boolean_op(top, cut, 'DIFFERENCE', "PH%d" % i)
    clean_mesh(top)

    # pegs on Bottom (gotcha #14), shaft + OVERLAPPING chamfer cone (gotcha #30)
    b_z_max = max(v.co.z for v in bottom.data.vertices)
    shaft_h = PEG_HEIGHT - PEG_CHAMFER
    for i, (px, py) in enumerate(PEGS):
        cyl = add_cylinder(peg_r, shaft_h, (px, py, b_z_max + shaft_h / 2.0), verts=32)
        boolean_op(bottom, cyl, 'UNION', "Peg%d" % i)
        ov = 0.15                                   # cone MUST overlap the shaft
        bpy.ops.mesh.primitive_cone_add(
            vertices=32, radius1=peg_r, radius2=max(peg_r - PEG_CHAMFER, 0.2),
            depth=PEG_CHAMFER + ov,
            location=(px, py, b_z_max + shaft_h - ov + (PEG_CHAMFER + ov) / 2.0))
        boolean_op(bottom, bpy.context.active_object, 'UNION', "PegTip%d" % i)
    clean_mesh(bottom)

    # THE GLYPH - carved into the Top show face
    carve_glyph(top, glyph, z_max)

    # verification (gotcha #8)
    nm_b, nm_t = check_nonmanifold(bottom), check_nonmanifold(top)
    if verbose:
        print("  non-manifold: Bottom=%d Top=%d" % (nm_b, nm_t))
    verify_hole(top, Vector((-R - 2, HOLE_Y, z_hole)), Vector((1, 0, 0)), "string hole")
    for i, (px, py) in enumerate(PEGS):
        verify_hole(top, Vector((px, py, t_z_min - 2)), Vector((0, 0, 1)), "peg socket %d" % i)
    if nm_b or nm_t:
        raise RuntimeError("%s: non-manifold geometry (B=%d T=%d) - do not print"
                           % (name, nm_b, nm_t))

    # print orientation: centred-cylinder pipeline needs NO flips (gotcha #16)
    bottom.location.z -= min(v.co.z for v in bottom.data.vertices)
    top.location.z    -= min(v.co.z for v in top.data.vertices)
    bpy.context.view_layer.update()

    out = os.path.join(PRINT_DIR, name)
    os.makedirs(out, exist_ok=True)
    for obj, fn in ((bottom, "Bottom.stl"), (top, "Top.stl")):
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True); bpy.context.view_layer.objects.active = obj
        bpy.ops.wm.stl_export(filepath=os.path.join(out, fn),
                              export_selected_objects=True, ascii_format=False)
    if verbose:
        print("  exported -> %s" % out)
    return bottom, top
