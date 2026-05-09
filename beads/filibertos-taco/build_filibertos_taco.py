"""Filiberto's Taco NFC bead builder.

Two-half snap-fit charm with a multi-color raised relief of a cartoon taco
on the show face: red outline + yellow shell + green lettuce, each as a
separate decoration object so the multi-filament slicer can assign colors.

Run via Blender MCP `exec(open(r"<path>").read(), {"__name__": "__main__"})`,
or:
    blender --background --python build_filibertos_taco.py
"""
import bpy
import bmesh
import math
import os
from mathutils import Vector

# ── CONFIG ─────────────────────────────────────────────────────────────
REPO_DIR  = r"D:\Projects\nfc-bead"
BEAD_DIR  = os.path.join(REPO_DIR, "beads", "filibertos-taco")
SVG_BODY  = os.path.join(BEAD_DIR, "silhouette.svg")
PRINT_DIR = os.path.join(BEAD_DIR, "print")

# Decoration style:
#   'painted' — fill colored regions on the show face (4-layer cartoon look)
#   'neon'    — line-art strokes on a dark body (synthwave / stencil look)
# Switch with `bpy.context.scene["nfc_taco_style"] = "neon"` before exec, or
# the env var FILIBERTOS_TACO_STYLE.
STYLE = os.environ.get('FILIBERTOS_TACO_STYLE', 'painted')

# Painted-mode color palette (display only; slicer assigns filaments).
REGION_COLORS = {
    "shell_dark":     (0.93, 0.66, 0.05, 1),
    "shell_light":    (0.98, 0.82, 0.36, 1),
    "lettuce_dark":   (0.22, 0.36, 0.04, 1),
    "lettuce_light":  (0.37, 0.78, 0.13, 1),
    "outline":        (0.82, 0.13, 0.10, 1),
}

# Neon-mode color palette.
NEON_COLORS = {
    "silhouette":    (0.36, 0.84, 1.00, 1),    # primary light blue stroke
    "filling_line":  (0.36, 0.84, 1.00, 1),    # the lettuce-shell dividing line
}

def _camel(name): return ''.join(p.capitalize() for p in name.split('_'))

def _discover(prefix, color_map):
    import glob
    out = []
    for path in sorted(glob.glob(os.path.join(BEAD_DIR, f'{prefix}_*.svg'))):
        base = os.path.splitext(os.path.basename(path))[0]
        slug = base[len(prefix)+1:]
        col = color_map.get(slug, (0.7, 0.7, 0.7, 1))
        out.append((f"Decoration{_camel(slug)}", path, col))
    return out

if STYLE == 'neon':
    SVG_REGIONS = _discover('stroke', NEON_COLORS)
else:
    SVG_REGIONS = _discover('region', REGION_COLORS)

TARGET_WIDTH  = 25.0          # mm (taco silhouette ~25w x 17h after extraction)
THICKNESS     = 5.0           # mm total split into 2 x 2.5

HOLE_DIA      = 2.0           # mm
HOLE_Y        = 5.0           # mm — auto-fit found 5.02; rounded so cleanly inside silhouette
HOLE_Z_OFFSET = 1.25          # mm — shift hole entirely into Top half (recipe gotcha #23)

NFC_DIAMETER  = 10.5          # mm — recipe default (NTAG215)
NFC_DEPTH     = 0.8           # mm
NFC_POS       = (0.0, 0.5)    # mm — auto-fit: largest inscribed disk near center

PEG_DIAMETER  = 2.0           # mm
PEG_HEIGHT    = 1.5
PEG_CLEARANCE = 0.1
# auto-fit picked corners; pull inward a touch so peg perimeter sits comfortably
# inside the silhouette
PEGS = [
    ( 7.5, -6.0),     # right shell tip
    (-9.5,  0.0),     # left taco tip
    ( 7.5,  2.5),     # right upper, near filling
]

# Multi-color raised relief on Top show face
DECO_RELIEF = 0.4              # mm — extruded above show face
DECO_LIFT_EPS = 0.01           # mm — Z-fight buffer above show face

# ── BUILD HELPERS ──────────────────────────────────────────────────────
def clean_mesh(obj, threshold=0.005):
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=threshold)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

def repair_manifold(obj):
    """After EXACT boolean on thin extruded shapes, the EXACT solver
    sometimes leaves coplanar fragments and unfilled boundary loops.
    This pass dissolves zero-area features, deletes loose verts/edges,
    and fills any open boundary loops to recover a watertight mesh."""
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

