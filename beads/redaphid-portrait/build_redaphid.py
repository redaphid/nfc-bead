"""Redaphid-portrait NFC bead builder.

Imports the silhouette traced from the screenshot via Sobel-style
edge extraction, then runs the canonical NFC-bead pipeline (extrude,
string hole, split, NFC pocket, peg holes, pegs).

Eye positions are taken from the SVG <circle> elements emitted by
extract_silhouette.py and become a single neon "Decoration" object.

Run via Blender MCP `exec(open(r"<path>").read())`, or:
    blender --background --python build_redaphid.py
"""
import bpy
import bmesh
import math
import os
import re
from mathutils import Vector

# ── CONFIG ─────────────────────────────────────────────────────────
SVG_PATH      = r"D:\Projects\nfc-bead\beads\redaphid-portrait\silhouette.svg"
HAIR_SVG_PATH = r"D:\Projects\nfc-bead\beads\redaphid-portrait\hair.svg"
REPO_DIR      = r"D:\Projects\nfc-bead"
BEAD_DIR      = os.path.join(REPO_DIR, "beads", "redaphid-portrait")

TARGET_WIDTH  = 20.0           # mm (kandi-bracelet — shrunk again after second print)
THICKNESS     = 5.0            # mm total (split 2.5 + 2.5). v5 returns to v3 thickness
                               # because v5 also moves the entire string hole into Top
                               # (HOLE_Z_OFFSET below): tube walls of 0.5 mm above + below
                               # only fit cleanly when the host half is ≥ 2.5 mm thick.

# String hole: along X axis, through the HAIR BAND. Scaled with TARGET_WIDTH.
# Silhouette top ≈ y=+8.46 (TARGET_WIDTH=20, h_mm=16.92, half=8.46).
# Third-print fix: HOLE_DIA 2.0 → 1.5 + HOLE_Y 6.6 → 5.5 because the
# previous wall above the hole (0.86 mm) snapped on the printed bead.
# y=5.5 + 0.75 (radius) leaves 8.46 − 5.5 − 0.75 = 2.21 mm solid wall.
HOLE_DIA      = 1.5
HOLE_Y        = 5.5            # mm — through hair, ≥ 2.2 mm wall above
# Z offset of the string-hole center from the bead's Z midplane. 0 (recipe
# default) puts the hole *on* the split plane → each half hosts an open
# half-circle groove on its inner face. Non-zero shifts the hole entirely
# into one half so the inner face is solid at y=HOLE_Y (better first-layer
# adhesion) and the tube becomes a small interior cavity bridged twice by
# the slicer. Sign: positive → into Top, negative → into Bottom.
# At THICKNESS=5.0 the Top half spans z=[0,+2.5]; +1.25 centers the tube
# in Top (z=[+0.50, +2.00]), giving 0.50 mm wall above + below the tube.
HOLE_Z_OFFSET = 1.25

# NFC pocket — face/snout area, below the eyes, well within head ellipse
NFC_DIAMETER  = 10.0
NFC_DEPTH     = 0.8
NFC_POS       = (0.0, -1.0)    # mm — kept where it was even after dropping the
                               # chin peg in v4; the offset still keeps the NFC
                               # pocket clear of the eye decorations and the
                               # string hole channel above.

# Peg friction-fit
PEG_DIAMETER  = 2.6            # mm — v5 bumped from 2.0 (recipe default) for
                               # better friction grip on the assembled bead.
                               # Thicker pegs cost silhouette-clearance margin,
                               # so PEG_CANDIDATES below pulls each peg inward.
PEG_HEIGHT    = 1.5            # mm — recipe default; first print at 1.0 mm
                               # didn't grip. With THICKNESS=5 (halves 2.5),
                               # sockets at 1.8 mm leave 0.7 mm wall — fine.
PEG_CLEARANCE = 0.05         # mm radial — recipe default 0.1 was too generous
                              # for the Centauri Carbon 2; v5c assembled but had
                              # no snap. Halved for v6 (only Top changes — sockets
                              # are in Top; pegs in Bottom keep their dimensions).
