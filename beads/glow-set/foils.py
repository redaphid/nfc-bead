"""Foil / rosette silhouettes - a historically grounded perimeter language.

WHERE THIS COMES FROM. The constraint set here - monochrome, small, must read as
a pure outline, strictly symmetric, and the shape itself carries meaning - is not
new. Three traditions solved it:

  * Japanese MON (family crests). Circular, n-fold symmetric, abstract, designed
    to read in ONE colour at small size. The closest match to all our
    constraints simultaneously.
  * ADINKRA (Akan, Ghana). Geometric stamps, each carrying a proverb - "as if
    the shapes have meaning" is the literal design brief.
  * GOTHIC TRACERY FOILS - trefoil, quatrefoil, cinquefoil, multifoil. A whole
    grammar for building an interesting PERIMETER out of arcs and cusps. The
    same vocabulary shows up in Islamic girih rosettes and Mudejar cusped arches.

WHY IT FIXES WHAT THE POLYGONS GOT WRONG. Straight-edged archetypes with wide
bases read as cartoon weights, and their perimeters are dull because a perimeter
of 6 straight lines has nothing happening along it. A foil's perimeter is arcs
meeting at cusps, so interest is distributed all the way around.

CONSTRUCTION. n lobe-circles of radius `rho`, centres on a ring of radius `c`,
unioned with a central disc of radius `r0`. The outline is the union boundary,
sampled in polar: for each angle, the distance to the furthest circle exit.
Cusps appear naturally where adjacent lobes intersect - they are not faked.

The central disc is doing structural work, not just visual: it guarantees the
10.5mm NTAG215 pocket always fits, so the lobes are free to be pure ornament.
"""
import hashlib
import math
import random

import shapes as S


def rng_for(name):
    h = hashlib.sha256(name.strip().lower().encode("utf-8")).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def _ray_exit(ux, uy, cx, cy, rho):
    """Distance from origin along unit ray (ux,uy) to exit circle (cx,cy,rho).
    Returns 0 if the ray misses."""
    b = ux * cx + uy * cy
    c2 = cx * cx + cy * cy - rho * rho
    disc = b * b - c2
    if disc < 0:
        return 0.0
    return b + math.sqrt(disc)


def foil(n, r0, c, rho, samples=360, phase=0.0, alt=None):
    """Union of n lobe-circles plus a central disc, as a closed polygon.

    alt: optional (c2, rho2) for ALTERNATING lobes - big/small around the ring,
    which is how a lot of mon and tracery get a richer perimeter without adding
    more lobes.
    """
    lobes = []
    for i in range(n):
        a = phase + 2 * math.pi * i / n
        if alt and i % 2 == 1:
            lobes.append((alt[0] * math.cos(a), alt[0] * math.sin(a), alt[1]))
        else:
            lobes.append((c * math.cos(a), c * math.sin(a), rho))

    pts = []
    for k in range(samples):
        th = 2 * math.pi * k / samples
        ux, uy = math.cos(th), math.sin(th)
        r = r0                                   # central disc floor
        for (cx, cy, rr) in lobes:
            r = max(r, _ray_exit(ux, uy, cx, cy, rr))
        pts.append((r * ux, r * uy))
    return S.ccw(pts)


def solve_lobes(n, r_tip, r_valley):
    """Given n lobes with tips at r_tip and cusps biting down to r_valley,
    solve for the lobe centre-radius c and lobe radius rho.

    Cusp DEPTH is the thing that makes a foil read as tracery rather than as a
    cluster of balloons, so it is the parameter, not an emergent side effect.
    Two adjacent lobe circles meet on the midline at
        d = c*cos(pi/n) + sqrt(rho^2 - (c*sin(pi/n))^2)
    with rho = r_tip - c. d falls as c grows, so bisect on c."""
    half = math.pi / n

    def valley(c):
        rho = r_tip - c
        inner = rho * rho - (c * math.sin(half)) ** 2
        if inner < 0:
            return -1.0
        return c * math.cos(half) + math.sqrt(inner)

    lo, hi = 1e-4, r_tip * 0.999
    for _ in range(80):
        mid = (lo + hi) / 2
        if valley(mid) > r_valley:
            lo = mid
        else:
            hi = mid
    c = (lo + hi) / 2
    return c, r_tip - c


def deepest_valley(n, r_tip):
    """The deepest cusp n lobes can physically cut.

    Lobes stop reaching the midline once rho < c*sin(pi/n); past that the ray
    finds no circle and the outline collapses to r=0, producing a degenerate
    pinwheel rather than a foil. So cusp depth is BOUNDED BY LOBE COUNT: 3
    lobes reach 0.27r, 6 lobes only 0.58r, 12 lobes only 0.77r. More lobes
    necessarily means shallower cusps."""
    half = math.pi / n
    c_max = r_tip / (1.0 + math.sin(half))
    return c_max * math.cos(half)


