---
name: nfc-bead
description: Build a two-half snap-fit NFC charm/bead from a 2D silhouette SVG. Use when the user wants to design or build a new NFC-tagged charm, bead, or pendant — anything that needs to host a 10mm NTAG215 sticker between two press-fit halves with a string hole. Triggers on "new charm", "NFC bead", "make a [thing] charm", "build a charm with NFC", or similar. Loads the technical recipe from prompts/nfc-bead/prompt.md so the user can focus on the creative/aesthetic side.
---

# NFC Bead Skill

You are helping the user design and build a new two-half snap-fit NFC charm. The technical recipe — dimensions, build pipeline, gotchas — lives in `prompts/nfc-bead/prompt.md`. Read it first, then drive the conversation toward the creative side.

## What to do when invoked

1. **Read `prompts/nfc-bead/prompt.md`** to load the full recipe into context.
2. **Read `build_charm.py.example`** to see the canonical Blender pipeline implementation. This is what you'll copy and adapt per charm.
3. **Read `GUIDE.md`** for long-form context on lessons learned.
4. **Ask the user** for what they actually need to make creative decisions on:
   - The silhouette: SVG path on disk, or a description (offer to sketch via SVG if needed).
   - String-hole position: usually through the head/top of the silhouette along the long axis. Specify Y in mm.
   - Any dimension overrides (default is 25mm wide, 5mm thick, 10.5mm × 0.8mm NFC pocket, 3 pegs).
   - Theme/aesthetic notes for naming and any flourishes.
5. **Propose** peg positions and NFC pocket center based on the silhouette's bounding box and interior — show the user before building. Triangulated, ≥1mm clear of NFC pocket / string hole / silhouette edge.
6. **Build**: copy `build_charm.py.example` to a per-charm script (e.g. `build_<name>.py`), update the CONFIG block at the top, run via `blender --background --python build_<name>.py` (or via the Blender MCP if connected).
7. **Verify** with the built-in raycast checks the script prints. If any peg lands outside the silhouette or overlaps the NFC cavity, iterate on positions.
8. **Export** both STLs and report dimensions back.

## Tools available

- **Blender MCP** (configured in `.mcp.json` as `blender`) — direct Blender control if the user has the Blender MCP addon running. Useful for live-iterating geometry before committing to the script.
- **Headless Blender** via `blender --background --python <script>.py` — repeatable, what the script targets.
- Standard file tools (Read/Write/Edit) for the SVG and script.

## What to NOT do

- Don't skip the verification raycasts — peg placement is the most common failure mode.
- Don't change the build pipeline order without re-reading the gotchas section in the prompt (split-before-peg-holes is non-obvious and silently produces broken parts).
- Don't propose peg positions without seeing the silhouette geometry — the bounding box alone isn't enough; you need to know where the silhouette is solid.
- Don't generate STL output without raycast-verifying the string hole and all peg holes are open and the pegs all land on solid material.

## Output

Produce two STL files (`<name>_top.stl`, `<name>_bottom.stl`) plus the editable `.blend` file. Report the final bounding-box dimensions and confirm 0 non-manifold edges before declaring success.