# Four pegs in a quadrilateral. The original v3/v4 used a centered chin
# peg at (0, -8), but with PEG_DIAMETER=2.6 there is NO valid y position
# for a peg on x=0 in the chin region — the NFC bottom edge (y=-6, plus
# 0.5 mm clearance + 1.3 mm peg radius = y < -7.8) and the silhouette
# y_min near x=0 (≈ -8.44, plus 1.3 mm peg radius = y > -7.04) exclude
# each other. The off-axis pair (±4.5, -7) sits in the wider lower-face
# silhouette and clears NFC by ~1.2 mm. Bonus: 4 anchors hold the halves
# more rigidly than a triangulated 3, especially with thicker pegs.
# Each entry is either (x, y) — uses the global PEG_DIAMETER — or
# (x, y, dia) which overrides the diameter for that one peg only. This
# lets the centerline chin peg use a thinner profile that actually fits
# between NFC and the silhouette boundary, while keeping the side pegs
# at full thickness for friction. After a real print, the v5b 4-peg
# layout had jaw pegs at (±4.3, -7.1) whose sockets visibly poked through
# the neck of the silhouette — even though the verifier passed them,
# wall-thickness around the socket was paper-thin in places. Going back
# to a 3-peg triangle with one centered chin peg is the correct topology;
# the trick is that the chin peg has to be smaller (1.4 mm) because the
# centerline at this y simply cannot host a 2.6 mm peg + NFC + silhouette
# clearance — the inequality has no solution (proved analytically).
PEG_CANDIDATES = [
    ( 7.0,  0.0),         # right ear / mid-head — default 2.6 mm
    (-7.0,  0.0),         # left ear / mid-head — default 2.6 mm
    ( 0.0, -7.4, 1.7),    # centered chin — bumped from 1.4 mm in v6 because
                          # the assembled bead had no friction. 1.7 mm is at
                          # the math limit of what fits between NFC bottom
                          # (y=-6) and the silhouette y_min near x=0 (≈-8.44)
                          # once peg radius + socket clearance are added.
]

# Peg ↔ socket assignment. Recipe default puts pegs on Bottom + sockets on
# Top; setting this False inverts (pegs on Top stick DOWN, sockets recessed
# UP into Bottom body). PEGS_ON_BOTTOM=False causes a printability problem:
# pegs hanging off Top become cantilevers in the slicer (Top assembly with
# Hair + Decoration on the show face can't be flipped to put pegs up because
# the hair would point into the build plate). Keep True for printable charms.
PEGS_ON_BOTTOM = True

# Eye decoration — raised cylinders. Positions below are FALLBACKs,
# overridden if SVG carries <circle> elements.
EYE_HEIGHT       = 0.5
EYE_FALLBACK     = [(-2.5, 2.0, 1.3), (2.5, 2.0, 1.3)]  # (x, y, r) mm

# Hair region — imported directly from hair.svg (the haircut shape:
# top of silhouette + side ear-flaps). Top's full silhouette show face
# stays as the skin/face base; Hair sits ON TOP of it, covering only
# the haircut regions. Where Hair isn't (face + chin/neck), Top's body
# color shows through.
HAIR_HEIGHT     = 0.4

# Pegs need to land in HAIR or BODY area, not crossing the face contour
# silhouette. The default candidates are validated against the silhouette
# only; future iteration could also reject any candidate that lands inside
# the imported face mesh.
PEG_CANDIDATES_OVERRIDE = None

# ── HELPERS ─────────────────────────────────────────────────────────


def boolean_op(target, cutter, operation, name, solver='EXACT'):
    bpy.ops.object.select_all(action='DESELECT')
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    b = target.modifiers.new(name=name, type='BOOLEAN')
    b.operation = operation
    b.object = cutter
    b.solver = solver
    bpy.ops.object.modifier_apply(modifier=name)
    bpy.ops.object.select_all(action='DESELECT')
    cutter.select_set(True)
    bpy.ops.object.delete()


def clean_mesh(obj, threshold=0.005):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=threshold)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def seal_nm(obj):
    """Tiny remove_doubles + fill_holes to close cut-plane seams."""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0005)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold()
    bpy.ops.mesh.fill_holes(sides=0)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def parse_eyes_from_svg(svg_path):
    """Extract eye positions from SVG <circle> data. Returns list of (x, y, r)
    in mm, in **Blender coordinates** (centered at origin, y-axis up)."""
    if not os.path.isfile(svg_path):
        return list(EYE_FALLBACK)
    txt = open(svg_path, encoding='utf-8').read()
    # Match width/height in mm
    w_match = re.search(r'width="([\d.]+)mm"', txt)
    h_match = re.search(r'height="([\d.]+)mm"', txt)
    if not (w_match and h_match):
        return list(EYE_FALLBACK)
    w_mm = float(w_match.group(1))
    h_mm = float(h_match.group(1))
    cx = w_mm / 2.0
    cy = h_mm / 2.0
    eyes = []
    for m in re.finditer(
        r'<circle\s+cx="([\d.]+)"\s+cy="([\d.]+)"\s+r="([\d.]+)"', txt
    ):
        ex, ey, er = float(m.group(1)), float(m.group(2)), float(m.group(3))
        # SVG: y down, origin top-left. Blender: y up, origin centered.
        bx = ex - cx
        by = -(ey - cy)        # invert y
        eyes.append((bx, by, er))
    return eyes if len(eyes) >= 2 else list(EYE_FALLBACK)


