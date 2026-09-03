"""Gang several finished beads onto ONE plate.

`build_3mf.py` lays out a single bead: one Bottom and one Top assembly. Printing
a batch that way costs a full ~12 minute preamble per bead, which dwarfs the ~6
minutes of actual printing on a 25mm charm.

This merges N bead directories into the two grouped STLs that `build_3mf.py`
already understands: every Bottom becomes one `Bottom.stl`, every Top becomes
one `Top.stl`. They stay separate objects to the slicer only in the sense that
matters here - a single-colour batch shares one extruder, so nothing is lost by
welding them into one mesh each, and the whole plate slices as two parts.

Each group is packed into a GRID (--cols) and `build_3mf.py` places the two
blocks via --bottom-xy / --top-xy. Bottoms share a block because they all print
pegs-up; tops share a block because they all print mating-face-down. Keeping the
halves apart also makes a failed plate readable at a glance: one block of
silhouettes, one block of sockets.

Do NOT expect the slicer's --arrange to densify this. It works headlessly, but
these groups are welded into one mesh each, and the arranger packs OBJECTS, not
the bodies inside one - it rotates the whole block as a rigid unit and gains
nothing. Packing individual beads via --arrange would need build_3mf.py to emit
one object per part. Until then the layout here is the layout you get, so wrap
it into a grid rather than leaving a 256mm bed holding one 170mm row.

Geometry is translated in XY only. Z is left exactly as exported, because each
part was already bed-flattened to z=0 and nudging that would lift a part off
the plate or bury it.

Usage:
    python tools/make_plate.py --pitch 35 beads/glow-set/print/plate3-{skull,ghost,cat}
"""
import argparse
import pathlib
import sys

import numpy as np
import trimesh

REPO = pathlib.Path(__file__).resolve().parent.parent
TMP_LATEST = REPO / "tmp" / "latest"


def load_flat(path):
    m = trimesh.load(path, process=False)
    if m.is_empty:
        raise SystemExit(f"empty mesh: {path}")
    return m


def grid(meshes, pitch, cols, y0):
    """Pack meshes into a grid of `cols` columns on a fixed pitch, centred on
    x=0, with the block's first row at y0 and later rows stacked BELOW it.

    A single long row is what a hand-written layout naturally produces and it
    wastes the bed badly: six 20mm beads in a row span 170mm of a 256mm bed and
    leave everything above and below empty. Wrapping into a grid is what buys
    more beads per preamble, which is the entire reason to gang a tray.

    Each mesh is centred on its own XY bounding box first, so a silhouette whose
    origin sits off-centre (the solver places pegs and holes, not the outline)
    does not drag its slot off the pitch.
    """
    out = []
    n = len(meshes)
    cols = max(1, min(cols, n))
    for i, m in enumerate(meshes):
        m = m.copy()
        lo, hi = m.bounds
        cx, cy = (lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0
        r, c = divmod(i, cols)
        wide = min(cols, n)
        tx = (c - (wide - 1) / 2.0) * pitch
        ty = y0 - r * pitch
        m.apply_translation([tx - cx, ty - cy, 0.0])
        out.append(m)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", help="bead dirs, each with Bottom.stl + Top.stl")
    ap.add_argument("--pitch", type=float, default=35.0,
                    help="mm between bead centres within a row (default 35)")
    ap.add_argument("--cols", type=int, default=99,
                    help="beads per row before wrapping (default: one row). "
                         "A 256mm bed fits 8 columns at 30mm pitch.")
    ap.add_argument("--row-gap", type=float, default=0.0,
                    help="mm between the bottom row and the top row, measured "
                         "centre to centre. 0 means the rows are emitted "
                         "centred on y=0 each, and build_3mf.py separates them "
                         "via --bottom-xy / --top-xy (the normal path).")
    ap.add_argument("--out", default=str(TMP_LATEST))
    a = ap.parse_args()

    dirs = [pathlib.Path(d) for d in a.dirs]
    for d in dirs:
        for f in ("Bottom.stl", "Top.stl"):
            if not (d / f).is_file():
                raise SystemExit(f"missing {f} in {d}")

    bottoms = [load_flat(d / "Bottom.stl") for d in dirs]
    tops = [load_flat(d / "Top.stl") for d in dirs]

    # Guard the thing that silently ruins a plate: a part not sitting on z=0
    # prints in mid-air or gouges the bed, and it is invisible in the 3MF.
    for d, m in list(zip(dirs, bottoms)) + list(zip(dirs, tops)):
        if abs(m.bounds[0][2]) > 1e-4:
            raise SystemExit(f"{d.name}: part does not sit at z=0 "
                             f"(z_min={m.bounds[0][2]:.4f}) - refusing to plate it")

    by = -a.row_gap / 2.0 if a.row_gap else 0.0
    ty = +a.row_gap / 2.0 if a.row_gap else 0.0
    bottom = trimesh.util.concatenate(grid(bottoms, a.pitch, a.cols, by))
    top = trimesh.util.concatenate(grid(tops, a.pitch, a.cols, ty))

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name in ("Bottom.stl", "Top.stl", "Decoration.stl"):
        p = out / name
        if p.exists():
            p.unlink()          # stale parts from a previous bead bundle in
    bottom.export(out / "Bottom.stl")
    top.export(out / "Top.stl")

    for label, m in (("Bottom", bottom), ("Top", top)):
        lo, hi = m.bounds
        print(f"  {label:<7} {len(dirs)} parts  "
              f"{hi[0]-lo[0]:6.1f} x {hi[1]-lo[1]:6.1f} x {hi[2]-lo[2]:5.2f} mm  "
              f"z_min={lo[2]:.3f}  watertight={m.is_watertight}")
    print(f"[plate] wrote {out}/Bottom.stl and Top.stl "
          f"({', '.join(d.name for d in dirs)})")


if __name__ == "__main__":
    main()
