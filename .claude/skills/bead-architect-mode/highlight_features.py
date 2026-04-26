"""(EXPERIMENTAL) Color the actual print geometry's feature faces, NOT the STL.

After `architect_on.py` paints `Bottom`/`Top`/`Decoration` with their
solid wash colors, this script classifies each face of `Bottom` and
`Top` by geometric position and assigns it to a per-feature material
slot — so pegs, the NFC pocket, peg holes, and the string hole tunnel
each render in a distinct color in the live Blender viewport.

These materials are local to the .blend; STL export ignores material
info, so the slicer never sees them. The actual print geometry is the
visualization — no `DBG_*` widgets needed.

⚠ STATUS: experimental. The classifier uses object-local face centers
compared against build-script CONFIG positions, but the build pipeline
applies `origin_set BOUNDS` between feature creation and STL export,
which shifts the local origin to the bbox center. As a result the
peg/NFC classification undercounts faces unless the mesh is freshly
imported and untouched. The string-hole classifier works reliably (it's
keyed on Y/Z distance only, no XY origin dependency).

Per-bead tunables match the canonical rezz build
(`beads/rezz/build_rezz.py`). For other beads, copy this script and
adjust the CONFIG block.

Idempotent — re-running rebuilds the material slots and reassigns
indices.

Requires `Bottom` + `Top` in the scene. Run AFTER `architect_on.py`.
"""
import bpy

# ─── Per-bead CONFIG (matches beads/rezz/build_rezz.py) ─────────────────
# These are the construction parameters used to build the bead. Each
# face is classified by checking its centroid against these.
NFC_POS         = (0.0, -1.0)    # NFC pocket center in object-local XY
NFC_DIAMETER    = 10.5
NFC_DEPTH       = 0.8

PEGS            = [(-7.25, -1.0), (7.25, -1.0), (0.0, -8.25)]
PEG_DIAMETER    = 2.0
PEG_HEIGHT      = 1.5
PEG_HOLE_DIAMETER = PEG_DIAMETER + 0.2   # 0.1 mm clearance per side

HOLE_Y          = 7.0     # string hole at this Y, runs along X
HOLE_DIAMETER   = 2.0

THICKNESS_HALF  = 2.5     # each printable half is THICKNESS / 2
EPSILON         = 0.15    # tolerance for face-vs-feature checks

# ─── Architect-aesthetic feature palette ────────────────────────────────
# Saturated enough to read against the watercolor wash. Each is a "void or
# raised feature" per the engineering convention.
PEG_COLOR        = (0.95, 0.74, 0.18, 1.0)   # warm ochre        — pegs (raised)
NFC_COLOR        = (0.78, 0.32, 0.62, 1.0)   # rose-magenta      — NFC pocket (recess)
PEG_HOLE_COLOR   = (0.78, 0.22, 0.20, 1.0)   # venetian red      — peg holes (void)
STRING_HOLE_COLOR= (0.95, 0.52, 0.18, 1.0)   # rust orange       — string hole (void)


def _ensure_material(name: str, rgba):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF") if m.use_nodes else None
    if p:
        p.inputs["Base Color"].default_value = rgba
        p.inputs["Roughness"].default_value = 0.55
        p.inputs["Metallic"].default_value = 0.0
    return m


def _slot_index(obj, mat):
    """Append `mat` to obj.data.materials and return its index."""
    obj.data.materials.append(mat)
    return len(obj.data.materials) - 1


def _peg_inside(face_x, face_y, peg_x, peg_y, radius_with_eps):
    return (face_x - peg_x) ** 2 + (face_y - peg_y) ** 2 <= radius_with_eps ** 2


def _classify_bottom_face(poly, bbox_zmax):
    """Bottom is post-flip print orientation: silhouette face at z=0,
    inner face (with NFC pocket recess + pegs sticking up) at z=zmax-PEG_HEIGHT.
    Pegs occupy z=zmax-PEG_HEIGHT..zmax. NFC pocket is recessed into the puck
    from the inner face — interior surface in the local XY footprint of the NFC.
    """
    cx, cy, cz = poly.center

    inner_z = bbox_zmax - PEG_HEIGHT
    peg_radius = PEG_DIAMETER / 2 + EPSILON

    # Pegs: face center is in the peg-cylinder zone (z above inner face)
    if cz > inner_z - EPSILON:
        for px, py in PEGS:
            if _peg_inside(cx, cy, px, py, peg_radius):
                return "peg"

    # NFC pocket: face center is inside the NFC circle, AND below the inner face
    nfc_radius = NFC_DIAMETER / 2 + EPSILON
    if (cx - NFC_POS[0]) ** 2 + (cy - NFC_POS[1]) ** 2 <= nfc_radius ** 2 \
            and cz < inner_z + EPSILON:
        return "nfc"

    return "body"


