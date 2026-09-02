"""Dependency-free SVG contact sheet of glow-medallion glyphs.

Renders each glyph the way it will look AT NIGHT: dark engraved lines on a
glowing disc. This is the honest test - a glyph that reads here reads on the
bead; one that disappears here will disappear at 2am too.

    python beads/glow-set/preview_svg.py            # default roster
    python beads/glow-set/preview_svg.py alice bob  # explicit names
"""
import os
import sys

import glyphs as G

MM = 9.0            # px per mm
BEAD_R = 11.0       # mm (TARGET_WIDTH 22 / 2)
PAD = 14            # px
COLS = 4


def render_one(name, theme, cx, cy):
    g = G.build(theme, name)
    out = []
    r_px = BEAD_R * MM
    out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="url(#glow)" '
               'stroke="#0c1810" stroke-width="1"/>' % (cx, cy, r_px))
    # string hole at y=+8mm (SVG y is down, so negate)
    out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#05080a"/>'
               % (cx, cy - 8.0 * MM, 0.6 * MM))
    for p in g:
        k = p[0]
        if k == "dot":
            out.append('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="#0a1410"/>'
                       % (cx + p[1] * MM, cy - p[2] * MM, p[3] * MM))
        elif k == "line":
            out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" '
                       'stroke="#0a1410" stroke-width="%.2f" stroke-linecap="round"/>'
                       % (cx + p[1] * MM, cy - p[2] * MM,
                          cx + p[3] * MM, cy - p[4] * MM, p[5] * MM))
        elif k == "ring":
            ri, ro = p[1], p[2]
            mid, w = (ri + ro) / 2.0, ro - ri
            out.append('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="none" '
                       'stroke="#0a1410" stroke-width="%.2f"/>'
                       % (cx, cy, mid * MM, w * MM))
    out.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="11" '
               'font-family="monospace" fill="#7fe6a8">%s</text>'
               % (cx, cy + r_px + 15, name))
    return "\n".join(out), g


def main(names, themes=("star", "groove", "sigil")):
    cell = BEAD_R * 2 * MM + PAD * 2
    rows_per_theme = (len(names) + COLS - 1) // COLS
    head_h = 30
    total_h = len(themes) * (rows_per_theme * (cell + 18) + head_h) + PAD
    total_w = COLS * cell + PAD * 2

    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="0 0 %d %d">' % (total_w, total_h, total_w, total_h)]
    svg.append('<defs><radialGradient id="glow" cx="50%%" cy="45%%">'
               '<stop offset="0%%" stop-color="#b8ffd0"/>'
               '<stop offset="70%%" stop-color="#6ee7a0"/>'
               '<stop offset="100%%" stop-color="#2fa86a"/>'
               '</radialGradient></defs>')
    svg.append('<rect width="100%" height="100%" fill="#05080a"/>')

    y = PAD
    report = []
    for theme in themes:
        svg.append('<text x="%d" y="%d" font-size="15" font-family="monospace" '
                   'fill="#e8f8ee">theme: %s</text>' % (PAD, y + 16, theme))
        y += head_h
        for i, nm in enumerate(names):
            col, row = i % COLS, i // COLS
            cx = PAD + col * cell + cell / 2.0
            cy = y + row * (cell + 18) + cell / 2.0
            frag, g = render_one(nm, theme, cx, cy)
            svg.append(frag)
            report.append((theme, nm, len(g), G_extent(g), G_min(g)))
        y += rows_per_theme * (cell + 18)
    svg.append('</svg>')

    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "glyph_contact_sheet.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))
    print("wrote %s" % path)
    print()
    print("%-8s %-12s %5s %8s %8s" % ("theme", "name", "prims", "extent", "minstk"))
    bad = 0
    for t, nm, n, ext, ms in report:
        flag = ""
        if ext > 6.2:
            flag += "  EXTENT>6.2"; bad += 1
        if ms < 0.8 - 1e-9:
            flag += "  STROKE<0.8"; bad += 1
        print("%-8s %-12s %5d %8.2f %8.2f%s" % (t, nm, n, ext, ms, flag))
    print()
    print("envelope violations: %d" % bad)
    return path


def G_extent(g):
    import math
    m = 0.0
    for p in g:
        if p[0] == "dot":
            m = max(m, math.hypot(p[1], p[2]) + p[3])
        elif p[0] == "line":
            w = p[5] / 2.0
            m = max(m, math.hypot(p[1], p[2]) + w, math.hypot(p[3], p[4]) + w)
        elif p[0] in ("ring", "arc"):
            m = max(m, p[2])
    return m


def G_min(g):
    w = []
    for p in g:
        if p[0] == "dot":            w.append(p[3] * 2)
        elif p[0] == "line":         w.append(p[5])
        elif p[0] in ("ring", "arc"): w.append(p[2] - p[1])
    return min(w) if w else 0.0


if __name__ == "__main__":
    roster = sys.argv[1:] or ["sterling", "brycen", "fm__lou", "eddy_hart",
                              "elli", "redaphid", "jared", "virginia"]
    main(roster)
