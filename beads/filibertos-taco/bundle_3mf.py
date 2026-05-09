"""Bundle a multi-decoration 3MF for filibertos-taco.

`nfc-make-3mf` only knows one `Decoration.stl` slot. Multi-color charms
need each color region as a SEPARATE object/component in the 3MF so the
slicer can assign one filament per object. This script discovers
`Bottom.stl`, `Top.stl`, and every `Decoration*.stl` in a print-bundle
directory and emits them as distinct components in a single 3MF.

Run:
    uv run python beads/filibertos-taco/bundle_3mf.py \
        --dir beads/filibertos-taco/print/blocks \
        --out beads/filibertos-taco/print/blocks/filibertos-taco-blocks.3mf
"""
import argparse
import os
import sys
from pathlib import Path

import numpy as np
import trimesh


def _import_lib3mf():
    try:
        import lib3mf
    except ImportError:
        print("lib3mf not installed. uv add lib3mf  (or pip install lib3mf)", file=sys.stderr)
        sys.exit(2)
    return lib3mf


def _load_stl(path):
    m = trimesh.load(path)
    return m


def _add_mesh(model, lib3mf, name, m):
    obj = model.AddMeshObject()
    obj.SetName(name)
    pos = []
    for v in m.vertices:
        p = lib3mf.Position()
        p.Coordinates[0] = float(v[0]); p.Coordinates[1] = float(v[1]); p.Coordinates[2] = float(v[2])
        pos.append(p)
    tri = []
    for f in m.faces:
        t = lib3mf.Triangle()
        t.Indices[0] = int(f[0]); t.Indices[1] = int(f[1]); t.Indices[2] = int(f[2])
        tri.append(t)
    obj.SetGeometry(pos, tri)
    return obj


def _identity_transform(lib3mf):
    t = lib3mf.Transform()
    fields = t.Fields                              # c_float_Array_3_Array_4
    for col in range(4):
        for row in range(3):
            fields[col][row] = 1.0 if (col == row) else 0.0
    return t


def _translate_transform(lib3mf, dx, dy, dz):
    t = _identity_transform(lib3mf)
    t.Fields[3][0] = float(dx)
    t.Fields[3][1] = float(dy)
    t.Fields[3][2] = float(dz)
    return t


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--dir', required=True, help="Directory holding Bottom.stl, Top.stl, Decoration*.stl")
    ap.add_argument('--out', required=True, help="Output 3MF path")
    ap.add_argument('--separate-plates', action='store_true',
                    help="Place Bottom and Top assembly on separate plate offsets (default: both at origin)")
    args = ap.parse_args()

    d = Path(args.dir)
    bottom_p = d / 'Bottom.stl'
    top_p    = d / 'Top.stl'
    if not bottom_p.is_file() or not top_p.is_file():
        print(f"need Bottom.stl + Top.stl in {d}", file=sys.stderr); sys.exit(1)

    # Discover decorations: Decoration.stl is the legacy single-decoration slot,
    # DecorationXxx.stl are per-color components. Prefer the per-color ones —
    # if any exist, ignore the unified Decoration.stl since slicer can't split it.
    deco_per_color = sorted(d.glob('Decoration[A-Z]*.stl'))
    if not deco_per_color:
        legacy = d / 'Decoration.stl'
        deco_per_color = [legacy] if legacy.is_file() else []

    print(f"Bottom: {bottom_p.name}")
    print(f"Top:    {top_p.name}")
    print(f"Decorations: {[p.name for p in deco_per_color]}")

    lib3mf = _import_lib3mf()
    wrapper = lib3mf.Wrapper()
    model = wrapper.CreateModel()
    model.SetUnit(lib3mf.ModelUnit.MilliMeter)

    bottom_mesh = _load_stl(str(bottom_p))
    top_mesh    = _load_stl(str(top_p))
    deco_meshes = [(p.stem, _load_stl(str(p))) for p in deco_per_color]

    bottom_obj = _add_mesh(model, lib3mf, 'Bottom', bottom_mesh)
    top_obj    = _add_mesh(model, lib3mf, 'Top',    top_mesh)
    deco_objs  = [_add_mesh(model, lib3mf, name, m) for name, m in deco_meshes]

    # Each part is a TOP-LEVEL object with its semantic name. Slicers
    # (Bambu Studio / Elegoo Slicer) display each by the SetName above
    # — no ComponentsObject wrapping that would cause the slicer to
    # rewrite child names like `top_with_decorations_5`.
    #
    # All Top-frame parts share the same XY offset so the slicer sees
    # them as co-located (auto-pairs them on the same plate position).
    if args.separate_plates:
        bot_offset = _translate_transform(lib3mf, -15, 0, 0)
        top_offset = _translate_transform(lib3mf, +15, 0, 0)
    else:
        bot_offset = _identity_transform(lib3mf)
        top_offset = _identity_transform(lib3mf)

    model.AddBuildItem(bottom_obj, bot_offset)
    model.AddBuildItem(top_obj,    top_offset)
    for o in deco_objs:
        model.AddBuildItem(o, top_offset)

    md = model.GetMetaDataGroup()
    md.AddMetaData('', 'Title', f"{d.parent.name} multi-color print bundle", 'string', True)
    md.AddMetaData('', 'Description',
                   f"Bottom + Top + {len(deco_per_color)} decoration component(s). "
                   "Slicer should expose each Decoration* component for per-filament color assignment.",
                   'string', True)

    writer = model.QueryWriter('3mf')
    writer.WriteToFile(str(args.out))
    size = os.path.getsize(args.out)
    print(f"\nwrote {args.out} ({size:,} bytes)")
    print(f"  objects: Bottom, Top, {', '.join(p.stem for p in deco_per_color)}")
    print(f"  in slicer: each appears with its semantic name; assign 1 filament per object")


if __name__ == '__main__':
    main()
