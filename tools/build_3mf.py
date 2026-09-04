#!/usr/bin/env python3
"""Build an Elegoo Slicer / Bambu Studio .3mf project for a multi-color NFC bead.

Takes the latest STLs from `tmp/latest/` and produces
`tmp/latest/bead_multicolor.3mf`, a slicer project with:

- `Bottom` as one object on plate 1, filament 1 (red).
- `Top` + `Decoration` merged as one multi-part object on plate 1,
  Top body on filament 1 (red), Decoration on filament 2 (black).
- Parts pre-arranged on the build plate so they import already on the bed
  and ready to slice — no manual positioning, no auto-orient confusion,
  no "raft" appearance from floating parts.

The metadata templates (project_settings.config, slice_info.config, the
content-type / relationships XMLs) are taken from a reference 3MF that
the user has already saved out of Elegoo Slicer for this printer
(default: `tmp/latest/slicer_template/`). That keeps the printer / process
preset matching whatever the user has dialed in.

Verification: extracts the produced 3MF and checks each part's geometry
matches the source STL (vertex + triangle counts).

Usage:
    python tools/build_3mf.py
"""

import argparse
import io
import json
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
TEMPLATE_DIR   = TMP_LATEST / "slicer_template"     # extracted reference 3MF

# Producer string the slicer sees. Elegoo Slicer warns "the 3mf file you are
# importing may be incompatible" when this names a tool it does not recognise -
# and a package it treats as foreign may also ignore the embedded
# project_settings, silently dropping the brim and reproducing the very failure
# the template mechanism exists to prevent. So adopt the template's own
# Application string when one is available.
PRODUCER = "nfc-bead-3mf-builder/1.0"
DEFAULT_OUT    = TMP_LATEST / "bead_multicolor.3mf"

# ─── Per-bead config ──────────────────────────────────────────────────
# Each part: (canonical name, source STL filename, extruder index, optional Z offset)
# Extruders are 1-indexed in 3MF. Default mapping: body on extruder 2, decoration
# on extruder 1 — adjust to match the slicer profile the reference template was
# saved from so material slot assignments stay consistent.
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
    # The 3MF transform layout is: a b c d e f g h i x y z
    # (linear part 3×3 + translation 3) written as column-major rows.
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
            out.write(f' <metadata name="{tag}">{PRODUCER}</metadata>\n')
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


def build_model_settings(top_assembly, bottom, body_extruder=2):
    """Build Metadata/model_settings.config — per-part extruder + matrix."""
    out = io.StringIO()
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n<config>\n')

    # Top object (multi-part: body + decoration)
    obj_id, parts = top_assembly
    out.write(f'  <object id="{obj_id}">\n')
    out.write('    <metadata key="name" value="top_assembly"/>\n')
    out.write(f'    <metadata key="extruder" value="{body_extruder}"/>\n')   # default; overridden per part
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
    out.write(f'    <metadata key="extruder" value="{body_extruder}"/>\n')
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
def _patch_array_element(text, key, index, value, label):
    """Replace ONE element of a per-filament array, preserving the others.

    Used for filament_colour, where the point is to make a slot's colour
    visible in the slicer preview. A silent no-op here would ship a preview
    showing the template's colour while the log claims otherwise, so a miss is
    fatal rather than ignored.
    """
    m = re.search(rf'"{key}"\s*:\s*\[([^\]]*)\]', text)
    if not m:
        raise SystemExit(f"[3mf] {label}: key {key!r} not found in template.")
    elems = re.findall(r'"([^"]*)"', m.group(1))
    if index >= len(elems):
        raise SystemExit(
            f"[3mf] {label}: slot {index + 1} is out of range - the template "
            f"profile only defines {len(elems)} filament slots. Load the "
            f"filament in the slicer and re-save the reference 3MF.")
    elems[index] = value
    body = ",\n        ".join(f'"{e}"' for e in elems)
    return text[:m.start()] + f'"{key}": [\n        {body}\n    ]' + text[m.end():]


