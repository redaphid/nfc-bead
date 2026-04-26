# CLAUDE.md — guidance for Claude Code in this repo

This repo is a **template / recipe** for designing two-half snap-fit NFC charms (beads) from a 2D silhouette. It's not a single-product codebase — each branch typically hosts one specific charm built on top of the recipe.

## Greet the user on the first turn of a session on `main`

When the user opens this repo in Claude Code and sends their first message of the session, **and they're on the `main` branch** (i.e. they haven't checked out a charm branch yet), open your reply with a short orientation before answering. Skip the greeting on subsequent turns, and skip it entirely if they're already on a charm branch — they know what they're doing.

The greeting should be terse (≤10 lines) and cover:

1. **What this repo does** — turns a 2D silhouette into a 3D-printable two-half NFC charm with a snap-fit and a string hole.
2. **The workflow** — they describe the charm they want; I branch off `main` into a `<bead-name>` branch, drive Blender live (via the Blender MCP) to build it, and export STLs into `beads/<name>/print/`.
3. **What they need installed** — Blender 4.x+ and `uvx`. If missing, I can install via winget. The Blender MCP addon is bundled in this repo (no separate download).
4. **How to start** — they can either describe a charm directly ("make a Rezz spiral bead", "I want an octopus charm") or ask `/mcp` to check if the live Blender bridge is connected. If not connected, I'll run `tools/launch.ps1` to bring it up.

After the greeting, answer whatever they actually asked. If their first message **was** a charm request, the greeting is one or two sentences ("Welcome — I'll branch into `<name>` and we'll build it together"), then go straight into the work.

Don't repeat the greeting on later turns even if the conversation pauses; once is enough per session.

## Where to look

- **`prompts/nfc-bead/prompt.md`** — the technical recipe (dimensions, pipeline order, gotchas). Read this first when starting a new charm.
- **`build_charm.py.example`** — canonical Blender pipeline. Copy to `beads/<name>/build_<name>.py` and edit the CONFIG block at the top.
- **`beads/<name>/`** — per-charm work tree (silhouette, build script, stage `.blend` snapshots with notes, final STLs). The active branch usually owns one bead here.
- **`GUIDE.md`** — long-form lessons-learned walkthrough.
- **`SETUP.md`** — one-time and per-session setup for the live Blender MCP workflow (Windows-focused; macOS / Linux outlined).
- **`tools/launch.ps1`** + **`tools/blender_bootstrap.py`** — one-shot launcher that opens Blender with the addon installed/enabled and the MCP server running. Use this when the user wants to start (or restart after a crash) the live workflow. Don't walk them through the manual click-through unless they specifically ask.
- **`tools/blender_send.py`** — sends Python code directly to the BlenderMCP socket (`localhost:9876`). Use when the Claude Code MCP layer has dropped but Blender is still up.
- **`pyproject.toml`** — uv-managed Python project. Host-side CLI commands (run via `uv run <name>`):
  - `nfc-blender-send` — send code to Blender's MCP socket (alternative to `python tools/blender_send.py`)
  - `nfc-verify-stls` — load `tmp/latest/*.stl` via trimesh, run 14+ structural checks, exit non-zero on any failure
  - `nfc-make-3mf` — generic 3MF Consortium bundle of the latest STLs (no slicer-specific config)
  - `nfc-build-3mf` — slicer-ready Bambu Studio / Elegoo Slicer 3MF with parts pre-merged, extruders assigned, brim/raft disabled, printer profile inherited from a reference template at `tmp/latest/slicer_template/`
- **`samples/rezz_sample.blend`** — tracked reference scene with canonical `Bottom`/`Top`/`Decoration` objects. `tools/launch.ps1` falls back to this when no charm-specific blend exists, so the architect / debug-overlays / stl-export skills always have something to act on.
- **`print/PRINT_GUIDE.md`** — multi-color print workflow for the Centauri Carbon 2 / Elegoo Slicer (filament assignment, layer height, wipe tower, slice verification).
- **`.claude/skills/nfc-bead/`** — auto-loads on charm requests. Bundles the Blender MCP addon source.
- **`.claude/skills/bead-debug-overlays/`** — CAD palette + DBG_* overlays for hidden structural features. Canonical object names: `Bottom`, `Top`, `Decoration`.
- **`.claude/skills/bead-architect-mode/`** — parchment+ink aesthetic + cinematic camera animations (`architect_on.py`, `anim_*.py`, `architect_off.py`).
- **`.claude/skills/theater-mode/`** — protocol and quality bar for iterating on the architect aesthetic. The "Westworld bar" + screenshot-verified iteration loop.
- **`.claude/skills/bead-stl-export/`** — defensive STL export with deterministic per-part print-orientation flip; strips MA_* and DBG_* first.
- **`.mcp.json`** — wires up `uvx blender-mcp` as a project-scoped MCP server. Loaded at Claude Code startup.

## Working norms in this repo

- **Branches host charms — always start a new bead on its own branch off `main`.** The first thing to do when a new charm session begins is to confirm the user is on a current `main`, then create a branch named after the bead:
  ```bash
  git checkout main && git pull --ff-only
  git checkout -b <bead-name>          # e.g. `rezz`, `wooli`, `octopus`
  ```
  All charm-specific work (silhouette SVG, `build_<name>.py`, `beads/<name>/` tree, stage snapshots, exported STLs, debugging notes) lives on that branch and never lands on `main`. Generic improvements discovered during the build (recipe gotchas, launcher fixes, skill updates) get backported to `main` separately. If the user starts asking for charm-specific changes while on `main`, stop and create the branch first.
- **Live MCP, not headless, when the user is watching.** If the user is in this repo and the Blender MCP is connected (`mcp__blender__*` tools available), prefer driving Blender live so they can see and steer. Fall back to headless `blender --background --python` only if MCP is unavailable.
- **Multi-color outputs are the norm for users with multi-filament printers.** When generating a build script, default to emitting separate STLs per color region (body, accent), all sharing the same coordinate origin so they assemble cleanly in the slicer.
- **Show the user the layout before booleans.** Peg placement is the most common failure mode; propose positions and let the user confirm (ideally with a viewport screenshot when MCP is live) before running booleans.
- **Verify with raycasts before declaring success.** The build script template includes raycast checks for the string hole and each peg hole — do not skip them.

## Conventions

- Default charm dimensions live in `prompts/nfc-bead/prompt.md` — override per charm in the CONFIG block, don't edit the recipe.
- Per-charm outputs (STLs, `.blend`, stage snapshots) live under `beads/<name>/` and are tracked. Only the root-level `out/` and `tmp/` directories are gitignored — those are scratch space, not the canonical artifact location.
- The `.blend` file is exported alongside the STLs so the user can inspect afterward even on headless runs.
