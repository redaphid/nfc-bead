# CLAUDE.md — guidance for Claude Code in this repo

This repo is a **template / recipe** for designing two-half snap-fit NFC charms (beads) from a 2D silhouette. It's not a single-product codebase — each branch typically hosts one specific charm built on top of the recipe.

## Where to look

- **`prompts/nfc-bead/prompt.md`** — the technical recipe (dimensions, pipeline order, gotchas). Read this first when starting a new charm.
- **`build_charm.py.example`** — canonical Blender pipeline. Copy to `beads/<name>/build_<name>.py` and edit the CONFIG block at the top.
- **`beads/<name>/`** — per-charm work tree (silhouette, build script, stage `.blend` snapshots with notes, final STLs). The active branch usually owns one bead here.
- **`GUIDE.md`** — long-form lessons-learned walkthrough.
- **`SETUP.md`** — one-time and per-session setup for the live Blender MCP workflow (Windows-focused; macOS / Linux outlined).
- **`tools/launch.ps1`** + **`tools/blender_bootstrap.py`** — one-shot launcher that opens Blender with the addon installed/enabled and the MCP server running. Use this when the user wants to start (or restart after a crash) the live workflow. Don't walk them through the manual click-through unless they specifically ask.
- **`.claude/skills/nfc-bead/`** — the `nfc-bead` skill that auto-loads on charm requests. Bundles the Blender MCP addon source.
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
