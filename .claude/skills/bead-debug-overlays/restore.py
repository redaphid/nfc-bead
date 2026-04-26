"""Restore production "true" colors and wipe debug overlays.

Companion to recolor.py. Run this when you want to leave debug mode and
return the scene to what the build script produced (the colors the
slicer / final viewer would see).

Idempotent: safe to run when there are no overlays or when overlays
are already gone.

Edit the CONFIG block to match the bead's production palette. Defaults
are red bodies + black decoration, the most common two-color setup;
override per charm in `build_<charm>.py`.
"""
import bpy

# ─── CONFIG — mirror the build_<name>.py material colors ───
COL_BOTTOM_PROD  = (0.85, 0.10, 0.10, 1)   # red
COL_TOP_PROD     = (0.85, 0.10, 0.10, 1)   # red
COL_DECOR_PROD   = (0.05, 0.05, 0.05, 1)   # black

DECORATION_NAME = "Decoration"   # canonical project name


def repaint(obj, rgba, name):
    obj.data.materials.clear()
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.45
    bsdf.inputs["Metallic"].default_value = 0.0
    obj.data.materials.append(m)


# ─── Wipe all DBG_* overlay objects (peg widgets, NFC, string hole, etc) ───
_protected = {"Bottom", "Top", DECORATION_NAME}
removed = 0
for obj in list(bpy.data.objects):
    if obj.name.startswith("DBG_") and obj.name not in _protected:
        bpy.data.objects.remove(obj, do_unlink=True)
        removed += 1

# ─── Restore production materials on the printable parts ───
for name, rgba, mat_name in [
    ("Bottom",        COL_BOTTOM_PROD, "RedMat_Bottom"),
    ("Top",           COL_TOP_PROD,    "RedMat_Top"),
    (DECORATION_NAME, COL_DECOR_PROD,  "BlackMat_Spiral"),
]:
    obj = bpy.data.objects.get(name)
    if obj is None:
        continue
    repaint(obj, rgba, mat_name)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_flat()

print(f"[bead-debug-overlays] restored production palette ({removed} overlay(s) removed)")
print("  Bottom + Top = RED, Decor = BLACK")
