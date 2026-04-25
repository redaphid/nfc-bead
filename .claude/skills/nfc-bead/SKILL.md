---
name: nfc-bead
description: Build a two-half snap-fit NFC charm/bead from a 2D silhouette SVG. Use when the user wants to design or build a new NFC-tagged charm, bead, or pendant — anything that needs to host a 10mm NTAG215 sticker between two press-fit halves with a string hole. Triggers on "new charm", "NFC bead", "make a [thing] charm", "build a charm with NFC", or similar. Loads the technical recipe from prompts/nfc-bead/prompt.md so the user can focus on the creative/aesthetic side.
---

# NFC Bead Skill

You are helping the user design and build a new two-half snap-fit NFC charm. The technical recipe — dimensions, build pipeline, gotchas — lives in `prompts/nfc-bead/prompt.md`. Read it first, then drive the conversation toward the creative side.

## What to do when invoked

1. **Branch off `main` first.** Per-charm work never lives on `main`. Run `git status` to see the current branch — if the user is on `main` (or any branch that isn't named after this charm), create the charm branch before touching geometry:
   ```bash
   git checkout main && git pull --ff-only
   git checkout -b <bead-name>          # name should match the charm — e.g. `rezz`, `wooli`
   ```
   If they're already on a charm branch (e.g. resuming work), confirm and continue. If unsure what to name the branch, ask the user — usually the charm's theme/subject is the right name (`rezz`, `mammoth`, `octopus`).
2. **Read `prompts/nfc-bead/prompt.md`** to load the full recipe into context.
3. **Read `build_charm.py.example`** to see the canonical Blender pipeline implementation. This is what you'll copy and adapt per charm.
4. **Read `GUIDE.md`** for long-form context on lessons learned.
5. **Ask the user** for what they actually need to make creative decisions on:
   - The silhouette: SVG path on disk, or a description (offer to sketch via SVG if needed).
   - String-hole position: usually through the head/top of the silhouette along the long axis. Specify Y in mm.
   - Any dimension overrides (default is 25mm wide, 5mm thick, 10.5mm × 0.8mm NFC pocket, 3 pegs).
   - Theme/aesthetic notes for naming and any flourishes.
6. **Propose** peg positions and NFC pocket center based on the silhouette's bounding box and interior — show the user before building. Triangulated, ≥1mm clear of NFC pocket / string hole / silhouette edge.
7. **Build**: copy `build_charm.py.example` to a per-charm script at `beads/<name>/build_<name>.py`, update the CONFIG block at the top, run via the Blender MCP if connected (preferred) or `blender --background --python beads/<name>/build_<name>.py` headless.
8. **Verify** with the built-in raycast checks the script prints. If any peg lands outside the silhouette or overlaps the NFC cavity, iterate on positions.
9. **Export** STLs to `beads/<name>/print/` and report dimensions back. Commit + push to the charm branch frequently as work progresses.

## Tools available

- **Blender MCP** (configured in `.mcp.json` as `blender`) — direct Blender control if the user has the Blender MCP addon running. Useful for live-iterating geometry before committing to the script.
- **Headless Blender** via `blender --background --python <script>.py` — repeatable, what the script targets.
- **`tools/launch.ps1`** — Windows one-shot launcher that opens Blender with the addon installed/enabled and the MCP server running. Wraps `tools/blender_bootstrap.py` (idempotent: copies-if-stale → enables → saves prefs → starts server).
- Standard file tools (Read/Write/Edit) for the SVG and script.

## Helping the user get into a working live-MCP state

If the user wants the live Blender MCP workflow but doesn't have it running yet, walk them through this — don't just hand them `SETUP.md`. The dance is:

1. **Verify prerequisites.** Blender 4.x+ installed (default `D:\tools\blender\blender.exe` on Windows; override via env `NFC_BEAD_BLENDER`) and `uvx` on `PATH` (winget package `astral-sh.uv`). If either is missing, install it before continuing — `winget install BlenderFoundation.Blender astral-sh.uv` (open a fresh shell after `uv` so PATH refreshes).
2. **Use `tools/launch.ps1`** for everything. It's idempotent and one-shot:
   ```powershell
   .\tools\launch.ps1                       # opens Blender pre-wired for the rezz bead
   .\tools\launch.ps1 -Bead <other>         # different bead from beads/<other>/
   .\tools\launch.ps1 -BlendFile foo.blend  # arbitrary file
   ```
   The launcher calls `tools/blender_bootstrap.py` inside Blender, which copies the bundled addon into the user-addons directory if missing/stale, enables it persistently (`addon_utils.enable(..., persistent=True)`), saves user prefs (so a Blender crash doesn't wipe the enable state), and starts the MCP server.
3. **After Blender opens**, run `/mcp` in this Claude Code session to (re)connect. On a fresh Claude Code session, the bridge auto-connects on startup. On an existing session, `/mcp` retries.
4. **If `/mcp` reports "Failed to reconnect to blender"**: usually means the addon's "Connect to Claude" hasn't fired yet. Wait a beat (the bootstrap defers it 1 s) and `/mcp` again. If it still fails, the bootstrap output is in Blender's terminal — ask the user to check it.

**When NOT to use the launcher:** if Blender is already running with a connected MCP and a useful scene loaded, don't re-launch — you'll lose the scene. Just resume.

**When the user says "Blender crashed":** re-run `tools/launch.ps1` (preserving any `-Bead` or `-BlendFile` they had); the bootstrap is idempotent so this is the right answer every time.

**When working live:** the build pipeline saves `beads/<bead>/print/<bead>_charm.blend` after each successful end-to-end build, so re-launching with `-Bead <bead>` drops you back into the last good state.

## What to NOT do

- Don't skip the verification raycasts — peg placement is the most common failure mode.
- Don't change the build pipeline order without re-reading the gotchas section in the prompt (split-before-peg-holes is non-obvious and silently produces broken parts).
- Don't propose peg positions without seeing the silhouette geometry — the bounding box alone isn't enough; you need to know where the silhouette is solid.
- Don't generate STL output without raycast-verifying the string hole and all peg holes are open and the pegs all land on solid material.

## Output

Produce two STL files (`<name>_top.stl`, `<name>_bottom.stl`) plus the editable `.blend` file. Report the final bounding-box dimensions and confirm 0 non-manifold edges before declaring success.
