"""Fire-Heart NFC bead builder — THROUGH-COLOR multi-region charm.

A black heart with chunky red→orange flame wings. Unlike the relief-on-face
charms (filibertos-taco), the flames here are FULL-THICKNESS colored regions
of the bead body, not raised relief: each half is sliced by vertical prisms
into a black heart chunk + red flame chunk + orange flame-tip chunk that the
multi-filament slicer assembles into one solid part.

Pipeline:
  silhouette.svg (heart+flames) → extrude → string hole → split halves
  → NFC pocket (Bottom) → peg sockets (Top) → pegs (Bottom)
  → THROUGH-COLOR SPLIT each half by heart_prism / red_prism (regions.json)
  → 6 meshes: {Bottom,Top} x {Heart,Red,Orange}

Run via Blender MCP:
    exec(open(r"D:\\Projects\\nfc-bead\\beads\\fire-heart\\build_fire_heart.py").read(),
         {"__name__": "__main__"})
or headless:
    blender --background --python beads/fire-heart/build_fire_heart.py
"""
import bpy
import bmesh
import math
import os
import json
from mathutils import Vector

# ── CONFIG ─────────────────────────────────────────────────────────────
REPO_DIR  = r"D:\Projects\nfc-bead"
BEAD_DIR  = os.path.join(REPO_DIR, "beads", "fire-heart")
SVG_BODY  = os.path.join(BEAD_DIR, "silhouette.svg")
REGIONS   = os.path.join(BEAD_DIR, "regions.json")
PRINT_DIR = os.path.join(BEAD_DIR, "print")

TARGET_WIDTH  = 28.0          # mm — heart+flames overall (matches extraction)
THICKNESS     = 5.0           # mm — total, split 2.5 + 2.5

HOLE_DIA      = 2.0           # mm
HOLE_Y        = 0.5           # mm — through solid heart; 1.8mm wall up to cleft
HOLE_Z_OFFSET = 1.25          # mm — shift hole fully into Top half (gotcha #23)

NFC_DIAMETER  = 10.5          # mm — NTAG215
NFC_DEPTH     = 0.8           # mm
NFC_POS       = (0.0, -2.5)   # mm — top of pocket clears the heart cleft (+3.3)

PEG_DIAMETER  = 2.0           # mm
PEG_HEIGHT    = 1.5
PEG_CLEARANCE = 0.1
PEGS = [
    (-5.5,  3.0),    # left lobe
    ( 5.5,  3.0),    # right lobe
    ( 0.0, -10.0),   # lower point (triangulated, clears the big NFC pocket)
]

# Display colors (slicer assigns filaments; these are for the .blend preview).
COL_HEART  = (0.05, 0.05, 0.05, 1)
COL_RED    = (0.83, 0.07, 0.07, 1)
COL_ORANGE = (1.00, 0.45, 0.00, 1)

# Through-color prisms span well beyond the bead in Z so the vertical cut is
# unambiguous (covers body + pegs).
PRISM_Z_LO = -6.0
PRISM_Z_HI =  7.0

# The heart sits IN FRONT of the flames (as in the source art): on the show
# (Top) face the flame regions are recessed by this much, so the heart's
# lobes stand proud and read clearly instead of blending into the wings.
# Only the front is stepped — the back face is the print bed and must stay
# flat or the flame wings would print as cantilevers.
HEART_PROUD = 1.0             # mm — heart stands above flames on the show face

# ── HELPERS (mirrors build_charm.py.example / filibertos) ───────────────
def clean_mesh(obj, threshold=0.005):
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=threshold)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

def repair_manifold(obj):
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.dissolve_degenerate(threshold=0.001)
    bpy.ops.mesh.delete_loose()
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold(extend=False, use_wire=True, use_boundary=True,
                                     use_multi_face=False, use_non_contiguous=False, use_verts=False)
    bpy.ops.mesh.fill_holes(sides=8)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

