"""Adinkra silhouettes for the glow-in-the-dark bead set.

WHAT THESE ARE. Adinkra are Akan (Asante / Gyaman, Ghana and Cote d'Ivoire)
symbols, each carrying a proverb or concept. They are stamped on cloth with
calabash stamps and badie-bark dye. Every generator below records the Akan
name, the literal translation, and the proverb, because on this product the
MEANING is the point - these get handed out and the symbol is what makes one
personal. Sources for names/meanings are cited in SOURCES at the bottom.

THE CENTRAL DIFFICULTY, stated honestly. A glow bead is a filled silhouette
on black: no colour, no shading, no relief. Many adinkra are LINE ART -
Gye Nyame, Nyansapo, Sankofa's heart-and-spiral variant, Nkyinkyim - and a
line drawing filled in is a blob. There are only two honest routes:

  (a) the symbol is already solid or has a strong closed boundary
      (Akoma, Nsoromma, Musuyidee, Sankofa's BIRD variant) -> silhouette it.
  (b) the symbol is strapwork -> THE STROKE BECOMES THE BODY: thicken each
      stroke to >= 2.5mm and let the outline of the thickened stroke be the
      silhouette, with interior voids wherever the strapwork encloses space.

Route (b) is why this file is built on signed distance fields rather than
hand-typed vertices. A stroke of width w is exactly `sd_polyline(..., w/2)`;
a union of strokes is a `min`; the silhouette is the zero contour. Marching
squares then hands back the outer ring AND every interior void for free.
Hand-typing the outline of four overlapping curls is not a thing a person
should do.

THE GATE IS ARITHMETIC, NOT TASTE. shapes.fit_report() places a 10.5mm
NTAG215 pocket, three 2.6mm pegs and a 1.2mm cord hole, and it is the gate.
Route (b) fails it far more often than it looks like it should: a 3mm stroke
has 1.5mm of clearance anywhere along it, and the pocket needs 5.85mm. So a
strapwork symbol only survives if some part of it is a genuine BLOB. That is
the single fact that decides most of this file, and REJECTED at the bottom
records the ones it killed, with numbers.

THREE GATES THIS FILE ADDS ON TOP OF fit_report, because fit_report does not
model them and each one has a physical failure behind it:

  connectivity - fit_report is happy to bless a shape made of disconnected
      rings. Adinkrahene (three concentric circles) is EXACTLY that: as ink
      it is three rings, as a printed pendant it is three loose parts. Nesting
      depth of the contour rings catches it.
  hole vs pocket - place_pegs avoids the cord hole but place_pocket does not.
      A cord bore driven through the NFC pocket destroys the tag. Dono dies
      here and it is not obvious until you compute it.
  limbs - erode the body by 0.8mm; if it falls into more than one piece some
      limb is under 1.6mm and will print as a thread.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapes as S

# ---------------------------------------------------------------- tuning
RES = 0.06            # mm per grid sample for the contour extraction
HALF = 21.0           # mm half-window the SDF is evaluated over
DP_TOL = 0.045        # mm - Douglas-Peucker tolerance on the extracted ring
MIN_STROKE = 2.5      # mm - route (b) floor. Below this a glowing stroke
                      # reads as a scratch and prints as a single bead of
                      # plastic with nothing either side of it.
MIN_TURN = 26.0       # deg - min interior angle, measured over a 1.0mm window
TURN_SPAN = 1.0       # mm - see min_turn(); a raw vertex-to-vertex angle is
                      # meaningless on a curve sampled every 0.5mm.
LIMB_ERODE = 0.8      # mm - half of the 1.6mm minimum feature size
CORD_LANE = 3.0       # mm - keep keyhole bridges out of |x| < this above y=0,
                      # because that strip is where place_hole looks.
MIN_RING = 2.0        # mm^2 - a void smaller than the 1.6mm minimum feature
                      # (area pi*0.8^2 = 2.01) cannot be printed; the slicer
                      # would bridge it anyway. Dropping it here keeps a
                      # 0.9mm-wide union artifact from failing the barb gate
                      # as a 10-degree sliver.


# =========================================================== SDF primitives
# All take (X, Y) meshgrids and return signed distance in mm, negative inside.
def sd_circle(X, Y, cx, cy, r):
    return np.hypot(X - cx, Y - cy) - r


def sd_segment(X, Y, a, b, w):
    """Capsule: a stroke of width 2*w from a to b, round caps."""
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 < 1e-12:
        return sd_circle(X, Y, ax, ay, w)
    t = np.clip(((X - ax) * vx + (Y - ay) * vy) / L2, 0.0, 1.0)
    return np.hypot(X - (ax + t * vx), Y - (ay + t * vy)) - w


def sd_polyline(X, Y, pts, w):
    """A thickened open stroke. THIS is route (b): the stroke IS the body."""
    d = sd_segment(X, Y, pts[0], pts[1], w)
    for i in range(1, len(pts) - 1):
        d = np.minimum(d, sd_segment(X, Y, pts[i], pts[i + 1], w))
    return d


def sd_box(X, Y, cx, cy, hx, hy, r=0.0):
    """Rounded box; half-extent is (hx + r, hy + r)."""
    qx = np.abs(X - cx) - hx
    qy = np.abs(Y - cy) - hy
    out = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0))
    return out + np.minimum(np.maximum(qx, qy), 0.0) - r


def sd_poly(X, Y, pts):
    """Signed distance to an arbitrary (possibly non-convex) polygon."""
    n = len(pts)
    d = np.full(X.shape, 1e9, np.float64)
    inside = np.zeros(X.shape, bool)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        vx, vy = x2 - x1, y2 - y1
        L2 = vx * vx + vy * vy or 1e-12
        t = np.clip(((X - x1) * vx + (Y - y1) * vy) / L2, 0.0, 1.0)
        d = np.minimum(d, np.hypot(X - (x1 + t * vx), Y - (y1 + t * vy)))
        if y1 != y2:
            cond = (y1 > Y) != (y2 > Y)
            xin = x1 + (Y - y1) * vx / (y2 - y1)
            inside ^= cond & (X < xin)
    return np.where(inside, -d, d)


def u(*ds):
    """Union."""
    out = ds[0]
    for d in ds[1:]:
        out = np.minimum(out, d)
    return out


def sub(d, e):
    """Cut e out of d."""
    return np.maximum(d, -e)


# ----------------------------------------------------------- stroke paths
def arc_pts(cx, cy, r, a0, a1, n=64):
    return [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
            for a in (a0 + (a1 - a0) * i / n for i in range(n + 1))]


def spiral_pts(cx, cy, r0, r1, a0, sweep, n=72):
    """Archimedean curl - a ram's horn. Under one full turn, so it never
    laps itself and there is no hairline slot between coils to print."""
    out = []
    for i in range(n + 1):
        t = i / n
        a = math.radians(a0 + sweep * t)
        r = r0 + (r1 - r0) * t
        out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def tri_ray(t_deg, r_base, half_w, r_tip):
    """A tapered star ray as a triangle: base chord of 2*half_w at r_base,
    apex at r_tip. Returned as a polygon for sd_poly / union."""
    t = math.radians(t_deg)
    ux, uy = math.cos(t), math.sin(t)
    px, py = -uy, ux
    return [(ux * r_base + px * half_w, uy * r_base + py * half_w),
            (ux * r_tip, uy * r_tip),
            (ux * r_base - px * half_w, uy * r_base - py * half_w)]


# ======================================================= contour extraction
_MS = {
    1: [(3, 0)], 2: [(0, 1)], 3: [(3, 1)], 4: [(1, 2)],
    6: [(0, 2)], 7: [(3, 2)], 8: [(2, 3)], 9: [(2, 0)],
    11: [(2, 1)], 12: [(1, 3)], 13: [(1, 0)], 14: [(0, 3)],
}


def contours(sdf, half=HALF, res=RES):
    """Marching squares on the SDF. Returns rings as lists of (x, y) mm.

    Rings come back unordered; nest() sorts outer from void. Every point sits
    on a grid edge and is derived identically from both cells that share it,
    so segments are chained by EDGE IDENTITY rather than by coordinate
    rounding - no epsilon, no dangling ends."""
    n = int(2 * half / res) + 1
    ax = np.linspace(-half, half, n)
    X, Y = np.meshgrid(ax, ax)
    F = sdf(X, Y)

    b = F < 0
    idx = (b[:-1, :-1].astype(np.uint8) | (b[:-1, 1:].astype(np.uint8) << 1) |
           (b[1:, 1:].astype(np.uint8) << 2) | (b[1:, :-1].astype(np.uint8) << 3))
    cells = np.argwhere((idx != 0) & (idx != 15))

    def interp(pa, pb, va, vb):
        t = va / (va - vb) if va != vb else 0.5
        return (pa[0] + t * (pb[0] - pa[0]), pa[1] + t * (pb[1] - pa[1]))

    segs = []
    ends = {}
    for j, i in cells:
        c = int(idx[j, i])
        v = [F[j, i], F[j, i + 1], F[j + 1, i + 1], F[j + 1, i]]
        p = [(ax[i], ax[j]), (ax[i + 1], ax[j]),
             (ax[i + 1], ax[j + 1]), (ax[i], ax[j + 1])]
        if c in (5, 10):                      # saddle: resolve on the mean
            mean = sum(v) / 4.0
            if (c == 5) == (mean < 0):
                pairs = [(3, 2), (1, 0)]
            else:
                pairs = [(3, 0), (1, 2)]
        else:
            pairs = _MS[c]
        # edge ids: 0=bottom H(i,j) 1=right V(i+1,j) 2=top H(i,j+1) 3=left V(i,j)
        eid = [("H", i, j), ("V", i + 1, j), ("H", i, j + 1), ("V", i, j)]
        epts = [interp(p[0], p[1], v[0], v[1]), interp(p[1], p[2], v[1], v[2]),
                interp(p[3], p[2], v[3], v[2]), interp(p[0], p[3], v[0], v[3])]
        for e1, e2 in pairs:
            k = len(segs)
            segs.append((eid[e1], eid[e2], epts[e1], epts[e2]))
            ends.setdefault(eid[e1], []).append(k)
            ends.setdefault(eid[e2], []).append(k)

    used = [False] * len(segs)
    rings = []
    for start in range(len(segs)):
        if used[start]:
            continue
        used[start] = True
        e0, e1, p0, p1 = segs[start]
        ring = [p0, p1]
        cur_e, cur_p = e1, p1
        while True:
            nxt = None
            for k in ends.get(cur_e, ()):
                if not used[k]:
                    nxt = k
                    break
            if nxt is None:
                break
            used[nxt] = True
            a, bb, pa, pb = segs[nxt]
            if a == cur_e:
                cur_e, cur_p = bb, pb
            else:
                cur_e, cur_p = a, pa
            if cur_e == e0:
                break
            ring.append(cur_p)
        if len(ring) > 8:
            rings.append(ring)
    return rings


def _area(pts):
    return 0.5 * sum(x1 * y2 - x2 * y1
                     for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))


def _dp(pts, tol):
    """Douglas-Peucker on a CLOSED ring: anchor at the two most distant
    vertices, simplify the two open chains, rejoin."""
    def run(ch):
        if len(ch) < 3:
            return ch
        ax_, ay_ = ch[0]
        bx_, by_ = ch[-1]
        vx, vy = bx_ - ax_, by_ - ay_
        L = math.hypot(vx, vy) or 1e-9
        worst, wi = -1.0, 0
        for i in range(1, len(ch) - 1):
            d = abs((ch[i][0] - ax_) * vy - (ch[i][1] - ay_) * vx) / L
            if d > worst:
                worst, wi = d, i
        if worst <= tol:
            return [ch[0], ch[-1]]
        return run(ch[:wi + 1])[:-1] + run(ch[wi:])

    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    a = max(range(n), key=lambda i: math.hypot(pts[i][0] - cx, pts[i][1] - cy))
    b = max(range(n), key=lambda i: math.hypot(pts[i][0] - pts[a][0],
                                               pts[i][1] - pts[a][1]))
    lo, hi = (a, b) if a < b else (b, a)
    return run(pts[lo:hi + 1])[:-1] + run(pts[hi:] + pts[:lo + 1])[:-1]


def build(sdf, tol=DP_TOL):
    """SDF -> [outer_ring, void_ring, ...] in mm, decimated, outer CCW."""
    rings = [_dp(r, tol) for r in contours(sdf)]
    rings = [r for r in rings if len(r) >= 3 and abs(_area(r)) >= MIN_RING]
    return nest(rings)


def nest(rings):
    """Order rings outer-first and orient them.

    Nesting depth is also a connectivity signal - two depth-0 rings means two
    loose parts - but audit_one measures connectivity on the raster instead,
    which is exact for touching-at-a-point cases too."""
    depth = []
    for i, r in enumerate(rings):
        d = 0
        for j, q in enumerate(rings):
            if i != j and abs(_area(q)) > abs(_area(r)) and S.contains(q, *r[0]):
                d += 1
        depth.append(d)
    order = sorted(range(len(rings)), key=lambda i: (depth[i], -abs(_area(rings[i]))))
    return [S.ccw(rings[i]) if depth[i] % 2 == 0 else S.ccw(rings[i])[::-1]
            for i in order]


# ============================================================ keyhole flatten
def flatten(rings, eps=0.0):
    """One closed point list for fit_report / the even-odd renderer / Blender.

    Voids are spliced in with a KEYHOLE: walk the outer ring to the vertex
    nearest the void, hop across, go round the void, hop back. With eps=0 the
    two hop segments are coincident, so even-odd fill cancels them exactly and
    the rendered mask is the true annulus.

    The cost is that clearance() measures distance to the hop as if it were
    real wall, so the fit solver UNDERSTATES clearance near a bridge. That is
    the safe direction: a shape that passes here passes for real.

    eps > 0 opens the hop into a hairline slit, which is what Blender's
    extrude_polygon needs (an n-gon with a zero-width slit will not
    triangulate); build_talisman's clean_mesh merge welds it shut again.
    """
    outer = list(rings[0])
    voids = rings[1:]
    if not voids:
        return outer
    plans = []
    for v in voids:
        best = None
        for i, o in enumerate(outer):
            for j, q in enumerate(v):
                d = math.hypot(o[0] - q[0], o[1] - q[1])
                # ROUTE THE HOP AWAY FROM THE CORD CORRIDOR. The bridge is a
                # fiction that only shows up as depressed clearance along it,
                # so put it where clearance is not needed. Bese Saka's shortest
                # hop ran straight down x=0 from the crown to the top void -
                # exactly the strip place_hole scans - and reported clearance
                # 0.00 for every y the cord hole wanted, dragging the hole down
                # to y=3.2 and the pocket off the centre with it.
                pen = 0.0
                for t in (0.0, 0.25, 0.5, 0.75, 1.0):
                    px = o[0] + t * (q[0] - o[0])
                    py = o[1] + t * (q[1] - o[1])
                    if py > 0.0:
                        pen = max(pen, max(0.0, CORD_LANE - abs(px)))
                score = d + 12.0 * pen
                if best is None or score < best[0]:
                    best = (score, i, j)
        _, i, j = best
        plans.append((i, v[j:] + v[:j]))
    out = list(outer)
    for i, vr in sorted(plans, key=lambda p: -p[0]):
        anchor = out[i]
        if eps > 0:
            dx, dy = vr[0][0] - anchor[0], vr[0][1] - anchor[1]
            L = math.hypot(dx, dy) or 1.0
            ox, oy = -dy / L * eps, dx / L * eps
            back = [(vr[0][0] + ox, vr[0][1] + oy),
                    (anchor[0] + ox, anchor[1] + oy)]
        else:
            back = [vr[0], anchor]
        out = out[:i + 1] + vr + back + out[i:]
    return out


# ============================================================ quality gates
def min_turn(ring, span=TURN_SPAN):
    """Smallest interior angle, measured across +-`span` mm of arc length.

    talismans.min_angle compares adjacent EDGES, which is right for a 7-vertex
    hand-typed shield and wrong here: a contour sampled every 0.5mm along a
    smooth arc shows a 178 deg vertex angle at every point and a genuine 30 deg
    spike shows up as several near-180 vertices in a row. Stepping a fixed
    ARC LENGTH either side measures the feature, not the sampling."""
    n = len(ring)
    if n < 3:
        return 0.0
    cum = [0.0]
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = cum[-1]
    if total < 4 * span:
        return 180.0

    def at(s):
        s %= total
        k = 0
        while cum[k + 1] < s:
            k += 1
        f = (s - cum[k]) / (cum[k + 1] - cum[k] or 1.0)
        a, b = ring[k % n], ring[(k + 1) % n]
        return (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]))

    worst = 180.0
    for i in range(n):
        p = ring[i]
        a, b = at(cum[i] - span), at(cum[i] + span)
        v1 = (a[0] - p[0], a[1] - p[1])
        v2 = (b[0] - p[0], b[1] - p[1])
        n1 = math.hypot(*v1) or 1.0
        n2 = math.hypot(*v2) or 1.0
        c = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
        worst = min(worst, math.degrees(math.acos(c)))
    return worst


def _raster(pts, ppm=8.0, pad=1.5):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(xs) - pad, max(xs) + pad
    y0, y1 = min(ys) - pad, max(ys) + pad
    nx = max(4, int((x1 - x0) * ppm))
    ny = max(4, int((y1 - y0) * ppm))
    X, Y = np.meshgrid(x0 + (np.arange(nx) + 0.5) / ppm,
                       y0 + (np.arange(ny) + 0.5) / ppm)
    inside = np.zeros(X.shape, bool)
    n = len(pts)
    for i in range(n):
        ax_, ay_ = pts[i]
        bx_, by_ = pts[(i + 1) % n]
        if ay_ == by_:
            continue
        cond = (ay_ > Y) != (by_ > Y)
        xin = ax_ + (Y - ay_) * (bx_ - ax_) / (by_ - ay_)
        inside ^= cond & (X < xin)
    return inside


def _components(mask):
    """Union-find CCL over the True pixels. Exact, and fast enough here."""
    h, w = mask.shape
    par = {}

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            par[rb] = ra

    for j, i in np.argwhere(mask):
        k = j * w + i
        par.setdefault(k, k)
        if i and mask[j, i - 1]:
            union(find(j * w + i - 1), k)
        if j and mask[j - 1, i]:
            union(find((j - 1) * w + i), k)
        if j and i and mask[j - 1, i - 1]:
            union(find((j - 1) * w + i - 1), k)
        if j and i < w - 1 and mask[j - 1, i + 1]:
            union(find((j - 1) * w + i + 1), k)
    return len({find(k) for k in par}) if par else 0


def _erode(mask, r_px):
    """Chamfer erosion: alternate 4- and 8-neighbour to approximate a disc."""
    m = mask.copy()
    for step in range(r_px):
        a = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) \
              & np.roll(m, 1, 1) & np.roll(m, -1, 1)
        if step % 2:
            a &= (np.roll(np.roll(m, 1, 0), 1, 1) &
                  np.roll(np.roll(m, 1, 0), -1, 1) &
                  np.roll(np.roll(m, -1, 0), 1, 1) &
                  np.roll(np.roll(m, -1, 0), -1, 1))
        a[0, :] = a[-1, :] = a[:, 0] = a[:, -1] = False
        m = a
    return m


def _seg_dist(pt, ring):
    return min(S._seg_d(pt[0], pt[1], ring[i][0], ring[i][1],
                        ring[(i + 1) % len(ring)][0], ring[(i + 1) % len(ring)][1])
               for i in range(len(ring)))


BORE_KEEPOUT = S.POCKET_R + S.HOLE_R + 0.6     # 6.45mm centre-to-centre


def place_pocket_clear(pts, hole_y, step=0.4):
    """The deepest interior point that ALSO stays off the cord bore.

    shapes.place_pocket returns the pole of inaccessibility - the single
    deepest point - which is the right answer to "how thick is this shape"
    and the wrong answer to "where does the tag go". On a heart the deepest
    point sits directly under the notch the cord hole has to use, so the
    unconstrained pocket and the bore collide even though sliding the pocket
    3mm down clears both with room to spare. The pocket only ever needed
    5.85mm of clearance, not the maximum available."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    best, bx, by = -1e9, 0.0, 0.0
    x = min(xs)
    while x <= max(xs):
        y = min(ys)
        while y <= max(ys):
            if math.hypot(x, y - hole_y) >= BORE_KEEPOUT:
                c = S.clearance(pts, x, y)
                if c > best:
                    best, bx, by = c, x, y
            y += step
        x += step
    for st in (0.2, 0.08, 0.03):
        improved = True
        while improved:
            improved = False
            for dx in (-st, 0, st):
                for dy in (-st, 0, st):
                    nx, ny = bx + dx, by + dy
                    if math.hypot(nx, ny - hole_y) < BORE_KEEPOUT:
                        continue
                    c = S.clearance(pts, nx, ny)
                    if c > best + 1e-9:
                        best, bx, by = c, nx, ny
                        improved = True
    return (bx, by, best)


