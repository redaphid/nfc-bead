# Redaphid Portrait Medallion

A 20 mm round NFC bead with the **redaphid portrait** as a raised relief on the
top face — the medallion variant of `beads/redaphid-portrait`, built on the
gymnast-medallion "new design" (procedural round base, thin asymmetric halves,
single-half string hole, chamfered snap-fit pegs).

## Source

- Silhouette: `beads/redaphid-portrait/silhouette.svg` (outline `<path>` + two
  eye `<circle>`s), copied here and parsed by `parse_silhouette.py` →
  `figure.json` (Y-up mm polygon + eyes).
- That silhouette was originally image-derived from
  `C:\Users\hypnodroid\Pictures\Screenshots\Screenshot 2026-04-25 235837.png`
  via `beads/redaphid-portrait/extract_silhouette.py`.

## Why this exists

The user asked for "a variant of the redaphid-portrait bead that has this new
design" — i.e. the portrait rendered as a round medallion using everything
learned on `gymnast-medallion` and backported to the recipe (gotchas #29–#32).

## Design (the "new design" spec)

| Feature | Value | Notes |
|---|---|---|
| Base | 20 mm circle, **procedural cylinder** (160 verts) | recipe gotcha #32 |
| Thickness | **1.5 mm bottom + 2.0 mm top + 0.5 relief = 4.0 mm** | asymmetric; thin back, thicker figure half (gotcha #31) |
| Relief | portrait outline, 0.5 mm proud, mass-centered, scaled to fit radius 9 | figure-as-relief medallion (gotcha #32) |
| Eyes | 2 discs **cut through** the relief | the Top show face (body color) reads through → 2-color portrait |
| String hole | 1.2 mm, X axis, Y=+7, in the **thick Top** half | single-half hole (gotcha #23/#31), ~0.4 mm walls |
| NFC pocket | 10.5 mm × 0.8 mm, centered, bottom inner face | NTAG215 |
| Pegs | 3 × 2.6 mm × 1.2 mm, 0.05 mm clearance, **chamfered tips** | snap-fit + self-start (gotchas #29/#30) |

## Files

| File | What |
|---|---|
| `silhouette.svg` | portrait outline + eyes (from redaphid-portrait) |
| `parse_silhouette.py` | SVG → `figure.json` (polygon + eyes, Y-up mm) |
| `figure.json` | parsed portrait geometry the build consumes |
| `build_redaphid_medallion.py` | headless Blender build → 3 STLs + blend + preview |
| `print/Bottom.stl` `print/Top.stl` `print/Decoration.stl` | printable parts |
| `print/redaphid_medallion.3mf` | slicer bundle (Bottom + Top+Decoration merged) |
| `preview.png` | print-layout render |

## Rebuild

```sh
uv run python beads/redaphid-medallion/parse_silhouette.py
"D:\tools\blender\blender.exe" --background --python beads/redaphid-medallion/build_redaphid_medallion.py
uv run nfc-make-3mf --dir beads/redaphid-medallion/print --out beads/redaphid-medallion/print/redaphid_medallion.3mf
```

## Multi-color print (Elegoo Slicer)

1. Import `redaphid_medallion.3mf` — Top + Decoration come in as one object with the portrait as a part.
2. Assign: body (Bottom, Top) → first filament; portrait part → second filament. The eyes are the body color showing through the relief.
3. PLA/PETG, 0.12–0.16 mm layers, 100% infill, no supports. Both halves print flat.

## Print notes / watch

- Thin spots from the new design: the 0.4 mm walls above/below the 1.2 mm string hole, and under the figure at y=7 — bridge fine on a tuned printer; bump the Top toward 2.2–2.5 mm if they sag.
- The pegs grip at 0.05 mm clearance (firm); the 0.35 mm tip chamfer lets them self-start so they don't need forcing.
