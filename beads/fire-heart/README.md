# Fire-Heart NFC charm

A black traditional heart with chunky red→orange flame wings — a multi-color,
two-half snap-fit NTAG215 charm.

![preview](../../tmp/screenshots/fire-heart_proud.png)

## Source

- **Image:** `beads/fire-heart/black-heart.png` (512×512 raster: a black heart
  with warm flame wings on a white background).
- Extracted with `extract_fireheart.py` (not the generic `image-to-silhouette`
  skill — this charm needs region separation by color, which that skill doesn't
  do).

## Why this charm exists

Pipeline stress-test for a **through-color multi-region** charm. Every prior
multi-color charm (filibertos-taco, redaphid-portrait) puts color on the show
face as raised relief over a single-color body. Fire-heart instead makes the
color regions *full-thickness* parts of the body: the heart and each flame band
are their own solid sub-mesh, sliced from the halves by vertical prisms. This
exercises a path the recipe didn't have and surfaces what generalizes.

## Key creative decisions & tradeoffs

| Decision | Why | Cost |
|---|---|---|
| **Through-color, not relief** | Flames are colored on *both* faces and full depth, not a thin skin on a black body. | A custom build (6 sub-meshes) + a custom 3MF bundle; diverges from `build_charm.py.example`. |
| **Chunky, thickened flames** | Thin source flame tongues (~0.7 mm) would snap; dilate+close fattens every tongue to ≥~1.5 mm. | Loses some fine flame filigree; wings read bolder/rounder than the source. |
| **Red base → orange tips by distance-from-heart** | Reads as real fire (deep at the base, bright at the tips) regardless of the source's interleaved highlights. | Two extra filament regions; `SPLIT_DIST_MM` is tuned to this heart's proportions. |
| **Synthetic parametric heart, not the detected blob** | Source flames overlap the heart's lobes, so the detected dark blob has non-round lobes. A fitted parametric heart guarantees clean round lobes + cleft + point. | Heart shape is idealized, not a literal trace; `HEART_FATTEN` set so lobes occlude the fire. |
| **Cleft cusp locally rounded** | The parametric cleft is a sharp downward cusp that reads as a vertical clip where the lobes meet. Blend-smoothed *only* near t=0. | None meaningful — bottom point stays sharp. |
| **Heart stands proud 1 mm of the flames on the show face** | The heart must read as *in front of* the wings (source art layering); also visually separates the round lobes from the adjacent flame. | Show face is stepped; the back face stays flat (it's the print bed — stepping it would cantilever the wings). |
| **28 mm wide (vs 25 mm default)** | The flames eat width; 28 mm keeps the heart wide enough to host the 10.5 mm NFC pocket with margin. | Slightly larger than a stock Kandi bead. |
| **String hole at y=+0.5 (low/central)** | The heart cleft caps solid material at y≈+3.3 at center; a higher hole has <1.5 mm wall above. | Hangs from near the vertical center; flames splay up like wings (intended). |

## What's transferable vs. specific

- **Transferable:** the through-color split via vertical prisms
  (`build_prism` + INTERSECT/DIFFERENCE complement so color seams have no gaps);
  `drop_nm_slivers` for boolean chips on fragmented region meshes; the
  chroma→region extraction with flame thickening; recess-before-split so the
  proud-layer cut runs on one connected mesh.
- **Specific to this charm:** all geometry constants (NFC/peg/hole positions
  are tuned to the heart's cleft constraint), `HEART_FATTEN`, `SPLIT_DIST_MM`,
  `FLAME_DILATE_PX`, the parametric-heart substitution, and the 1 mm proud step.

## Files

| File | What |
|---|---|
| `black-heart.png` | Source raster. |
| `extract_fireheart.py` | Chroma region extraction → `silhouette.svg` + `regions.json`. |
| `silhouette.svg` | Outer outline (heart + thickened flames), shared mm frame. |
| `regions.json` | `heart` / `flames_red` / `flames_orange` polygons (mm, origin = bbox center). |
| `extract_debug.png` | Segmentation overlay (blue heart / red / orange). |
| `build_fire_heart.py` | Through-color two-half build. Edit the CONFIG block. |
| `print/fire-heart_charm.blend` | Last good live build (6 parts). |
| `print/` | Exported STLs + 3MF (after `bead-stl-export` / bundle). |

## Dimensions

28.0 × 26.0 × 5.0 mm. NFC pocket 10.5 mm ⌀ × 0.8 mm. 3 pegs (2 mm). String
hole 2 mm. All 6 parts manifold (0 non-manifold edges). NFC 16/16 perimeter
inside, pegs clear, string hole verified open.
