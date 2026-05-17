"""Black-rainbow NFC bead builder.

Two-half snap-fit charm with a multi-color FLUSH inlay on the show face:
3 rainbow bands (red/yellow/blue) + black thorn wings, each as a separate
decoration object so a multi-filament slicer can assign filaments.

Pipeline source: regions.json (polygon manifest in shared mm coords, written
by extract_regions.py from simplified_rainbow_1024.png). No SVG round-trip.

Layout decisions (see beads/black-rainbow/README.md for the why):
  - Silhouette is the FILLED convex-hull-bridged shape (~25 × 16 mm) — the
    under-arch is solid back-body that hosts NFC + pegs.
  - 2 pegs in the under-arch corners (no clear spot for a 3rd peg that
    clears NFC + decorations + string hole — the bead is too short
    vertically for a triangulated triple).
  - String hole at y=+5.5 in the rainbow band area: hole tunnels through
    Bottom only (HOLE_Z_OFFSET=-1.25) so Top's inner face is solid at
    the hole's Y — keeps the multi-color decoration sockets unbroken.

Run via Blender MCP:
    exec(open(r"D:\\Projects\\nfc-bead\\beads\\black-rainbow\\build_black_rainbow.py").read(),
         {"__name__": "__main__"})

Or headless:
    blender --background --python beads/black-rainbow/build_black_rainbow.py
"""
import bpy
import bmesh
import math
import os
import json
from mathutils import Vector

# ── CONFIG ─────────────────────────────────────────────────────────────
REPO_DIR  = r"D:\Projects\nfc-bead"
BEAD_DIR  = os.path.join(REPO_DIR, "beads", "black-rainbow")
REGIONS_JSON = os.path.join(BEAD_DIR, "regions.json")
PRINT_DIR = os.path.join(BEAD_DIR, "print")

# Visual palette (display only; slicer assigns filaments).
DECO_COLORS = {
    "rainbow_outer": (0.78, 0.09, 0.09, 1),  # red
    "rainbow_mid":   (0.90, 0.78, 0.12, 1),  # yellow
    "rainbow_inner": (0.11, 0.37, 0.72, 1),  # blue
    "wings":         (0.05, 0.05, 0.05, 1),  # black
}

# Decoration stack order: lowest first. Overlap-resolution subtracts later
# entries from earlier ones, so the LAST entry stays intact on top.
# Order: rainbow bands (no mutual overlap — they tile cleanly) then wings
# on top so wings cover the rainbow at the wing/arch overlap.
DECO_ORDER = ["rainbow_outer", "rainbow_mid", "rainbow_inner", "wings"]

TARGET_WIDTH  = 25.0          # mm (silhouette is ~25 × 16.19 from extraction)
THICKNESS     = 5.0           # mm total, split into 2 × 2.5

HOLE_DIA      = 2.0           # mm
HOLE_Y        = 5.5           # mm — inside rainbow_mid band area; ONLY 1.6mm of
                              # silhouette material above (recipe rule asks
                              # ≥2.5mm). The bead is too short vertically for
                              # a structurally ideal placement; this is the
                              # compromise. README captures the rationale.
HOLE_Z_OFFSET = -1.25         # mm — push hole entirely into Bottom half. Top's
                              # inner face stays solid at y=HOLE_Y so the
                              # rainbow decoration sockets aren't interrupted
                              # by an open half-tube. Also gives the cleaner
                              # first-layer adhesion of gotcha #23.

NFC_DIAMETER  = 10.5          # mm — NTAG215 sticker
NFC_DEPTH     = 0.8           # mm
NFC_POS       = (0.0, -2.7)   # mm — slightly below silhouette center so the
                              # 5.25mm radius clears below into the convex-
                              # hull-bridged under-arch. Verified: bottom
                              # perimeter at y=-7.95, silhouette y_min=-8.11
                              # (0.16mm margin).

PEG_DIAMETER  = 2.6           # mm — per recipe gotcha update (Centauri Carbon 2
                              # needs 2.6 for snap-fit; 2.0 too narrow)
PEG_HEIGHT    = 1.5
PEG_CLEARANCE = 0.05          # mm radial

# Only 2 pegs — the wide/short geometry has no spot for a triangulated 3rd
# that clears NFC (10.5mm dia centered y=-2.7), all 4 decoration sockets
# (which cover essentially all of the rainbow region above y=-2.5), and
# the string hole at y=+5.5. See README for the search results.
PEGS = [
    (-7.0, -5.0),    # under-arch left
    ( 7.0, -5.0),    # under-arch right
]

