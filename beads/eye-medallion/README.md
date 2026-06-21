# Eye Medallion — round NFC bead with a concentric-circle eye

A 20 mm round NFC bead (full gymnast-medallion machinery) with a **classic eye
built from concentric circles** raised as relief on the top face — the eye plays
the role of the rezz spiral / the gymnast figure. Multi-color: white body
(doubles as the sclera), black eye-outline ring, blue iris, black pupil.

## Source

- **Fully procedural** — no image / SVG. The round base is a Blender cylinder and
  the eye is concentric rings generated in `build_eye_medallion.py` (outer/inner
  cylinders booleaned into annuli). Nothing to re-extract.

## Why this charm exists

A sibling of `gymnast-medallion`: the user wanted "the same general
characteristics — bead hole, width, NFC depression, etc. — but a simple eye,
just a few concentric circles" instead of the handstand figure. It's the first
medallion whose relief is **fully procedural geometry** (vs a figure traced from
an image) and the first to carry **multiple color regions** on the show face.

## Design

| Feature | Value | Notes |
|---|---|---|
| Diameter | 20 mm | same as gymnast-medallion; ~1 mm white rim outside the eye. |
| Thickness | **asymmetric: 1.5 mm bottom + 2.0 mm top + 0.5 mm relief = 4.0 mm** | thin back/NFC half (Bottom), thick eye/socket half (Top). Same split as gymnast-medallion (recipe gotcha #31). |
| String hole | 1.2 mm dia, X axis, Y = +7 | in the **Top** (thick) half, centered in its 2.0 mm (walls ~0.4 mm, bridged). Verified OPEN by side raycast. |
| NFC pocket | 10.5 mm dia × 0.8 mm, centered (0,0) | NTAG215, on the bottom inner face; 0.7 mm floor under it in the 1.5 mm half. |
| Pegs | 3 × **2.6 mm** dia × 1.2 mm at radius 7.5, **0.05 mm** clearance, **chamfered tips** | (−7.5,0)(7.5,0)(0,−7.5); 0.95 mm to NFC edge, 1.2 mm to rim. Same snap-fit as gymnast-medallion (gotchas #29/#30). |
| Eye relief | 0.5 mm proud, fit radius 9 | three rings, **no XY overlap** so all sit at the same relief height (gotcha #27 never applies). |

### Eye geometry (radii from center, mm)

| Region | Inner r | Outer r | Color | Object |
|---|---|---|---|---|
| Eye outline | 7.8 | 9.0 | black | `DecorationOutline` |
| Sclera | 5.0 | 7.8 | white | *(flat body face — no object)* |
| Iris | 2.2 | 5.0 | blue | `DecorationIris` |
| Pupil | 0.0 | 2.2 | black | `DecorationPupil` |

3 filaments: white (body + sclera), black (outline + pupil — assign both to one
filament), blue (iris).

## Key decisions / tradeoffs

| Decision | Why / cost |
|---|---|
| Procedural rings (annuli via boolean), not an SVG/figure | Concentric circles are exact geometry; an outer cylinder minus an inner cylinder is cleaner and parameter-driven. No `extract_*.py`, no `figure.json`. |
| White body doubles as the sclera | Skips a fourth decoration object — the flat white show face between the outline ring and the iris *is* the sclera. Cost: the sclera is flush (not raised), giving a subtle domed-iris step (fine, even attractive). |
| Rings don't overlap in XY | All three sit at the same relief Z (0.5 mm), so gotcha #27's z-step ambiguity never applies — no need for a 0.2 mm stack. Simpler and uses less plastic than stacked discs. |
| Reused gymnast-medallion machinery verbatim | Diameter, asymmetric halves, peg geometry, hole placement, NFC pocket all proven on a printed bead — only the decoration changed. |
| Multi-color via per-region `Decoration*.stl` + `bundle_3mf.py` | `nfc-make-3mf` only knows one `Decoration.stl` slot. The eye needs 3 regions as separate components so the slicer can assign a filament per part (recipe gotcha #28). `bundle_3mf.py` is the generic discoverer copied from `filibertos-taco`. |

## What's transferable / specific

- **Transferable**: building a multi-color medallion as N concentric `Decoration*`
  annuli (white body = background) generalizes to any target/ring/badge charm.
  The `_ring_mesh()` helper (outer cyl − inner cyl) is reusable.
- **Specific**: 20 mm diameter, peg radius 7.5, HOLE_Y=7, and the four eye radii
  are tuned to this size.

## Files

| File | What |
|---|---|
| `build_eye_medallion.py` | Headless / live Blender build → 5 STLs + blend + preview |
| `bundle_3mf.py` | Discovers `Bottom`/`Top`/`Decoration*.stl` → multi-color 3MF (gotcha #28) |
| `print/Bottom.stl` | White — bottom half, NFC pocket + pegs, print circle-face-down (pegs up) |
| `print/Top.stl` | White — top half, peg-hole sockets, print inner-face-down (eye up) |
| `print/DecorationOutline.stl` | Black — raised eye-outline ring |
| `print/DecorationIris.stl` | Blue — raised iris annulus |
| `print/DecorationPupil.stl` | Black — raised pupil disc |
| `print/eye_medallion.3mf` | Slicer bundle: Bottom + (Top + 3 decorations as one object with parts) |
| `preview.png` | Print-layout render |
| `eye_top.png` | Top-down render of the eye |

## Rebuild

```sh
"D:\tools\blender\blender.exe" --background --python beads/eye-medallion/build_eye_medallion.py
uv run python beads/eye-medallion/bundle_3mf.py \
    --dir beads/eye-medallion/print --out beads/eye-medallion/print/eye_medallion.3mf
```

## Multi-color print (Elegoo Slicer)

1. Import `eye_medallion.3mf` — Top + the 3 decorations come in as one object with parts.
2. Assign filaments: body (Bottom, Top) → white; `DecorationIris` → blue;
   `DecorationOutline` + `DecorationPupil` → black.
3. PLA/PETG, 0.12–0.16 mm layers, 100% infill, no supports. Both halves print flat.