def audit_one(rings):
    """fit_report (the required gate) plus the gates it does not model.

    fit_report is run first and unmodified - `fit` in the table is its verdict.
    Everything after it either measures something fit_report has no concept of
    (connectivity, cord-bore-vs-pocket, void-vs-pocket, limb width) or re-places
    the pocket under the bore constraint, which fit_report cannot express."""
    pts = flatten(rings)
    f = S.fit_report(pts)

    # 1. connectivity - would this print as one part?
    ppm = 8.0
    mask = _raster(pts, ppm)
    comps = _components(mask)

    # 2. cord bore must not breach the NFC pocket. Re-solve the pocket under
    #    that constraint rather than asking the deepest point to get lucky.
    if f["hole"]:
        hy = f["hole"][0]
        pocket = place_pocket_clear(pts, hy)
        hole_gap = math.hypot(0.0 - pocket[0], hy - pocket[1]) - \
            (S.POCKET_R + S.HOLE_R)
        pegs = (S.place_pegs(pts, pocket, hole_y=hy)
                if pocket[2] >= S.POCKET_R + S.WALL else None)
    else:
        pocket, hole_gap, pegs = f["pocket"], None, f["pegs"]
    pocket_ok = pocket[2] >= S.POCKET_R + S.WALL
    spread = S._tri_area(pegs) if pegs else 0.0

    # 3. every void must stay out of the pocket zone
    void_gap = min((_seg_dist(pocket[:2], v) - S.POCKET_R for v in rings[1:]),
                   default=None)

    # 4. limbs: erode by 0.8mm; more than one piece means something is < 1.6mm
    er = _erode(mask, int(round(LIMB_ERODE * ppm)))
    limbs = _components(er)
    er_frac = er.sum() / max(1, mask.sum())

    turn = min(min_turn(r) for r in rings)
    ok = (f["ok"] and pocket_ok and pegs is not None and spread > 40.0
          and comps == 1 and limbs == 1 and turn >= MIN_TURN
          and (hole_gap is None or hole_gap >= 0.6)
          and (void_gap is None or void_gap >= 0.6))
    return dict(f, pts=pts, pocket=pocket, pocket_ok=pocket_ok, pegs=pegs,
                pegs_ok=pegs is not None, spread=spread,
                comps=comps, limbs=limbs, er_frac=er_frac,
                turn=turn, hole_gap=hole_gap, void_gap=void_gap,
                voids=len(rings) - 1, fit_ok=f["ok"], ok_all=ok)


