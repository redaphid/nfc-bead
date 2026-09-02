"""Japanese mon (家紋) silhouettes for the glow bead set.

WHY MON. The bead glows as a filled shape against black, so the OUTLINE is the
whole design - no colour, no shading, no interior line work. Japanese family
crests were designed under almost exactly that constraint: a single ink shape,
legible at the size of a kimono badge, built from circles and straight edges
with a compass and rule. The good ones are already silhouettes.

WHY THESE ELEVEN, AND NOT THE OTHER 490. Most mon in the reference corpus are
multi-part line art - three separate hawk feathers, a crane drawn in outline,
paulownia leaves with veins, a ring enclosing a flower. Rendered as one filled
region those collapse into a disc or a blob. The eleven here were chosen
because their OUTER BOUNDARY is one closed shape that still reads when solid.
Rejections are recorded at the bottom of this file so the next person does not
re-litigate them - including two that were rejected only AFTER being built and
looked at, which is the only way some of them can be judged.

WHY A DISTANCE FIELD, NOT HAND-PLACED VERTICES. Mon are compass constructions:
mokko is four circles around a core, ume is five, suhama is three overlapping
mounds, matsukawa-bishi is three stacked rhombi. Building each as a union of
exact primitives and contouring the result reproduces the real construction
instead of approximating it with a vertex list, and it gives two things for
free that hand-placed vertices do not:

  * every junction is filleted to a known radius, so there are no zero-radius
    cusps that print as voids and no barbs;
  * n-fold symmetry is exact, because one petal is defined once and rotated.
    The brief's rule - draw a proportion ONCE and mirror it - is structural
    here, not a thing to remember.

PROPORTIONS ARE MEASURED, NOT REMEMBERED. Every peak/valley ratio below came
off the Wikimedia Commons reference bitmaps: threshold, take the outer
boundary of the largest ink component, and read the polar radius profile. The
measured numbers are quoted in each generator's docstring. Two of them
contradicted what the crest "looks like" at a glance - kikko has a vertex at
the top, not a flat top, and suhama's notch is at the BOTTOM - which is
exactly why they were measured.

OUTPUT is a closed list of (x, y) vertices in millimetres, wound CCW, centred
near the origin, uniformly sampled along arc length. Not SVG: recipe gotcha
#25 - Blender's SVG importer scales each curve from its path bbox rather than
the viewBox, so a family of SVGs lands at inconsistent scales.

    uv run python beads/glow-set/japanese.py            # audit table
    uv run python beads/glow-set/japanese.py --render   # glow contact sheet
"""
import math
import os
import sys

import numpy as np
from skimage import measure

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapes as S

SIZE = 30.0           # default max dimension, mm
FILLET = 0.85         # mm - radius applied at every union/cut seam. Below
                      # ~0.6mm a 0.4mm nozzle leaves a void at the seam; this
                      # is the same lesson PRINT_LOG v5b recorded for peg walls.
MIN_STROKE = 1.6      # mm - nothing thinner than this survives the print
MIN_ANGLE = 26.0      # deg - sharper than this is a barb, not a point
SAMPLE = 0.45         # mm - contour vertex spacing


# ---------------------------------------------------------------- primitives
# All fields are signed distances in mm, negative inside, vectorised over
# numpy arrays. Exact SDFs (not scaled-space approximations) matter here
# because the fillet radius of a rounded union is only correct when both
# operands report true distance.
def sd_circle(X, Y, cx, cy, r):
    return np.hypot(X - cx, Y - cy) - r


def sd_capsule(X, Y, ax, ay, bx, by, r):
    """Stadium: the set within r of segment AB. This is how an elongated mon
    petal is actually drawn - a rod with hemispherical ends."""
    pax, pay = X - ax, Y - ay
    bax, bay = bx - ax, by - ay
    den = bax * bax + bay * bay
    if den < 1e-12:
        return np.hypot(pax, pay) - r
    h = np.clip((pax * bax + pay * bay) / den, 0.0, 1.0)
    return np.hypot(pax - bax * h, pay - bay * h) - r


