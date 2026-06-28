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
from .. import liftosaur_names as N


def _setvars(tier, ex=None):
    if tier == "t1":
        return "3x4,1x4+ / 3x3,1x3+ / 3x2,1x2+"
    if tier == "t2":
        return "4x12 / 4x10 / 4x8"
    # t3
    kind = P.t3_type(ex) if ex else "weighted"
    if kind == "weighted":
        return "1x25,1x20,1x15 / 1x20,1x15,1x10 / 1x15,1x8,1x7"
    return "3x20 / 3x16 / 3x12"


def _t1_script():
    return ("progress: custom(prevL1: 0lb) {~ "
            "var.base = setVariationIndex == 1 ? 4 : (setVariationIndex == 2 ? 3 : 2) "
            "var.extra = completedReps[ns] - var.base "
            "if (var.extra >= 5) { weights += 10lb } "
            "else if (var.extra >= 1) { weights += 5lb } "
            "else if (setVariationIndex == 1) { state.prevL1 = weights[1]; setVariationIndex = 2 } "
            "else if (setVariationIndex == 2) { setVariationIndex = 3 } "
            "else { setVariationIndex = 1; weights = roundWeight(state.prevL1 * 0.9) } ~}")


def _pool_progress():
    return ("progress: custom(a1: 0, a2: 0, a3: 0, a4: 0, lastL1: 0lb, exhausted: 0) {~ "
            "if (completedReps >= reps) { "
            "if (setVariationIndex == 1) { state.lastL1 = weights[1] } weights += 5lb "
            "} else if (setVariationIndex < 3) { setVariationIndex += 1 } "
            "else { state.exhausted = 1 } ~}")


def _pool_update():
    return ("update: custom() {~ if (setIndex == 0) { "
            "if (day == 1 && state.a1 == 0) { numberOfSets = 0 } "
            "if (day == 2 && state.a2 == 0) { numberOfSets = 0 } "
            "if (day == 3 && state.a3 == 0) { numberOfSets = 0 } "
            "if (day == 4 && state.a4 == 0) { numberOfSets = 0 } } ~}")


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
    for _, _, _, pool in slots:        # pre-assign uids so the controller can address all
        for ex in pool:
            uid(ex)

    defined = set()
    out = ["# Week 1"]
    for day in (1, 2, 3, 4):
        cfg = P.DAYS[day]
        out.append(f"## Day {day}")

        # T1 (fixed; progression defined once)
        t1 = cfg["t1"]; ref = N.liftosaur_ref(t1, mode)
        if t1 not in defined:
            out.append(f"{ref} / {_setvars('t1')} {weight}lb / {_t1_script()}")
            defined.add(t1)
        else:
            out.append(f"{ref} / {_setvars('t1')} {weight}lb")

        # T2 + T3 slots: list every pool exercise, gated
        for tier, areas in (("t2", cfg["t2"]), ("t3", cfg["t3"])):
            pools = P.T2_POOLS if tier == "t2" else P.T3_POOLS
            for area in areas:
                for ex in pools[area]:
                    ref = N.liftosaur_ref(ex, mode)
                    if ex not in defined:
                        out.append(f"{ref} / {_setvars(tier, ex)} {weight}lb / id: tags({uid(ex)}) "
                                   f"/ {_pool_progress()} / {_pool_update()}")
                        defined.add(ex)
                    else:
                        out.append(f"{ref} / {_setvars(tier, ex)} {weight}lb")

        # prehab finisher (fixed A/B; show A)
        pre = cfg["prehab"]["A"]; pref = N.liftosaur_ref(pre, mode)
        if pre not in defined:
            out.append(f"{pref} / 1x40 {weight}lb / progress: custom() {{~ "
                       f"if (completedReps[1] >= 50) {{ weights += 5lb }} "
                       f"if (completedReps[1] < 30) {{ weights -= 5lb }} ~}}")
            defined.add(pre)
        else:
            out.append(f"{pref} / 1x40 {weight}lb")

        # single centralized controller (defined once, reused after)
        if "CTRL" not in defined:
            out.append(_controller(slots, slotvar, uid))
            defined.add("CTRL")
        else:
            out.append("Wrist Roller / 1x1 0lb")

    return "\n".join(out) + "\n"


def _controller(slots, slotvar, uid):
    """One exercise holding ALL area×day rotation indices. Pushes each pool
    exercise's per-day active flag from its slot index. (Collision/exhaustion
    advance is validated in the differential phase; here it's representative size.)"""
    decls = ["tick: 0"] + [f"{v}: 0" for v in slotvar.values()]
    pieces = ["state.tick += 1"]
    for area, day, tier, pool in slots:
        v = slotvar[(area, day)]
        for k, ex in enumerate(pool):
            pieces.append(f"state[{uid(ex)}].a{day} = state.{v} == {k} ? 1 : 0")
    return (f"Wrist Roller / 1x1 0lb / id: tags(999) "
            f"/ progress: custom({', '.join(decls)}) {{~ {' '.join(pieces)} ~}}")
