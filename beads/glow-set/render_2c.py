"""Render a two-colour glow bead: glow-green body, black raised figure.

An honest picture of the EXPORTED STLs, not a redrawing of the source polygons.
The 2D previews in this folder (preview_shapes.py, preview_talismans.py) draw
the string hole as a disc punched through the FACE, which is not where the hole
actually is - it runs side-to-side through the body. Loading the real meshes
avoids inventing that kind of artefact: whatever this renders is what was
exported.

Run:
  BEAD_DIR=print/quatrefoil24-2c OUT=tmp/x.png \\
    blender.exe -b --gpu-backend opengl --python beads/glow-set/render_2c.py

--gpu-backend opengl matters: Blender 5.0 defaults to Vulkan, which hangs on
startup in a headless agent shell.
"""
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() \
       else r"D:\Projects\nfc-bead\beads\glow-set"

BEAD_DIR = os.environ.get("BEAD_DIR", "print/quatrefoil24-2c")
if not os.path.isabs(BEAD_DIR):
    BEAD_DIR = os.path.join(HERE, BEAD_DIR)
OUT = os.environ.get("OUT", os.path.join(HERE, "tmp_2c.png"))
RES = int(os.environ.get("RES", "760"))
LABEL = os.environ.get("LABEL", "")

GLOW = (0.22, 0.95, 0.42, 1.0)      # strontium-aluminate green
BLACK = (0.02, 0.02, 0.025, 1.0)


def wipe():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)


def mat(name, rgba, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.55
    if emit:
        # glow PLA reads as a lit surface even in daylight; a little emission
        # keeps the green from going muddy under a single key light
        bsdf.inputs["Emission Color"].default_value = rgba
        bsdf.inputs["Emission Strength"].default_value = emit
    return m


def load(fn, material):
    path = os.path.join(BEAD_DIR, fn)
    if not os.path.isfile(path):
        return None
    bpy.ops.wm.stl_import(filepath=path)
    o = bpy.context.selected_objects[0]
    o.data.materials.append(material)
    return o


def main():
    wipe()
    glow = mat("Glow", GLOW, emit=0.35)
    black = mat("Black", BLACK)

    top = load("Top.stl", glow)
    deco = load("Decoration.stl", black)
    if top is None:
        raise SystemExit("no Top.stl in %s" % BEAD_DIR)
    if deco is None:
        print("WARNING: no Decoration.stl - this is a single-colour bead")

    # frame the bead from its real bounds rather than a hardcoded radius
    xs = [ (top.matrix_world @ v.co) for v in top.data.vertices ]
    r = max(max(abs(v.x) for v in xs), max(abs(v.y) for v in xs))

    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'          # headless: no GPU compute context
    scene.cycles.samples = 48
    scene.render.resolution_x = RES
    scene.render.resolution_y = RES
    scene.render.film_transparent = False
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = \
        (0.05, 0.05, 0.06, 1.0)

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = r * 2.35
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    # slight tilt so the 0.5mm relief casts a visible shadow and reads as
    # raised; straight-on would flatten it into a decal
    tilt = math.radians(18)
    d = 60.0
    cam.location = (0, -d * math.sin(tilt), d * math.cos(tilt) + 1.5)
    cam.rotation_euler = (tilt, 0, 0)
    scene.camera = cam

    for loc, energy in (((-28, -22, 40), 9000), ((26, -14, 26), 3500)):
        lamp = bpy.data.lights.new("L", type='AREA')
        lamp.energy = energy
        lamp.size = 26
        o = bpy.data.objects.new("L", lamp)
        o.location = loc
        scene.collection.objects.link(o)
        o.rotation_euler = (math.atan2(math.hypot(loc[0], loc[1]), loc[2]),
                            0, math.atan2(loc[1], loc[0]) + math.pi / 2)

    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    scene.render.filepath = OUT
    bpy.ops.render.render(write_still=True)
    print("rendered -> %s%s" % (OUT, (" [%s]" % LABEL) if LABEL else ""))


if __name__ == "__main__":
    main()
