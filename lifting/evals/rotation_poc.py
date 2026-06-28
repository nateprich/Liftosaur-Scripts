"""
PoC: prove the 4-day multi-skip collision-avoidance works in pure Liftoscript.

A Core-style area spans days 1-4 with a pool of 8. When one day's slot exhausts,
the controller must advance to the next index that isn't active on any of the OTHER
three days. Liftoscript has no `while`, so the skip is UNROLLED (3 checks suffice
since at most 3 others collide). We drive exhaustion via `set_state_variable` and
diff the controller's resulting indices against a Python oracle.

Run: python3 -m lifting.evals.rotation_poc
"""

import json
import re
import urllib.request
import urllib.error

from .. import config

POOL = 8
SKIP = ("if (state.{c} == state.{a} || state.{c} == state.{b} || state.{c} == state.{d}) "
        "{{ state.{c} = (state.{c} + 1) % {pool} }}")


def _advance_block(cur, others):
    a, b, d = others
    base = f"state.{cur} = (state.{cur} + 1) % {POOL}; "
    skips = " ".join(SKIP.format(c=cur, a=a, b=b, d=d, pool=POOL) for _ in range(3))
    return base + skips


def program():
    # indices c1..c4 (active per day). The day that 'exhausts' is encoded as the
    # completed reps of the single set (1-4) — same-exercise data, always visible
    # to its own progress this session (no cross-write timing to worry about).
    decl = "c1: 0, c2: 1, c3: 2, c4: 3"
    sib = {"c1": ("c2", "c3", "c4"), "c2": ("c1", "c3", "c4"),
           "c3": ("c1", "c2", "c4"), "c4": ("c1", "c2", "c3")}
    blocks = []
    for i, c in enumerate(("c1", "c2", "c3", "c4"), 1):
        blocks.append(f"if (completedReps[1] == {i}) {{ {_advance_block(c, sib[c])} }}")
    script = " ".join(blocks)
    return f"# Week 1\n## Day 1\nWrist Roller / 1x1 0lb / id: tags(999) / progress: custom({decl}) {{~ {script} ~}}\n"


def oracle_advance(c, day):
    """Same rule in Python: advance c[day] to next index not in the other days."""
    others = {c[d] for d in c if d != day}
    nxt = c[day]
    for _ in range(POOL):
        nxt = (nxt + 1) % POOL
        if nxt not in others:
            break
    c[day] = nxt
    return c


def _run(prog, exday):
    K = config.load_key("LIFTOSAUR_API_KEY")
    cmds = [f"change_reps(1, 1, {exday})", "complete_set(1, 1)", "finish_workout()"]
    payload = {"programText": prog, "day": 1, "week": 1, "commands": cmds}
    req = urllib.request.Request("https://www.liftosaur.com/api/v1/playground",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {K}", "Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0 Chrome/124.0"}, method="POST")
    txt = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())["data"]["updatedProgramText"]
    idx = {int(m.group(1)[1]): int(m.group(2)) for m in re.finditer(r"(c[1-4]): (\d+)", txt)}
    return txt, idx


def main():
    prog = program()
    c = {1: 0, 2: 1, 3: 2, 4: 3}
    sequence = [1, 3, 1, 2, 4, 1]   # which day exhausts each step
    ok = True
    print(f"start active indices: {c}")
    for step, exday in enumerate(sequence, 1):
        oracle = oracle_advance(dict(c), exday)
        prog, got = _run(prog, exday)
        match = got == oracle
        ok &= match
        print(f"step {step}: exhaust day {exday} -> playground {got} | oracle {oracle} "
              f"| {'MATCH' if match else 'MISMATCH'}")
        c = got
    print("\nRESULT:", "ALL MATCH — 4-day multi-skip works in-app" if ok else "MISMATCH PRESENT")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
