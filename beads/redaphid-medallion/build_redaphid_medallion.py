"""Gymnast Medallion — round NFC bead with the handstand gymnast as a RAISED
RELIEF on the top face (the gymnast plays the role of the rezz spiral).

Full NFC machinery: two-half snap-fit, NTAG215 pocket, 3 pegs, string hole.
The round base is built procedurally as a cylinder (cleaner than an SVG for a
circle). The figure relief is read from figure.json (run extract_figure.py
first) and scaled to fit fully inside the circle so no limb gets clipped.

Outputs (print/): Bottom.stl, Top.stl, Decoration.stl, gymnast_medallion.blend,
preview.png. Canonical object names so `nfc-make-3mf` bundles them.

Run headless:
  "D:\\tools\\blender\\blender.exe" --background --python beads/gymnast-medallion/build_gymnast_medallion.py
"""
import bpy, bmesh, math, os, json
from mathutils import Vector

# ═══ CONFIG ═══════════════════════════════════════════════════════════════
HERE         = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() \
               else r"D:\Projects\nfc-bead\beads\gymnast-medallion"
FIGURE_JSON  = os.path.join(HERE, "figure.json")
PRINT_DIR    = os.path.join(HERE, "print")

TARGET_WIDTH = 20.0      # mm — bead diameter
CIRCLE_VERTS = 160       # smoothness of the round base

# ── Asymmetric halves (user: "shrink both, mostly the back") ──
# The Top hosts the figure + the peg SOCKETS (so it must stay thick enough for
# full-length pegs) and now the string hole; the Bottom only holds the shallow
# NFC pocket + the peg bases, so it can be thinner. Body = 3.5mm + 0.5 relief =
# 4.0mm total (was 5.5mm).
TOP_THICK     = 2.0      # mm — figure side (sockets + string hole live here)
BOTTOM_THICK  = 1.5      # mm — back/NFC side (thinner)
BODY          = TOP_THICK + BOTTOM_THICK

HOLE_DIAMETER = 1.2      # mm — string hole, Kandi elastic cord. Lives in the THICK
HOLE_Y        = 7.0      # Top half (centered in its 2.0mm) — walls ~0.4mm, bridged.

NFC_DIAMETER  = 10.5     # mm — NTAG215 pocket on bottom inner face
NFC_DEPTH     = 0.8
NFC_POS       = (0.0, 0.0)   # centered: pocket reaches y=5.25, clear of the hole at y=7

# Pegs: 2.6mm dia at 0.05mm clearance grips firmly (user confirmed it holds when
# seated) — keep that. The problem was ENTRY: they had to be forced in. Add a
# CHAMFERED TIP (lead-in taper) so each peg self-starts into its socket.
PEG_DIAMETER  = 2.6
PEG_HEIGHT    = 1.2      # shorter to fit the thinner Top's socket (depth = +0.3)
PEG_CLEARANCE = 0.05     # radial — unchanged; grip is good, only entry needed help
PEG_CHAMFER   = 0.35     # mm — tip taper height; tip radius shrinks by this much
PEGS = [(-7.5, 0.0), (7.5, 0.0), (0.0, -7.5)]   # radius 7.5: ~0.95mm to NFC edge, 1.2mm to rim

FIGURE_FIT_RADIUS = 9.0  # mm — scale figure so its farthest point is this from center (1mm rim)
RELIEF_HEIGHT     = 0.5  # mm — raised height of the figure (matches rezz spiral)
RELIEF_LIFT       = 0.01 # mm — ε lift to avoid Z-fight with the show face (gotcha #11)

OUT_BOTTOM = os.path.join(PRINT_DIR, "Bottom.stl")
OUT_TOP    = os.path.join(PRINT_DIR, "Top.stl")
OUT_DECO   = os.path.join(PRINT_DIR, "Decoration.stl")
OUT_BLEND  = os.path.join(PRINT_DIR, "redaphid_medallion.blend")
PREVIEW    = os.path.join(HERE, "preview.png")


# ═══ HELPERS ══════════════════════════════════════════════════════════════
def clean_mesh(obj, threshold=0.005):
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
    b.operation = operation; b.object = cutter; b.solver = 'EXACT'
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


