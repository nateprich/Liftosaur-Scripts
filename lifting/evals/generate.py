"""
Generate the full Option-A Liftoscript program from protocol.py.

This is the worst-case shape: every pool exercise is listed on every day its slot
appears, each gated by its own per-day active flag; a controller exercise per day
holds the rotation indices and pushes active flags. Used for the Tier-4 size probe
and (later) the differential eval harness.

NOTE: progression/rotation scripts here are representative-but-simplified — enough
to be valid Liftoscript at realistic size. Exact-rule correctness is validated
separately against the Python oracle.
"""

from .. import protocol as P
from .. import engine as E
from .. import liftosaur_names as N


def _seed(ex, kind):
    """Production starting weight: Ripley seed if known, else a conservative
    default (0lb for bodyweight/time, 45lb for weighted) that Nate dials in-app."""
    w, _src = E.derive_weight(ex, {})
    if w is not None:
        return w
    return 0 if kind in ("bodyweight", "time") else 45


def _setvars(tier, weight, ex=None):
    """Set/rep/weight schemes per tier, with per-group weights (validated:
    shared trailing weight after a comma breaks the parser)."""
    w = f"{weight}lb"
    if tier == "t1":
        return f"3x4 {w},1x4+ {w} / 3x3 {w},1x3+ {w} / 3x2 {w},1x2+ {w}"
    if tier == "t2":
        return f"4x12 {w} / 4x10 {w} / 4x8 {w}"
    # t3
    kind = P.t3_type(ex) if ex else "weighted"
    if kind == "weighted":
        return (f"1x25 {w},1x20 {w},1x15 {w} / 1x20 {w},1x15 {w},1x10 {w} "
                f"/ 1x15 {w},1x8 {w},1x7 {w}")
    return f"3x20 {w} / 3x16 {w} / 3x12 {w}"


def _t1_script(weight):
    """T1 AMRAP ladder: +5/+10 on AMRAP overshoot, level drop on miss, 90% reset
    after L3. Tracks state.w and writes weights = state.w (validated vs oracle)."""
    return (f"progress: custom(prevL1: {weight}lb, w: {weight}lb) {{~ "
            "var.base = setVariationIndex == 1 ? 4 : (setVariationIndex == 2 ? 3 : 2) "
            "var.extra = completedReps[ns] - var.base "
            "if (var.extra >= 5) { state.w += 10lb } "
            "else if (var.extra >= 1) { state.w += 5lb } "
            "else if (setVariationIndex == 1) { state.prevL1 = state.w; setVariationIndex = 2 } "
            "else if (setVariationIndex == 2) { setVariationIndex = 3 } "
            "else { setVariationIndex = 1; state.w = round(state.prevL1 * 0.9 / 5lb) * 5lb } "
            "weights = state.w ~}")


def _pool_progress(weight, area, k, days_of, sloti, init):
    """T2/T3 pool exercise: +5 on full completion, level drop on miss, and on
    exhaustion (miss at L3) cross-write the controller's per-day exhaust flag and
    self-reset to L1 at lastL1-5 (validated vs oracle). Active flags a1..a4 are
    pre-seeded so the day-1 active exercise renders before the controller runs."""
    ainit = {1: 0, 2: 0, 3: 0, 4: 0}
    for d in days_of[area]:
        ainit[d] = 1 if init[(area, d)] == k else 0
    branch = []
    for j, d in enumerate(sorted(days_of[area])):
        kw = "if" if j == 0 else "else if"
        branch.append(f"{kw} (day == {d}) {{ state[999].e{sloti[(area, d)]} = 1 }}")
    exhaust = " ".join(branch)
    return (f"progress: custom(a1: {ainit[1]}, a2: {ainit[2]}, a3: {ainit[3]}, a4: {ainit[4]}, "
            f"lastL1: {weight}lb, w: {weight}lb) {{~ "
            "if (completedReps >= reps) { "
            "if (setVariationIndex == 1) { state.lastL1 = state.w } state.w += 5lb "
            "} else if (setVariationIndex < 3) { setVariationIndex += 1 } "
            f"else {{ {exhaust} setVariationIndex = 1; state.w = state.lastL1 - 5lb }} "
            "weights = state.w ~}")


