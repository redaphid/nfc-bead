"""Printability checks on the latest bead STL set.

Runs after `bead-stl-export` and before the slicer. Catches failure modes
that the geometry-only `verify_stls.py` misses — the ones we ran into the
hard way during physical printing of redaphid-portrait. See
`.claude/skills/bead-printability-check/SKILL.md` for the full list.

Usage:
    uv run nfc-printability-check               # default: tmp/latest/
    uv run nfc-printability-check --dir <path>  # alternate dir
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import trimesh
import trimesh.path
import trimesh.path.polygons


# ─── Tunables ────────────────────────────────────────────────────────────
MIN_WALL_ABOVE_HOLE_MM   = 2.0     # recipe ideal >= 2.5 mm; hard fail below 1.5
SOFT_WALL_ABOVE_HOLE_MM  = 1.5
MAX_CANTILEVER_RATIO     = 5.0
PEG_EDGE_TOLERANCE_MM    = 0.1
MIN_BED_CONTACT_MM2      = 80.0


# ─── Pretty output ───────────────────────────────────────────────────────
def ok(label, msg=""):
    print(f"  \033[32mOK\033[0m  {label:32s} {msg}")
    return 0


def warn(label, msg):
    print(f"  \033[33mWARN\033[0m {label:32s} {msg}")
    return 0


def fail(label, msg):
    print(f"  \033[31mFAIL\033[0m {label:32s} {msg}")
    return 1


# ─── Helpers ─────────────────────────────────────────────────────────────
def _section_polygons(mesh: trimesh.Trimesh, z: float):
    """Return shapely polygons of the mesh's cross-section at plane z, in
    WORLD XY coordinates. Trimesh's `Path3D.to_2D()` reprojects to a local
    2D frame whose axes don't match world X/Y; building polygons from the
    section's discrete 3D loops + dropping Z preserves world XY directly."""
    from shapely.geometry import Polygon  # noqa: PLC0415
    sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if sec is None:
        return []

    # Each closed loop is a 3D polyline; drop Z to get world XY polygons.
    polygons = []
    for loop in sec.discrete:
        if len(loop) < 4:
            continue
        verts_xy = np.asarray(loop)[:, :2]
        try:
            poly = Polygon(verts_xy)
            if poly.is_valid and poly.area > 0.05:
                polygons.append(poly)
        except (ValueError, TypeError):
            continue

    # Resolve interior holes via shapely: smaller polygons fully contained
    # inside a larger one are holes; rebuild as Polygon(exterior, interiors).
    if not polygons:
        return []
    polygons.sort(key=lambda p: -p.area)
    used = [False] * len(polygons)
    final = []
    for i, outer in enumerate(polygons):
        if used[i]:
            continue
        used[i] = True
        holes = []
        for j in range(i + 1, len(polygons)):
            if used[j]:
                continue
            inner = polygons[j]
            if outer.contains(inner):
                holes.append(list(inner.exterior.coords))
                used[j] = True
        final.append(Polygon(list(outer.exterior.coords), holes))
    return final


def _section_area(mesh: trimesh.Trimesh, z: float) -> float:
    """Sum area of all polygon islands in the cross-section at z."""
    polys = _section_polygons(mesh, z)
    return float(sum(p.area for p in polys))