def verify_hole(obj, origin, direction, label=""):
    deps = bpy.context.evaluated_depsgraph_get()
    res = obj.evaluated_get(deps).ray_cast(origin, direction)
    status = "OPEN" if not res[0] else f"hit z={res[1].z:.2f}"
    print(f"  {label}: {status}")
    return not res[0]


def add_cylinder(radius, depth, location, rotation=(0, 0, 0), verts=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth,
                                        location=location, rotation=rotation)
    return bpy.context.active_object


# ═══ BUILD ════════════════════════════════════════════════════════════════
def wipe():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
    for m in list(bpy.data.meshes): bpy.data.meshes.remove(m)


def main():
    print("=" * 60); print("Redaphid Portrait Medallion build"); print("=" * 60)
    wipe()
    R = TARGET_WIDTH / 2.0

    # ── round base, centered on z=0 (z in -BODY/2 .. +BODY/2) ──
    full = add_cylinder(R, BODY, (0, 0, 0), verts=CIRCLE_VERTS)
    full.name = "FullBead"
    clean_mesh(full)
    z_min, z_max = -BODY / 2.0, BODY / 2.0
    z_split = z_min + BOTTOM_THICK          # asymmetric seam: Bottom below, Top above
    top_mid = (z_split + z_max) / 2.0        # center of the (thicker) Top half

    # ── string hole (X axis) — in the THICK Top half, centered in its thickness ──
    z_hole = top_mid
    print(f"String hole d={HOLE_DIAMETER} at Y={HOLE_Y} z={z_hole:.2f} (in Top half, "
          f"walls ~{(TOP_THICK - HOLE_DIAMETER) / 2:.2f}mm)")
    cut = add_cylinder(HOLE_DIAMETER / 2.0, TARGET_WIDTH * 2,
                       (0, HOLE_Y, z_hole), rotation=(0, math.radians(90), 0), verts=48)
    boolean_op(full, cut, 'DIFFERENCE', "Hole")
    clean_mesh(full)
    print(f"Z: {z_min:.2f}..{z_max:.2f}  seam={z_split:.2f}  (Bottom {BOTTOM_THICK} / Top {TOP_THICK})")

    # ── peg + NFC perimeter sanity (circle is convex, but verify anyway) ──
    deps = bpy.context.evaluated_depsgraph_get(); ev = full.evaluated_get(deps)
    nfc_r, peg_r = NFC_DIAMETER / 2.0, PEG_DIAMETER / 2.0
    for (px, py) in PEGS:
        edge_miss = sum(1 for k in range(8)
                        if not ev.ray_cast(Vector((px + peg_r*math.cos(k*math.pi/4),
                                                    py + peg_r*math.sin(k*math.pi/4), z_max+5)),
                                           Vector((0, 0, -1)))[0])
        nfc_clear = math.hypot(px-NFC_POS[0], py-NFC_POS[1]) - nfc_r - peg_r
        rim_clear = R - math.hypot(px, py) - peg_r
        warn = "  <-- CHECK" if (edge_miss or nfc_clear < 0 or rim_clear < 0) else ""
        print(f"  peg ({px:+.1f},{py:+.1f}): edge_out={edge_miss}/8 NFCclr={nfc_clear:.2f} rimclr={rim_clear:.2f}{warn}")

    # ── split into Bottom (lower) + Top (upper) ──
    def half(name, zlo, zhi):
        bpy.ops.object.select_all(action='DESELECT')
        full.select_set(True); bpy.context.view_layer.objects.active = full
        bpy.ops.object.duplicate()
        h = bpy.context.active_object; h.name = name
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, (zlo + zhi) / 2.0))
        b = bpy.context.active_object
        b.scale = (TARGET_WIDTH * 4, TARGET_WIDTH * 4, (zhi - zlo)); bpy.ops.object.transform_apply(scale=True)
        boolean_op(h, b, 'INTERSECT', "Cut")
        clean_mesh(h, 0.01)
        return h

    bottom = half("Bottom", z_min, z_split)
    print(f"Bottom non-manifold: {check_nonmanifold(bottom)}")
    top = half("Top", z_split, z_max)
    print(f"Top non-manifold: {check_nonmanifold(top)}")

    # ── NFC pocket on Bottom inner face ──
    b_z_max = max(v.co.z for v in bottom.data.vertices)
    d = NFC_DEPTH * 2 + 0.1
    cut = add_cylinder(NFC_DIAMETER / 2.0, d, (NFC_POS[0], NFC_POS[1], b_z_max - NFC_DEPTH + d/2.0), verts=64)
    boolean_op(bottom, cut, 'DIFFERENCE', "NFC")
    clean_mesh(bottom)

    # ── peg holes on Top inner face (post-split) ──
    t_z_min = min(v.co.z for v in top.data.vertices)
    hole_r = (PEG_DIAMETER + PEG_CLEARANCE * 2) / 2.0
    for i, (px, py) in enumerate(PEGS):
        cb, ct = t_z_min - 1.0, t_z_min + PEG_HEIGHT + 0.3
        cut = add_cylinder(hole_r, ct - cb, (px, py, (cb + ct) / 2.0), verts=32)
        boolean_op(top, cut, 'DIFFERENCE', f"PH{i}")
    clean_mesh(top)
    print(f"Top after peg holes non-manifold: {check_nonmanifold(top)}")
    for i, (px, py) in enumerate(PEGS):
        verify_hole(top, Vector((px, py, t_z_min - 2)), Vector((0, 0, 1)), f"peg hole {i}")

    # ── pegs on Bottom inner face (UNION) — full shaft + chamfered tip ──
    # The shaft (full PEG_DIAMETER) does the gripping; the tip tapers down over
    # PEG_CHAMFER so the peg self-starts into the socket instead of catching on
    # the rim and needing to be forced.
    b_z_max = max(v.co.z for v in bottom.data.vertices)
    peg_r = PEG_DIAMETER / 2.0
    shaft_h = PEG_HEIGHT - PEG_CHAMFER
    for i, (px, py) in enumerate(PEGS):
        cyl = add_cylinder(peg_r, shaft_h, (px, py, b_z_max + shaft_h / 2.0), verts=32)
        boolean_op(bottom, cyl, 'UNION', f"Peg{i}")
        # chamfer tip: frustum from full radius up to (full - PEG_CHAMFER)
        bpy.ops.mesh.primitive_cone_add(
            vertices=32, radius1=peg_r, radius2=max(peg_r - PEG_CHAMFER, 0.2),
            depth=PEG_CHAMFER, location=(px, py, b_z_max + shaft_h + PEG_CHAMFER / 2.0))
        boolean_op(bottom, bpy.context.active_object, 'UNION', f"PegTip{i}")
    clean_mesh(bottom)
    print(f"Bottom after chamfered pegs non-manifold: {check_nonmanifold(bottom)}")

    # ── Decoration: gymnast relief on Top show face ──
    deco = build_decoration(z_max)

    # ── orient for print (centered-cylinder pipeline: NO flips needed) ──
    # Bottom: circle/back face is lowest (z_min) -> raise so it sits on z=0,
    #         pegs point up. Top: inner face (peg holes) already lowest -> sits
    #         on z=0, show face + figure up. Decoration rides with Top.
    bottom.location.z -= min(v.co.z for v in bottom.data.vertices)
    dz_top = min(v.co.z for v in top.data.vertices)
    top.location.z -= dz_top
    deco.location.z -= dz_top
    bpy.context.view_layer.update()

    apply_materials(bottom, top, deco)
    export(bottom, top, deco)
    render_preview(bottom, top, deco)

    os.makedirs(PRINT_DIR, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print(f"saved {OUT_BLEND}")
    print("DONE")


def _area_centroid(pts):
    """Shoelace area-centroid — the figure's visual center of mass, not the
    bbox center (which a long thin limb skews)."""
    A = cx = cy = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]; x1, y1 = pts[(i + 1) % n]
        cr = x0 * y1 - x1 * y0
        A += cr; cx += (x0 + x1) * cr; cy += (y0 + y1) * cr
    if abs(A) < 1e-9:
        return sum(x for x, _ in pts) / n, sum(y for _, y in pts) / n
    return cx / (3 * A), cy / (3 * A)