def boolean_op(target, cutter, operation='DIFFERENCE', name='Bool', delete_cutter=True):
    bpy.context.view_layer.objects.active = target; target.select_set(True)
    b = target.modifiers.new(name=name, type='BOOLEAN')
    b.operation = operation; b.object = cutter; b.solver = 'EXACT'
    bpy.ops.object.modifier_apply(modifier=name)
    if delete_cutter:
        bpy.ops.object.select_all(action='DESELECT')
        cutter.select_set(True); bpy.ops.object.delete()

def drop_nm_slivers(obj):
    """Delete tiny non-manifold fragments left by EXACT booleans on the
    fragmented flame meshes (a sub-0.1mm chip at a red/orange boundary).
    Selects non-manifold edges, grows to their linked component, and removes
    it — only ever catches small disconnected slivers, not the body."""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='VERT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold()
    bpy.ops.mesh.select_linked(delimit=set())
    bpy.ops.mesh.delete(type='VERT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

def check_nonmanifold(obj):
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold()
    bm = bmesh.from_edit_mesh(obj.data)
    nm = sum(1 for e in bm.edges if e.select)
    bpy.ops.object.mode_set(mode='OBJECT')
    return nm

def verify_hole(obj, origin, direction, label=''):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    r = ev.ray_cast(origin, direction)
    print(f"  {label}: {'OPEN' if not r[0] else f'hit z={r[1].z:.3f}'}")
    return not r[0]

def assign_material(obj, name, color):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    b = mat.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = color
    b.inputs['Roughness'].default_value = 0.5
    obj.data.materials.clear(); obj.data.materials.append(mat)

def polygons_to_mesh(polygons, name, z=0.0):
    """Flat mesh from [{'outer':[(x,y)...], 'holes':[[(x,y)...]]}]."""
    if not polygons:
        return None
    me = bpy.data.meshes.new(name + 'Mesh'); bm = bmesh.new()
    for poly in polygons:
        outer = poly['outer'] if isinstance(poly, dict) else poly
        holes = poly.get('holes', []) if isinstance(poly, dict) else []
        if len(outer) < 3: continue
        if not holes:
            try:
                vs = [bm.verts.new((float(x), float(y), float(z))) for x, y in outer]
                bm.faces.new(vs)
            except ValueError:
                pass
            continue
        loops = [outer] + holes; edges = []
        for loop in loops:
            vs = [bm.verts.new((float(x), float(y), float(z))) for x, y in loop]
            for i in range(len(vs)):
                try: edges.append(bm.edges.new((vs[i], vs[(i+1) % len(vs)])))
                except ValueError: pass
        if edges:
            try: bmesh.ops.triangle_fill(bm, edges=edges, use_beauty=True)
            except Exception as ex: print(f"  triangle_fill failed {name}: {ex}")
    bm.normal_update(); bm.to_mesh(me); bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    return obj

def build_prism(polygons, name, z_lo, z_hi):
    """Flat region polygons → tall vertical prism for color-split booleans."""
    m = polygons_to_mesh(polygons, name, z=z_lo)
    if m is None: return None
    bpy.ops.object.select_all(action='DESELECT')
    m.select_set(True); bpy.context.view_layer.objects.active = m
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": (0, 0, z_hi - z_lo)})
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    return m

def import_svg_to_mesh(path, name, target_width_mm):
    pre = {o.name for o in bpy.context.scene.objects}
    bpy.ops.import_curve.svg(filepath=path)
    curves = [o for o in bpy.context.scene.objects if o.type == 'CURVE' and o.name not in pre]
    if not curves: return None
    bpy.ops.object.select_all(action='DESELECT')
    for o in curves: o.select_set(True)
    bpy.context.view_layer.objects.active = curves[0]
    if len(curves) > 1: bpy.ops.object.join()
    cv = bpy.context.active_object
    cv.data.dimensions = '2D'; cv.data.fill_mode = 'BOTH'; cv.data.resolution_u = 64
    bpy.ops.object.convert(target='MESH')
    m = bpy.context.active_object; m.name = name
    sf = (target_width_mm / 1000.0) / m.dimensions.x
    m.scale = (sf, sf, sf); bpy.ops.object.transform_apply(scale=True)
    m.scale = (1000, 1000, 1000); bpy.ops.object.transform_apply(scale=True)
    return m

def dup(obj, name):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.duplicate()
    d = bpy.context.active_object; d.name = name
    return d

# ── BUILD ──────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("Fire-Heart NFC bead — through-color build")
    print("=" * 60)

    region_data = json.load(open(REGIONS, encoding='utf-8'))
    heart_polys = region_data['regions']['heart']['polygons']
    red_polys   = region_data['regions']['flames_red']['polygons']

    # wipe scene meshes/curves/helpers
    try: bpy.ops.object.mode_set(mode='OBJECT')
    except Exception: pass
    for o in list(bpy.data.objects):
        if o.type in ('MESH', 'CURVE') or o.name.startswith(('_', 'DBG_', 'MA_')):
            bpy.data.objects.remove(o, do_unlink=True)

    # ── Step 1: body silhouette ────────────────────────────────────────
    body = import_svg_to_mesh(SVG_BODY, 'HeartFlat', TARGET_WIDTH)
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    body.location = (0, 0, 0)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": (0, 0, THICKNESS)})
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    body.location = (0, 0, 0)
    d = body.dimensions
    print(f"Extruded body: {d.x:.2f} x {d.y:.2f} x {d.z:.2f} mm")

    # ── Step 2: string hole (full bead, before split) ──────────────────
    zs = [v.co.z for v in body.data.vertices]
    z_mid_live = (min(zs) + max(zs)) / 2.0
    z_hole = z_mid_live + HOLE_Z_OFFSET
    print(f"String hole d={HOLE_DIA} Y={HOLE_Y} z={z_hole:.2f}")
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=48, radius=HOLE_DIA/2.0, depth=d.x*4,
        location=(0, HOLE_Y, z_hole), rotation=(0, math.radians(90), 0))
    boolean_op(body, bpy.context.active_object, 'DIFFERENCE', 'Hole')
    clean_mesh(body)
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    body.location = (0, 0, 0); body.name = 'FullBead'

    z_min = min(v.co.z for v in body.data.vertices)
    z_max = max(v.co.z for v in body.data.vertices)
    z_mid = (z_min + z_max) / 2.0
    print(f"Z: [{z_min:.2f},{z_max:.2f}] mid={z_mid:.2f}")

    # ── Step 3: verify peg + NFC positions on full bead ────────────────
    print("\nPeg + NFC perimeter check:")
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    nfc_r = NFC_DIAMETER/2.0; peg_r = PEG_DIAMETER/2.0
    perim = [(peg_r*math.cos(k*math.pi/4), peg_r*math.sin(k*math.pi/4)) for k in range(8)]
    bad = False
    nfc_perim = [(nfc_r*math.cos(k*math.pi/8), nfc_r*math.sin(k*math.pi/8)) for k in range(16)]
    nfc_misses = sum(1 for ox, oy in nfc_perim
                     if not ev.ray_cast(Vector((NFC_POS[0]+ox, NFC_POS[1]+oy, z_max+5)),
                                        Vector((0, 0, -1)))[0])
    print(f"  NFC ({NFC_POS[0]:+.1f},{NFC_POS[1]:+.1f}) r={nfc_r}: inside = {16-nfc_misses}/16"
          + (f"  CLIPPING {nfc_misses}/16!" if nfc_misses else ""))
    if nfc_misses: bad = True
    for i,(px,py) in enumerate(PEGS):
        c = ev.ray_cast(Vector((px,py,z_max+5)), Vector((0,0,-1)))[0]
        miss = sum(1 for ox,oy in perim
                   if not ev.ray_cast(Vector((px+ox,py+oy,z_max+5)), Vector((0,0,-1)))[0])
        nfc_d = math.hypot(px-NFC_POS[0], py-NFC_POS[1]); clear = nfc_d - nfc_r - peg_r
        hd = abs(py - HOLE_Y)
        note = '' if miss == 0 else f", EDGES_CLIPPING={miss}/8"
        print(f"  Peg {i} ({px:+.1f},{py:+.1f}): solid={c}, NFC={clear:+.2f}, hole={hd:.2f}{note}")
        if not c or miss > 0 or clear < 0: bad = True
    if bad:
        print("  → fix PEGS/NFC positions; aborting"); return

    # ── Step 4: split into halves ──────────────────────────────────────
    box = 200
    print("\n--- Bottom Half ---")
    bottom = dup(body, 'Bottom')
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,z_min + (z_mid-z_min)/2.0))
    cu = bpy.context.active_object; cu.scale = (box, box, z_mid-z_min)
    bpy.ops.object.transform_apply(scale=True)
    boolean_op(bottom, cu, 'INTERSECT', 'Cut'); clean_mesh(bottom, 0.01)
    print(f"Bottom non-manifold: {check_nonmanifold(bottom)}")

    print("\n--- Top Half ---")
    top = dup(body, 'Top')
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,z_mid + (z_max-z_mid)/2.0))
    cu = bpy.context.active_object; cu.scale = (box, box, z_max-z_mid)
    bpy.ops.object.transform_apply(scale=True)
    boolean_op(top, cu, 'INTERSECT', 'Cut'); clean_mesh(top, 0.01)
    print(f"Top non-manifold: {check_nonmanifold(top)}")

    # ── Step 5: NFC pocket on Bottom ───────────────────────────────────
    b_z_max = max(v.co.z for v in bottom.data.vertices)
    cd = NFC_DEPTH*2 + 0.1
    print(f"\nNFC pocket {NFC_DIAMETER}@{NFC_POS}")
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64, radius=NFC_DIAMETER/2.0, depth=cd,
        location=(NFC_POS[0], NFC_POS[1], b_z_max - NFC_DEPTH + cd/2.0))
    boolean_op(bottom, bpy.context.active_object, 'DIFFERENCE', 'NFC'); clean_mesh(bottom)

    # ── Step 6: peg holes on Top (post-split) ──────────────────────────
    t_z_min = min(v.co.z for v in top.data.vertices)
    hole_r = (PEG_DIAMETER + PEG_CLEARANCE*2) / 2.0
    print(f"\nPeg sockets (r={hole_r:.2f})")
    for i,(px,py) in enumerate(PEGS):
        cb = t_z_min - 1.0; ct = t_z_min + PEG_HEIGHT + 0.3
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=hole_r, depth=ct-cb,
                                            location=(px,py,(cb+ct)/2.0))
        boolean_op(top, bpy.context.active_object, 'DIFFERENCE', f'PH{i}')
    clean_mesh(top)
    print(f"Top after sockets non-manifold: {check_nonmanifold(top)}")
    print("Verifying sockets:")
    for i,(px,py) in enumerate(PEGS):
        verify_hole(top, Vector((px,py,t_z_min-2)), Vector((0,0,1)), f'Peg {i}')

    # ── Step 7: pegs on Bottom (UNION) ─────────────────────────────────
    b_z_max = max(v.co.z for v in bottom.data.vertices)
    print(f"\nPegs d={PEG_DIAMETER} h={PEG_HEIGHT}")
    for i,(px,py) in enumerate(PEGS):
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=PEG_DIAMETER/2.0,
                                            depth=PEG_HEIGHT, location=(px,py,b_z_max+PEG_HEIGHT/2.0))
        boolean_op(bottom, bpy.context.active_object, 'UNION', f'Peg{i}')
    clean_mesh(bottom)
    print(f"Bottom after pegs non-manifold: {check_nonmanifold(bottom)}")

    # ── Step 8: verify string hole open (side raycast) ─────────────────
    print("\nString hole (side raycast through Top):")
    verify_hole(top, Vector((-TARGET_WIDTH, HOLE_Y, z_hole)), Vector((1,0,0)), 'String')

    # ── Step 9: THROUGH-COLOR SPLIT ────────────────────────────────────
    # Each half → Heart (∩ heart_prism) + flames (− heart_prism), then
    # flames → Red (∩ red_prism) + Orange (remainder). Complement-based so
    # there are no seam gaps between colors.
    print("\n--- Through-color split ---")
    final = []
    for half, hname in ((bottom, 'Bottom'), (top, 'Top')):
        heart_prism = build_prism(heart_polys, f'_{hname}HeartPrism', PRISM_Z_LO, PRISM_Z_HI)
        red_prism   = build_prism(red_polys,   f'_{hname}RedPrism',   PRISM_Z_LO, PRISM_Z_HI)

        heart_part = dup(half, f'{hname}Heart')
        boolean_op(heart_part, heart_prism, 'INTERSECT', 'HeartCut', delete_cutter=False)
        clean_mesh(heart_part); repair_manifold(heart_part)

        flames_part = dup(half, f'{hname}Flames')
        boolean_op(flames_part, heart_prism, 'DIFFERENCE', 'FlameCut', delete_cutter=True)
        clean_mesh(flames_part)

        # Recess the whole connected flame body on the show (Top) face so the
        # heart stands proud → its lobes read clearly above the wings (source
        # art layering). Done BEFORE the red/orange split so the recess cut
        # runs once on a single connected mesh (the fragmented sub-meshes
        # left non-manifold slivers when cut individually).
        if hname == 'Top':
            show_z = max(v.co.z for v in heart_part.data.vertices)
            z_floor = show_z - HEART_PROUD
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z_floor + 50))
            cu = bpy.context.active_object; cu.scale = (400, 400, 100)
            bpy.ops.object.transform_apply(scale=True)
            boolean_op(flames_part, cu, 'DIFFERENCE', 'Recess')
            clean_mesh(flames_part); repair_manifold(flames_part)
            print(f"  recessed Top flames by {HEART_PROUD}mm (heart proud at z={show_z:.2f})")

        red_part = dup(flames_part, f'{hname}Red')
        boolean_op(red_part, red_prism, 'INTERSECT', 'RedCut', delete_cutter=False)
        clean_mesh(red_part); repair_manifold(red_part); drop_nm_slivers(red_part)

        orange_part = dup(flames_part, f'{hname}Orange')
        boolean_op(orange_part, red_prism, 'DIFFERENCE', 'OrangeCut', delete_cutter=True)
        clean_mesh(orange_part); repair_manifold(orange_part); drop_nm_slivers(orange_part)

        bpy.data.objects.remove(flames_part, do_unlink=True)

        assign_material(heart_part,  f'{hname}HeartMat',  COL_HEART)
        assign_material(red_part,    f'{hname}RedMat',    COL_RED)
        assign_material(orange_part, f'{hname}OrangeMat', COL_ORANGE)
        for p in (heart_part, red_part, orange_part):
            nm = check_nonmanifold(p)
            print(f"  {p.name:14} dims={p.dimensions.x:.1f}x{p.dimensions.y:.1f}x{p.dimensions.z:.1f}  nm={nm}")
            final.append(p)

    # remove the now-consumed full halves + full bead
    for o in (bottom, top, body):
        if o.name in bpy.data.objects:
            bpy.data.objects.remove(o, do_unlink=True)

    # ── Step 10: orientation override + save ───────────────────────────
    # Centered-mesh build → Bottom* already silhouette-DOWN / pegs-UP (print
    # orientation). Don't let bead-stl-export flip them (gotcha #16).
    bpy.context.scene["nfc_export_flip_override"] = json.dumps(
        {p.name: 0.0 for p in final})

    os.makedirs(PRINT_DIR, exist_ok=True)
    blend_path = os.path.join(PRINT_DIR, 'fire-heart_charm.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"\n.blend saved: {blend_path}")
    print("Build complete:", [p.name for p in final])


if __name__ == '__main__':
    main()