def setup_theater_scene():
    """Camera + animated turntable + 3-point lighting + dark world."""
    scn = bpy.context.scene
    # Drop everything in scene first
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for c in list(bpy.data.collections):
        if c.name != 'Scene Collection':
            bpy.data.collections.remove(c)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)

    turn = bpy.data.objects.new("Turntable", None)
    scn.collection.objects.link(turn)
    turn.location = (0, 0, 2.5)

    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Camera", cam_data)
    scn.collection.objects.link(cam)
    cam.parent = turn
    cam.location = (0, -36, 14)
    cam.rotation_euler = (math.radians(72), 0, 0)
    cam_data.lens = 70
    cam_data.clip_start = 0.1
    cam_data.clip_end = 500
    scn.camera = cam

    scn.frame_start = 1
    scn.frame_end = 240
    fcd = turn.driver_add("rotation_euler", 2)
    fcd.driver.expression = "frame * (2 * pi / 240)"
    fcd.driver.type = 'SCRIPTED'

    def L(name, ltype, energy, loc, rot=(0, 0, 0), color=(1, 1, 1), size=5):
        d = bpy.data.lights.new(name, type=ltype)
        d.energy = energy
        d.color = color
        if ltype == 'AREA':
            d.size = size
        o = bpy.data.objects.new(name, d)
        o.location = loc
        o.rotation_euler = rot
        scn.collection.objects.link(o)

    L("Key",  'AREA', 800, (-20, -25, 30), (math.radians(50), 0, math.radians(-30)),
      color=(1.0, 0.95, 0.9), size=18)
    L("Fill", 'AREA', 250, (25, -10, 18),  (math.radians(70), 0, math.radians(60)),
      color=(0.85, 0.9, 1.0), size=22)
    L("Rim",  'AREA', 600, (0, 30, 25),    (math.radians(115), 0, 0),
      color=(1.0, 0.55, 0.85), size=14)

    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.02, 0.02, 0.04, 1)
    scn.world = world

    # Material preview shading + camera view
    for area in bpy.context.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        for space in area.spaces:
            if space.type != 'VIEW_3D':
                continue
            space.shading.type = 'MATERIAL'
            space.shading.use_scene_world = True
            space.shading.use_scene_lights = True
            space.region_3d.view_perspective = 'CAMERA'
            space.overlay.show_floor = False
            space.overlay.show_axis_x = False
            space.overlay.show_axis_y = False
            space.overlay.show_cursor = False

    bpy.ops.screen.animation_play()


def import_silhouette():
    """Import the SVG, convert to mesh, scale to TARGET_WIDTH, center origin."""
    bpy.ops.import_curve.svg(filepath=SVG_PATH)
    curves = [o for o in bpy.context.scene.objects if o.type == 'CURVE']
    if not curves:
        raise RuntimeError("SVG import produced no curves")
    bpy.ops.object.select_all(action='DESELECT')
    for c in curves:
        c.select_set(True)
    bpy.context.view_layer.objects.active = curves[0]
    if len(curves) > 1:
        bpy.ops.object.join()

    # The silhouette path is the largest spline; the eye <circle>s are
    # also imported as smaller curves. Filter to keep ONLY the largest by
    # bounding-box area before mesh conversion.
    obj = bpy.context.active_object
    obj.data.dimensions = '2D'
    obj.data.fill_mode = 'BOTH'
    obj.data.resolution_u = 64

    # Drop any spline whose bbox is smaller than 5% of the largest — that
    # culls the two eye <circle>s, leaving only the silhouette path.
    splines = list(obj.data.splines)
    if len(splines) > 1:
        def spline_area(sp):
            xs = [p.co.x for p in (sp.points if sp.type != 'BEZIER' else sp.bezier_points)]
            ys = [p.co.y for p in (sp.points if sp.type != 'BEZIER' else sp.bezier_points)]
            if not xs:
                return 0.0
            return (max(xs) - min(xs)) * (max(ys) - min(ys))
        biggest = max(spline_area(s) for s in splines)
        threshold = biggest * 0.05
        for s in list(obj.data.splines):
            if spline_area(s) < threshold:
                obj.data.splines.remove(s)

    # Convert curve → mesh
    bpy.ops.object.convert(target='MESH')
    mesh = bpy.context.active_object

    # Scale: SVG units come in as meters by default; scale to target width
    cur_w = mesh.dimensions.x
    if cur_w > 0:
        sf = (TARGET_WIDTH / 1000.0) / cur_w
        mesh.scale = (sf, sf, sf)
        bpy.ops.object.transform_apply(scale=True)
    mesh.scale = (1000.0, 1000.0, 1000.0)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    mesh.location = (0, 0, 0)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

    print(f"[redaphid] silhouette flat: {mesh.dimensions.x:.2f} x {mesh.dimensions.y:.2f}")
    return mesh


