"""Eye Medallion — round NFC bead with a CLASSIC EYE built from concentric
circles raised as relief on the top show face (the eye plays the role of the
rezz spiral / the gymnast figure).

Same machinery as beads/gymnast-medallion: procedural cylinder base, asymmetric
1.5mm Bottom + 2.0mm Top halves, NTAG215 pocket, 3 chamfered snap pegs, string
hole in the THICK Top half. The only charm-specific part is the decoration: a
multi-color classic eye made of concentric circles.

The eye is fully procedural — no figure.json / SVG extraction. The white body
doubles as the sclera, so only three raised decoration regions are emitted, and
they DON'T overlap in XY (so gotcha #27's z-step ambiguity never applies):

    DecorationOutline  black ring    r 7.8 .. 9.0   (eye outline)
    (sclera = flat white body face)  r 5.0 .. 7.8
    DecorationIris     blue annulus  r 2.2 .. 5.0
    DecorationPupil    black disc    r 0   .. 2.2

Outputs (print/): Bottom.stl, Top.stl, DecorationOutline.stl, DecorationIris.stl,
DecorationPupil.stl, eye_medallion.blend, preview.png. Decoration*.stl names are
discovered by bundle_3mf.py (gotcha #28) for the multi-color slicer bundle.

Run headless:
  "D:\\tools\\blender\\blender.exe" --background --python beads/eye-medallion/build_eye_medallion.py
or exec'd live through the Blender MCP (pass {"__name__": "__main__"}, gotcha #18).
"""
import bpy, bmesh, math, os
from mathutils import Vector

# ═══ CONFIG ═══════════════════════════════════════════════════════════════
HERE       = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() \
             else r"D:\Projects\nfc-bead\beads\eye-medallion"
PRINT_DIR  = os.path.join(HERE, "print")

TARGET_WIDTH = 20.0      # mm — bead diameter
CIRCLE_VERTS = 160       # smoothness of the round base

# ── Asymmetric halves (same split as gymnast-medallion, gotcha #31) ──
# Top hosts the eye + peg SOCKETS + string hole, so it stays thick. Bottom only
# holds the shallow NFC pocket + peg bases, so it's the thin one.
TOP_THICK     = 2.0      # mm — eye side (sockets + string hole live here)
BOTTOM_THICK  = 1.5      # mm — back/NFC side (thinner)
BODY          = TOP_THICK + BOTTOM_THICK

HOLE_DIAMETER = 1.2      # mm — string hole, Kandi elastic cord. Lives in the THICK
HOLE_Y        = 7.0      # Top half (centered in its 2.0mm) — walls ~0.4mm, bridged.

NFC_DIAMETER  = 10.5     # mm — NTAG215 pocket on bottom inner face
NFC_DEPTH     = 0.8
NFC_POS       = (0.0, 0.0)   # centered: pocket reaches y=5.25, clear of the hole at y=7

# Snap-fit pegs: 2.6mm dia / 0.05mm clearance + chamfered tip (gotchas #29/#30).
PEG_DIAMETER  = 2.6
PEG_HEIGHT    = 1.2      # fits the thinner Top's socket (depth = +0.3)
PEG_CLEARANCE = 0.05     # radial — grip is good, only entry needs the chamfer
PEG_CHAMFER   = 0.35     # mm — tip taper height; tip radius shrinks by this much
PEGS = [(-7.5, 0.0), (7.5, 0.0), (0.0, -7.5)]   # radius 7.5: ~0.95mm to NFC edge

# ── The eye: concentric circles. Radii are measured from center (mm). Each ring
# is its own decoration object so the slicer can assign a filament per region.
# None of them overlap in XY, so they all sit at the SAME relief height — no
# z-step needed (gotcha #27 only bites when decorations overlap in XY).
FIT_RADIUS    = 9.0      # outermost eye radius (leaves a ~1mm white rim to the edge)
RELIEF_HEIGHT = 0.5      # mm — raised height of the eye relief
RELIEF_LIFT   = 0.01     # mm — ε lift to avoid Z-fight with the show face (gotcha #11)
# (r_inner, r_outer, color RGBA, name).  sclera = flat white body face (r 5.0..7.8)
EYE_RINGS = [
    (7.8, 9.0, (0.05, 0.05, 0.05, 1.0), "DecorationOutline"),  # black eye outline
    (2.2, 5.0, (0.10, 0.30, 0.85, 1.0), "DecorationIris"),     # blue iris
    (0.0, 2.2, (0.05, 0.05, 0.05, 1.0), "DecorationPupil"),    # black pupil
]
BODY_COLOR = (0.90, 0.90, 0.90, 1.0)   # white — also reads as the sclera

