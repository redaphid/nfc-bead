"""Architectural / CAD coloring for an NFC bead in Blender.

Recolors the three printable parts (Bottom, Top, decoration) with muted
drafting colors and adds overlays for the hidden features. Convention
follows engineering drawings:

  POSITIVE features (added material): SOLID warm colors
    - Pegs                      → solid YELLOW (filled cylinder)

  NEGATIVE features (voids / removed material): WIREFRAME cool colors
    - Peg holes                 → wireframe RED
    - NFC pocket                → wireframe MAGENTA
    - String hole               → wireframe ORANGE (long cylinder along X)

  Printable bodies: muted blueprint tones so the brightly-colored
  features pop against the bodies.

Idempotent: running it twice produces the same scene state.

Edit the CONFIG block at the top to match the bead being debugged. The
defaults here mirror the rezz bead's print-layout (halves at x=±18).

Coordinate convention (the canonical print-layout produced by build_*.py):
  - Bottom is FLIPPED 180° around X then placed at (BOTTOM_X, 0, dim.z/2).
    Pegs face DOWN; tips touch z=0. Original mesh's +Y becomes -Y in
    world space, so a feature originally at local (px, py, …) ends up
    at world (BOTTOM_X + px, -py, …).
  - Top is NOT flipped, placed at (TOP_X, 0, dim.z/2). Inner face (with
    peg holes) is at world z=0.
"""
import bpy, math

# ─── CONFIG — pull from beads/<name>/build_<name>.py CONFIG block ───
# Active bead: rezz (post-flip; print-layout halves at X=±18; HOLE_Y=9 etc.)
PEGS         = [(-7.5, 3.0), (7.5, 3.0), (0.0, -10.0)]
PEG_DIA      = 2.0
PEG_HEIGHT   = 1.5
PEG_HOLE_DIA = PEG_DIA + 0.2          # 0.1 mm clearance per side
NFC_POS      = (0.0, -1.0)
NFC_DIA      = 10.5
NFC_DEPTH    = 0.8
HOLE_Y       = 9.0
HOLE_DIA     = 2.0

DECORATION_NAME = "Decoration"   # canonical project name; legacy *_spiral / *_decor still found by fallback
BOTTOM_X     = -18.0
TOP_X        =  18.0

# True post-flip (print-layout — bottom rotated 180° around X so the silhouette
# face is on the build plate and pegs point up). The y-axis sign on bottom-half
# widgets flips accordingly.
BOTTOM_FLIPPED = True

# ─── CAD / drafting palette ───
# Bodies — muted blueprint tones
COL_BOTTOM   = (0.55, 0.68, 0.78, 1)   # blueprint blue-gray
COL_TOP      = (0.62, 0.74, 0.70, 1)   # subtly greener for contrast
COL_DECOR    = (0.82, 0.55, 0.20, 1)   # warm bronze (raised relief)

# Positive features (added material) — solid warm
COL_PEG      = (1.00, 0.82, 0.10, 1)   # solid YELLOW

# Negative features (voids) — wireframe cool/red
COL_PEGHOLE  = (0.92, 0.15, 0.15, 1)   # wireframe RED (CAD void convention)
COL_NFC      = (0.88, 0.15, 0.78, 1)   # wireframe MAGENTA (different void shape)
COL_HOLE     = (1.00, 0.50, 0.10, 1)   # wireframe ORANGE (string hole)


def repaint(obj, rgba, name):
    obj.data.materials.clear()
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.55
    bsdf.inputs["Metallic"].default_value = 0.0
    obj.data.materials.append(m)