def sd_polygon(X, Y, verts):
    """Exact SDF of a simple polygon (Inigo Quilez's winding formulation)."""
    v = np.asarray(verts, float)
    n = len(v)
    d = np.full(X.shape, 1e18)
    s = np.ones(X.shape)
    for i in range(n):
        j = (i - 1) % n
        ex, ey = v[j][0] - v[i][0], v[j][1] - v[i][1]
        wx, wy = X - v[i][0], Y - v[i][1]
        t = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey), 0.0, 1.0)
        bx, by = wx - ex * t, wy - ey * t
        d = np.minimum(d, bx * bx + by * by)
        c1 = Y >= v[i][1]
        c2 = Y < v[j][1]
        c3 = (ex * wy - ey * wx) > 0
        flip = (c1 & c2 & c3) | ((~c1) & (~c2) & (~c3))
        s = np.where(flip, -s, s)
    return s * np.sqrt(d)


def rot(X, Y, deg):
    """Coordinates of (X,Y) in a frame rotated by `deg`, so a primitive drawn
    along +x can be stamped at any angle."""
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return X * ca + Y * sa, -X * sa + Y * ca


def round_poly(X, Y, verts, r):
    """Polygon with every corner rounded to radius r.

    Offsetting an SDF by r does NOT round anything - it just moves the level
    set and the corner stays a corner. The rounding has to be a real
    Minkowski sum: pull each vertex inward along its angle bisector far
    enough that both adjacent edges move in by r, then dilate the shrunken
    polygon by r. Vertices must be CCW for the inward normals to point in."""
    v = np.asarray(S.ccw(list(map(tuple, verts))), float)
    n = len(v)
    inner = []
    for i in range(n):
        p, c, q = v[(i - 1) % n], v[i], v[(i + 1) % n]
        e1 = c - p
        e2 = q - c
        e1 = e1 / (np.hypot(*e1) or 1.0)
        e2 = e2 / (np.hypot(*e2) or 1.0)
        n1 = np.array([-e1[1], e1[0]])      # inward normal, CCW winding
        n2 = np.array([-e2[1], e2[0]])
        bis = n1 + n2
        nb = float(np.hypot(*bis))
        if nb < 1e-9:
            inner.append(c)
            continue
        bis = bis / nb
        inner.append(c + bis * (r / max(1e-6, float(np.dot(bis, n1)))))
    return sd_polygon(X, Y, inner) - r


# --------------------------------------------------------- rounded booleans
# Sharp unions leave zero-radius interior cusps. Those are the features that
# print as voids and read as barbs on the angle gate, so every combination
# here is filleted.
def op_union(a, b, k=FILLET):
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def op_sub(a, b, k=FILLET):
    """a minus b."""
    if k <= 0:
        return np.maximum(a, -b)
    h = np.clip(0.5 - 0.5 * (a + b) / k, 0.0, 1.0)
    return a + (-b - a) * h + k * h * (1.0 - h)


def op_inter(a, b, k=FILLET):
    if k <= 0:
        return np.maximum(a, b)
    h = np.clip(0.5 - 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h + k * h * (1.0 - h)


# ------------------------------------------------------------------ tracing
def trace(sdf, half=26.0, ppm=16.0, step=SAMPLE, scale_x=1.0):
    """Contour the zero set and return uniformly-sampled CCW mm vertices.

    scale_x stretches the finished polygon rather than the field: several mon
    are wider than tall (mokko 1.30, matsukawa 1.27, ogi 1.55) and stretching
    the field would make the SDF non-metric, corrupting every fillet radius.
    Stretching the traced points keeps the zero set exact."""
    n = int(round(2 * half * ppm))
    ax = np.linspace(-half, half, n)
    X, Y = np.meshgrid(ax, ax)          # X varies along columns, Y along rows
    D = sdf(X, Y)
    loops = measure.find_contours(D, 0.0)
    if not loops:
        raise ValueError("empty shape")

    def to_mm(c):
        x = np.interp(c[:, 1], np.arange(n), ax)
        y = np.interp(c[:, 0], np.arange(n), ax)
        return np.column_stack([x, y])

    cand = [to_mm(c) for c in loops]
    # the silhouette is the loop enclosing the most area, not the longest one:
    # a fine internal ripple can out-length the true boundary
    best = max(cand, key=lambda p: abs(_area(p)))
    if scale_x != 1.0:
        best = best * np.array([scale_x, 1.0])
    return S.ccw(_resample(best, step))


def _area(p):
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def _resample(p, step):
    """Uniform arc-length sampling. Uniform spacing is what makes min_edge a
    meaningful gate on a curved shape: every edge is the same length, so a
    short edge would mean a genuine degeneracy rather than a dense arc."""
    if np.hypot(*(p[0] - p[-1])) > 1e-9:
        p = np.vstack([p, p[0]])
    seg = np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1]))
    s = np.concatenate([[0.0], np.cumsum(seg)])
    L = float(s[-1])
    m = max(48, int(round(L / step)))
    t = np.linspace(0.0, L, m, endpoint=False)
    return [(float(np.interp(u, s, p[:, 0])), float(np.interp(u, s, p[:, 1])))
            for u in t]


