"""Contact sheet of motif outlines, drawn at TRUE SCALE with their hardware.

Shows what actually goes in the bead, not just the pretty silhouette: the
10.5mm NFC pocket, the three peg positions and the string hole, all placed by
shapes.py's own solver. That is what makes the sheet worth looking at - a
silhouette that "looks fine" can still be unbuildable at a given size, and here
you can see the pocket crowding the outline rather than reading a refusal
message.

Usage:
    python beads/glow-set/preview_outlines.py tmp/outlines/sm_*.json -o sheet.svg
"""
import argparse
import json
import os
import pathlib
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import shapes as S            # noqa: E402

CELL = 46.0        # mm of drawing space per bead
COLS = 3
PAD = 6.0
INK = "#1b1b1b"
POCKET = "#c8102e"
PEG = "#0072ce"
HOLE = "#00875a"


def solve(pts):
    """Ask the same solver the builder uses, so the sheet shows the hardware
    that would really be cut - not an idealised guess.

    place_pocket returns (x, y, clearance) and place_hole returns (y, crown);
    both carry their margin alongside the coordinate, which is worth surfacing
    because it is exactly what the refusals are about.
    """
    out = {"pocket": None, "pegs": [], "hole": None, "clear": None}
    try:
        px, py, clear = S.place_pocket(pts)
        out["pocket"], out["clear"] = (px, py), clear
    except Exception:
        return out
    try:
        out["hole"] = S.place_hole(pts)[0]
    except Exception:
        pass
    try:
        out["pegs"] = S.place_pegs(pts, out["pocket"], hole_y=out["hole"])
    except Exception:
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsons", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()

    beads = []
    for f in sorted(a.jsons):
        doc = json.load(open(f))
        pts = [(float(x), float(y)) for x, y in doc["outer"]]
        voids = [[(float(x), float(y)) for x, y in v]
                 for v in doc.get("voids", [])]
        beads.append((doc.get("lib", "?"), doc.get("name", pathlib.Path(f).stem),
                      pts, voids))

    rows = (len(beads) + COLS - 1) // COLS
    W, H = COLS * CELL, rows * CELL + 14
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W*4:.0f}" '
         f'height="{H*4:.0f}" viewBox="0 0 {W} {H}">',
         f'<rect width="{W}" height="{H}" fill="#fbfaf7"/>',
         f'<text x="{W/2:.1f}" y="7" font-family="Helvetica,Arial" font-size="4.2" '
         f'text-anchor="middle" fill="{INK}">'
         f'{len(beads)} motifs that fit at 20mm '
         f'(pocket {S.POCKET_R*2:.1f}mm, 3 pegs, cord hole)</text>']

    for i, (lib, name, pts, voids) in enumerate(beads):
        r, c = divmod(i, COLS)
        cx = c * CELL + CELL / 2
        cy = r * CELL + CELL / 2 + 12
        o.append(f'<g transform="translate({cx:.2f},{cy:.2f}) scale(1,-1)">')

        d = "M " + " L ".join(f"{x:.3f},{y:.3f}" for x, y in pts) + " Z"
        for v in voids:
            d += " M " + " L ".join(f"{x:.3f},{y:.3f}" for x, y in v) + " Z"
        o.append(f'<path d="{d}" fill="#e9e4d9" stroke="{INK}" '
                 f'stroke-width="0.35" fill-rule="evenodd"/>')

        s = solve(pts)
        if s["pocket"]:
            px, py = s["pocket"]
            o.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="{S.POCKET_R:.2f}" '
                     f'fill="none" stroke="{POCKET}" stroke-width="0.3" '
                     f'stroke-dasharray="1,0.7"/>')
        for gx, gy in s["pegs"] or []:
            o.append(f'<circle cx="{gx:.2f}" cy="{gy:.2f}" r="{S.PEG_R:.2f}" '
                     f'fill="{PEG}" fill-opacity="0.55"/>')
        if s["hole"] is not None:
            hy = s["hole"]
            o.append(f'<circle cx="0" cy="{hy:.2f}" r="{S.HOLE_R:.2f}" '
                     f'fill="{HOLE}"/>')
        o.append("</g>")

        w = max(x for x, _ in pts) - min(x for x, _ in pts)
        h = max(y for _, y in pts) - min(y for _, y in pts)
        o.append(f'<text x="{cx:.1f}" y="{cy + CELL/2 - 4.5:.1f}" '
                 f'font-family="Helvetica,Arial" font-size="3.1" '
                 f'text-anchor="middle" fill="{INK}">{name}</text>')
        o.append(f'<text x="{cx:.1f}" y="{cy + CELL/2 - 1.2:.1f}" '
                 f'font-family="Helvetica,Arial" font-size="2.3" '
                 f'text-anchor="middle" fill="#7a7368">{lib} · '
                 f'{w:.1f}×{h:.1f}mm</text>')

    o.append("</svg>")
    pathlib.Path(a.out).write_text("\n".join(o), encoding="utf-8")
    print(f"wrote {a.out} ({len(beads)} beads)")


if __name__ == "__main__":
    main()
