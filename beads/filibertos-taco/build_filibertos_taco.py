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
#   'painted' — fill 4 colored regions on the show face (cartoon)
#   'neon'    — line-art strokes on a dark body (synthwave / stencil)
#   'blocks'  — 3 flat colors: filling, shell, body (Filibertos block-color)
# Switch with `bpy.context.scene["nfc_taco_style"] = "neon"` before exec, or
# env var FILIBERTOS_TACO_STYLE.
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
    "filling_line":  (0.36, 0.84, 1.00, 1),    # lettuce-shell dividing line
    "accents":       (0.92, 0.20, 0.30, 1),    # cheese/salsa drips — third filament
}

# Block-mode color palette.
BLOCK_COLORS = {
    "filling":            (0.30, 0.65, 0.20, 1),    # green lettuce slab
    "shell":              (0.95, 0.72, 0.10, 1),    # yellow shell slab
    "interior_detail":    (0.78, 0.13, 0.10, 1),    # red veins inside lettuce
    "shell_outline":      (0.63, 0.10, 0.08, 1),    # red ring around silhouette
    "lettuce_separator":  (0.78, 0.13, 0.10, 1),    # red curve between filling/shell
}
# Block-mode: each Decoration region is built by joining MULTIPLE source SVGs
# under one name, so we get a single solid filling/shell slab even though the
# extractor split each by brightness (light/dark green, light/dark yellow).
BLOCK_GROUPS = {
    # Body (Bottom + Top) prints in shell yellow — it IS the shell.
    # Decorations stack on the show face (lower layer_idx = closer to body).
    # Order matters: things higher in z OCCLUDE things lower. The slicer
    # also fights coplanar/near-coplanar surfaces, so each layer sits
    # 0.1mm above the previous (above typical layer height 0.16mm so the
    # slicer can cleanly assign each to its own filament without z-fight).
    "filling":            ("region_filling.svg",),             # base — green lettuce
    "lettuce_separator":  ("region_lettuce_separator.svg",),   # red curve over filling
    "interior_detail":    ("region_interior_detail.svg",),     # red veins inside lettuce
    "shell_outline":      ("region_shell_outline.svg",),       # red ring TOP layer; never gets z-fought
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

def _discover_blocks():
    """Block style: list every region from BLOCK_GROUPS, even if no SVG
    exists for it. The polygon-manifest path (regions.json) doesn't need
    SVGs; it discovers regions by name match. SVG paths are still
    returned for fallback when regions.json is unavailable.
    Returns list of (object_name, svg_paths_tuple, color)."""
    out = []
    for slug, files in BLOCK_GROUPS.items():
        # Always include the slug — polygon path will skip if regions.json
        # has no entry for it. SVG fallback path filters out missing files.
        paths = tuple(os.path.join(BEAD_DIR, f) for f in files
                      if os.path.exists(os.path.join(BEAD_DIR, f)))
        col = BLOCK_COLORS.get(slug, (0.7, 0.7, 0.7, 1))
        out.append((f"Decoration{_camel(slug)}", paths, col))
    return out

if STYLE == 'neon':
    SVG_REGIONS = _discover('stroke', NEON_COLORS)
elif STYLE == 'blocks':
    SVG_REGIONS = _discover_blocks()
else:
    SVG_REGIONS = _discover('region', REGION_COLORS)

TARGET_WIDTH  = 25.0          # mm (taco silhouette ~25w x 17h after extraction)
THICKNESS     = 5.0           # mm total split into 2 x 2.5

HOLE_DIA      = 2.0           # mm
HOLE_Y        = 5.0           # mm — auto-fit found 5.02; rounded so cleanly inside silhouette
HOLE_Z_OFFSET = 1.25          # mm — shift hole entirely into Top half (recipe gotcha #23)

NFC_DIAMETER  = 10.5          # mm — recipe default (NTAG215)
NFC_DEPTH     = 0.8           # mm
NFC_POS       = (0.0, 1.5)    # mm — bumped up from (0, 0.5): perimeter raycast
                              # caught that with a 5.25mm radius the bottom of
                              # the pocket sat too close to the silhouette
                              # bottom edge (Y≈-8.5). Y=1.5 keeps perimeter
                              # comfortably inside.

PEG_DIAMETER  = 2.6           # mm — recipe default 2.0 is too narrow on the
                              # Centauri Carbon 2; redaphid-portrait v5 bumped
                              # to 2.6 for actual snap-fit. See gotcha #30.
PEG_HEIGHT    = 1.5
PEG_CLEARANCE = 0.05          # mm radial — recipe default 0.1 was too generous;
                              # redaphid-portrait v6 nailed snap-fit at 0.05.
# Re-tuned for PEG_DIAMETER=2.6: original (7.5,-6),(-9.5,0),(7.5,+2.5) all
# failed the perimeter check at peg_r=1.35mm. find_pegs.py scans candidates
# against the clean silhouette + NFC + string-hole clearances. These three
# form the widest triangle that passes (silhouette is asymmetric — there
# are no valid left-side candidates below y≈-1).
PEGS = [
    (-10.5,  0.0),    # far-left, mid-height (left shell tip area)
    (  8.5,  2.0),    # upper right (above lettuce)
    (  9.5, -5.5),    # lower right (right shell tip)
]

# Multi-color FLUSH inlay on Top show face. Each decoration's top face sits
# exactly at t_z_max (the bead surface) and the mesh extrudes DOWN by
# DECO_RELIEF into Top; matching pockets are carved out of Top so the inlay
# fills its socket without protrusion. Painter's order is resolved by
# subtracting higher-rank deco footprints from lower-rank ones (so each
# pixel of the show face belongs to exactly one filament). The whole bead
# surface is therefore smooth — colors are visible at the surface only as
# different filaments, not as raised relief. See gotcha #29 in the recipe.
DECO_RELIEF = 0.4              # mm — depth of inlay socket
DECO_LIFT_EPS = 0.0            # mm — kept for API compat; 0 in flush mode
DECO_LAYER_STEP = 0.0          # mm — flush mode: no z-stack between layers

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

def boolean_diff_keep_cutter(target, cutter, name='DiffKeep'):
    """Boolean DIFFERENCE that preserves the cutter (uses a copy)."""
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

def verify_hole(obj, origin, direction, label=''):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    r = ev.ray_cast(origin, direction)
    print(f"  {label}: {'OPEN' if not r[0] else f'hit z={r[1].z:.3f}'}")
    return not r[0]

def polygons_to_mesh(polygons, name, z=0.0):
    """Build a flat Blender mesh from a list of polygons.

    Each polygon is a dict {'outer': [(x,y),...], 'holes': [[(x,y),...]]}
    (legacy flat lists also accepted). Hole-aware: ring-shaped regions
    (silhouette outline) print as actual rings, not solid disks.

    Uses bmesh.ops.triangle_fill which handles polygon-with-holes via
    constrained Delaunay triangulation — built into Blender, no extra
    dependencies."""
    import bmesh
    if not polygons:
        return None
    me = bpy.data.meshes.new(name + 'Mesh')
    bm = bmesh.new()
    for poly in polygons:
        if isinstance(poly, dict):
            outer = poly.get('outer', [])
            holes = poly.get('holes', [])
        else:
            outer = poly
            holes = []
        if len(outer) < 3: continue

        if not holes:
            # Simple polygon: direct n-gon face.
            try:
                verts = [bm.verts.new((float(x), float(y), float(z))) for x, y in outer]
                bm.faces.new(verts)
            except ValueError:
                pass
            continue

        if len(holes) == 1:
            # Ring polygon: outer loop + 1 inner loop = annulus. Build by
            # creating both loops as edges, then bridge_loops to skin.
            # Manifold by construction (no triangle_fill artifacts).
            outer_verts = [bm.verts.new((float(x), float(y), float(z))) for x, y in outer]
            inner_verts = [bm.verts.new((float(x), float(y), float(z))) for x, y in holes[0]]
            outer_edges, inner_edges = [], []
            for i in range(len(outer_verts)):
                try:
                    outer_edges.append(bm.edges.new((outer_verts[i], outer_verts[(i+1) % len(outer_verts)])))
                except ValueError: pass
            for i in range(len(inner_verts)):
                try:
                    inner_edges.append(bm.edges.new((inner_verts[i], inner_verts[(i+1) % len(inner_verts)])))
                except ValueError: pass
            try:
                bmesh.ops.bridge_loops(bm, edges=outer_edges + inner_edges)
            except Exception as ex:
                print(f"  bridge_loops failed for {name}: {ex}; falling back to triangle_fill")
                try:
                    bmesh.ops.triangle_fill(bm, edges=outer_edges + inner_edges, use_beauty=True)
                except Exception:
                    pass
            continue

        # Multi-hole polygon: triangle_fill (best Blender can do without earcut)
        all_loops = [outer] + holes
        loop_edges = []
        for loop in all_loops:
            verts = [bm.verts.new((float(x), float(y), float(z))) for x, y in loop]
            for i in range(len(verts)):
                try:
                    loop_edges.append(bm.edges.new((verts[i], verts[(i+1) % len(verts)])))
                except ValueError:
                    pass
        if loop_edges:
            try:
                bmesh.ops.triangle_fill(bm, edges=loop_edges, use_beauty=True)
            except Exception as ex:
                print(f"  triangle_fill failed for {name}: {ex}")
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    return obj

def import_svg_to_mesh(path, name, target_width_mm, force_scale=None):
    """Import an SVG and convert to mesh.

    `target_width_mm` auto-fits the mesh's *own* X bbox to that width. ONLY
    appropriate for the body silhouette — for decoration SVGs whose path
    extent is a SUBSET of the viewBox (e.g. small interior detail fragments),
    auto-fit stretches the fragments to fill 25mm and breaks alignment with
    the silhouette frame.

    `force_scale` (preferred for decorations) applies a fixed Blender-unit
    scale instead, derived from the silhouette's import. Pass the silhouette's
    `_silhouette_scale_factor` so all decorations share its coordinate frame."""
    pre_objs = {o.name for o in bpy.context.scene.objects}
    bpy.ops.import_curve.svg(filepath=path)
    curves = [o for o in bpy.context.scene.objects
              if o.type == 'CURVE' and o.name not in pre_objs]
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
    if force_scale is not None:
        # Apply the silhouette's known scale uniformly. Two-step like target-
        # width path: scale + apply, then x1000 + apply.
        sf = force_scale
        m.scale = (sf, sf, sf); bpy.ops.object.transform_apply(scale=True)
        m.scale = (1000, 1000, 1000); bpy.ops.object.transform_apply(scale=True)
    elif target_width_mm:
        sf = (target_width_mm/1000.0) / m.dimensions.x
        m.scale = (sf, sf, sf); bpy.ops.object.transform_apply(scale=True)
        m.scale = (1000, 1000, 1000); bpy.ops.object.transform_apply(scale=True)
        # Stash the scale so subsequent decoration imports can reuse it
        bpy.context.scene['_silhouette_scale_factor'] = sf
    return m

def _build_silhouette_cropper(svg_path, target_w, z_lo, z_hi):
    """Make a clean tall extrusion of silhouette.svg (no peg/NFC holes).
    Used as a boolean INTERSECT cropper for decorations so they get
    clipped to the silhouette outer boundary without inheriting any
    interior holes from Top/Bottom."""
    pre_objs = {o.name for o in bpy.context.scene.objects}
    bpy.ops.import_curve.svg(filepath=svg_path)
    curves = [o for o in bpy.context.scene.objects
              if o.type == 'CURVE' and o.name not in pre_objs]
    bpy.ops.object.select_all(action='DESELECT')
    for o in curves: o.select_set(True)
    bpy.context.view_layer.objects.active = curves[0]
    if len(curves) > 1: bpy.ops.object.join()
    cv = bpy.context.active_object
    cv.data.dimensions = '2D'; cv.data.fill_mode = 'BOTH'; cv.data.resolution_u = 64
    bpy.ops.object.convert(target='MESH')
    m = bpy.context.active_object
    sf = (target_w / 1000.0) / m.dimensions.x
    m.scale = (sf, sf, sf); bpy.ops.object.transform_apply(scale=True)
    m.scale = (1000, 1000, 1000); bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    m.location = (0, 0, z_lo)
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
    scene_style = bpy.context.scene.get('nfc_taco_style')
    if scene_style:
        STYLE = scene_style
    if STYLE == 'neon':
        SVG_REGIONS = _discover('stroke', NEON_COLORS)
    elif STYLE == 'blocks':
        SVG_REGIONS = _discover_blocks()
    else:
        SVG_REGIONS = _discover('region', REGION_COLORS)
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

    # ── Step 3: Verify peg + NFC positions on full bead ────────────────
    print("\nPeg + NFC perimeter check:")
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    nfc_r = NFC_DIAMETER/2.0; peg_r = PEG_DIAMETER/2.0
    perim = [(peg_r*math.cos(k*math.pi/4), peg_r*math.sin(k*math.pi/4)) for k in range(8)]
    bad = False

    # NFC perimeter check: 16 points around the pocket boundary must all
    # land in solid silhouette. Without this, a too-large or off-center
    # pocket can clip past the silhouette outer boundary, leaving a
    # paper-thin or open wall along one side. Symmetric to the peg
    # perimeter check (recipe gotcha #21) but with more samples since
    # NFC radius is much larger.
    nfc_perim = [(nfc_r*math.cos(k*math.pi/8), nfc_r*math.sin(k*math.pi/8))
                 for k in range(16)]
    nfc_misses = sum(1 for ox, oy in nfc_perim
                     if not ev.ray_cast(Vector((NFC_POS[0]+ox, NFC_POS[1]+oy, z_max+5)),
                                        Vector((0, 0, -1)))[0])
    print(f"  NFC ({NFC_POS[0]:+.1f},{NFC_POS[1]:+.1f}) r={nfc_r}: "
          f"perimeter inside silhouette = {16-nfc_misses}/16"
          + (f"  CLIPPING {nfc_misses}/16 outside!" if nfc_misses else ""))
    if nfc_misses > 0:
        print(f"    → NFC pocket clips past silhouette boundary; "
              f"adjust NFC_POS or shrink NFC_DIAMETER")
        bad = True

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

    # ── Step 8: Multi-color FLUSH decoration on Top show face ──────────
    t_z_max = max(v.co.z for v in top.data.vertices)
    # Inlay: top face of every deco = bead surface; mesh extrudes DOWN.
    deco_z_floor = t_z_max - DECO_RELIEF
    print(f"\nDecorations FLUSH at z=[{deco_z_floor:.3f}, {t_z_max:.3f}]  relief={DECO_RELIEF}mm")

    # Prefer the polygon manifest when available — guaranteed-consistent
    # coordinate frame across regions. Falls back to per-SVG import if
    # regions.json is missing.
    regions_json = os.path.join(BEAD_DIR, 'regions.json')
    polygon_data = None
    if os.path.exists(regions_json) and STYLE in ('blocks',):
        import json
        polygon_data = json.load(open(regions_json, encoding='utf-8'))
        print(f"  using regions.json polygon manifest "
              f"({sum(len(r['polygons']) for r in polygon_data['regions'].values())} polygons)")

    decos = []

    # ── Polygon-manifest path (clean, consistent coordinate frame) ─────
    if polygon_data is not None:
        for layer_idx, (name, svg, color) in enumerate(SVG_REGIONS):
            # Map decoration name back to the manifest key (camelCase → snake_case)
            slug = ''.join('_' + c.lower() if c.isupper() else c
                           for c in name[len('Decoration'):]).lstrip('_')
            region = polygon_data['regions'].get(slug)
            if not region or not region['polygons']:
                print(f"  skip {name} (no polygons in regions.json for '{slug}')"); continue
            d = polygons_to_mesh(region['polygons'], name,
                                 z=deco_z_floor + layer_idx * DECO_LAYER_STEP)
            if d is None:
                print(f"  skip {name} (polygons→mesh empty)"); continue
            # Extrude to relief
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
            # Crop to silhouette via fresh-silhouette cropper
            cropper = _build_silhouette_cropper(SVG_BODY, TARGET_WIDTH,
                                                z_lo=t_z_min,
                                                z_hi=t_z_max + DECO_RELIEF + 0.5)
            cropper.name = '_Cropper'
            boolean_op(d, cropper, 'INTERSECT', f'{name}Crop')
            clean_mesh(d)
            repair_manifold(d)
            assign_material(d, f"{name}Mat", color)
            decos.append(d)
            nm = check_nonmanifold(d)
            print(f"  {name}: dims={d.dimensions.x:.2f}x{d.dimensions.y:.2f}x{d.dimensions.z:.2f}  non-manifold={nm}")
        # Skip the SVG path below
        SVG_REGIONS = []

    for layer_idx, (name, svg, color) in enumerate(SVG_REGIONS):
        # `svg` may be either a single path str (painted/neon) or a tuple of
        # paths (blocks — multiple SVGs joined into one decoration object).
        svg_paths = (svg,) if isinstance(svg, str) else tuple(svg)
        existing_paths = [p for p in svg_paths if os.path.exists(p)]
        if not existing_paths:
            print(f"  skip {name} (no svg)"); continue
        _existing_objs = {o.name for o in bpy.data.objects}
        # Import each SVG, then join them into a single mesh under `name`
        imported = []
        for i, p in enumerate(existing_paths):
            sub_name = name if len(existing_paths) == 1 else f"{name}__part{i}"
            # All region SVGs are written with corner markers anchoring
            # their path bbox to the silhouette's bbox (extract_regions.py
            # write_svg). So per-SVG auto-fit-to-25mm gives consistent
            # scale + position across regions. No force_scale needed.
            d_part = import_svg_to_mesh(p, sub_name, TARGET_WIDTH)
            if d_part: imported.append(d_part)
        if not imported:
            print(f"  skip {name} (no curves imported)"); continue
        # If multiple parts were imported (legacy layout), join them as
        # flat 2D first (before extrude). The combined SVG is preferred —
        # see BLOCK_GROUPS in CONFIG.
        if len(imported) > 1:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in imported: obj.select_set(True)
            bpy.context.view_layer.objects.active = imported[0]
            bpy.ops.object.join()
            d = bpy.context.active_object
            d.name = name
        else:
            d = imported[0]
        # bbox-center each decoration at the silhouette's center; stack
        # subsequent layers slightly above the previous one so order is stable.
        bpy.ops.object.select_all(action='DESELECT')
        d.select_set(True); bpy.context.view_layer.objects.active = d
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
        d.location = (0, 0, deco_z_floor + layer_idx * DECO_LAYER_STEP)

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
        # Crop the decoration to the silhouette OUTER boundary so it never
        # extends past the bead edge. Build the cropper from a fresh
        # silhouette.svg import — NOT from Top. Top has peg-socket holes
        # cut into it, and INTERSECT with that punches the socket holes
        # through the decoration (visible as bare-show-face circles).
        cropper = _build_silhouette_cropper(SVG_BODY, TARGET_WIDTH,
                                            z_lo=t_z_min,
                                            z_hi=t_z_max + DECO_RELIEF + 0.5)
        cropper.name = '_Cropper'
        boolean_op(d, cropper, 'INTERSECT', f'{name}Crop')
        clean_mesh(d)
        repair_manifold(d)        # fixes ring-shape boolean artifacts
        assign_material(d, f"{name}Mat", color)
        decos.append(d)
        # report manifold so the build log surfaces issues immediately
        nm = check_nonmanifold(d)
        print(f"  {name}: dims={d.dimensions.x:.2f}x{d.dimensions.y:.2f}x{d.dimensions.z:.2f}  non-manifold={nm}")

    # ── Step 8.5: FLUSH inlay postprocess ──────────────────────────────
    # decos[] is populated in painter's order: index 0 = lowest layer,
    # index -1 = topmost. With flush mode all decos occupy the same Z
    # slab [deco_z_floor, t_z_max], so overlapping footprints would
    # z-fight. Resolve by subtracting every higher-rank deco from each
    # lower-rank one (so each pixel of the show face belongs to a single
    # filament), then carve matching pockets in Top so the inlay sits
    # flush. See gotcha #29.
    if decos:
        print(f"\nFlush inlay: resolving overlap (n={len(decos)})...")
        for i, target in enumerate(decos):
            for j in range(i + 1, len(decos)):
                boolean_diff_keep_cutter(target, decos[j], f'OvrRes_{j}_into_{i}')
            clean_mesh(target)

        print("Flush inlay: cutting Top pockets...")
        for d in decos:
            cut = d.copy(); cut.data = d.data.copy()
            bpy.context.collection.objects.link(cut)
            # extend cutter up 0.05mm so the coplanar top face cuts cleanly
            for v in cut.data.vertices:
                if v.co.z >= t_z_max - 1e-4:
                    v.co.z += 0.05
            cut.data.update()
            boolean_op(top, cut, 'DIFFERENCE', f'Pocket_{d.name}')
        clean_mesh(top)
        repair_manifold(top)   # ring-shape pockets (e.g. shell_outline) leave coplanar fragments
        print(f"  Top after pockets: dims={top.dimensions.x:.2f}x{top.dimensions.y:.2f}x{top.dimensions.z:.2f}  non-manifold={check_nonmanifold(top)}")

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
    # Decos already have absolute z baked into their vertex coords from the
    # polygon-manifest path (or via location set in the SVG-fallback path).
    # Don't rewrite location.z — would double-shift polygon-built decos.

    # Recipe gotcha #16: this centered-mesh pipeline produces Bottom already
    # in print orientation (silhouette face DOWN, pegs UP). The default
    # bead-stl-export flip would un-orient it, putting pegs on the bed and
    # silhouette cantilevered above. Override per-charm so re-exports stay
    # printable.
    import json
    flip_overrides = {"Bottom": 0.0, "Top": 0.0}
    for d in decos:
        flip_overrides[d.name] = 0.0
    bpy.context.scene["nfc_export_flip_override"] = json.dumps(flip_overrides)

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
