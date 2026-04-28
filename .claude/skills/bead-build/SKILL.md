---
name: bead-build
description: One-shot orchestration of the full bead pipeline — rebuild the live Blender scene from the charm's build script, export STLs, verify geometry, run printability checks, build the 3MF, and copy print artifacts to beads/<charm>/print/. Use after editing a build_<charm>.py CONFIG block, or after Blender edits when you want a slicer-ready 3MF in one trigger. Triggers on "rebuild and export", "build the bead", "ship to slicer", "run the full pipeline", or similar.
---

# Bead Build — pipeline orchestration

A single skill that chains every step from "edited the build script" to "ready-to-slice 3MF in the bead's print/ dir". Each step in the chain already works as a standalone (and should be invoked individually when iterating mid-pipeline); this skill is the "I'm done iterating, give me the artifact" trigger.

## What it runs, in order

```
1. rebuild — Blender MCP exec of beads/<charm>/build_<charm>.py
              with namespace {"__name__": "__main__"} so main() fires
2. export  — exec bead-stl-export's export.py inside the same Blender,
              produces tmp/latest/*.stl
3. verify  — uv run nfc-verify-stls (manifold, dimensions, alignment)
4. check   — uv run nfc-printability-check (wall-above-hole,
              cantilever, peg edges, bed contact)
5. 3mf     — uv run nfc-make-3mf, writes tmp/latest/bead.3mf
6. copy    — cp tmp/latest/{*.stl,bead.3mf} into beads/<charm>/print/
              (renames bead.3mf → <charm>.3mf for clarity)
```

Each step is short-circuiting: if step 1 (Blender rebuild) fails, the chain stops with the error. If step 3 (verify) reports failures the chain continues but flags them — the user sees what's wrong before the 3MF lands. Printability check failures are also non-fatal — they're warnings the user reads before sending to the slicer.

## How to invoke

```sh
# Auto-detect charm from current branch name (matches beads/<branch>/)
uv run nfc-bead-build

# Explicit charm
uv run nfc-bead-build --charm redaphid-portrait
```

Requires Blender MCP connected (steps 1-2 use it). If it's not, the skill prints a "/mcp to reconnect" hint and exits.

## When to use

- After editing the build script's CONFIG block (`HOLE_Y`, peg positions, dimensions). Saves typing four chained commands.
- After hand-editing geometry in Blender that you want captured into the printable artifacts.
- Before opening the slicer — confirms the 3MF is fresh and the geometry is valid.

## When NOT to use

- Mid-iteration when only ONE step is what you need. If you just want to re-verify after a slicer rejected a print, run `nfc-verify-stls` directly.
- If the build script is in a known-broken state. The orchestrator's job is to *run* the chain, not to fix upstream errors.
- If you don't have a build script for the current charm yet (still drafting). Build interactively first; orchestrate once it's stable.

## Failure modes the orchestrator surfaces

| Step | Failure surfaces as | What to do |
|---|---|---|
| 1 (rebuild) | Blender MCP error / Python traceback in build script | Fix the build script; re-run |
| 2 (export) | Non-manifold warnings, missing canonical objects | Investigate in Blender; re-run |
| 3 (verify) | Dimension or watertight failure | Iterate on the build params or skill |
| 4 (check) | Cantilever / wall / peg-edge warnings | Decide whether to print anyway or iterate |
| 5 (3mf) | lib3mf import or write error | Check the latest STL set is intact |
| 6 (copy) | Permission / missing dir | mkdir -p the bead's print/ dir |

## What this skill does NOT do

- It does not push or commit. The orchestrator stops at the print/ dir; the user reviews and commits when satisfied.
- It does not auto-fix issues. Failures are reported, not patched.
- It does not run the slicer. The 3MF lands in print/; the user drags it into Elegoo Slicer / Bambu Studio.
