# Setup — Blender MCP for live charm building

This is the one-time setup so Claude can drive Blender live (you watch geometry build in the viewport and can steer mid-build).

## On this machine (already done)

- Blender 5.0.1 at `D:\tools\blender\blender.exe`
- `uvx` (Astral) installed via winget — `uvx 0.11.7`
- Project `.mcp.json` configured to spawn `uvx blender-mcp`
- Blender MCP addon downloaded to `.claude/skills/nfc-bead/blender_mcp_addon.py` (versioned with the skill; no need to re-download)

## One-time Blender addon install

1. Open Blender (`D:\tools\blender\blender.exe`)
2. **Edit → Preferences → Add-ons**
3. Click **Install from Disk...** (top-right dropdown in newer Blender; was just "Install" in older versions)
4. Pick `D:\Projects\nfc-bead\.claude\skills\nfc-bead\blender_mcp_addon.py`
5. Search the addon list for `MCP` and tick the box next to **Interface: Blender MCP** to enable it
6. Close Preferences

## Per-session: start the bridge

Inside Blender (every time you want a live MCP session):

1. In the 3D viewport press **N** to open the right sidebar
2. Click the **BlenderMCP** tab (vertical text on the sidebar edge)
3. Click **Connect to Claude** — this starts a socket server inside Blender (default port 9876)

Inside Claude Code:

4. Restart Claude Code so it picks up `.mcp.json` and spawns `uvx blender-mcp`. The bridge connects to the socket Blender opened.
5. After restart, ask Claude to do something Blender-y; the MCP tools (`mcp__blender__*`) should be available. If not, run `/mcp` to see server status.

## Stopping

- Click **Disconnect** in the BlenderMCP sidebar tab in Blender, or just close Blender
- The `uvx blender-mcp` process stops when Claude Code exits

## Why a restart is needed

Claude Code reads `.mcp.json` only at startup. If you add or change MCP servers mid-session, you have to restart Claude Code to register them. (Project-scoped servers like ours are loaded from `.mcp.json` in the working directory.)

## Troubleshooting

- **`/mcp` shows blender as failed**: Blender isn't running, or the addon's "Connect to Claude" isn't clicked, or another process is holding port 9876.
- **`uvx` not found**: refresh PATH — winget puts it under `%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_*\`. New shells should pick it up; existing ones may need to be restarted.
- **Addon doesn't appear in the list after install**: search literally "MCP" — Blender filters by description not file name. The display name is "Interface: Blender MCP".