def build_decoration(show_z):
    data = json.load(open(FIGURE_JSON))
    poly = data["polygon"]
    if len(poly) > 2 and abs(poly[0][0]-poly[-1][0]) < 1e-4 and abs(poly[0][1]-poly[-1][1]) < 1e-4:
        poly = poly[:-1]
    # Center on the area centroid (visual mass), not the bbox.
    ccx, ccy = _area_centroid(poly)
    poly = [(x - ccx, y - ccy) for x, y in poly]
    # scale so farthest point from the (mass) center == FIGURE_FIT_RADIUS
    rmax = max(math.hypot(x, y) for x, y in poly)
    s = FIGURE_FIT_RADIUS / rmax
    print(f"  portrait mass-centered (shifted {ccx:+.2f},{ccy:+.2f} from bbox)")
    z0 = show_z + RELIEF_LIFT
    bm = bmesh.new()
    verts = [bm.verts.new((x * s, y * s, z0)) for x, y in poly]
    face = bm.faces.new(verts)
    bm.normal_update()
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    up = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, RELIEF_HEIGHT), verts=up)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("Decoration"); bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new("Decoration", mesh)
    bpy.context.scene.collection.objects.link(obj)

    # Eyes: cut through the relief (same centroid-shift + scale) so the Top
    # show face (body color) reads through -> a 2-color portrait.
    eyes = data.get("eyes", [])
    for i, e in enumerate(eyes):
        ex, ey = (e["x"] - ccx) * s, (e["y"] - ccy) * s
        er = e["r"] * s
        cut = add_cylinder(er, RELIEF_HEIGHT + 1.0, (ex, ey, z0 + RELIEF_HEIGHT / 2.0), verts=32)
        boolean_op(obj, cut, 'DIFFERENCE', f"Eye{i}")
    clean_mesh(obj)
    print(f"Decoration: portrait scaled {s:.3f}x -> fits radius {FIGURE_FIT_RADIUS}mm, "
          f"relief {RELIEF_HEIGHT}mm, {len(poly)} pts, {len(eyes)} eyes cut through")
    return obj