def fit_size(pts, size):
    """Scale so the larger of width/height is exactly `size`, and centre."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    k = size / max(max(xs) - min(xs), max(ys) - min(ys))
    return [((x - cx) * k, (y - cy) * k) for x, y in pts]


# ------------------------------------------------------------- petal makers
def disc_petal(d, r):
    """Round petal: a circle of radius r whose centre sits d from the origin.
    Ume, mokko and suhama are literally drawn this way."""
    def f(X, Y, deg):
        return sd_circle(X, Y, d * math.cos(math.radians(deg)),
                         d * math.sin(math.radians(deg)), r)
    return f


def rod_petal(r0, r1, rc):
    """Elongated petal: a radial capsule from r0 to r1, half-width rc. The
    chrysanthemum's narrow tongues."""
    def f(X, Y, deg):
        Xr, Yr = rot(X, Y, deg)
        return sd_capsule(Xr, Yr, r0, 0.0, r1, 0.0, rc)
    return f


def rosette(core_r, petal, n, phase=90.0, k=FILLET):
    """Core disc plus n identical petals. The core GUARANTEES the valley
    radius: whatever the petals do, the silhouette never dips below core_r,
    so 'how deep the notches cut' is a directly-set number rather than an
    emergent one. phase=90 puts a petal at the top, which is what gives the
    string hole its 2.5mm crown."""
    def f(X, Y):
        d = sd_circle(X, Y, 0.0, 0.0, core_r)
        for i in range(n):
            d = op_union(d, petal(X, Y, phase + 360.0 * i / n), k)
        return d
    return f


# ------------------------------------------------------------------ the mon
def mokko(size=SIZE):
    """木瓜 - "melon". Four plump lobes on the axes, narrow slit cusps at the
    diagonals, distinctly wider than tall. Oda Nobunaga's crest.

    Measured (Japanese Crest Mokkou.svg): aspect 1.295, 4 lobes, vertical
    peak 0.77 of horizontal, cusp floor 0.60-0.67 of peak.

    The first attempt put four small discs (r=0.40R at d=0.60R) around a big
    0.63R core and it rendered as a PLUS SIGN with round ends: the lobes sat
    apart on the core and the gaps between them were wide circular valleys.
    A mokko's cusps are narrow SLITS. The fix is that adjacent lobes must
    intersect each OTHER rather than both fading into a core - so the discs
    are large enough to overlap the centre (d=0.53R, r=0.47R, which puts
    their mutual crossing at 0.659R, right on the measured 0.60-0.67 floor)
    and the core is demoted to a connectivity guard. A small fillet keeps
    the slit crisp; at 0.85mm it blurs back into a valley."""
    R = size / 2 / 1.295
    f = rosette(0.30 * R, disc_petal(0.53 * R, 0.47 * R), 4, phase=90.0,
                k=0.55)
    return fit_size(trace(f, half=R * 1.6, scale_x=1.295), size)


def kikko(size=SIZE):
    """亀甲 - tortoise shell. A regular hexagon with a VERTEX at the top.

    Measured (Kikko ni Hana Hisi): aspect 0.861 against 0.866 for a regular
    hexagon with vertices top and bottom - decisive. It looks flat-topped at
    a glance and it is not; that misreading is the reason this file measures
    instead of remembering. The top vertex is also what gives the cord hole
    a clean crown."""
    R = size / 2
    verts = [(R * math.cos(math.radians(90 + 60 * i)),
              R * math.sin(math.radians(90 + 60 * i))) for i in range(6)]
    return fit_size(trace(lambda X, Y: round_poly(X, Y, verts, 1.1),
                          half=R * 1.5), size)


