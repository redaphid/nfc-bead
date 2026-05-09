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
N_CLUSTERS = 7      # over-cluster, then merge by named-region
MIN_CLUSTER_PCT = 6 # discard clusters smaller than this (% of fg pixels)
FOURIER_HARM = 18

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

def mask_to_paths(mask, smooth=True, harm=FOURIER_HARM, min_area=200):
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

def write_svg(filename, paths, fill='#000'):
    if not paths: print(f"  (skip {filename} — no paths)"); return False
    global Hmm
    Wmm = TARGET_WIDTH_MM
    Hmm = (by1 - by0) * SCALE_PX_TO_MM
    svg_w = Wmm * 100; svg_h = Hmm * 100
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}">']
    for c in paths:
        ys = c[:, 0]; xs = c[:, 1]
        x_mm = (xs - bx0) * SCALE_PX_TO_MM
        y_mm = (ys - by0) * SCALE_PX_TO_MM
        d = 'M ' + ' L '.join(f'{x*100:.2f},{y*100:.2f}' for x,y in zip(x_mm, y_mm)) + ' Z'
        parts.append(f'<path fill="{fill}" stroke="none" d="{d}"/>')
    parts.append('</svg>')
    open(filename, 'w', encoding='utf-8').write('\n'.join(parts))
    return True

# Outer silhouette (smoothed)
write_svg(OUT/'silhouette.svg', mask_to_paths(outer, smooth=True, harm=24, min_area=2000), '#000')

palette_lines = []
for name, hex_col, _ in REGIONS:
    paths = mask_to_paths(region_masks[name], smooth=True, harm=FOURIER_HARM, min_area=200)
    if write_svg(OUT/f'region_{name}.svg', paths, hex_col):
        print(f"  region_{name}.svg ← {len(paths)} path(s) ({region_masks[name].sum()} px)")
        palette_lines.append(f"{name}\t{hex_col}\t{region_masks[name].sum()} px")
    else:
        palette_lines.append(f"{name}\t{hex_col}\t(empty)")

(OUT/'region_palette.txt').write_text('\n'.join(palette_lines) + '\n', encoding='utf-8')
print(f"\nwrote silhouette + {len(REGIONS)} region SVGs + palette.txt + extract_debug.png")
print(f"scale: {SCALE_PX_TO_MM:.4f} mm/px (silhouette {TARGET_WIDTH_MM}mm × {Hmm:.2f}mm)")
