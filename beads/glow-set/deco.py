"""Raised glyph decoration for two-colour glow beads: glow body + black figure.

WHY RAISED, NOT INLAID. The single-colour glow medallion carves each glyph as a
recessed groove (`build_glow_medallion.carve_glyph`) so it self-shadows at
night. The two-colour bead wants the same figure in black filament, and there
are two ways to get it:

  inlay  - carve the groove, then fill it with a black solid. Every layer from
           the recess floor up to the show face contains BOTH colours, so the
           printer swaps filament twice per layer for ~6 layers. On a tool
           changer that is a huge wipe tower and minutes of purge per bead.
  raised - leave Top solid and stand the black figure ON the show face. Every
           layer up to the show face is pure glow; every layer above it is pure
           black. That is exactly ONE filament change for the whole bead.

Raised wins on print economics by a wide margin, and it reads the same: an
opaque black figure against a glowing green field. So this module builds the
glyph as a solid prism sitting on the show face.

The primitives are the same ones `glyphs.py` emits (dot / line / ring / arc),
built here as solids and UNIONed instead of DIFFERENCEd out of Top.

Gotchas honoured:
  #9  - solids built from primitives and from_pydata, never curve-bevel-clip
        (which silently collapses to an empty mesh against a thin slab).
  #11 - the decoration is lifted off the show face by EPS so the viewport does
        not Z-fight along the shared plane.
  #26 - the crop mask is a FRESH extrusion of the silhouette, never a duplicate
        of Top, so peg sockets cannot be punched through the decoration.
"""
import math

import bmesh
import bpy

EPS = 0.01          # gotcha #11 - lift off the host face
RELIEF = 0.5        # mm of black standing proud of the show face
EDGE_INSET = 0.6    # mm the decoration is held back from the silhouette rim


# ── local bpy helpers (self-contained: this module is imported by builders) ──
def _cyl(r, d, loc, verts=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d,
                                        location=loc)
    return bpy.context.active_object


def _boolean(target, cutter, operation, name):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = target
    target.select_set(True)
    m = target.modifiers.new(name=name, type='BOOLEAN')
    m.operation = operation
    m.object = cutter
    m.solver = 'EXACT'                      # gotcha #2
    bpy.ops.object.modifier_apply(modifier=name)
    bpy.ops.object.select_all(action='DESELECT')
    cutter.select_set(True)
    bpy.ops.object.delete()


def _clean(obj, threshold=0.005):           # gotcha #5
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=threshold)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def _nonmanifold(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold()
    bm = bmesh.from_edit_mesh(obj.data)
    n = sum(1 for e in bm.edges if e.select)
    bpy.ops.object.mode_set(mode='OBJECT')
    return n


def _prism(pts, z_lo, z_hi, name):
    """Closed polygon -> solid prism spanning z_lo..z_hi."""
    h = z_hi - z_lo
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, y, z_lo) for x, y in pts], [], [list(range(len(pts)))])
    me.update()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bm = bmesh.new()
    bm.from_mesh(me)
    r = bmesh.ops.extrude_face_region(bm, geom=[bm.faces[:][0]])
    vs = [v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0.0, 0.0, h), verts=vs)
    bm.to_mesh(me)
    bm.free()
    _clean(obj)
    return obj


def _wedge(radius, z_lo, z_hi, a0, a1, name="Wedge"):
    """Pie wedge a0..a1 radians, used as an INTERSECT mask for arcs."""
    span = a1 - a0
    steps = max(4, int(abs(span) / math.radians(6)))
    pts = [(0.0, 0.0)]
    for s in range(steps + 1):
        a = a0 + span * s / steps
        pts.append((radius * math.cos(a), radius * math.sin(a)))
    return _prism(pts, z_lo, z_hi, name)


# ── polygon inset ───────────────────────────────────────────────────────────
def inset_polygon(pts, d):
    """Shrink a CCW polygon inward by d mm (edge-offset + line intersection).

    Returns the ORIGINAL polygon if the result self-intersects or inverts -
    the caller only uses this to hold the decoration off the rim, so a failed
    inset must degrade to "no inset", never to a broken mask.
    """
    n = len(pts)
    lines = []
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        ln = math.hypot(dx, dy)
        if ln < 1e-9:
            return list(pts)
        # CCW winding: interior lies to the LEFT of each directed edge
        nx, ny = -dy / ln, dx / ln
        lines.append((x1 + nx * d, y1 + ny * d, dx / ln, dy / ln))

    out = []
    for i in range(n):
        px, py, ux, uy = lines[i - 1]
        qx, qy, vx, vy = lines[i]
        den = ux * vy - uy * vx
        if abs(den) < 1e-9:                 # parallel edges - keep the corner
            out.append((qx, qy))
            continue
        t = ((qx - px) * vy - (qy - py) * vx) / den
        out.append((px + ux * t, py + uy * t))

    def area(p):
        return 0.5 * sum(a[0] * b[1] - b[0] * a[1]
                         for a, b in zip(p, p[1:] + p[:1]))

    a0, a1 = area(pts), area(out)
    if a1 <= 0 or a1 > a0:                  # inverted or grew - reject
        return list(pts)
    return out