# FLUSH inlay (gotcha #29): decorations sit IN sockets carved out of Top so
# the show face is smooth. All decos share the same Z slab; overlap is
# resolved by subtracting higher-rank from lower-rank.
DECO_RELIEF = 0.4              # mm — depth of inlay socket
DECO_LIFT_EPS = 0.0
DECO_LAYER_STEP = 0.0          # mm — flush


# ── BUILD HELPERS ──────────────────────────────────────────────────────
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


def boolean_op(target, cutter, operation='DIFFERENCE', name='Bool'):
    bpy.context.view_layer.objects.active = target; target.select_set(True)
    b = target.modifiers.new(name=name, type='BOOLEAN')
    b.operation = operation; b.object = cutter; b.solver = 'EXACT'
    bpy.ops.object.modifier_apply(modifier=name)
    bpy.ops.object.select_all(action='DESELECT')
    cutter.select_set(True); bpy.ops.object.delete()


def boolean_diff_keep_cutter(target, cutter, name='DiffKeep'):
    cut_copy = cutter.copy()
    cut_copy.data = cutter.data.copy()
    bpy.context.collection.objects.link(cut_copy)
    boolean_op(target, cut_copy, 'DIFFERENCE', name)


def check_nonmanifold(obj):
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold()
    bm = bmesh.from_edit_mesh(obj.data)
    nm = sum(1 for e in bm.edges if e.select)
    bpy.ops.object.mode_set(mode='OBJECT')
    return nm


def polygons_to_mesh(polygons, name, z=0.0):
    """Build flat Blender mesh from polygons in shared mm coords. Each polygon
    is a dict {'outer': [(x,y),...], 'holes': [...]}. Simple polygons get a
    direct n-gon; ring polygons get bridge_loops between outer + inner."""
    if not polygons:
        return None
    me = bpy.data.meshes.new(name + 'Mesh')
    bm = bmesh.new()
    for poly in polygons:
        outer = poly.get('outer') if isinstance(poly, dict) else poly
        holes = poly.get('holes', []) if isinstance(poly, dict) else []
        if not outer or len(outer) < 3:
            continue
        if not holes:
            try:
                verts = [bm.verts.new((float(x), float(y), float(z))) for x, y in outer]
                bm.faces.new(verts)
            except ValueError:
                pass
            continue
        if len(holes) == 1:
            outer_v = [bm.verts.new((float(x), float(y), float(z))) for x, y in outer]
            inner_v = [bm.verts.new((float(x), float(y), float(z))) for x, y in holes[0]]
            outer_e, inner_e = [], []
            for i in range(len(outer_v)):
                try: outer_e.append(bm.edges.new((outer_v[i], outer_v[(i+1) % len(outer_v)])))
                except ValueError: pass
            for i in range(len(inner_v)):
                try: inner_e.append(bm.edges.new((inner_v[i], inner_v[(i+1) % len(inner_v)])))
                except ValueError: pass
            try: bmesh.ops.bridge_loops(bm, edges=outer_e + inner_e)
            except Exception:
                try: bmesh.ops.triangle_fill(bm, edges=outer_e + inner_e, use_beauty=True)
                except Exception: pass
            continue
        loop_edges = []
        for loop in [outer] + holes:
            verts = [bm.verts.new((float(x), float(y), float(z))) for x, y in loop]
            for i in range(len(verts)):
                try: loop_edges.append(bm.edges.new((verts[i], verts[(i+1) % len(verts)])))
                except ValueError: pass
        if loop_edges:
            try: bmesh.ops.triangle_fill(bm, edges=loop_edges, use_beauty=True)
            except Exception: pass
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    return obj


def build_silhouette_cropper(silhouette_polygons, z_lo, z_hi):
    """Build a clean tall extrusion of the silhouette outline (no holes /
    NFC / pegs cut) for the decoration INTERSECT cropper. Gotcha #26:
    NEVER duplicate Top — Top has peg sockets that would punch through
    the decoration. Build from a fresh silhouette polygon instead."""
    m = polygons_to_mesh(silhouette_polygons, '_SilhCropFlat', z=z_lo)
    bpy.ops.object.select_all(action='DESELECT')
    m.select_set(True); bpy.context.view_layer.objects.active = m
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.mesh.extrude_region_move(
        TRANSFORM_OT_translate={"value": (0, 0, z_hi - z_lo)})
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    m.name = '_Cropper'
    return m