def extrude_to_thickness(mesh):
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.extrude_region_move(
        TRANSFORM_OT_translate={"value": (0, 0, THICKNESS)})
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    mesh.location = (0, 0, 0)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    d = mesh.dimensions
    print(f"[redaphid] extruded: {d.x:.2f} x {d.y:.2f} x {d.z:.2f}")
    return mesh


def drill_string_hole(mesh):
    d = mesh.dimensions
    # Drill at the mesh's actual Z midpoint, NOT THICKNESS/2 — extrude_to_thickness
    # leaves verts spanning z=−THICKNESS/2..+THICKNESS/2 (centered), so a
    # hard-coded THICKNESS/2 put the hole at the TOP face instead of the middle.
    # Compute z_mid live, then offset by HOLE_Z_OFFSET (positive → into Top,
    # negative → into Bottom; 0 keeps the recipe-default split-plane hole).
    zs = [v.co.z for v in mesh.data.vertices]
    z_mid = (min(zs) + max(zs)) / 2.0
    z_hole = z_mid + HOLE_Z_OFFSET
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=48, radius=HOLE_DIA / 2.0, depth=d.x * 4,
        location=(0, HOLE_Y, z_hole),
        rotation=(0, math.radians(90), 0))
    boolean_op(mesh, bpy.context.active_object, 'DIFFERENCE', "Hole")
    clean_mesh(mesh)
    mesh.name = "FullBead"
    print(f"[redaphid] string hole drilled @ y={HOLE_Y}, z_hole={z_hole:.2f} (offset={HOLE_Z_OFFSET:+.2f})")


def split_halves(mesh):
    z_min = min(v.co.z for v in mesh.data.vertices)
    z_max = max(v.co.z for v in mesh.data.vertices)
    z_mid = (z_min + z_max) / 2.0
    box_size = 200

    # Bottom
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.duplicate()
    bottom = bpy.context.active_object
    bottom.name = "Bottom"
    bpy.ops.mesh.primitive_cube_add(size=1,
        location=(0, 0, z_min + (z_mid - z_min) / 2.0))
    box = bpy.context.active_object
    box.scale = (box_size, box_size, (z_mid - z_min))
    bpy.ops.object.transform_apply(scale=True)
    boolean_op(bottom, box, 'INTERSECT', "Cut")
    clean_mesh(bottom, 0.01)

    # Top
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.duplicate()
    top = bpy.context.active_object
    top.name = "Top"
    bpy.ops.mesh.primitive_cube_add(size=1,
        location=(0, 0, z_mid + (z_max - z_mid) / 2.0))
    box = bpy.context.active_object
    box.scale = (box_size, box_size, (z_max - z_mid))
    bpy.ops.object.transform_apply(scale=True)
    boolean_op(top, box, 'INTERSECT', "Cut")
    clean_mesh(top, 0.01)

    mesh.hide_set(True)
    mesh.hide_render = True
    print(f"[redaphid] split. Bottom={bottom.dimensions.z:.2f}, Top={top.dimensions.z:.2f}")
    return bottom, top


def _peg_dia(entry):
    """Per-peg diameter: PEG_CANDIDATES entries are (x,y) for the default
    PEG_DIAMETER, or (x,y,dia) to override on that peg only."""
    return entry[2] if len(entry) >= 3 else PEG_DIAMETER