def add_widget(name, mesh_call, rgba, location, rotation=(0, 0, 0), display='WIRE'):
    """Add an overlay cylinder. display='WIRE' for voids, 'TEXTURED' for solids."""
    mesh_call(location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    repaint(obj, rgba, f"{name}_M")
    obj.display_type = display
    return obj


# ─── Recolor printable parts (canonical names only — no legacy fallbacks) ───
def _find_mesh(name):
    o = bpy.data.objects.get(name)
    return o if (o and o.type == 'MESH') else None

bottom = _find_mesh("Bottom")
top    = _find_mesh("Top")
decor  = _find_mesh(DECORATION_NAME)

if bottom: repaint(bottom, COL_BOTTOM, "DBG_Bottom_BlueprintGray")
if top:    repaint(top,    COL_TOP,    "DBG_TopBody_BlueprintSage")
if decor:  repaint(decor,  COL_DECOR,  "DBG_Decor_Bronze")

# Flat shading reads more "drafting drawing" than smooth shading
for obj in (bottom, top, decor):
    if obj is None:
        continue
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_flat()

# ─── Wipe any prior DBG_* overlay objects (don't touch Bottom/Top/decor) ───
_protected = {"Bottom", "Top", DECORATION_NAME}
for obj in list(bpy.data.objects):
    if obj.name.startswith("DBG_") and obj.name not in _protected:
        bpy.data.objects.remove(obj, do_unlink=True)

# Sign for bottom-half widget Y. If bottom has been flipped 180° around X,
# its mesh-local +Y now reads as world -Y. Pre-flip, +Y stays +Y.
_BY = -1.0 if BOTTOM_FLIPPED else 1.0

# ── Inner-face Z is computed from the ACTUAL mesh bbox in world coords. ──
# This works for both build-pipeline scenes (where halves are recentered to
# inner-face=z=0) AND for STL imports (where halves keep their print-layout
# z-range). The canonical PEG_HEIGHT lets us infer where the inner face sits
# without scanning vertex normals.
def _world_z_range(name):
    """Return (zmin, zmax) of the mesh bbox in world coords, or None if missing."""
    o = _find_mesh(name)
    if o is None:
        return None
    zs = [(o.matrix_world @ v.co).z for v in o.data.vertices]
    return (min(zs), max(zs)) if zs else None

_bottom_z = _world_z_range("Bottom")
_top_z    = _world_z_range("Top")

if _bottom_z is None:
    _BOTTOM_INNER_Z = 0.0
elif BOTTOM_FLIPPED:
    # Print-layout: pegs stick UP from inner face; inner face is at zmax-PEG_HEIGHT.
    # If the puck has no protruding pegs in this mesh (rare), zmax IS the inner face.
    span = _bottom_z[1] - _bottom_z[0]
    _BOTTOM_INNER_Z = (_bottom_z[1] - PEG_HEIGHT) if span >= PEG_HEIGHT * 1.5 else _bottom_z[1]
else:
    # Pre-flip: inner face is the top of the mesh
    _BOTTOM_INNER_Z = _bottom_z[1]

if _top_z is None:
    _TOP_INNER_Z = 0.0
else:
    # Top is never flipped. Inner face = mating face = bottom of mesh = zmin.
    _TOP_INNER_Z = _top_z[0]

# Pegs grow upward from the inner face in both build-time AND print-layout
# (post-flip the bottom is upside-down so its "up" still points toward the top).
_PEG_DZ      = PEG_HEIGHT / 2
# NFC pocket is recessed INTO the puck from the inner face
_NFC_DZ      = -NFC_DEPTH / 2
# Peg holes are recesses UP into the top half from inner face = z=0 in print-layout
peg_hole_depth = PEG_HEIGHT + 0.3
_PH_DZ       = peg_hole_depth / 2

print(f"[recolor] inner_z bottom={_BOTTOM_INNER_Z:.2f} top={_TOP_INNER_Z:.2f}  "
      f"(bottom z range={_bottom_z}, top z range={_top_z})")

# ─── PEGS — positive features, SOLID yellow widgets ───
for i, (px, py) in enumerate(PEGS):
    add_widget(
        f"DBG_Peg{i}",
        lambda **kw: bpy.ops.mesh.primitive_cylinder_add(
            vertices=24, radius=PEG_DIA / 2, depth=PEG_HEIGHT, **kw),
        COL_PEG,
        location=(BOTTOM_X + px, _BY * py, _BOTTOM_INNER_Z + _PEG_DZ),
        display='TEXTURED',                # SOLID — represents added material
    )

# ─── PEG HOLES — negative features, RED wireframe ───
for i, (px, py) in enumerate(PEGS):
    add_widget(
        f"DBG_PegHole{i}",
        lambda **kw: bpy.ops.mesh.primitive_cylinder_add(
            vertices=24, radius=PEG_HOLE_DIA / 2, depth=peg_hole_depth, **kw),
        COL_PEGHOLE,
        location=(TOP_X + px, py, _TOP_INNER_Z + _PH_DZ),
        display='WIRE',
    )

# ─── NFC POCKET — negative, MAGENTA wireframe ───
add_widget(
    "DBG_NFCPocket",
    lambda **kw: bpy.ops.mesh.primitive_cylinder_add(
        vertices=48, radius=NFC_DIA / 2, depth=NFC_DEPTH, **kw),
    COL_NFC,
    location=(BOTTOM_X + NFC_POS[0], _BY * NFC_POS[1], _BOTTOM_INNER_Z + _NFC_DZ),
    display='WIRE',
)

# ─── STRING HOLE — negative, ORANGE wireframe (long cylinder along X) ───
def _midz(obj):
    return obj.matrix_world.translation.z if obj is not None else 0.0

add_widget("DBG_StringHole_Top",
    lambda **kw: bpy.ops.mesh.primitive_cylinder_add(
        vertices=24, radius=HOLE_DIA / 2, depth=30, **kw),
    COL_HOLE,
    location=(TOP_X, HOLE_Y, _midz(top)),
    rotation=(0, math.radians(90), 0),
    display='WIRE')

add_widget("DBG_StringHole_Bottom",
    lambda **kw: bpy.ops.mesh.primitive_cylinder_add(
        vertices=24, radius=HOLE_DIA / 2, depth=30, **kw),
    COL_HOLE,
    location=(BOTTOM_X, _BY * HOLE_Y, _midz(bottom)),
    rotation=(0, math.radians(90), 0),
    display='WIRE')

print("[bead-debug-colors] CAD palette applied:")
print("  Bottom=blueprint blue-gray   Top=blueprint sage   Decor=bronze")
print("  POSITIVE (solid):  Pegs=YELLOW")
print("  NEGATIVE (wire):   PegHoles=RED  NFC=MAGENTA  StringHole=ORANGE")
