# Gymnast Medallion — round NFC bead with a raised handstand gymnast

A 20 mm round NFC bead (full rezz-style machinery) with the one-arm-handstand
gymnast as a **raised relief** on the top face — the gymnast plays the role of
the rezz spiral. Multi-color: red body, black figure.

## Source

- Figure image: `D:\Projects\paper-cranes\public\images\handstand.png` (single
  black silhouette on white). Extracted by `extract_figure.py`.
- The round base is **procedural** (a Blender cylinder), not an SVG.

## Why this charm exists

The user wanted the gymnast printed *onto a circle like the rezz spiral bead* —
i.e. the full two-half NFC bead with the figure as the raised top decoration,
rather than the flat standalone silhouette charms on the `gymnasts` branch. It's
the first charm to use a **figure silhouette as the raised relief** (vs the
procedural rezz spiral) and the first to build the round base as a cylinder
primitive instead of importing a circle SVG.

## Design

| Feature | Value | Notes |
|---|---|---|
| Diameter | 20 mm | ~30% under 25 mm; floor is ~17 mm (NTAG215 pocket + pegs + walls). Rim wall ~2 mm. |
| Thickness | 5.0 mm + 0.5 mm relief | 2.5 mm bottom + 2.5 mm top + 0.5 mm raised figure = 5.5 mm total |
| String hole | 2 mm dia, X axis, Y = +7 | Entirely in the **Bottom** half (HOLE_Z_OFFSET = −1.25), filibertos-taco model. No seam groove; Top stays solid under the figure; Bottom's first print layer (back face) is solid. Tube walls 0.25 mm top/bottom (verified open by ray cast). |
| NFC pocket | 10.5 mm dia × 0.8 mm, centered (0,0) | NTAG215, on the bottom inner face; clear of the y=7 hole (pocket reaches y=5.25). |
| Pegs | 3 × **2.6 mm** dia × 1.5 mm at radius 7.5, **0.05 mm** clearance | (−7.5,0)(7.5,0)(0,−7.5); 0.95 mm to NFC edge, 1.2 mm to rim, 0/8 perimeter clip. Snap-fit tuning from redaphid-portrait v5/v6 (gotcha #30) — 2.0 mm/0.1 mm was too narrow + loose to grip. |
| Figure relief | 0.5 mm proud, scaled to fit radius 9 | Whole figure fits inside the circle (no clipped limbs); lifted 0.01 mm to avoid Z-fight |

## Key decisions / tradeoffs

| Decision | Why / cost |
|---|---|
| Procedural cylinder base | A circle doesn't need an SVG; a 160-vertex cylinder is cleaner and exact. |
| Figure scaled to *fit radius 9*, not "longest side" | The handstand sprawls (extended leg); scaling by max radial extent guarantees the whole figure sits inside the circle so no limb is clipped at the rim. Cost: the compact body ends up ~14 mm across — smaller than the bead, with a margin ring. |
| Relief is a plain extruded polygon | The figure is a filled shape (not a tube), so the rezz "flat ribbon" workaround (gotcha #9) isn't needed — a simple ngon extrude is manifold. Thin limbs are fine here: they sit on the solid top face, unlike the standalone charms. |
| No decoration crop boolean | The figure is fully inside radius 9 < the 10 mm circle, so cropping (gotcha #26) is unnecessary — skipped to avoid fragmenting thin limbs. |
| String hole in one half (Bottom), not the split plane | The **filibertos-taco model** (recipe gotcha #23). v1 put the hole on the seam → half-groove on each inner face. Moving it fully into the Bottom keeps the seam clean, the decorated Top solid, and gives Bottom a solid first layer. Cost: 0.25 mm tube walls top/bottom (printable; bump THICKNESS if it fails). |
| Snap-fit pegs: 2.6 mm dia, 0.05 mm clearance | v1 used the recipe-default 2.0 mm / 0.1 mm and **the pegs didn't grip** ("didn't fit together"). redaphid-portrait v5/v6 (adopted by filibertos) proved 2.6 mm + 0.05 mm radial clearance is the actual snap-fit on the Centauri Carbon 2 (gotcha #30). |

## What's transferable / specific

- **Transferable**: building the round base as a cylinder + using any centered
  mm figure polygon as a raised relief (scale-to-fit-radius, extrude, place on
  show face) generalizes to any "figure on a medallion" charm.
- **Specific**: 20 mm diameter, peg radius 7.5, HOLE_Y=7 are tuned to this size.

## Files

| File | What |
|---|---|
| `extract_figure.py` | handstand.png → `figure.json` (+ `figure_debug.png`) |
| `figure.json` | Centered mm polygon of the gymnast |
| `build_gymnast_medallion.py` | Headless Blender build → 3 STLs + blend + preview |
| `print/Bottom.stl` | Red — bottom half, NFC pocket + pegs, print circle-face-down (pegs up) |
| `print/Top.stl` | Red — top half, peg-hole sockets, print inner-face-down (figure up) |
| `print/Decoration.stl` | Black — the raised gymnast, aligned in Top's frame |
| `print/gymnast_medallion.3mf` | Slicer bundle: Bottom + (Top+Decoration merged as one object) |
| `preview.png` | Print-layout render |

## Rebuild

```sh
uv run python beads/gymnast-medallion/extract_figure.py
"D:\tools\blender\blender.exe" --background --python beads/gymnast-medallion/build_gymnast_medallion.py
uv run nfc-make-3mf --dir beads/gymnast-medallion/print --out beads/gymnast-medallion/print/gymnast_medallion.3mf
```

## Multi-color print (Elegoo Slicer)

1. Import `gymnast_medallion.3mf` — Top + Decoration come in as one object with the figure as a part.
2. Assign: body (Bottom, Top) → first filament; the figure part → second filament.
3. PLA/PETG, 0.12–0.16 mm layers, 100% infill, no supports. Both halves print flat.
