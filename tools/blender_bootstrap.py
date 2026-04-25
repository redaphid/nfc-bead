"""Bootstrap Blender into the live-MCP working state.

Idempotent: copies the bundled BlenderMCP addon into the user-addons directory
(if missing or stale), enables it, saves user prefs so the enable persists past
the next crash, and starts the MCP server.

Run via:
    blender.exe --python tools/blender_bootstrap.py
    blender.exe path/to/some.blend --python tools/blender_bootstrap.py

Use the `tools/launch.ps1` wrapper to pick this up with sane defaults.
"""
import bpy, os, shutil

HERE       = os.path.dirname(os.path.abspath(__file__))
REPO       = os.path.dirname(HERE)
ADDON_SRC  = os.path.join(REPO, ".claude", "skills", "nfc-bead", "blender_mcp_addon.py")
ADDON_NAME = "blender_mcp_addon"

# 1. Copy addon into Blender's user-addons directory if missing or older than source
addons_dir = bpy.utils.user_resource('SCRIPTS', path='addons')
os.makedirs(addons_dir, exist_ok=True)
addon_dst  = os.path.join(addons_dir, ADDON_NAME + ".py")
needs_copy = (not os.path.exists(addon_dst)) or (os.path.getmtime(ADDON_SRC) > os.path.getmtime(addon_dst))
if needs_copy:
    shutil.copy2(ADDON_SRC, addon_dst)
    print(f"[bootstrap] addon copied:  {ADDON_SRC}\n               -> {addon_dst}")
else:
    print(f"[bootstrap] addon up to date: {addon_dst}")

# 2. Refresh module cache then enable (persistent so it survives crashes)
import addon_utils
addon_utils.modules_refresh()
addon_utils.enable(ADDON_NAME, default_set=True, persistent=True)
print(f"[bootstrap] addon enabled: {ADDON_NAME}")

# 3. Save user preferences so addon enable-state outlives a crash
bpy.ops.wm.save_userpref()
print("[bootstrap] user preferences saved")

# 4. Start the MCP server. Defer via timer so context is fully ready.
def _start_mcp():
    try:
        bpy.ops.blendermcp.start_server()
        port = getattr(bpy.context.scene, 'blendermcp_port', 9876)
        print(f"[bootstrap] MCP server listening on port {port}")
        print("[bootstrap] now restart Claude Code (or run /mcp) to connect")
    except Exception as e:
        print(f"[bootstrap] start_server failed (click 'Connect to Claude' manually): {e}")
    return None    # don't reschedule

bpy.app.timers.register(_start_mcp, first_interval=1.0)