def kiku(size=SIZE, n=12):
    """菊 - chrysanthemum. A rosette of narrow round-tipped tongues.

    Measured (Kiku ni Ichimonnji): 16 petals, aspect 0.993, slits running
    almost to the centre (valley 0.19 of peak).

    Two constraints fight here and both were got wrong first time. At 30mm a
    16-petal crest wants 0.3mm slits, which no nozzle resolves; but thinning
    the petals to open the slits produced a SPIKED BALL - it read as a virus,
    not a flower, because a chrysanthemum's petals are broad tongues that
    touch each other and are parted by a narrow slit, not thin rods with air
    between them. Resolution: drop to 12 petals (juni-giku is itself a real
    variant) and make each tongue 0.80 of the angular pitch wide, which
    leaves a ~1.3mm slit - printable, and still reading as petals rather
    than spikes. The petals merge below r=0.68R, so the slits are finite
    cuts into a disc, which is exactly how the crest is drawn."""
    R = size / 2
    pitch = 2 * math.pi * 0.85 * R / n
    rc = 0.40 * pitch                      # tongue half-width
    f = rosette(0.60 * R, rod_petal(0.55 * R, R - rc, rc), n, phase=90.0,
                k=0.5)
    return fit_size(trace(f, half=R * 1.4), size)


def ume(size=SIZE):
    """梅 - plum blossom. Five fat circular petals, moderate notches.

    Measured (Japanese Crest Ume.svg): 5 petals, aspect 1.03, valley 0.50-0.59
    of peak. Petals are near-circles: this is the compass construction, five
    circles about a core."""
    R = size / 2
    f = rosette(0.56 * R, disc_petal(0.63 * R, 0.37 * R), 5, phase=90.0)
    return fit_size(trace(f, half=R * 1.5), size)


def kikyo(size=SIZE):
    """桔梗 - Chinese bellflower. Five petals with POINTED tips - that is the
    entire difference from ume, which has round tips, and it is enough to
    tell them apart as glowing shapes.

    Measured (Japanese crest Kikyou.svg): 5 petals, aspect 1.04, valley
    0.50-0.58.

    Narrow petals over a deep valley rendered as a plain five-pointed STAR -
    which the set already has, and which says nothing about Japan. A kikyo
    petal is broad-shouldered and only gently pointed, so the shoulders are
    widened to 0.30R and pushed out to 0.55R (just inside the core, so they
    blend rather than stand proud) and the tip angle opened to ~67 degrees.
    The difference from ume is now only the tip - pointed against round -
    which is the difference the crests themselves turn on."""
    R = size / 2

    def petal(X, Y, deg):
        # A triangular petal - however wide at the base - narrows immediately
        # and reads as a STAR POINT. A flower petal stays wide almost to the
        # end. So the petal is ume's fat disc with a point grafted onto its
        # outer end: round shoulders, pointed tip.
        Xr, Yr = rot(X, Y, deg)
        body = sd_circle(Xr, Yr, 0.58 * R, 0.0, 0.34 * R)
        tip = round_poly(Xr, Yr, [(1.00 * R, 0.0), (0.50 * R, 0.26 * R),
                                  (0.50 * R, -0.26 * R)], 0.7)
        return op_union(body, tip, 0.6)

    def f(X, Y):
        d = sd_circle(X, Y, 0.0, 0.0, 0.55 * R)
        for i in range(5):
            d = op_union(d, petal(X, Y, 90.0 + 72.0 * i), 0.6)
        return d
    return fit_size(trace(f, half=R * 1.5), size)


def suhama(size=SIZE):
    """州浜 - sandbar. Three overlapping mounds; the notch is at the BOTTOM.

    Measured (Japanese crest Suhama.svg): aspect 1.135, peaks at -150 and -30
    degrees at 0.99 (the two lower mounds are the widest points), the crown
    at +90 only 0.78, and a deep notch straight DOWN at 0.37. Reading the
    contact sheet I had this upside down - the measurement caught it."""
    R = size / 2
    r = 0.52 * R
    def f(X, Y):
        d = sd_circle(X, Y, -0.48 * R, -0.30 * R, r)
        d = op_union(d, sd_circle(X, Y, 0.48 * R, -0.30 * R, r))
        d = op_union(d, sd_circle(X, Y, 0.0, 0.30 * R, r * 1.02))
        return d
    return fit_size(trace(f, half=R * 1.6), size)


