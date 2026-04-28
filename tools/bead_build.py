"""One-shot orchestration of the full bead pipeline.

Chains: rebuild (via Blender MCP) -> export STLs -> verify -> printability
check -> make 3MF -> copy to beads/<charm>/print/. See
`.claude/skills/bead-build/SKILL.md` for the full contract.

Usage:
    uv run nfc-bead-build                       # auto-detect from current branch
    uv run nfc-bead-build --charm redaphid-portrait
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _branch_name() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO, text=True
        ).strip()
        return out
    except Exception:
        return ""


def _resolve_charm(arg_charm: str | None) -> str | None:
    if arg_charm:
        return arg_charm
    branch = _branch_name()
    candidate = REPO / "beads" / branch
    if candidate.is_dir():
        return branch
    return None


def _find_build_script(bead_dir: Path, charm: str) -> Path | None:
    """Build script naming is loose — try several patterns and fall back
    to any `build_*.py` in the bead dir."""
    candidates = [
        bead_dir / f"build_{charm}.py",
        bead_dir / f"build_{charm.replace('-', '_')}.py",
        bead_dir / f"build_{charm.split('-')[0]}.py",          # build_redaphid.py for redaphid-portrait
    ]
    for c in candidates:
        if c.exists():
            return c
    # Last resort: any build_*.py
    matches = list(bead_dir.glob("build_*.py"))
    if len(matches) == 1:
        return matches[0]
    return None


def _step_header(n: int, label: str):
    print(f"\n\033[36m[{n}/6] {label}\033[0m")


def _run(cmd: list[str], cwd: Path) -> int:
    print("  $ " + " ".join(cmd))
    return subprocess.call(cmd, cwd=cwd)


def _send_to_blender(code: str, host: str = "localhost", port: int = 9876) -> int:
    """Send a Python snippet to Blender via the MCP socket. Returns 0 on success."""
    cmd = ["uv", "run", "nfc-blender-send", "-c", code, "--host", host, "--port", str(port)]
    return _run(cmd, REPO)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--charm", default=None,
                   help="Charm name under beads/<charm>/. Auto-detects from current branch if omitted.")
    p.add_argument("--skip-printability", action="store_true",
                   help="Skip the bead-printability-check step")
    p.add_argument("--mcp-host", default="localhost")
    p.add_argument("--mcp-port", type=int, default=9876)
    args = p.parse_args()

    charm = _resolve_charm(args.charm)
    if not charm:
        print("Could not auto-detect charm. Pass --charm <name>.", file=sys.stderr)
        return 1
    bead_dir   = REPO / "beads" / charm
    build_py   = _find_build_script(bead_dir, charm)
    if build_py is None:
        print(f"No build script found in {bead_dir} (looked for build_*.py)", file=sys.stderr)
        return 1
    print_dir = bead_dir / "print"
    print_dir.mkdir(parents=True, exist_ok=True)

    print(f"\033[33mbead-build:\033[0m {charm}")
    print(f"  build script: {build_py.relative_to(REPO)}")
    print(f"  print dir:    {print_dir.relative_to(REPO)}")

    failures = []

    # ── 1. Rebuild via Blender MCP ────────────────────────────────────
    _step_header(1, "rebuild via Blender MCP")
    rebuild_code = textwrap.dedent(f"""
        import bpy
        # Wipe FullBead* and the canonical names so the build starts clean
        for n in list(bpy.data.objects.keys()):
            if n.startswith('FullBead') or n in ('Bottom','Top','Hair','Decoration'):
                try: bpy.data.objects.remove(bpy.data.objects[n], do_unlink=True)
                except Exception: pass
        script = open(r'{build_py}', encoding='utf-8').read()
        ns = {{'__name__': '__main__'}}
        exec(script, ns)
    """).strip()
    rc = _send_to_blender(rebuild_code, args.mcp_host, args.mcp_port)
    if rc != 0:
        print("\033[31mrebuild failed — Blender MCP not reachable or build script raised\033[0m", file=sys.stderr)
        return 1

    # ── 2. Export STLs via skill ──────────────────────────────────────
    _step_header(2, "export STLs (bead-stl-export)")
    export_py = REPO / ".claude" / "skills" / "bead-stl-export" / "export.py"
    export_code = f"exec(open(r'{export_py}', encoding='utf-8').read())"
    rc = _send_to_blender(export_code, args.mcp_host, args.mcp_port)
    if rc != 0:
        print("\033[31mexport failed\033[0m", file=sys.stderr)
        return 1

    # ── 3. Verify STLs ────────────────────────────────────────────────
    _step_header(3, "verify STLs (geometry hygiene)")
    rc = _run(["uv", "run", "nfc-verify-stls"], REPO)
    if rc != 0:
        failures.append("verify-stls")

    # ── 4. Printability check ─────────────────────────────────────────
    if not args.skip_printability:
        _step_header(4, "printability check (slicer-failure gate)")
        rc = _run(["uv", "run", "nfc-printability-check"], REPO)
        if rc != 0:
            failures.append("printability-check")

    # ── 5. Build 3MF ──────────────────────────────────────────────────
    _step_header(5, "build slicer-ready 3MF")
    rc = _run(["uv", "run", "nfc-make-3mf"], REPO)
    if rc != 0:
        print("\033[31m3MF build failed\033[0m", file=sys.stderr)
        return 1

    # ── 6. Copy artifacts to bead's print dir ─────────────────────────
    _step_header(6, f"copy artifacts -> {print_dir.relative_to(REPO)}/")
    latest = REPO / "tmp" / "latest"
    copied = []
    for stl in latest.glob("*.stl"):
        dst = print_dir / stl.name
        shutil.copy2(stl, dst)
        copied.append(dst.name)
    bead_3mf = latest / "bead.3mf"
    charm_3mf = print_dir / f"{charm}.3mf"
    if bead_3mf.exists():
        shutil.copy2(bead_3mf, charm_3mf)
        copied.append(charm_3mf.name)
    print("  copied: " + ", ".join(copied))

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if failures:
        print(f"\033[33mbead-build complete with warnings: {', '.join(failures)}\033[0m")
        print(f"  3MF: {charm_3mf.relative_to(REPO)}  (review warnings before slicing)")
        return 0   # warnings don't fail the chain
    print(f"\033[32mbead-build OK\033[0m  -> {charm_3mf.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
