#!/usr/bin/env python3
"""Build an Elegoo Slicer / Bambu Studio .3mf project for the multi-color rezz bead.

Takes the latest STLs from `tmp/latest/` and produces
`tmp/latest/rezz_multicolor.3mf`, a slicer project with:

- `Bottom` as one object on plate 1, filament 1 (red).
- `Top` + `Decoration` merged as one multi-part object on plate 1,
  Top body on filament 1 (red), Decoration on filament 2 (black).
- Parts pre-arranged on the build plate so they import already on the bed
  and ready to slice — no manual positioning, no auto-orient confusion,
  no "raft" appearance from floating parts.

The metadata templates (project_settings.config, slice_info.config, the
content-type / relationships XMLs) are taken from a reference 3MF that
the user has already saved out of Elegoo Slicer for this printer
(default: `tmp/latest/r1_extracted/`). That keeps the printer / process
preset matching whatever the user has dialed in.

Verification: extracts the produced 3MF and checks each part's geometry
matches the source STL (vertex + triangle counts).

Usage:
    python tools/build_rezz_3mf.py
"""

import argparse
import io
import re
import struct
import time
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

# ─── Paths ────────────────────────────────────────────────────────────
REPO_ROOT      = Path(__file__).resolve().parent.parent
TMP_LATEST     = REPO_ROOT / "tmp" / "latest"
TEMPLATE_DIR   = TMP_LATEST / "r1_extracted"     # extracted reference 3MF
DEFAULT_OUT    = TMP_LATEST / "rezz_multicolor.3mf"

# ─── Per-bead config ──────────────────────────────────────────────────
# Each part: (canonical name, source STL filename, extruder index, optional Z offset)
# Extruders are 1-indexed in 3MF. The user's r1.3mf had body on extruder 2 and
# spiral on extruder 1 — keep that mapping so existing material slot assignments
# in their printer profile stay consistent.
PARTS_TOP_ASSEMBLY = [
    # (filename in tmp/latest, displayed_name, extruder, z_offset_mm)
    ("Top.stl",        "Top",        2, 0.0),  # red body sits on the plate
    ("Decoration.stl", "Decoration", 1, 0.0),  # spiral already at z=2.5..3 in the STL — no extra offset
]
PARTS_BOTTOM = [
    ("Bottom.stl", "Bottom", 2, 0.0),  # red body, print-flipped already
]

# Plate placement (Centauri Carbon 2 is 256x256mm). Park bottom and top side-by-side
# near the center of the plate.
PLATE_BOTTOM_XY = (110.0, 128.0)   # mm — center of Bottom on the plate
PLATE_TOP_XY    = (146.0, 128.0)   # mm — center of Top assembly (slightly to the right)


# ─── STL → 3MF mesh conversion ────────────────────────────────────────
def read_binary_stl(path):
    """Parse a binary STL. Return (verts_list, tri_indices_list).

    De-duplicates vertices so the 3MF has compact indices.
    """
    with open(path, "rb") as f:
        f.read(80)
        (num_tris,) = struct.unpack("<I", f.read(4))
        verts_index = {}
        verts = []
        tris = []
        for _ in range(num_tris):
            data = f.read(50)
            if len(data) != 50:
                raise OSError(f"truncated STL at {path}")
            # bytes 0..11 = normal (skip), 12..47 = 3 vertices (3 floats each), 48..49 = attribute
            v_floats = struct.unpack("<9f", data[12:48])
            tri = []
            for i in range(3):
                vx, vy, vz = v_floats[i*3:i*3+3]
                key = (round(vx, 6), round(vy, 6), round(vz, 6))
                idx = verts_index.get(key)
                if idx is None:
                    idx = len(verts)
                    verts_index[key] = idx
                    verts.append((vx, vy, vz))
                tri.append(idx)
            tris.append(tri)
    return verts, tris