# ================================================================= SYMBOLS
# Each generator returns rings: [outer, void, void, ...] in mm, centred near
# the origin, sized for a ~30-32mm pendant.

def akoma():
    """Akoma - "the heart".  ROUTE (a).

    Meaning: patience, tolerance, endurance, goodwill. "Nya akoma" - take
    heart. On the Ghanaian monuments it is glossed simply "Endurance".
    Note: this is the one symbol whose silhouette is also a generic heart, so
    it carries its meaning only if it is labelled."""
    def f(X, Y):
        return u(sd_circle(X, Y, -6.0, 4.8, 7.3),
                 sd_circle(X, Y, 6.0, 4.8, 7.3),
                 sd_poly(X, Y, [(-13.1, 4.8), (13.1, 4.8), (0.0, -15.4)]))
    return build(f)


def akoma_ntoaso():
    """Akoma Ntoaso - "joined / linked hearts".  ROUTE (a).

    Meaning: understanding, agreement, unity, the charter of a shared
    obligation. Four hearts fused at the centre - the solid hub is what makes
    it fit, and it is also the whole idea of the symbol.

    Arms on the AXES, not the diagonals. Drawn as an X the top of the outline
    at x=0 is the notch between two arms, which leaves the cord hole nowhere
    to go above the pocket; with an arm pointing up its round cap gives 2.5mm
    of crown. A stamp carries no canonical rotation, so this costs nothing.

    THE CLEFT HAS TO SHOW. First pass ran the arm capsule all the way out to
    the lobe centres, and its round cap filled the notch between them: four
    pairs of circles on a lumpy plus, no hearts. Stopping the arm at ARM (well
    short of LOBE) leaves a 4.4mm cleft between each pair, which is what makes
    the tip read as a heart rather than as two dots.

    THE ARMS ALSO HAVE TO SHOW. With LOBE=11.4/LR=4.4 the lobes of adjacent
    arms passed within 1.2mm of each other, the gaps between the arms closed
    up, and the bead read as a ring of eight circles - i.e. as Ohene Aniwa,
    which is already in the set. Pushing the lobes out and slimming them opens
    the inter-arm gap to ~3mm, and the cross of four hearts comes back."""
    ARM, LOBE, W = 9.6, 12.2, 2.8
    LO, LR = 4.6, 3.9

    def f(X, Y):
        d = sd_box(X, Y, 0, 0, 4.4, 4.4, 1.9)
        for k in range(4):
            t = math.radians(90 * k)
            ux, uy = math.cos(t), math.sin(t)
            px, py = -uy, ux
            d = u(d, sd_segment(X, Y, (0, 0), (ux * ARM, uy * ARM), W),
                  sd_circle(X, Y, ux * LOBE + px * LO, uy * LOBE + py * LO, LR),
                  sd_circle(X, Y, ux * LOBE - px * LO, uy * LOBE - py * LO, LR))
        return d
    return build(f)


