"""Chinese ornamental silhouettes for the glow bead set.

THE BRIEF, RESTATED AS A FILTER. These print in single-colour strontium-
aluminate PLA, so at night the bead is a lit body on black: the OUTLINE is the
entire design. No colour, no shading, no engraved detail survives. A motif
earns a slot here only if it is legible as a PURE FILLED SHAPE, and a good half
of the work below was deciding honestly which famous Chinese motifs are not.
Ten ship. Six were built, audited, rendered and cut; three more were rejected
on arithmetic before there was anything to render. All of them are recorded, in
TESTED and REJECTED, because "this will not read" is a claim that has to be
tested rather than asserted.

CUSP DEPTH IS THE WHOLE GAME. An earlier Gothic-foil attempt in this repo
failed by making lobes fat and cusps shallow, so it read as clover. The fix is
not taste, it is construction: a historical foliate form is a UNION OF LOBE
CIRCLES whose neighbours are very nearly tangent, and that produces a deep
re-entrant cusp by construction rather than by eye. Measured off the
cloud-collar plates the cusp valley sits at 0.42-0.50 of the outer radius for
4-fold pieces and about 0.72 for 8-fold ones; solving the tangency condition
gives cos(pi/n)/(1+sin(pi/n)) = 0.414 for n=4 and 0.668 for n=8. The historical
proportions ARE the near-tangent foil. `solve_lobes` solves the circle geometry
and everything here runs at depth 0.97.

AND DEPTH STILL IS NOT ENOUGH, WHICH COST A ROUND. A four-foil of CIRCULAR
lobes reads as a four-leaf clover no matter how deep its cusps are cut - that
was the clearest failure in the first render. What fixes it is the shape of the
lobe, not the depth of the gap: `foil` also takes vesica PETALS, pointed at
both ends, and the same four-fold form built from ogee points reads as
architecture (`haitang`). Round lobes and pointed petals are not
interchangeable, and the distinction is historical too - Tang mirrors come in
round-lobed mallow (葵花) and pointed caltrop (菱花) forms.

READ THE REFERENCE TWICE. The cloud head was built first as two lobes with a
dip on the centre line, and every variant of it rendered as a HEART, because
that structure IS a heart. Zooming into the plates showed the opposite: the
cloud head is a TREFOIL whose centre projects OUTWARD, flanked by scrolls that
curl back. The same misreading made the collar an eight-lobed flower - its
four-fold identity comes from four POINTS standing proud of a scrolled band,
not from deep valleys between fat lappets.

THE CENTRAL-VOID CONFLICT, which is engineering and not style. The bi disc, the
cash coin, the pan chang knot, the shou roundel, the bagua and every lattice
put their identity in the MIDDLE of the form - a hole, a woven grid, a
character, a ring of trigrams. The bead puts a 10.5mm NTAG215 pocket there.
`shapes.place_pocket` needs 5.85mm of clearance, so on a 30mm blank an annulus
can host the pocket only if it is at least 11.7mm wide, i.e. inner radius 3.3mm
or less - and at that radius the pocket fills the ring edge to edge with
nothing left for three pegs. A real bi's hole is 0.20-0.30 of its diameter
(measured across 36 Commons plates), so the true bi is not tight, it is
impossible below about 44mm. Nor is the outer annulus free: the peg ring sits
at r~12.8 and the cord bore crosses the top, so a ring of ornamental voids has
almost nowhere to live either. That is one arithmetic argument, and it disposes
of six motifs.

VOIDS. Interior through-holes are allowed and are modelled explicitly: a motif
carries `voids`, polygons subtracted from the body in BOTH halves. They are NOT
handed to `shapes.fit_report`, because that solver models a single simple
outline and stitching voids in through keyhole bridges would put phantom
zero-width walls into its distance field and move the pocket. The outline is
gated there, unchanged; `void_report` gates the voids separately against the
pocket, the pegs, the cord bore and each other.

ONE THING THAT LOOKS LIKE A BUG AND IS NOT. A cord hole may sit directly over
the NFC pocket in plan - `hulu` and the rejected `yuanbao` both do. They never
touch: `build_glow_medallion.py` cuts the pocket into the BOTTOM half's inner
face and bores the cord hole entirely inside the THICK top half, so the two are
separated by the seam plane. Do not add a gate for it.

REFERENCES. Proportions were measured off Wikimedia Commons plates, principally
Category:Cloud collar, Category:Yunjian, Category:Bi discs,
Category:Chinese cash coins, Category:Pan Chang knots and
Category:Latticed windows in China. Those categories mix licences - CC0, CC BY,
CC BY-SA and public-domain museum photography - so nothing from them is
redistributed here. Only measurements and proportions were taken, and the
generated geometry below is original.

    uv run python beads/glow-set/chinese.py           # audit the family
    uv run python beads/glow-set/chinese.py --all     # and the cut motifs
    uv run python beads/glow-set/preview_chinese.py   # glow contact sheet
"""
import math
import os
import sys
from collections import namedtuple

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapes as S
import talismans as T

R_OUT = 15.0          # nominal outer radius -> a 30mm charm
MIN_FEATURE = 1.6     # mm of material; thinner prints as a sliver
MIN_GAP = 0.5         # mm of air; narrower than this the nozzle cannot resolve
MIN_CONVEX = T.MIN_ANGLE   # deg - sharper than this is a barb, not a point;
                      # shared with the talisman family so the two agree
MIN_NOTCH = 18.0      # deg - a sharper re-entrant cusp is a crack starter
ANGLE_SPAN = 0.7      # mm - arc length at which angles are measured, so the
                      # number describes the real form and not the sampling

Motif = namedtuple("Motif", "pts voids note")