# ── the builder ─────────────────────────────────────────────────────────────
def glyph_extent(glyph):
    """Max radius the glyph touches, so the caller can gate on an envelope."""
    r = 0.0
    for p in glyph:
        k = p[0]
        if k == "dot":
            r = max(r, math.hypot(p[1], p[2]) + p[3])
        elif k == "line":
            _, x1, y1, x2, y2, w = p
            r = max(r, math.hypot(x1, y1) + w / 2, math.hypot(x2, y2) + w / 2)
        elif k in ("ring", "arc"):
            r = max(r, p[2])
    return r


def fit_glyph(glyph, r_target, max_stroke=2.2):
    """Centre a glyph on the face and grow it to use the available room.

    glyphs.py was written for a 22mm ROUND medallion with its figure carved as
    a grooved recess, where a small off-centre mark still reads because it
    self-shadows. Raised on a 24mm talisman face it does not: `sigil` in
    particular starts off-centre and wanders, landing as a small mark parked in
    one corner of the bead.

    Widths and dot radii scale with the coordinates, which is the right
    direction for a raised feature - a wider black stroke is bolder and prints
    more robustly than a narrow one. Growth stops when either the extent target
    is met OR the widest stroke reaches `max_stroke`, so the limit is the one
    that actually matters (glyphs.py caps line art at 2.2mm) rather than an
    arbitrary scale factor. The glyph is only ever enlarged, never shrunk.

    Ring/arc glyphs are returned untouched: they are concentric about the
    origin by construction, so they are already centred and already sized to
    the envelope.
    """
    if any(p[0] in ("ring", "arc") for p in glyph):
        return glyph

    xs, ys = [], []
    for p in glyph:
        if p[0] == "dot":
            _, x, y, r = p
            xs += [x - r, x + r]
            ys += [y - r, y + r]
        elif p[0] == "line":
            _, x1, y1, x2, y2, w = p
            xs += [x1 - w / 2, x1 + w / 2, x2 - w / 2, x2 + w / 2]
            ys += [y1 - w / 2, y1 + w / 2, y2 - w / 2, y2 + w / 2]
    if not xs:
        return glyph
    cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0

    def radius(g):
        return glyph_extent(g)

    centred = []
    for p in glyph:
        if p[0] == "dot":
            centred.append(("dot", p[1] - cx, p[2] - cy, p[3]))
        else:
            centred.append(("line", p[1] - cx, p[2] - cy,
                            p[3] - cx, p[4] - cy, p[5]))

    r_now = radius(centred)
    if r_now <= 1e-6:
        return centred
    s = max(r_target / r_now, 1.0)

    # Strokes grow as sqrt(s), NOT s. Scaling widths linearly with the
    # coordinates preserves the figure exactly - including how much of it is
    # ink - so a small glyph blown up to fill the face closes its own counters
    # and lands as a solid blob instead of line art. Sub-linear growth opens
    # the gaps back up while still thickening the strokes.
    sw = math.sqrt(s)
    w_max = max([p[3] * 2 if p[0] == "dot" else p[5] for p in centred] or [0.0])
    if w_max > 1e-6:
        sw = min(sw, max(max_stroke / w_max, 1.0))
    if abs(s - 1.0) < 1e-6 and abs(sw - 1.0) < 1e-6:
        return centred

    out = []
    for p in centred:
        if p[0] == "dot":
            out.append(("dot", p[1] * s, p[2] * s, p[3] * sw))
        else:
            out.append(("line", p[1] * s, p[2] * s, p[3] * s, p[4] * s,
                        p[5] * sw))
    return out


