#!/usr/bin/env python3
"""
Read-only runner for the deterministic lifting engine.

  python3 -m scripts.lifting.run            # derive state + print Session 1 (all days)
  python3 -m scripts.lifting.run --selftest # simulate the rules with assertions
  python3 -m scripts.lifting.run --json     # dump derived state as JSON

Writes nothing anywhere. Reads KeyLifts history (cached at /tmp/klw.json) and the
Ripley seed in protocol.py.
"""

import sys
import json

try:
    from . import protocol as P, engine as E, keylifts as KL
except ImportError:  # allow running as a plain script
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from lifting import protocol as P, engine as E, keylifts as KL

BAR = "=" * 72


def print_starting_weights(state):
    print(BAR)
    print("DERIVED STARTING WEIGHTS")
    print(BAR)
    print("\nT1 (main lifts):")
    for lift in P.T1_LIFTS:
        st = state["t1"][lift]
        print(f"  {lift:16} {st['weight']}lb   [{st['source']}]")

    print("\nT2 / T3 (per rotation pool):")
    for area in list(P.T2_POOLS) + list(P.T3_POOLS):
        ar = state["areas"][area]
        print(f"  {area}:")
        for ex in ar["queue"]:
            s = ar["per_exercise"][ex]
            if "weight" in s:
                w = f"{s['weight']}lb" if s["weight"] is not None else "?? needs-init"
                print(f"      {ex:32} {w:14} [{s['source']}]")
            elif "anchor_reps" in s:
                print(f"      {ex:32} anchor {s['anchor_reps']} reps  [{s['source']}]")
            else:
                print(f"      {ex:32} anchor {s['anchor_sec']}s     [{s['source']}]")


def print_sessions(state):
    print("\n" + BAR)
    print("NEXT SESSION (Session 1) — ALL 4 DAYS")
    print(BAR)
    for day in sorted(P.DAYS):
        cfg = P.DAYS[day]
        s = E.build_day_session(day, state, session_idx=1)
        print(f"\n--- Day {day}: {cfg['t1']} focus ---")
        print(f"  T1  {s['t1']}")
        for area, line in s["t2"]:
            print(f"  T2  [{area}] {line}")
        for area, line in s["t3"]:
            print(f"  T3  [{area}] {line}")
        print(f"  Fin {s['prehab']}")


def print_pending():
    print("\n" + BAR)
    print("PENDING INPUTS")
    print(BAR)
    print("  - Band progression list (assist levels) for:", ", ".join(P.BAND_ASSISTED))
    print("  - Per-exercise anchors for bodyweight-rep + time T3 (defaulted to 20).")
    print("  - 'keylifts-stale' weights are from Jan-2026 — verify before first use.")
    print("  - Live Liftosaur read/write switches on once the membership key is added.")


def selftest():
    print(BAR)
    print("SELF-TEST — deterministic rule simulation")
    print(BAR)
    ok = True

    # T1: walk a full cycle L1 -> L2 -> L3 -> reset, asserting the 90% reset.
    st = {"level": 1, "weight": 100, "prev_L1_peak": 100, "source": "test"}
    trace = []
    for extra in [6, 2, 0, 6, 0, 3, 0]:
        st, note = E.apply_t1(st, extra)
        trace.append((extra, st["level"], st["weight"], note))
    for extra, lvl, w, note in trace:
        print(f"  T1 amrap+{extra:<2} -> L{lvl} {w}lb   ({note})")
    try:
        assert st["level"] == 1, "should wrap back to L1"
        assert st["weight"] == 105, f"reset should be 90% of 115 -> 105, got {st['weight']}"
        assert st["prev_L1_peak"] == 115, "L1 peak should be recorded at 115"
        print("  T1 cycle + 90% reset: PASS")
    except AssertionError as e:
        ok = False
        print(f"  T1 cycle: FAIL — {e}")

    # T2: add weight while completing, drop levels on miss, exhaust at L3.
    st2 = {"level": 1, "weight": 50, "last_L1_weight": 50, "source": "test"}
    st2, _, ex = E.apply_t2(st2, True)   # 55 L1
    st2, _, ex = E.apply_t2(st2, True)   # 60 L1
    st2, _, ex = E.apply_t2(st2, False)  # L2
    st2, _, ex = E.apply_t2(st2, False)  # L3
    st2, _, ex = E.apply_t2(st2, False)  # exhausted
    try:
        assert ex is True and st2["level"] == 3, "T2 should exhaust at L3"
        assert st2["last_L1_weight"] == 55, f"last L1 should be 55, got {st2['last_L1_weight']}"
        print(f"  T2 ladder + exhaust (last L1 {st2['last_L1_weight']}lb): PASS")
    except AssertionError as e:
        ok = False
        print(f"  T2 ladder: FAIL — {e}")

    # T3 time anchor: +1s on success, drop level on miss.
    st3 = {"level": 1, "anchor_sec": 20, "source": "test"}
    st3, _, _ = E.apply_t3_anchor(st3, True, P.T3_TIME_ANCHOR_STEP)
    try:
        assert st3["anchor_sec"] == 21, "time anchor should +1s"
        print("  T3 time anchor +1s: PASS")
    except AssertionError as e:
        ok = False
        print(f"  T3 time: FAIL — {e}")

    # Rotation: collision-aware swap (the only thing the engine owns under Option B).
    # Horizontal Pull spans days 1 & 3 (pool of 4).
    pull = {"queue": list(P.T2_POOLS["Horizontal Pull"]),
            "active_by_day": {1: "Pendlay Row", 3: "Straight-Back Seated Row"},
            "per_exercise": {}}
    o1, n1 = E.advance_slot(pull, 1)   # day1 exhausts; must skip day3's active
    o3, n3 = E.advance_slot(pull, 3)   # day3 exhausts; must skip day1's new active
    try:
        assert (o1, n1) == ("Pendlay Row", "Bent-Over Row"), f"day1 -> {n1}"
        assert (o3, n3) == ("Straight-Back Seated Row", "Underhand Bent-Over Row"), f"day3 -> {n3}"
        assert pull["active_by_day"] == {1: "Bent-Over Row", 3: "Underhand Bent-Over Row"}
        print("  Rotation no-collision (2-day pool): PASS")
    except AssertionError as e:
        ok = False
        print(f"  Rotation 2-day: FAIL — {e}")

    # Core spans all 4 days (pool of 8): day1 must skip the 3 active elsewhere.
    core = {"queue": list(P.T3_POOLS["Core"]),
            "active_by_day": {1: "Ab Wheel Rollout", 2: "Russian Twist",
                              3: "Plank", 4: "Crunch"},
            "per_exercise": {}}
    oc, nc = E.advance_slot(core, 1)
    try:
        assert (oc, nc) == ("Ab Wheel Rollout", "Dragon Flag"), f"core day1 -> {nc}"
        print("  Rotation no-collision (4-day pool): PASS")
    except AssertionError as e:
        ok = False
        print(f"  Rotation 4-day: FAIL — {e}")

    print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return ok


def main():
    if "--selftest" in sys.argv:
        sys.exit(0 if selftest() else 1)

    workouts = KL.fetch_workouts()
    kl_derived = KL.derive_from_keylifts(workouts)
    state = E.init_state(kl_derived)

    if "--json" in sys.argv:
        print(json.dumps(state, indent=2))
        return

    print(f"Loaded {len(workouts)} KeyLifts workouts; "
          f"{len(kl_derived)} distinct logged exercises.\n")
    print_starting_weights(state)
    print_sessions(state)
    print_pending()


if __name__ == "__main__":
    main()
