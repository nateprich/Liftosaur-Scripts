"""
Install the production program into Liftosaur as a NEW program (never touches the
user's existing programs). Generates prod-mode Liftoscript from protocol.py and
creates it via the MCP `create_program` tool.

Run:
  python3 -m lifting.install               # create (refuses if name exists)
  python3 -m lifting.install --update      # update the existing one in place
  python3 -m lifting.install --name "..."  # override program name
"""

import argparse
import json
import urllib.request

from . import config
from .evals import generate as G

MCP = "https://www.liftosaur.com/mcp"
DEFAULT_NAME = "T1/T2/T3 Auto-Rotation"


def _call(tool, args):
    key = config.load_key("LIFTOSAUR_API_KEY")
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": tool, "arguments": args}}
    req = urllib.request.Request(MCP, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "User-Agent": "Mozilla/5.0 Chrome/124.0"}, method="POST")
    raw = urllib.request.urlopen(req, timeout=90).read().decode()
    r = json.loads(raw)
    if "error" in r:
        raise RuntimeError(json.dumps(r["error"]))
    return r["result"]["content"][0]["text"]


def _programs():
    """Return [(id, name, isCurrent)] from list_programs (tolerant of format)."""
    txt = _call("list_programs", {})
    try:
        data = json.loads(txt)
        items = data if isinstance(data, list) else data.get("programs", [])
        return [(p.get("id"), p.get("name"), p.get("isCurrent", False)) for p in items]
    except json.JSONDecodeError:
        return [("?", line.strip(), False) for line in txt.splitlines() if line.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default=DEFAULT_NAME)
    ap.add_argument("--update", action="store_true",
                    help="update the existing program with this name instead of creating")
    args = ap.parse_args()

    prog = G.generate(mode="prod")
    print(f"Generated prod program: {len(prog)} bytes, "
          f"{sum(1 for l in prog.splitlines() if l and not l.startswith('#'))} exercise lines.")

    existing = _programs()
    print(f"Existing programs ({len(existing)}):")
    for pid, name, cur in existing:
        print(f"  - {name}  (id={pid}{', CURRENT' if cur else ''})")

    match = next((p for p in existing if p[1] == args.name), None)
    if args.update:
        if not match:
            raise SystemExit(f"--update given but no program named {args.name!r} exists.")
        res = _call("update_program", {"id": match[0], "text": prog})
        print(f"\nUpdated {args.name!r} (id={match[0]}).\n{res[:200]}")
    else:
        if match:
            raise SystemExit(
                f"A program named {args.name!r} already exists (id={match[0]}). "
                f"Re-run with --update to overwrite, or pass --name to use a new name.")
        res = _call("create_program", {"name": args.name, "text": prog})
        print(f"\nCreated {args.name!r}.\n{res[:200]}")


if __name__ == "__main__":
    main()