def build_decoration(glyph, outline, show_z, relief=RELIEF, eps=EPS,
                     inset=EDGE_INSET, name="Decoration", verbose=True):
    """Solid black figure standing on the Top show face.

    `outline` is the bead silhouette in mm (same coords as the body). Returns
    the Decoration object, spanning show_z+eps .. show_z+eps+relief.
    """
    z_lo = show_z + eps
    z_hi = z_lo + relief
    z_c = (z_lo + z_hi) / 2.0

    # Union the primitives OVERSIZED in Z, then let the final crop cut the
    # exact z_lo..z_hi slab. Building them at the true height instead makes
    # every bar and cap share top/bottom faces at exactly the same z, and
    # UNIONing coplanar faces is what the EXACT solver handles worst - it was
    # returning hundreds of non-manifold edges. The per-primitive jitter keeps
    # even the oversized faces off each other's planes.
    H_BUILD = (z_hi - z_lo) + 2.0
    _n = [0]

    def _h():
        _n[0] += 1
        return H_BUILD + _n[0] * 0.007

    acc = None
    # A sigil is a connected stroke path, so consecutive segments share an
    # endpoint and would each contribute an IDENTICAL cap cylinder there.
    # UNIONing a solid with an exact duplicate of itself is degenerate and the
    # EXACT solver returns non-manifold geometry, so emit each cap once.
    seen_caps = set()

    def add(obj):
        nonlocal acc
        if acc is None:
            acc = obj
            acc.name = name
        else:
            _boolean(acc, obj, 'UNION', "U%d" % id(obj))

    for p in glyph:
        k = p[0]
        if k == "dot":
            _, x, y, r = p
            add(_cyl(r, _h(), (x, y, z_c), verts=48))
        elif k == "line":
            _, x1, y1, x2, y2, w = p
            dx, dy = x2 - x1, y2 - y1
            ln = math.hypot(dx, dy)
            bpy.ops.mesh.primitive_cube_add(
                size=1, location=((x1 + x2) / 2, (y1 + y2) / 2, z_c))
            bar = bpy.context.active_object
            # Jitter the width by microns as well as the height: a sigil may
            # run two collinear strokes in a row, and at identical widths their
            # side faces are coplanar - the same union hazard as above. Far
            # below what a 0.4mm nozzle can resolve.
            bar.scale = (ln, w + _n[0] * 0.0011, _h())
            bar.rotation_euler = (0, 0, math.atan2(dy, dx))
            bpy.ops.object.transform_apply(scale=True, rotation=True)
            add(bar)
            # round caps so strokes join cleanly instead of leaving notches
            for (cx, cy) in ((x1, y1), (x2, y2)):
                key = (round(cx, 3), round(cy, 3), round(w, 3))
                if key in seen_caps:
                    continue
                seen_caps.add(key)
                # Radius w/2 would make the cap exactly TANGENT to the bar's
                # two side faces - a cylinder tangent to a plane is the
                # arrangement gotcha #9 warns collapses under the EXACT solver.
                # Oversize it by 2um so the surfaces cross cleanly instead.
                add(_cyl(w / 2.0 + 0.002, _h(), (cx, cy, z_c), verts=24))
        elif k in ("ring", "arc"):
            ri, ro = p[1], p[2]
            bh = _h()
            band = _cyl(ro, bh, (0, 0, z_c), verts=128)
            if ri > 1e-6:
                _boolean(band, _cyl(ri, bh * 3, (0, 0, z_c), verts=128),
                         'DIFFERENCE', "Hollow")
            if k == "arc":
                _boolean(band, _wedge(ro * 1.5, z_c - bh, z_c + bh,
                                      math.radians(p[3]), math.radians(p[4])),
                         'INTERSECT', "Wedge")
            add(band)
        else:
            raise ValueError("unknown glyph primitive %r" % (k,))

    if acc is None:
        raise ValueError("empty glyph - nothing to decorate with")
    # Weld at 1e-5, NOT the pipeline's usual 0.005. EXACT boolean output is
    # already welded; at 0.005 it collapses genuinely distinct vertices on the
    # 0.8mm-wide strokes into each other and TEARS the mesh - that alone took
    # this decoration to 1020 non-manifold edges.
    _clean(acc, 1e-5)

    # gotcha #26: crop against a FRESH silhouette extrusion, never a copy of
    # Top - a copy of Top carries the peg sockets and would punch them through
    # the decoration. This single INTERSECT does both jobs: it trims the
    # oversized union down to the exact z_lo..z_hi slab AND clips it to the
    # silhouette. Because the union overhangs the mask in Z, the cut planes
    # pass through solid material rather than lying tangent to a face, which
    # is the arrangement the EXACT solver actually handles well (gotcha #9).
    mask_pts = inset_polygon(list(outline), inset) if inset > 0 else list(outline)
    inset_applied = mask_pts != list(outline)
    mask = _prism(mask_pts, z_lo, z_hi, "DecoCrop")
    _boolean(acc, mask, 'INTERSECT', "Crop")
    _clean(acc, 1e-5)

    if not acc.data.vertices:
        raise RuntimeError(
            "decoration is EMPTY after cropping - the glyph fell entirely "
            "outside the silhouette. Do not export a bead with a missing "
            "colour; shrink the glyph or pick a wider shape.")

    nm = _nonmanifold(acc)
    zs = [acc.matrix_world @ v.co for v in acc.data.vertices]
    lo, hi = min(v.z for v in zs), max(v.z for v in zs)
    if verbose:
        print("  decoration: %d verts, z=%.2f..%.2f, non-manifold=%d, "
              "inset=%s" % (len(acc.data.vertices), lo, hi, nm,
                            "yes" if inset_applied else "no (fallback)"))
    if nm:
        raise RuntimeError("decoration non-manifold (%d edges) - do not print"
                           % nm)
    if abs(lo - z_lo) > 1e-3 or abs(hi - z_hi) > 1e-3:
        raise RuntimeError(
            "decoration z-range %.3f..%.3f != expected %.3f..%.3f - it is not "
            "sitting on the show face" % (lo, hi, z_lo, z_hi))
    return acc
