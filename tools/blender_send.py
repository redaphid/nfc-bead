#!/usr/bin/env python3
"""Send Python code to a running Blender's BlenderMCP socket.

Bypasses the Claude-Code MCP layer — useful when the MCP server got
disconnected but Blender is still up. The BlenderMCP addon listens on
localhost:9876 by default and expects JSON
    {"type": "execute_code", "params": {"code": "..."}}
returning JSON
    {"status": "success", "result": {"executed": true, "result": "<stdout>"}}
or
    {"status": "error", "message": "..."}.

Usage:
    python tools/blender_send.py < snippet.py
    python tools/blender_send.py -c "import bpy; print(len(bpy.data.objects))"
    python tools/blender_send.py -f .claude/skills/bead-architect-mode/architect_on.py
"""
import argparse
import json
import socket
import sys


def send(code, host="localhost", port=9876, timeout=180):
    msg = json.dumps({"type": "execute_code", "params": {"code": code}}).encode("utf-8")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
    except (TimeoutError, ConnectionRefusedError) as e:
        return {"status": "error", "message": f"Cannot reach Blender on {host}:{port} — is it running with the BlenderMCP addon enabled? ({e})"}

    s.sendall(msg)
    buf = b""
    while True:
        try:
            chunk = s.recv(65536)
        except TimeoutError:
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
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group()
    g.add_argument("-c", "--code", help="inline python code")
    g.add_argument("-f", "--file", help="path to a python file to read and execute")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=9876)
    p.add_argument("--timeout", type=int, default=180)
    args = p.parse_args()

    if args.code:
        code = args.code
    elif args.file:
        with open(args.file, encoding="utf-8") as fh:
            code = fh.read()
    else:
        code = sys.stdin.read()

    resp = send(code, host=args.host, port=args.port, timeout=args.timeout)
    if resp.get("status") == "error":
        print(f"ERROR: {resp.get('message')}", file=sys.stderr)
        sys.exit(1)
    result = resp.get("result", {})
    if isinstance(result, dict) and "result" in result:
        # The 'result' field of execute_code is the captured stdout
        print(result["result"], end="")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