def nsoromma():
    """Nsoromma - "child of the heavens", the star.  ROUTE (a).

    Meaning: "Oba Nyankonsoromma te Nyame so na onnte ne ho so" - the child
    of the Supreme Being leans on God and not on himself. Faith, guardianship,
    dependence on a higher power. Eight blunt rays on a fat hub; the hub is
    sized by the peg ring, not by taste."""
    HUB, RB, HW, RT = 9.6, 5.0, 3.4, 16.0

    def f(X, Y):
        d = sd_circle(X, Y, 0, 0, HUB)
        for k in range(8):
            d = u(d, sd_poly(X, Y, tri_ray(90 + 45 * k, RB, HW, RT)))
        return d
    return build(f)


def musuyidee():
    """Musuyidee (also Krapa) - "that which removes bad luck".  ROUTE (a).

    Meaning: good fortune, sanctity, spiritual balance and the uprightness of
    the soul. Drawn as a cross patee - four flared arms cut back to a deep
    notch. The most structurally comfortable symbol in the set: solid
    everywhere the hardware needs to be."""
    L, FO, M = 15.4, 8.6, 6.8
    m = M / math.sqrt(2.0)
    pts = []
    for k in range(4):
        c, s = math.cos(math.radians(90 * k)), math.sin(math.radians(90 * k))
        def rot(x, y):
            return (x * c - y * s, x * s + y * c)
        pts += [rot(L, -FO), rot(L, FO), rot(m, m)]
    return build(lambda X, Y: sd_poly(X, Y, pts))