def matsukawa_bishi(size=SIZE):
    """松皮菱 - pine-bark lozenge. Three stacked rhombi fused into one.

    Measured (Japanese Crest Matukawa Hisi): aspect 1.266, sharp points left
    and right at 1.00, top and bottom vertices at 0.79, re-entrant steps at
    +/-30 degrees dropping to 0.57, and r=0.66 at 60 degrees. Those four
    steps are the whole crest - without them it is just a diamond.

    The geometry is pinned by those four numbers rather than guessed. The
    step corner sits at (0.494, 0.285); requiring it to lie on the central
    rhombus's edge fixes that rhombus at half-height 0.563, and requiring
    r(60 deg) = 0.66 fixes the capping rhombus's shoulder at (0.55, 0.45).
    Half-height 0.563 also happens to be what keeps the pocket in: a flatter
    central rhombus (0.42, my first guess) has an inscribed circle of only
    4.7mm and fails the 5.85mm gate."""
    H = size / 2                      # half-width, the long axis
    def rhomb(cy, hw, hh):
        return [(hw, cy), (0.0, cy + hh), (-hw, cy), (0.0, cy - hh)]

    def f(X, Y):
        d = round_poly(X, Y, rhomb(0.0, 1.000 * H, 0.563 * H), 0.8)
        d = op_union(d, round_poly(X, Y, rhomb(0.45 * H, 0.55 * H,
                                               0.34 * H), 0.8), 0.7)
        d = op_union(d, round_poly(X, Y, rhomb(-0.45 * H, 0.55 * H,
                                               0.34 * H), 0.8), 0.7)
        return d
    return fit_size(trace(f, half=H * 1.5), size)


def katabami(size=SIZE):
    """酢漿草 - wood sorrel. Three heart leaves, one up and two down, each
    leaf notched at its outer tip.

    Measured (Japanese Crest Katabami): aspect 1.10, three leaves with
    valleys at 0.55 between them. Each leaf is two round bumps side by side,
    so the tip notch falls out of the construction rather than being cut in.
    That double bump is the signature - a plain trefoil reads as clover."""
    R = size / 2
    lobe = 0.34 * R
    d0 = 0.60 * R                      # leaf centre distance
    spread = 0.22 * R                  # half-separation of the two bumps

    def leaf(X, Y, deg):
        Xr, Yr = rot(X, Y, deg)
        d = sd_circle(Xr, Yr, d0, spread, lobe)
        return op_union(d, sd_circle(Xr, Yr, d0, -spread, lobe), 0.5)

    def f(X, Y):
        # A 0.53R core made the leaves barely protrude and the whole thing
        # read as a six-bump blob. The core has to sit well below the valley
        # so the three leaves separate; 0.44R still leaves 6.6mm of pocket
        # clearance against the 5.85mm gate.
        d = sd_circle(X, Y, 0.0, 0.0, 0.48 * R)
        for i in range(3):
            d = op_union(d, leaf(X, Y, 90.0 + 120.0 * i), 0.7)
        return d
    return fit_size(trace(f, half=R * 1.6), size)


def hakkaku(size=SIZE):
    """八角 / 角十字 - the eight-point star of two crossed squares, as on the
    Kabayama ju-monji.

    Measured (Ju-monji - Kabayama): aspect 0.996, 8 points, valley 0.41-0.55
    of peak. Straight edges throughout - the one shape in the family with no
    curvature at all, which is why it earns a slot next to nine round ones."""
    R = size / 2
    rv = 0.55 * R
    verts = []
    for i in range(8):
        a_out = math.radians(90 + 45 * i)
        a_in = a_out + math.radians(22.5)
        verts.append((R * math.cos(a_out), R * math.sin(a_out)))
        verts.append((rv * math.cos(a_in), rv * math.sin(a_in)))
    return fit_size(trace(lambda X, Y: round_poly(X, Y, verts, 0.9),
                          half=R * 1.5), size)


def ogi(size=SIZE):
    """扇 - folding fan. A circular sector, pivot down, arc up.

    Measured (Gohonnhone Oogi): aspect 1.553, so the half-angle is
    asin(1.553/2) = 51 degrees. Hangs from the arc rather than the pivot
    because the cord hole is bored on the x=0 axis from the top down, and the
    pivot is far too narrow to carry 2.5mm of crown."""
    beta = math.asin(1.553 / 2.0)          # half-angle, ~51 degrees
    Rr = size / (2 * math.sin(beta))
    cb, sb = math.cos(beta), math.sin(beta)

    def f(X, Y):
        # pivot at the origin, arc overhead; fit_size recentres afterwards
        d = sd_circle(X, Y, 0.0, 0.0, Rr)
        # the wedge is two half-planes through the pivot. Both normals are
        # unit length, so these are exact distances and the fillet radius at
        # the pivot is the k passed in.
        d = op_inter(d, X * cb - Y * sb, 1.2)
        d = op_inter(d, -X * cb - Y * sb, 1.2)
        return d
    return fit_size(trace(f, half=Rr * 1.4), size)


