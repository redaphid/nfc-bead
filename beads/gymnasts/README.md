# Gymnast beads — 6 acrobat silhouette charms

Six gymnast/acrobat pose silhouettes turned into simple flat extruded charms.
**This is a deliberately simplified branch of the recipe** — no NFC pocket, no
two-half snap-fit, no pegs. Each bead is a single solid extrusion of one
silhouette with a through-thickness string hole where the pose is thick enough
to host one.

## Two hole variants

| Variant | Hole axis | Files | Hangs like |
|---|---|---|---|
| **Face** (default) | Z — through the 2.5 mm flat face, 1.4 mm dia | `print/pose*.stl`, `print/gymnasts.3mf` | a flat pendant facing forward |
| **Thread** | X — horizontal tunnel through the body, 1.5 mm dia | `print_thread/pose*.stl`, `print_thread/gymnasts_thread.3mf` | a bead the cord passes through |

Both share the same silhouettes and dimensions, and the same poses host a hole
(1/4/5/6; slim handstands 2/3 are hole-free in both). Hole *placement* differs by
intent: the **face** hole biases to the upper body so the pendant hangs
right-side-up, while the **thread** hole goes to the *global thickest* point
(most material all around, so the horizontal tunnel has walls above + below and
the bead hangs balanced). For most poses these coincide; on pose6 the thread
hole drops lower into the body. The thread hole (1.5 mm) is sized by
the 2.5 mm thickness, not the silhouette — it leaves ~0.5 mm walls above/below
that the slicer bridges. **The thread cutter is limited to the local solid span
at the hole point** (a short tunnel through one body part), NOT a full-width
slot — a full-width cut shaved thin floating slivers off far parts of arched
poses like pose5. Build either via the `--axis`/`--suffix` args (see Rebuild).
Thread tunnels verified open by raycast (0/40 centerline points inside), all
parts single-body + watertight.

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
| 17.5 mm longest side, 2.5 mm thick | Each figure scaled so its *longest* bbox side = 17.5 mm (~30% smaller than the original 25 mm; poses vary wildly in aspect ratio). Thickness deliberately NOT scaled — 2.5 mm keeps parts sturdy and hole walls printable. |
| Hole scaled with the figure (1.4 mm dia / 0.7 mm wall) | At 0.7× the original 2.0/1.0, so the *same* poses (1/4/5/6) keep a hole — a fixed 2 mm hole would be too large a fraction of the shrunken figure and poses would drop out. |
| Faithful outlines (no limb thickening) | Kept the silhouettes exact. Cost: thin extended limbs/toes (esp. poses 2, 3, 6 feet) are the fragility risk on the print. |
| String hole = thickest interior point, prefer upper body | Auto-placed via distance transform so the hole always lands in load-bearing material. |
| Poses 2 & 3 have **no hole** | The slim vertical handstands lack 1.4 mm-dia + 0.7 mm-wall of material anywhere. Per user ("keep the easy ones") they ship hole-free rather than getting a non-faithful hang tab. |
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
| `build_gymnasts.py` | Headless Blender build: polygon → extrude → drill → STL + preview. `--axis Z\|X`, `--hole-dia`, `--suffix` |
| `regions.json` | shared by both variants |
| `gymnasts.blend` / `gymnasts_thread.blend` | Saved scenes (all 6 on a grid) |
| `preview.png` / `preview_thread.png` | Top-down renders |
| `bundle_3mf.py` | Bundles `pose*.stl` from `--dir` into `--out` 3MF |
| `print/pose1..6.stl` + `print/gymnasts.3mf` | **Face** variant (Z hole) |
| `print_thread/pose1..6.stl` + `print_thread/gymnasts_thread.3mf` | **Thread** variant (X hole) |

## Rebuild

```sh
uv run python beads/gymnasts/extract_gymnasts.py            # image -> regions.json

# Face variant (Z hole through the flat face)
"D:\tools\blender\blender.exe" --background --python beads/gymnasts/build_gymnasts.py
uv run python beads/gymnasts/bundle_3mf.py

# Thread variant (X hole horizontally through the body)
"D:\tools\blender\blender.exe" --background --python beads/gymnasts/build_gymnasts.py -- --axis X --hole-dia 1.5 --suffix _thread
uv run python beads/gymnasts/bundle_3mf.py --dir print_thread --out print_thread/gymnasts_thread.3mf
```

## Print notes

- Single color, PLA/PETG, 0.12–0.16 mm layer height, 100% infill (tiny parts),
  no supports — they print flat on the silhouette face.
- Watch the thin limbs/toes (poses 2, 3, and the pointed feet on 6). If any snap
  off the plate or after printing, scale up in the slicer or thicken in
  `extract_gymnasts.py`.
