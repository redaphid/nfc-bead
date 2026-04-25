"""Architectural coloring for an NFC bead in Blender.

Recolors the three printable parts (Bottom, Top, decoration) with distinct
solid materials and adds wireframe overlay objects (DBG_*) marking where the
hidden features live (pegs, peg holes, NFC pocket, string hole).

Idempotent: running it twice produces the same scene state. Run via MCP
execute_blender_code, or copy-paste into Blender's scripting workspace.

Edit the CONFIG block at the top to match the bead being debugged. The
defaults here mirror the rezz bead's print-layout (halves at x=±18).

Coordinate convention (the canonical print-layout produced by build_*.py):
  - Bottom half is FLIPPED 180° around X then placed at (BOTTOM_X, 0, dim.z/2).
    Pegs face DOWN; their tips touch z=0 (the build plate). Original mesh's
    +Y becomes -Y in world space, so a feature originally at local (px, py, …)
    ends up at world (BOTTOM_X + px, -py, …).
  - Top half is NOT flipped, placed at (TOP_X, 0, dim.z/2). Inner face (with
    peg holes) is at world z=0.
  - String hole runs along X through both halves at world Y = ±HOLE_Y
    (mirrored on bottom because of the flip).

Overlays use these explicit world coords rather than chaining matrix_world
through transform_apply'd halves — that path is fragile because the local
frame meaning differs before vs after transform_apply.
"""
import bpy, math

# ─── CONFIG — pull from beads/<name>/build_<name>.py CONFIG block ───
PEGS         = [(-7.5, 3.0), (7.5, 3.0), (0.0, -10.0)]
PEG_DIA      = 2.0
PEG_HEIGHT   = 1.5
PEG_HOLE_DIA = PEG_DIA + 0.2          # 0.1 mm clearance per side
NFC_POS      = (0.0, -1.0)
NFC_DIA      = 10.5
NFC_DEPTH    = 0.8
HOLE_Y       = 9.0
HOLE_DIA     = 2.0

DECORATION_NAME = "RezzSpiral"        # whatever the build script names the show-face decor
BOTTOM_X     = -18.0                  # canonical print-layout positions
TOP_X        =  18.0

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


# ─── Recolor printable parts ───
bottom = bpy.data.objects.get("Bottom")
top    = bpy.data.objects.get("Top")
decor  = bpy.data.objects.get(DECORATION_NAME)

if bottom: repaint(bottom, COL_BOTTOM, "DBG_Bottom_Cyan")
if top:    repaint(top,    COL_TOP,    "DBG_TopBody_Blue")
if decor:  repaint(decor,  COL_DECOR,  "DBG_Decor_Magenta")

# ─── Wipe any prior DBG_* overlay objects (don't touch Bottom/Top/decor) ───
_protected = {"Bottom", "Top", DECORATION_NAME}
for obj in list(bpy.data.objects):
    if obj.name.startswith("DBG_") and obj.name not in _protected:
        bpy.data.objects.remove(obj, do_unlink=True)

# ─── Peg overlays — pegs face DOWN on bottom, centers at world z = PEG_HEIGHT/2 ───
for i, (px, py) in enumerate(PEGS):
    add_overlay(
        f"DBG_Peg{i}",
        lambda **kw: bpy.ops.mesh.primitive_cylinder_add(
            vertices=24, radius=PEG_DIA / 2, depth=PEG_HEIGHT, **kw),
        COL_PEG,
        location=(BOTTOM_X + px, -py, PEG_HEIGHT / 2),
    )

# ─── Peg-hole overlays — blind sockets in top half inner face (z=0..PEG_HEIGHT+0.3) ───
peg_hole_depth = PEG_HEIGHT + 0.3
for i, (px, py) in enumerate(PEGS):
    add_overlay(
        f"DBG_PegHole{i}",
        lambda **kw: bpy.ops.mesh.primitive_cylinder_add(
            vertices=24, radius=PEG_HOLE_DIA / 2, depth=peg_hole_depth, **kw),
        COL_PEGHOLE,
        location=(TOP_X + px, py, peg_hole_depth / 2),
    )

# ─── NFC pocket — recessed in bottom's inner face (world z = 0..NFC_DEPTH after flip) ───
add_overlay(
    "DBG_NFCPocket",
    lambda **kw: bpy.ops.mesh.primitive_cylinder_add(
        vertices=48, radius=NFC_DIA / 2, depth=NFC_DEPTH, **kw),
    COL_NFC,
    location=(BOTTOM_X + NFC_POS[0], -NFC_POS[1], NFC_DEPTH / 2),
)

# ─── String hole overlays — one along X through each half (Y mirrored on bottom) ───
# Mid-Z of each half is read from the actual object's world position so the
# overlay sits inside the half rather than guessing.
def _midz(obj):
    return obj.matrix_world.translation.z if obj is not None else 0.0

add_overlay("DBG_StringHole_Top",
    lambda **kw: bpy.ops.mesh.primitive_cylinder_add(
        vertices=24, radius=HOLE_DIA / 2, depth=30, **kw),
    COL_HOLE,
    location=(TOP_X, HOLE_Y, _midz(top)),
    rotation=(0, math.radians(90), 0))

add_overlay("DBG_StringHole_Bottom",
    lambda **kw: bpy.ops.mesh.primitive_cylinder_add(
        vertices=24, radius=HOLE_DIA / 2, depth=30, **kw),
    COL_HOLE,
    location=(BOTTOM_X, -HOLE_Y, _midz(bottom)),
    rotation=(0, math.radians(90), 0))

print("[bead-debug-colors] Bottom=CYAN  Top=BLUE  Decor=MAGENTA")
print("[bead-debug-colors] overlays — Pegs=YELLOW  PegHoles=GREEN  NFC=ORANGE  StringHole=GREEN-cyl")
