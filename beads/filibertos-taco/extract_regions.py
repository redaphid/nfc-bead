"""Extract the taco JPG into N color-region SVGs via k-means clustering.

Outputs:
  beads/filibertos-taco/silhouette.svg          - outer body (single closed path)
  beads/filibertos-taco/region_<name>.svg       - one per useful color cluster
  beads/filibertos-taco/extract_debug.png       - segmentation overlay
  beads/filibertos-taco/region_palette.txt      - palette legend (one per region)

Run:
    uv run python beads/filibertos-taco/extract_regions.py
"""
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
from sklearn.cluster import KMeans
from skimage import measure

SRC = Path('beads/filibertos-taco/just-taco.jpg')
OUT = Path('beads/filibertos-taco')
TARGET_WIDTH_MM = 25.0
N_CLUSTERS = 7
MIN_CLUSTER_PCT = 6
# Lower harmonics + heavier mask blur = smoother taco-logo shape, less stair-step.
# At 25mm bead width / 443px source, FOURIER_HARM=12 gives a logo-like profile;
# 18 keeps the lettuce frill texture; 24 keeps every pixel artifact.
FOURIER_HARM_BODY     = 12   # silhouette.svg outer outline
FOURIER_HARM_REGION   = 14   # interior color regions
SILHOUETTE_BLUR_SIGMA = 2.5  # gaussian on silhouette mask before contour

# Named regions: (name, hex preview color, predicate)
# Each predicate takes (R, G, B) of a cluster center and returns whether
# this cluster belongs to this named region. Multiple clusters can map
# into one region (so light-yellow + bright-yellow → "shell").
REGIONS = [
    ("shell_dark",  "#d68a00", lambda r,g,b: r > 200 and g > 130 and g < 190 and b < 80),    # bright orange-yellow
    ("shell_light", "#fbcf5d", lambda r,g,b: r > 220 and g > 170 and b > 50 and b < 130),    # pale yellow highlight
    ("lettuce_dark","#374806", lambda r,g,b: g > r and g > b and g < 100),                   # deep green shadow
    ("lettuce_light","#5fa520", lambda r,g,b: g > r and g > b and g >= 100),                 # bright green highlight
    ("outline",      "#921209", lambda r,g,b: r > 100 and g < 60 and b < 60),                # red outline
]

# ── Load + foreground mask ───────────────────────────────────────────
img = np.array(Image.open(SRC).convert('RGB'))
H, W, _ = img.shape
R, G, B = img[...,0].astype(np.int16), img[...,1].astype(np.int16), img[...,2].astype(np.int16)
bg = (R > 235) & (G > 235) & (B > 235)
fg = ~bg

# ── K-means on FG pixels ─────────────────────────────────────────────
ys, xs = np.where(fg)
np.random.seed(0)
sample_n = min(50000, len(ys))
sub = np.random.choice(len(ys), sample_n, replace=False)
fg_pixels = img[ys[sub], xs[sub]]
km = KMeans(n_clusters=N_CLUSTERS, n_init=10, random_state=0).fit(fg_pixels)
print(f"Cluster centers (most-to-least populated):")
sizes = [(i, (km.labels_==i).sum()) for i in range(N_CLUSTERS)]
sizes.sort(key=lambda t: -t[1])
useful_clusters = []
for rank, (i, n) in enumerate(sizes):
    pct = 100*n/len(km.labels_)
    c = km.cluster_centers_[i]
    print(f"  c{i}: ({c[0]:3.0f},{c[1]:3.0f},{c[2]:3.0f})  {pct:5.2f}%")
    if pct >= MIN_CLUSTER_PCT:
        useful_clusters.append(i)