def stl_to_3mf_object_xml(verts, tris, object_id, uuid_str):
    """Build the per-object 3D/Objects/<name>.model XML body."""
    out = io.StringIO()
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    out.write('<model unit="millimeter" xml:lang="en-US" '
              'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
              'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
              'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
              'requiredextensions="p">\n')
    out.write(' <metadata name="BambuStudio:3mfVersion">1</metadata>\n')
    out.write(' <resources>\n')
    out.write(f'  <object id="{object_id}" p:UUID="{uuid_str}" type="model">\n')
    out.write('   <mesh>\n')
    out.write('    <vertices>\n')
    for x, y, z in verts:
        out.write(f'     <vertex x="{x:.7f}" y="{y:.7f}" z="{z:.7f}"/>\n')
    out.write('    </vertices>\n')
    out.write('    <triangles>\n')
    for v1, v2, v3 in tris:
        out.write(f'     <triangle v1="{v1}" v2="{v2}" v3="{v3}"/>\n')
    out.write('    </triangles>\n')
    out.write('   </mesh>\n')
    out.write('  </object>\n')
    out.write(' </resources>\n')
    out.write('</model>\n')
    return out.getvalue()


# ─── 3MF assembly ─────────────────────────────────────────────────────
def matrix_to_3mf_str(m):
    """4×4 matrix → 12-element row-major string (3MF transform format)."""
    # 3MF transform is 4 rows of 3 elements each = 12 floats
    # The matrix layout in r1.3mf is: a b c d e f g h i x y z
    # (linear part 3×3 + translation 3) but written as column-major rows.
    return " ".join(f"{v:.9g}" for v in m)


def identity_with_translation(tx, ty, tz):
    """Identity rotation + translation, in the 3MF 12-float row-major form."""
    return [1.0, 0.0, 0.0,
            0.0, 1.0, 0.0,
            0.0, 0.0, 1.0,
            tx,  ty,  tz]


def build_object_model_xml(obj_id, components):
    """Build the parent object XML in 3D/3dmodel.model.

    components is a list of (model_path, child_object_id, transform_12f, uuid).
    """
    lines = [f'  <object id="{obj_id}" p:UUID="{uuid.uuid4()}" type="model">']
    lines.append('   <components>')
    for path, cid, xform, comp_uuid in components:
        xform_str = matrix_to_3mf_str(xform)
        lines.append(f'    <component p:path="{path}" objectid="{cid}" '
                     f'p:UUID="{comp_uuid}" transform="{xform_str}"/>')
    lines.append('   </components>')
    lines.append('  </object>')
    return "\n".join(lines)


def build_3dmodel_model(parent_objects, build_items):
    """Build the top-level 3D/3dmodel.model file.

    parent_objects: list of pre-built object XML chunks (strings) for parents
                    that reference components.
    build_items: list of (object_id, transform_12f, uuid_str) for the build plate.
    """
    out = io.StringIO()
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    out.write('<model unit="millimeter" xml:lang="en-US" '
              'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
              'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
              'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
              'requiredextensions="p">\n')
    for tag in ("Application", "BambuStudio:3mfVersion", "Copyright",
                "CreationDate", "Description", "Designer", "DesignerCover",
                "DesignerUserId", "License", "ModificationDate", "Origin", "Title"):
        if tag == "Application":
            out.write(f' <metadata name="{tag}">rezz-3mf-builder/1.0</metadata>\n')
        elif tag == "BambuStudio:3mfVersion":
            out.write(f' <metadata name="{tag}">1</metadata>\n')
        elif tag == "CreationDate":
            out.write(f' <metadata name="{tag}">{time.strftime("%Y-%m-%d %H:%M:%S")}</metadata>\n')
        else:
            out.write(f' <metadata name="{tag}"></metadata>\n')
    out.write(' <resources>\n')
    for chunk in parent_objects:
        out.write(chunk + "\n")
    out.write(' </resources>\n')
    out.write(' <build>\n')
    for obj_id, xform, uuid_str in build_items:
        xform_str = matrix_to_3mf_str(xform)
        out.write(f'  <item objectid="{obj_id}" p:UUID="{uuid_str}" transform="{xform_str}" '
                  f'printable="1"/>\n')
    out.write(' </build>\n')
    out.write('</model>\n')
    return out.getvalue()


