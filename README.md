# nfc-bead

Reusable scaffolding for designing two-half snap-fit NFC charms / beads from a 2D silhouette SVG. Built around a Blender + Python pipeline that handles the boring mechanical bits (split, pegs, NFC pocket, string hole) so creative sessions can focus on the silhouette and aesthetic.

First charm built with this recipe: the [Wooli mammoth](https://github.com/redaphid/wooli-bead) (private). This repo is the template extracted from that work.

## What's in here

| Path | Purpose |
|---|---|
| `prompts/nfc-bead/prompt.md` | The technical recipe — dimensions, pipeline order, gotchas. Drop this into any new Claude session as the scaffolding for a new charm. |
| `.claude/skills/nfc-bead/SKILL.md` | Claude Code skill that auto-triggers on new-charm requests, loads the prompt, and drives the workflow. |
| `.claude/settings.json` | Project Claude settings — pre-allows Blender / uvx / python invocations. |
| `.mcp.json` | Project-level MCP server config. Wires up the Blender MCP server (`uvx blender-mcp`). |
| `build_charm.py.example` | Reference implementation of the full Blender pipeline. Copy to `build_<charm>.py` and edit the CONFIG block at the top per charm. |
| `GUIDE.md` | Long-form walkthrough with lessons learned from the original Wooli build. |

## Quick start

1. Open this repo in Claude Code. The `nfc-bead` skill auto-loads.
2. Say something like: *"new charm — here's the silhouette"* and attach an SVG. The skill reads the prompt, asks the right questions, and walks the build.
3. Or, manually: read `prompts/nfc-bead/prompt.md` yourself, copy `build_charm.py.example`, edit the CONFIG block, run headless:
   ```
   blender --background --python build_yourcharm.py
   ```

## MCP — Blender

`.mcp.json` configures the [Blender MCP](https://github.com/ahujasid/blender-mcp) server (`uvx blender-mcp`). To use it live (for iterating geometry interactively rather than via headless script):

1. Install the Blender MCP addon in Blender (see upstream docs).
2. Start the addon server inside Blender.
3. `uvx` must be on `PATH` (install via [astral.sh/uv](https://astral.sh/uv)).
4. Approve the server when Claude prompts.

Headless `blender --background --python` works without the MCP — the MCP is only for live interactive sessions.

## Default charm spec

| Feature | Value |
|---|---|
| Width | 25 mm (sized for Kandi bracelets) |
| Thickness | 5 mm (2.5 mm × 2 halves) |
| String hole | 2 mm dia, X-axis through head |
| NFC pocket | 10.5 mm dia × 0.8 mm deep (NTAG215, 10mm sticker) |
| Pegs | 3 × 2 mm dia × 1.5 mm tall, 0.1 mm clearance per side |

Override any of these per charm in the CONFIG block.

## Print settings

PLA or PETG, 0.12–0.16 mm layers, 100% infill, no supports. Bottom half flipped 180° around X (pegs face up, silhouette on build plate). Top half prints with peg-hole face on the build plate.

## License

Private template repo. Do whatever you want with it.