def fawohodie():
    """Fawohodie - "independence".  ROUTE (a).

    Meaning: freedom, emancipation, self-determination. "Fawohodie ene obre
    na enam" - independence comes with its responsibilities. Four arms with
    forked tips and a pinched waist between them.

    Arms on the AXES for the same reason as Akoma Ntoaso: as an X the waist
    is the highest point at x=0 and sits at y=6.6, so the cord hole ends up
    below the tag pocket.

    The first pass used a shallow 4mm fork and ran the arm straight from the
    waist to the tip. It rendered as a lumpy plus with flat banners on it -
    unreadable. What makes this symbol legible is the CUP: a 6mm-deep fork,
    and concave arm flanks (the SHOULDER vertex) so the arm necks down before
    it flares."""
    TIP, FORK, NOTCH = 16.0, 16.0, 11.0
    SHOULDER, SH_A, WAIST = 9.4, 28.0, 6.3
    pts = []
    for k in range(4):
        t0 = 90 * k
        for a, r in ((t0 - FORK, TIP), (t0, NOTCH), (t0 + FORK, TIP),
                     (t0 + SH_A, SHOULDER), (t0 + 45, WAIST),
                     (t0 + 90 - SH_A, SHOULDER)):
            pts.append((r * math.cos(math.radians(a)),
                        r * math.sin(math.radians(a))))
    return build(lambda X, Y: sd_poly(X, Y, pts))


def nyame_dua():
    """Nyame Dua - "God's tree", the altar.  REJECTED ON THE RENDER.

    Meaning: the presence and protection of God. A forked post holding a pot
    of water and herbs stood in Akan compounds; the symbol is its plan view.

    This one passes every number in the audit - pocket 6.90, three pegs,
    spread 148, 4.2mm of crown - and still does not ship, because on the glow
    sheet it reads as a generic four-leaf clover with four needles stuck in
    it. Two separate failures: the spikes are too thin to register as the
    altar's arms, and what is left is close enough to Akoma Ntoaso that in a
    bowl of beads you could not tell them apart. Kept here as code because
    "passes the arithmetic, fails the eye" is a real category and this is the
    cleanest example of it in the set."""
    HUB, C, P = 6.9, 10.2, 4.6

    def f(X, Y):
        d = sd_circle(X, Y, 0, 0, HUB)
        for k in range(4):
            t = math.radians(45 + 90 * k)
            d = u(d, sd_circle(X, Y, C * math.cos(t), C * math.sin(t), P))
            d = u(d, sd_poly(X, Y, tri_ray(90 * k, 6.0, 2.4, 15.6)))
        return d
    return build(f)