def tomoe(size=32.0):
    """巴 - the comma / magatama, drawn as ONE comma rather than the usual
    three. A mitsudomoe's three commas are separated by whitespace, so as a
    filled silhouette it is just a disc; a single comma is a closed shape and
    is the only OBVIOUSLY asymmetric member of the family, which is what the
    brief asks for in place of near-symmetry.

    The head has to carry the whole NFC pocket AND the three peg sockets: the
    pocket needs 5.85mm of clearance and a peg ring needs another 2.2mm
    outside it, so the head radius is pinned at >= 9.3mm and the bead comes
    out slightly over 30mm. That is a hard constraint from the solver, not a
    style choice."""
    R = size / 2
    head_r = 0.66 * R
    gap = 0.11 * R                    # the comma's eye: the slot the tail
                                      # leaves against the head
    tr0 = 0.16 * R                    # tail half-thickness at the root
    trmin = 0.058 * R                 # ... and at the tip, >= MIN_STROKE/2

    def f(X, Y):
        d = sd_circle(X, Y, 0.0, 0.0, head_r)
        # Tail: a chain of shrinking discs sweeping clockwise from the head's
        # right shoulder around and over the top. The gap ramps up from
        # negative (fully merged into the head, so the tail has a root) to
        # `gap`, which is what opens the eye. A tail tapered to a true point
        # would be unprintable, hence trmin.
        n = 40
        for i in range(n):
            t = i / (n - 1.0)
            a = math.radians(-95 + 250 * t)
            tr = tr0 * (1.0 - t) + trmin
            g = -tr0 + (gap + tr0) * min(1.0, t / 0.18)
            rad = head_r + g + tr
            d = op_union(d, sd_circle(X, Y, rad * math.cos(a),
                                      rad * math.sin(a), tr), 0.7)
        return d
    return fit_size(trace(f, half=R * 1.8), size)


MON = {
    "mokko": mokko,
    "kikko": kikko,
    "kiku": kiku,
    "ume": ume,
    "kikyo": kikyo,
    "suhama": suhama,
    "matsukawa": matsukawa_bishi,
    "katabami": katabami,
    "hakkaku": hakkaku,
    "ogi": ogi,
    "tomoe": tomoe,
}


# ------------------------------------------------------------ quality gates
def _mask(pts, X, Y):
    inside = np.zeros(X.shape, bool)
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if y1 == y2:
            continue
        cond = (y1 > Y) != (y2 > Y)
        xin = x1 + (Y - y1) * (x2 - x1) / (y2 - y1)
        inside ^= cond & (X < xin)
    return inside


def _grid(pts, ppm=10.0, pad=2.0):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    half = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 + pad
    n = int(2 * half * ppm)
    ax = (np.arange(n) + 0.5) / ppm - half
    return np.meshgrid(ax, ax), 1.0 / ppm


def min_edge(pts):
    n = len(pts)
    return min(math.hypot(pts[(i + 1) % n][0] - pts[i][0],
                          pts[(i + 1) % n][1] - pts[i][1]) for i in range(n))


def max_edge(pts):
    n = len(pts)
    return max(math.hypot(pts[(i + 1) % n][0] - pts[i][0],
                          pts[(i + 1) % n][1] - pts[i][1]) for i in range(n))


def min_angle(pts, window=1.5):
    """Interior angle measured across a `window` mm arc either side, NOT
    between adjacent vertices.

    On a densely sampled curve the adjacent-vertex angle is always ~179
    degrees and the gate is meaningless; measuring across a real 1.5mm span
    is what actually detects a barb at the scale the nozzle sees it."""
    n = len(pts)
    k = max(1, int(round(window / max(1e-6, max_edge(pts)))))
    worst = 180.0
    for i in range(n):
        a, b, c = pts[(i - k) % n], pts[i], pts[(i + k) % n]
        v1 = (a[0] - b[0], a[1] - b[1])
        v2 = (c[0] - b[0], c[1] - b[1])
        n1 = math.hypot(*v1) or 1.0
        n2 = math.hypot(*v2) or 1.0
        cosv = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
        worst = min(worst, math.degrees(math.acos(cosv)))
    return worst