def _t3_progress(area, k, days_of, init, weight):
    """T3 (optional accessory): only a FULL completion bumps weight (+5lb). A
    partial or skipped session repeats the same prescription next time — no
    deload, no level drop, no auto-rotation. Active flags gate visibility."""
    ainit = {1: 0, 2: 0, 3: 0, 4: 0}
    for d in days_of[area]:
        ainit[d] = 1 if init[(area, d)] == k else 0
    return (f"progress: custom(a1: {ainit[1]}, a2: {ainit[2]}, a3: {ainit[3]}, a4: {ainit[4]}, "
            f"w: {weight}lb) {{~ "
            "if (completedReps >= reps) { state.w += 5lb } "
            "weights = state.w ~}")


def _pool_update():
    return ("update: custom() {~ if (setIndex == 0) { "
            "if (day == 1 && state.a1 == 0) { numberOfSets = 0 } "
            "if (day == 2 && state.a2 == 0) { numberOfSets = 0 } "
            "if (day == 3 && state.a3 == 0) { numberOfSets = 0 } "
            "if (day == 4 && state.a4 == 0) { numberOfSets = 0 } } ~}")


def _band_w_expr():
    """Nested ternary: state.band step -> signed weight (negative = assist)."""
    expr = "(state.band - 6) * 5lb"
    for step in range(P.BAND_BODYWEIGHT, 0, -1):
        expr = f"state.band == {step} ? {P.band_weight(step)}lb : ({expr})"
    return expr


def _band_progress(area, k, days_of, sloti, init):
    """Band-assisted T2: success removes one band step (assist -> bodyweight ->
    +weight); miss drops a rep level; exhaust at L3 rotates. Same ladder/exhaust
    wiring as _pool_progress, weight axis replaced by the band step."""
    ainit = {1: 0, 2: 0, 3: 0, 4: 0}
    for d in days_of[area]:
        ainit[d] = 1 if init[(area, d)] == k else 0
    branch = []
    for j, d in enumerate(sorted(days_of[area])):
        kw = "if" if j == 0 else "else if"
        branch.append(f"{kw} (day == {d}) {{ state[999].e{sloti[(area, d)]} = 1 }}")
    exhaust = " ".join(branch)
    start = P.band_weight(0)
    return (f"progress: custom(a1: {ainit[1]}, a2: {ainit[2]}, a3: {ainit[3]}, a4: {ainit[4]}, "
            f"band: 0, w: {start}lb) {{~ "
            "if (completedReps >= reps) { state.band += 1 "
            f"state.w = {_band_w_expr()} "
            "} else if (setVariationIndex < 3) { setVariationIndex += 1 } "
            f"else {{ {exhaust} setVariationIndex = 1; state.band = 0; state.w = {start}lb }} "
            "weights = state.w ~}")



