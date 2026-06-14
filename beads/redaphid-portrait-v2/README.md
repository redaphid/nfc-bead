# Redaphid Portrait — v2 (new design)

The `redaphid-portrait` charm rebuilt on the "new design" learned from
`gymnast-medallion` (recipe gotchas #29–32), **keeping the portrait outline as
the bead shape** (NOT a round medallion). Same multi-color portrait — cream
face, magenta hair, glowing eyes — just slimmer with a one-sided string hole and
self-starting pegs.

## What changed vs the original `redaphid-portrait`

| Aspect | Original | v2 |
|---|---|---|
| Thickness | 4.0 mm symmetric (2.0 + 2.0) | **3.5 mm asymmetric**: Bottom 2.0 + Top 1.5 (slimmer decorated front) |
| String hole | 2.0 mm, on the split plane (half-groove each side) | **1.2 mm, entirely in the thick Bottom half** (gotcha #23/#31), ~0.4 mm walls |
| Pegs | 2.0 mm, 0.1 mm clearance, blunt | 2.0 mm, **0.05 mm clearance + 0.3 mm chamfered tips** (gotcha #29/#30) so they self-start instead of needing force |

Everything else is the original portrait pipeline: silhouette extrude → hole →
asymmetric split → NFC pocket → peg sockets (in Bottom) → pegs (on Top) → Hair
decoration (magenta) + Eyes (Decoration, glow). Pegs stay on Top per the
charm's chosen layout, so the Top prints **show-face-down** (hair/eyes on the
plate, pegs up); the build exports STLs already in that orientation.

## Source

- `silhouette.svg` + `hair.svg` copied from `beads/redaphid-portrait` (tuned).
- `extract_silhouette.py` (reference) re-extracts both from the source
  screenshot `C:\Users\hypnodroid\Pictures\Screenshots\Screenshot 2026-04-25 235837.png`.

## Files

| File | What |
|---|---|
| `silhouette.svg` / `hair.svg` | portrait outline (+eyes) and haircut shape |
| `build_redaphid.py` | headless Blender build → 4 STLs + blend (+ direct print-oriented export) |
| `print/Bottom.stl` | cream — thick back half: NFC pocket, peg sockets, string hole |
| `print/Top.stl` | cream — thin front half + pegs (prints show-face-down) |
| `print/Hair.stl` | magenta — raised haircut |
| `print/Decoration.stl` | glow — the two eyes |
| `print/redaphid-portrait-v2.3mf` | slicer bundle (Bottom + Top+Hair+Decoration merged) |
| `preview.png` | render (viewed from the show-face side) |

## Rebuild

```sh
"D:\tools\blender\blender.exe" --background --python beads/redaphid-portrait-v2/build_redaphid.py
uv run nfc-make-3mf --dir beads/redaphid-portrait-v2/print --out beads/redaphid-portrait-v2/print/redaphid-portrait-v2.3mf
```

## Verified

All four parts watertight (Decoration = 2 eyes = 2 bodies, expected). String
hole open in the Bottom (ray cast: solid/void/void/solid, 0.4 mm walls). Pegs
single-body welded to Top with chamfered tips. Three peg positions pass the
silhouette + NFC + hole clearance checks.

## Watch on print

- 0.4 mm walls around the 1.2 mm string hole bridge fine on a tuned printer; bump `BOTTOM_THICK` toward 2.2 mm if they sag.
- Top prints show-face-down — the multi-color hair/eyes are the first layers (mind the bed finish). The original tracked this as `top-v5b-1stlayer`.
