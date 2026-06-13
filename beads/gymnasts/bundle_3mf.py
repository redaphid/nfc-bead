"""Bundle the 6 gymnast bead STLs into a single slicer-ready 3MF.

Unlike the canonical make_3mf (Bottom + Top-with-Decoration assembly), these
are 6 INDEPENDENT single-color parts. Each gets its own top-level object and
its own build item, arranged on a 3x2 grid so the slicer imports them already
spread across the plate (distinct XY per part — the multi-item-same-XY trap
from prompts/nfc-bead/prompt.md gotcha #28 does NOT apply here).

  uv run python beads/gymnasts/bundle_3mf.py
"""
from __future__ import annotations

import glob
import os

import trimesh

HERE      = os.path.dirname(os.path.abspath(__file__))
PRINT_DIR = os.path.join(HERE, "print")
OUT       = os.path.join(PRINT_DIR, "gymnasts.3mf")

GRID_COLS = 3
SPACING   = 30.0   # mm between part centers; parts are <=25mm so 5mm gap


def _import_lib3mf():
    import lib3mf
    return lib3mf


def _add_mesh(model, lib3mf, name, mesh):
    obj = model.AddMeshObject()
    obj.SetName(name)
    verts = [lib3mf.Position(Coordinates=(float(x), float(y), float(z)))
             for x, y, z in mesh.vertices]
    tris = [lib3mf.Triangle(Indices=(int(a), int(b), int(c)))
            for a, b, c in mesh.faces]
    obj.SetGeometry(verts, tris)
    return obj


def _translate(lib3mf, dx, dy, dz):
    t = lib3mf.Transform()
    for col in range(4):
        for row in range(3):
            t.Fields[col][row] = 1.0 if col == row else 0.0
    t.Fields[3][0], t.Fields[3][1], t.Fields[3][2] = float(dx), float(dy), float(dz)
    return t


def main():
    lib3mf = _import_lib3mf()
    stls = sorted(glob.glob(os.path.join(PRINT_DIR, "pose*.stl")))
    if not stls:
        raise SystemExit(f"no pose*.stl in {PRINT_DIR}")

    wrapper = lib3mf.Wrapper()
    model = wrapper.CreateModel()
    model.SetUnit(lib3mf.ModelUnit.MilliMeter)

    for i, path in enumerate(stls):
        name = os.path.splitext(os.path.basename(path))[0]
        mesh = trimesh.load(path, force="mesh")
        obj = _add_mesh(model, lib3mf, name, mesh)
        col, row = i % GRID_COLS, i // GRID_COLS
        model.AddBuildItem(obj, _translate(lib3mf, col * SPACING, -row * SPACING, 0.0))
        print(f"  {name}: placed at grid ({col},{row})")

    md = model.GetMetaDataGroup()
    md.AddMetaData("", "Title", "Gymnast beads (6 poses)", "string", True)
    md.AddMetaData("", "Designer", "nfc-bead pipeline (simplified)", "string", True)
    md.AddMetaData("", "Description",
                   "6 extruded gymnast silhouette charms, 2.5mm thick, "
                   "string holes on poses 1/4/5/6", "string", True)

    model.QueryWriter("3mf").WriteToFile(OUT)
    print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes, {len(stls)} parts)")


if __name__ == "__main__":
    main()
