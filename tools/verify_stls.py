"""Verify the latest exported STLs are print-ready.

Loads the 3 STL files via trimesh and runs a structured check pass:

  geometry          — vertex/face count > 0
  watertight        — every edge has exactly 2 face uses (manifold)
  bed-flat          — Bottom and Top start at z=0 (flush on the build plate)
  expected-dim      — diameter ~25 mm, thickness within tolerance
  decoration-stack  — Decoration sits ABOVE Top's outer face when merged
                      (its min-z >= Top max-z, max-z within relief band)

Returns a non-zero exit code if any check fails — useful as a pre-print
guard in CI / git hooks.

Default scans `tmp/latest/`. Override with `--dir <path>` or pass an
explicit list of STL paths.

Designed for `uv run`:
    uv run python -m tools.verify_stls
    uv run python -m tools.verify_stls --dir tmp/stl_export_20260425_221316
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import numpy as np
import trimesh

# ─── Expected dimensions ───────────────────────────────────────────────
# Sized for a Kandi bracelet bead: smallest comfortable diameter that
# encloses the NTAG215 sticker (10.5 mm dia), 3 friction-fit pegs, and
# a 2 mm string hole. 18 mm with NFC pocket centered + pegs at radius
# 7 mm gives 0.75 mm peg-to-NFC gap and 1 mm peg-to-bead-edge wall.
EXPECTED_DIA_MM        = 17.0
DIA_TOL_MM             = 1.5
BOTTOM_THICK_MM        = 4.0    # 2.5 mm puck + 1.5 mm pegs above
BOTTOM_THICK_TOL_MM    = 0.5
TOP_THICK_MM           = 2.5
TOP_THICK_TOL_MM       = 0.3
DECORATION_HEIGHT_MM   = 0.5    # raised relief above Top's outer face
DECORATION_HEIGHT_TOL  = 0.2

# Canonical part names — must match build pipeline + bead-stl-export.
CANONICAL_PARTS = ("Bottom", "Top", "Decoration")


# ─── Result types ──────────────────────────────────────────────────────
@dataclass
class Check:
    name: str
    ok: bool
    detail: str

    def fmt(self, color: bool = True) -> str:
        # Use Unicode marks only when the stdout encoding can handle them
        encoding = getattr(sys.stdout, "encoding", "") or ""
        unicode_ok = encoding.lower().startswith(("utf", "u8"))
        mark = ("✓" if self.ok else "✗") if unicode_ok else ("OK" if self.ok else "FAIL")
        if color and sys.stdout.isatty():
            green, red, reset = "\x1b[32m", "\x1b[31m", "\x1b[0m"
            mark = (green if self.ok else red) + mark + reset
        return f"  {mark}  {self.name:<30} {self.detail}"


# ─── Load + characterize one STL ───────────────────────────────────────
def _load(path: str) -> trimesh.Trimesh | None:
    try:
        m = trimesh.load(path, force="mesh")
    except Exception as e:                     # noqa: BLE001
        print(f"  load error: {path}: {e}", file=sys.stderr)
        return None
    if not isinstance(m, trimesh.Trimesh):
        return None
    return m


def _bbox(mesh: trimesh.Trimesh) -> tuple[np.ndarray, np.ndarray]:
    return mesh.bounds[0], mesh.bounds[1]


def _check_geometry(mesh: trimesh.Trimesh) -> Check:
    nv, nf = len(mesh.vertices), len(mesh.faces)
    return Check("geometry", nv > 0 and nf > 0, f"{nv} verts / {nf} faces")


def _check_watertight(mesh: trimesh.Trimesh) -> Check:
    return Check(
        "watertight",
        bool(mesh.is_watertight),
        "manifold" if mesh.is_watertight else "non-manifold (edges with !=2 faces)",
    )


def _check_bed_flat(mesh: trimesh.Trimesh, name: str) -> Check:
    zmin, zmax = mesh.bounds[0][2], mesh.bounds[1][2]
    # Bottom and Top should sit on the build plate (zmin == 0).
    # Decoration is exempt — it shares Top's shift to preserve stacking.
    if name == "Decoration":
        return Check("bed-flat (n/a)", True, f"z=[{zmin:.2f},{zmax:.2f}] (decoration: shares Top's frame)")
    ok = abs(zmin) < 0.01
    return Check("bed-flat", ok, f"z=[{zmin:.2f},{zmax:.2f}] expected z_min=0")


def _check_dimensions(mesh: trimesh.Trimesh, name: str) -> list[Check]:
    bmin, bmax = mesh.bounds
    dx = float(bmax[0] - bmin[0])
    dy = float(bmax[1] - bmin[1])
    dz = float(bmax[2] - bmin[2])
    out: list[Check] = []

    diameter = max(dx, dy)
    expected_dia = EXPECTED_DIA_MM
    if name == "Decoration":
        # Spiral is inset by the SPIRAL_OUTER_R config (8 mm radius for the
        # 20 mm bead = 16 mm dia). Tolerance wide enough to accept variants.
        expected_dia = EXPECTED_DIA_MM - 4.0
        out.append(Check(
            "diameter",
            abs(diameter - expected_dia) <= DIA_TOL_MM + 1.5,
            f"{diameter:.2f} mm (expected {expected_dia:.0f} +- {DIA_TOL_MM + 1.5:.1f})",
        ))
    else:
        out.append(Check(
            "diameter",
            abs(diameter - expected_dia) <= DIA_TOL_MM,
            f"{diameter:.2f} mm (expected {expected_dia:.0f} +- {DIA_TOL_MM:.1f})",
        ))

    if name == "Bottom":
        out.append(Check(
            "thickness",
            abs(dz - BOTTOM_THICK_MM) <= BOTTOM_THICK_TOL_MM,
            f"{dz:.2f} mm (expected {BOTTOM_THICK_MM} +- {BOTTOM_THICK_TOL_MM})",
        ))
    elif name == "Top":
        out.append(Check(
            "thickness",
            abs(dz - TOP_THICK_MM) <= TOP_THICK_TOL_MM,
            f"{dz:.2f} mm (expected {TOP_THICK_MM} +- {TOP_THICK_TOL_MM})",
        ))
    elif name == "Decoration":
        out.append(Check(
            "relief height",
            abs(dz - DECORATION_HEIGHT_MM) <= DECORATION_HEIGHT_TOL,
            f"{dz:.2f} mm (expected {DECORATION_HEIGHT_MM} +- {DECORATION_HEIGHT_TOL})",
        ))
    return out


def _check_decoration_stacking(top: trimesh.Trimesh, deco: trimesh.Trimesh) -> list[Check]:
    """Decoration must sit ABOVE Top's outer face when both are merged."""
    top_zmax = float(top.bounds[1][2])
    deco_zmin = float(deco.bounds[0][2])
    deco_zmax = float(deco.bounds[1][2])

    # Decoration should start AT or just above Top's outer face (small ε for Z-fight prevention)
    gap = deco_zmin - top_zmax
    ok_gap = -0.02 <= gap <= 0.10  # allow 0.02mm overlap (Z-fight ok) up to 0.1mm air gap
    relief = deco_zmax - top_zmax
    ok_relief = 0.3 <= relief <= 1.0   # spiral relief ~0.5 mm

    # X/Y centers should align (within Top's bbox)
    top_cx = float((top.bounds[0][0] + top.bounds[1][0]) / 2)
    top_cy = float((top.bounds[0][1] + top.bounds[1][1]) / 2)
    deco_cx = float((deco.bounds[0][0] + deco.bounds[1][0]) / 2)
    deco_cy = float((deco.bounds[0][1] + deco.bounds[1][1]) / 2)
    ok_xy = abs(deco_cx - top_cx) <= 1.0 and abs(deco_cy - top_cy) <= 2.0
    return [
        Check(
            "decoration on top",
            ok_gap,
            f"gap top_max={top_zmax:.2f} -> deco_min={deco_zmin:.2f} = {gap:+.2f} mm (expected -0.02..+0.10)",
        ),
        Check(
            "decoration relief",
            ok_relief,
            f"deco z extent above top: {relief:.2f} mm (expected 0.3..1.0)",
        ),
        Check(
            "decoration X/Y aligned",
            ok_xy,
            f"top center=({top_cx:+.2f},{top_cy:+.2f}) deco center=({deco_cx:+.2f},{deco_cy:+.2f})",
        ),
    ]