def ohene_aniwa():
    """Ohene Aniwa - "the king's eyes".  ROUTE (a).

    Meaning: vigilance, watchfulness, the reach of a ruler's attention.
    Eight eyes on short spokes around a hub. Reads as a rosette glowing, and
    the knobs are exactly where the pegs and the cord hole want to be."""
    HUB, SP, KN, W = 6.8, 11.2, 4.0, 1.6

    def f(X, Y):
        d = sd_circle(X, Y, 0, 0, HUB)
        for k in range(8):
            t = math.radians(90 + 45 * k)
            e = (SP * math.cos(t), SP * math.sin(t))
            d = u(d, sd_segment(X, Y, (0, 0), e, W), sd_circle(X, Y, e[0], e[1], KN))
        return d
    return build(f)


def dwennimmen():
    """Dwennimmen - "ram's horns".  ROUTE (b), stroke width 4.6mm.

    Meaning: humility together with strength. "It is the heart and not the
    horns that leads a ram to bully" - the ram fights fiercely but submits to
    slaughter; strength that knows when to yield.

    WHY CURLS AND NOT RINGS. The first attempt drew each horn as a C-shaped
    arc with its opening facing the centre, which puts the enclosed void
    directly behind the gap - so the central boss can only seal the gap by
    also eating the void. An Archimedean curl has no enclosed void at all,
    is what a horn actually looks like, and prints without a hairline slot."""
    BOSS, W = 7.2, 2.4

    def f(X, Y):
        d = sd_circle(X, Y, 0, 0, BOSS)
        for sx in (-1, 1):
            for sy in (-1, 1):
                cx, cy = 7.3 * sx, 7.5 * sy
                a0 = math.degrees(math.atan2(-cy, -cx))
                d = u(d, sd_polyline(
                    X, Y, spiral_pts(cx, cy, 1.9, 6.8, a0, 320 * sx * sy), W))
        return d
    return build(f)


def bese_saka():
    """Bese Saka - "a sack of cola nuts".  ROUTE (b), band width 4.9mm.

    Meaning: affluence, abundance, plenty - and, because cola nuts are the
    gift that opens every Akan negotiation, togetherness and the duty to
    share. Four rings of nuts with true glowing voids in them.

    Rotated 45 deg from the usual diagonal layout so a lobe sits at the top:
    the cord hole needs 2.5mm of crown above it, and on the diagonal layout
    the top of the outline at x=0 is a notch, not a lobe.

    VOID SIZE IS THE WHOLE READ, AND THE CORD HOLE SIZES IT. At 4mm across the
    voids rendered as pinholes and the bead read as a clover with dots rather
    than four rings of nuts. Opening them to 6mm then failed by 0.05mm, which
    is worth writing down: the cord hole must clear the void below it by 1.15mm
    AND carry 2.5mm of crown above it, so the band it lives in gives a usable
    window of only

        RO - RV - 4.25   mm

    and at RO 7.3 / RV 3.0 that window was 0.05mm wide - place_hole stepping in
    0.1mm increments simply stepped over it, fell through the void, and landed
    at y=2.8 with the pocket shoved off-centre behind it. These numbers hold
    the window at ~1.0mm, which is a margin rather than a coincidence.

    Constraints, all binding: C - RV >= 5.85 (void off the pocket),
    RO - RV >= 4.4 (band thick enough for a peg), RO - RV >= 5.25 (cord
    window), BOSS < C - RV (hub must not eat the void)."""
    C, RO, RV, BOSS = 8.6, 7.7, 2.4, 5.9

    def f(X, Y):
        d = sd_circle(X, Y, 0, 0, BOSS)
        for k in range(4):
            t = math.radians(90 * k)
            d = u(d, sd_circle(X, Y, C * math.cos(t), C * math.sin(t), RO))
        for k in range(4):
            t = math.radians(90 * k)
            d = sub(d, sd_circle(X, Y, C * math.cos(t), C * math.sin(t), RV))
        return d
    return build(f)


def sankofa():
    """Sankofa - "san-ko-fa": go back and fetch it.  ROUTE (a), asymmetric.

    Meaning: "Se wo were fi na wosan kofa a yenkyi" - it is not taboo to go
    back and fetch what you forgot. Learn from the past to build the future.

    Two forms exist. The heart-and-spiral one is strapwork and is rejected
    below; THIS is the bird form - body forward, head turned back over its
    own tail - and it is a genuine filled silhouette, the best glow shape in
    the set.

    THE PEG PROBLEM, and why the tail is a fan. Three pegs must sit 7.05mm
    clear of the pocket centre with 2.2mm of wall, and on a bird whose body is
    one 8.4mm disc that rules the body out entirely - a peg 7.05mm from the
    centre of an 8.4mm disc has 1.35mm of wall. So the pegs live in the head,
    the tail and the neck, the cord hole then claims the neck, and the tail has
    to be broad enough to hold two of them 4mm apart on its own."""
    def f(X, Y):
        body = sd_circle(X, Y, 1.2, 1.0, 8.6)
        tail = sd_poly(X, Y, [(3.5, 5.5), (17.0, 12.8), (17.4, 4.2),
                              (9.5, -3.2)])
        # The neck arches off the breast, over, and back. Its radius is set so
        # the opening under it is a REAL void (~10mm2) rather than the 0.6mm2
        # crack the first pass left between the stroke's inner edge and the
        # body - a crack that read as a 10-degree barb and printed as nothing.
        neck = sd_polyline(X, Y, arc_pts(-1.0, 5.6, 7.6, 20, 186, 40), 2.4)
        # The head sits clear of the body and hangs off the neck. At (-8.4,5.0)
        # it overlapped the body by 1.5mm and the "looking backward" - the
        # entire point of the symbol - dissolved into the breast.
        head = sd_circle(X, Y, -9.8, 6.6, 3.4)
        # the beak is a tapered CAPSULE, not a triangle: as a triangle it met
        # the head at a 10 deg spike, which is a barb that snaps off a
        # bracelet and glows as a scratch.
        beak = u(sd_segment(X, Y, (-10.6, 4.4), (-7.8, 1.4), 1.45),
                 sd_segment(X, Y, (-7.8, 1.4), (-6.4, -0.2), 0.95))
        legs = u(sd_polyline(X, Y, [(-2.4, -6.6), (-3.4, -12.2),
                                    (-6.4, -13.8)], 1.35),
                 sd_polyline(X, Y, [(3.6, -6.6), (4.2, -12.2),
                                    (1.4, -13.8)], 1.35))
        return u(body, tail, neck, head, beak, legs)
    return build(f)