def assign_material(obj, name, color):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    b = mat.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = color
    b.inputs['Roughness'].default_value = 0.5
    obj.data.materials.clear(); obj.data.materials.append(mat)


# ── BUILD ──────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("Black-Rainbow NFC bead build")
    print("=" * 60)

    # Wipe scene of any leftover meshes/curves/overlays
    try: bpy.ops.object.mode_set(mode='OBJECT')
    except Exception: pass
    for o in list(bpy.data.objects):
        if o.type in ('MESH', 'CURVE') or o.name.startswith(('_', 'DBG_', 'MA_')):
            bpy.data.objects.remove(o, do_unlink=True)

    # Load polygon manifest
    if not os.path.exists(REGIONS_JSON):
        raise SystemExit(f"Missing regions.json at {REGIONS_JSON} — run extract_regions.py first")
    manifest = json.load(open(REGIONS_JSON, encoding='utf-8'))
    silh_polys = manifest['regions']['outer']['polygons']
    print(f"  loaded regions.json: {len(manifest['regions'])} regions, "
          f"{sum(len(r['polygons']) for r in manifest['regions'].values())} polygons")

    # ── Step 1: Body silhouette from polygon → extrude to THICKNESS ────
    body = polygons_to_mesh(silh_polys, 'BlackRainbowFlat', z=0.0)
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True); bpy.context.view_layer.objects.active = body
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.mesh.extrude_region_move(
        TRANSFORM_OT_translate={"value": (0, 0, THICKNESS)})
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    body.location = (0, 0, 0)
    dims = body.dimensions
    print(f"Extruded body: {dims.x:.2f} × {dims.y:.2f} × {dims.z:.2f} mm")

    # ── Step 2: String hole (full bead, before split) ──────────────────
    zs = [v.co.z for v in body.data.vertices]
    z_mid_live = (min(zs) + max(zs)) / 2.0
    z_hole = z_mid_live + HOLE_Z_OFFSET
    print(f"String hole d={HOLE_DIA} at Y={HOLE_Y}, z={z_hole:.2f} "
          f"(offset={HOLE_Z_OFFSET:+.2f})")
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=48, radius=HOLE_DIA/2.0, depth=dims.x*4,
        location=(0, HOLE_Y, z_hole),
        rotation=(0, math.radians(90), 0),
    )
    boolean_op(body, bpy.context.active_object, 'DIFFERENCE', 'Hole')
    clean_mesh(body)
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    body.location = (0, 0, 0)
    body.name = 'FullBead'

    z_min = min(v.co.z for v in body.data.vertices)
    z_max = max(v.co.z for v in body.data.vertices)
    z_mid = (z_min + z_max) / 2.0
    print(f"Z: [{z_min:.2f}, {z_max:.2f}] mid={z_mid:.2f}")

    # ── Step 3: Verify peg + NFC perimeters ────────────────────────────
    print("\nPeg + NFC perimeter check:")
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    nfc_r = NFC_DIAMETER/2.0; peg_r = PEG_DIAMETER/2.0
    perim = [(peg_r*math.cos(k*math.pi/4), peg_r*math.sin(k*math.pi/4)) for k in range(8)]
    bad = False

    nfc_perim = [(nfc_r*math.cos(k*math.pi/8), nfc_r*math.sin(k*math.pi/8))
                 for k in range(16)]
    nfc_misses = sum(1 for ox, oy in nfc_perim
                     if not ev.ray_cast(Vector((NFC_POS[0]+ox, NFC_POS[1]+oy, z_max+5)),
                                        Vector((0, 0, -1)))[0])
    print(f"  NFC ({NFC_POS[0]:+.1f},{NFC_POS[1]:+.1f}) r={nfc_r}: "
          f"perimeter inside silhouette = {16-nfc_misses}/16"
          + (f"  CLIPPING {nfc_misses}/16!" if nfc_misses else ""))
    if nfc_misses > 0:
        bad = True
        print(f"    → adjust NFC_POS or shrink NFC_DIAMETER")

    for i, (px, py) in enumerate(PEGS):
        c = ev.ray_cast(Vector((px, py, z_max+5)), Vector((0, 0, -1)))[0]
        miss = sum(1 for ox, oy in perim
                   if not ev.ray_cast(Vector((px+ox, py+oy, z_max+5)), Vector((0, 0, -1)))[0])
        nfc_d = math.sqrt((px-NFC_POS[0])**2 + (py-NFC_POS[1])**2)
        clear = nfc_d - nfc_r - peg_r
        hd = abs(py - HOLE_Y)
        note = '' if miss == 0 else f", EDGES_CLIPPING={miss}/8"
        print(f"  Peg {i} ({px:+.1f},{py:+.1f}): solid={c}, "
              f"NFC_clr={clear:+.2f}, hole_dy={hd:.2f}{note}")
        if not c or miss > 0 or clear < 0:
            bad = True

    if bad:
        print("  → fix positions; aborting")
        return

    # ── Step 4: Split into halves ──────────────────────────────────────
    box_size = 200
    print("\n--- Bottom Half ---")
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True); bpy.context.view_layer.objects.active = body
    bpy.ops.object.duplicate()
    bottom = bpy.context.active_object; bottom.name = 'Bottom'
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z_min + (z_mid-z_min)/2.0))
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
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z_mid + (z_max-z_mid)/2.0))
    cu = bpy.context.active_object; cu.scale = (box_size, box_size, z_max-z_mid)
    bpy.ops.object.transform_apply(scale=True)
    boolean_op(top, cu, 'INTERSECT', 'Cut')
    clean_mesh(top, 0.01)
    print(f"Top non-manifold: {check_nonmanifold(top)}")

    # ── Step 5: NFC pocket on Bottom ───────────────────────────────────
    b_z_max = max(v.co.z for v in bottom.data.vertices)
    cd = NFC_DEPTH*2 + 0.1
    print(f"\nNFC pocket d={NFC_DIAMETER} @ {NFC_POS}")
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64, radius=NFC_DIAMETER/2.0, depth=cd,
        location=(NFC_POS[0], NFC_POS[1], b_z_max - NFC_DEPTH + cd/2.0),
    )
    boolean_op(bottom, bpy.context.active_object, 'DIFFERENCE', 'NFC')
    clean_mesh(bottom)

    # ── Step 6: Peg holes on Top (post-split) ──────────────────────────
    t_z_min = min(v.co.z for v in top.data.vertices)
    hole_r = (PEG_DIAMETER + PEG_CLEARANCE*2) / 2.0
    print(f"\nPeg holes r={hole_r:.2f}mm")
    for i, (px, py) in enumerate(PEGS):
        cb = t_z_min - 1.0; ct = t_z_min + PEG_HEIGHT + 0.3
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=32, radius=hole_r, depth=ct-cb, location=(px, py, (cb+ct)/2.0),
        )
        boolean_op(top, bpy.context.active_object, 'DIFFERENCE', f'PH{i}')
    clean_mesh(top)
    print(f"Top after peg holes non-manifold: {check_nonmanifold(top)}")

    # ── Step 7: Pegs on Bottom (boolean UNION) ─────────────────────────
    b_z_max = max(v.co.z for v in bottom.data.vertices)
    print(f"\nPegs d={PEG_DIAMETER} h={PEG_HEIGHT}")
    for i, (px, py) in enumerate(PEGS):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=32, radius=PEG_DIAMETER/2.0, depth=PEG_HEIGHT,
            location=(px, py, b_z_max + PEG_HEIGHT/2.0),
        )
        boolean_op(bottom, bpy.context.active_object, 'UNION', f'Peg{i}')
    clean_mesh(bottom)
    print(f"Bottom after pegs non-manifold: {check_nonmanifold(bottom)}")

    # ── Step 8: Multi-color FLUSH decoration on Top show face ──────────
    t_z_max = max(v.co.z for v in top.data.vertices)
    deco_z_floor = t_z_max - DECO_RELIEF
    print(f"\nDecorations FLUSH at z=[{deco_z_floor:.3f}, {t_z_max:.3f}]  "
          f"relief={DECO_RELIEF}mm")

    decos = []
    for layer_idx, slug in enumerate(DECO_ORDER):
        region = manifest['regions'].get(slug)
        if not region or not region['polygons']:
            print(f"  skip {slug} (not in regions.json)"); continue
        camel = ''.join(p.capitalize() for p in slug.split('_'))
        d_name = f"Decoration{camel}"
        color = DECO_COLORS.get(slug, (0.7, 0.7, 0.7, 1))
        d = polygons_to_mesh(region['polygons'], d_name,
                             z=deco_z_floor + layer_idx * DECO_LAYER_STEP)
        if d is None:
            print(f"  skip {slug} (polygons→mesh empty)"); continue
        bpy.ops.object.select_all(action='DESELECT')
        d.select_set(True); bpy.context.view_layer.objects.active = d
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.005)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.mesh.extrude_region_move(
            TRANSFORM_OT_translate={"value": (0, 0, DECO_RELIEF)})
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.005)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode='OBJECT')

        # Crop to silhouette outer boundary (gotcha #26)
        cropper = build_silhouette_cropper(silh_polys,
                                           z_lo=t_z_min,
                                           z_hi=t_z_max + DECO_RELIEF + 0.5)
        boolean_op(d, cropper, 'INTERSECT', f'{d_name}Crop')
        clean_mesh(d); repair_manifold(d)
        assign_material(d, f"{d_name}Mat", color)
        decos.append(d)
        nm = check_nonmanifold(d)
        print(f"  {d_name}: {d.dimensions.x:.2f}×{d.dimensions.y:.2f}×{d.dimensions.z:.2f}  nm={nm}")

    # ── Step 8.5: FLUSH inlay overlap-resolution + Top pocket carving ──
    # Painter's order: index 0 = lowest layer, index -1 = topmost. With
    # FLUSH each deco occupies the same Z slab — overlap is resolved by
    # subtracting every higher-rank deco from each lower-rank one, then
    # carving matching pockets in Top so the inlay sits flush. (Gotcha #29.)
    if decos:
        print(f"\nFlush inlay overlap resolution (n={len(decos)})...")
        for i, target in enumerate(decos):
            for j in range(i + 1, len(decos)):
                boolean_diff_keep_cutter(target, decos[j], f'OvrRes_{j}_into_{i}')
            clean_mesh(target)

        print("Flush inlay: cutting Top pockets...")
        for d in decos:
            cut = d.copy(); cut.data = d.data.copy()
            bpy.context.collection.objects.link(cut)
            for v in cut.data.vertices:
                if v.co.z >= t_z_max - 1e-4:
                    v.co.z += 0.05
            cut.data.update()
            boolean_op(top, cut, 'DIFFERENCE', f'Pocket_{d.name}')
        clean_mesh(top); repair_manifold(top)
        print(f"  Top after pockets: {top.dimensions.x:.2f}×{top.dimensions.y:.2f}×{top.dimensions.z:.2f}  "
              f"nm={check_nonmanifold(top)}")

    # ── Step 9: Materials + hide FullBead ──────────────────────────────
    body.hide_set(True); body.hide_render = True
    assign_material(bottom, 'BottomMat', (0.05, 0.05, 0.05, 1))  # black back
    assign_material(top, 'TopMat', (1.0, 1.0, 1.0, 1))  # white show-face base

    # Build orientation — leave Bottom and Top at origin; bead-stl-export
    # applies the print-orientation flip at export time.
    bottom.location = (0, 0, 0)
    top.location = (0, 0, 0)

    # Gotcha #16: this centered-mesh pipeline produces Bottom already in
    # print orientation (silhouette face DOWN, pegs UP). Default export flip
    # would un-orient it; override to 0° for every part.
    flip_overrides = {"Bottom": 0.0, "Top": 0.0}
    for d in decos:
        flip_overrides[d.name] = 0.0
    bpy.context.scene["nfc_export_flip_override"] = json.dumps(flip_overrides)

    os.makedirs(PRINT_DIR, exist_ok=True)
    blend_path = os.path.join(PRINT_DIR, 'black-rainbow_charm.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"\n.blend saved: {blend_path}")

    print("\n" + "=" * 60)
    print(f"Bottom: {bottom.dimensions.x:.2f} × {bottom.dimensions.y:.2f} × {bottom.dimensions.z:.2f}")
    print(f"Top:    {top.dimensions.x:.2f} × {top.dimensions.y:.2f} × {top.dimensions.z:.2f}")
    for d in decos:
        print(f"  {d.name:<28} {d.dimensions.x:.2f} × {d.dimensions.y:.2f} × {d.dimensions.z:.2f}")
    print("Build complete.")


if __name__ == '__main__':
    main()
