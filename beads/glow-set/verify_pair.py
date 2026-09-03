"""Run tools/verify_stls.py's real checks on a single-colour TWO-part bead.

verify_stls.verify() hard-requires Bottom+Top+Decoration and bails before
checking anything if one is missing. Glow-set beads are single-filament, so
there is no Decoration and never will be. Faking one is not an option - a stray
Decoration.stl in tmp/latest is exactly the stale-staging trap that silently
bundles the wrong geometry into the 3MF.

So this imports the module and calls the SAME per-part check functions, rather
than reimplementing them. The only check skipped is decoration-stacking, which
is meaningless without a decoration.

  .venv/Scripts/python.exe beads/glow-set/verify_pair.py [--dir tmp/latest]
"""
import argparse
import os
import sys

_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(_d, "tools")) and os.path.dirname(_d) != _d:
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)
from tools import verify_stls as V  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--dir", default=os.path.join(V.__file__, "..", "..", "tmp", "latest"))
ap.add_argument("--r", type=float, default=16.0, help="BEAD_R the bead was built at")
a = ap.parse_args()
stl_dir = os.path.abspath(a.dir)

# verify_stls' dimension constants describe the original 17mm rezz Kandi bead
# (17 dia / 4.0 bottom / 2.5 top). The glow-set family is a different size and
# a different split, so against those constants every glow bead "fails" four
# checks that are not about it. Retarget them at build_talisman.py's CONFIG
# instead of skipping them - the check stays real and will still catch a bead
# built at the wrong scale or split at the wrong Z.
#   BOTTOM_THICK 1.5 + PEG_HEIGHT 1.2 = 2.7mm standing on the plate
#   TOP_THICK    3.0
V.EXPECTED_DIA_MM = 2.0 * a.r
V.DIA_TOL_MM = 0.5
V.BOTTOM_THICK_MM, V.BOTTOM_THICK_TOL_MM = 2.7, 0.15
V.TOP_THICK_MM, V.TOP_THICK_TOL_MM = 3.0, 0.15

fails = 0
for name in ("Bottom", "Top"):
    path = os.path.join(stl_dir, "%s.stl" % name)
    if not os.path.isfile(path):
        print("MISSING %s" % path)
        fails += 1
        continue
    m = V._load(path)
    if m is None:
        print("UNREADABLE %s" % path)
        fails += 1
        continue
    checks = [V._check_geometry(m), V._check_watertight(m),
              V._check_bed_flat(m, name), *V._check_dimensions(m, name)]
    print(name)
    for c in checks:
        print(c.fmt())
        if not c.ok:
            fails += 1
    print()

print("PAIR VERIFICATION %s" % ("FAILED: %d check(s)" % fails if fails else "PASSED"))
sys.exit(1 if fails else 0)
