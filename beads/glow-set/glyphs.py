"""Glyph generators for the glow medallion.

Every glyph is a list of primitives consumed by build_glow_medallion.carve_glyph:
    ("dot",  x, y, r)                          - r in mm
    ("line", x1, y1, x2, y2, w)                - w in mm
    ("ring", r_inner, r_outer)
    ("arc",  r_inner, r_outer, a0deg, a1deg)

All strokes obey the engraved-line-art rule: 0.8mm <= width <= 2.2mm, so a
1.2mm-deep groove keeps aspect >= 1 and self-shadows at night. Broad filled
shapes are deliberately not offered - they vanish in the dark.

Randomness is seeded with a stable hash of the person's name, NOT Python's
built-in hash(), which is salted per-process and would give a different bead on
every run. Same name -> same bead, forever, on any machine.
"""
import hashlib
import math
import random

R_MAX = 6.2          # must match build_glow_medallion.GLYPH_R_MAX


def rng_for(name):
    """Deterministic RNG seeded from a name. Stable across runs and machines."""
    h = hashlib.sha256(name.strip().lower().encode("utf-8")).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


# ---------------------------------------------------------------- star chart
def star_chart(name, n_stars=None, link=True):
    """A unique constellation. Dots are kept <=1.3mm across so they stay
    self-shadowing; links are 0.8mm hairlines."""
    r = rng_for(name)
    n = n_stars or r.randint(5, 8)
    pts = []
    tries = 0
    while len(pts) < n and tries < 400:
        tries += 1
        # sample in polar so the middle does not over-crowd
        rad = R_MAX * 0.92 * math.sqrt(r.uniform(0.02, 1.0))
        ang = r.uniform(0, 2 * math.pi)
        x, y = rad * math.cos(ang), rad * math.sin(ang)
        if all(math.hypot(x - px, y - py) > 2.4 for px, py, _ in pts):
            pts.append((x, y, r.choice([0.45, 0.5, 0.55, 0.65])))
    glyph = []
    if link and len(pts) > 1:
        # link each star to its nearest unlinked neighbour: an open path, so the
        # figure reads as a constellation rather than a polygon
        order = [0]
        remaining = set(range(1, len(pts)))
        while remaining:
            last = order[-1]
            nxt = min(remaining, key=lambda i: math.hypot(pts[i][0] - pts[last][0],
                                                          pts[i][1] - pts[last][1]))
            order.append(nxt)
            remaining.discard(nxt)
        for a, b in zip(order, order[1:]):
            glyph.append(("line", pts[a][0], pts[a][1], pts[b][0], pts[b][1], 0.8))
    for (x, y, rr) in pts:
        glyph.append(("dot", x, y, rr))
    return glyph


# --------------------------------------------------------------- vinyl groove
def groove(name, n_bands=None):
    """Concentric grooves marching outward - reads as a record. The RHYTHM of
    the gaps is the personalisation, so grooves are laid down sequentially with
    guaranteed lands between them rather than sampled and filtered (which left
    only two or three rings and looked like nothing)."""
    r = rng_for(name)
    glyph = []
    widths = [0.8, 0.9, 1.0]
    gaps = [0.5, 0.6, 0.8]
    rad = r.choice([1.0, 1.2, 1.4])
    while True:
        w = r.choice(widths)
        if rad + w > R_MAX - 0.2:
            break
        glyph.append(("ring", round(rad, 3), round(rad + w, 3)))
        rad += w + r.choice(gaps)
    glyph.append(("dot", 0.0, 0.0, 0.6))     # spindle
    return glyph


# ---------------------------------------------------------------------- sigil
def sigil(name, strokes=None):
    """A bold seeded glyph: a connected stroke path on a lattice. Angular and
    rune-like, because straight strokes engrave cleanly. Step length and turn
    set vary per person, otherwise every sigil lands on the same few radii and
    they all look like siblings."""
    r = rng_for(name)
    n = strokes or r.randint(5, 8)
    step = r.choice([1.9, 2.2, 2.5, 2.8])
    turn = r.choice([45, 60, 72, 90])
    dirs = [(math.cos(math.radians(a)), math.sin(math.radians(a)))
            for a in range(0, 360, turn)]
    # start off-centre so the figure is not always radially symmetric
    a0 = r.uniform(0, 2 * math.pi)
    x, y = r.uniform(0, 1.4) * math.cos(a0), r.uniform(0, 1.4) * math.sin(a0)
    pts = [(x, y)]
    prev = None
    for _ in range(n):
        opts = [d for d in dirs
                if prev is None or (d[0] * -prev[0] + d[1] * -prev[1]) < 0.99]
        r.shuffle(opts)
        for dx, dy in opts:
            nx, ny = x + dx * step, y + dy * step
            if math.hypot(nx, ny) <= R_MAX - 0.7:
                pts.append((nx, ny))
                prev = (dx, dy)
                x, y = nx, ny
                break
        else:
            break
    w = r.choice([1.0, 1.1, 1.3])
    glyph = [("line", a[0], a[1], b[0], b[1], w) for a, b in zip(pts, pts[1:])]
    glyph.append(("dot", pts[0][0], pts[0][1], 0.6))
    return glyph


GENERATORS = {"star": star_chart, "groove": groove, "sigil": sigil}


def build(theme, name, **kw):
    if theme not in GENERATORS:
        raise ValueError("unknown theme %r - pick one of %s"
                         % (theme, sorted(GENERATORS)))
    return GENERATORS[theme](name, **kw)