def _template_nozzle(template_dir):
    """Nozzle diameter recorded in the template's project_settings, or None.

    plate_1.json carries its OWN nozzle_diameter, separate from
    project_settings. It was hardcoded 0.4 here, which meant that dropping in a
    correct 0.6mm template still emitted a 0.4mm plate and handed the slicer two
    different answers inside one package. Read it from the template so the two
    always agree, and let --nozzle-diameter override when they must not.
    """
    f = template_dir / "Metadata" / "project_settings.config"
    if not f.is_file():
        return None
    try:
        v = json.loads(f.read_text(encoding="utf-8")).get("nozzle_diameter")
    except Exception:
        return None
    if isinstance(v, list):
        v = v[0] if v else None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build(out_path=DEFAULT_OUT, template_dir=TEMPLATE_DIR, no_brim=False,
          force_brim=False,
          body_extruder=2, keep_cooling=False, decoration_extruder=1,
          body_colour=None, bottom_xy=None, top_xy=None,
          nozzle_diameter=None):
    if not template_dir.is_dir():
        raise SystemExit(f"Template dir missing: {template_dir}\n"
                         f"  Drop a reference .3mf into tmp/latest/ and extract it there, "
                         f"OR adjust TEMPLATE_DIR in build_3mf.py.")

    # 0. Adopt the reference slicer's producer string (see PRODUCER above).
    global PRODUCER
    _tmpl_model = template_dir / "3D" / "3dmodel.model"
    if _tmpl_model.is_file():
        _m = re.search(r'<metadata name="Application">([^<]+)</metadata>',
                       _tmpl_model.read_text(encoding="utf-8", errors="replace"))
        if _m:
            PRODUCER = _m.group(1).strip()
            print(f"[3mf] producer adopted from template: {PRODUCER}")

    # A two-colour bead whose two parts name the SAME slot prints as one
    # colour, and nothing downstream would complain - the 3MF is valid, it just
    # silently loses the decoration. Catch it here.
    if (TMP_LATEST / "Decoration.stl").is_file() \
            and body_extruder == decoration_extruder:
        raise SystemExit(
            f"[3mf] body and decoration are both on slot {body_extruder}. This "
            f"bead has a Decoration.stl, so that would print it as a single "
            f"colour. Pass --body-extruder / --decoration-extruder.")

    # 1. Read STL geometry
    print(f"[3mf] reading STLs from {TMP_LATEST}")
    parts = []   # list of dicts: name, source_path, verts, tris, model_filename
    for fname, dispname, extruder, _zoff in [(PARTS_BOTTOM[0])] + PARTS_TOP_ASSEMBLY:
        stl_path = TMP_LATEST / fname
        if not stl_path.is_file():
            # Decoration is optional - a single-filament bead has no accent
            # part. Bottom and Top remain required.
            if fname == "Decoration.stl":
                print(f"  {fname:<24} absent - single-filament bead")
                continue
            raise SystemExit(f"missing STL: {stl_path}")
        v, t = read_binary_stl(stl_path)
        print(f"  {fname:<24} {len(v):>5} verts  {len(t):>5} tris")
        parts.append({
            "filename":  fname,
            "name":      dispname,
            # Decoration takes the accent slot and the body takes its own, so
            # each names the slot actually loaded with that colour. The
            # per-part default in PARTS_* is only a fallback.
            "extruder":  (decoration_extruder if dispname == "Decoration"
                          else body_extruder),
            "stl_path":  stl_path,
            "verts":     v,
            "tris":      t,
            # 3MF object IDs are assigned below
        })

    # 2. Assign 3MF object IDs (parents + children) and UUIDs
    # Layout:
    #   parent object 1 = Top assembly      (id 3)
    #     child Top      (id 1, model file top_assembly.model:1)
    #     child Decoration (id 2, model file top_assembly.model:2)
    #   parent object 2 = Bottom            (id 5)
    #     child Bottom   (id 4, model file Bottom.model:4)
    bottom = parts[0]
    top    = parts[1]
    decor  = parts[2] if len(parts) > 2 else None

    bottom["object_id"] = 4
    top["object_id"]    = 1
    bottom["parent_id"] = 5
    top["parent_id"]    = 3   # shared parent
    if decor is not None:
        decor["object_id"]  = 2
        decor["parent_id"]  = 3   # shared parent
    # Everything downstream iterates top_children, so a two-part (single
    # filament) bead and a three-part (body + inscription) bead share a path.
    top_children = [top] if decor is None else [top, decor]

    bottom["model_path"] = "/3D/Objects/Bottom.model"
    top["model_path"]    = "/3D/Objects/top_assembly.model"
    if decor is not None:
        decor["model_path"] = "/3D/Objects/top_assembly.model"  # same file, different objectid

    for p in parts:
        p["uuid"] = str(uuid.uuid4())
    bottom["parent_uuid"] = str(uuid.uuid4())
    top["parent_uuid"]    = str(uuid.uuid4())  # used for Top assembly

    # 3. Build per-object 3MF .model XMLs.
    # Bottom is its own file. Top + Decoration share top_assembly.model.
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
    for p in top_children:
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
        [(p["model_path"], p["object_id"], identity_with_translation(0, 0, 0),
          str(uuid.uuid4())) for p in top_children],
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
    # Defaults park a single bead's two halves side by side. A ganged plate
    # from make_plate.py hands us two ROWS instead, which are far wider than
    # that 36mm gap, so those callers pass explicit centres.
    def _xy_span(vlist):
        xs = [v[0] for v in vlist]
        ys = [v[1] for v in vlist]
        return (max(xs) - min(xs)), (max(ys) - min(ys))

    bw, bh = _xy_span(bottom["verts"])
    _tv = [v for p in parts if p is not bottom for v in p["verts"]] or bottom["verts"]
    tw, th = _xy_span(_tv)

    bxy = bottom_xy or PLATE_BOTTOM_XY
    txy = top_xy or PLATE_TOP_XY

    # The defaults park a single bead's two halves 36mm apart in X. A ganged
    # plate from make_plate.py is a whole ROW, far wider than that, so the two
    # blocks land on top of each other. The slicer then refuses the file with
    # only "Slic3r::CLI::run found error" to show for it - a silent unsliceable
    # 3MF, which cost a long debugging detour. Auto-stack them in Y instead.
    if bottom_xy is None and top_xy is None and (bw + tw) / 2.0 > abs(txy[0] - bxy[0]):
        gap = 12.0
        cx, cy = 128.0, 128.0
        bxy = (cx, cy - (bh + gap) / 2.0)
        txy = (cx, cy + (th + gap) / 2.0)
        print(f"[3mf] blocks are {bw:.1f} and {tw:.1f}mm wide - the {abs(PLATE_TOP_XY[0]-PLATE_BOTTOM_XY[0]):.0f}mm "
              f"default gap would overlap them; stacking in Y instead")

    # Refuse rather than emit a 3MF the slicer will reject without saying why.
    if abs(txy[0] - bxy[0]) < (bw + tw) / 2.0 and abs(txy[1] - bxy[1]) < (bh + th) / 2.0:
        raise SystemExit(
            f"[3mf] REFUSING: Bottom ({bw:.1f}x{bh:.1f}mm at {bxy}) and Top "
            f"({tw:.1f}x{th:.1f}mm at {txy}) overlap on the plate. The slicer "
            f"would reject this with no useful message. Pass --bottom-xy/--top-xy "
            f"further apart.")

    print(f"[3mf] placing Bottom at {bxy}, Top assembly at {txy}")
    build_items = [
        (top["parent_id"],    identity_with_translation(txy[0], txy[1], 0), str(uuid.uuid4())),
        (bottom["parent_id"], identity_with_translation(bxy[0], bxy[1], 0), str(uuid.uuid4())),
    ]

    main_3dmodel = build_3dmodel_model(parent_chunks, build_items)

    # 5. Build relationships file (3D/_rels/3dmodel.model.rels)
    rels_xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                ' <Relationship Target="/3D/Objects/top_assembly.model" Id="rel-1" '
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
        [(p["object_id"], p["name"], str(p["stl_path"]),
          identity_with_translation(0, 0, 0), p["extruder"]) for p in top_children],
    )
    bottom_meta = (
        bottom["parent_id"],
        [
            (bottom["object_id"], bottom["name"], str(bottom["stl_path"]), identity_with_translation(0, 0, 0), bottom["extruder"]),
        ],
    )
    model_settings = build_model_settings(top_assembly_meta, bottom_meta,
                                          body_extruder=body_extruder)

    # 7. plate_1.json — minimal valid placement
    bottom_xy_min = (bxy[0] - 12.5, bxy[1] - 12.5)
    bottom_xy_max = (bxy[0] + 12.5, bxy[1] + 12.5)
    top_xy_min    = (txy[0] - 12.5, txy[1] - 12.5)
    top_xy_max    = (txy[0] + 12.5, txy[1] + 12.5)
    nozzle_d = nozzle_diameter or _template_nozzle(template_dir) or 0.4

    plate_json = (
        '{\n'
        '  "version": 2,\n'
        '  "bed_type": "textured_plate",\n'
        '  "first_extruder": 0,\n'
        '  "is_seq_print": false,\n'
        f'  "nozzle_diameter": {nozzle_d},\n'
        '  "filament_colors": [],\n'
        '  "filament_ids": [],\n'
        '  "bbox_objects": [\n'
        f'    {{"id":{top["parent_id"]}, "name":"top_assembly", "bbox":[{top_xy_min[0]:.3f},{top_xy_min[1]:.3f},{top_xy_max[0]:.3f},{top_xy_max[1]:.3f}], "area":625.0, "layer_height":0.12}},\n'
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
    # The slicer's own packages carry plate previews and reference them from
    # _rels/.rels. Shipping them (copied from the template) keeps the package
    # shaped like slicer output rather than like a foreign file.
    thumbs = []
    for _fn, _rid, _rt in (
        ("plate_1.png", "rel-2",
         "http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail"),
        ("plate_1.png", "rel-4",
         "http://schemas.bambulab.com/package/2021/cover-thumbnail-middle"),
        ("plate_1_small.png", "rel-5",
         "http://schemas.bambulab.com/package/2021/cover-thumbnail-small"),
    ):
        if (template_dir / "Metadata" / _fn).is_file():
            thumbs.append((_fn, _rid, _rt))

    pkg_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
        + ''.join(' <Relationship Target="/Metadata/%s" Id="%s" Type="%s"/>\n'
                  % (fn, rid, rt) for fn, rid, rt in thumbs)
        + '</Relationships>\n'
    )

    # Pull printer/process settings from the template, then patch them.
    # BRIM POLICY. This used to force no_brim, on the reasoning that the brim
    # merely looked like an unwanted raft and the textured plate had adhesion
    # to spare. That was a cosmetic judgement and the evidence went the other
    # way: on 2026-09-02 a ~30mm single-filament talisman sliced WITHOUT a brim
    # lifted, was dragged by the nozzle and smeared, while the medallion
    # printed from a profile carrying auto_brim/5mm came out clean. The vault
    # had this logged as an unresolved conflict ("add a brim" vs the
    # PRINT_GUIDE's "no brim"); this is the resolution.
    # Default is now to KEEP whatever the reference template used. Pass
    # --no-brim to force it off.
    project_settings = None
    proj_path = template_dir / "Metadata" / "project_settings.config"
    if proj_path.is_file():
        project_settings = proj_path.read_text(encoding="utf-8")
        # Patch settings via simple regex (the file is JSON-formatted but with
        # comments/extras in places, safer than full-parse for now).
        # Z-SEAM. PRINT_LOG v5c: with seam_position=aligned the slicer put the
        # seam on the same XY every layer and compounded it into a visible
        # stringy mass around ONE peg socket - deformed bores that will not
        # take a peg at 0.05mm clearance. Random spreads the artefact around
        # the perimeter. The log calls this the single setting most likely to
        # ruin a print, so it is forced here rather than left to the template.
        patches = {"raft_layers": "0", "seam_position": "random"}

        # COOLING. The template ships close_fan_the_first_x_layers=1 and
        # full_fan_speed_layer=0, so part cooling jumps straight to 100% from
        # layer 2 - confirmed live on the quatrefoil print, where ModelFan read
        # 232-250 of 255 from layer 2 on. On a small flat PLA slab that is a
        # textbook edge-curl driver: the upper layers contract hard while the
        # first layer is still pinned to the plate, and the edges lift. These
        # beads are flat slabs with no real overhangs, so the aggressive early
        # cooling buys nothing; overhang_fan_speed still covers the string-hole
        # bridge. Hold the fan off for 3 layers, then ramp to full by layer 5.
        array_patches = {}
        if not keep_cooling:
            array_patches["close_fan_the_first_x_layers"] = "3"
            array_patches["full_fan_speed_layer"] = "5"

        if no_brim:
            patches["brim_type"] = "no_brim"
            patches["brim_width"] = "0"
        elif force_brim:
            # AUTO IS NOT ON. auto_brim lets the slicer decide per object, and
            # for a compact 20mm slab it routinely decides NO brim - so the
            # profile reads "brim 5mm" while the part prints with none. On
            # 2026-09-04 a Top came off the plate WARPED and would not snap;
            # the Top is the half whose first layer is perforated by three
            # 2.6mm socket mouths plus their funnels, so it has markedly less
            # bed contact than the solid Bottom and lifts first. A lifted edge
            # is also what the nozzle catches on, which is how a warp becomes a
            # knocked-off part and then a blob on the hotend. outer_only puts a
            # brim on every object unconditionally.
            patches["brim_type"] = "outer_only"
            patches["brim_width"] = "5"
        for key, value in patches.items():
            project_settings, n = re.subn(
                rf'"{key}"\s*:\s*"[^"]*"',
                f'"{key}": "{value}"',
                project_settings,
            )
            if n == 0:
                raise SystemExit(
                    f"[3mf] patch {key!r} matched NOTHING. It is probably an "
                    f"array-valued key - put it in array_patches, not patches. "
                    f"A silent no-op here ships the template's value while the "
                    f"log claims it was patched.")

        # Array-valued keys are per-filament: "key": [ "v", "v", "v", "v" ].
        # The scalar regex above cannot touch them - it matches nothing and
        # exits cleanly, which would report a patch that never happened. These
        # are rewritten separately, preserving the element count.
        for key, value in array_patches.items():
            m = re.search(rf'"{key}"\s*:\s*\[([^\]]*)\]', project_settings)
            if not m:
                raise SystemExit(f"[3mf] array patch {key!r} matched NOTHING.")
            count = len(re.findall(r'"[^"]*"', m.group(1))) or 1
            body = ",\n        ".join([f'"{value}"'] * count)
            project_settings = (project_settings[:m.start()]
                                + f'"{key}": [\n        {body}\n    ]'
                                + project_settings[m.end():])

        allk = list(patches) + list(array_patches)

        # BODY COLOUR. The saved profile describes four Elegoo PLA slots as
        # black / red / white / blue - it has no entry for glow filament. A
        # glow bead therefore points at a slot whose recorded colour is a lie,
        # and the slicer preview would render the body red (or blue) while the
        # log claims glow. Rewriting the slot's colour makes the intent visible
        # in the preview, so a wrong slot is something you SEE rather than
        # something you discover after the print.
        if body_colour:
            project_settings = _patch_array_element(
                project_settings, "filament_colour", body_extruder - 1,
                body_colour, "body colour")
            allk.append(f"filament_colour[{body_extruder}]={body_colour}")

        print(f"[3mf] patched project_settings: {', '.join(allk)}")

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
        z.writestr("3D/Objects/top_assembly.model", top_assembly_model.getvalue())
        z.writestr("Metadata/model_settings.config", model_settings)
        z.writestr("Metadata/plate_1.json", plate_json)
        z.writestr("Metadata/slice_info.config", slice_info)
        if project_settings:
            z.writestr("Metadata/project_settings.config", project_settings)
        for _fn in sorted({t[0] for t in thumbs}):
            z.writestr("Metadata/" + _fn,
                       (template_dir / "Metadata" / _fn).read_bytes())

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
                          "3D/Objects/top_assembly.model",
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
        content = z.read("3D/Objects/top_assembly.model").decode("utf-8")
        v_total = len(re.findall(r"<vertex\s", content))
        t_total = len(re.findall(r"<triangle\s", content))
        deco = expected_counts.get("Decoration.stl", (0, 0))
        exp_v = expected_counts["Top.stl"][0] + deco[0]
        exp_t = expected_counts["Top.stl"][1] + deco[1]
        ok = (v_total == exp_v and t_total == exp_t)
        print(f"  3D/Objects/top_assembly.model: {v_total} verts, {t_total} tris  "
              f"(expect {exp_v}/{exp_t})  {'OK' if ok else 'MISMATCH'}")
        if not ok:
            raise SystemExit("VERIFY FAIL: top assembly geometry count mismatch")

    print(f"[3mf] OK — {path}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-o", "--out", default=str(DEFAULT_OUT))
    p.add_argument("-t", "--template-dir", default=str(TEMPLATE_DIR))
    p.add_argument("--force-brim", action="store_true",
                   help="force an unconditional brim on every object "
                        "(brim_type=outer_only). Use this rather than trusting "
                        "the template's auto_brim, which declines to brim a "
                        "small slab and lets the Top warp.")
    p.add_argument("--no-brim", action="store_true",
                   help="force brim off (default: keep the template's brim - "
                        "a missing brim caused a dragged/smeared print)")
    p.add_argument("--keep-cooling", action="store_true",
                   help="keep the template's 100%%-from-layer-2 part cooling "
                        "(default: hold the fan off 3 layers, full by 5 - "
                        "the aggressive default curls the edges of a flat slab)")
    p.add_argument("--body-extruder", type=int, default=2, metavar="N",
                   help="filament slot for the bead body (default 2, the red "
                        "slot the multi-colour recipe was built around). A "
                        "single-colour bead must name the slot actually holding "
                        "that filament - 1 is black in the saved profile - or "
                        "it prints in the wrong colour.")
    p.add_argument("--decoration-extruder", type=int, default=1, metavar="N",
                   help="filament slot for the Decoration part (default 1, "
                        "black in the saved profile). Ignored for a bead with "
                        "no Decoration.stl.")
    p.add_argument("--bottom-xy", default=None, metavar="X,Y",
                   help="plate centre for the Bottom object, mm (default "
                        "%.1f,%.1f). Needed when plating several beads at "
                        "once - the default gap only suits one bead."
                        % PLATE_BOTTOM_XY)
    p.add_argument("--top-xy", default=None, metavar="X,Y",
                   help="plate centre for the Top assembly, mm (default "
                        "%.1f,%.1f)." % PLATE_TOP_XY)
    p.add_argument("--nozzle-diameter", type=float, default=None, metavar="D",
                   help="Nozzle diameter written into plate_1.json. Default: read it "
                        "from the template's project_settings, else 0.4. plate_1.json "
                        "keeps its own copy, so a 0.6 template with a stale 0.4 here "
                        "puts two answers in one package.")
    p.add_argument("--body-colour", default=None, metavar="HEX",
                   help="rewrite the body slot's colour in the profile, e.g. "
                        "#7CFC00 for glow-green. The saved profile has no glow "
                        "slot, so without this the preview shows the body in "
                        "whatever colour that slot was last saved as.")
    args = p.parse_args()
    def _xy(v):
        if not v:
            return None
        try:
            x, y = (float(t) for t in v.replace(" ", "").split(","))
        except ValueError:
            raise SystemExit(f"--bottom-xy/--top-xy want 'X,Y' in mm, got {v!r}")
        return (x, y)

    build(bottom_xy=_xy(args.bottom_xy), top_xy=_xy(args.top_xy),
          out_path=Path(args.out), template_dir=Path(args.template_dir),
          no_brim=args.no_brim, force_brim=args.force_brim,
          body_extruder=args.body_extruder,
          keep_cooling=args.keep_cooling,
          decoration_extruder=args.decoration_extruder,
          body_colour=args.body_colour,
          nozzle_diameter=args.nozzle_diameter)


if __name__ == "__main__":
    main()