def build_model_settings(top_assembly, bottom):
    """Build Metadata/model_settings.config — per-part extruder + matrix."""
    out = io.StringIO()
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n<config>\n')

    # Top object (multi-part: body + decoration)
    obj_id, parts = top_assembly
    out.write(f'  <object id="{obj_id}">\n')
    out.write('    <metadata key="name" value="rezz_top_assembly"/>\n')
    out.write('    <metadata key="extruder" value="2"/>\n')   # default; overridden per part
    for part_id, name, source_file, matrix_12f, extruder in parts:
        out.write(f'    <part id="{part_id}" subtype="normal_part">\n')
        out.write(f'      <metadata key="name" value="{xml_escape(name)}"/>\n')
        out.write(f'      <metadata key="matrix" value="{matrix_to_3mf_str(matrix_12f)}"/>\n')
        out.write(f'      <metadata key="source_file" value="{xml_escape(source_file)}"/>\n')
        out.write(f'      <metadata key="extruder" value="{extruder}"/>\n')
        out.write('      <mesh_stat edges_fixed="0" degenerate_facets="0" facets_removed="0" '
                  'facets_reversed="0" backwards_edges="0"/>\n')
        out.write('    </part>\n')
    out.write('  </object>\n')

    # Bottom object (single part)
    obj_id_b, parts_b = bottom
    out.write(f'  <object id="{obj_id_b}">\n')
    out.write('    <metadata key="name" value="Bottom"/>\n')
    out.write('    <metadata key="extruder" value="2"/>\n')
    for part_id, name, source_file, matrix_12f, extruder in parts_b:
        out.write(f'    <part id="{part_id}" subtype="normal_part">\n')
        out.write(f'      <metadata key="name" value="{xml_escape(name)}"/>\n')
        out.write(f'      <metadata key="matrix" value="{matrix_to_3mf_str(matrix_12f)}"/>\n')
        out.write(f'      <metadata key="source_file" value="{xml_escape(source_file)}"/>\n')
        out.write(f'      <metadata key="extruder" value="{extruder}"/>\n')
        out.write('      <mesh_stat edges_fixed="0" degenerate_facets="0" facets_removed="0" '
                  'facets_reversed="0" backwards_edges="0"/>\n')
        out.write('    </part>\n')
    out.write('  </object>\n')

    # Plate
    out.write('  <plate>\n')
    out.write('    <metadata key="plater_id" value="1"/>\n')
    out.write('    <metadata key="plater_name" value=""/>\n')
    out.write('    <metadata key="locked" value="false"/>\n')
    out.write('    <metadata key="filament_map_mode" value="Auto For Flush"/>\n')
    out.write('    <metadata key="filament_maps" value="1 1 1 1"/>\n')
    out.write(f'    <model_instance>\n      <metadata key="object_id" value="{obj_id}"/>\n'
              f'      <metadata key="instance_id" value="0"/>\n    </model_instance>\n')
    out.write(f'    <model_instance>\n      <metadata key="object_id" value="{obj_id_b}"/>\n'
              f'      <metadata key="instance_id" value="0"/>\n    </model_instance>\n')
    out.write('  </plate>\n')
    out.write('</config>\n')
    return out.getvalue()