SYMBOLS = {
    "akoma": akoma,
    "akoma_ntoaso": akoma_ntoaso,
    "nsoromma": nsoromma,
    "musuyidee": musuyidee,
    "fawohodie": fawohodie,
    "ohene_aniwa": ohene_aniwa,
    "dwennimmen": dwennimmen,
    "bese_saka": bese_saka,
    "sankofa": sankofa,
}


# ================================================================ REJECTED
# Implemented ON PURPOSE so the rejection is a measurement and not an
# opinion. Run `python adinkra.py --rejects` for the numbers.

def adinkrahene():
    """Adinkrahene - "chief of the adinkra".  REJECTED: three loose parts.

    Meaning: greatness, charisma, leadership - the symbol said to have
    inspired all the others. Three concentric circles. As ink that is one
    mark; as a printed pendant it is three separate rings with nothing joining
    them. Adding spokes to connect them makes a wheel, which is a different
    symbol. There is no honest version of this shape as a single body."""
    def f(X, Y):
        r = np.hypot(X, Y)
        d = sd_circle(X, Y, 0, 0, 5.0)
        for a, b in ((7.4, 10.2), (12.6, 15.4)):
            d = np.minimum(d, np.maximum(r - b, a - r))
        return d
    return build(f)


def dono():
    """Dono - the tension "talking" drum.  REJECTED: solver, not shape.

    Meaning: praise, appellation, goodwill, rhythm - the drum that speaks the
    tonal language of Akan praise poetry, hence the name "talking drum".

    THE PREDICTION WAS WRONG AND THE MEASUREMENT IS WORTH KEEPING. I expected
    this to die because the widest part of an hourglass is a lobe and the cord
    hole wants the same lobe. It does not: an hourglass has TWO lobes, so the
    pocket simply takes the lower one. Re-solved that way it is one of the
    best shapes here - pocket 6.38, three pegs, spread 143, cord bore 14.6mm
    clear of the tag.

    It is rejected anyway because shapes.place_pocket returns the pole of
    inaccessibility, and on a symmetric hourglass that lands in the UPPER
    lobe; the cord hole then strands the pegs in the waist and the spread
    collapses to 16.6 against a minimum of 40. So fit_report says no to a
    shape that is physically fine. The fix is one of: teach place_pocket about
    the cord hole (place_pocket_clear in this file already does exactly that,
    and would want promoting into shapes.py), or draw the drum with a
    deliberately larger lower head - which is a real design change, not a
    tweak, so it is not made here."""
    return build(lambda X, Y: sd_poly(X, Y, [
        (-11.6, 15.0), (11.6, 15.0), (3.0, 1.4), (3.0, -1.4),
        (11.6, -15.0), (-11.6, -15.0), (-3.0, -1.4), (-3.0, 1.4)]))


def fihankra():
    """Fihankra - "an enclosed compound house".  REJECTED: no pocket.

    Meaning: security, safety, solidarity, the household as a walled unit
    with a single entrance. The courtyard void is the entire idea, and it is
    also what kills it: with the courtyard open, the frame is ~5mm of band
    and the largest disc that fits in it is about 3.6mm, against the 5.85mm
    the NFC pocket needs. Shrinking the courtyard until the pocket fits
    leaves a dot, and the symbol is gone."""
    def f(X, Y):
        outer = np.maximum(
            np.maximum(25.84 - np.hypot(X - 36.04, Y), 25.84 - np.hypot(X + 36.04, Y)),
            np.maximum(25.84 - np.hypot(X, Y - 36.04), 25.84 - np.hypot(X, Y + 36.04)))
        return sub(outer, sd_box(X, Y, 0, 0, 5.0, 5.0))
    return build(f)


def epa():
    """Epa - "handcuffs".  REJECTED: band too thin for the pocket.

    Meaning: law, justice, and the obligations that bind captive to captor -
    "onii a ope se obedi hene daakye no, firi ase sua kanea" is often paired
    with it. HEAVY MEANING: epa is also read as slavery and captivity, which
    is a poor thing to hand a stranger at a festival. Geometry rejects it
    anyway: a 15mm diamond with a 9.6mm diamond cut out is a 3.8mm band."""
    def f(X, Y):
        dia = np.abs(X) + np.abs(Y)
        ring = np.maximum(dia - 15.0, 9.6 - dia)
        return u(ring, sd_circle(X, Y, -4.4, 0, 3.0), sd_circle(X, Y, 4.4, 0, 3.0))
    return build(f)


def aya():
    """Aya - "the fern".  REJECTED: nothing on it is wider than its stem.

    Meaning: endurance, resourcefulness, defiance - "I am not afraid of you,
    I am independent of you". The fern grows where little else will. As a
    silhouette it is a 3mm stem with 2mm leaflets: the largest disc anywhere
    inside it is about 1.6mm, against 5.85mm needed."""
    def f(X, Y):
        d = sd_segment(X, Y, (0, -15.5), (0, 14.0), 1.6)
        for i in range(7):
            y = -11.0 + i * 3.6
            L = 11.5 - i * 1.3
            d = u(d, sd_segment(X, Y, (0, y), (L, y + 3.0), 1.1),
                  sd_segment(X, Y, (0, y), (-L, y + 3.0), 1.1))
        return d
    return build(f)


REJECTED = {
    "adinkrahene": adinkrahene, "dono": dono, "fihankra": fihankra,
    "epa": epa, "aya": aya, "nyame_dua": nyame_dua,
}

