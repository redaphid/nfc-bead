# Gymnast beads — 6 acrobat silhouette charms

Six gymnast/acrobat pose silhouettes turned into simple flat extruded charms.
**This is a deliberately simplified branch of the recipe** — no NFC pocket, no
two-half snap-fit, no pegs. Each bead is a single solid extrusion of one
silhouette with a through-thickness string hole where the pose is thick enough
to host one.

## Source

- Image: `C:\Users\hypnodroid\Downloads\handstand.png` — a single 1570×1210 PNG
  with 6 black acrobat silhouettes on white, inside a rounded-rect border frame.
- Extraction: `extract_gymnasts.py` (run it to regenerate `regions.json` +
  `extract_debug.png`).

## Why this charm exists

Exercises the pipeline on a **multi-figure** input and a **simplified, NFC-less
bead** path — the first time the repo has produced plain extruded silhouette
charms rather than the full two-half snap-fit. Useful as the reference for "I
just want the outline as a printable token/pendant."

## Key creative decisions and tradeoffs

| Decision | Why / tradeoff |
|---|---|
| No NFC pocket / split / pegs | User wanted plain extruded outlines. Drops most of the recipe; each bead is one watertight solid. |
| 25 mm longest side, 2.5 mm thick | Each figure scaled so its *longest* bbox side = 25 mm (poses vary wildly in aspect ratio). 2.5 mm is sturdy for a flat charm. |
| Faithful outlines (no limb thickening) | Kept the silhouettes exact. Cost: thin extended limbs/toes (esp. poses 2, 3, 6 feet) are the fragility risk on the print. |
| String hole = thickest interior point, prefer upper body | Auto-placed via distance transform so the hole always lands in load-bearing material. Hole runs through the 2.5 mm face (flat-pendant style), not lengthwise. |
| Poses 2 & 3 have **no hole** | The slim vertical handstands lack 2 mm-dia + 1 mm-wall of material anywhere. Per user ("keep the easy ones") they ship hole-free rather than getting a non-faithful hang tab. |
| 6 parts → one 3MF, 3×2 grid | Distinct XY per part, so slicers import them already spread on the plate. |

## What's transferable / what's specific

- **Transferable**: the multi-figure extractor (invert + label-all-components +
  drop-frame + per-figure fourier trace) and the adaptive distance-transform
  hole placement generalize to any "many silhouettes in one image" job.
- **Specific**: `LUMA_THRESHOLD=128` (dark-on-white), `FRAME_BBOX_FRAC` frame
  rejection, and the 6-figure reading-order sort are tuned to this image.

## Files

| File | What |
|---|---|
| `extract_gymnasts.py` | Multi-figure extractor → `regions.json` + `extract_debug.png` |
| `regions.json` | Per-figure mm polygon + auto hole position |
| `extract_debug.png` | Source image with traced contours + hole rings (sanity check) |
| `build_gymnasts.py` | Headless Blender build: polygon → extrude → drill → STL + preview |
| `gymnasts.blend` | Saved scene (all 6 laid out on a grid) |
| `preview.png` | Top-down render of the 6 beads |
| `bundle_3mf.py` | Bundles `print/pose*.stl` into `print/gymnasts.3mf` |
| `print/pose1..6.stl` | The 6 printable parts (each watertight, 2.5 mm thick) |
| `print/gymnasts.3mf` | Slicer-ready bundle, all 6 on one plate |

## Rebuild

```sh
uv run python beads/gymnasts/extract_gymnasts.py            # image -> regions.json
"D:\tools\blender\blender.exe" --background --python beads/gymnasts/build_gymnasts.py
uv run python beads/gymnasts/bundle_3mf.py                  # STLs -> 3MF
```

## Print notes

- Single color, PLA/PETG, 0.12–0.16 mm layer height, 100% infill (tiny parts),
  no supports — they print flat on the silhouette face.
- Watch the thin limbs/toes (poses 2, 3, and the pointed feet on 6). If any snap
  off the plate or after printing, scale up in the slicer or thicken in
  `extract_gymnasts.py`.