# ─── Main builder ─────────────────────────────────────────────────────
def build(out_path=DEFAULT_OUT, template_dir=TEMPLATE_DIR):
    if not template_dir.is_dir():
        raise SystemExit(f"Template dir missing: {template_dir}\n"
                         f"  Drop a reference .3mf into tmp/latest/ and extract it there, "
                         f"OR adjust TEMPLATE_DIR in build_rezz_3mf.py.")

    # 1. Read STL geometry
    print(f"[3mf] reading STLs from {TMP_LATEST}")
    parts = []   # list of dicts: name, source_path, verts, tris, model_filename
    for fname, dispname, extruder, _zoff in [(PARTS_BOTTOM[0])] + PARTS_TOP_ASSEMBLY:
        stl_path = TMP_LATEST / fname
        if not stl_path.is_file():
            raise SystemExit(f"missing STL: {stl_path}")
        v, t = read_binary_stl(stl_path)
        print(f"  {fname:<24} {len(v):>5} verts  {len(t):>5} tris")
        parts.append({
            "filename":  fname,
            "name":      dispname,
            "extruder":  extruder,
            "stl_path":  stl_path,
            "verts":     v,
            "tris":      t,
            # 3MF object IDs are assigned below
        })

    # 2. Assign 3MF object IDs (parents + children) and UUIDs
    # Layout:
    #   parent object 1 = Top assembly      (id 3)
    #     child Top      (id 1, model file rezz_top_assembly.model:1)
    #     child Decoration (id 2, model file rezz_top_assembly.model:2)
    #   parent object 2 = Bottom            (id 5)
    #     child Bottom   (id 4, model file Bottom.model:4)
    bottom = parts[0]
    top    = parts[1]
    decor  = parts[2]

    bottom["object_id"] = 4
    top["object_id"]    = 1
    decor["object_id"]  = 2
    bottom["parent_id"] = 5
    top["parent_id"]    = 3   # shared parent
    decor["parent_id"]  = 3   # shared parent

    bottom["model_path"] = "/3D/Objects/Bottom.model"
    top["model_path"]    = "/3D/Objects/rezz_top_assembly.model"
    decor["model_path"]  = "/3D/Objects/rezz_top_assembly.model"   # same file, different objectid

    for p in parts:
        p["uuid"] = str(uuid.uuid4())
    bottom["parent_uuid"] = str(uuid.uuid4())
    top["parent_uuid"]    = str(uuid.uuid4())  # used for Top assembly

    # 3. Build per-object 3MF .model XMLs.
    # Bottom is its own file. Top + Decoration share rezz_top_assembly.model.
    bottom_model = stl_to_3mf_object_xml(bottom["verts"], bottom["tris"],
                                          bottom["object_id"], bottom["uuid"])
    # The shared file needs both objects in one resources block.
    top_assembly_model = io.StringIO()
    top_assembly_model.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    top_assembly_model.write('<model unit="millimeter" xml:lang="en-US" '
                              'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
                              'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
                              'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
                              'requiredextensions="p">\n')
    top_assembly_model.write(' <metadata name="BambuStudio:3mfVersion">1</metadata>\n')
    top_assembly_model.write(' <resources>\n')
    for p in (top, decor):
        top_assembly_model.write(f'  <object id="{p["object_id"]}" p:UUID="{p["uuid"]}" type="model">\n')
        top_assembly_model.write('   <mesh>\n')
        top_assembly_model.write('    <vertices>\n')
        for x, y, z in p["verts"]:
            top_assembly_model.write(f'     <vertex x="{x:.7f}" y="{y:.7f}" z="{z:.7f}"/>\n')
        top_assembly_model.write('    </vertices>\n')
        top_assembly_model.write('    <triangles>\n')
        for v1, v2, v3 in p["tris"]:
            top_assembly_model.write(f'     <triangle v1="{v1}" v2="{v2}" v3="{v3}"/>\n')
        top_assembly_model.write('    </triangles>\n')
        top_assembly_model.write('   </mesh>\n')
        top_assembly_model.write('  </object>\n')
    top_assembly_model.write(' </resources>\n')
    top_assembly_model.write('</model>\n')

    # 4. Build top-level 3D/3dmodel.model with parents referencing the children
    #    via <component p:path="..." objectid="N" transform="..."/>
    parent_chunks = []

    # Top assembly parent: Top body at z=0, Decoration at z=0 (geometry already has z=2.5..3.0)
    top_parent_xml = build_object_model_xml(
        top["parent_id"],
        [
            (top["model_path"],   top["object_id"],   identity_with_translation(0, 0, 0), str(uuid.uuid4())),
            (decor["model_path"], decor["object_id"], identity_with_translation(0, 0, 0), str(uuid.uuid4())),
        ],
    )
    parent_chunks.append(top_parent_xml)

    # Bottom parent: just one component
    bottom_parent_xml = build_object_model_xml(
        bottom["parent_id"],
        [
            (bottom["model_path"], bottom["object_id"], identity_with_translation(0, 0, 0), str(uuid.uuid4())),
        ],
    )
    parent_chunks.append(bottom_parent_xml)

    # Build items: place each parent on the plate at its desired XY
    bxy = PLATE_BOTTOM_XY
    txy = PLATE_TOP_XY
    build_items = [
        (top["parent_id"],    identity_with_translation(txy[0], txy[1], 0), str(uuid.uuid4())),
        (bottom["parent_id"], identity_with_translation(bxy[0], bxy[1], 0), str(uuid.uuid4())),
    ]

    main_3dmodel = build_3dmodel_model(parent_chunks, build_items)

    # 5. Build relationships file (3D/_rels/3dmodel.model.rels)
    rels_xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                ' <Relationship Target="/3D/Objects/rezz_top_assembly.model" Id="rel-1" '
                'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
                ' <Relationship Target="/3D/Objects/Bottom.model" Id="rel-2" '
                'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
                '</Relationships>\n')

    # 6. Build model_settings.config (the slicer-side per-part metadata)
    # Matrices: identity for parts (geometry already in correct coords).
    #   Top body is at z=0..2.5
    #   Decoration is at z=2.5..3.0 (per the export's shared-shift fix)
    top_assembly_meta = (
        top["parent_id"],
        [
            (top["object_id"],   top["name"],   str(top["stl_path"]),   identity_with_translation(0, 0, 0), top["extruder"]),
            (decor["object_id"], decor["name"], str(decor["stl_path"]), identity_with_translation(0, 0, 0), decor["extruder"]),
        ],
    )
    bottom_meta = (
        bottom["parent_id"],
        [
            (bottom["object_id"], bottom["name"], str(bottom["stl_path"]), identity_with_translation(0, 0, 0), bottom["extruder"]),
        ],
    )
    model_settings = build_model_settings(top_assembly_meta, bottom_meta)

    # 7. plate_1.json — minimal valid placement
    bottom_xy_min = (bxy[0] - 12.5, bxy[1] - 12.5)
    bottom_xy_max = (bxy[0] + 12.5, bxy[1] + 12.5)
    top_xy_min    = (txy[0] - 12.5, txy[1] - 12.5)
    top_xy_max    = (txy[0] + 12.5, txy[1] + 12.5)
    plate_json = (
        '{\n'
        '  "version": 2,\n'
        '  "bed_type": "textured_plate",\n'
        '  "first_extruder": 0,\n'
        '  "is_seq_print": false,\n'
        '  "nozzle_diameter": 0.4,\n'
        '  "filament_colors": [],\n'
        '  "filament_ids": [],\n'
        '  "bbox_objects": [\n'
        f'    {{"id":{top["parent_id"]}, "name":"rezz_top_assembly", "bbox":[{top_xy_min[0]:.3f},{top_xy_min[1]:.3f},{top_xy_max[0]:.3f},{top_xy_max[1]:.3f}], "area":625.0, "layer_height":0.12}},\n'
        f'    {{"id":{bottom["parent_id"]}, "name":"Bottom", "bbox":[{bottom_xy_min[0]:.3f},{bottom_xy_min[1]:.3f},{bottom_xy_max[0]:.3f},{bottom_xy_max[1]:.3f}], "area":625.0, "layer_height":0.12}}\n'
        '  ]\n'
        '}\n'
    )

    # 8. Boilerplate: [Content_Types].xml, _rels/.rels (use template if available)
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
        ' <Default Extension="png" ContentType="image/png"/>\n'
        ' <Default Extension="gcode" ContentType="text/x.gcode"/>\n'
        '</Types>\n'
    )
    pkg_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
        '</Relationships>\n'
    )

    # Pull printer/process settings from the template, then patch them.
    # The user reported "raft" appearance — that's actually the BRIM
    # (auto_brim, 5mm wide) the user's saved profile has. Disable brim and
    # raft for these tiny press-fit parts; the Centauri Carbon's textured
    # plate has plenty of bed adhesion at this footprint.
    project_settings = None
    proj_path = template_dir / "Metadata" / "project_settings.config"
    if proj_path.is_file():
        project_settings = proj_path.read_text(encoding="utf-8")
        # Patch settings via simple regex (the file is JSON-formatted but with
        # comments/extras in places, safer than full-parse for now).
        patches = {
            "brim_type":    "no_brim",
            "brim_width":   "0",
            "raft_layers":  "0",
        }
        for key, value in patches.items():
            project_settings = re.sub(
                rf'"{key}"\s*:\s*"[^"]*"',
                f'"{key}": "{value}"',
                project_settings,
            )
        print(f"[3mf] patched project_settings: {', '.join(patches.keys())}")

    slice_info = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n  <header>\n'
        '    <header_item key="X-BBL-Client-Type" value="slicer"/>\n'
        '    <header_item key="X-BBL-Client-Name" value="ElegooSlicer"/>\n'
        '  </header>\n</config>\n'
    )
    slice_path = template_dir / "Metadata" / "slice_info.config"
    if slice_path.is_file():
        slice_info = slice_path.read_text(encoding="utf-8")

    # 9. Write the .3mf zip
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", pkg_rels)
        z.writestr("3D/_rels/3dmodel.model.rels", rels_xml)
        z.writestr("3D/3dmodel.model", main_3dmodel)
        z.writestr("3D/Objects/Bottom.model", bottom_model)
        z.writestr("3D/Objects/rezz_top_assembly.model", top_assembly_model.getvalue())
        z.writestr("Metadata/model_settings.config", model_settings)
        z.writestr("Metadata/plate_1.json", plate_json)
        z.writestr("Metadata/slice_info.config", slice_info)
        if project_settings:
            z.writestr("Metadata/project_settings.config", project_settings)

    # 10. Verify by re-reading the zip + parsing the model files
    print(f"\n[3mf] wrote {out_path} ({out_path.stat().st_size} bytes)")
    verify(out_path, parts)
    return out_path