# ======================================================================
# polygon utilities
# ======================================================================
def _perp_d(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    if L < 1e-12:
        return math.hypot(px - ax, py - ay)
    return abs(dy * (px - ax) - dx * (py - ay)) / L


def _rdp_open(chain, tol):
    """Iterative Douglas-Peucker on an open chain."""
    keep = [False] * len(chain)
    keep[0] = keep[-1] = True
    stack = [(0, len(chain) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        worst, wi = -1.0, i
        for k in range(i + 1, j):
            d = _perp_d(chain[k], chain[i], chain[j])
            if d > worst:
                worst, wi = d, k
        if worst > tol:
            keep[wi] = True
            stack.append((i, wi))
            stack.append((wi, j))
    return [p for p, k in zip(chain, keep) if k]


def simplify(pts, tol=0.03):
    """Decimate a densely sampled outline without moving it more than `tol`.

    Why this exists: the foil generators emit ~2000 points so the render is
    smooth, but `shapes.place_pocket` scans a grid calling `clearance` against
    every segment, so cost is linear in vertex count and a 2000-gon makes the
    audit take minutes. Splitting at the two extreme points keeps the closed
    curve's extremes pinned, so cusps and lobe apexes always survive."""
    if len(pts) < 4:
        return list(pts)
    i0 = max(range(len(pts)), key=lambda i: pts[i][0])
    rot = pts[i0:] + pts[:i0]
    i1 = max(range(len(rot)), key=lambda i: _perp_d(rot[i], rot[0], rot[len(rot) // 2]))
    i1 = max(i1, 1)
    a = _rdp_open(rot[:i1 + 1], tol)
    b = _rdp_open(rot[i1:] + [rot[0]], tol)
    out = a[:-1] + b[:-1]
    return S.ccw(out)


def resample(pts, spacing=ANGLE_SPAN):
    """Points at fixed arc length around a closed polygon.

    Angles must be measured on this, not on the raw sampling: a 2000-gon has
    0.05mm edges and every vertex reads as ~180 degrees, which says nothing
    about whether a cusp is a printable notch or a crack."""
    n = len(pts)
    segs = [(pts[i], pts[(i + 1) % n]) for i in range(n)]
    lens = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in segs]
    total = sum(lens)
    if total < 1e-9:
        return list(pts)
    out, target, acc, i = [], 0.0, 0.0, 0
    while target < total and i < len(segs):
        while i < len(segs) and acc + lens[i] < target:
            acc += lens[i]
            i += 1
        if i >= len(segs):
            break
        (ax, ay), (bx, by) = segs[i]
        t = (target - acc) / (lens[i] or 1.0)
        out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
        target += spacing
    return out


def signed_angles(pts):
    """(min convex angle, min re-entrant notch angle) in degrees.

    Split, because the two failure modes are different objects. A sharp CONVEX
    vertex is a barb: a sliver of material that snaps off. A sharp CONCAVE
    vertex is a notch: a gap the nozzle cannot enter and a stress riser that
    starts a crack. `talismans.min_angle` conflates them, which would reject
    every properly cusped foil for having good cusps."""
    q = resample(S.ccw(pts))
    n = len(q)
    conv, notch = 180.0, 180.0
    for i in range(n):
        a, b, c = q[(i - 1) % n], q[i], q[(i + 1) % n]
        v1 = (a[0] - b[0], a[1] - b[1])
        v2 = (c[0] - b[0], c[1] - b[1])
        n1 = math.hypot(*v1) or 1.0
        n2 = math.hypot(*v2) or 1.0
        cs = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
        ang = math.degrees(math.acos(cs))
        # cross product sign: CCW winding -> positive means the interior angle
        # is the convex one.
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        if cross < 0:
            conv = min(conv, ang)
        else:
            notch = min(notch, ang)
    return conv, notch


# ======================================================================
# lobe / cusp machinery
# ======================================================================
def tangent_ratio(n):
    """Cusp radius / outer radius when adjacent lobe circles are tangent.

    n=3 0.268, n=4 0.414, n=5 0.510, n=6 0.577, n=8 0.668, n=12 0.767.
    These are the deepest cusps an n-foil admits, and the measured historical
    proportions sit right on them."""
    return math.cos(math.pi / n) / (1.0 + math.sin(math.pi / n))


def _cusp_radius(n, r_out, d):
    """Union radius along the bisector between two adjacent lobe circles."""
    rho = r_out - d
    s = d * math.sin(math.pi / n)
    k = rho * rho - s * s
    if k < 0.0:
        return None                      # circles no longer reach the bisector
    return d * math.cos(math.pi / n) + math.sqrt(k)


def solve_lobes(n, r_out, r_in):
    """Lobe-circle geometry (d, rho) for an n-foil.

    d is the lobe centre radius, rho the lobe radius, with d + rho = r_out and
    the union's bisector radius equal to r_in. Monotone in d, so bisect."""
    lo, hi = 1e-6, r_out / (1.0 + math.sin(math.pi / n))
    if r_in >= r_out:
        return 0.0, r_out
    if r_in < r_out * tangent_ratio(n) - 1e-9:
        raise ValueError("n=%d cannot cusp below %.3f*r_out" % (n, tangent_ratio(n)))
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        c = _cusp_radius(n, r_out, mid)
        if c is None or c < r_in:
            hi = mid
        else:
            lo = mid
    d = 0.5 * (lo + hi)
    return d, r_out - d


def _petal_circles(th, r_out, r_in, halfw):
    """The two circles whose INTERSECTION is a vesica petal on axis `th`.

    A petal is pointed at both ends, which is the whole reason it exists here:
    a lobe built from one circle bulges, and n of them read as a clover no
    matter how deep the cusps between them are. A vesica comes to an ogee point
    at the apex, which is what turns a quatrefoil into a begonia panel."""
    a = 0.5 * (r_out + r_in)
    h = 0.5 * (r_out - r_in)
    c = (h * h - halfw * halfw) / (2.0 * halfw)
    rho = c + halfw
    t = math.radians(th)
    out = []
    for sgn in (1.0, -1.0):
        cx = a * math.cos(t) - sgn * c * math.sin(t)
        cy = a * math.sin(t) + sgn * c * math.cos(t)
        out.append((cx, cy, rho))
    return out


def foil(circles=(), hub_r=0.0, petals=(), samples=2000):
    """Outline of a union of lobe circles, vesica petals and a central hub.

    Circles are (d, theta_deg, rho) in polar form; petals are
    (theta_deg, r_out, r_in, halfwidth). Every arrangement used here is
    star-shaped about the origin, so the boundary is just the outermost ray
    hit - which keeps cusps mathematically exact instead of rounding them off
    against a marching grid.

    Petals must satisfy r_in < hub_r so their inner point is swallowed by the
    hub; otherwise a petal floats free and the max-of-rays boundary silently
    jumps across the gap."""
    cs = [(d, math.radians(t), rho) for d, t, rho in circles]
    ps = [_petal_circles(*p) for p in petals]
    pts = []
    for i in range(samples):
        a = 2.0 * math.pi * i / samples
        u, v = math.cos(a), math.sin(a)
        r = hub_r
        for d, th, rho in cs:
            perp = d * math.sin(a - th)
            k = rho * rho - perp * perp
            if k > 0.0:
                hit = d * math.cos(a - th) + math.sqrt(k)
                if hit > r:
                    r = hit
        for pair in ps:
            near, far = -1e9, 1e9
            for cx, cy, rho in pair:
                B = u * cx + v * cy
                D = B * B - (cx * cx + cy * cy - rho * rho)
                if D < 0.0:
                    far = -1e9
                    break
                s = math.sqrt(D)
                near = max(near, B - s)
                far = min(far, B + s)
            if far > near and far > r:
                r = far
        pts.append((r * u, r * v))
    return S.ccw(pts)


def cusped(n, r_out=R_OUT, depth=0.92, rot=90.0, samples=2000):
    """A plain n-foil. depth=1 puts adjacent lobe circles exactly tangent.

    depth is deliberately not allowed to reach 1.0 in the shapes below: a
    tangent cusp has zero notch angle, which is an unprintable crack rather
    than an ornament. 0.85-0.95 keeps the cusp visually knife-sharp while
    leaving a notch the nozzle and the material can survive."""
    k = tangent_ratio(n)
    r_in = r_out * (1.0 - depth * (1.0 - k))
    d, rho = solve_lobes(n, r_out, r_in)
    return foil([(d, 360.0 * i / n + rot, rho) for i in range(n)], samples=samples)


# ======================================================================
# implicit-field machinery, for the forms that are not star-shaped
# ======================================================================
def f_circle(X, Y, cx, cy, r):
    return np.hypot(X - cx, Y - cy) - r


def f_poly(X, Y, poly):
    """Exact signed distance to a polygon: negative inside."""
    n = len(poly)
    d = np.full(X.shape, 1e9)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy
        t = np.clip(((X - ax) * vx + (Y - ay) * vy) / (L2 if L2 > 1e-12 else 1.0), 0.0, 1.0)
        d = np.minimum(d, np.hypot(X - (ax + t * vx), Y - (ay + t * vy)))
    inside = np.zeros(X.shape, bool)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        if ay == by:
            continue
        cond = (ay > Y) != (by > Y)
        xin = ax + (Y - ay) * (bx - ax) / (by - ay)
        inside ^= cond & (X < xin)
    return np.where(inside, -d, d)


def f_union(*fs):
    out = fs[0]
    for f in fs[1:]:
        out = np.minimum(out, f)
    return out


def f_sub(a, b):
    return np.maximum(a, -b)


def f_and(*fs):
    out = fs[0]
    for f in fs[1:]:
        out = np.maximum(out, f)
    return out


def f_smooth_union(a, b, k):
    """Polynomial smooth-min: rounds the junction by roughly k mm."""
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


# --- marching squares -------------------------------------------------
def _ms_table():
    """case -> list of (from_edge, to_edge), oriented interior-on-the-left.

    Derived rather than typed: walking a cell's corners CCW, the contour leaves
    the cell border where a corner is inside and the next is outside, and
    rejoins where the reverse happens. Hand-written tables are where marching
    squares goes wrong."""
    tab = {}
    for b in range(16):
        ins = [(b >> k) & 1 for k in range(4)]
        fr = [k for k in range(4) if ins[k] and not ins[(k + 1) % 4]]
        to = [k for k in range(4) if not ins[k] and ins[(k + 1) % 4]]
        tab[b] = (fr, to)
    return tab


_MS = _ms_table()


def contours(f, xs, ys, step):
    """Closed contours of f == 0 on a grid. Outer loops CCW, holes CW.

    f is indexed [j, i] against ys[j], xs[i]. Only cells that actually straddle
    the level set are visited, so cost is O(perimeter), not O(area)."""
    sgn = f < 0.0
    b = (sgn[:-1, :-1].astype(np.uint8)
         | (sgn[:-1, 1:].astype(np.uint8) << 1)
         | (sgn[1:, 1:].astype(np.uint8) << 2)
         | (sgn[1:, :-1].astype(np.uint8) << 3))
    jj, ii = np.nonzero((b != 0) & (b != 15))

    def hkey(i, j):
        return ("h", i, j)

    def vkey(i, j):
        return ("v", i, j)

    def edge_key(i, j, e):
        return (hkey(i, j), vkey(i + 1, j), hkey(i, j + 1), vkey(i, j))[e]

    nxt = {}
    for j, i in zip(jj.tolist(), ii.tolist()):
        code = int(b[j, i])
        fr, to = _MS[code]
        if len(fr) == 1:
            pairs = [(fr[0], to[0])]
        else:
            # Saddle. The cell centre decides whether the two inside corners are
            # joined through the middle or pinched apart, and that choice is the
            # same rule for both saddle cases: joined -> each exit turns to the
            # NEXT edge CCW, pinched -> to the previous one. Hardcoding edge
            # numbers here instead is the classic marching-squares bug, because
            # case 10's exits sit on the edges case 5 uses as entries.
            centre = 0.25 * (f[j, i] + f[j, i + 1] + f[j + 1, i + 1] + f[j + 1, i])
            d = 1 if centre < 0.0 else -1
            pairs = [(k, (k + d) % 4) for k in fr]
        for a, c in pairs:
            nxt[edge_key(i, j, a)] = edge_key(i, j, c)

    def point(key):
        kind, i, j = key
        if kind == "h":
            v0, v1 = f[j, i], f[j, i + 1]
            t = v0 / (v0 - v1) if v0 != v1 else 0.5
            return (xs[i] + t * step, ys[j])
        v0, v1 = f[j, i], f[j + 1, i]
        t = v0 / (v0 - v1) if v0 != v1 else 0.5
        return (xs[i], ys[j] + t * step)

    loops, seen = [], set()
    for start in list(nxt.keys()):
        if start in seen:
            continue
        loop, k = [], start
        while k in nxt and k not in seen:
            seen.add(k)
            loop.append(point(k))
            k = nxt[k]
        if len(loop) >= 8:
            loops.append(loop)
    return loops


def from_field(fn, half=19.0, step=0.035):
    """Trace a CSG field into (outer, [voids]).

    step 0.035mm is deliberately far finer than the 0.4mm nozzle: it keeps the
    grid's rounding of a cusp an order of magnitude below anything the printer
    or the eye can resolve, so the cusp depth survives the raster."""
    n = int(2 * half / step) + 1
    xs = np.linspace(-half, half, n)
    ys = np.linspace(-half, half, n)
    X, Y = np.meshgrid(xs, ys)
    f = fn(X, Y)
    loops = contours(f, xs, ys, xs[1] - xs[0])
    if not loops:
        raise ValueError("field produced no contour")
    scored = [(0.5 * sum(p[0] * q[1] - q[0] * p[1]
                         for p, q in zip(L, L[1:] + L[:1])), L) for L in loops]
    scored.sort(key=lambda s: -abs(s[0]))
    outer = S.ccw(simplify(scored[0][1], 0.02))
    voids = [S.ccw(simplify(L, 0.02)) for a, L in scored[1:] if abs(a) > 0.5]
    return outer, voids


# ======================================================================
# the motifs
# ======================================================================
def ruyi():
    """如意頭 / 雲頭 - the ruyi cloud head, the family's keystone.

    Its whole identity is perimeter, so it is the most translatable Chinese
    ornament there is for a glowing outline. Getting it right took reading the
    cloud-collar plates twice. The first version built the head as two lobes
    with a dip on the centre line and every variant of it rendered as a HEART -
    because that structure IS a heart. The plates show the opposite: the cloud
    head is a TREFOIL whose centre projects OUTWARD, a broad central lobe
    flanked by two scrolls that curl back on themselves, with a small point
    opposite. The curl is the part that stops it reading as three balloons, and
    in silhouette a scroll reads only as an undercut - hence the subtracted
    discs biting the top-outer flank of each side lobe.

    Hung from the crown of the central lobe, so the cord sits where a lappet
    joins its collar."""
    def fn(X, Y):
        head = f_union(f_circle(X, Y, 0.0, 0.0, 8.8),
                       f_circle(X, Y, -9.8, -3.2, 5.6),
                       f_circle(X, Y, 9.8, -3.2, 5.6))
        curl = f_union(f_circle(X, Y, -11.3, 4.6, 5.1),
                       f_circle(X, Y, 11.3, 4.6, 5.1))
        pt = f_union(f_poly(X, Y, [(-7.2, -1.0), (7.2, -1.0),
                                   (2.1, -10.8), (-2.1, -10.8)]),
                     f_circle(X, Y, 0.0, -9.1, 2.1))
        return f_union(f_sub(head, curl), pt)
    pts, voids = from_field(fn)
    return Motif(pts, voids, "cloud head: centre lobe, two curled scrolls, point")


def cloud_collar():
    """雲肩 - the four-lappet cloud collar, compressed into one medallion.

    Second reading of the plates changed this one too. The 4-fold structure
    does NOT come from deep valleys between fat lappets - that construction
    renders as an eight-lobed flower, because a lappet's two shoulders read as
    two equal lobes. It comes from four POINTS at the compass directions
    standing proud of a band of scroll lobes. So: four vesica tips reaching the
    full radius, eight scroll circles filling the band between them, and a hub
    that carries the middle."""
    scrolls = [(8.8, a, 3.6) for a in (30, 60, 120, 150, 210, 240, 300, 330)]
    tips = [(90.0 + 90.0 * k, R_OUT, 4.0, 3.4) for k in range(4)]
    return Motif(foil(scrolls, hub_r=6.4, petals=tips), [],
                 "4 pointed lappets over a scrolled band")


def octofoil():
    """葵花鏡 - the mallow-flower mirror, whose lobes are ROUND.

    Paired deliberately with `lianhua`: Tang foliate mirrors come in a
    round-lobed mallow (葵花) form and a pointed caltrop (菱花) form, and the
    difference between a circular lobe and an ogee point is the whole reason
    both exist. This is the round one, near-tangent so the scallops stay
    crisp."""
    return Motif(cusped(8, R_OUT, depth=0.97, rot=90.0), [],
                 "8 round lobes, cusp at 0.68 r")


def plum():
    """梅花 - the five-petal plum blossom, after the plum-blossom cash coins.

    Five is the count that reads as a flower rather than as a gear, and the
    n=5 tangent limit (0.510) separates the petals cleanly instead of merging
    them into a fat pentagon."""
    return Motif(cusped(5, R_OUT, depth=0.97, rot=90.0), [],
                 "5 round petals, cusp at 0.52 r")


def haitang():
    """海棠 - the begonia panel: the four-lobed window, door and mirror frame.

    Built from vesica petals, not circles, and that is not a detail. A
    four-foil of circular lobes is a four-leaf clover however deep its cusps
    are cut - it was the clearest failure in the first render. Giving each
    petal an ogee point at the apex turns the same four-fold form into
    architecture."""
    return Motif(foil(hub_r=7.8,
                      petals=[(90.0 + 90.0 * k, R_OUT, 3.0, 5.0) for k in range(4)]),
                 [], "4 pointed petals, cusp at 0.52 r")


def lianhua():
    """蓮花 / 寶相花 - the eight-petal lotus medallion.

    The Tang lotus roundel, and the strongest reading in the whole set: eight
    ogee points on a full body, which is dense enough to survive as a lit mass
    yet articulated enough that the eye counts the petals."""
    return Motif(foil(hub_r=10.0,
                      petals=[(90.0 + 45.0 * k, R_OUT, 3.5, 3.3) for k in range(8)]),
                 [], "8 pointed petals on a full body")


def hulu():
    """葫蘆 - the bottle gourd.

    A pure-outline motif needing no voids and no cusps at all, and the best
    engineering fit in the set: `place_pocket` does not require a centred
    pocket, so the tag lives in the big lower lobe and the cord in the small
    upper one - which is how a real hulu charm hangs. Lobe ratio 9.6/5.4 =
    1.78, matching charm gourds rather than a snowman."""
    def fn(X, Y):
        return f_smooth_union(f_circle(X, Y, 0.0, -4.6, 9.6),
                              f_circle(X, Y, 0.0, 8.4, 5.4), 2.4)
    pts, voids = from_field(fn)
    return Motif(pts, voids, "double gourd, offset pocket in the lower lobe")


def changming():
    """長命鎖 - the child's longevity lock, the archetypal Chinese pendant.

    A broad plaque with chamfered top corners, a ruyi-cusped skirt below and a
    raised centre tab for the cord. The first version put round volutes on the
    top corners and the whole thing read as an animal's head, ears and all;
    the chamfers do the same job without the mammal."""
    def fn(X, Y):
        body = f_poly(X, Y, [(-12.8, 6.0), (-10.0, 8.8), (10.0, 8.8),
                             (12.8, 6.0), (12.8, -2.4), (-12.8, -2.4)])
        skirt = f_union(f_circle(X, Y, -7.9, -2.4, 5.7),
                        f_circle(X, Y, 7.9, -2.4, 5.7),
                        f_circle(X, Y, 0.0, -4.8, 6.7))
        tab = f_union(f_poly(X, Y, [(-4.4, 6.0), (4.4, 6.0),
                                    (3.4, 12.6), (-3.4, 12.6)]),
                      f_circle(X, Y, 0.0, 12.6, 3.4))
        return f_union(body, skirt, tab)
    pts, voids = from_field(fn)
    return Motif(pts, voids, "lock plaque, ruyi skirt, cord tab")


def fangsheng():
    """方勝 - twin interlocked lozenges, one of the Eight Treasures.

    Pure silhouette with genuinely re-entrant geometry: the two notches where
    the lozenges cross ARE the motif, and they survive at any size. Stacked
    vertically rather than the usual side-by-side, because that puts a lozenge
    APEX on the centre line where `place_hole` wants the cord; side-by-side
    puts a notch there and the crown falls under 2.5mm."""
    a, b, off = 12.0, 10.5, 4.5

    def loz(cy):
        return [(a, cy), (0.0, cy + b), (-a, cy), (0.0, cy - b)]

    def fn(X, Y):
        return f_union(f_poly(X, Y, loz(-off)), f_poly(X, Y, loz(off)))
    pts, voids = from_field(fn)
    return Motif(pts, voids, "two lozenges crossed, notches on the waist")


def yuanbao():
    """元寶 - the sycee, the boat-shaped silver ingot. Kept as evidence.

    Passes every engineering gate and renders as a BUCKET. Four rounds of
    bigger horns and deeper dishes did not shift it, because the sycee is
    recognised by its three-dimensional boat form - an oval collar standing on
    a rounded body - and its front elevation really is a trapezoid with two
    knobs. Nothing about the silhouette was fixable; the information is not in
    the silhouette."""
    def fn(X, Y):
        body = f_poly(X, Y, [(-8.4, -11.0), (8.4, -11.0), (13.0, 4.6), (-13.0, 4.6)])
        body = f_smooth_union(body, f_circle(X, Y, 0.0, -7.0, 6.6), 2.0)
        horns = f_union(f_circle(X, Y, -12.0, 4.6, 3.0),
                        f_circle(X, Y, 12.0, 4.6, 3.0))
        dish = f_circle(X, Y, 0.0, 12.0, 8.6)
        return f_union(f_sub(body, dish), horns)
    pts, voids = from_field(fn)
    return Motif(pts, voids, "ingot: dished top between two horns")


def yaxing():
    """亞形 - the stepped cruciform of Shang bronzes and the TLV mirror.

    The one rectilinear member, and the honest survivor of the lattice family:
    an ice-ray or key-fret window is a FIELD of voids and cannot be a 30mm
    silhouette (see REJECTED), but the ya-form is a stepped OUTLINE needing no
    voids at all. Every step is 3.4mm or more and every corner is 90 degrees,
    so it has neither barbs nor cusps to print."""
    o, m, i = 13.2, 8.4, 4.6          # outer reach, step shoulder, arm half-width
    # One quadrant of boundary, from the +x arm's upper corner CCW into the
    # corner staircase and out along the +y arm. Rotating it four times closes
    # the figure, and consecutive copies join across each arm's flat end.
    q = [(o, i), (m, i), (m, m), (i, m), (i, o)]
    pts = []
    for k in range(4):
        c, s = math.cos(math.pi / 2 * k), math.sin(math.pi / 2 * k)
        pts += [(x * c - y * s, x * s + y * c) for x, y in q]
    return Motif(S.ccw(_dedup(pts)), [], "stepped cruciform, all right angles")


def _dedup(pts):
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    if len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-6:
        out.pop()
    return out


# ------------------------------------------------------------- the rejects
# Implemented, audited and rendered rather than dismissed from memory, because
# "this motif will not read" is a claim that has to be tested. Each one is kept
# so the reasoning is reproducible; none of them ships. See REJECTED below.
def bi():
    """璧 - the ritual disc, with the central hole displaced into a boss ring.

    The true bi cannot be built at this size (see REJECTED). This is the best
    substitute the plates offer: the 蒲紋 boss field, the regular array of small
    circles real bi carry across their faces, cut as voids. Ring at r 8.3, so
    it clears the pocket wall outside and the peg band inside."""
    ring = []
    for k in range(12):
        a = 2 * math.pi * k / 12 + math.pi / 12
        cx, cy = 8.3 * math.cos(a), 8.3 * math.sin(a)
        ring.append([(cx + 1.05 * math.cos(t), cy + 1.05 * math.sin(t))
                     for t in [2 * math.pi * i / 40 for i in range(40)]])
    disc = [(R_OUT * math.cos(2 * math.pi * i / 400),
             R_OUT * math.sin(2 * math.pi * i / 400)) for i in range(400)]
    return Motif(S.ccw(disc), [S.ccw(r) for r in ring], "disc + 12 boss voids")


def cash():
    """方孔錢 - the cash coin, with the square hole turned inside out.

    The square cannot be a hole here, so it becomes a square FRAME of four slot
    voids inside a round rim: round heaven and square earth, drawn rather than
    pierced."""
    # The frame has to live INSIDE the peg ring. Pegs land wherever the outline
    # allows 2.2mm of clearance, i.e. on a circle of radius ~12.8 here, and they
    # spread to maximise their triangle, so a frame whose corners reach past
    # ~10.5 gets fouled at some angle. The cord bore at y=11.8 rules out the top
    # slot rising above ~10.4 as well. Both push the square in to half-size 7.5
    # - which is the whole problem with this motif, see REJECTED.
    h, w, L = 7.5, 0.9, 5.4           # frame half-size, slot half-width, half-length
    slots = []
    for cx, cy, hx, hy in ((0, h, L, w), (0, -h, L, w), (h, 0, w, L), (-h, 0, w, L)):
        slots.append([(cx - hx, cy - hy), (cx + hx, cy - hy),
                      (cx + hx, cy + hy), (cx - hx, cy + hy)])
    disc = [(R_OUT * math.cos(2 * math.pi * i / 400),
             R_OUT * math.sin(2 * math.pi * i / 400)) for i in range(400)]
    return Motif(S.ccw(disc), [S.ccw(s) for s in slots], "disc + square slot frame")


def panchang():
    """盤長 - the endless knot, reduced to its ring of loops.

    The real knot's identity is the woven grid in the middle, which is exactly
    where the tag goes. What could survive outside that zone is the ring of
    loop ears - so, a six-foil body with a void inside each lobe."""
    body = cusped(6, R_OUT, depth=0.97, rot=90.0)
    voids = []
    for k in range(6):
        a = math.radians(90.0 + 60.0 * k)
        cx, cy = 8.6 * math.cos(a), 8.6 * math.sin(a)
        voids.append([(cx + 1.6 * math.cos(t), cy + 1.6 * math.sin(t))
                      for t in [2 * math.pi * i / 48 for i in range(48)]])
    return Motif(body, [S.ccw(v) for v in voids], "6-foil with a void per lobe")


def taiji():
    """太極 - one half of the taijitu, the yang fish, eye included.

    A whole taijitu is a circle in silhouette and dead on arrival. One fish is
    not obviously dead: the comma body with its counter-coloured eye is the
    only part of the symbol carrying any outline, and it would have been the
    set's one deliberately asymmetric member."""
    R = 14.6

    def fn(X, Y):
        right = f_and(f_circle(X, Y, 0, 0, R), -X)
        body = f_union(right, f_circle(X, Y, 0.0, R / 2, R / 2))
        body = f_sub(body, f_circle(X, Y, 0.0, -R / 2, R / 2))
        return f_sub(body, f_circle(X, Y, 0.0, R / 2, R / 5.6))
    pts, voids = from_field(fn)
    return Motif(pts, voids, "yang fish with eye void")


def lingzhi():
    """靈芝 - the fungus of immortality, the form the ruyi head derives from.

    Kept only as evidence. A wide low cap with a waved rim over a stem is what
    the motif is, and what it renders as is broccoli."""
    def fn(X, Y):
        cap = f_union(f_circle(X, Y, 0.0, 3.2, 8.4),
                      f_circle(X, Y, -7.6, 2.0, 6.4),
                      f_circle(X, Y, 7.6, 2.0, 6.4))
        bite = f_union(f_circle(X, Y, -11.6, -5.4, 3.4),
                       f_circle(X, Y, 0.0, -7.2, 3.4),
                       f_circle(X, Y, 11.6, -5.4, 3.4))
        stem = f_poly(X, Y, [(-3.6, -2.0), (3.6, -2.0), (4.6, -13.6), (-4.6, -13.6)])
        return f_union(f_sub(cap, bite), stem)
    pts, voids = from_field(fn)
    return Motif(pts, voids, "wide low cap with rim waves, over a stem")


# The shipping family.
SHAPES = {
    "ruyi": ruyi,
    "cloud_collar": cloud_collar,
    "lianhua": lianhua,
    "haitang": haitang,
    "octofoil": octofoil,
    "plum": plum,
    "hulu": hulu,
    "changming": changming,
    "fangsheng": fangsheng,
    "yaxing": yaxing,
}

# Built and rendered, then cut. Reasons in REJECTED.
TESTED = {
    "yuanbao": yuanbao,
    "bi": bi,
    "cash": cash,
    "panchang": panchang,
    "taiji": taiji,
    "lingzhi": lingzhi,
}

ALL = dict(SHAPES, **TESTED)

REJECTED = {
    "yuanbao": "Renders as a bucket with two handles, through four rounds of "
               "bigger horns and deeper dishes. A sycee is recognised by its "
               "three-dimensional boat shape - an oval collar on a rounded body - "
               "and its front elevation is honestly just a trapezoid with two "
               "knobs on top. Passes every engineering gate; fails the only test "
               "that matters here.",
    "bi": "Reads as a polka-dot circle. The true bi's hole is 0.20-0.30 of its "
          "diameter (measured across 36 Commons plates), i.e. r_in 3.0-4.5mm "
          "here. An annulus hosts a 10.5mm pocket only if it is >= 11.7mm wide, "
          "so r_in <= 3.3mm - and at r_in 3.3 the pocket fills the ring edge to "
          "edge with nothing left for three pegs. The bi needs ~44mm, not 30mm. "
          "The boss-ring substitute is buildable but is not a bi.",
    "cash": "The square must be an OUTLINE rather than a hole, which inverts the "
            "figure-ground that makes a cash coin recognisable, and it has to be "
            "15mm across to clear the pocket inside and the peg ring outside - "
            "twice the 7.5mm a real coin's hole would be at this diameter. It "
            "renders as a disc with a dashed square printed on it.",
    "panchang": "The knot IS its woven centre, and the centre is the tag pocket. "
                "Pushed outward, the loops collide with the peg ring and the cord "
                "bore; pushed inward to clear them they sit well inside the lobes "
                "and the result renders as a flower with six holes. The outer "
                "annulus of a 30mm bead is already fully spoken for.",
    "taiji": "Three hard failures, not a matter of taste: the fish's tail is a "
             "6.6 degree convex cusp (a spike, by construction - the tail is "
             "where two circles meet tangentially), the peg triangle collapses to "
             "27mm2 against a 40mm2 floor, and the eye void overlaps the only "
             "pocket the solver can find. Half a taijitu also reads as a comma.",
    "lingzhi": "Renders as broccoli. The cap-over-stem proportion that makes a "
               "lingzhi legible in a drawing is carried by its concentric growth "
               "zones, which are surface detail and vanish in silhouette. Its "
               "perimeter contribution is already covered, better, by `ruyi` - "
               "which is the same form stylised.",
    "shou / double happiness (壽, 囍)": "Never implemented, and the plates say "
        "why: both are dense fields of near-parallel strokes. As a filled "
        "silhouette a character roundel is a disc; as strokes-with-voids it needs "
        "15-40 separate voids on a 30mm blank, putting every bar and gap far "
        "under the 1.6mm feature floor, quite apart from every one of them "
        "crossing the pocket.",
    "lattice / ice-ray (窗棂)": "Same arithmetic. A lattice is a FIELD of voids, "
        "and on a 30mm bead the pocket plus its wall claims everything inside "
        "r=5.9 while the peg ring claims r=12.8, leaving a ~4mm annulus. Two bars "
        "deep is not a lattice. `yaxing` is the part of this family that "
        "survives, because it is a stepped outline rather than a grid.",
    "bagua (八卦)": "Eight trigrams of three bars each is 24-40 voids around a "
        "ring; at r=12.5 each trigram gets a 9.8mm arc, so bars land near 1mm. "
        "Under the floor by a factor of 1.6, and the octagon they sit on is a "
        "featureless silhouette on its own.",
}


# ======================================================================
# gates
# ======================================================================
def _mask(pts, X, Y):
    inside = np.zeros(X.shape, bool)
    n = len(pts)
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        if ay == by:
            continue
        cond = (ay > Y) != (by > Y)
        xin = ax + (Y - ay) * (bx - ax) / (by - ay)
        inside ^= cond & (X < xin)
    return inside


def _disc(rpx):
    return [(dy, dx) for dy in range(-rpx, rpx + 1) for dx in range(-rpx, rpx + 1)
            if dx * dx + dy * dy <= rpx * rpx]


def _shift(m, dy, dx, fill):
    out = np.full(m.shape, fill, bool)
    ys = slice(max(0, dy), m.shape[0] + min(0, dy))
    yd = slice(max(0, -dy), m.shape[0] + min(0, -dy))
    xs = slice(max(0, dx), m.shape[1] + min(0, dx))
    xd = slice(max(0, -dx), m.shape[1] + min(0, -dx))
    out[yd, xd] = m[ys, xs]
    return out


def _shiftf(a, dy, dx, fill):
    out = np.full(a.shape, fill, a.dtype)
    ys = slice(max(0, dy), a.shape[0] + min(0, dy))
    yd = slice(max(0, -dy), a.shape[0] + min(0, -dy))
    xs = slice(max(0, dx), a.shape[1] + min(0, dx))
    xd = slice(max(0, -dx), a.shape[1] + min(0, -dx))
    out[yd, xd] = a[ys, xs]
    return out


def _erode(m, offs):
    out = m.copy()
    for dy, dx in offs:
        out &= _shift(m, dy, dx, False)
    return out


def _dilate(m, offs):
    out = m.copy()
    for dy, dx in offs:
        out |= _shift(m, dy, dx, False)
    return out


def _grow1(m):
    return (m | _shift(m, 1, 0, False) | _shift(m, -1, 0, False)
            | _shift(m, 0, 1, False) | _shift(m, 0, -1, False))


def _components(m):
    """Number of 4-connected components. Only ever a handful, so flood by
    dilation rather than dragging in a labelling dependency."""
    rem, n = m.copy(), 0
    while rem.any():
        n += 1
        seed = np.zeros_like(rem)
        seed.flat[int(np.argmax(rem))] = True
        prev = -1
        while seed.sum() != prev:
            prev = int(seed.sum())
            seed = _grow1(seed) & rem
        rem &= ~seed
        if n > 8:
            break
    return n


def morph_report(pts, voids, step=0.12):
    """Printability measured the way the nozzle meets the part.

    An edge-length gate is meaningless for sampled curves - every edge of a
    2000-gon is 0.05mm - so this rasterises and asks morphological questions.

    The first version of this gate measured the AREA of material thinner than
    1.6mm and failed `yaxing`, a figure made entirely of right angles and
    3.4mm steps that any printer will produce perfectly. That was the gate
    being wrong, not the shape: opening a polygon with a disc always eats the
    neighbourhood of every convex corner, so "thin area" really measures
    "how many corners", which is not a defect. What actually breaks a print is

      pieces  - opening severs the shape, i.e. some lobe hangs on a neck
                thinner than MIN_FEATURE and will snap off;
      spur    - material reaching far beyond the region a MIN_FEATURE-wide
                bead can fill, i.e. a genuine spike rather than a corner tip
                (a 90 degree corner scores 0.33mm, a 60 degree one 0.46mm);
      gap     - air narrower than MIN_GAP, which the nozzle cannot enter.

    All three are defects. Corner count is not."""
    xs_ = [p[0] for p in pts]
    ys_ = [p[1] for p in pts]
    pad = 2.0
    xa = np.arange(min(xs_) - pad, max(xs_) + pad, step)
    ya = np.arange(min(ys_) - pad, max(ys_) + pad, step)
    X, Y = np.meshgrid(xa, ya)
    m = _mask(pts, X, Y)
    for v in voids:
        m &= ~_mask(v, X, Y)
    px = step * step
    dm = _disc(max(1, int(round((MIN_FEATURE / 2.0) / step))))
    dg = _disc(max(1, int(round((MIN_GAP / 2.0) / step))))
    opened = _dilate(_erode(m, dm), dm)
    closed = _erode(_dilate(m, dg), dg)

    def reach(region, core):
        cur = core.copy()
        for k in range(1, 41):
            if not (region & ~cur).any():
                return (k - 1) * step
            cur = _grow1(cur) & region
        return 99.0

    # `gap` is the mirror of `spur`, and for the same reason: the first version
    # measured the AREA of sub-MIN_GAP air and failed `cash`, whose slots are
    # 2.0mm wide, purely because sixteen right-angled slot corners each leave a
    # crumb of narrow air. A corner is not a defect on either side of the
    # boundary. How FAR the air runs past what a MIN_GAP path can fill is.
    air = ~m
    return {"spur": reach(m, opened),
            "pieces": _components(opened),
            "gap": reach(air, air & ~(closed & ~m)),
            "area": float(np.count_nonzero(m) * px)}


def fillet(pts, r=0.20, step=0.04):
    """Round every re-entrant corner by r, leaving convex ones alone.

    A near-tangent foil cusp is geometrically a crack: the notch narrows to
    nothing, the nozzle cannot enter the last millimetre of it, and in a
    printed part a zero-radius internal corner is where the crack starts. A
    morphological closing puts a small root radius in exactly the places that
    need one - and only there, because closing cannot move a convex boundary.
    At 0.3mm the root is invisible on a 30mm charm but the cusp keeps its full
    depth, so this buys printability without paying for it in reading."""
    src = simplify(pts, 0.03)
    xs_ = [p[0] for p in src]
    ys_ = [p[1] for p in src]
    pad = 2.0
    xa = np.arange(min(xs_) - pad, max(xs_) + pad, step)
    ya = np.arange(min(ys_) - pad, max(ys_) + pad, step)
    X, Y = np.meshgrid(xa, ya)
    # Grey-scale morphology on the signed distance field, not on a binary mask:
    # thresholding first and re-contouring afterwards would hand back a 0.05mm
    # staircase instead of a smooth curve.
    f = f_poly(X, Y, src)
    d = _disc(max(1, int(round(r / step))))
    dil = f.copy()
    for dy, dx in d:
        dil = np.minimum(dil, _shiftf(f, dy, dx, np.inf))
    ero = dil.copy()
    for dy, dx in d:
        ero = np.maximum(ero, _shiftf(dil, dy, dx, -np.inf))
    loops = contours(ero, xa, ya, xa[1] - xa[0])
    loops.sort(key=lambda L: -abs(sum(p[0] * q[1] - q[0] * p[1]
                                      for p, q in zip(L, L[1:] + L[:1]))))
    return S.ccw(simplify(loops[0], 0.015))


def _poly_dist(poly, x, y):
    """Unsigned distance from a point to a polygon's boundary."""
    n = len(poly)
    return min(S._seg_d(x, y, poly[i][0], poly[i][1],
                        poly[(i + 1) % n][0], poly[(i + 1) % n][1])
               for i in range(n))


def _poly_gap(a, b):
    return min(min(_poly_dist(b, x, y) for x, y in a),
               min(_poly_dist(a, x, y) for x, y in b))


def void_report(pts, voids, fit):
    """Do the interior voids respect the hardware?

    Not folded into `fit_report`: that solver models one simple outline, and
    stitching voids in through keyhole bridges would put phantom zero-width
    walls into its distance field and move the pocket. So the outline is gated
    there, unchanged, and the voids are gated here against everything the
    solver placed."""
    issues = []
    px, py, _ = fit["pocket"]
    for k, v in enumerate(voids):
        if min(S.clearance(pts, x, y) for x, y in v) < 1.2:
            issues.append("void%d within 1.2mm of the rim" % k)
        # True polygon distance, not a bounding circle. The first version used
        # a bounding radius and reported cash's slot frame as breaching a
        # pocket it clears by 4mm - an 8mm slot's bounding circle swallows the
        # whole coin.
        if _poly_dist(v, px, py) < S.POCKET_R + 1.0 or S.contains(v, px, py):
            issues.append("void%d breaches the NFC pocket" % k)
        for (gx, gy) in (fit["pegs"] or []):
            if _poly_dist(v, gx, gy) < S.PEG_R + 0.9 or S.contains(v, gx, gy):
                issues.append("void%d fouls a peg" % k)
                break
        # the cord bore is a tube along X through the whole body, so any void
        # sharing its y band intersects it wherever it sits in x.
        if fit["hole"] and min(abs(y - fit["hole"][0]) for _, y in v) < S.HOLE_R + 0.6:
            issues.append("void%d fouls the cord bore" % k)
        for j in range(k + 1, len(voids)):
            if _poly_gap(v, voids[j]) < 1.2:
                issues.append("void%d/%d walls too thin" % (k, j))
    return sorted(set(issues))


MAX_SPUR = 1.2        # mm of reach beyond a MIN_FEATURE-wide bead: a corner
                      # tip scores 0.3-0.5, a spike scores much more
MAX_GAP = 0.7         # mm of air reaching past a MIN_GAP-wide path

_CACHE = {}


def build(name):
    """The finished motif: cusps filleted, outline decimated for the solver."""
    if name in _CACHE:
        return _CACHE[name]
    m = ALL[name]()
    pts = m.pts
    _, notch = signed_angles(pts)
    if notch < 80.0:                       # has real cusps -> give them a root
        pts = fillet(pts, 0.20)
    out = Motif(pts, m.voids, m.note)
    _CACHE[name] = out
    return out


def audit_one(name):
    m = build(name)
    pts = simplify(m.pts, 0.03)
    fit = S.fit_report(pts)
    conv, notch = signed_angles(pts)
    mp = morph_report(m.pts, m.voids)
    vi = void_report(pts, m.voids, fit)
    ok = (fit["ok"] and conv >= MIN_CONVEX and notch >= MIN_NOTCH
          and mp["pieces"] == 1 and mp["spur"] <= MAX_SPUR
          and mp["gap"] <= MAX_GAP and not vi)
    return {"motif": m, "pts": pts, "fit": fit, "conv": conv, "notch": notch,
            "morph": mp, "voids": vi, "ok": ok, "n": len(pts)}


if __name__ == "__main__":
    # Several motif names are the Chinese characters themselves, and a Windows
    # console defaults to cp1252, which cannot encode them.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="include the motifs that were built, tested and cut")
    order = list(SHAPES) + (list(TESTED) if ap.parse_args().all else [])
    print("%-13s %-4s %-6s %-5s %6s %-11s %5s %5s %5s %5s %3s %5s %4s"
          % ("motif", "fit", "pocket", "pegs", "spread", "hole y/crown",
             "conv", "notch", "spur", "gap", "pcs", "wxh", "n"))
    print("-" * 108)
    bad = []
    for nm in order:
        r = audit_one(nm)
        f = r["fit"]
        hs = ("%.1f/%.1f" % f["hole"]) if f["hole"] else "-"
        print("%-13s %-4s %-6.2f %-5s %6.1f %-11s %5.1f %5.1f %5.2f %5.2f %3d %2.0fx%-2.0f %4d"
              % (nm, "ok" if r["ok"] else "FAIL", f["pocket"][2],
                 "yes" if f["pegs_ok"] else "NO", f["spread"], hs,
                 r["conv"], r["notch"], r["morph"]["spur"], r["morph"]["gap"],
                 r["morph"]["pieces"], f["w"], f["h"], r["n"]))
        if not r["ok"]:
            why = []
            if not f["pocket_ok"]:
                why.append("pocket %.2f < %.2f" % (f["pocket"][2], S.POCKET_R + S.WALL))
            if not f["pegs_ok"]:
                why.append("no peg triple")
            elif f["spread"] <= 40.0:
                why.append("pegs cramped (%.0f)" % f["spread"])
            if not f["hole_ok"]:
                why.append("no cord hole with %.1fmm crown" % S.HOLE_CROWN)
            if r["conv"] < MIN_CONVEX:
                why.append("barb %.1f deg" % r["conv"])
            if r["notch"] < MIN_NOTCH:
                why.append("cusp notch %.1f deg" % r["notch"])
            if r["morph"]["pieces"] != 1:
                why.append("%d pieces - a neck is thinner than %.1fmm"
                           % (r["morph"]["pieces"], MIN_FEATURE))
            if r["morph"]["spur"] > MAX_SPUR:
                why.append("spike reaches %.2fmm past solid material"
                           % r["morph"]["spur"])
            if r["morph"]["gap"] > MAX_GAP:
                why.append("air runs %.2fmm into a gap the nozzle cannot enter"
                           % r["morph"]["gap"])
            why += r["voids"]
            bad.append(nm)
            print("%-13s     -> %s" % ("", "; ".join(why)))
    print()
    print("pocket needs >= %.2f mm clearance; features >= %.1f mm; gaps >= %.1f mm"
          % (S.POCKET_R + S.WALL, MIN_FEATURE, MIN_GAP))
    ship = [n for n in order if n in SHAPES]
    print("shipping family: %d/%d pass every gate"
          % (len([n for n in ship if n not in bad]), len(ship)))
    if bad:
        print("failing: %s" % ", ".join(bad))
    print()
    print("REJECTED (built and rendered where a shape existed to render):")
    for k in REJECTED:
        body = " ".join(REJECTED[k].split())
        print("  %s" % k)
        while body:
            cut = body[:84] if len(body) > 84 else body
            if len(body) > 84:
                cut = cut[:cut.rfind(" ")]
            print("      %s" % cut)
            body = body[len(cut):].lstrip()
