"""Generate a slicer-ready 3MF from the canonical STL set.

Packages Bottom.stl + Top.stl + Decoration.stl into a single 3MF file
laid out for the Centauri Carbon 2:

  - Bottom is its own object (placed left on the build plate)
  - Top + Decoration are bundled as a single ComponentsObject so the
    slicer treats them as ONE OBJECT WITH PARTS — the user no longer
    has to manually 'Combine' them after import. The decoration's
    +0.7 mm Y offset and +2.51 mm Z offset (sitting on Top's outer
    face) are baked into the components transform.
  - Plate offsets keep the two build items separated so they don't
    collide on the slicer's auto-arrange.

Bambu Studio / Elegoo Slicer / Prusa Slicer all read this 3MF
Consortium-format file. Filament assignments are NOT baked in (the
3MF Production Extension does not standardize per-part filament IDs;
that's a slicer-vendor extension). The user assigns filaments in the
slicer once after import — but the 'merge as one object' step is
done.

Default scans `tmp/latest/` and writes to `tmp/latest/bead.3mf`.

    uv run python -m tools.make_3mf
    uv run python -m tools.make_3mf --dir tmp/stl_export_<ts> --out my.3mf
"""
from __future__ import annotations

import argparse
import os
import sys

import trimesh


# lib3mf module is a generated ctypes binding.
# We import lazily so `--help` works even if lib3mf isn't installed.
def _import_lib3mf():
    import lib3mf  # noqa: PLC0415
    return lib3mf


# ─── Tunables ───────────────────────────────────────────────────────────
# Plate-arrangement offsets so Bottom and (Top+Decoration) don't overlap
# on the slicer's plate. The bead is 25mm dia, so 30mm spacing leaves a
# 5mm gap.
PLATE_BOTTOM_OFFSET = (-15.0, 0.0, 0.0)
PLATE_TOPASM_OFFSET = ( 15.0, 0.0, 0.0)


# ─── Helpers ────────────────────────────────────────────────────────────
def _load_stl(path: str) -> trimesh.Trimesh:
    m = trimesh.load(path, force="mesh")
    if not isinstance(m, trimesh.Trimesh):
        raise SystemExit(f"failed to load {path} as a single mesh")
    return m


def _add_mesh(model, lib3mf, name: str, mesh: trimesh.Trimesh):
    """Add a trimesh.Trimesh into a lib3mf model as a MeshObject."""
    mesh_obj = model.AddMeshObject()
    mesh_obj.SetName(name)

    verts = [lib3mf.Position(Coordinates=(float(x), float(y), float(z)))
             for x, y, z in mesh.vertices]
    tris = [lib3mf.Triangle(Indices=(int(a), int(b), int(c)))
            for a, b, c in mesh.faces]
    mesh_obj.SetGeometry(verts, tris)
    return mesh_obj


def _identity_transform(lib3mf):
    """3MF Transform: 4 columns × 3 rows (column-major). Identity = basis vectors + zero translation."""
    t = lib3mf.Transform()
    fields = t.Fields                              # c_float_Array_3_Array_4 → 4 columns of 3
    for col in range(4):
        for row in range(3):
            fields[col][row] = 1.0 if (col == row) else 0.0
    return t


def _translate_transform(lib3mf, dx: float, dy: float, dz: float):
    t = _identity_transform(lib3mf)
    # Column 3 is the translation vector
    t.Fields[3][0] = float(dx)
    t.Fields[3][1] = float(dy)
    t.Fields[3][2] = float(dz)
    return t


# ─── Driver ─────────────────────────────────────────────────────────────
def make_3mf(stl_dir: str, out_path: str) -> int:
    lib3mf = _import_lib3mf()

    bottom_path = os.path.join(stl_dir, "Bottom.stl")
    top_path    = os.path.join(stl_dir, "Top.stl")
    deco_path   = os.path.join(stl_dir, "Decoration.stl")
    for p in (bottom_path, top_path, deco_path):
        if not os.path.isfile(p):
            print(f"missing: {p}", file=sys.stderr)
            return 1

    bottom = _load_stl(bottom_path)
    top    = _load_stl(top_path)
    deco   = _load_stl(deco_path)

    wrapper = lib3mf.Wrapper()
    model = wrapper.CreateModel()
    model.SetUnit(lib3mf.ModelUnit.MilliMeter)

    # Add the three meshes as separate MeshObjects.
    # NOTE: Decoration's STL coords are already in Top's frame (X/Y center
    # aligned with Top, Z offset 2.51mm above Top's max-Z). When we add
    # both as components in the same ComponentsObject below, those relative
    # positions are preserved.
    bottom_obj = _add_mesh(model, lib3mf, "Bottom", bottom)
    top_obj    = _add_mesh(model, lib3mf, "Top", top)
    deco_obj   = _add_mesh(model, lib3mf, "Decoration", deco)

    # Bundle Top + Decoration as a single ComponentsObject so the slicer
    # treats them as ONE OBJECT WITH PARTS.
    asm = model.AddComponentsObject()
    asm.SetName("Top_with_Decoration")
    asm.AddComponent(top_obj,  _identity_transform(lib3mf))
    asm.AddComponent(deco_obj, _identity_transform(lib3mf))

    # Place build items on the plate.
    model.AddBuildItem(
        bottom_obj,
        _translate_transform(lib3mf, *PLATE_BOTTOM_OFFSET),
    )
    model.AddBuildItem(
        asm,
        _translate_transform(lib3mf, *PLATE_TOPASM_OFFSET),
    )

    # Metadata
    md = model.GetMetaDataGroup()
    md.AddMetaData("", "Title",       "NFC bead — print bundle", "string", True)
    md.AddMetaData("", "Designer",    "nfc-bead pipeline",       "string", True)
    md.AddMetaData("", "Description",
                   "Bottom + (Top with Decoration) on a single plate; spiral pre-merged onto top body",
                   "string", True)

    # Write
    writer = model.QueryWriter("3mf")
    writer.WriteToFile(out_path)
    size = os.path.getsize(out_path) if os.path.isfile(out_path) else 0
    print(f"wrote {out_path} ({size} bytes)")
    print(f"  Bottom: {len(bottom.vertices)} verts / {len(bottom.faces)} faces  -> placed at {PLATE_BOTTOM_OFFSET}")
    print("  Top + Decoration (merged components):")
    print(f"    Top:        {len(top.vertices)} verts / {len(top.faces)} faces")
    print(f"    Decoration: {len(deco.vertices)} verts / {len(deco.faces)} faces")
    print(f"    -> placed at {PLATE_TOPASM_OFFSET}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--dir", default=None,
                   help="STL source directory (default: tmp/latest/ at repo root)")
    p.add_argument("--out", default=None,
                   help="Output 3MF path (default: <dir>/<basename>.3mf)")
    args = p.parse_args()

    if args.dir:
        stl_dir = args.dir
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        for _ in range(4):
            cand = os.path.join(here, "tmp", "latest")
            if os.path.isdir(cand):
                stl_dir = cand
                break
            here = os.path.dirname(here)
        else:
            stl_dir = os.path.join(os.getcwd(), "tmp", "latest")

    out_path = args.out or os.path.join(stl_dir, "bead.3mf")
    return make_3mf(stl_dir, out_path)


if __name__ == "__main__":
    sys.exit(main())
