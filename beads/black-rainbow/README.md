# black-rainbow — goth rainbow NFC charm

A two-half snap-fit NFC bead built from a stylized image: a 3-band rainbow arch
(red / yellow / blue) bridged with black thorny "wings" sprouting from each end.

**First charm in this repo where the silhouette had a HOLLOW under-arch** —
the literal outline can't host a 10.5 mm NFC pocket. Solved by convex-hull-
bridging the under-arch into a closed body and treating the rainbow + wings as
multi-color FLUSH inlay decorations on a white show-face base.

## Source

`beads/black-rainbow/black-rainbow.png` — a 1024 × 768 PNG of a 7-band ROYGBIV
rainbow with black bat-wing thorn shapes on each end, hollow under-arch on a
white background. Provided by the user.

Collapsed to a 3-band rainbow per user request (cleaner print, fewer filament
swaps). The cleaned reference is `simplified_rainbow_1024.png` — a 1024 × 1024
transparent canvas with the rainbow centered, the cleaned source that the build
pipeline actually consumes.

## Why this charm exists

To exercise the multi-color FLUSH inlay pipeline with a silhouette that REQUIRES
under-arch closure. Earlier charms (Wooli, Rezz, filibertos-taco, redaphid-
portrait) all had naturally-closed silhouettes — their outlines could host the
NFC pocket directly. This one is the first where the silhouette must be
RECONSTRUCTED before it can be a bead body.

The pipeline that came out of this iteration:

1. **`extract_regions.py`** — direct pure-color matching (no HSV / radial
   binning) since the cleaned source has discrete pure colors. Builds the
   filled silhouette as `figure_mask ∪ convex_hull(figure_mask)` — the convex
   hull bridges the under-arch, the figure union recovers thorn detail the
   hull would otherwise straight-line away.
2. **Polygon-manifest pipeline** (regions.json) — no SVG round-trip. The
   build script consumes the manifest directly via `bmesh.from_pydata` so
   every region shares the silhouette's coordinate frame (gotcha #25 — no
   per-SVG bbox auto-fit drift).
3. **Multi-color FLUSH inlay** — 4 decorations (rainbow_outer, _mid, _inner,
   wings) sit in sockets carved out of Top so the show face is smooth. Wings
   are the topmost layer so they cover the rainbow at the natural wing/arch
   overlap.

## Key creative decisions (and tradeoffs)

| Decision | Why | Cost |
|---|---|---|
| Fill the under-arch via convex hull | A 25 mm bead can't host a 10.5 mm NFC pocket if the literal outline is preserved (rainbow arc + thin wings = no body) | Bead loses the see-through-arch aesthetic; the front is a solid filled shape with the rainbow + wings as raised colored regions |
| Collapse 7 bands → 3 bands (R/Y/B) | Fewer filament swaps, simpler slicer, easier to assign colors | Loses ROYGBIV fidelity — the print is a triadic primary palette, not a full spectrum |
| WHITE show-face base, BLACK back | User-specified: white background "lifts" the rainbow visually, black back hides the NFC pocket | 5 filaments total (W + R + Y + B + K) — more swaps than a standard 3-color charm |
| Wings on top of rainbow (highest deco layer) | Wings naturally overlap the bottom of the rainbow in the source image; FLUSH overlap-resolution subtracts lower layers from higher | Rainbow stripes get a notch cut out where wings overlap — visible as a tiny "bite" but matches the source |
| 2 pegs, not the recipe's 3 | The wide-and-short geometry (25×16) plus the central NFC pocket (10.5 dia at y=-2.7) plus all 4 decorations covering most of the show face leaves no clean spot for a triangulated 3rd peg | Slight torsional play around the peg axis (y=-5); friction-fit should compensate. Documented in PRINT_LOG.md as the first thing to watch |
| String hole at y=+5.5 (inside the rainbow band area) | The arch peak is at y=+8 with only 0.4 mm of silhouette above the rainbow outer band — nowhere near the recipe's 2.5 mm wall rule. Inside the rainbow band, the bead body is thick (5 mm + 0.4 mm decoration) so the hole tunnels through plenty of material laterally | Only 1.6 mm of silhouette material above the hole — below the safety rule. The bead may snap off the bracelet under heavy load; print log will track failures |
| `HOLE_Z_OFFSET = -1.25` (hole entirely in Bottom) | Keeps Top's inner face solid at y=HOLE_Y so the rainbow_mid + rainbow_outer FLUSH sockets aren't interrupted by an open half-tube | The hole is a closed tube inside Bottom — slicer must bridge top + bottom of the tube. With 5 mm thickness and Bottom 2.5 mm, the tube has ~0.5 mm wall above + below — printable but tight |
| Wings + rainbow as same-Z FLUSH inlay, not stacked relief | The source is a flat-color illustration, not a 3D scene with depth | Loses any "raised wing" tactile depth — the bead is a smooth flat puck with painted regions |

## What's transferable to future charms

- **The `figure ∪ convex_hull` silhouette-closing pattern** generalizes to any
  charm whose source has an open / non-convex outer boundary (animal silhouettes
  with legs apart, letterforms with holes, instruments with thin arms). When the
  literal outline can't host the NFC pocket, close it via the hull.
- **The polygon-manifest pipeline** (regions.json + `polygons_to_mesh`) is the
  preferred handoff for multi-region charms — see filibertos-taco for the
  reference and this charm for the second example. Avoid per-SVG import unless
  you have a single-region source.
- **Direct pure-color matching** in `extract_regions.py` works when the source
  image has been pre-quantized to discrete colors (this case). For continuous
  / antialiased sources, fall back to k-means clustering (filibertos-taco
  reference) or hue-radial binning.

## What's specific to this charm

- The peg positions `[(-7, -5), (+7, -5)]` are tuned to THIS silhouette's
  under-arch corners. Different silhouettes with different under-arch
  geometry will need different positions.
- The HOLE_Y compromise (1.6 mm wall above) is THIS charm's structural
  reality, not a recipe default. Don't cargo-cult it.
- DECO_ORDER (`rainbow_outer → rainbow_mid → rainbow_inner → wings`) is
  THIS charm's visual stacking. Other multi-color charms have different
  natural orderings.

## Files

- `black-rainbow.png` — the original raster source the user provided
- `simplified_rainbow.png` — solid-white-bg preview of the 3-band charm
  (delivered to the user as a parallel asset)
- `simplified_rainbow_transparent.png` — same, transparent bg
- `simplified_rainbow_1024.png` — 1024×1024 transparent, centered. **The
  pipeline source.** Re-derive the regions if this file changes.
- `extract_regions.py` — PNG → regions.json + preview PNGs
- `extract_debug.png` — debug overlay showing detected masks
- `regions.json` — polygon manifest in shared mm coordinates
- `build_black_rainbow.py` — regions.json → Blender → STLs
- `bundle_3mf.py` — STLs → multi-decoration 3MF (ComponentsObject pattern)
- `print/` — exported STLs + `black-rainbow.3mf` (drag into Bambu Studio /
  Elegoo Slicer)
- `print/black-rainbow_charm.blend` — working scene snapshot (refreshed
  on every successful build)
- `README.md` — this file
- `PRINT_LOG.md` — append-only log of physical print attempts
