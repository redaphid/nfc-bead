# Setup — Blender MCP for live charm building

This is the one-time setup so Claude Code can drive Blender live (you watch geometry build in the viewport and can steer mid-build). Headless `blender --background --python <script>.py` works without any of this — only set up the MCP if you want the live workflow.

The repo is platform-agnostic, but the prerequisites differ by OS. Windows is the most thoroughly tested path; macOS / Linux are sketched at the bottom.

## Prerequisites

You need three things, regardless of OS:

1. **Blender 4.x or newer** (tested on 5.0.1)
2. **`uvx`** (from [Astral `uv`](https://astral.sh/uv)) — runs the Blender MCP bridge
3. **The Blender MCP addon** — bundled in this repo at `.claude/skills/nfc-bead/blender_mcp_addon.py` (sourced from [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp))

The repo's `.mcp.json` is already wired to spawn `uvx blender-mcp` when Claude Code starts in this directory. So once Blender + `uvx` exist and the addon is enabled, the bridge connects automatically on Claude Code startup.

## Windows setup

### One-time installs

```powershell
winget install BlenderFoundation.Blender    # if not already installed
winget install astral-sh.uv                 # provides uv + uvx
```

After installing `uv`, **open a fresh terminal** so `PATH` picks up the new binary. The freshly installed `uvx.exe` lives under `%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_*\` and is added to user `PATH` by the installer.

If Blender lives somewhere non-standard (e.g. a portable install under `D:\tools\blender`), it doesn't need to be on `PATH` for the MCP — but for headless runs you'll invoke its full path directly.

### Install the Blender addon (one-time)

1. Open Blender
2. **Edit → Preferences → Add-ons**
3. Top-right dropdown → **Install from Disk...** *(in older Blender, just an "Install" button)*
4. Pick `<repo>\.claude\skills\nfc-bead\blender_mcp_addon.py`
5. In the addon list, type `MCP` in the search box → tick the checkbox next to **Interface: Blender MCP**
6. Close Preferences

### Per-session: bring up the bridge

Inside Blender (every time you want a live MCP session):

1. In the 3D viewport press **N** to open the right sidebar
2. Click the **BlenderMCP** tab (vertical text on the sidebar's edge)
3. Click **Connect to Claude** — this starts a socket inside Blender on port 9876

Inside Claude Code:

4. Restart Claude Code so it picks up `.mcp.json` and spawns `uvx blender-mcp`. The bridge then connects to the socket Blender just opened.
5. After restart, run `/mcp` — the `blender` server should show **connected**. If you previously had a session running with `blender` failed, `/mcp` will retry the connection automatically and report **Reconnected to blender.**

If `/mcp` keeps reporting **Failed to reconnect to blender**, it means `uvx blender-mcp` is running but can't reach the addon's socket. Double-check the addon is enabled (step 6 above) and that you clicked **Connect to Claude** in the BlenderMCP sidebar tab.

## macOS / Linux

Same shape, different installers. Use Homebrew / the package manager / the distro repo for Blender, then `curl -LsSf https://astral.sh/uv/install.sh | sh` for `uv`. The addon install and per-session bring-up steps are identical.

## Why a Claude Code restart is needed

Claude Code reads `.mcp.json` only at startup. Even if you add the addon to a running Blender mid-session, the `uvx blender-mcp` bridge process must already be running, which only happens at Claude Code startup. So the order is always: **install addon → click "Connect to Claude" in Blender → restart Claude Code**.

## Stopping

- Click **Disconnect** in the BlenderMCP sidebar tab in Blender, or close Blender
- The `uvx blender-mcp` bridge process stops when Claude Code exits

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/mcp` shows blender failed | Addon not enabled, or "Connect to Claude" not clicked | Enable addon + click connect, then `/mcp` to retry |
| `uvx` not found | Fresh terminal hasn't picked up new PATH | Open a new shell after installing `uv` |
| Addon doesn't appear in install list | Blender filters by description text | Search literally `MCP` — display name is "Interface: Blender MCP" |
| Port 9876 in use | Another process holds it (or a stale Blender) | Kill the holder, or change the port in the BlenderMCP sidebar |
| MCP works but tools missing in Claude | `/mcp` shows blender connected but no `mcp__blender__*` tools | Restart Claude Code — tool schemas register at startup |