def verify_pegs(mesh, candidates):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_full = mesh.evaluated_get(depsgraph)
    nfc_r = NFC_DIAMETER / 2.0
    valid = []
    for entry in candidates:
        px, py = entry[0], entry[1]
        peg_d = _peg_dia(entry)
        peg_r = peg_d / 2.0
        # Check at the SOCKET radius — wider than the peg by PEG_CLEARANCE on
        # each side. The socket is what carves through the half-shell via
        # boolean DIFFERENCE; if its perimeter pokes past the silhouette, the
        # printed bead shows a malformed open hole instead of a clean socket.
        socket_r = peg_r + PEG_CLEARANCE
        perim_offsets = [(socket_r * math.cos(k * math.pi / 4.0),
                          socket_r * math.sin(k * math.pi / 4.0)) for k in range(8)]
        center_hit = eval_full.ray_cast(
            Vector((px, py, 10)), Vector((0, 0, -1)))[0]
        edge_misses = [(ox, oy) for ox, oy in perim_offsets
                       if not eval_full.ray_cast(
                           Vector((px + ox, py + oy, 10)),
                           Vector((0, 0, -1)))[0]]
        in_silhouette = center_hit and not edge_misses
        nfc_dist = math.sqrt((px - NFC_POS[0]) ** 2 + (py - NFC_POS[1]) ** 2)
        nfc_clear = nfc_dist - nfc_r - peg_r
        hole_dist = abs(py - HOLE_Y)
        ok = in_silhouette and nfc_clear > 0.5 and hole_dist > peg_r + 1.0
        edge_note = "" if not edge_misses else f"  edges_clipping={len(edge_misses)}/8"
        print(f"  peg ({px:+.2f},{py:+.2f}) d={peg_d:.1f}: solid={center_hit}  "
              f"nfc_clear={nfc_clear:+.2f}  hole_d={hole_dist:.2f}{edge_note}  "
              f"-> {'OK' if ok else 'REJECTED'}")
        if ok:
            valid.append(entry)
    if len(valid) < len(candidates):
        raise RuntimeError(
            f"Only {len(valid)} of {len(candidates)} configured peg(s) validated; "
            "refine PEG_CANDIDATES so every entry passes the silhouette/NFC/hole checks")
    return valid


def add_nfc_pocket(bottom):
    b_z_max = max((bottom.matrix_world @ v.co).z for v in bottom.data.vertices)
    cd = NFC_DEPTH * 2 + 0.1
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64, radius=NFC_DIAMETER / 2.0, depth=cd,
        location=(NFC_POS[0], NFC_POS[1], b_z_max - NFC_DEPTH + cd / 2.0))
    boolean_op(bottom, bpy.context.active_object, 'DIFFERENCE', "NFC")
    clean_mesh(bottom)


def add_peg_sockets(half, pegs, mode):
    """Drill peg sockets into a half.

    mode='into_top'    : drill UP into the top half from its bottom face
                         (ceiling sockets — pegs come from below).
    mode='into_bottom' : drill DOWN into the bottom half from its top face
                         (floor sockets — pegs come from above, hanging
                         off the top half's inner face).
    """
    if mode == 'into_top':
        z_face = min((half.matrix_world @ v.co).z for v in half.data.vertices)
        cb = z_face - 1.0                            # 1 mm below face — through-going cutter
        ct = z_face + PEG_HEIGHT + 0.3
    elif mode == 'into_bottom':
        z_face = max((half.matrix_world @ v.co).z for v in half.data.vertices)
        cb = z_face - PEG_HEIGHT - 0.3
        ct = z_face + 1.0                            # 1 mm above face
    else:
        raise ValueError(f"unknown socket mode: {mode}")
    for i, entry in enumerate(pegs):
        px, py = entry[0], entry[1]
        peg_d = _peg_dia(entry)
        hole_r = (peg_d + PEG_CLEARANCE * 2) / 2.0
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=32, radius=hole_r, depth=ct - cb,
            location=(px, py, (cb + ct) / 2.0))
        boolean_op(half, bpy.context.active_object, 'DIFFERENCE', f"PH{i}")
    clean_mesh(half)