def _classify_top_face(poly):
    """Top is print-orient as built: peg-hole face on the build plate (z=0),
    outer face (decoration host) at z=THICKNESS_HALF=2.5. Peg holes are
    cylindrical voids going UP from z=0 into the body. String hole is a
    cylinder along X at Y=HOLE_Y, Z=THICKNESS_HALF/2.
    """
    cx, cy, cz = poly.center

    # Peg holes: face inside a peg-hole cylinder near z=0
    peg_hole_radius = PEG_HOLE_DIAMETER / 2 + EPSILON
    if cz < PEG_HEIGHT + EPSILON:
        for px, py in PEGS:
            if _peg_inside(cx, cy, px, py, peg_hole_radius):
                return "peg_hole"

    # String hole: cylinder along X at Y=HOLE_Y, Z=mid
    string_hole_radius = HOLE_DIAMETER / 2 + EPSILON
    dy = cy - HOLE_Y
    dz = cz - THICKNESS_HALF / 2
    if dy ** 2 + dz ** 2 <= string_hole_radius ** 2:
        return "string_hole"

    return "body"


def _highlight_object(obj_name: str, classifier, body_mat, *feature_mats):
    obj = bpy.data.objects.get(obj_name)
    if obj is None or obj.type != 'MESH':
        return None
    me = obj.data

    # Reset to a fresh material list. Keeping the body wash material first
    # guarantees its slot index is 0.
    obj.data.materials.clear()
    obj.data.materials.append(body_mat)
    feature_slots = {}
    for label, mat in feature_mats:
        feature_slots[label] = _slot_index(obj, mat)

    counts = {label: 0 for label in feature_slots}
    counts["body"] = 0
    for poly in me.polygons:
        cls = classifier(poly, *([me.vertices[poly.vertices[0]].co.z * 0  # placeholder unused
                                   ] if False else []))  # keep call signature simple
        if cls in feature_slots:
            poly.material_index = feature_slots[cls]
            counts[cls] += 1
        else:
            poly.material_index = 0
            counts["body"] += 1

    me.update()
    return counts


# ─── Main ───────────────────────────────────────────────────────────────
peg_mat        = _ensure_material("MA_Feat_Peg",        PEG_COLOR)
nfc_mat        = _ensure_material("MA_Feat_NFC",        NFC_COLOR)
peg_hole_mat   = _ensure_material("MA_Feat_PegHole",    PEG_HOLE_COLOR)
string_hole_mat = _ensure_material("MA_Feat_StringHole", STRING_HOLE_COLOR)

# Pull the body wash materials that architect_on already created.
# If they're missing the user hasn't run architect_on yet — bail with a
# helpful message rather than producing a half-painted scene.
bottom_body_mat = bpy.data.materials.get("MA_Body_BlueGray")
top_body_mat    = bpy.data.materials.get("MA_Body_Sage")
if bottom_body_mat is None or top_body_mat is None:
    raise RuntimeError(
        "MA_Body_BlueGray / MA_Body_Sage missing — run architect_on.py first."
    )

# Bottom: classify pegs + NFC pocket
bottom = bpy.data.objects.get("Bottom")
if bottom is not None:
    zmax = max((bottom.matrix_world @ v.co).z for v in bottom.data.vertices)
    counts = _highlight_object(
        "Bottom",
        lambda poly: _classify_bottom_face(poly, zmax),
        bottom_body_mat,
        ("peg", peg_mat),
        ("nfc", nfc_mat),
    )
    print(f"[highlight] Bottom: body={counts.get('body',0)} peg={counts.get('peg',0)} nfc={counts.get('nfc',0)}")

# Top: classify peg holes + string hole
top = bpy.data.objects.get("Top")
if top is not None:
    counts = _highlight_object(
        "Top",
        lambda poly: _classify_top_face(poly),
        top_body_mat,
        ("peg_hole", peg_hole_mat),
        ("string_hole", string_hole_mat),
    )
    print(f"[highlight] Top: body={counts.get('body',0)} peg_hole={counts.get('peg_hole',0)} string_hole={counts.get('string_hole',0)}")

print("[highlight] Material slots assigned. STL export is unaffected — slicer ignores material info.")
