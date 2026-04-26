"""CLI: switch the live Blender scene to a stored animation.

Wraps `bead-architect-mode/anim_switch.py` so the user can run from a
shell prompt without typing the exec() boilerplate:

    uv run nfc-anim-switch orbit
    uv run nfc-anim-switch tour
    uv run nfc-anim-switch _LIST          # show all stored anims

Requires a running Blender with the BlenderMCP socket addon enabled
(launch via `tools/launch.ps1`).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWITCHER  = os.path.join(REPO_ROOT, ".claude", "skills", "bead-architect-mode", "anim_switch.py")


def _send(code: str, host: str = "localhost", port: int = 9876, timeout: int = 30):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
    except (ConnectionRefusedError, socket.timeout) as e:
        return {"status": "error",
                "message": f"Cannot reach Blender on {host}:{port} — is it running with the BlenderMCP addon enabled? ({e})"}
    msg = json.dumps({"type": "execute_code", "params": {"code": code}}).encode("utf-8")
    s.sendall(msg)
    buf = b""
    while True:
        try:
            chunk = s.recv(65536)
        except socket.timeout:
            break
        if not chunk:
            break
        buf += chunk
        try:
            json.loads(buf.decode("utf-8"))
            break
        except json.JSONDecodeError:
            continue
    s.close()
    if not buf:
        return {"status": "error", "message": "no response"}
    try:
        return json.loads(buf.decode("utf-8"))
    except json.JSONDecodeError:
        return {"status": "error", "message": f"non-json response: {buf[:200]!r}"}


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument(
        "anim",
        nargs="?",
        default="_LIST",
        help="anim name (orbit, macro_pull, raking_light, tour, locked_profile, top_down) or _LIST",
    )
    args = p.parse_args()

    if not os.path.isfile(SWITCHER):
        print(f"ERROR: switcher script not found: {SWITCHER}", file=sys.stderr)
        return 1

    with open(SWITCHER, encoding="utf-8") as fh:
        switcher_src = fh.read()

    # Inject ANIM_NAME into the exec scope BEFORE the switcher runs.
    code = (
        f"ANIM_NAME = {args.anim!r}\n"
        + switcher_src
    )
    resp = _send(code)
    if resp.get("status") == "error":
        print(f"ERROR: {resp.get('message')}", file=sys.stderr)
        return 1
    out = resp.get("result", {})
    if isinstance(out, dict) and "result" in out:
        print(out["result"], end="")
    else:
        print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
