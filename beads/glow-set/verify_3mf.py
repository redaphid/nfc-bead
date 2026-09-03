"""Independently verify a bead .3mf. Does not trust build_3mf's own log line.

Checks the four things that have actually gone wrong on this project:
  * every part on extruder 1  - extruder 2 is #FF0000 in the saved profile and
    these are single-colour glow/black beads
  * a printer profile is present at all - the shield printed badly because its
    3MF carried three entries and no project_settings.config, so the slicer
    fell back to whatever was loaded and produced NO BRIM
  * brim_type=auto_brim, brim_width=5 - the adhesion fix the quatrefoil proved
  * seam_position=random - PRINT_LOG v5c: 'aligned' stacks the seam into a scar

  .venv/Scripts/python.exe beads/glow-set/verify_3mf.py <a.3mf> [<b.3mf> ...]
"""
import re
import sys
import zipfile

WANT = {"brim_type": "auto_brim", "brim_width": "5", "seam_position": "random"}
bad = 0

for path in sys.argv[1:]:
    print(path)
    try:
        z = zipfile.ZipFile(path)
    except Exception as e:
        print("  FAIL unreadable: %s" % e)
        bad += 1
        continue
    names = z.namelist()

    ms = [n for n in names if n.endswith("model_settings.config")]
    if not ms:
        print("  FAIL no model_settings.config (extruder assignment absent)")
        bad += 1
    else:
        ex = re.findall(r'key="extruder" value="(\d+)"', z.read(ms[0]).decode())
        if ex and set(ex) == {"1"}:
            print("  OK   extruders %s" % "/".join(ex))
        else:
            print("  FAIL extruders %s - must all be 1" % ("/".join(ex) or "NONE"))
            bad += 1

    ps = [n for n in names if n.endswith("project_settings.config")]
    if not ps:
        print("  FAIL no project_settings.config - NO PRINTER PROFILE, "
              "this is the shield failure mode")
        bad += 1
    else:
        d = z.read(ps[0]).decode()
        for k, want in WANT.items():
            m = re.search(r'"%s":\s*"([^"]*)"' % k, d)
            got = m.group(1) if m else None
            if got == want:
                print("  OK   %-14s %s" % (k, got))
            else:
                print("  FAIL %-14s %r (want %r)" % (k, got, want))
                bad += 1
        m = re.search(r'"printer_model":\s*"([^"]*)"', d)
        print("  --   printer_model  %s" % (m.group(1) if m else "MISSING"))

    meshes = [n for n in names if n.endswith(".model") and "Objects" in n]
    print("  --   %d entries, %d part model(s)" % (len(names), len(meshes)))
    print()

print("3MF VERIFY %s" % ("FAILED: %d problem(s)" % bad if bad else "PASSED"))
sys.exit(1 if bad else 0)