# ─── Checks ──────────────────────────────────────────────────────────────
def check_wall_above_hole(bottom: trimesh.Trimesh, top: trimesh.Trimesh) -> int:
    """The silhouette must have >= MIN_WALL_ABOVE_HOLE_MM of solid material
    above the string hole. The hole is drilled at z_mid (cut plane); after
    splitting, each half has a HALF-pipe notch on its inner face. Detect
    the notch by diffing two cross-sections of the half: one in the body
    (clean silhouette) and one just below the inner face (silhouette minus
    the half-pipe). The diff's bbox gives hole Y center + radius.
    """
    from shapely.ops import unary_union  # noqa: PLC0415

    # Bottom canonical: silhouette face z=0, inner face z≈z_mid (~2.5).
    # Pick a Z that's solidly inside the body (z=0.5) and just below
    # the inner face (z=z_max_body - 0.05). Body z_max is roughly
    # the bottom's bbox z_max minus PEG_HEIGHT (~1.5 mm).
    z_body  = bottom.bounds[0, 2] + 0.5
    # Find the plane between body and pegs by looking for a sharp area drop
    # going up; or just sample a band that's clearly inside the body.
    z_inner = bottom.bounds[1, 2]      # absolute top of Bottom (peg tips)
    # Walk DOWN from peg tips until cross-section area jumps up (hit body
    # top = inner face). Sample a few z values.
    z_samples = np.linspace(bottom.bounds[1, 2] - 0.1,
                            bottom.bounds[0, 2] + 0.5, 10)
    best_z, best_area = None, 0.0
    for z in z_samples:
        polys = _section_polygons(bottom, z)
        a = sum(p.area for p in polys)
        if a > best_area * 1.5 and best_z is not None:
            # Big jump = transitioned from pegs into body
            z_inner = z
            break
        if a > best_area:
            best_area, best_z = a, z

    # Sample slightly below the inner face — captures the half-pipe notch
    z_notch = z_inner - 0.1 if z_inner is not None else bottom.bounds[1, 2] - 2.0
    polys_body  = _section_polygons(bottom, z_body)
    polys_notch = _section_polygons(bottom, z_notch)
    if not polys_body or not polys_notch:
        return warn("wall above hole", "couldn't sample silhouette cross-sections")

    body  = max(polys_body,  key=lambda p: p.area)
    notch = max(polys_notch, key=lambda p: p.area)
    diff = body.difference(notch)        # half-pipe carved away
    if diff.is_empty or diff.area < 0.5:
        return ok("wall above hole",
                  "no string-hole notch detected on inner face (charm may not have one)")
    # Sanity: a real string hole half-pipe is small (< ~5 mm^2). If the diff
    # is huge, it's a Z-taper or boolean noise, not a hole. Skip.
    if diff.area > body.area * 0.10:
        return warn("wall above hole",
                    f"diff area {diff.area:.1f} mm^2 too large to be a hole notch; skipping")

    # Extract the notch's bbox — its width in X is the hole length-ish
    # (bounded by silhouette), height in Y is the hole radius.
    minx, miny, maxx, maxy = diff.bounds
    hole_y_top = maxy

    # Silhouette top at the hole's center X — find body exterior points near x=0
    ext = np.array(body.exterior.coords)
    near_center = ext[np.abs(ext[:, 0]) < 1.5]
    if len(near_center) == 0:
        return warn("wall above hole", "no silhouette boundary near center X")
    sil_top_y = float(near_center[:, 1].max())

    wall = sil_top_y - hole_y_top
    msg = f"hole top y={hole_y_top:+.2f} silhouette top y={sil_top_y:+.2f} -> wall = {wall:.2f} mm"
    if wall < SOFT_WALL_ABOVE_HOLE_MM:
        return fail("wall above hole", msg + f"  (need >= {MIN_WALL_ABOVE_HOLE_MM} mm)")
    if wall < MIN_WALL_ABOVE_HOLE_MM:
        return warn("wall above hole", msg + "  (recipe wants >= 2.5 mm; consider lowering HOLE_Y)")
    return ok("wall above hole", msg)


def check_cantilever(name: str, mesh: trimesh.Trimesh) -> int:
    """Compare cross-section area at z=0.5 (bottom slice) and z=2.5 (mid).
    A printable part has area_low >= area_high / MAX_CANTILEVER_RATIO. A
    cantilevered part has tiny pegs touching the plate (small area_low)
    and a wide body above (large area_high)."""
    if mesh.bounds[1, 2] < 1.0:
        return ok(f"cantilever ({name})", "part too thin to assess")
    z_low  = mesh.bounds[0, 2] + 0.5
    z_mid  = mesh.bounds[0, 2] + 2.5
    if z_mid >= mesh.bounds[1, 2]:
        z_mid = (mesh.bounds[0, 2] + mesh.bounds[1, 2]) / 2.0
    a_low = _section_area(mesh, z_low)
    a_mid = _section_area(mesh, z_mid)
    if a_low < 0.1:
        return fail(f"cantilever ({name})", f"no plate-contact area at z={z_low:.2f}")
    ratio = a_mid / a_low
    msg = f"area z={z_low:.2f}: {a_low:.0f} mm^2,  z={z_mid:.2f}: {a_mid:.0f} mm^2  ratio={ratio:.1f}"
    if ratio > MAX_CANTILEVER_RATIO:
        return fail(f"cantilever ({name})", msg + f"  > {MAX_CANTILEVER_RATIO} (cantilever — supports needed)")
    return ok(f"cantilever ({name})", msg)