def add_pegs(half, pegs, mode):
    """UNION peg cylinders onto a half.

    mode='from_bottom_up'  : pegs on bottom half, sticking UP from inner face
    mode='from_top_down'   : pegs on top half,    hanging DOWN from inner face
    """
    if mode == 'from_bottom_up':
        z_face = max((half.matrix_world @ v.co).z for v in half.data.vertices)
        cz = z_face + PEG_HEIGHT / 2.0
    elif mode == 'from_top_down':
        z_face = min((half.matrix_world @ v.co).z for v in half.data.vertices)
        cz = z_face - PEG_HEIGHT / 2.0
    else:
        raise ValueError(f"unknown peg mode: {mode}")
    for i, entry in enumerate(pegs):
        px, py = entry[0], entry[1]
        peg_d = _peg_dia(entry)
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=32, radius=peg_d / 2.0, depth=PEG_HEIGHT,
            location=(px, py, cz))
        boolean_op(half, bpy.context.active_object, 'UNION', f"Peg{i}")
    clean_mesh(half)


def build_eye_decoration(eyes_xyr, top):
    """Two raised cylinders at eye positions; joined into 'Decoration'.

    Z is taken from `top`'s actual world-space max-Z so eyes sit flush on
    the show face regardless of how the build script shifted the origin.
    """
    show_z = max((top.matrix_world @ v.co).z for v in top.data.vertices)
    objs = []
    for i, (ex, ey, er) in enumerate(eyes_xyr):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=48, radius=er, depth=EYE_HEIGHT,
            # Eyes sit DIRECTLY on Top's show face. The face contour cuts
            # the Hair slab away from the eye region, so there's nothing
            # else for the eyes to rest on. Same Z baseline as Hair so
            # printability + color-region cleanliness are both preserved.
            location=(ex, ey, show_z + 0.01 + EYE_HEIGHT / 2.0))
        o = bpy.context.active_object
        o.name = f"Eye_tmp_{i}"
        objs.append(o)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs[1:]:
        o.select_set(True)
    objs[0].select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    deco = bpy.context.active_object
    deco.name = "Decoration"
    return deco


