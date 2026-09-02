"""Parametric silhouettes for the glow bead set.

WHY POLYGONS, NOT SVG: recipe gotcha #25 names the "polygon manifest pipeline"
as the preferred route for multi-shape work - Blender's SVG importer sizes each
curve from its PATH bbox rather than the viewBox, so a family of SVGs lands at
inconsistent scales and positions. Emitting vertices in shared mm coordinates
and building with from_pydata skips that class of bug completely, and lets us
validate fit analytically before Blender is ever opened.

THE CONSTRAINT, modelled properly: the shape must fit a 10.5mm NTAG215 pocket
SOMEWHERE (not necessarily centred) plus 3 pegs in solid material with wall
clearance. An earlier version of this file demanded the outline contain a
19.2mm concentric disc - that was far too strict and failed shapes that are
perfectly buildable. redaphid-portrait puts its pegs at the ears and chin, at
different radii AND different diameters; the pocket can offset too. So the gate
is a solver (place_pocket + place_pegs), not a disc test.

Each generator returns a closed list of (x, y) vertices in mm, wound CCW, with
the core centred on the origin.
"""
import math

PEG_RING = 7.1        # min: pocket_r 5.25 + peg_r 1.3 + 0.55 wall
PEG_R = 1.3
CORE_R = PEG_RING + PEG_R + 1.2      # 9.6mm - solid disc every shape must hold


# ----------------------------------------------------------------- utilities
def arc(cx, cy, r, a0, a1, n=48):
    """Points along an arc, degrees, inclusive of both ends."""
    return [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
            for a in (a0 + (a1 - a0) * i / n for i in range(n + 1))]


def _poly_area(pts):
    return 0.5 * sum(x1 * y2 - x2 * y1
                     for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))


def ccw(pts):
    return pts if _poly_area(pts) > 0 else pts[::-1]


def contains(pts, x, y):
    """Even-odd point-in-polygon."""
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
    return inside


def _seg_d(px, py, x1, y1, x2, y2):
    vx, vy = x2 - x1, y2 - y1
    L2 = vx * vx + vy * vy
    if L2 < 1e-12:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * vx + (py - y1) * vy) / L2))
    return math.hypot(px - (x1 + t * vx), py - (y1 + t * vy))


def clearance(pts, x, y):
    """Signed distance to the outline: + inside, - outside. This is the whole
    fit model - a feature of radius r fits at (x,y) iff clearance >= r + wall."""
    d = min(_seg_d(x, y, pts[i][0], pts[i][1],
                   pts[(i + 1) % len(pts)][0], pts[(i + 1) % len(pts)][1])
            for i in range(len(pts)))
    return d if contains(pts, x, y) else -d