def apply_materials(bottom, top, deco):
    specs = [(bottom, (0.85, 0.15, 0.15, 1), "Body"),   # red body
             (top,    (0.85, 0.15, 0.15, 1), "Body"),
             (deco,   (0.05, 0.05, 0.05, 1), "Figure")]  # black figure
    for obj, color, nm in specs:
        mat = bpy.data.materials.get(nm) or bpy.data.materials.new(nm)
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
        mat.diffuse_color = color
        obj.data.materials.clear(); obj.data.materials.append(mat)
        obj.color = color   # for Workbench OBJECT color_type preview


def export(bottom, top, deco):
    os.makedirs(PRINT_DIR, exist_ok=True)
    for obj, path in [(bottom, OUT_BOTTOM), (top, OUT_TOP), (deco, OUT_DECO)]:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True); bpy.context.view_layer.objects.active = obj
        bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, ascii_format=False)
        print(f"  exported {path}")


def render_preview(bottom, top, deco):
    # separate the halves so the preview reads as a print layout: Bottom (pegs
    # up) on the left, Top + figure on the right. Export already happened, so
    # moving objects here is preview-only.
    bottom.location.x -= TARGET_WIDTH * 0.7
    top.location.x += TARGET_WIDTH * 0.7
    deco.location.x += TARGET_WIDTH * 0.7
    bpy.context.view_layer.update()
    cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = (8, -34, 30); cam.rotation_euler = (math.radians(50), 0, math.radians(12))
    cam_d.type = "ORTHO"; cam_d.ortho_scale = 60
    bpy.context.scene.camera = cam
    ld = bpy.data.lights.new("Sun", type="SUN"); ld.energy = 4.0
    light = bpy.data.objects.new("Sun", ld); bpy.context.scene.collection.objects.link(light)
    light.rotation_euler = (math.radians(35), math.radians(15), 0)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x = 1200; sc.render.resolution_y = 900
    sc.display.shading.color_type = "OBJECT"
    sc.render.filepath = PREVIEW
    bpy.ops.render.render(write_still=True)
    print(f"  rendered {PREVIEW}")


if __name__ == "__main__":
    main()
