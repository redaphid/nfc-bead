"""Bundle the 6 fire-heart STLs into a slicer-ready multi-color 3MF.

Two ComponentsObjects (so each slicer treats its color parts as ONE object
with parts — recipe gotcha #28), placed side by side on the plate:

  BottomAsm = BottomHeart + BottomRed + BottomOrange   (back face down, pegs up)
  TopAsm    = TopHeart    + TopRed    + TopOrange       (sockets down, heart up)

The build pipeline is a centered-mesh build, so both halves are ALREADY in
print orientation (gotcha #16) — no rotation, just bed-flatten each assembly
to z=0. Per-mesh base-material colors are baked in so the slicer shows
heart=black / red / orange and you can map filaments at a glance.

Run:
    uv run python beads/fire-heart/bundle_3mf.py
    uv run python beads/fire-heart/bundle_3mf.py --out my.3mf
"""
from __future__ import annotations
import argparse
import os
import sys
import trimesh

PRINT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "print")

# Components and their display colors (R,G,B,A bytes). Slicer maps these to
# filaments on import.
COLORS = {
    "Heart":  (20, 20, 20, 255),     # near-black
    "Red":    (212, 18, 18, 255),
    "Orange": (255, 140, 0, 255),
}
BOTTOM = ["BottomHeart", "BottomRed", "BottomOrange"]
TOP    = ["TopHeart", "TopRed", "TopOrange"]

# Side-by-side plate placement (bead ~28mm wide → ~8mm gap).
PLATE_BOTTOM_OFFSET = (-18.0, 0.0, 0.0)
PLATE_TOP_OFFSET    = ( 18.0, 0.0, 0.0)


def _import_lib3mf():
    import lib3mf
    return lib3mf


def _load(name):
    p = os.path.join(PRINT_DIR, name + ".stl")
    if not os.path.isfile(p):
        raise SystemExit(f"missing STL: {p} (run the build + STL export first)")
    m = trimesh.load(p, force="mesh")
    if not isinstance(m, trimesh.Trimesh):
        raise SystemExit(f"failed to load {p} as a single mesh")
    return m


def _identity(lib3mf):
    t = lib3mf.Transform()
    for c in range(4):
        for r in range(3):
            t.Fields[c][r] = 1.0 if c == r else 0.0
    return t


def _translate(lib3mf, dx, dy, dz):
    t = _identity(lib3mf)
    t.Fields[3][0] = float(dx); t.Fields[3][1] = float(dy); t.Fields[3][2] = float(dz)
    return t


def _color_for(name, lib3mf):
    for key, rgba in COLORS.items():
        if name.endswith(key):
            return lib3mf.Color(Red=rgba[0], Green=rgba[1], Blue=rgba[2], Alpha=rgba[3])
    return lib3mf.Color(Red=180, Green=180, Blue=180, Alpha=255)


def _add_mesh(model, lib3mf, name, mesh, matgroup):
    obj = model.AddMeshObject()
    obj.SetName(name)
    verts = [lib3mf.Position(Coordinates=(float(x), float(y), float(z)))
             for x, y, z in mesh.vertices]
    tris = [lib3mf.Triangle(Indices=(int(a), int(b), int(c)))
            for a, b, c in mesh.faces]
    obj.SetGeometry(verts, tris)
    pid = matgroup.AddMaterial(name, _color_for(name, lib3mf))
    obj.SetObjectLevelProperty(matgroup.GetResourceID(), pid)
    return obj


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--out", default=os.path.join(PRINT_DIR, "fire-heart.3mf"))
    args = ap.parse_args()
    lib3mf = _import_lib3mf()

    meshes = {n: _load(n) for n in BOTTOM + TOP}

    # Bed-flatten each assembly: translate all its meshes so the assembly's
    # collective min-z sits on z=0 (preserves intra-assembly XY/Z alignment).
    for group in (BOTTOM, TOP):
        minz = min(meshes[n].bounds[0][2] for n in group)
        for n in group:
            meshes[n].apply_translation((0, 0, -minz))

    model = lib3mf.Wrapper().CreateModel()
    model.SetUnit(lib3mf.ModelUnit.MilliMeter)
    matgroup = model.AddBaseMaterialGroup()

    objs = {n: _add_mesh(model, lib3mf, n, meshes[n], matgroup) for n in BOTTOM + TOP}

    bottom_asm = model.AddComponentsObject(); bottom_asm.SetName("FireHeart_Bottom")
    for n in BOTTOM:
        bottom_asm.AddComponent(objs[n], _identity(lib3mf))
    top_asm = model.AddComponentsObject(); top_asm.SetName("FireHeart_Top")
    for n in TOP:
        top_asm.AddComponent(objs[n], _identity(lib3mf))

    model.AddBuildItem(bottom_asm, _translate(lib3mf, *PLATE_BOTTOM_OFFSET))
    model.AddBuildItem(top_asm, _translate(lib3mf, *PLATE_TOP_OFFSET))

    md = model.GetMetaDataGroup()
    md.AddMetaData("", "Title", "Fire-Heart NFC charm", "string", True)
    md.AddMetaData("", "Designer", "nfc-bead pipeline", "string", True)
    md.AddMetaData("", "Description",
                   "Through-color flaming heart: black heart + red/orange flames, "
                   "two halves on one plate (each multi-color)", "string", True)

    model.QueryWriter("3mf").WriteToFile(args.out)
    size = os.path.getsize(args.out) if os.path.isfile(args.out) else 0
    print(f"wrote {args.out} ({size} bytes)")
    for group, off in ((BOTTOM, PLATE_BOTTOM_OFFSET), (TOP, PLATE_TOP_OFFSET)):
        zmax = max(meshes[n].bounds[1][2] for n in group)
        print(f"  {'Bottom' if group is BOTTOM else 'Top':6} @ {off}  height={zmax:.2f}mm  "
              + " + ".join(f"{n}({len(meshes[n].vertices)}v)" for n in group))


if __name__ == "__main__":
    sys.exit(main())
