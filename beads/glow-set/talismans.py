"""Talisman / rune silhouettes - clean geometric archetypes, seeded per person.

WHY ANGULAR BEATS LITERAL. The 10.5mm NTAG215 pocket forces a ~19mm round mass
into the centre of every bead. A literal figure (cat, owl, flame) survives only
as a fringe around that disc, so everything reads as "circle with bumps". An
angular envelope wraps the core instead of fighting it, and hard corners stay
legible as a glowing outline where soft lobes blur.

WHY ARCHETYPES, NOT NOISE. The first version perturbed an n-gon with random
teeth, chamfers and notches. It read as LUMPY, not deliberate - the opposite of
a rune - and a winding bug in the chamfer threw thin barbs off every vertex that
would print as fragile slivers. A talisman looks MADE: symmetric, purposeful,
few decisions. So each shape is now a recognisable archetype (shield, lozenge,
stele, seal, spear, keystone, star) with seeded PROPORTIONS. Variation lives in
the numbers, identity lives in the archetype.

Every candidate is gated by min_edge() before it ships - no slivers.
"""
import hashlib
import math
import random

import shapes as S

MIN_EDGE = 1.6        # mm - shorter than this prints as a sliver
MIN_ANGLE = 26.0      # deg - sharper than this is a barb, not a point


def rng_for(name):
    h = hashlib.sha256(name.strip().lower().encode("utf-8")).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def chamfer(pts, dist):
    """Cut each corner back by `dist` mm along both adjacent edges.

    Order matters: traversing CCW you ARRIVE at a vertex along the prev edge and
    LEAVE along the next, so the prev-side point must be emitted first. The
    earlier version swapped them, which reversed winding locally and produced
    barbs."""
    if dist <= 0:
        return pts
    out = []
    n = len(pts)
    for i in range(n):
        prev, cur, nxt = pts[(i - 1) % n], pts[i], pts[(i + 1) % n]
        for other in (prev, nxt):                      # prev FIRST
            L = math.hypot(other[0] - cur[0], other[1] - cur[1]) or 1.0
            t = min(dist / L, 0.42)
            out.append((cur[0] + (other[0] - cur[0]) * t,
                        cur[1] + (other[1] - cur[1]) * t))
    return out


def min_edge(pts):
    n = len(pts)
    return min(math.hypot(pts[(i + 1) % n][0] - pts[i][0],
                          pts[(i + 1) % n][1] - pts[i][1]) for i in range(n))


def min_angle(pts):
    n = len(pts)
    worst = 180.0
    for i in range(n):
        a, b, c = pts[(i - 1) % n], pts[i], pts[(i + 1) % n]
        v1 = (a[0] - b[0], a[1] - b[1]); v2 = (c[0] - b[0], c[1] - b[1])
        n1 = math.hypot(*v1) or 1.0; n2 = math.hypot(*v2) or 1.0
        cosv = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
        worst = min(worst, math.degrees(math.acos(cosv)))
    return worst


def clean(pts):
    """Drop duplicate/near-duplicate vertices."""
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 0.05:
            out.append(p)
    if len(out) > 1 and math.hypot(out[0][0] - out[-1][0],
                                   out[0][1] - out[-1][1]) < 0.05:
        out.pop()
    return out


# ------------------------------------------------------------- archetypes
def shield(r, g):
    w = r * g.uniform(0.80, 0.95)
    sh = r * g.uniform(0.18, 0.34)          # shoulder height below the top
    return [(-w, r - sh), (-w * g.uniform(0.55, 0.85), r),
            (w * g.uniform(0.55, 0.85), r), (w, r - sh),
            (w * g.uniform(0.70, 0.92), -r * g.uniform(0.10, 0.35)),
            (0.0, -r), (-w * g.uniform(0.70, 0.92), -r * g.uniform(0.10, 0.35))]


def lozenge(r, g):
    w = r * g.uniform(0.62, 0.86)
    k = g.uniform(0.30, 0.55)               # waist height as a fraction of r
    return [(0.0, r), (w, r * k), (w * g.uniform(0.80, 1.0), -r * k),
            (0.0, -r), (-w * g.uniform(0.80, 1.0), -r * k), (-w, r * k)]


def stele(r, g):
    w = r * g.uniform(0.66, 0.84)
    sh = r * g.uniform(0.52, 0.74)          # where the shoulders start
    peak = g.uniform(0.30, 0.62)            # apex width fraction
    return [(-w, -r), (-w, sh), (-w * peak, r), (w * peak, r), (w, sh), (w, -r)]


