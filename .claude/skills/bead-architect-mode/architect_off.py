"""Strip the 'architect' aesthetic from the current scene.

Removes everything `architect_on.py` adds — MA_LineArt GP, MA_*
materials on bodies, MA_* lights, optional MA_GraphPaper plate — and
neutralizes the world shader so the scene is back to a non-styled
state without touching the bead geometry.

Idempotent. Safe to run when nothing is on (no-op).

Does NOT touch DBG_* debug overlays or production materials. To return
to production palette, run `restore.py` afterwards.

Note: STL export selects the printable parts by canonical name
(`Bottom`, `Top`, `Decoration`), so `architect_on.py`'s MA_* extras
are already invisible to the export pipeline. This script exists for
cases where the user wants the scene visually clean without exporting.
"""
import bpy

# ─── Remove MA_ objects (GP line-art, lights, optional plate) ──────────
removed_objs = []
for obj in list(bpy.data.objects):
    if obj.name.startswith("MA_"):
        removed_objs.append(obj.name)
        bpy.data.objects.remove(obj, do_unlink=True)

# ─── Drop MA_ materials from any printable body that's still wearing one ──
def _strip_material(obj):
    if obj is None or obj.type != 'MESH':
        return
    keep = [m for m in obj.data.materials if m and not m.name.startswith("MA_")]
    obj.data.materials.clear()
    for m in keep:
        obj.data.materials.append(m)

for name in ("Bottom", "Top", "Decoration"):
    _strip_material(bpy.data.objects.get(name))

# Also drop unused MA_ materials from the data block list
removed_mats = []
for m in list(bpy.data.materials):
    if m.name.startswith("MA_") and m.users == 0:
        removed_mats.append(m.name)
        bpy.data.materials.remove(m)

# ─── Reset world shader to a neutral mid-gray so the scene isn't styled ──
world = bpy.context.scene.world
if world:
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld"); out.location = (240, 0)
    bg  = nt.nodes.new("ShaderNodeBackground");  bg.location  = (0, 0)
    bg.inputs["Color"].default_value    = (0.5, 0.5, 0.5, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

# ─── Kill any animation on the camera rig (orbit, wobble, dolly) ───────
for name in ("CameraPivot", "Camera"):
    o = bpy.data.objects.get(name)
    if o and o.animation_data:
        o.animation_data_clear()

print(f"[architect_off] removed {len(removed_objs)} MA_ object(s), "
      f"{len(removed_mats)} unused MA_ material(s); world reset to neutral; "
      f"camera animation cleared.")
print("  Production colors? Run restore.py.")