def check_peg_edges_inside_silhouette(bottom: trimesh.Trimesh) -> int:
    """Peg cylinders should sit ENTIRELY inside the silhouette at their Y
    position — `verify_pegs` only checks peg CENTER lands on solid material.
    Take the silhouette polygon at z=0.5 (pure body) and the peg outlines
    at z=3 (above the body, where pegs cross-section), and confirm each peg
    polygon is contained within the silhouette polygon."""
    # Silhouette outline at z just above the silhouette face
    z_low = bottom.bounds[0, 2] + 0.5
    sil_polys = _section_polygons(bottom, z_low)
    if not sil_polys:
        return warn("peg edges inside silhouette", "no silhouette slice")
    silhouette = max(sil_polys, key=lambda p: p.area)

    # Peg outlines higher up (above body, at peg height)
    z_pegs = bottom.bounds[1, 2] - 0.5     # 0.5 mm below peg tips
    peg_polys = _section_polygons(bottom, z_pegs)
    # Pegs are smaller than the silhouette -> keep only those significantly smaller
    peg_polys = [p for p in peg_polys if p.area < silhouette.area * 0.5]
    if not peg_polys:
        return ok("peg edges inside silhouette", "no peg cross-sections detected (no pegs?)")

    # Buffer the silhouette inward by tolerance — pegs should be inside this
    sil_inner = silhouette.buffer(-PEG_EDGE_TOLERANCE_MM)
    bad = []
    for p in peg_polys:
        if not sil_inner.contains(p):
            cx, cy = p.centroid.x, p.centroid.y
            # find max protrusion: any point on p outside silhouette
            from shapely.geometry import Point  # noqa: PLC0415
            ext = np.array(p.exterior.coords)
            outside = [Point(x, y) for x, y in ext if not silhouette.contains(Point(x, y))]
            if outside:
                # measure max distance from outside point to silhouette
                protrude = max(silhouette.distance(o) for o in outside)
                bad.append((cx, cy, protrude))
    if not bad:
        return ok("peg edges inside silhouette", f"{len(peg_polys)} peg(s) contained")
    msgs = "; ".join(f"({cx:+.1f},{cy:+.1f}) by {p:.2f} mm" for cx, cy, p in bad)
    return warn("peg edges inside silhouette", f"{len(bad)} peg(s) protrude past silhouette: {msgs}")


def check_bed_contact(name: str, mesh: trimesh.Trimesh) -> int:
    """First-layer area must be large enough for stable adhesion. Slice at
    z = z_min + 0.1 (essentially the first layer). Bottom should be silhouette
    cross-section (~150 mm^2); a small contact = adhesion concern."""
    z_first = mesh.bounds[0, 2] + 0.1
    a = _section_area(mesh, z_first)
    msg = f"first-layer area = {a:.0f} mm^2"
    if a < MIN_BED_CONTACT_MM2:
        return fail(f"bed contact ({name})", msg + f"  (need >= {MIN_BED_CONTACT_MM2:.0f} mm^2)")
    return ok(f"bed contact ({name})", msg)


# ─── Driver ──────────────────────────────────────────────────────────────
def run_checks(stl_dir: str) -> int:
    bottom_path = os.path.join(stl_dir, "Bottom.stl")
    top_path    = os.path.join(stl_dir, "Top.stl")
    if not (os.path.isfile(bottom_path) and os.path.isfile(top_path)):
        print(f"missing Bottom.stl or Top.stl in {stl_dir}", file=sys.stderr)
        return 1
    bottom = trimesh.load(bottom_path, force="mesh")
    top    = trimesh.load(top_path,    force="mesh")
    print(f"checking STLs in {stl_dir}\n")

    failures = 0
    failures += check_wall_above_hole(bottom, top)
    failures += check_cantilever("Bottom", bottom)
    failures += check_cantilever("Top",    top)
    failures += check_peg_edges_inside_silhouette(bottom)
    failures += check_bed_contact("Bottom", bottom)
    failures += check_bed_contact("Top",    top)

    print()
    if failures:
        print(f"PRINTABILITY CHECK FAILED: {failures} check(s) did not pass")
        return 1
    print("PRINTABILITY CHECK OK")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--dir", default=None,
                   help="STL source directory (default: tmp/latest/ at repo root)")
    args = p.parse_args()
    if args.dir:
        stl_dir = args.dir
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        for _ in range(4):
            cand = os.path.join(here, "tmp", "latest")
            if os.path.isdir(cand):
                stl_dir = cand
                break
            here = os.path.dirname(here)
        else:
            stl_dir = os.path.join(os.getcwd(), "tmp", "latest")
    return run_checks(stl_dir)


if __name__ == "__main__":
    sys.exit(main())