def boolean_op(target, cutter, operation='DIFFERENCE', name='Bool'):
    bpy.context.view_layer.objects.active = target; target.select_set(True)
    b = target.modifiers.new(name=name, type='BOOLEAN')
    b.operation = operation; b.object = cutter; b.solver = 'EXACT'
    bpy.ops.object.modifier_apply(modifier=name)
    bpy.ops.object.select_all(action='DESELECT')
    cutter.select_set(True); bpy.ops.object.delete()

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

def import_svg_to_mesh(path, name, target_width_mm):
    bpy.ops.import_curve.svg(filepath=path)
    curves = [o for o in bpy.context.scene.objects if o.type == 'CURVE' and o.name not in _existing_objs]
    if not curves:
        return None
    bpy.ops.object.select_all(action='DESELECT')
    for o in curves: o.select_set(True)
    bpy.context.view_layer.objects.active = curves[0]
    if len(curves) > 1: bpy.ops.object.join()
    cv = bpy.context.active_object
    cv.data.dimensions = '2D'; cv.data.fill_mode = 'BOTH'; cv.data.resolution_u = 64
    bpy.ops.object.convert(target='MESH')
    m = bpy.context.active_object; m.name = name
    if target_width_mm:
        sf = (target_width_mm/1000.0) / m.dimensions.x
        m.scale = (sf, sf, sf); bpy.ops.object.transform_apply(scale=True)
        m.scale = (1000, 1000, 1000); bpy.ops.object.transform_apply(scale=True)
    return m

def assign_material(obj, name, color):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    b = mat.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = color
    b.inputs['Roughness'].default_value = 0.5
    obj.data.materials.clear(); obj.data.materials.append(mat)