def thin_area(pts, w=MIN_STROKE):
    """Area (mm^2) of material thinner than w, via a morphological opening.

    This is the honest 'no slivers' test. A minimum EDGE length says nothing
    about whether an arm of the shape is thin - a 2mm-long edge can bound a
    0.3mm spike. Opening by w/2 removes anything narrower than w, so whatever
    the opening drops is exactly the unprintable material."""
    from scipy.ndimage import binary_erosion, binary_dilation
    (X, Y), px = _grid(pts)
    m = _mask(pts, X, Y)
    r = int(round((w / 2.0) / px))
    if r < 1:
        return 0.0
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    se = (xx * xx + yy * yy) <= r * r
    opened = binary_dilation(binary_erosion(m, se), se)
    return float(np.sum(m & ~opened)) * px * px


def asymmetry(pts):
    """Left/right mismatch as a fraction of area. The brief's rule is that a
    shape must be symmetric or OBVIOUSLY asymmetric; a few percent reads as a
    mistake. Mirrored constructions land at ~0 (grid noise only)."""
    (X, Y), px = _grid(pts)
    m = _mask(pts, X, Y)
    mm = _mask([(-x, y) for x, y in pts], X, Y)
    a = float(np.sum(m))
    return float(np.sum(m ^ mm)) / a if a else 1.0


def rot_order(pts, kmax=16):
    """Largest k for which a 360/k rotation maps the shape onto itself.

    Rotate about the AREA CENTROID, not the origin. fit_size centres each
    shape on its bounding box, and for anything with odd-fold symmetry - a
    5-petal ume, a 3-leaf katabami - the bbox centre is not the rotational
    centre, so rotating about the origin reported every one of them as
    1-fold."""
    (X, Y), px = _grid(pts)
    m = _mask(pts, X, Y)
    a = float(np.sum(m))
    if not a:
        return 1
    cx = float(np.sum(X[m])) / a
    cy = float(np.sum(Y[m])) / a
    best = 1
    for k in range(2, kmax + 1):
        th = 2 * math.pi / k
        ca, sa = math.cos(th), math.sin(th)
        r = [(cx + (x - cx) * ca - (y - cy) * sa,
              cy + (x - cx) * sa + (y - cy) * ca) for x, y in pts]
        if float(np.sum(m ^ _mask(r, X, Y))) / a < 0.03:
            best = k
    return best


def gates(pts):
    return {
        "min_edge": min_edge(pts), "max_edge": max_edge(pts),
        "min_angle": min_angle(pts), "thin": thin_area(pts),
        "asym": asymmetry(pts), "rot": rot_order(pts),
    }


def ok_gates(g):
    return (g["thin"] < 1.0 and g["min_angle"] >= MIN_ANGLE
            and (g["asym"] < 0.02 or g["asym"] > 0.15))


