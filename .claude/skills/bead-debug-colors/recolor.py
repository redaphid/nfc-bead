"""Architectural coloring for an NFC bead in Blender.

Recolors the three printable parts (Bottom, Top, decoration) with distinct
solid materials and adds wireframe overlay objects (DBG_*) marking where the
hidden features live (pegs, peg holes, NFC pocket, string hole).

Idempotent: running it twice produces the same scene state. Run via MCP
execute_blender_code, or copy-paste into Blender's scripting workspace.

Edit the CONFIG block at the top to match the bead being debugged. The
defaults here mirror the rezz bead's layout.
"""
import bpy, math
from mathutils import Vector

# ─── CONFIG — pull from beads/<name>/build_<name>.py ───
PEGS         = [(-7.5, 3.0), (7.5, 3.0), (0.0, -10.0)]
PEG_DIA      = 2.0
PEG_HEIGHT   = 1.5
PEG_HOLE_DIA = PEG_DIA + 0.2          # 0.1mm clearance per side
NFC_POS      = (0.0, -1.0)
NFC_DIA      = 10.5
NFC_DEPTH    = 0.8
HOLE_Y       = 9.0
HOLE_DIA     = 2.0

DECORATION_NAME = "RezzSpiral"        # or whatever the build script names it

# ─── Color palette (the convention) ───
COL_BOTTOM  = (0.10, 0.80, 0.95, 1)   # CYAN
COL_TOP     = (0.20, 0.30, 0.95, 1)   # BLUE
COL_DECOR   = (1.00, 0.10, 0.65, 1)   # MAGENTA
COL_PEG     = (0.95, 0.85, 0.10, 1)   # YELLOW
COL_PEGHOLE = (0.10, 0.95, 0.30, 1)   # GREEN
COL_NFC     = (1.00, 0.55, 0.10, 1)   # ORANGE
COL_HOLE    = (0.30, 1.00, 0.40, 1)   # GREEN-cyl


def repaint(obj, rgba, name):
    obj.data.materials.clear()
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.4
    bsdf.inputs["Metallic"].default_value = 0.0
    obj.data.materials.append(m)


def add_overlay(name, mesh_call, rgba, location, rotation=(0, 0, 0)):
    mesh_call(location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    repaint(obj, rgba, f"{name}_M")
    obj.display_type = 'WIRE'
    return obj


def world_pt(obj, local_xyz):
    """World-space coordinate of a local-space point on obj. Use this rather
    than guessing where flipped/translated halves end up."""
    return obj.matrix_world @ Vector(local_xyz)


# ─── Recolor printable parts ───
bottom = bpy.data.objects.get("Bottom")
top    = bpy.data.objects.get("Top")
decor  = bpy.data.objects.get(DECORATION_NAME)

if bottom: repaint(bottom, COL_BOTTOM, "DBG_Bottom_Cyan")
if top:    repaint(top,    COL_TOP,    "DBG_TopBody_Blue")
if decor:  repaint(decor,  COL_DECOR,  "DBG_Decor_Magenta")

# ─── Wipe prior overlays ───
for obj in list(bpy.data.objects):
    if obj.name.startswith("DBG_") and obj.type == 'MESH':
        # Only remove the overlay primitives, not the recolored printable parts
        # (those have DBG_-prefixed material names but their object names are
        # still Bottom/Top/<decor>)
        if obj.name not in ("Bottom", "Top", DECORATION_NAME):
            bpy.data.objects.remove(obj, do_unlink=True)

# ─── Peg overlays on bottom ───
if bottom:
    for i, (px, py) in enumerate(PEGS):
        # Peg cylinder local position is (px, py, half_top_face_z); world via matrix.
        # The build script positions pegs at z=b_z_max..b_z_max+PEG_HEIGHT in
        # original space; we just need a marker — use the peg's CENTER in the
        # bottom's local space at z = pre-flip top + PEG_HEIGHT/2.
        loc = world_pt(bottom, (px, py, 2.5 + PEG_HEIGHT / 2.0))
        add_overlay(
            f"DBG_Peg{i}",
            lambda **kw: bpy.ops.mesh.primitive_cylinder_add(
                vertices=24, radius=PEG_DIA / 2, depth=PEG_HEIGHT, **kw),
            COL_PEG, location=tuple(loc),
        )

# ─── Peg-hole overlays on top ───
if top:
    for i, (px, py) in enumerate(PEGS):
        loc = world_pt(top, (px, py, PEG_HEIGHT / 2.0))
        add_overlay(
            f"DBG_PegHole{i}",
            lambda **kw: bpy.ops.mesh.primitive_cylinder_add(
                vertices=24, radius=PEG_HOLE_DIA / 2, depth=PEG_HEIGHT + 0.3, **kw),
            COL_PEGHOLE, location=tuple(loc),
        )

# ─── NFC pocket overlay on bottom ───
if bottom:
    loc = world_pt(bottom, (NFC_POS[0], NFC_POS[1], 2.5 - NFC_DEPTH / 2.0))
    add_overlay(
        "DBG_NFCPocket",
        lambda **kw: bpy.ops.mesh.primitive_cylinder_add(
            vertices=48, radius=NFC_DIA / 2, depth=NFC_DEPTH, **kw),
        COL_NFC, location=tuple(loc),
    )

# ─── String hole overlays — one cylinder along X for each half ───
for half in (bottom, top):
    if half is None:
        continue
    loc = world_pt(half, (0, HOLE_Y, 0))
    add_overlay(
        f"DBG_StringHole_{half.name}",
        lambda **kw: bpy.ops.mesh.primitive_cylinder_add(
            vertices=24, radius=HOLE_DIA / 2, depth=30, **kw),
        COL_HOLE, location=tuple(loc),
        rotation=(0, math.radians(90), 0),
    )

print("[bead-debug-colors] applied — Bottom=CYAN  Top=BLUE  Decor=MAGENTA")
print("[bead-debug-colors] overlays — Pegs=YELLOW  PegHoles=GREEN  NFC=ORANGE  StringHole=GREEN-cyl")
