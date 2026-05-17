"""Bundle a multi-decoration 3MF for black-rainbow.

Wraps the generic multi-decoration 3MF bundler so the slicer sees one
ComponentsObject (`Top_with_decorations`) holding Top + every Decoration*.stl
as named child parts. The slicer's "object with parts" workflow lets the
user assign one filament per part — needed for the 5 distinct prints
(black back, white show-face base, red, yellow, blue, plus black wings).

The bundle structure matches recipe gotcha #28 — one ComponentsObject + one
build item for the assembly is the only structure all our slicers parse
cleanly. Bottom is its own build item next to it on the plate.

Run:
    uv run python beads/black-rainbow/bundle_3mf.py \
        --dir beads/black-rainbow/print \
        --out beads/black-rainbow/print/black-rainbow.3mf
"""
import argparse
import os
import sys
from pathlib import Path

import trimesh


def _import_lib3mf():
    try:
        import lib3mf
    except ImportError:
        print("lib3mf not installed. uv add lib3mf  (or pip install lib3mf)", file=sys.stderr)
        sys.exit(2)
    return lib3mf


def _add_mesh(model, lib3mf, name, m):
    obj = model.AddMeshObject()
    obj.SetName(name)
    pos = []
    for v in m.vertices:
        p = lib3mf.Position()
        p.Coordinates[0] = float(v[0])
        p.Coordinates[1] = float(v[1])
        p.Coordinates[2] = float(v[2])
        pos.append(p)
    tri = []
    for f in m.faces:
        t = lib3mf.Triangle()
        t.Indices[0] = int(f[0])
        t.Indices[1] = int(f[1])
        t.Indices[2] = int(f[2])
        tri.append(t)
    obj.SetGeometry(pos, tri)
    return obj


def _identity_transform(lib3mf):
    t = lib3mf.Transform()
    fields = t.Fields
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
    ap.add_argument('--dir', required=True, help="Directory with Bottom.stl + Top.stl + Decoration*.stl")
    ap.add_argument('--out', required=True, help="Output 3MF path")
    ap.add_argument('--separate-plates', action='store_true',
                    help="Offset Bottom/Top assembly to separate plate positions")
    args = ap.parse_args()

    d = Path(args.dir)
    bottom_p = d / 'Bottom.stl'
    top_p = d / 'Top.stl'
    if not bottom_p.is_file() or not top_p.is_file():
        print(f"need Bottom.stl + Top.stl in {d}", file=sys.stderr)
        sys.exit(1)

    deco_per_color = sorted(d.glob('Decoration[A-Z]*.stl'))
    print(f"Bottom: {bottom_p.name}")
    print(f"Top:    {top_p.name}")
    print(f"Decorations: {[p.name for p in deco_per_color]}")

    lib3mf = _import_lib3mf()
    wrapper = lib3mf.Wrapper()
    model = wrapper.CreateModel()
    model.SetUnit(lib3mf.ModelUnit.MilliMeter)

    bottom_mesh = trimesh.load(str(bottom_p))
    top_mesh = trimesh.load(str(top_p))
    deco_meshes = [(p.stem, trimesh.load(str(p))) for p in deco_per_color]

    bottom_obj = _add_mesh(model, lib3mf, 'Bottom', bottom_mesh)
    top_obj = _add_mesh(model, lib3mf, 'Top', top_mesh)
    deco_objs = [_add_mesh(model, lib3mf, name, m) for name, m in deco_meshes]

    asm = model.AddComponentsObject()
    asm.SetName('Top_with_decorations')
    asm.AddComponent(top_obj, _identity_transform(lib3mf))
    for o in deco_objs:
        asm.AddComponent(o, _identity_transform(lib3mf))

    if args.separate_plates:
        model.AddBuildItem(bottom_obj, _translate_transform(lib3mf, -15, 0, 0))
        model.AddBuildItem(asm, _translate_transform(lib3mf, +15, 0, 0))
    else:
        model.AddBuildItem(bottom_obj, _identity_transform(lib3mf))
        model.AddBuildItem(asm, _identity_transform(lib3mf))

    md = model.GetMetaDataGroup()
    md.AddMetaData('', 'Title', "black-rainbow multi-color print bundle", 'string', True)
    md.AddMetaData('', 'Description',
                   f"Bottom + Top + {len(deco_per_color)} decoration component(s). "
                   "Slicer should expose each Decoration* component for per-filament color assignment.",
                   'string', True)

    writer = model.QueryWriter('3mf')
    writer.WriteToFile(str(args.out))
    size = os.path.getsize(args.out)
    print(f"\nwrote {args.out} ({size:,} bytes)")
    print(f"  parts: Bottom + Top + {len(deco_per_color)} decoration(s)")
    print(f"  in slicer: Top_with_decorations is one object with parts; assign 1 filament per part")


if __name__ == '__main__':
    main()