# ------------------------------------------------------------------- render
def render(names=None, path=None):
    import imageio.v2 as imageio
    import preview_talismans as PT
    names = names or list(MON)
    tiles = []
    for nm in names:
        pts = MON[nm]()
        tiles.append(PT.render_pts(pts, size_mm=38.0))
        print("  rendered %s" % nm)
    h, w = tiles[0].shape[:2]
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    pad = 8
    out = np.full((rows * (h + pad) + pad, cols * (w + pad) + pad, 3), 10,
                  np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        out[pad + r * (h + pad):pad + r * (h + pad) + h,
            pad + c * (w + pad):pad + c * (w + pad) + w] = t
    here = os.path.dirname(os.path.abspath(__file__))
    p = path or os.path.join(here, "japanese_glow.png")
    imageio.imwrite(p, out)
    print("wrote %s  %dx%d" % (os.path.basename(p), out.shape[1], out.shape[0]))
    print("order (%d cols): %s" % (cols, ", ".join(names)))


# -------------------------------------------------------------------- audit
def audit():
    print("%-11s %-4s %-6s %-4s %7s %-11s %5s %5s | %5s %5s %6s %5s %4s"
          % ("mon", "fit", "pocket", "pegs", "spread", "hole y/crown",
             "w", "h", "edge", "angle", "thin", "asym", "rot"))
    bad = []
    for nm in MON:
        pts = MON[nm]()
        f = S.fit_report(pts)
        g = gates(pts)
        note = ""
        if not f["pocket_ok"]:
            note += "  POCKET %.2f<%.2f" % (f["pocket"][2], S.POCKET_R + S.WALL)
        elif not f["pegs_ok"]:
            note += "  NO PEG TRIPLE"
        elif f["spread"] <= 40.0:
            note += "  PEGS CRAMPED"
        if not f["hole_ok"]:
            note += "  NO HOLE"
        if g["thin"] >= 1.0:
            note += "  THIN %.1fmm2" % g["thin"]
        if g["min_angle"] < MIN_ANGLE:
            note += "  BARB %.0fdeg" % g["min_angle"]
        if 0.02 <= g["asym"] <= 0.15:
            note += "  NEAR-SYMMETRIC %.3f" % g["asym"]
        if not (f["ok"] and ok_gates(g)):
            bad.append(nm)
        hs = ("%.1f / %.1f" % f["hole"]) if f["hole"] else "-"
        print("%-11s %-4s %-6.2f %-4s %7.1f %-11s %5.1f %5.1f | %5.2f %5.1f "
              "%6.2f %5.3f %4d%s"
              % (nm, "ok" if (f["ok"] and ok_gates(g)) else "FAIL",
                 f["pocket"][2], "yes" if f["pegs_ok"] else "no", f["spread"],
                 hs, f["w"], f["h"], g["min_edge"], g["min_angle"], g["thin"],
                 g["asym"], g["rot"], note))
    print()
    print("pocket needs >= %.2fmm clearance; stroke >= %.1fmm; angle >= %.0fdeg"
          % (S.POCKET_R + S.WALL, MIN_STROKE, MIN_ANGLE))
    print("failing: %s" % (", ".join(bad) if bad else "none"))
    return bad


# ---------------------------------------------------------------- rejections
REJECTED = """
Mon looked at and rejected, with the reason - so this is not re-litigated:

  mitsudomoe (三つ巴)   three commas separated by whitespace; solid-filled it
                        is a plain disc. Kept as a SINGLE comma instead.
  kiri (桐, paulownia)  three flower spikes over three leaves, all detached.
  myoga (茗荷)          two crossed ginger sprouts; the crossing is line art.
  takanoha (鷹の羽)     hawk feathers. One feather is too narrow to hold a
                        10.5mm pocket at 30mm; two crossed feathers are two
                        parts plus the vane lines that make them read.
  wachigai (輪違い)     interlocked rings - an annulus cannot host the pocket.
  janome (蛇の目)       same problem, one ring.
  jumonji in a circle   ring plus cross: two parts.
  aoi (葵, hollyhock)   three leaves with heavy vein work; the veins ARE the
                        crest.
  kashiwa (柏, oak)     ditto, and the leaf outline alone reads as a blob.
  sasa (笹, bamboo)     bundles of separate leaves.
  tsuru (鶴, crane)     outline drawing of a bird.
  uroko (鱗)            a bare equilateral triangle: authentic, but nothing
                        about it says 'mon' as a silhouette. Mitsu-uroko is
                        three detached triangles.
  shippo (七宝)         four petals with concave sides pinching the middle -
                        the concavity eats the pocket clearance.
  yotsume-yui (四つ目結) four detached squares.
  hoshi / mitsuboshi    detached circles.
  kagome (籠目)         hexagram drawn as line art; filled it is a hexagon.
  igeta (井桁)          a well-frame: hollow by definition.
  moji-mon (字紋)       crests that are literally a kanji - not a silhouette
                        problem, a typography one.

Two were rejected only after being BUILT and rendered, which is the honest
way to find out:

  hana-kurusu (花久留子) the trefoil-ended cross. Killed by measurement, not
                        taste: its diagonal valleys drop to 0.19 of the
                        radius, so the solid core is ~2.9mm across where the
                        NFC pocket needs 11.7mm. Unbuildable at any size that
                        is still a 30mm pendant.
  hanabishi (花菱)      built, rendered, cut. Its measured profile has only
                        TWO strong peaks - the sharp left and right points -
                        with everything else sitting at 0.61-0.70, so solid
                        it is a wavy lozenge, and matsukawa-bishi already
                        occupies that slot with crisper steps. Adding the
                        tip notch that would distinguish it read as a dent,
                        not a petal. Unstretched it is the same construction
                        as mokko: four discs about a core.

Reference corpus: Wikimedia Commons "Category:SVG Japanese family crests",
504 files. Japanese mon designs are centuries old and in the public domain;
the SVG renderings in that category are published as public domain / CC0 by
their uploaders. Nothing here traces a specific file - the generators are
parametric reconstructions of the underlying compass geometry - but the
proportions were measured from those renderings.
"""


if __name__ == "__main__":
    if "--render" in sys.argv:
        render()
    elif "--rejects" in sys.argv:
        print(REJECTED)
    else:
        audit()
