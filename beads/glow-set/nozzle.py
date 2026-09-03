"""Nozzle-dependent constants for the glow-set bead, as named profiles.

WHY THIS EXISTS. Every dimension in this bead that touches a wall, a bore or a
clearance was tuned empirically on a **0.4mm nozzle at 0.42mm line width and
0.20mm layers**. Those numbers are not geometry, they are a fit between geometry
and one extruder. `WALL = 0.6` is 1.4 line widths at 0.4 and *less than one* at
0.6; `HOLE_D = 1.2` is three line widths at 0.4 and under two at 0.6. Swapping
the nozzle and keeping the constants would silently produce walls the slicer
cannot fill and bores it closes over.

So the nozzle-sensitive constants live here, keyed by nozzle, and `shapes.py`
and `build_talisman.py` read them instead of hardcoding. `BEAD_NOZZLE` selects
the profile and **defaults to "0.4", so the existing 0.4mm build is unchanged**
- byte-identical STLs, verified by rebuilding a bead before and after this
module existed and comparing sha256.

    BEAD_NOZZLE=0.6 blender -b --python build_talisman.py

Any single key can be overridden with `BEAD_<KEY>` for a single-variable
experiment. That is how the PEG_CLEAR fit ladder is built - one geometry, four
clearances - without editing a profile:

    BEAD_NOZZLE=0.6 BEAD_PEG_CLEAR=0.10 blender -b --python build_talisman.py

WHAT IS *NOT* HERE. `BOTTOM_THICK`, `TOP_THICK` and `PEG_HEIGHT` stay in
build_talisman.py. They are already exact multiples of both 0.20 and 0.30, so
they quantise cleanly at either nozzle and there is nothing to vary.
"""
import os

PROFILES = {
    # --------------------------------------------------------------- 0.4mm
    # The shipped, hardware-proven set. Do not tune these here; they are the
    # record of what actually printed and snapped (recipe gotchas #29/#30/#40).
    "0.4": dict(
        LINE_W=0.42,
        LAYER=0.20,
        WALL=0.6,           # 1.43 line widths - two perimeters, slightly lean
        HOLE_R=0.6,
        HOLE_CROWN=2.5,
        HOLE_D=1.2,         # 2.86 line widths
        NFC_DEPTH=0.8,      # 4 x 0.20 layers
        SOCKET_LEADIN=0.4,  # 2 x 0.20 layers
        PEG_DIAMETER=2.6,
        PEG_CLEAR=0.01,
    ),
    # --------------------------------------------------------------- 0.6mm
    # DERIVED, NOT MEASURED. Nothing in this profile has been printed. It
    # assumes 0.63mm line width and 0.30mm layers - if the real Elegoo profile
    # differs, every ratio below moves. See beads/glow-set/NOZZLE_06.md for the
    # per-constant reasoning and for what still has to be settled on hardware.
    "0.6": dict(
        LINE_W=0.63,
        LAYER=0.30,
        # Two perimeters meeting back to back need 2 x 0.63 = 1.26mm. 1.20 is
        # 0.06 under that, which a slicer absorbs by thinning both perimeters;
        # 1.26 itself is not used because it costs a silhouette (kikyo clears
        # the pocket by 6.55mm, and 5.25 + 1.26 = 6.51 leaves 0.04mm of margin,
        # which is inside the solver's own grid noise).
        WALL=1.2,
        HOLE_R=0.9,
        HOLE_CROWN=2.5,     # unchanged: a cord-strength rule, not a nozzle one
        HOLE_D=1.8,         # 2.86 line widths - the same ratio 1.2 had at 0.4
        NFC_DEPTH=0.9,      # 3 x 0.30 layers (0.8 is not a layer multiple)
        SOCKET_LEADIN=0.6,  # 2 x 0.30 layers; 0.4 is 1.33 layers and relieves
                            # only the first of the two squished layers (#42)
        PEG_DIAMETER=2.6,   # 4.1 line widths - two perimeters plus gap fill.
                            # Unchanged: it is a grip dimension, and the bore
                            # around it is what moves at a wider line width.
        PEG_CLEAR=0.06,     # PLACEHOLDER - the middle of the fit ladder. This
                            # is the one number the 0.6 print has to settle.
    ),
}

NOZZLE = os.environ.get("BEAD_NOZZLE", "0.4")
if NOZZLE not in PROFILES:
    raise SystemExit("BEAD_NOZZLE=%r - pick one of %s"
                     % (NOZZLE, sorted(PROFILES)))

P = dict(PROFILES[NOZZLE])
OVERRIDES = {}
for _k in sorted(P):
    _v = os.environ.get("BEAD_" + _k)
    if _v is not None:
        P[_k] = float(_v)
        OVERRIDES[_k] = P[_k]


def banner():
    s = "nozzle %s (line %.2f, layer %.2f)" % (NOZZLE, P["LINE_W"], P["LAYER"])
    if OVERRIDES:
        s += "  overrides: " + " ".join("%s=%g" % kv
                                        for kv in sorted(OVERRIDES.items()))
    return s


if __name__ == "__main__":
    print(banner())
    for k in sorted(P):
        print("  %-14s %s" % (k, P[k]))