def extent(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (max(xs) - min(xs), max(ys) - min(ys))


POCKET_R = 5.25       # NTAG215 10.5mm pocket
WALL = 0.6            # min material between a feature and the outline


def place_pocket(pts, step=0.4):
    """Pole of inaccessibility: the deepest interior point. The pocket does NOT
    have to be centred - offsetting it is what lets a tent or a pine work."""
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    best, bx, by = -1e9, 0.0, 0.0
    x = min(xs)
    while x <= max(xs):
        y = min(ys)
        while y <= max(ys):
            c = clearance(pts, x, y)
            if c > best:
                best, bx, by = c, x, y
            y += step
        x += step
    # refine
    for st in (0.2, 0.08, 0.03):
        improved = True
        while improved:
            improved = False
            for dx in (-st, 0, st):
                for dy in (-st, 0, st):
                    c = clearance(pts, bx + dx, by + dy)
                    if c > best + 1e-9:
                        best, bx, by = c, bx + dx, by + dy
                        improved = True
    return (bx, by, best)


def place_pegs(pts, pocket, peg_r=PEG_R, wall=0.9, n=3, hole_y=None):
    """Pick n peg positions in solid material, clear of the pocket and the
    outline. Mirrors how redaphid-portrait placed its ear + chin pegs.

    wall=0.9 (not 0.55): PRINT_LOG v5b records jaw pegs that PASSED the
    perimeter raycast yet left a wall thinner than one perimeter width, which
    printed as voids and stringing around the socket. Maximising spread alone
    actively pushes pegs toward the boundary, so spread is now maximised only
    among candidates that already clear the wall."""
    px0, py0, _ = pocket
    cands = []
    for ring in [r * 0.35 for r in range(18, 46)]:        # 6.3 .. 15.7 mm
        for k in range(72):
            a = 2 * math.pi * k / 72
            x, y = px0 + ring * math.cos(a), py0 + ring * math.sin(a)
            if clearance(pts, x, y) < peg_r + wall:
                continue
            if math.hypot(x - px0, y - py0) < POCKET_R + peg_r + 0.5:
                continue
            # the string hole is a tube along X at y=hole_y, living in the SAME
            # half as the peg sockets. A socket that lands within its band
            # breaches the cord tube - caught by a raycast reporting a socket
            # floor 0.3mm off from its siblings.
            if hole_y is not None and abs(y - hole_y) < HOLE_R + peg_r + 0.6:
                continue
            cands.append((x, y))
    if len(cands) < n:
        return None
    # greedy farthest-point spread
    best = max(cands, key=lambda p: math.hypot(p[0] - px0, p[1] - py0))
    chosen = [best]
    while len(chosen) < n:
        nxt = max(cands, key=lambda p: min(math.hypot(p[0] - q[0], p[1] - q[1])
                                           for q in chosen))
        if min(math.hypot(nxt[0] - q[0], nxt[1] - q[1]) for q in chosen) < 4.0:
            return None
        chosen.append(nxt)
    return chosen


HOLE_R = 0.6          # 1.2mm string hole (medallion gauge)
HOLE_CROWN = 2.5      # min material ABOVE the hole. black-rainbow shipped 1.6mm
                      # and is flagged in the vault as liable to snap off a
                      # bracelet - this is that lesson encoded as a gate.


def place_hole(pts, x=0.0):
    """Find a string-hole centre on the x=0 axis as high as possible while
    keeping HOLE_CROWN of material above it. Returns (y, crown) or None."""
    ys = [q[1] for q in pts]
    top = max(ys)
    y = top - HOLE_R
    while y > min(ys):
        if clearance(pts, x, y) >= HOLE_R + 0.55:
            # crown = distance straight up from the hole's top to the outline
            crown = 0.0
            probe = y + HOLE_R
            while probe < top + 1.0 and contains(pts, x, probe):
                crown += 0.05
                probe += 0.05
            if crown >= HOLE_CROWN:
                return (y, crown)
        y -= 0.1
    return None


def _tri_area(t):
    (x1, y1), (x2, y2), (x3, y3) = t
    return abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2.0


def fit_report(pts):
    """Can this silhouette actually be a bead? Returns a dict."""
    pocket = place_pocket(pts)
    pocket_ok = pocket[2] >= POCKET_R + WALL
    hole = place_hole(pts)
    pegs = (place_pegs(pts, pocket, hole_y=hole[0] if hole else None)
            if pocket_ok else None)
    w, h = extent(pts)
    return {
        "pocket": pocket, "pocket_ok": pocket_ok,
        "pegs": pegs, "pegs_ok": pegs is not None,
        "hole": hole, "hole_ok": hole is not None,
        "spread": _tri_area(pegs) if pegs else 0.0,
        "w": w, "h": h,
        "ok": (pocket_ok and pegs is not None and _tri_area(pegs) > 40.0
               and hole is not None),
    }


# ------------------------------------------------------------------- shapes
def mushroom():
    """Cap dome over a flared stem. The rave totem."""
    cap_r = 13.0
    pts = arc(0, 0.5, cap_r, 180, 0, 64)                  # dome, left to right
    pts += [(9.2, -2.6), (5.2, -3.4)]                     # under-cap right
    pts += [(4.6, -8.0), (5.6, -13.0), (-5.6, -13.0), (-4.6, -8.0)]   # stem
    pts += [(-5.2, -3.4), (-9.2, -2.6)]
    return ccw(pts)


def skull():
    cr = 12.0
    pts = arc(0, 1.5, cr, 165, 15, 56)                    # cranium
    pts += [(10.4, -4.0), (6.6, -6.2)]                    # temple -> cheek
    pts += [(6.0, -11.0), (3.2, -9.6), (0.0, -11.4), (-3.2, -9.6), (-6.0, -11.0)]
    pts += [(-6.6, -6.2), (-10.4, -4.0)]
    return ccw(pts)


def moon():
    """Gibbous, not crescent - a crescent cannot hold the core."""
    outer = arc(0, 0, 13.0, -78, 258, 72)
    inner = arc(7.6, 0, 12.4, 214, 146, 48)               # bite, right side
    return ccw(outer + inner)


def star5():
    """Fat five-point star - points short enough that the core still fits."""
    pts = []
    for i in range(5):
        a_out = 90 + i * 72
        a_in = a_out + 36
        pts.append((14.5 * math.cos(math.radians(a_out)),
                    14.5 * math.sin(math.radians(a_out))))
        pts.append((10.2 * math.cos(math.radians(a_in)),
                    10.2 * math.sin(math.radians(a_in))))
    return ccw(pts)


def pine():
    """Ponderosa - the Mogollon Rim tree. Three tiers over a trunk."""
    pts = [(0.0, 15.5)]
    pts += [(5.0, 8.2), (2.9, 8.2), (8.2, 1.4), (5.0, 1.4), (12.2, -7.0)]
    pts += [(2.4, -7.0), (2.4, -13.0), (-2.4, -13.0), (-2.4, -7.0)]
    pts += [(-12.2, -7.0), (-5.0, 1.4), (-8.2, 1.4), (-2.9, 8.2), (-5.0, 8.2)]
    return ccw(pts)


def ghost():
    pts = arc(0, 1.0, 12.0, 180, 0, 56)
    pts += [(12.0, -7.0)]
    pts += [(8.0, -11.5), (4.0, -7.5), (0.0, -11.5), (-4.0, -7.5), (-8.0, -11.5)]
    pts += [(-12.0, -7.0)]
    return ccw(pts)


def gem():
    """Faceted teardrop crystal."""
    pts = [(0.0, 14.5), (7.6, 7.4), (11.8, -0.6), (6.4, -10.0), (0.0, -13.6),
           (-6.4, -10.0), (-11.8, -0.6), (-7.6, 7.4)]
    return ccw(pts)


def cat():
    pts = [(-7.4, 7.6), (-9.6, 14.6), (-3.0, 10.6)]       # left ear
    pts += arc(0, 1.0, 12.0, 108, 72, 8)[1:-1] or []
    pts += [(3.0, 10.6), (9.6, 14.6), (7.4, 7.6)]         # right ear
    pts += arc(0, 0.0, 12.4, 44, -224, 56)
    return ccw(pts)


def alien():
    """Big cranium, tapered jaw."""
    pts = arc(0, 3.0, 12.6, 172, 8, 56)
    pts += [(8.4, -4.6), (4.4, -12.4), (0.0, -14.2), (-4.4, -12.4), (-8.4, -4.6)]
    return ccw(pts)


def flame():
    """Campfire tongue - wide base, licked tip."""
    pts = [(0.0, 16.0), (4.2, 9.0), (7.0, 10.6), (8.6, 3.0), (11.6, -1.0)]
    pts += arc(0, -3.0, 11.9, -5, -175, 40)
    pts += [(-11.6, -1.0), (-8.6, 3.0), (-7.0, 10.6), (-4.2, 9.0)]
    return ccw(pts)


def heart():
    lobe = 6.6
    pts = arc(-6.2, 5.2, lobe, 168, -12, 32)
    pts += arc(6.2, 5.2, lobe, 192, 12, 32)
    pts += [(11.4, 0.6), (0.0, -14.2), (-11.4, 0.6)]
    return ccw(pts)


def saucer():
    """UFO: dome over a wide hull."""
    pts = arc(0, 0.0, 9.4, 168, 12, 40)                   # dome
    pts += [(15.2, -2.2), (8.0, -8.4), (-8.0, -8.4), (-15.2, -2.2)]
    return ccw(pts)


def owl():
    pts = [(-8.2, 9.0), (-10.0, 14.8), (-4.6, 11.8)]      # left tuft
    pts += [(4.6, 11.8), (10.0, 14.8), (8.2, 9.0)]        # right tuft
    pts += arc(0, -0.5, 12.4, 52, -232, 56)
    return ccw(pts)


def tent():
    """Scaled 1.12x over the first draft: it missed the pocket clearance gate by
    0.05mm, which is a sizing problem, not a shape problem."""
    k = 1.12
    pts = [(0.0, 14.6), (13.6, -9.4), (7.4, -9.4), (0.0, -3.0), (-7.4, -9.4),
           (-13.6, -9.4)]
    return ccw([(x * k, y * k) for x, y in pts])


# --- string hole ------------------------------------------------------------
# The cord hole is a 1.2mm bore along X through the THICK Top half. On a circle
# a fixed y=8.0 was fine; on a silhouette the top edge moves, so the hole has to
# be placed per shape or it breaks out through the outline.
SHAPES = {
    "mushroom": mushroom, "skull": skull, "moon": moon, "star": star5,
    "pine": pine, "ghost": ghost, "gem": gem, "cat": cat, "alien": alien,
    "flame": flame, "heart": heart, "saucer": saucer, "owl": owl, "tent": tent,
}


def audit():
    rows = []
    for nm in sorted(SHAPES):
        pts = SHAPES[nm]()
        rows.append((nm, pts, fit_report(pts)))
    return rows


if __name__ == "__main__":
    print("%-9s %-4s %-7s %-5s %8s %-12s %6s %6s"
          % ("shape", "fit", "pocket", "pegs", "spread", "hole(y/crown)", "w", "h"))
    bad = []
    for nm, pts, f in audit():
        px, py, cl = f["pocket"]
        note = ""
        if not f["pocket_ok"]:
            note += "  POCKET r%.1f<%.1f" % (cl, POCKET_R + WALL)
        elif not f["pegs_ok"]:
            note += "  NO PEG TRIPLE"
        elif f["spread"] <= 40.0:
            note += "  PEGS CRAMPED"
        if not f["hole_ok"]:
            note += "  NO HOLE w/ %.1fmm CROWN" % HOLE_CROWN
        if not f["ok"]:
            bad.append(nm)
        hs = ("%.1f / %.1f" % f["hole"]) if f["hole"] else "-"
        print("%-9s %-4s %-7s %-5s %8.1f %-12s %6.1f %6.1f%s"
              % (nm, "ok" if f["ok"] else "FAIL",
                 "%.2f" % cl, "yes" if f["pegs_ok"] else "no",
                 f["spread"], hs, f["w"], f["h"], note))
    print()
    print("pocket needs clearance >= %.2f mm" % (POCKET_R + WALL))
    print("failing: %s" % (", ".join(bad) if bad else "none"))
