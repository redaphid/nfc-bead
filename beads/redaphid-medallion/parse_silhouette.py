"""Parse the redaphid-portrait silhouette.svg (one outline <path> + two eye
<circle>s) into the figure.json the medallion build expects: a centered-later
mm polygon (Y-up) plus eye discs. The build mass-centers + scales both together
and cuts the eyes through the raised relief (so they read as the body color).

Output: beads/redaphid-medallion/figure.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SVG  = HERE / "silhouette.svg"


def main():
    txt = SVG.read_text(encoding="utf-8")

    # viewBox height for the SVG-Y-down -> Y-up flip
    vb = re.search(r'viewBox="([\d.\- ]+)"', txt).group(1).split()
    H = float(vb[3])

    # outline path: "M x,y L x,y ... Z"  -> list of (x, y_up)
    d = re.search(r'<path[^>]*\bd="([^"]+)"', txt).group(1)
    pts = re.findall(r'(-?\d+\.?\d*),(-?\d+\.?\d*)', d)
    poly = [[round(float(x), 4), round(H - float(y), 4)] for x, y in pts]

    # eyes
    eyes = []
    for m in re.finditer(r'<circle[^>]*\bcx="([\d.\-]+)"[^>]*\bcy="([\d.\-]+)"[^>]*\br="([\d.\-]+)"', txt):
        cx, cy, r = map(float, m.groups())
        eyes.append({"x": round(cx, 4), "y": round(H - cy, 4), "r": round(r, 4)})

    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    out = {
        "source": "beads/redaphid-portrait silhouette.svg (outline + eyes)",
        "width_mm": round(max(xs) - min(xs), 4),
        "height_mm": round(max(ys) - min(ys), 4),
        "polygon": poly,
        "eyes": eyes,
    }
    (HERE / "figure.json").write_text(json.dumps(out, indent=2))
    print(f"polygon pts: {len(poly)}  bbox {out['width_mm']}x{out['height_mm']}mm  eyes: {len(eyes)}")
    for e in eyes:
        print(f"  eye @ ({e['x']},{e['y']}) r={e['r']}")
    print(f"Wrote {HERE / 'figure.json'}")


if __name__ == "__main__":
    main()
