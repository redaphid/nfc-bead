# Filiberto's Taco

A two-half NFC charm shaped like a cartoon taco — yellow shell, green lettuce, red outline — built as a multi-color print on the Centauri Carbon 2.

## Source

- `just-taco.jpg` — the reference cartoon taco art (yellow shell + green lettuce + red outline on white background).
- `silhouette.svg` — outer body silhouette extracted from the JPEG via custom multi-color extraction (Pillow + numpy + scipy + skimage). Single Fourier-smoothed closed path, 400 verts.
- `region_yellow.svg`, `region_green.svg`, `region_red.svg` — color-segmented decoration regions in the same coordinate frame as `silhouette.svg`.
- `extract_debug.png` — segmentation overlay (blue=outer, red=outline, yellow=shell, green=lettuce). Sanity-check before importing.

The original `taco.svg` Potrace tracing was discarded — it was a B&W line-art trace, not a filled silhouette, and produced a hollow body with even-odd fill. The JPEG-based extraction yields a clean filled outer outline plus three color regions.

## Why this charm exists

Exercises the multi-color decoration pattern: rather than a single `Decoration` object, the show face hosts three overlapping color regions (yellow shell base, green lettuce on top, red outline detail) extruded as raised relief. Slicer assigns one filament per region.

It also stress-tests the SVG → silhouette pipeline against a *bitmap* input — Potrace traces of pen-and-ink illustrations don't make clean filled silhouettes; you need a color-aware mask of the colored regions. That extraction lives at the top of `build_filibertos_taco.py` documentation, not as a generalized skill (yet).

## Key creative decisions

| Decision | Cost |
|---|---|
| Multi-color decoration as 3 separate STLs (Yellow / Green / Red) | More slicer setup; user assigns filaments per object. Simpler than paint-on-color in Bambu Studio / Elegoo Slicer. |
| Show face raised relief (0.4 mm) instead of recessed groove | Bumpy show face but reliable bridge-free print; recess would need the slicer to color-paint the same Top STL. |
| String hole tube entirely inside Top half (`HOLE_Z_OFFSET=1.25`) | First-layer adhesion is solid silhouette across the seam; tube becomes a small interior cavity bridged twice (~0.5 mm wall above and below). Recipe gotcha #23. |
| Bottom in print orientation already at end of build (centered-mesh pipeline) | Sets `nfc_export_flip_override` so `bead-stl-export` doesn't apply its default 180° flip. Recipe gotcha #16. |
| 3 pegs (not 4) at `(7.5,-6.0)`, `(-9.5,0.0)`, `(7.5,2.5)` | Triangulated; auto-fit found ≥1mm clearance from NFC and silhouette boundary, ≥1mm from string-hole tube. |
| Concatenate the 3 color STLs into a unified `Decoration.stl` for the 3MF builder | Lets `nfc-make-3mf` ship a slicer-ready bundle. Per-color STLs remain separate in `print/` for users with multi-filament setups who want explicit per-region color control. |

## What's transferable / what's specific

**Transferable** (could become recipe defaults):
- `nfc_export_flip_override` discipline for centered-mesh build pipelines — already in recipe gotcha #16.
- Multi-color decoration as raised relief at `top_z + ε` rather than recessed cuts.
- Cropping decorations to silhouette via boolean INTERSECT with a duplicate-extruded Top.

**Specific** (tuned to this taco):
- Custom extraction script at the top of `build_filibertos_taco.py`'s sibling files. It assumes a white-background cartoon with red/yellow/green color clusters. Other illustrations will need per-charm tuning of the channel-discriminator thresholds.
- 25 mm × 17 mm bounding box with NFC at `(0, 0.5)` and `HOLE_Y=5.0` — auto-fit picked these for this silhouette's specific shape.

## Files

| File | What it is |
|---|---|
| `just-taco.jpg` | source reference image |
| `silhouette.svg` | outer body silhouette (used by `build_filibertos_taco.py`) |
| `region_yellow.svg` / `region_green.svg` / `region_red.svg` | color region inputs |
| `extract_debug.png` | extraction sanity overlay |
| `build_filibertos_taco.py` | Blender pipeline — extrude → split → NFC + hole + pegs → 3 decoration extrudes |
| `print/Bottom.stl` | back half — silhouette face on bed, pegs up |
| `print/Top.stl` | front half — peg sockets in inner face, show face up |
| `print/DecorationYellow.stl` / `DecorationGreen.stl` / `DecorationRed.stl` | per-color decoration regions, 0.4 mm raised relief on Top |
| `print/Decoration.stl` | concatenation of the 3 color STLs (used by `nfc-make-3mf`) |
| `print/filibertos-taco.3mf` | Bambu Studio / Elegoo Slicer bundle (Bottom + Top with Decoration assembly) |
| `print/filibertos-taco_charm.blend` | live Blender scene at end of build — re-launch via `tools/launch.ps1 -Bead filibertos-taco` |
| `stages/01_built_verified.blend` | snapshot at the post-build verification step |
| `PRINT_LOG.md` | per-print iteration log (failure modes + parameter changes) |

## Two style variants

Build script `build_filibertos_taco.py` switches between two looks by
reading `STYLE` (env var `FILIBERTOS_TACO_STYLE`, scene custom prop
`nfc_taco_style`, default `"painted"`):

| Style | Decoration source | Output |
|---|---|---|
| `painted` (default) | `region_*.svg` (filled color regions, k-means extraction) | `print/` — 4-filament cartoon look |
| `neon` | `stroke_*.svg` (line strokes, dilate-XOR extraction) | `print/neon/` — 2-3-filament neon-sign look on a black body |

Switch in Blender:
```python
bpy.context.scene["nfc_taco_style"] = "neon"
exec(open(r"...build_filibertos_taco.py").read(), {"__name__":"__main__"})
```

Re-extract decoration sources independently:
```sh
uv run python beads/filibertos-taco/extract_regions.py   # k-means → region_*.svg
uv run python beads/filibertos-taco/extract_strokes.py   # dilate-XOR → stroke_*.svg
```

## Re-build / re-export

```sh
# from a fresh shell, in the repo root:
.\tools\launch.ps1 -Bead filibertos-taco
# in Claude Code:
/mcp                       # reconnect bridge
# Then in conversation:
exec(open(r"D:\Projects\nfc-bead\beads\filibertos-taco\build_filibertos_taco.py").read(), {"__name__": "__main__"})
```

The build sets `nfc_export_flip_override` automatically. After it completes:

```sh
# back in the host shell:
uv run python -c "import trimesh; from pathlib import Path; LAT=Path('tmp/latest'); parts=[trimesh.load(LAT/n) for n in ('DecorationYellow.stl','DecorationGreen.stl','DecorationRed.stl')]; trimesh.util.concatenate(parts).export(LAT/'Decoration.stl')"
uv run nfc-printability-check
uv run nfc-make-3mf
```