def build_hair_decoration(top, full_silhouette):
    """Hair = imported hair.svg (the haircut shape), extruded HAIR_HEIGHT
    on top of the Top show face. No face subtraction — Top's full
    silhouette show face stays underneath as the skin/face color, and
    Hair drapes over the haircut regions on top."""
    show_z = max((top.matrix_world @ v.co).z for v in top.data.vertices)

    # Import hair.svg as a fresh curve set
    pre = set(bpy.data.objects.keys())
    bpy.ops.import_curve.svg(filepath=HAIR_SVG_PATH)
    new_curves = [bpy.data.objects[n] for n in bpy.data.objects.keys() if n not in pre]
    if not new_curves:
        raise RuntimeError("hair.svg import produced no objects")
    bpy.ops.object.select_all(action='DESELECT')
    for c in new_curves:
        c.select_set(True)
    bpy.context.view_layer.objects.active = new_curves[0]
    if len(new_curves) > 1:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.data.dimensions = '2D'
    obj.data.fill_mode = 'BOTH'
    obj.data.resolution_u = 64

    # Convert curve → mesh, scale to share silhouette coordinate frame
    bpy.ops.object.convert(target='MESH')
    hair = bpy.context.active_object
    hair.name = "Hair"
    cur_w = hair.dimensions.x
    if cur_w > 0:
        sf = (TARGET_WIDTH / 1000.0) / cur_w
        hair.scale = (sf, sf, sf)
        bpy.ops.object.transform_apply(scale=True)
    hair.scale = (1000.0, 1000.0, 1000.0)
    bpy.ops.object.transform_apply(scale=True)

    # Both SVGs (silhouette + hair) share the same viewBox, so origin_set
    # BOUNDS gives the silhouette's bbox center for both — same X/Y frame.
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

    # The silhouette occupies the FULL viewBox; the haircut is a SUBSET of
    # it. Their bbox CENTERS therefore differ slightly — using BOUNDS-
    # origin would re-center the haircut to (0,0), pulling it sideways
    # off the silhouette. Instead, restore the haircut to its absolute
    # SVG-native position by shifting back so its centroid matches what
    # an SVG-coord-preserving import would have produced.
    # SVG width 25 mm centered → x range -12.5..+12.5 in mm before BOUNDS.
    # After BOUNDS, hair was re-centered. To put it back at the
    # silhouette's coordinate frame, we'd need the haircut's original
    # centroid offset. Easier: rely on the fact that we DON'T call
    # BOUNDS on the silhouette pre-extrude either — we use BOUNDS there
    # too. So both meshes get bbox-centered, which means the silhouette
    # center sits at (0,0) and the hair center sits at (0,0). Their
    # actual positions in the SOURCE image differ but get re-aligned by
    # this BOUNDS pass — which is what we want, since both viewBoxes
    # are the same.
    #
    # ACTUALLY — silhouette spans the full viewBox so its bbox center IS
    # the viewBox center. Hair spans only the upper-and-sides portion of
    # the viewBox so its bbox center is OFFSET from the viewBox center
    # (further up). After BOUNDS, both centers land at (0,0), which
    # MIS-ALIGNS them.
    #
    # Fix: place the hair such that its viewBox-relative position
    # matches. We already know the silhouette's viewBox center maps to
    # (0,0) and silhouette y range is symmetric about y=0. Hair's
    # viewBox-relative y center is (h_top + h_bot) / 2 — that's where
    # hair should sit relative to viewBox center. We can't get that here
    # without parsing the SVG. Cheapest fix: write hair.svg using the
    # FULL viewBox of silhouette but keep hair shape's pixels in their
    # original positions, so its bbox != viewBox and BOUNDS re-centers
    # it correctly when the source is repositioned.
    # extract_silhouette.py already writes hair.svg with the same
    # viewBox; the hair PATH retains its coordinates inside that
    # viewBox. After Blender's import, the imported curve KEEPS the
    # coordinate frame of the SVG viewBox (origin at viewBox top-left).
    # When we then origin_set BOUNDS, it re-centers around the bbox of
    # the *path*, not the viewBox — which is the bug.
    #
    # Correct approach: SHIFT the hair so its viewBox top-left sits where
    # the silhouette's viewBox top-left sat before bbox-centering. The
    # silhouette before BOUNDS occupies x=[0..25] y=[-thickness..0]
    # (after extrude). After BOUNDS, silhouette center → (0,0,h/2).
    # Equivalent shift on hair: shift by viewBox_center → centers viewBox
    # not bbox. We can simulate by inversely shifting the SVG-parsed
    # offset:
    #     hair_center_in_viewBox = (hair_bbox_center) in SVG coords
    #     viewBox_center = (W/2, H/2) in SVG coords
    #     shift = viewBox_center - hair_center_in_viewBox
    # Apply that shift in mm to bring hair into silhouette frame.
    # Read the SVG to get that offset.
    import re
    svg_text = open(HAIR_SVG_PATH, encoding='utf-8').read()
    vb = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg_text)
    if vb:
        view_w = float(vb.group(1))
        view_h = float(vb.group(2))
        # Hair bbox center in SVG coords from the path d (parse first M and all L points):
        coords = re.findall(r'[ML]\s*([-\d.]+),([-\d.]+)', svg_text)
        if coords:
            xs = [float(x) for x, _ in coords]
            ys = [float(y) for _, y in coords]
            hair_cx_svg = (max(xs) + min(xs)) / 2.0
            hair_cy_svg = (max(ys) + min(ys)) / 2.0
            view_cx_svg = view_w / 2.0
            view_cy_svg = view_h / 2.0
            # Shift in SVG mm. SVG y increases downward; Blender y is up.
            # After Blender's SVG import, the curve's y is inverted.
            # After Blender SVG import + BOUNDS, hair.location is at hair's
            # bbox center in world coords (i.e., the same Blender world
            # position the bbox-center vertex would occupy). To put hair
            # in the silhouette's frame, set its location to where its
            # bbox center BELONGS: SVG (hair_cx, hair_cy) projects through
            # the silhouette's mapping (subtract viewBox center, flip Y)
            # to world (hair_cx - vcx, vcy - hair_cy).
            shift_x_mm = hair_cx_svg - view_cx_svg
            shift_y_mm = view_cy_svg - hair_cy_svg
            hair.location = (shift_x_mm, shift_y_mm, 0)
            print(f"[redaphid] hair placed at silhouette-frame center ({shift_x_mm:+.2f}, {shift_y_mm:+.2f}) mm")

    bpy.ops.object.transform_apply(location=True)

    # Lift to show face + 0.01 and extrude HAIR_HEIGHT
    bpy.ops.object.select_all(action='DESELECT')
    hair.select_set(True)
    bpy.context.view_layer.objects.active = hair

    # Move flat polygon to z = show_z + 0.01
    z_target = show_z + 0.01
    z_current = max((hair.matrix_world @ v.co).z for v in hair.data.vertices)
    hair.location.z += (z_target - z_current)
    bpy.ops.object.transform_apply(location=True)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.extrude_region_move(
        TRANSFORM_OT_translate={"value": (0, 0, HAIR_HEIGHT)})
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

    return hair


