# CLAUDE.md — guidance for Claude Code in this repo

This repo is a **template / recipe** for designing two-half snap-fit NFC charms (beads) from a 2D silhouette. It's not a single-product codebase — each branch typically hosts one specific charm built on top of the recipe.

## Where to look

- **`prompts/nfc-bead/prompt.md`** — the technical recipe (dimensions, pipeline order, gotchas). Read this first when starting a new charm.
- **`build_charm.py.example`** — canonical Blender pipeline. Copy to `build_<name>.py` and edit the CONFIG block at the top.
- **`GUIDE.md`** — long-form lessons-learned walkthrough.
- **`SETUP.md`** — one-time and per-session setup for the live Blender MCP workflow (Windows-focused; macOS / Linux outlined).
- **`.claude/skills/nfc-bead/`** — the `nfc-bead` skill that auto-loads on charm requests. Bundles the Blender MCP addon source.
- **`.mcp.json`** — wires up `uvx blender-mcp` as a project-scoped MCP server. Loaded at Claude Code startup.

## Working norms in this repo

- **Live MCP, not headless, when the user is watching.** If the user is in this repo and the Blender MCP is connected (`mcp__blender__*` tools available), prefer driving Blender live so they can see and steer. Fall back to headless `blender --background --python` only if MCP is unavailable.
- **Branches host charms.** `main` holds the generic recipe. Per-charm work lives on its own branch (e.g. `rezz` for the Rezz bead). Setup / pipeline improvements that aren't charm-specific should land on `main`.
- **Multi-color outputs are the norm for users with multi-filament printers.** When generating a build script, default to emitting separate STLs per color region (body, accent), all sharing the same coordinate origin so they assemble cleanly in the slicer.
- **Show the user the layout before booleans.** Peg placement is the most common failure mode; propose positions and let the user confirm (ideally with a viewport screenshot when MCP is live) before running booleans.
- **Verify with raycasts before declaring success.** The build script template includes raycast checks for the string hole and each peg hole — do not skip them.

## Conventions

- Default charm dimensions live in `prompts/nfc-bead/prompt.md` — override per charm in the CONFIG block, don't edit the recipe.
- Output STLs go to `out/` (gitignored).
- The `.blend` file is exported alongside the STLs so the user can inspect afterward even on headless runs.
