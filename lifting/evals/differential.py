"""
Differential evals: drive Liftoscript through the playground and assert it matches
the Python oracle (engine.py / the rotation rule). Suites:

  1. CONTROLLER COLLISION  — all 25 area×day slots, random exhaustion sequences,
     compare every slot index to the oracle (this is the novel/risky logic).
  2. T1 LADDER             — AMRAP +5/+10, level drops, 90% reset.
  3. T2 LADDER             — +5 on completion, level drops, exhaust + re-seed.

Run: python3 -m lifting.evals.differential
"""

import json
import random
import re
import urllib.request

from .. import protocol as P
from .. import engine as E
from .. import config

PG = "https://www.liftosaur.com/api/v1/playground"


def _post(prog, cmds, day=1):
    K = config.load_key("LIFTOSAUR_API_KEY")
    payload = {"programText": prog, "day": day, "week": 1, "commands": cmds}
    req = urllib.request.Request(PG, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {K}", "Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0 Chrome/124.0"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())["data"]["updatedProgramText"]


def _active_level(prog, name):
    """Active set-variation (1-3) from the '!' marker in the rendered program."""
    line = next(l for l in prog.splitlines() if l.startswith(name))
    scheme = line.split("/ progress")[0]
    variations = [p.strip() for p in scheme.split("/") if re.match(r"!?\s*\d+x\d+", p.strip())]
    for i, p in enumerate(variations, 1):
        if p.startswith("!"):
            return i
    return 1


# --------------------------------------------------------------------------
# Suite 1 — controller collision across all 25 slots
# --------------------------------------------------------------------------

def _slots():
    out = []
    for day in (1, 2, 3, 4):
        cfg = P.DAYS[day]
        for area in cfg["t2"]:
            out.append((area, day, len(P.T2_POOLS[area])))
        for area in cfg["t3"]:
            out.append((area, day, len(P.T3_POOLS[area])))
    return out


def controller_suite(seeds=4, steps=25):
    sl = _slots()
    var = {(a, d): f"s{i+1}" for i, (a, d, _) in enumerate(sl)}
    size = {(a, d): s for (a, d, s) in sl}
    days_of = {}
    for (a, d, _) in sl:
        days_of.setdefault(a, []).append(d)
    init = {(a, d): sorted(days_of[a]).index(d) % size[(a, d)] for (a, d, _) in sl}

    decls = ", ".join(f"{var[(a, d)]}: {init[(a, d)]}" for (a, d, _) in sl)
    blocks = []
    for i, (a, d, s) in enumerate(sl, 1):
        sibs = [var[(a, dd)] for dd in days_of[a] if dd != d]
        v = var[(a, d)]
        adv = f"state.{v} = (state.{v} + 1) % {s}; "
        if sibs:
            cond = " || ".join(f"state.{v} == state.{sb}" for sb in sibs)
            adv += " ".join(f"if ({cond}) {{ state.{v} = (state.{v} + 1) % {s} }}" for _ in sibs)
        blocks.append(f"if (completedReps[1] == {i}) {{ {adv} }}")
    base_prog = (f"# Week 1\n## Day 1\nWrist Roller / 1x1 0lb / id: tags(999) "
                 f"/ progress: custom({decls}) {{~ {' '.join(blocks)} ~}}\n")

    def oracle_adv(state, a, d):
        others = {state[(a, dd)] for dd in days_of[a] if dd != d}
        nx = state[(a, d)]
        for _ in range(size[(a, d)]):
            nx = (nx + 1) % size[(a, d)]
            if nx not in others:
                break
        state[(a, d)] = nx

    ok = True
    for seed in range(seeds):
        rng = random.Random(seed)
        state = dict(init)
        prog = base_prog
        for step in range(steps):
            i = rng.randrange(len(sl))
            a, d, _ = sl[i]
            oracle_adv(state, a, d)
            prog = _post(prog, [f"change_reps(1, 1, {i+1})", "complete_set(1, 1)", "finish_workout()"])
            got = {m.group(1): int(m.group(2)) for m in re.finditer(r"(s\d+): (\d+)", prog)}
            exp = {var[k]: state[k] for k in state}
            if got != exp:
                ok = False
                diff = {k: (got.get(k), exp[k]) for k in exp if got.get(k) != exp[k]}
                print(f"  CONTROLLER seed {seed} step {step}: MISMATCH exhaust {a} d{d} -> {diff}")
                break
        if not ok:
            break
    print(f"1. CONTROLLER COLLISION ({seeds} seeds x {steps} steps): {'PASS' if ok else 'FAIL'}")
    return ok


# --------------------------------------------------------------------------
# Suite 2 — T1 ladder
# --------------------------------------------------------------------------

def t1_suite(steps=14):
    prog = ("# Week 1\n## Day 1\n"
            "Squat / 1x4 100lb / 1x3 100lb / 1x2 100lb "
            "/ progress: custom(prevL1: 0lb, w: 100lb, lvl: 1) {~ "
            "var.base = setVariationIndex == 1 ? 4 : (setVariationIndex == 2 ? 3 : 2) "
            "var.extra = completedReps[1] - var.base "
            "if (var.extra >= 5) { state.w += 10lb } "
            "else if (var.extra >= 1) { state.w += 5lb } "
            "else if (setVariationIndex == 1) { state.prevL1 = state.w; setVariationIndex = 2 } "
            "else if (setVariationIndex == 2) { setVariationIndex = 3 } "
            "else { setVariationIndex = 1; state.w = round(state.prevL1 * 0.9 / 5lb) * 5lb } "
            "weights = state.w  state.lvl = setVariationIndex ~}\n")
    st = {"level": 1, "weight": 100, "prev_L1_peak": 100, "source": "t"}
    rng = random.Random(7)
    ok = True
    for step in range(steps):
        extra = rng.choice([-1, 0, 1, 2, 3, 6, 7])
        base = {1: 4, 2: 3, 3: 2}[st["level"]]
        st, _ = E.apply_t1(st, extra)
        cmds = [f"change_reps(1, 1, {base + extra})", "complete_set(1, 1)", "finish_workout()"]
        prog = _post(prog, cmds)
        w = int(float(re.search(r"w: ([\d.]+)lb", prog).group(1)))
        lvl = _active_level(prog, "Squat")
        if (w, lvl) != (st["weight"], st["level"]):
            ok = False
            print(f"  T1 step {step} extra={extra}: pg ({w}lb,L{lvl}) != oracle ({st['weight']}lb,L{st['level']})")
            break
    print(f"2. T1 LADDER + RESET ({steps} steps): {'PASS' if ok else 'FAIL'}")
    return ok


# --------------------------------------------------------------------------
# Suite 3 — T2 ladder + exhaust + re-seed
# --------------------------------------------------------------------------

def t2_suite(steps=14):
    prog = ("# Week 1\n## Day 1\n"
            "Bench Press / 1x12 100lb / 1x10 100lb / 1x8 100lb "
            "/ progress: custom(lastL1: 100lb, w: 100lb, lvl: 1) {~ "
            "var.base = setVariationIndex == 1 ? 12 : (setVariationIndex == 2 ? 10 : 8) "
            "if (completedReps[1] >= var.base) { "
            "if (setVariationIndex == 1) { state.lastL1 = state.w } state.w += 5lb "
            "} else if (setVariationIndex < 3) { setVariationIndex += 1 } "
            "else { setVariationIndex = 1; state.w = state.lastL1 - 5lb } "
            "weights = state.w  state.lvl = setVariationIndex ~}\n")
    st = {"level": 1, "weight": 100, "last_L1_weight": 100, "source": "t"}
    rng = random.Random(3)
    ok = True
    for step in range(steps):
        done = rng.random() < 0.6
        base = {1: 12, 2: 10, 3: 8}[st["level"]]
        st, _, exhausted = E.apply_t2(st, done)
        if exhausted:
            st["level"] = 1
            st["weight"] = E.round5(st["last_L1_weight"] - P.T2_RETURN_DROP)
        reps = base if done else base - 2
        cmds = [f"change_reps(1, 1, {reps})", "complete_set(1, 1)", "finish_workout()"]
        prog = _post(prog, cmds)
        w = int(float(re.search(r"w: ([\d.]+)lb", prog).group(1)))
        lvl = _active_level(prog, "Bench Press")
        if (w, lvl) != (st["weight"], st["level"]):
            ok = False
            print(f"  T2 step {step} done={done}: pg ({w}lb,L{lvl}) != oracle ({st['weight']}lb,L{st['level']})")
            break
    print(f"3. T2 LADDER + EXHAUST ({steps} steps): {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    print("=" * 60)
    print("DIFFERENTIAL EVALS — Liftoscript vs Python oracle")
    print("=" * 60)
    r1 = controller_suite()
    r2 = t1_suite()
    r3 = t2_suite()
    print("=" * 60)
    print("OVERALL:", "ALL PASS" if (r1 and r2 and r3) else "FAILURES PRESENT")
    return r1 and r2 and r3


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
