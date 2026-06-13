"""Build 6 simplified gymnast beads from regions.json.

SIMPLIFIED recipe — no NFC pocket, no two-half split, no pegs. Each figure is:
  polygon (mm, Y-up)  ->  ngon face  ->  extrude to THICKNESS  ->  drill a
  through-thickness string hole (where regions.json gives one).

Each part is centered on its own XY origin, sitting on z=0 (print orientation
is trivial — flat silhouette on the plate). STLs land in beads/gymnasts/print/,
the .blend alongside, and a top-down preview render in the bead dir.

Run headless:
  "D:\\tools\\blender\\blender.exe" --background --python beads/gymnasts/build_gymnasts.py
"""
import json
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector

HERE      = os.path.dirname(os.path.abspath(__file__))
REGIONS   = os.path.join(HERE, "regions.json")
PRINT_DIR = os.path.join(HERE, "print")
BLEND_OUT = os.path.join(HERE, "gymnasts.blend")
PREVIEW   = os.path.join(HERE, "preview.png")
EPS       = 1e-4


def wipe_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)


def build_figure(name, poly, thickness, hole):
    # drop closing duplicate vertex if the contour wraps onto itself
    if len(poly) > 2 and abs(poly[0][0] - poly[-1][0]) < EPS and abs(poly[0][1] - poly[-1][1]) < EPS:
        poly = poly[:-1]

    bm = bmesh.new()
    verts = [bm.verts.new((float(x), float(y), 0.0)) for x, y in poly]
    face = bm.faces.new(verts)
    bm.normal_update()
    # extrude the flat profile up to `thickness`
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    up = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0.0, 0.0, thickness), verts=up)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)

    if hole is not None:
        drill_hole(obj, hole, thickness)

    # center on its own XY origin, drop to z=0
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    obj.location = (0.0, 0.0, 0.0)
    obj.select_set(False)

    zmin = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
    obj.location.z -= zmin
    bpy.context.view_layer.update()
    return obj


def drill_hole(obj, hole, thickness):
    bpy.ops.mesh.primitive_cylinder_add(
        radius=float(hole["r"]),
        depth=thickness + 4.0,
        location=(float(hole["x"]), float(hole["y"]), thickness / 2.0),
        vertices=48,
    )
    cutter = bpy.context.active_object
    cutter.name = obj.name + "_holecut"
    mod = obj.modifiers.new("hole", type="BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    # weld + consistent normals after the boolean
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.005)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()


def export_stls(objs):
    os.makedirs(PRINT_DIR, exist_ok=True)
    for obj in objs:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        out = os.path.join(PRINT_DIR, obj.name + ".stl")
        bpy.ops.wm.stl_export(filepath=out, export_selected_objects=True,
                              apply_modifiers=True)
        print(f"  exported {out}")


def setup_preview_camera(objs):
    # frame everything from straight above
    xs, ys = [], []
    for o in objs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            xs.append(w.x); ys.append(w.y)
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    span = max(max(xs) - min(xs), max(ys) - min(ys))

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = span * 1.15
    cam = bpy.data.objects.new("Cam", cam_data)
    cam.location = (cx, cy, 120.0)
    cam.rotation_euler = (0, 0, 0)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    light_data = bpy.data.lights.new("Sun", type="SUN")
    light_data.energy = 4.0
    light = bpy.data.objects.new("Sun", light_data)
    light.location = (cx, cy, 100)
    light.rotation_euler = (math.radians(20), math.radians(10), 0)
    bpy.context.scene.collection.objects.link(light)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1000
    scene.render.film_transparent = False
    scene.world.color = (0.9, 0.9, 0.9) if scene.world else None
    scene.render.filepath = PREVIEW
    bpy.ops.render.render(write_still=True)
    print(f"  rendered {PREVIEW}")


def main():
    data = json.load(open(REGIONS))
    thickness = data["thickness_mm"]
    figs = data["figures"]
    print(f"Building {len(figs)} gymnast beads @ {thickness}mm thick")

    wipe_scene()
    objs = []
    GRID_COLS = 3
    SPACING = 30.0
    for i, fig in enumerate(figs):
        obj = build_figure(fig["name"], fig["polygon"], thickness, fig.get("hole"))
        # grid layout for scene + preview
        col = i % GRID_COLS
        row = i // GRID_COLS
        obj.location.x += col * SPACING
        obj.location.y -= row * SPACING
        objs.append(obj)
        h = fig.get("hole")
        print(f"  {fig['name']}: {fig['width_mm']:.1f}x{fig['height_mm']:.1f}mm "
              f"hole={'yes' if h else 'no'}  verts={len(obj.data.vertices)}")

    export_stls(objs)
    setup_preview_camera(objs)

    bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
    print(f"  saved {BLEND_OUT}")
    print("DONE")


if __name__ == "__main__":
    main()