def verify(path, parts):
    """Open the produced 3MF and confirm geometry counts match source STLs."""
    print(f"[3mf] verifying {path.name}...")
    expected_counts = {p["filename"]: (len(p["verts"]), len(p["tris"])) for p in parts}
    with zipfile.ZipFile(path, "r") as z:
        names = z.namelist()
        for required in ("[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model",
                          "3D/_rels/3dmodel.model.rels",
                          "3D/Objects/Bottom.model",
                          "3D/Objects/rezz_top_assembly.model",
                          "Metadata/model_settings.config",
                          "Metadata/plate_1.json"):
            if required not in names:
                raise SystemExit(f"VERIFY FAIL: {required} missing from {path.name}")

        # Check vertex / triangle counts inside the .model files
        for member, _name in (("3D/Objects/Bottom.model", "Bottom"),):
            content = z.read(member).decode("utf-8")
            v = len(re.findall(r"<vertex\s", content))
            t = len(re.findall(r"<triangle\s", content))
            exp_v, exp_t = expected_counts["Bottom.stl"]
            ok = (v == exp_v and t == exp_t)
            print(f"  {member}: {v} verts, {t} tris  (expect {exp_v}/{exp_t})  {'OK' if ok else 'MISMATCH'}")
            if not ok:
                raise SystemExit("VERIFY FAIL: geometry count mismatch")

        # Top assembly has 2 objects in one .model file
        content = z.read("3D/Objects/rezz_top_assembly.model").decode("utf-8")
        v_total = len(re.findall(r"<vertex\s", content))
        t_total = len(re.findall(r"<triangle\s", content))
        exp_v = expected_counts["Top.stl"][0] + expected_counts["Decoration.stl"][0]
        exp_t = expected_counts["Top.stl"][1] + expected_counts["Decoration.stl"][1]
        ok = (v_total == exp_v and t_total == exp_t)
        print(f"  3D/Objects/rezz_top_assembly.model: {v_total} verts, {t_total} tris  "
              f"(expect {exp_v}/{exp_t})  {'OK' if ok else 'MISMATCH'}")
        if not ok:
            raise SystemExit("VERIFY FAIL: top assembly geometry count mismatch")

    print(f"[3mf] OK — {path}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-o", "--out", default=str(DEFAULT_OUT))
    p.add_argument("-t", "--template-dir", default=str(TEMPLATE_DIR))
    args = p.parse_args()
    build(out_path=Path(args.out), template_dir=Path(args.template_dir))


if __name__ == "__main__":
    main()
