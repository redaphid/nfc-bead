"""One-off: top-down hero render of the medallion face (Top + figure).
blender -b print/gymnast_medallion.blend --python _render_face.py -- out.png"""
import bpy, sys, math
out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "face.png"

top = bpy.data.objects.get("Top")
deco = bpy.data.objects.get("Decoration")
bottom = bpy.data.objects.get("Bottom")
if bottom:
    bottom.hide_render = True
cx, cy = top.location.x, top.location.y

cam_d = bpy.data.cameras.new("FaceCam"); cam = bpy.data.objects.new("FaceCam", cam_d)
bpy.context.scene.collection.objects.link(cam)
cam_d.type = "ORTHO"; cam_d.ortho_scale = 22
cam.location = (cx, cy, 60); cam.rotation_euler = (0, 0, 0)
bpy.context.scene.camera = cam

ld = bpy.data.lights.new("L", type="SUN"); ld.energy = 2.0
lt = bpy.data.objects.new("L", ld); bpy.context.scene.collection.objects.link(lt)
lt.rotation_euler = (math.radians(25), math.radians(15), 0)

sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.color_type = "OBJECT"
sc.display.shading.light = "STUDIO"
sc.render.resolution_x = 1000; sc.render.resolution_y = 1000
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print("rendered", out)