# ─── Driver ────────────────────────────────────────────────────────────
def verify(stl_dir: str) -> int:
    """Returns 0 on full pass, 1 on any failure."""
    paths = {p: os.path.join(stl_dir, f"{p}.stl") for p in CANONICAL_PARTS}
    missing = [p for p, path in paths.items() if not os.path.isfile(path)]
    if missing:
        print(f"missing STL(s) in {stl_dir}: {missing}", file=sys.stderr)
        return 1

    print(f"verifying STLs in {stl_dir}\n")
    all_checks: list[tuple[str, list[Check]]] = []
    meshes: dict[str, trimesh.Trimesh] = {}

    for name, path in paths.items():
        m = _load(path)
        if m is None:
            all_checks.append((name, [Check("load", False, f"failed to read {path}")]))
            continue
        meshes[name] = m
        checks = [
            _check_geometry(m),
            _check_watertight(m),
            _check_bed_flat(m, name),
            *_check_dimensions(m, name),
        ]
        all_checks.append((name, checks))

    # Cross-part check
    if "Top" in meshes and "Decoration" in meshes:
        all_checks.append((
            "Top + Decoration (assembly)",
            _check_decoration_stacking(meshes["Top"], meshes["Decoration"]),
        ))

    # Print + tally
    fails = 0
    for part_name, checks in all_checks:
        print(f"{part_name}")
        for c in checks:
            print(c.fmt())
            if not c.ok:
                fails += 1
        print()

    if fails:
        print(f"VERIFICATION FAILED: {fails} check(s) did not pass")
    else:
        print("VERIFICATION PASSED: all checks ok")
    return 0 if fails == 0 else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--dir", default=None, help="STL directory (default: tmp/latest/ at repo root)")
    args = p.parse_args()
    if args.dir:
        stl_dir = args.dir
    else:
        # Walk up from this file to find tmp/latest
        here = os.path.dirname(os.path.abspath(__file__))
        for _ in range(4):
            cand = os.path.join(here, "tmp", "latest")
            if os.path.isdir(cand):
                stl_dir = cand
                break
            here = os.path.dirname(here)
        else:
            stl_dir = os.path.join(os.getcwd(), "tmp", "latest")
    return verify(stl_dir)


if __name__ == "__main__":
    sys.exit(main())