OUT_BOTTOM = os.path.join(PRINT_DIR, "Bottom.stl")
OUT_TOP    = os.path.join(PRINT_DIR, "Top.stl")
OUT_BLEND  = os.path.join(PRINT_DIR, "eye_medallion.blend")
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
    print("=" * 60); print("Eye Medallion build"); print("=" * 60)
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

    # ── peg holes on Top inner face (post-split, gotcha #1) ──
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

    # ── pegs on Bottom inner face (UNION) — full shaft + chamfered tip (gotcha #30) ──
    b_z_max = max(v.co.z for v in bottom.data.vertices)
    peg_r = PEG_DIAMETER / 2.0
    shaft_h = PEG_HEIGHT - PEG_CHAMFER
    for i, (px, py) in enumerate(PEGS):
        cyl = add_cylinder(peg_r, shaft_h, (px, py, b_z_max + shaft_h / 2.0), verts=32)
        boolean_op(bottom, cyl, 'UNION', f"Peg{i}")
        # chamfer tip: cone frustum, OVERLAPPING the shaft by 0.15mm so the UNION merges
        ov = 0.15
        bpy.ops.mesh.primitive_cone_add(
            vertices=32, radius1=peg_r, radius2=max(peg_r - PEG_CHAMFER, 0.2),
            depth=PEG_CHAMFER + ov, location=(px, py, b_z_max + shaft_h - ov + (PEG_CHAMFER + ov) / 2.0))
        boolean_op(bottom, bpy.context.active_object, 'UNION', f"PegTip{i}")
    clean_mesh(bottom)
    print(f"Bottom after chamfered pegs non-manifold: {check_nonmanifold(bottom)}")

    # ── verify string hole open (side raycast through the bead at y=HOLE_Y) ──
    verify_hole(top, Vector((-R - 2, HOLE_Y, z_hole)), Vector((1, 0, 0)), "string hole (Top)")

    # ── Decoration: concentric-circle eye on the Top show face ──
    decos = build_eye(z_max)

    # ── orient for print (centered-cylinder pipeline: NO flips needed, gotcha #16) ──
    # Bottom: back face lowest -> raise so it sits on z=0, pegs point up.
    # Top: inner face (peg holes) lowest -> sits on z=0, show face + eye up.
    bottom.location.z -= min(v.co.z for v in bottom.data.vertices)
    dz_top = min(v.co.z for v in top.data.vertices)
    top.location.z -= dz_top
    for d_obj in decos:
        d_obj.location.z -= dz_top
    bpy.context.view_layer.update()

    apply_materials(bottom, top, decos)
    export(bottom, top, decos)
    render_preview(bottom, top, decos)

    os.makedirs(PRINT_DIR, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print(f"saved {OUT_BLEND}")
    print("DONE")


def _ring_mesh(r_inner, r_outer, z0, height, name, verts=128):
    """A raised ring (annulus, or disc when r_inner==0) as a clean manifold mesh.
    Built procedurally — outer cylinder, minus inner cylinder when needed."""
    obj = add_cylinder(r_outer, height, (0, 0, z0 + height / 2.0), verts=verts)
    obj.name = name
    if r_inner > 1e-6:
        inner = add_cylinder(r_inner, height * 3, (0, 0, z0 + height / 2.0), verts=verts)
        boolean_op(obj, inner, 'DIFFERENCE', "Hollow")
    clean_mesh(obj)
    return obj


def build_eye(show_z):
    z0 = show_z + RELIEF_LIFT
    decos = []
    for (ri, ro, _color, name) in EYE_RINGS:
        d_obj = _ring_mesh(ri, ro, z0, RELIEF_HEIGHT, name)
        print(f"  {name}: ring r{ri:.1f}..{ro:.1f} relief {RELIEF_HEIGHT}mm  nm={check_nonmanifold(d_obj)}")
        decos.append(d_obj)
    return decos


def apply_materials(bottom, top, decos):
    def _mat(obj, color, nm):
        mat = bpy.data.materials.get(nm) or bpy.data.materials.new(nm)
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
        mat.diffuse_color = color
        obj.data.materials.clear(); obj.data.materials.append(mat)
        obj.color = color   # Workbench OBJECT color_type preview
    _mat(bottom, BODY_COLOR, "Body")
    _mat(top,    BODY_COLOR, "Body")
    for d_obj, (_ri, _ro, color, name) in zip(decos, EYE_RINGS):
        _mat(d_obj, color, name)


def export(bottom, top, decos):
    os.makedirs(PRINT_DIR, exist_ok=True)
    items = [(bottom, OUT_BOTTOM), (top, OUT_TOP)]
    items += [(d_obj, os.path.join(PRINT_DIR, f"{d_obj.name}.stl")) for d_obj in decos]
    for obj, path in items:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True); bpy.context.view_layer.objects.active = obj
        bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, ascii_format=False)
        print(f"  exported {path}")


def render_preview(bottom, top, decos):
    # separate the halves so the preview reads as a print layout: Bottom (pegs
    # up) on the left, Top + eye on the right. Export already happened.
    bottom.location.x -= TARGET_WIDTH * 0.7
    top.location.x += TARGET_WIDTH * 0.7
    for d_obj in decos:
        d_obj.location.x += TARGET_WIDTH * 0.7
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