def cusped(n, r_tip, r_valley, samples=480, phase=0.0):
    """n-foil specified the way a mason would: tip radius and cusp depth.

    r_valley is clamped to what n lobes can actually reach, and the same value
    is passed as the central-disc floor so the union can never dip to zero."""
    floor = deepest_valley(n, r_tip)
    v = max(r_valley, floor * 1.001)
    c, rho = solve_lobes(n, r_tip, v)
    return foil(n, v * 0.995, c, rho, samples=samples, phase=phase)


def _ray_enter(ux, uy, cx, cy, q):
    """Distance along the ray to ENTER circle (cx,cy,q); inf if it misses."""
    b = ux * cx + uy * cy
    c2 = cx * cx + cy * cy - q * q
    disc = b * b - c2
    if disc < 0:
        return float("inf")
    t = b - math.sqrt(disc)
    return t if t > 0 else float("inf")


def cusped_rim(n, R, bite, q_frac=1.0, samples=600, phase=0.0):
    """A DISC with n circular bites cut into its rim, meeting at sharp cusps.

    This is what Gothic tracery actually is: the outer boundary is a circle and
    the foils are voids cut into it, so the cusps point INWARD as sharp spurs.
    Unioning convex lobes outward - the previous approach - can only ever make
    petals, which is why it read as clover no matter how the numbers moved.

    bite   : how far the cut reaches in from the rim (mm)
    q_frac : cutter radius as a fraction of the rim spacing; larger = wider,
             shallower-sided bites, smaller = narrow deep notches.
    """
    spacing = 2 * math.pi * R / n
    q = spacing * 0.5 * q_frac
    d = R - bite + q                       # centre distance so the cut reaches
    cutters = []
    for i in range(n):
        a = phase + 2 * math.pi * i / n
        cutters.append((d * math.cos(a), d * math.sin(a), q))

    pts = []
    for k in range(samples):
        th = 2 * math.pi * k / samples
        ux, uy = math.cos(th), math.sin(th)
        r = R
        for (cx, cy, qq) in cutters:
            r = min(r, _ray_enter(ux, uy, cx, cy, qq))
        pts.append((r * ux, r * uy))
    return S.ccw(pts)


# ------------------------------------------------------------------ presets
def trefoil(r, g):
    return cusped_rim(3, r, r * 0.30, 0.85, phase=math.pi / 6)


def quatrefoil(r, g):
    return cusped_rim(4, r, r * 0.26, 0.85, phase=math.pi / 4)


def cinquefoil(r, g):
    return cusped_rim(5, r, r * 0.24, 0.85, phase=math.pi / 5 + math.pi / 2)


def sexfoil(r, g):
    return cusped_rim(6, r, r * 0.22, 0.85, phase=math.pi / 6)


def octofoil(r, g):
    return cusped_rim(8, r, r * 0.20, 0.85, phase=math.pi / 8)


def scallop(r, g):
    """Many shallow bites - a rim ripple."""
    n = g.choice([12, 14, 16])
    return cusped_rim(n, r, r * 0.11, 0.95, phase=math.pi / n)


def star_foil(r, g):
    """Few, very deep bites - narrow spurs, the most dramatic rim here."""
    n = g.choice([5, 6, 7])
    return cusped_rim(n, r, r * 0.36, 0.70, phase=math.pi / 2)


def cusped_lozenge(r, g):
    """Deep bites on 4 - reads as a cross/quatrefoil hybrid."""
    return cusped_rim(4, r, r * 0.38, 0.72, phase=math.pi / 4)


def wheel(r, g):
    n = g.choice([9, 10, 11])
    return cusped_rim(n, r, r * 0.15, 0.9, phase=math.pi / 2)


PRESETS = {
    "trefoil": trefoil, "quatrefoil": quatrefoil, "cinquefoil": cinquefoil,
    "sexfoil": sexfoil, "octofoil": octofoil, "scallop": scallop,
    "star_foil": star_foil, "cusped_lozenge": cusped_lozenge, "wheel": wheel,
}
ORDER = ["trefoil", "quatrefoil", "cinquefoil", "sexfoil", "octofoil",
         "scallop", "star_foil", "cusped_lozenge", "wheel"]


def build(name, r=16.0, seed=None):
    g = rng_for(seed or name)
    return PRESETS[name](r, g)


if __name__ == "__main__":
    print("%-15s %8s %8s %6s %6s %5s %s"
          % ("preset", "pocket", "spread", "w", "h", "pts", "fit"))
    for nm in ORDER:
        pts = build(nm)
        f = S.fit_report(pts)
        print("%-15s %8.2f %8.1f %6.1f %6.1f %5d %s"
              % (nm, f["pocket"][2], f["spread"], f["w"], f["h"], len(pts),
                 "ok" if f["ok"] else "FAIL"))