# ── BUILD ──────────────────────────────────────────────────────────────
def main():
    global _existing_objs, SVG_REGIONS, STYLE
    # Allow scene custom-prop to override the env-var-derived STYLE.
    scene_style = bpy.context.scene.get('nfc_taco_style')
    if scene_style:
        STYLE = scene_style
    SVG_REGIONS = _discover('stroke', NEON_COLORS) if STYLE == 'neon' \
                  else _discover('region', REGION_COLORS)
    print("=" * 60)
    print(f"Filiberto's Taco NFC bead build  [STYLE={STYLE}]")
    print(f"  decorations: {[r[0] for r in SVG_REGIONS]}")
    print("=" * 60)

    # wipe scene meshes/curves and overlay objects
    try: bpy.ops.object.mode_set(mode='OBJECT')
    except Exception: pass
    for o in list(bpy.data.objects):
        if o.type in ('MESH', 'CURVE') or o.name.startswith(('_', 'DBG_', 'MA_')):
            bpy.data.objects.remove(o, do_unlink=True)

    # ── Step 1: Body silhouette (use the v2 cleaned outer) ─────────────
    _existing_objs = {o.name for o in bpy.data.objects}
    body = import_svg_to_mesh(SVG_BODY, 'TacoFlat', TARGET_WIDTH)
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
    dims = body.dimensions
    print(f"Extruded body: {dims.x:.2f} x {dims.y:.2f} x {dims.z:.2f} mm")

    # ── Step 2: String hole (full bead, before split) ──────────────────
    zs = [v.co.z for v in body.data.vertices]
    z_mid_live = (min(zs) + max(zs)) / 2.0
    z_hole = z_mid_live + HOLE_Z_OFFSET
    print(f"String hole d={HOLE_DIA} at Y={HOLE_Y} z={z_hole:.2f}")
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=48, radius=HOLE_DIA/2.0, depth=dims.x*4,
        location=(0, HOLE_Y, z_hole),
        rotation=(0, math.radians(90), 0),
    )
    boolean_op(body, bpy.context.active_object, 'DIFFERENCE', 'Hole')
    clean_mesh(body)
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    body.location = (0, 0, 0); body.name = 'FullBead'

    z_min = min(v.co.z for v in body.data.vertices)
    z_max = max(v.co.z for v in body.data.vertices)
    z_mid = (z_min + z_max) / 2.0
    print(f"Z: [{z_min:.2f},{z_max:.2f}] mid={z_mid:.2f}")

    # ── Step 3: Verify peg positions on full bead ──────────────────────
    print("\nPeg position check:")
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    nfc_r = NFC_DIAMETER/2.0; peg_r = PEG_DIAMETER/2.0
    perim = [(peg_r*math.cos(k*math.pi/4), peg_r*math.sin(k*math.pi/4)) for k in range(8)]
    bad = False
    for i,(px,py) in enumerate(PEGS):
        c = ev.ray_cast(Vector((px,py,z_max+5)), Vector((0,0,-1)))[0]
        miss = sum(1 for ox,oy in perim
                   if not ev.ray_cast(Vector((px+ox,py+oy,z_max+5)), Vector((0,0,-1)))[0])
        nfc_d = math.sqrt((px-NFC_POS[0])**2 + (py-NFC_POS[1])**2)
        clear = nfc_d - nfc_r - peg_r
        hd = abs(py - HOLE_Y)
        note = '' if miss == 0 else f", EDGES_CLIPPING={miss}/8"
        print(f"  Peg {i} ({px:+.1f},{py:+.1f}): solid={c}, NFC={clear:+.2f}, hole={hd:.2f}{note}")
        if not c or miss > 0 or clear < 0:
            bad = True
    if bad:
        print("  → fix PEGS positions; aborting")
        return

    # ── Step 4: Split into halves ──────────────────────────────────────
    box_size = 200
    print("\n--- Bottom Half ---")
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True); bpy.context.view_layer.objects.active = body
    bpy.ops.object.duplicate()
    bottom = bpy.context.active_object; bottom.name = 'Bottom'
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,z_min + (z_mid-z_min)/2.0))
    cu = bpy.context.active_object; cu.scale = (box_size, box_size, z_mid-z_min)
    bpy.ops.object.transform_apply(scale=True)
    boolean_op(bottom, cu, 'INTERSECT', 'Cut')
    clean_mesh(bottom, 0.01)
    print(f"Bottom non-manifold: {check_nonmanifold(bottom)}")

    print("\n--- Top Half ---")
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True); bpy.context.view_layer.objects.active = body
    bpy.ops.object.duplicate()
    top = bpy.context.active_object; top.name = 'Top'
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,z_mid + (z_max-z_mid)/2.0))
    cu = bpy.context.active_object; cu.scale = (box_size, box_size, z_max-z_mid)
    bpy.ops.object.transform_apply(scale=True)
    boolean_op(top, cu, 'INTERSECT', 'Cut')
    clean_mesh(top, 0.01)
    print(f"Top non-manifold: {check_nonmanifold(top)}")

    # ── Step 5: NFC pocket on Bottom ───────────────────────────────────
    b_z_max = max(v.co.z for v in bottom.data.vertices)
    cd = NFC_DEPTH*2 + 0.1
    print(f"\nNFC pocket {NFC_DIAMETER}@{NFC_POS}")
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64, radius=NFC_DIAMETER/2.0, depth=cd,
        location=(NFC_POS[0], NFC_POS[1], b_z_max - NFC_DEPTH + cd/2.0),
    )
    boolean_op(bottom, bpy.context.active_object, 'DIFFERENCE', 'NFC')
    clean_mesh(bottom)

    # ── Step 6: Peg holes on Top (post-split) ──────────────────────────
    t_z_min = min(v.co.z for v in top.data.vertices)
    hole_r = (PEG_DIAMETER + PEG_CLEARANCE*2) / 2.0
    print(f"\nPeg holes (r={hole_r:.2f}mm)")
    for i,(px,py) in enumerate(PEGS):
        cb = t_z_min - 1.0; ct = t_z_min + PEG_HEIGHT + 0.3
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=32, radius=hole_r, depth=ct-cb, location=(px,py,(cb+ct)/2.0),
        )
        boolean_op(top, bpy.context.active_object, 'DIFFERENCE', f'PH{i}')
    clean_mesh(top)
    print(f"Top after peg holes non-manifold: {check_nonmanifold(top)}")

    print("Verifying peg holes:")
    for i,(px,py) in enumerate(PEGS):
        verify_hole(top, Vector((px,py,t_z_min-2)), Vector((0,0,1)), f'Peg {i}')

    # ── Step 7: Pegs on Bottom (boolean UNION) ─────────────────────────
    b_z_max = max(v.co.z for v in bottom.data.vertices)
    print(f"\nPegs d={PEG_DIAMETER} h={PEG_HEIGHT}")
    for i,(px,py) in enumerate(PEGS):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=32, radius=PEG_DIAMETER/2.0, depth=PEG_HEIGHT,
            location=(px, py, b_z_max + PEG_HEIGHT/2.0),
        )
        boolean_op(bottom, bpy.context.active_object, 'UNION', f'Peg{i}')
    clean_mesh(bottom)
    print(f"Bottom after pegs non-manifold: {check_nonmanifold(bottom)}")

    # ── Step 8: Multi-color decoration on Top show face ────────────────
    t_z_max = max(v.co.z for v in top.data.vertices)
    deco_z_floor = t_z_max + DECO_LIFT_EPS
    print(f"\nDecorations at z={deco_z_floor:.3f}, relief={DECO_RELIEF}mm")

    decos = []
    for name, svg, color in SVG_REGIONS:
        if not os.path.exists(svg):
            print(f"  skip {name} (no svg)"); continue
        _existing_objs = {o.name for o in bpy.data.objects}
        d = import_svg_to_mesh(svg, name, TARGET_WIDTH)
        if d is None:
            print(f"  skip {name} (no curves imported)"); continue
        # the regions extracted are in the same scaled coordinate system as the
        # silhouette; bbox-center them at the silhouette's center
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
        d.location = (0, 0, deco_z_floor)
        # extrude to relief
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.005)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": (0, 0, DECO_RELIEF)})
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.005)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode='OBJECT')
        # crop the decoration to the Top silhouette so it never extends past the body edge
        # using a duplicate of Top extruded upward as the cropper
        bpy.ops.object.select_all(action='DESELECT')
        top.select_set(True); bpy.context.view_layer.objects.active = top
        bpy.ops.object.duplicate()
        cropper = bpy.context.active_object; cropper.name = '_Cropper'
        # raise the cropper's top so it intersects the decoration relief above the show face
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(cropper.data)
        for v in bm.verts:
            if v.co.z > t_z_min + 0.01:
                v.co.z = t_z_max + DECO_RELIEF + 0.5
        bmesh.update_edit_mesh(cropper.data)
        bpy.ops.object.mode_set(mode='OBJECT')
        boolean_op(d, cropper, 'INTERSECT', f'{name}Crop')
        clean_mesh(d)
        repair_manifold(d)        # fixes ring-shape boolean artifacts
        assign_material(d, f"{name}Mat", color)
        decos.append(d)
        # report manifold so the build log surfaces issues immediately
        nm = check_nonmanifold(d)
        print(f"  {name}: dims={d.dimensions.x:.2f}x{d.dimensions.y:.2f}x{d.dimensions.z:.2f}  non-manifold={nm}")

    # ── Step 9: Hide FullBead, materials, save ─────────────────────────
    body.hide_set(True); body.hide_render = True

    # body materials
    assign_material(bottom, 'BottomMat', (0.20, 0.55, 0.25, 1))
    assign_material(top, 'TopMat', (0.85, 0.55, 0.20, 1))

    # build orientation (NOT print orientation): leave Bottom and Top at origin
    # so architect mode sees them stacked. The bead-stl-export skill flips
    # Bottom 180° around X at export time.
    bottom.location = (0, 0, 0)
    top.location = (0, 0, 0)
    for d in decos:
        d.location = (d.location.x, d.location.y, deco_z_floor)

    # Recipe gotcha #16: this centered-mesh pipeline produces Bottom already
    # in print orientation (silhouette face DOWN, pegs UP). The default
    # bead-stl-export flip would un-orient it, putting pegs on the bed and
    # silhouette cantilevered above. Override per-charm so re-exports stay
    # printable.
    import json
    bpy.context.scene["nfc_export_flip_override"] = json.dumps({
        "Bottom": 0.0,
        "Top": 0.0,
        "DecorationYellow": 0.0,
        "DecorationGreen":  0.0,
        "DecorationRed":    0.0,
    })

    os.makedirs(PRINT_DIR, exist_ok=True)
    blend_path = os.path.join(PRINT_DIR, 'filibertos-taco_charm.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"\n.blend saved: {blend_path}")

    print("\n" + "=" * 60)
    print(f"Bottom:    {bottom.dimensions.x:.2f} x {bottom.dimensions.y:.2f} x {bottom.dimensions.z:.2f}")
    print(f"Top:       {top.dimensions.x:.2f} x {top.dimensions.y:.2f} x {top.dimensions.z:.2f}")
    for d in decos:
        print(f"{d.name:<10} {d.dimensions.x:.2f} x {d.dimensions.y:.2f} x {d.dimensions.z:.2f}")
    print("Build complete.")


if __name__ == '__main__':
    main()