# Rejected on inspection, without code, because the failure is the same one
# every time and it is visible in the reference: the whole mark is stroke, so
# nowhere on it is 11.7mm of solid material.
REJECTED_ON_SIGHT = {
    "gye_nyame": "'Except God' - the omnipotence of the Supreme Being. The "
                 "most famous adinkra there is, and pure strapwork: filled in "
                 "it is an unreadable blob, thickened it is still a 4mm ribbon.",
    "nyansapo": "'The wisdom knot' - wisdom, ingenuity, "
                "'a wise person can untie a knot'. Interlaced strapwork.",
    "sankofa_heart": "The heart-and-spiral Sankofa. Same meaning as the bird, "
                     "but the spirals are 2mm line art. Use the bird.",
    "nkyinkyim": "'Twisting' - initiative, dynamism, the twists of life's "
                 "journey. A meander of bars; no solid region anywhere.",
    "osram_ne_nsoromma": "'The moon and the star' - faithfulness, love, "
                         "harmony. The star is a separate island from the "
                         "crescent, so it is two parts, not one bead.",
    "nkonsonkonson": "'Chain link' - unity, human relations, 'we are linked "
                     "in both life and death'. Two rings, 3mm band.",
    "akofena": "'Sword of war' - courage, valour, heroism. Two crossed "
               "swords; only the crossing is solid and it is ~6mm across.",
    "denkyem": "'The crocodile' - adaptability, 'it lives in water yet "
               "breathes air'. Line-art creature with a hatched body.",
    "nsaa": "'Nea onnim nsaa oto n'ago' - he who cannot tell a real Nsaa "
            "blanket buys a fake. Excellence, authenticity. A blocky "
            "meander, all 3mm bars.",
    "mframadan": "'Wind-resistant house' - fortitude, preparedness. A grid "
                 "of bars.",
}


def audit(which=None):
    src = which or SYMBOLS
    return [(nm, src[nm]()) for nm in sorted(src)]


# Why each REJECTED shape is out, in one line. Three different kinds of no:
# the geometry cannot hold the hardware, the stock solver cannot find the
# placement that exists, or it passes every number and reads wrong.
REJECT_REASON = {
    "adinkrahene": "3 concentric rings = 3 loose parts; no single-body version",
    "aya": "stem/leaflets are 2-3mm; largest disc inside is 2.0mm",
    "dono": "SOLVER, not shape - place_pocket takes the upper lobe; see docstring",
    "epa": "diamond band is 3.8mm; cuff discs are loose parts",
    "fihankra": "courtyard void leaves a 5mm frame; best disc 3.6mm",
    "nyame_dua": "PASSES EVERY GATE - rejected on the render, reads as a clover"
                 " and collides with akoma_ntoaso",
}


def _row(nm, rings, r):
    hg = "-" if r["hole_gap"] is None else "%.1f" % r["hole_gap"]
    vg = "-" if r["void_gap"] is None else "%.1f" % r["void_gap"]
    hs = ("%.1f/%.1f" % r["hole"]) if r["hole"] else "-"
    note = []
    if not r["pocket_ok"]:
        note.append("POCKET %.2f<%.2f" % (r["pocket"][2], S.POCKET_R + S.WALL))
    elif not r["pegs_ok"]:
        note.append("NO PEG TRIPLE")
    elif r["spread"] <= 40.0:
        note.append("PEGS CRAMPED")
    if not r["hole_ok"]:
        note.append("NO HOLE w/ %.1fmm CROWN" % S.HOLE_CROWN)
    if r["comps"] != 1:
        note.append("%d LOOSE PARTS" % r["comps"])
    if r["limbs"] != 1:
        note.append("LIMB <%.1fmm" % (2 * LIMB_ERODE))
    if r["turn"] < MIN_TURN:
        note.append("BARB %.0fdeg" % r["turn"])
    if r["hole_gap"] is not None and r["hole_gap"] < 0.6:
        note.append("CORD BORE IN POCKET")
    if r["void_gap"] is not None and r["void_gap"] < 0.6:
        note.append("VOID IN POCKET")
    if nm in REJECT_REASON:
        note.append(REJECT_REASON[nm])
    print("%-13s %-4s %6.2f %5s %6.1f %9s %5s %5s %2d %2d %5.0f %6.1f %6.1f  %s"
          % (nm, "ok" if r["ok_all"] else "FAIL", r["pocket"][2],
             "yes" if r["pegs_ok"] else "no", r["spread"], hs, hg, vg,
             r["voids"], r["comps"], r["turn"], r["w"], r["h"],
             "; ".join(note)))


SOURCES = """
Names, literal translations and proverbs cross-checked against:
  - R. S. Rattray, "Religion and Art in Ashanti" (Oxford, 1927), plate of 53
    adinkra motifs. Public domain; the primary ethnographic record.
  - W. Bruce Willis, "The Adinkra Dictionary: A Visual Primer on the Language
    of Adinkra" (Pyramid Complex, 1998).
  - G. F. Kojo Arthur, "Cloth as Metaphor: (Re)reading the Adinkra Cloth
    Symbols of the Akan of Ghana" (2001).
  - adinkrasymbols.org, which compiles Willis and Arthur.
  - en.wikipedia.org/wiki/Adinkra_symbols for the history: Bowdich recorded
    adinkra cloth in Kumasi in 1817, BEFORE the 1818-19 Gyaman war, so the
    popular story that the Asante took the craft from Gyaman king Nana Kwadwo
    Agyemang Adinkra is disproven by the dating.

Reference images: Wikimedia Commons "Category:Adinkra" (277 files surveyed).
The individually-named symbol plates used here are CC BY-SA 3.0/4.0 (uploaders
incl. Kwame8, ZSM, AdinkraNkyea) and the Rattray 1927 plate is public domain.
Attribution is required if any reference image is redistributed; the polygons
in this file are original parametric constructions, not traced from them.
"""


if __name__ == "__main__":
    rejects = "--rejects" in sys.argv
    src = REJECTED if rejects else SYMBOLS
    print("%-13s %-4s %6s %5s %6s %9s %5s %5s %2s %2s %5s %6s %6s  %s"
          % ("symbol", "fit", "pocket", "pegs", "spread", "hole y/cr",
             "h-gap", "v-gap", "vd", "pc", "turn", "w", "h", "note"))
    good = 0
    for nm, rings in audit(src):
        r = audit_one(rings)
        if r["ok_all"]:
            good += 1
        _row(nm, rings, r)
    print()
    print("passing: %d/%d      (pocket needs >= %.2fmm clearance)"
          % (good, len(src), S.POCKET_R + S.WALL))
    if not rejects:
        print("run with --rejects to see the shapes that did not make it")
