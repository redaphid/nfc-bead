#!/usr/bin/env python3
"""Wrap ONE arbitrary STL in a slicer-ready Elegoo/Orca 3MF using a reference
template (default tmp/latest/slicer_template_06). Generic companion to
build_3mf.py, which is bead-specific (Bottom/Top/Decoration).

    python tools/build_3mf_single.py part.stl -o out.3mf --extruder 3 --xy 128,128

Mesh coordinates are kept as-is; the part is translated so its XY bbox centre
lands on --xy and its z-min on the plate.
"""
import argparse, json, re, sys, uuid, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_3mf import (read_binary_stl, stl_to_3mf_object_xml, build_object_model_xml,
                       build_3dmodel_model, identity_with_translation, matrix_to_3mf_str)

REPO = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = REPO / "tmp" / "latest" / "slicer_template_06"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("stl"); p.add_argument("-o", "--out", required=True)
    p.add_argument("-t", "--template-dir", default=str(DEFAULT_TEMPLATE))
    p.add_argument("--extruder", type=int, default=1, help="1-based filament slot")
    p.add_argument("--xy", default="128,128", help="plate centre for the part, mm")
    p.add_argument("--name", default=None)
    p.add_argument("--brim", choices=["outer_only", "no_brim", "auto_brim"], default=None)
    p.add_argument("--brim-width", type=float, default=None)
    p.add_argument("--bed-temp", type=int, default=None)
    p.add_argument("--wall-loops", type=int, default=None)
    p.add_argument("--infill", default=None, help="e.g. 20%%")
    p.add_argument("--layer-height", type=float, default=None)
    p.add_argument("--skirt-loops", type=int, default=None)
    a = p.parse_args()

    tmpl = Path(a.template_dir); stl = Path(a.stl)
    name = a.name or stl.stem
    verts, tris = read_binary_stl(stl)
    xs=[v[0] for v in verts]; ys=[v[1] for v in verts]; zs=[v[2] for v in verts]
    cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; zmin=min(zs)
    px, py = (float(s) for s in a.xy.split(","))
    xform = identity_with_translation(px-cx, py-cy, -zmin)

    obj_path = f"/3D/Objects/{name}.model"
    mesh_xml = stl_to_3mf_object_xml(verts, tris, 1, str(uuid.uuid4()))
    parent = build_object_model_xml(2, [(obj_path, 1, identity_with_translation(0,0,0), str(uuid.uuid4()))])
    model_xml = build_3dmodel_model([parent], [(2, xform, str(uuid.uuid4()))])

    ms = ['<?xml version="1.0" encoding="UTF-8"?>', '<config>', '  <object id="2">',
          f'    <metadata key="name" value="{name}"/>', f'    <metadata key="extruder" value="{a.extruder}"/>',
          '    <part id="1" subtype="normal_part">', f'      <metadata key="name" value="{name}"/>',
          '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>',
          f'      <metadata key="source_file" value="{stl.name}"/>', f'      <metadata key="extruder" value="{a.extruder}"/>',
          '      <mesh_stat edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>',
          '    </part>', '  </object>', '  <plate>', '    <metadata key="plater_id" value="1"/>',
          '    <metadata key="plater_name" value=""/>', '    <metadata key="locked" value="false"/>',
          '    <metadata key="filament_map_mode" value="Auto For Flush"/>', '    <metadata key="filament_maps" value="1 1 1 1"/>',
          '    <model_instance>', '      <metadata key="object_id" value="2"/>', '      <metadata key="instance_id" value="0"/>',
          '    </model_instance>', '  </plate>', '</config>', '']
    model_settings = "\n".join(ms)

    ps = json.loads((tmpl/"Metadata"/"project_settings.config").read_text(encoding="utf-8"))
    if a.brim: ps["brim_type"] = a.brim
    if a.brim_width is not None: ps["brim_width"] = str(a.brim_width)
    if a.wall_loops is not None: ps["wall_loops"] = str(a.wall_loops)
    if a.infill: ps["sparse_infill_density"] = a.infill
    if a.skirt_loops is not None: ps["skirt_loops"] = str(a.skirt_loops)
    if a.layer_height is not None:
        ps["layer_height"] = str(a.layer_height); ps["initial_layer_print_height"] = str(a.layer_height)
    if a.bed_temp is not None:
        for k in list(ps):
            if re.search(r"(plate_temp|bed_temperature)", k) and isinstance(ps[k], list):
                ps[k] = [str(a.bed_temp)]*len(ps[k])
    nozzle = float(ps.get("nozzle_diameter", ["0.4"])[0])
    plate = {"bbox_all":[px-(max(xs)-cx),py-(max(ys)-cy),px+(max(xs)-cx),py+(max(ys)-cy)],
             "bbox_objects":[{"area":0,"bbox":[px-(max(xs)-cx),py-(max(ys)-cy),px+(max(xs)-cx),py+(max(ys)-cy)],"id":2,"layer_height":float(ps["layer_height"]),"name":name}],
             "bed_type":"textured_plate","filament_colors":[],"filament_ids":[],"first_extruder":a.extruder-1,
             "is_seq_print":False,"nozzle_diameter":nozzle,"version":2}

    ct = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
          ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
          ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n</Types>\n')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n')
    mrels = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
             f' <Relationship Target="{obj_path}" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n')

    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct); z.writestr("_rels/.rels", rels)
        z.writestr("3D/_rels/3dmodel.model.rels", mrels); z.writestr("3D/3dmodel.model", model_xml)
        z.writestr(obj_path.lstrip("/"), mesh_xml); z.writestr("Metadata/model_settings.config", model_settings)
        z.writestr("Metadata/project_settings.config", json.dumps(ps, indent=4))
        z.writestr("Metadata/plate_1.json", json.dumps(plate))
        si = tmpl/"Metadata"/"slice_info.config"
        if si.is_file(): z.writestr("Metadata/slice_info.config", si.read_bytes())
    print(f"[3mf] {out}  {len(verts)} verts / {len(tris)} tris  extruder {a.extruder}  at ({px},{py})  "
          f"size {max(xs)-min(xs):.1f} x {max(ys)-min(ys):.1f} x {max(zs)-zmin:.1f}  nozzle {nozzle}  "
          f"brim {ps['brim_type']}/{ps['brim_width']}  walls {ps['wall_loops']}  infill {ps['sparse_infill_density']}  "
          f"bed {ps.get('textured_plate_temp_initial_layer')}  layer {ps['layer_height']}")

if __name__ == "__main__":
    main()