def generate(mode="eval", weight=100):
    tags = {}
    def uid(ex):
        return tags.setdefault(ex, len(tags) + 1)

    # Enumerate every (area, day) slot; assign a controller index var to each.
    slots = []
    for day in (1, 2, 3, 4):
        cfg = P.DAYS[day]
        for area in cfg["t2"]:
            slots.append((area, day, "t2", P.T2_POOLS[area]))
        for area in cfg["t3"]:
            slots.append((area, day, "t3", P.T3_POOLS[area]))
    slotvar = {(a, d): f"s{i+1}" for i, (a, d, _, _) in enumerate(slots)}
    sloti = {(a, d): i + 1 for i, (a, d, _, _) in enumerate(slots)}
    days_of = {}
    for (a, d, _, _) in slots:
        days_of.setdefault(a, []).append(d)
    size = {(a, d): len(pool) for (a, d, _, pool) in slots}
    # Initial slot index per (area, day): stagger by the area's day-order so the
    # day-1 and day-N exercises start on different pool members (collision-free).
    init = {(a, d): sorted(days_of[a]).index(d) % size[(a, d)] for (a, d, _, _) in slots}
    # Index of each exercise within its pool, per area, for active-flag seeding.
    pool_index = {}
    for (a, d, _, pool) in slots:
        for k, ex in enumerate(pool):
            pool_index[(a, ex)] = k
    for _, _, _, pool in slots:        # pre-assign uids so the controller can address all
        for ex in pool:
            uid(ex)

    def W(ex, tier):
        """Per-exercise weight: uniform in eval (deterministic probes), seeded in prod."""
        if mode == "eval":
            return weight
        kind = "t2" if tier == "t2" else (P.t3_type(ex) if tier == "t3" else "t1")
        return _seed(ex, kind)

    defined = set()
    out = ["# Week 1"]
    for day in (1, 2, 3, 4):
        cfg = P.DAYS[day]
        out.append(f"## Day {day}")

        # T1 (fixed; progression defined once)
        t1 = cfg["t1"]; ref = N.liftosaur_ref(t1, mode); tw = W(t1, "t1")
        if t1 not in defined:
            out.append(f"{ref} / {_setvars('t1', tw)} / warmup: none / {_t1_script(tw)}")
            defined.add(t1)
        else:
            out.append(f"{ref} / {_setvars('t1', tw)} / warmup: none")

        # T2 + T3 slots: list every pool exercise, gated
        for tier, areas in (("t2", cfg["t2"]), ("t3", cfg["t3"])):
            pools = P.T2_POOLS if tier == "t2" else P.T3_POOLS
            for area in areas:
                for ex in pools[area]:
                    ref = N.liftosaur_ref(ex, mode); w = W(ex, tier)
                    band = P.is_band_assisted(ex)
                    if band:
                        w = P.band_weight(0)   # start fully assisted (negative)
                    if ex not in defined:
                        k = pool_index[(area, ex)]
                        if tier == "t3":
                            prog = _t3_progress(area, k, days_of, init, w)
                        elif band:
                            prog = _band_progress(area, k, days_of, sloti, init)
                        else:
                            prog = _pool_progress(w, area, k, days_of, sloti, init)
                        out.append(f"{ref} / {_setvars(tier, w, ex)} / warmup: none / id: tags({uid(ex)}) "
                                   f"/ {prog} / {_pool_update()}")
                        defined.add(ex)
                    else:
                        out.append(f"{ref} / {_setvars(tier, w, ex)} / warmup: none")

        # prehab finisher (fixed A/B; show A)
        pre = cfg["prehab"]["A"]; pref = N.liftosaur_ref(pre, mode); pw = W(pre, "t3")
        if pre not in defined:
            out.append(f"{pref} / 1x40 {pw}lb / warmup: none / progress: custom() {{~ "
                       f"if (completedReps[1] >= 50) {{ weights += 5lb }} "
                       f"if (completedReps[1] < 30) {{ weights -= 5lb }} ~}}")
            defined.add(pre)
        else:
            out.append(f"{pref} / 1x40 {pw}lb / warmup: none")

        # single centralized controller (defined once, reused after)
        engine = "Rotation Engine" if mode == "prod" else "Wrist Roller"
        if "CTRL" not in defined:
            out.append(_controller(slots, slotvar, sloti, days_of, uid, init, engine))
            defined.add("CTRL")
        else:
            out.append(f"{engine} / 1x1 0lb")

    return "\n".join(out) + "\n"


def _controller(slots, slotvar, sloti, days_of, uid, init, engine="Wrist Roller"):
    """One exercise holding ALL area×day rotation indices plus a per-slot exhaust
    flag. On finishWorkout: for any slot whose exhaust flag is set, advance its
    index (collision-aware vs sibling days of the same area), clear the flag, then
    push every pool exercise's per-day active flag from the current slot index.
    Advance + collision logic validated vs the oracle (controller_suite)."""
    decls = ["tick: 0"]
    for (a, d, _, _) in slots:
        decls.append(f"{slotvar[(a, d)]}: {init[(a, d)]}")
        decls.append(f"e{sloti[(a, d)]}: 0")
    pieces = ["state.tick += 1"]
    # exhaustion-driven, collision-aware advance
    for (a, d, _, pool) in slots:
        v = slotvar[(a, d)]; i = sloti[(a, d)]; s = len(pool)
        sibs = [slotvar[(a, dd)] for dd in days_of[a] if dd != d]
        adv = f"state.{v} = (state.{v} + 1) % {s}; "
        if sibs:
            cond = " || ".join(f"state.{v} == state.{sb}" for sb in sibs)
            adv += " ".join(f"if ({cond}) {{ state.{v} = (state.{v} + 1) % {s} }}" for _ in sibs)
        pieces.append(f"if (state.e{i} == 1) {{ state.e{i} = 0; {adv} }}")
    # push active flags from current slot indices
    for (a, d, _, pool) in slots:
        v = slotvar[(a, d)]
        for k, ex in enumerate(pool):
            pieces.append(f"state[{uid(ex)}].a{d} = state.{v} == {k} ? 1 : 0")
    return (f"{engine} / 1x1 0lb / id: tags(999) "
            f"/ progress: custom({', '.join(decls)}) {{~ {' '.join(pieces)} ~}}")