def seal(r, g):
    n = g.choice([6, 7, 8])
    rot = math.pi / 2
    return [(r * math.cos(rot + 2 * math.pi * i / n),
             r * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]


def spear(r, g):
    w = r * g.uniform(0.50, 0.70)
    by = r * g.uniform(0.02, 0.26)          # barb height
    bw = w * g.uniform(1.18, 1.48)          # barb reach
    return [(0.0, r), (w, r * g.uniform(0.10, 0.34)), (bw, -by),
            (w * 0.52, -by - r * g.uniform(0.10, 0.20)), (0.0, -r),
            (-w * 0.52, -by - r * g.uniform(0.10, 0.20)), (-bw, -by),
            (-w, r * g.uniform(0.10, 0.34))]


def keystone(r, g):
    top = r * g.uniform(0.52, 0.74)
    bot = r * g.uniform(0.86, 1.0)
    return [(-top, r), (top, r), (bot, -r), (-bot, -r)]


def star_seal(r, g):
    n = g.choice([5, 6])
    inner = r * g.uniform(0.60, 0.72)       # deep enough to read as a star
    rot = math.pi / 2
    pts = []
    for i in range(n * 2):
        rr = r if i % 2 == 0 else inner
        a = rot + math.pi * i / n
        pts.append((rr * math.cos(a), rr * math.sin(a)))
    return pts


def cross(r, g):
    """Greek cross - the most distinct silhouette in the set, and the only one
    with concave corners."""
    a = r * g.uniform(0.30, 0.42)          # half arm width
    L = r * g.uniform(0.86, 1.0)
    return [(-a, -L), (a, -L), (a, -a), (L, -a), (L, a), (a, a),
            (a, L), (-a, L), (-a, a), (-L, a), (-L, -a), (-a, -a)]


def vesica(r, g):
    """Pointed oval on its side - wide and flat, the counterweight to all the
    tall pointed forms."""
    w = r * g.uniform(0.95, 1.0)
    h = r * g.uniform(0.66, 0.84)   # <0.66 leaves too little height to space
    k = g.uniform(0.52, 0.72)       # three pegs - the peg triangle collapses
    return [(-w, 0.0), (-w * k, h), (w * k, h), (w, 0.0), (w * k, -h),
            (-w * k, -h)]


def ziggurat(r, g):
    """Stepped terraces on a broad base - reads as built, not cut."""
    steps = g.choice([2, 3])
    bw = r * g.uniform(0.88, 1.0)
    tw = bw * g.uniform(0.34, 0.50)
    pts_r, pts_l = [], []
    for i in range(steps + 1):
        t = i / steps
        w = bw + (tw - bw) * t
        y0 = -r + 2 * r * t
        y1 = -r + 2 * r * (i + 1) / steps if i < steps else r
        pts_r += [(w, y0), (w, min(y1, r))]
        pts_l += [(-w, y0), (-w, min(y1, r))]
    return pts_r + pts_l[::-1]


def arch(r, g):
    """Flat base, domed top - a doorway/headstone form."""
    w = r * g.uniform(0.72, 0.90)
    base = -r * g.uniform(0.80, 1.0)
    n = 12
    top = [(w * math.cos(math.pi * i / n), r * 0.92 * math.sin(math.pi * i / n))
           for i in range(n + 1)]
    return [(-w, base)] + top[::-1] + [(w, base)]


# Weighted, because uniform choice let `spear` take 4 of 16 slots and every
# archetype was tall-and-pointed. The flat/wide forms are up-weighted to break
# up the arrowhead read.
ARCHETYPES = [shield, lozenge, stele, seal, spear, keystone, star_seal,
              cross, vesica, ziggurat, arch]
WEIGHTS = [3, 3, 3, 3, 1, 3, 2, 3, 3, 3, 3]


def talisman(name, r_out=16.0):
    """One seeded talisman: archetype + seeded proportions + optional chamfer."""
    g = rng_for(name)
    fn = g.choices(ARCHETYPES, weights=WEIGHTS, k=1)[0]
    pts = clean(fn(r_out, g))
    if g.random() < 0.55:
        c = g.choice([1.2, 1.8, 2.4])
        cand = clean(chamfer(pts, c))
        if min_edge(cand) >= MIN_EDGE:
            pts = cand
    return S.ccw(pts)


def ok_shape(pts):
    return min_edge(pts) >= MIN_EDGE and min_angle(pts) >= MIN_ANGLE


def fitted(name, r_out=16.0):
    """Return (pts, fit) once the shape is clean AND the hardware fits."""
    pts = talisman(name, r_out=r_out)
    if not ok_shape(pts):
        return None, None
    f = S.fit_report(pts)
    return (pts, f) if f["ok"] else (None, None)


ROSTER = ["sterling", "brycen", "eddy hart", "fm lou", "elli", "redaphid",
          "jared", "virginia", "fabian", "dylan", "kai", "nova",
          "sage", "wren", "juno", "rook"]


if __name__ == "__main__":
    print("%-10s %-10s %6s %6s %7s %7s %6s %6s"
          % ("name", "archetype", "edge", "angle", "pocket", "spread", "w", "h"))
    good = 0
    for nm in ROSTER:
        g = rng_for(nm)
        arch_name = g.choices(ARCHETYPES, weights=WEIGHTS, k=1)[0].__name__
        pts = talisman(nm)
        f = S.fit_report(pts)
        e, a = min_edge(pts), min_angle(pts)
        note = ""
        if e < MIN_EDGE: note += "  SLIVER"
        if a < MIN_ANGLE: note += "  BARB"
        if not f["ok"]: note += "  NO FIT"
        if not note: good += 1
        print("%-10s %-10s %6.2f %6.1f %7.2f %7.1f %6.1f %6.1f%s"
              % (nm, arch_name, e, a, f["pocket"][2], f["spread"],
                 f["w"], f["h"], note))
    print("\nclean and fitting: %d/%d" % (good, len(ROSTER)))
