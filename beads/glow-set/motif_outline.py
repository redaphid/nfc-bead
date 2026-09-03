"""Export one motif glyph to a JSON outline that build_talisman.py can eat.

WHY THIS EXISTS. The motif libraries (japanese.py, chinese.py, adinkra.py)
raster an SDF and march squares to get their outlines, so they need numpy AND
scikit-image. Blender 5.0 bundles numpy 1.26 but NOT scikit-image, so the glyph
libraries cannot be imported inside Blender at all. Rather than vendor skimage
into Blender, the outline is computed HERE - with the project .venv - and handed
to Blender as plain points. Blender then needs nothing but bpy.

That split also makes the build auditable: the JSON is the exact polygon that
was extruded, so a bead can be re-derived without re-running the SDF.

Usage (must be the project .venv python, not the bare host python):
  .venv/Scripts/python.exe beads/glow-set/motif_outline.py \
      --glow <worktree>/beads/glow-set --lib japanese --name kiku \
      --r 16.0 -o tmp/outlines/kiku.json
"""
import argparse
import json
import math
import os
import sys


def resample(pts, step_mm=0.35):
    """Same decimation build_talisman._resample applies to foils: the SDF trace
    is far finer than the 0.4mm nozzle can resolve, so it is pure STL bloat."""
    pts = [(float(x), float(y)) for x, y in pts]
    out = [pts[0]]
    for q in pts[1:]:
        if math.hypot(q[0] - out[-1][0], q[1] - out[-1][1]) >= step_mm:
            out.append(q)
    if math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < step_mm:
        out.pop()
    return out


def load(lib, name, r_out):
    """-> (outer, voids) at the library's native scale."""
    if lib == "japanese":
        import japanese as J
        return [(float(x), float(y)) for x, y in J.MON[name](size=2.0 * r_out)], []
    if lib == "chinese":
        import chinese as C
        m = C.build(name)
        return ([(float(x), float(y)) for x, y in m.pts],
                [[(float(x), float(y)) for x, y in v] for v in m.voids])
    if lib == "adinkra":
        import adinkra as A
        rings = A.SYMBOLS[name]()
        return ([(float(x), float(y)) for x, y in rings[0]],
                [[(float(x), float(y)) for x, y in v] for v in rings[1:]])
    raise SystemExit("unknown lib %r" % lib)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glow", required=True, help="that branch's beads/glow-set")
    ap.add_argument("--lib", required=True,
                    choices=["japanese", "chinese", "adinkra"])
    ap.add_argument("--name", required=True)
    ap.add_argument("--r", type=float, default=16.0,
                    help="circumscribed radius; 16 -> a 32mm bead")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--min-void-gap", type=float, default=0.6,
                    help="mm of solid required between any feature and a void")
    a = ap.parse_args()

    sys.path.insert(0, os.path.abspath(a.glow))
    import shapes as S

    outer, voids = load(a.lib, a.name, a.r)

    # Centre on the bbox and scale so max(w,h) == 2r, matching the foil
    # convention (foils.build(r=R_OUT) yields a 2*R_OUT bead). Voids are scaled
    # by the SAME factor about the SAME centre or they drift off their features.
    xs = [p[0] for p in outer]
    ys = [p[1] for p in outer]
    cx, cy = (max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0
    native = max(max(xs) - min(xs), max(ys) - min(ys))
    k = (2.0 * a.r) / native
    scale = lambda ring: [((x - cx) * k, (y - cy) * k) for x, y in ring]

    outer = S.ccw(resample(scale(outer)))
    voids = [S.ccw(resample(v)) for v in (scale(v) for v in voids)]
    voids = [v for v in voids if len(v) >= 3]

    fit = S.fit_report(outer)
    if not fit["ok"]:
        why = []
        if not fit["pocket_ok"]:
            why.append("pocket clearance %.2f < %.2f"
                       % (fit["pocket"][2], S.POCKET_R + S.WALL))
        if not fit["hole_ok"]:
            why.append("no string hole with a %.1fmm crown" % S.HOLE_CROWN)
        if not fit["pegs_ok"]:
            why.append("cannot place 3 pegs")
        elif fit["spread"] <= 40.0:
            why.append("peg spread %.0f <= 40" % fit["spread"])
        raise SystemExit("REFUSED %s/%s: %s" % (a.lib, a.name, "; ".join(why)))

    # fit_report is void-blind - it only ever sees the outer ring - so a pocket
    # or peg it calls solid can sit squarely over a hole. Gate that here, where
    # the voids are still in hand, rather than discovering it in the slicer.
    # S.clearance is SIGNED (+ inside the ring, - outside), so the solid margin
    # between a feature edge and a void edge is -clearance - r.
    worst, which = None, None
    if voids:
        px, py, _ = fit["pocket"]
        feats = [("pocket", px, py, S.POCKET_R)]
        feats += [("peg%d" % i, gx, gy, S.PEG_R)
                  for i, (gx, gy) in enumerate(fit["pegs"])]
        feats.append(("hole", 0.0, fit["hole"][0], S.HOLE_R))
        for nm, x, y, r in feats:
            for v in voids:
                gap = -S.clearance(v, x, y) - r
                if worst is None or gap < worst:
                    worst, which = gap, nm
        if worst < a.min_void_gap:
            raise SystemExit("REFUSED %s/%s: %s is %.2fmm from a void (need %.2f)"
                             % (a.lib, a.name, which, worst, a.min_void_gap))

    doc = {
        "name": a.name, "lib": a.lib, "r_out": a.r,
        "native_max_dim_mm": round(native, 3), "scale": round(k, 5),
        "outer": [[round(x, 4), round(y, 4)] for x, y in outer],
        "voids": [[[round(x, 4), round(y, 4)] for x, y in v] for v in voids],
        "fit": {
            "pocket": [round(v, 3) for v in fit["pocket"]],
            "pegs": [[round(x, 3), round(y, 3)] for x, y in fit["pegs"]],
            "hole": [round(v, 3) for v in fit["hole"]],
            "spread": round(fit["spread"], 1),
            "w": round(fit["w"], 2), "h": round(fit["h"], 2),
            "void_gap": None if worst is None else round(worst, 3),
        },
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(doc, fh, indent=1)
    print("%-14s %-12s %3d pts %d voids  %.1fx%.1fmm  pocket %.2f spread %.0f "
          "crown %.1f%s -> %s"
          % (a.lib, a.name, len(outer), len(voids), fit["w"], fit["h"],
             fit["pocket"][2], fit["spread"], fit["hole"][1],
             "" if worst is None else " voidgap %.2f" % worst, a.out))


if __name__ == "__main__":
    main()
