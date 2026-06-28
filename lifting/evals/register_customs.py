"""
Register the 16 custom exercises Liftosaur lacks (or grip-variants that must stay
distinct from their base for rotation) via the Liftosaur MCP `create_custom_exercise`
tool. Idempotent: create_custom_exercise updates an existing exercise with the same
name, so re-running is safe.

Run: python3 -m lifting.evals.register_customs
"""

import json
import time
import urllib.request

from .. import config
from .. import liftosaur_names as N

MCP = "https://www.liftosaur.com/mcp"

# name -> (targetMuscles, synergistMuscles, types)
META = {
    "Active Hang":                    (["Latissimus Dorsi"], ["Wrist Flexors", "Trapezius Upper Fibers"], ["pull", "upper"]),
    "Dead Hang Stretch":              (["Latissimus Dorsi"], ["Wrist Flexors", "Teres Major"], ["pull", "upper"]),
    "Pull-Apart":                     (["Deltoid Posterior"], ["Trapezius Middle Fibers", "Trapezius Lower Fibers"], ["pull", "upper"]),
    "Lateral-Incline Raise":          (["Deltoid Lateral"], ["Deltoid Anterior"], ["push", "upper"]),
    "Lean-In DB Lateral Raise":       (["Deltoid Lateral"], ["Trapezius Upper Fibers"], ["push", "upper"]),
    "Kelso Shrug":                    (["Trapezius Middle Fibers"], ["Trapezius Lower Fibers", "Deltoid Posterior"], ["pull", "upper"]),
    "Hex-Bar Shrug":                  (["Trapezius Upper Fibers"], ["Wrist Flexors"], ["pull", "upper"]),
    "Corkscrew":                      (["Obliques"], ["Rectus Abdominis", "Iliopsoas"], ["core"]),
    "Dragon Flag":                    (["Rectus Abdominis"], ["Obliques", "Iliopsoas"], ["core"]),
    "Bent-Knee (Soleus) Calf Raise":  (["Soleus"], ["Gastrocnemius"], ["lower", "legs"]),
    "Deficit Standing Calf Raise":    (["Gastrocnemius"], ["Soleus"], ["lower", "legs"]),
    "Single-Leg Standing Calf Raise": (["Gastrocnemius"], ["Soleus"], ["lower", "legs"]),
    "Underhand Pulldown":             (["Latissimus Dorsi"], ["Biceps Brachii", "Brachialis"], ["pull", "upper"]),
    "Underhand Bent-Over Row":        (["Latissimus Dorsi"], ["Biceps Brachii", "Trapezius Middle Fibers"], ["pull", "upper"]),
    "Alternating Curl":               (["Biceps Brachii"], ["Brachialis", "Brachioradialis"], ["pull", "upper"]),
    "Zottman Curl":                   (["Biceps Brachii"], ["Brachioradialis", "Wrist Extensors"], ["pull", "upper"]),
}


def _call(name, args, _id=1, _tries=3):
    key = config.load_key("LIFTOSAUR_API_KEY")
    body = {"jsonrpc": "2.0", "id": _id, "method": "tools/call",
            "params": {"name": name, "arguments": args}}
    last = None
    for attempt in range(_tries):
        req = urllib.request.Request(MCP, data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     "User-Agent": "Mozilla/5.0 Chrome/124.0"}, method="POST")
        try:
            raw = urllib.request.urlopen(req, timeout=60).read().decode()
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode()[:200]}"
            time.sleep(1.5 * (attempt + 1))
            continue
        try:
            r = json.loads(raw)
        except json.JSONDecodeError:
            last = f"non-JSON response: {raw[:200]!r}"
            time.sleep(1.5 * (attempt + 1))
            continue
        if "error" in r:
            last = json.dumps(r["error"])[:300]
            time.sleep(1.5 * (attempt + 1))
            continue
        txt = r["result"]["content"][0]["text"]
        try:
            return json.loads(txt), None
        except json.JSONDecodeError:
            # Tool returned a plain-text message (e.g. validation error), not the
            # exercise JSON — that's a failure, not success.
            last = f"tool error: {txt[:160]}"
            time.sleep(1.5 * (attempt + 1))
            continue
    return None, last


def main():
    # Sanity: every CUSTOM name has metadata.
    missing = [n for n in N.CUSTOM if n not in META]
    assert not missing, f"missing metadata for: {missing}"

    ok, fail = 0, 0
    for i, name in enumerate(N.CUSTOM, 1):
        tm, sm, ty = META[name]
        reg = N.prod_name(name)   # parser-safe registered name (no parens)
        res, err = _call("create_custom_exercise", {
            "name": reg,
            "targetMuscles": json.dumps(tm),
            "synergistMuscles": json.dumps(sm),
            "types": json.dumps(ty),
        }, _id=i)
        if err:
            fail += 1
            print(f"  FAIL {reg}: {err}")
        else:
            ok += 1
            print(f"  ok   {reg:32s} id={res.get('id')}")
        time.sleep(0.6)
    print(f"\n{ok}/{len(N.CUSTOM)} custom exercises registered ({fail} failed).")
    return fail == 0


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