def apply_materials(bottom, top, hair, deco):
    def mat(name, base, rough, emit_color=None, emit_strength=0.0):
        m = bpy.data.materials.new(name=name)
        m.use_nodes = True
        bsdf = m.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = base
        bsdf.inputs["Roughness"].default_value = rough
        if emit_color is not None and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = emit_color
            bsdf.inputs["Emission Strength"].default_value = emit_strength
        return m

    body = mat("MAT_Body", (0.85, 0.78, 0.70, 1.0), 0.55)              # warm cream face
    hairmat = mat("MAT_Hair", (0.55, 0.20, 0.55, 1.0), 0.30,
                  emit_color=(0.9, 0.4, 0.95, 1.0), emit_strength=1.8) # neon magenta hair
    glow = mat("MAT_EyeGlow", (1.00, 0.45, 0.20, 1.0), 0.20,
               emit_color=(1.0, 0.55, 0.25, 1.0), emit_strength=4.0)   # warm orange eyes
    for obj, m in ((bottom, body), (top, body), (hair, hairmat), (deco, glow)):
        obj.data.materials.clear()
        obj.data.materials.append(m)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.shade_smooth()


# ── PIPELINE ────────────────────────────────────────────────────────


def main():
    print("[redaphid] === BUILD START ===")
    setup_theater_scene()

    # 1. Silhouette
    mesh = import_silhouette()
    extrude_to_thickness(mesh)
    drill_string_hole(mesh)

    # 2. Split halves
    bottom, top = split_halves(mesh)

    # 3. Verify peg candidates
    print("[redaphid] verifying peg positions:")
    pegs = verify_pegs(mesh, PEG_CANDIDATES)

    # 4. NFC pocket on bottom
    add_nfc_pocket(bottom)
    seal_nm(bottom)

    # 5. Pegs ↔ sockets (POST-split). Layout is configurable via PEGS_ON_BOTTOM.
    if PEGS_ON_BOTTOM:
        add_peg_sockets(top, pegs, mode='into_top')
        add_pegs(bottom, pegs, mode='from_bottom_up')
        seal_nm(top)
        seal_nm(bottom)
    else:
        add_peg_sockets(bottom, pegs, mode='into_bottom')
        add_pegs(top, pegs, mode='from_top_down')
        seal_nm(bottom)
        seal_nm(top)

    # 6. Hair (silhouette - face ellipse)
    hair = build_hair_decoration(top, mesh)

    # 7. Eyes from SVG → Decoration
    eyes_xyr = parse_eyes_from_svg(SVG_PATH)
    print(f"[redaphid] eyes (Blender mm): {eyes_xyr}")
    deco = build_eye_decoration(eyes_xyr, top)

    # 8. Materials
    apply_materials(bottom, top, hair, deco)

    # 9. Inspection layout: halves apart on X. Bottom stays in canonical
    # print orientation (silhouette face DOWN to plate, pegs UP).
    bottom.location.x -= 16.0
    for o in (top, hair, deco):
        o.location.x += 16.0

    # 9a. Tell the export skill not to apply the canonical 180° X flip on
    # Bottom — our centered-mesh pipeline already produces it in print
    # orientation directly.
    import json
    bpy.context.scene["nfc_export_flip_override"] = json.dumps({
        "Bottom":     0.0,
        "Top":        0.0,
        "Hair":       0.0,
        "Decoration": 0.0,
    })

    # 10. Save stage snapshot
    stages_dir = os.path.join(BEAD_DIR, "stages")
    os.makedirs(stages_dir, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(stages_dir, "01_built.blend"))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BEAD_DIR, "redaphid-portrait.blend"))

    print("[redaphid] === BUILD DONE ===")
    print(f"[redaphid] Bottom: {bottom.dimensions.x:.2f} x {bottom.dimensions.y:.2f} x {bottom.dimensions.z:.2f}")
    print(f"[redaphid] Top:    {top.dimensions.x:.2f} x {top.dimensions.y:.2f} x {top.dimensions.z:.2f}")
    print(f"[redaphid] Hair:   {hair.dimensions.x:.2f} x {hair.dimensions.y:.2f} x {hair.dimensions.z:.2f}")
    print(f"[redaphid] Decor:  {deco.dimensions.x:.2f} x {deco.dimensions.y:.2f} x {deco.dimensions.z:.2f}")


if __name__ == "__main__":
    main()