# Assign EVERY fg pixel to nearest cluster center
fg_flat = img[ys, xs].astype(np.float32)
centers = km.cluster_centers_.astype(np.float32)
dists = ((fg_flat[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
labels_full = np.argmin(dists, axis=1)
label_grid = -np.ones((H, W), dtype=np.int32)
label_grid[ys, xs] = labels_full

# ── Map clusters to named regions ────────────────────────────────────
cluster_to_region = {}
for ci in useful_clusters:
    c = km.cluster_centers_[ci]
    for region_name, _hex, pred in REGIONS:
        if pred(c[0], c[1], c[2]):
            cluster_to_region[ci] = region_name; break
    if ci not in cluster_to_region:
        # nearest-color fallback
        best, best_d = None, 1e18
        for region_name, hex_col, _pred in REGIONS:
            hr, hg, hb = int(hex_col[1:3],16), int(hex_col[3:5],16), int(hex_col[5:7],16)
            d = (c[0]-hr)**2 + (c[1]-hg)**2 + (c[2]-hb)**2
            if d < best_d: best_d = d; best = region_name
        cluster_to_region[ci] = best
        print(f"  c{ci} ({c[0]:.0f},{c[1]:.0f},{c[2]:.0f}) -> {best} (fallback)")

# Build masks per named region
region_masks = {name: np.zeros((H, W), dtype=bool) for name, _h, _p in REGIONS}
for ci, region_name in cluster_to_region.items():
    region_masks[region_name] |= (label_grid == ci)

# Outer body: union of all FG (cleaner than union-of-regions, fills internal speckle)
def clean(m, close=4, open_=1):
    m = ndimage.binary_closing(m, iterations=close)
    m = ndimage.binary_opening(m, iterations=open_)
    return ndimage.binary_fill_holes(m)
outer = clean(fg, close=4, open_=1)
labeled, n = ndimage.label(outer)
if n > 0:
    sizes2 = ndimage.sum(outer, labeled, range(1, n+1))
    outer = labeled == 1 + int(np.argmax(sizes2))

# Restrict region masks to inside outer
for name in region_masks:
    region_masks[name] = clean(region_masks[name], close=2, open_=1) & outer

# ── Debug overlay ────────────────────────────────────────────────────
overlay = img.astype(np.float32) * 0.4
HEX = {n: tuple(int(h[i:i+2],16) for i in (1,3,5)) for n,h,_ in REGIONS}
for name, hex_col, _ in REGIONS:
    if region_masks[name].sum() == 0: continue
    overlay[region_masks[name]] += np.array(HEX[name], dtype=np.float32) * 0.6
overlay[outer & ~np.any([region_masks[n] for n in region_masks], axis=0)] += np.array((0,80,160), dtype=np.float32) * 0.3
dbg = np.clip(overlay, 0, 255).astype(np.uint8)
Image.fromarray(dbg).save(OUT/'extract_debug.png')

# ── SVG export ───────────────────────────────────────────────────────
def fourier_smooth(contour, harm):
    z = contour[:, 0] + 1j * contour[:, 1]
    Z = np.fft.fft(z)
    msk = np.zeros_like(Z, dtype=bool)
    msk[0] = True; msk[1:harm+1] = True; msk[-harm:] = True
    return np.fft.ifft(np.where(msk, Z, 0))

def downsample(contour, n_target=400):
    if len(contour) <= n_target: return contour
    idx = np.linspace(0, len(contour)-1, n_target).astype(int)
    return contour[idx]

def mask_to_paths(mask, smooth=True, harm=FOURIER_HARM_REGION, min_area=200,
                  pre_blur_sigma=0.0):
    """Trace closed contours of a binary mask, optionally pre-blurring
    and post-Fourier-smoothing. Pre-blur smooths the boundary BEFORE
    contour extraction (rounds stair-step pixel edges)."""
    if pre_blur_sigma > 0:
        mask = ndimage.gaussian_filter(mask.astype(np.float32), sigma=pre_blur_sigma) > 0.5
    labeled, n = ndimage.label(mask)
    paths = []
    for k in range(1, n+1):
        comp = labeled == k
        if comp.sum() < min_area: continue
        contours = measure.find_contours(comp.astype(np.uint8), level=0.5)
        if not contours: continue
        contours.sort(key=lambda c: -len(c))
        c = contours[0]
        c = downsample(c, 400)
        if smooth:
            z = fourier_smooth(c, harm)
            c = np.column_stack((z.real, z.imag))
        paths.append(c)
    return paths

# Outer bbox in pixel coords (for shared mm-coordinate frame)
ys_o, xs_o = np.where(outer)
bx0, bx1 = xs_o.min(), xs_o.max(); by0, by1 = ys_o.min(), ys_o.max()
SCALE_PX_TO_MM = TARGET_WIDTH_MM / (bx1 - bx0)

def write_svg(filename, paths, fill='#000', anchor=True):
    """Write the paths to an SVG, optionally adding 1×1 px invisible corner
    markers at the SILHOUETTE'S bbox corners.

    Why: every SVG share the same viewBox here, but Blender's SVG importer
    uses the PATH bbox (not the viewBox) when computing mesh dimensions.
    Auto-fit-to-target-width then scales each region by its OWN path extent,
    breaking alignment between region SVGs whose path bboxes differ.

    Adding two 1-px black dots at the silhouette bbox corners forces every
    SVG to have the same path bbox (= silhouette's). After Blender import +
    auto-fit, all regions land in the same coordinate frame.

    The dots are 1 viewBox unit = 0.01 mm — invisible in print and clipped
    by the silhouette cropper if they land outside the silhouette curve.
    Pass anchor=False to skip (used only for `silhouette.svg` itself,
    which already defines the bbox)."""
    if not paths: print(f"  (skip {filename} — no paths)"); return False
    global Hmm
    Wmm = TARGET_WIDTH_MM
    Hmm = (by1 - by0) * SCALE_PX_TO_MM
    svg_w = Wmm * 100; svg_h = Hmm * 100
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}">']
    if anchor:
        # Corner markers at the silhouette path bbox corners. These pin
        # every region's bbox to the silhouette's bbox so Blender's
        # auto-fit-to-25mm works consistently across SVGs.
        # Silhouette bbox in source pixels: x=[bx0,bx1], y=[by0,by1]; in
        # SVG units (mm × 100): x=[0, svg_w], y=[0, svg_h] (zero-shifted).
        parts.append(f'<rect x="0" y="0" width="1" height="1" fill="{fill}"/>')
        parts.append(f'<rect x="{svg_w-1}" y="{svg_h-1}" width="1" height="1" fill="{fill}"/>')
    for c in paths:
        ys = c[:, 0]; xs = c[:, 1]
        x_mm = (xs - bx0) * SCALE_PX_TO_MM
        y_mm = (ys - by0) * SCALE_PX_TO_MM
        d = 'M ' + ' L '.join(f'{x*100:.2f},{y*100:.2f}' for x,y in zip(x_mm, y_mm)) + ' Z'
        parts.append(f'<path fill="{fill}" stroke="none" d="{d}"/>')
    parts.append('</svg>')
    open(filename, 'w', encoding='utf-8').write('\n'.join(parts))
    return True

# Outer silhouette: stronger smoothing for a cleaner taco-logo shape.
# anchor=False because the silhouette path itself defines the reference bbox.
write_svg(OUT/'silhouette.svg',
          mask_to_paths(outer, smooth=True, harm=FOURIER_HARM_BODY,
                        min_area=2000, pre_blur_sigma=SILHOUETTE_BLUR_SIGMA),
          '#000', anchor=False)

palette_lines = []
for name, hex_col, _ in REGIONS:
    paths = mask_to_paths(region_masks[name], smooth=True, harm=FOURIER_HARM_REGION, min_area=200)
    if write_svg(OUT/f'region_{name}.svg', paths, hex_col):
        print(f"  region_{name}.svg <- {len(paths)} path(s) ({region_masks[name].sum()} px)")
        palette_lines.append(f"{name}\t{hex_col}\t{region_masks[name].sum()} px")
    else:
        palette_lines.append(f"{name}\t{hex_col}\t(empty)")

# ── Combined block-style regions ────────────────────────────────────
# For STYLE='blocks' in the build pipeline: filling = lettuce_dark + light,
# shell = shell_dark + light. Combined at MASK level (then morph-closed and
# fill-holes) so the resulting SVG is one solid filled region per group —
# no overlapping subpaths, clean boolean topology downstream.
def combine_region(*names, inset_iters=0, trim_bottom_px=0):
    """Combine color region masks: union → close → fill_holes → smooth →
    optional inset → optional bottom-edge-only trim.

    `inset_iters`: erode the result everywhere by N pixels (uniform).
    `trim_bottom_px`: pull ONLY the bottom edge of the region UP by N
        pixels. Preserves left / top / right contours; only the bottom
        contour gets pulled inward. Use this when the filling has a
        "tongue" extending toward the bottom-tip of the silhouette and
        you need the shell to show through there."""
    m = np.zeros_like(outer)
    for n in names:
        m |= region_masks[n]
    m = ndimage.binary_closing(m, iterations=6)
    m = ndimage.binary_fill_holes(m)
    blurred = ndimage.gaussian_filter(m.astype(np.float32), sigma=2.0)
    m = (blurred > 0.5) & outer
    if inset_iters > 0:
        m = ndimage.binary_erosion(m, iterations=inset_iters)
    if trim_bottom_px > 0:
        # Keep pixel (y,x) True only if (y+1,x), (y+2,x), … (y+N,x) are
        # also all True. Equivalent to a "trim from below" morphological
        # erosion that leaves the top edge alone.
        trimmed = m.copy()
        for shift in range(1, trim_bottom_px + 1):
            shifted = np.zeros_like(m)
            shifted[:-shift, :] = m[shift:, :]
            trimmed = trimmed & shifted
        m = trimmed
    return m

# Filling: NO uniform inset + smaller bottom trim.
#
# Source's lettuce takes ~50% of bead vertical area; we want to match.
# Reduced trim_bottom_px 14→8 so filling extends further down toward
# the lettuce-shell boundary as in the source.
combined_filling = combine_region('lettuce_dark', 'lettuce_light',
                                  inset_iters=0, trim_bottom_px=8)
# Shell = full silhouette MINUS the filling. Match the Filibertos logo's
# shell-as-base proportion: in the source, the yellow shell forms the
# entire taco shell shape (the "bun") with green lettuce sitting on top
# of it. Color predicates miss the parts of the shell hidden behind
# lettuce in the source image; reconstruct the full shell by subtracting.
combined_shell = outer & ~combined_filling

# Use raw mask boundary (no Fourier smoothing) for the filling contour
# so the natural quantize-style edge is preserved instead of getting
# the wavy Fourier-smoothed approximation. The mask is already smooth
# from the morph-close + gaussian + binarize chain.
write_svg(OUT/'region_filling.svg', mask_to_paths(combined_filling, smooth=False, min_area=300), '#3ea332')
print(f"  region_filling.svg <- combined ({combined_filling.sum()} px)")
write_svg(OUT/'region_shell.svg',   mask_to_paths(combined_shell,   smooth=False, min_area=300), '#e6c41e')
print(f"  region_shell.svg <- silhouette - filling ({combined_shell.sum()} px)")

# ── Interior detail "stuff in the taco" — strategy v15b ──────────────
# User-selected approach: raw red_inside fragments (no opening), top N
# by size, anywhere in the lettuce. Preserves the natural squiggly vein
# shape; picks the largest visible chunks so they read as decorative
# stuff at 25mm scale instead of getting eroded into dots.
#
# Use the k-means red cluster (NOT the RGB-predicate outline mask) so
# we don't include the wide outer outline in this. The cluster mask
# still includes everything red, but ANDing with combined_filling
# clips it to inside the lettuce.
INTERIOR_DETAIL_COUNT = 7      # source has many veins; 7 reads as "stuff" not just dots
INTERIOR_DETAIL_MIN_PX = 30

# Build a k-means-derived red mask matching the strategy used in tmp/
# debug scripts. Run the same k=N_CLUSTERS clustering already done
# above; then nearest-cluster-assign every FG pixel.
fg_pixels_full = img[ys, xs].astype(np.float32)
centers_full = km.cluster_centers_.astype(np.float32)
dists_full = ((fg_pixels_full[:, None, :] - centers_full[None, :, :]) ** 2).sum(-1)
labels_global = np.argmin(dists_full, axis=1)
label_grid = -np.ones((H, W), dtype=np.int32)
label_grid[ys, xs] = labels_global
def _nearest(target_rgb):
    return int(np.argmin([(c[0]-target_rgb[0])**2 + (c[1]-target_rgb[1])**2 + (c[2]-target_rgb[2])**2
                          for c in km.cluster_centers_]))
red_kcluster_idx = _nearest((140, 20, 9))
red_kmask = label_grid == red_kcluster_idx

red_inside = red_kmask & combined_filling
labeled_ri, n_ri = ndimage.label(red_inside)
interior_detail = np.zeros_like(red_inside)
if n_ri:
    sizes_ri = ndimage.sum(red_inside, labeled_ri, range(1, n_ri+1))
    centroids_ri = ndimage.center_of_mass(red_inside, labeled_ri, range(1, n_ri+1))
    cands = [(sz, i+1, centroids_ri[i]) for i, sz in enumerate(sizes_ri)
             if sz >= INTERIOR_DETAIL_MIN_PX]
    cands.sort(reverse=True)
    chosen = cands[:INTERIOR_DETAIL_COUNT]
    for sz, idx, ctr in chosen:
        interior_detail |= labeled_ri == idx
        print(f"    keep fragment idx={idx} size={int(sz)}px at {ctr}")

write_svg(OUT/'region_interior_detail.svg',
          mask_to_paths(interior_detail, smooth=False, min_area=INTERIOR_DETAIL_MIN_PX),
          '#921209')
print(f"  region_interior_detail.svg <- {INTERIOR_DETAIL_COUNT} largest fragments "
      f"({interior_detail.sum()} px)")

(OUT/'region_palette.txt').write_text('\n'.join(palette_lines) + '\n', encoding='utf-8')

# ── Polygon-coords manifest (preferred over SVGs for build pipeline) ────
# All regions emitted in a SHARED MM coordinate frame: origin at the
# silhouette bbox center. The build script reads this JSON and constructs
# Blender meshes directly via bmesh.from_pydata — no SVG round-trip,
# guaranteed-consistent scale + position across every region.
import json
def mask_to_polygons_mm(mask, simplify_tol_px=0.0, smooth=False, harm=14, min_area=200):
    """Return list of polygons, each as a dict:
       {'outer': [(x_mm, y_mm), ...], 'holes': [[(x_mm, y_mm), ...], ...]}
    Each connected component contributes one entry. Holes are inner
    contours (for ring-shaped components). Coords are in mm at the
    silhouette bbox center (origin = bead center, +X right, +Y up)."""
    px_to_mm = SCALE_PX_TO_MM
    silh_cx_px = (bx0 + bx1) / 2.0
    silh_cy_px = (by0 + by1) / 2.0
    polygons = []
    labeled, n = ndimage.label(mask)
    for k in range(1, n+1):
        comp = labeled == k
        if comp.sum() < min_area: continue
        contours = measure.find_contours(comp.astype(np.uint8), level=0.5)
        if not contours: continue
        # Sort by length: longest = outer; rest = holes
        contours.sort(key=lambda c: -len(c))

        def transform(c):
            c = downsample(c, 400)
            if smooth and len(c) > 10:
                z = fourier_smooth(c, harm)
                c = np.column_stack((z.real, z.imag))
            ys, xs = c[:, 0], c[:, 1]
            x_mm = (xs - silh_cx_px) * px_to_mm
            y_mm = -(ys - silh_cy_px) * px_to_mm
            return list(zip(x_mm.tolist(), y_mm.tolist()))

        outer = transform(contours[0])
        holes = [transform(h) for h in contours[1:] if len(h) >= 8]
        polygons.append({'outer': outer, 'holes': holes})
    return polygons

# ── Red shell outline (4th decoration layer) ────────────────────────
# The taco's outer red border in the source. Extract: red-cluster pixels
# OUTSIDE the lettuce blob (since pixels INSIDE lettuce are interior_detail).
# This captures the outer outline ring + the shell-vs-lettuce separator
# curve. Dilate by 2px (~0.14mm) to bring stroke width up to ~0.5mm so
# the Centauri Carbon 2's 0.4mm nozzle prints it reliably.
# Restrict the red mask to a THIN BAND along the silhouette outer edge —
# that's where the source's "outline" is. Without this restriction we
# pick up every red pixel everywhere (transition shading, red bits between
# elements) and the outline floods most of the bead.
SHELL_OUTLINE_THICK_MM = 0.5    # ~Centauri 0.4mm nozzle, slightly over for safety
# Build the outline ring DIRECTLY FROM THE SILHOUETTE POLYGON via shapely.
# This guarantees the outline's outer edge is identical to the silhouette
# polygon used for the bead body — no holes/gaps where they would diverge
# due to mismatched smoothing between the raw mask and silhouette.svg.
from shapely.geometry import Polygon as _Poly, MultiPolygon as _MPoly
import json as _json
shell_outline_polys_mm = None
silh_paths = mask_to_paths(outer, smooth=True, harm=FOURIER_HARM_BODY,
                           min_area=2000, pre_blur_sigma=SILHOUETTE_BLUR_SIGMA)
if silh_paths:
    silh_pts_px = silh_paths[0]
    # silh_pts_px is in source pixel coords (row=y, col=x). Convert to mm
    # at silhouette bbox center, +Y up.
    silh_cx_px = (bx0 + bx1) / 2.0
    silh_cy_px = (by0 + by1) / 2.0
    silh_xy_mm = [((float(p[1]) - silh_cx_px) * SCALE_PX_TO_MM,
                   -(float(p[0]) - silh_cy_px) * SCALE_PX_TO_MM)
                  for p in silh_pts_px]
    silh_poly = _Poly(silh_xy_mm)
    if not silh_poly.is_valid: silh_poly = silh_poly.buffer(0)
    inset_poly = silh_poly.buffer(-SHELL_OUTLINE_THICK_MM, join_style=2)
    # build polygon-with-holes representation
    outline_dicts = []
    if silh_poly.is_valid and not inset_poly.is_empty:
        # Inset can yield a MultiPolygon if the bead "pinches" thinner than
        # 2× outline thickness somewhere. Subtract each component.
        if isinstance(inset_poly, _MPoly):
            holes = [list(p.exterior.coords) for p in inset_poly.geoms]
        else:
            holes = [list(inset_poly.exterior.coords)]
        outline_dicts.append({
            'outer': list(silh_poly.exterior.coords),
            'holes': holes,
        })
    shell_outline_polys_mm = outline_dicts

# Filling-shell separator (a curve, not a ring): keep mask-derived
filling_inner_edge = combined_filling & ~ndimage.binary_erosion(
    combined_filling, iterations=int(SHELL_OUTLINE_THICK_MM/SCALE_PX_TO_MM))
silhouette_ring_mask = outer & ~ndimage.binary_erosion(
    outer, iterations=int(SHELL_OUTLINE_THICK_MM/SCALE_PX_TO_MM))
separator = filling_inner_edge & ~silhouette_ring_mask & outer

# Combined "shell_outline" data: polygon-with-holes ring (from shapely
# silhouette polygon offset) + separator polygons (from mask).
# Filter the separator mask of tiny fragments
labeled_so, n_so = ndimage.label(separator)
if n_so:
    sizes_so = ndimage.sum(separator, labeled_so, range(1, n_so+1))
    keep = np.zeros_like(separator)
    for i, sz in enumerate(sizes_so, 1):
        if sz >= 100: keep |= labeled_so == i
    separator = keep
print(f"  shell_outline ring polygons: {len(shell_outline_polys_mm or [])}, "
      f"separator px: {separator.sum()} ({ndimage.label(separator)[1]} fragments)")

regions_data = {
    'scale_mm_per_px': float(SCALE_PX_TO_MM),
    'silhouette_bbox_mm': {
        'width': float(TARGET_WIDTH_MM),
        'height': float((by1 - by0) * SCALE_PX_TO_MM),
    },
    'regions': {
        'filling': {
            'polygons': mask_to_polygons_mm(combined_filling, smooth=False, min_area=300),
            'color_hex': '#3ea332',
        },
        'shell': {
            'polygons': mask_to_polygons_mm(combined_shell, smooth=False, min_area=300),
            'color_hex': '#e6c41e',
        },
        'interior_detail': {
            'polygons': mask_to_polygons_mm(interior_detail, smooth=False, min_area=INTERIOR_DETAIL_MIN_PX),
            'color_hex': '#921209',
        },
        # Ring around the silhouette outer edge — sits BELOW filling in z stack
        'shell_outline': {
            'polygons': shell_outline_polys_mm or [],
            'color_hex': '#a01a14',
        },
        # Dividing curve between lettuce and shell — sits ABOVE filling so
        # the red curve is visible (otherwise filling would cover it).
        'lettuce_separator': {
            'polygons': mask_to_polygons_mm(separator, smooth=False, min_area=120),
            'color_hex': '#a01a14',
        },
    },
}
(OUT/'regions.json').write_text(json.dumps(regions_data, indent=2), encoding='utf-8')
total_polys = sum(len(r['polygons']) for r in regions_data['regions'].values())
print(f"\nwrote regions.json ({total_polys} polygons across "
      f"{len(regions_data['regions'])} regions)")
print(f"\nwrote silhouette + {len(REGIONS)} region SVGs + palette.txt + extract_debug.png")
print(f"scale: {SCALE_PX_TO_MM:.4f} mm/px (silhouette {TARGET_WIDTH_MM}mm × {Hmm:.2f}mm)")
