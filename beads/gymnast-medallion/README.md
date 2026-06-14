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
| Thickness | **asymmetric: 1.5 mm bottom + 2.0 mm top + 0.5 mm relief = 4.0 mm** | Slimmed from 5.5 mm. Back/NFC half (Bottom) is the thin one; the figure/socket half (Top) stays thicker so pegs keep length + grip. |
| String hole | 1.2 mm dia, X axis, Y = +7 | Now in the **Top** (thick) half, centered in its 2.0 mm (walls ~0.4 mm, bridged). Moved here because thinning the Bottom left it too thin to host a hole. Verified open by ray cast (void z 0.4–1.6). |
| NFC pocket | 10.5 mm dia × 0.8 mm, centered (0,0) | NTAG215, on the bottom inner face; 0.7 mm floor under the pocket in the 1.5 mm half. |
| Pegs | 3 × **2.6 mm** dia × 1.2 mm at radius 7.5, **0.05 mm** clearance, **chamfered tips** | (−7.5,0)(7.5,0)(0,−7.5); 0.95 mm to NFC edge. 2.6 mm/0.05 mm grips firmly (held when forced); a 0.35 mm tip chamfer (shaft 1.30 → tip 1.10 mm radius) lets each peg self-start into the socket instead of catching and needing force. |
| Figure relief | 0.5 mm proud, scaled to fit radius 9 | Whole figure fits inside the circle (no clipped limbs); lifted 0.01 mm to avoid Z-fight |

## Key decisions / tradeoffs

| Decision | Why / cost |
|---|---|
| Procedural cylinder base | A circle doesn't need an SVG; a 160-vertex cylinder is cleaner and exact. |
| Figure scaled to *fit radius 9*, not "longest side" | The handstand sprawls (extended leg); scaling by max radial extent guarantees the whole figure sits inside the circle so no limb is clipped at the rim. Cost: the compact body ends up ~14 mm across — smaller than the bead, with a margin ring. |
| Relief is a plain extruded polygon | The figure is a filled shape (not a tube), so the rezz "flat ribbon" workaround (gotcha #9) isn't needed — a simple ngon extrude is manifold. Thin limbs are fine here: they sit on the solid top face, unlike the standalone charms. |
| No decoration crop boolean | The figure is fully inside radius 9 < the 10 mm circle, so cropping (gotcha #26) is unnecessary — skipped to avoid fragmenting thin limbs. |
| Asymmetric halves (thin Bottom, thick Top) | User wanted it slimmer "but mostly the back". The Top must stay thick — it hosts the peg sockets (so pegs keep length/grip) and now the string hole. The Bottom only holds the shallow NFC pocket + peg bases, so it drops to 1.5 mm. The seam is off-center (z = −0.25 on a 3.5 mm body). |
| String hole in the THICK (Top) half | filibertos-taco single-half model (gotcha #23) — no seam groove. v2 had it in the Bottom, but thinning the Bottom to 1.5 mm left no room for a hole, so it moved to the 2.0 mm Top. Shrunk to 1.2 mm (Kandi cord) for ~0.4 mm walls. Cost: a 0.4 mm wall under the figure at y=7 (bridged, printable). |
| Snap-fit pegs: 2.6 mm / 0.05 mm + chamfered tip | The 2.6 mm/0.05 mm grip (gotcha #30) holds firmly — it held once *forced* together. The real problem was ENTRY: blunt peg tips caught on the socket rim. A 0.35 mm tip chamfer fixes self-start without touching the (good) grip diameter. Clearance deliberately NOT loosened. |

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
