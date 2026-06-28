"""
Deterministic progression engine.

Pure functions: given current state + a logged result, produce the next state.
No I/O here (KeyLifts read lives in keylifts.py; CLI in run.py). Everything is
driven by protocol.py so the rules live in exactly one place.
"""

from . import protocol as P


def round5(w):
    return int(round(w / 5.0)) * 5


# --------------------------------------------------------------------------
# Starting-weight derivation
# --------------------------------------------------------------------------

def keylifts_by_protocol(kl_derived):
    """Remap KeyLifts logged names -> protocol names, keeping the most recent."""
    out = {}
    for logged, rec in kl_derived.items():
        proto = P.normalize(logged)
        if not proto:
            continue
        cur = out.get(proto)
        if cur is None or rec["recent_date"] > cur["recent_date"]:
            out[proto] = rec
    return out


def derive_weight(exercise, kl_proto):
    """
    Resolve a starting weight + provenance.
      1. Ripley current seed (most recent real capacity) — authoritative.
      2. KeyLifts most-recent working set (stale Jan-2026, flag for review).
      3. None -> needs manual init.
    """
    if exercise in P.RIPLEY_SEED:
        return round5(P.RIPLEY_SEED[exercise]), "ripley-current"
    if exercise in kl_proto:
        return round5(kl_proto[exercise]["recent_weight"]), "keylifts-stale"
    return None, "needs-init"


# --------------------------------------------------------------------------
# Rotation queue: assign initial active exercise per day (no cross-day collision)
# --------------------------------------------------------------------------

def assign_initial_active(area):
    """{day: exercise} — distinct exercises off the front of the queue."""
    pool = (P.T2_POOLS.get(area) or P.T3_POOLS.get(area))[:]
    days = P.days_using_area(area)
    return {day: pool[i % len(pool)] for i, day in enumerate(days)}


def advance_slot(area_state, day):
    """
    OPTION B's one job: rotate the exhausted slot on `day` to the next queue
    exercise NOT currently active on another day (the no-collision rule).
    Returns (old_exercise, new_exercise); new is None on deadlock (only possible
    if a pool is smaller than days_using + 1).
    """
    queue = area_state["queue"]
    active = area_state["active_by_day"]
    current = active[day]
    others = {active[d] for d in active if d != day}
    start = queue.index(current)
    for k in range(1, len(queue) + 1):
        cand = queue[(start + k) % len(queue)]
        if cand != current and cand not in others:
            active[day] = cand
            return current, cand
    return current, None


def perform_swap(area_state, day, return_drop=P.T2_RETURN_DROP):
    """Rotate the slot and re-seed the incoming exercise at L1. A previously
    completed exercise re-enters at (last L1 weight - return_drop)."""
    old, new = advance_slot(area_state, day)
    if new is None:
        return old, None
    pe = area_state["per_exercise"][new]
    pe["level"] = 1
    if "weight" in pe and pe.get("last_L1_weight") is not None and pe.get("seen"):
        pe["weight"] = round5(pe["last_L1_weight"] - return_drop)
    return old, new


# --------------------------------------------------------------------------
# State initialization
# --------------------------------------------------------------------------

def init_state(kl_derived):
    kl_proto = keylifts_by_protocol(kl_derived)
    state = {"t1": {}, "areas": {}}

    for lift in P.T1_LIFTS:
        w, src = derive_weight(lift, kl_proto)
        state["t1"][lift] = {"level": 1, "weight": w, "prev_L1_peak": w, "source": src}

    for area in list(P.T2_POOLS) + list(P.T3_POOLS):
        active = assign_initial_active(area)
        per_ex = {}
        for ex in (P.T2_POOLS.get(area) or P.T3_POOLS.get(area)):
            kind = "t2" if area in P.T2_POOLS else P.t3_type(ex)
            if kind in ("t2", "weighted"):
                w, src = derive_weight(ex, kl_proto)
                per_ex[ex] = {"level": 1, "weight": w, "last_L1_weight": w, "source": src}
            elif kind == "bodyweight":
                per_ex[ex] = {"level": 1, "anchor_reps": 20, "source": "default-anchor"}
            else:  # time
                per_ex[ex] = {"level": 1, "anchor_sec": 20, "source": "default-anchor"}
        state["areas"][area] = {"queue": list(P.T2_POOLS.get(area) or P.T3_POOLS.get(area)),
                                "active_by_day": active, "per_exercise": per_ex}
    return state


# --------------------------------------------------------------------------
# Progression rules (used by the next-night recompute and the self-test)
# --------------------------------------------------------------------------

def apply_t1(st, amrap_extra, missed_base=False):
    """Mutate-return a new T1 state given the AMRAP extra reps over base."""
    s = dict(st)
    base_drop = missed_base or amrap_extra <= 0
    if not base_drop:
        s["weight"] += P.T1_INCREMENT_BIG if amrap_extra >= P.T1_BIG_THRESHOLD else P.T1_INCREMENT_SMALL
        return s, ("+%dlb" % (s["weight"] - st["weight"]))
    # stall -> drop a level (or reset from L3)
    if s["level"] == 1:
        s["prev_L1_peak"] = st["weight"]            # peak reached at L1
        s["level"] = 2
        return s, "stall@L1 -> L2 (hold weight)"
    if s["level"] == 2:
        s["level"] = 3
        return s, "stall@L2 -> L3 (hold weight)"
    # level 3 stall -> reset to L1 at 90% of previous L1 peak
    s["level"] = 1
    s["weight"] = round5(st["prev_L1_peak"] * P.T1_RESET_FACTOR)
    return s, "stall@L3 -> reset L1 @ 90%% of L1 peak (%dlb)" % s["weight"]


def apply_t2(st, completed_all):
    """T2 / weighted-T3 ladder. Returns (new_state, note, exhausted)."""
    s = dict(st)
    if completed_all:
        s["last_L1_weight"] = st["weight"] if st["level"] == 1 else st.get("last_L1_weight", st["weight"])
        s["weight"] += P.T2_INCREMENT
        return s, "+%dlb (level held)" % P.T2_INCREMENT, False
    if s["level"] < 3:
        s["level"] += 1
        return s, "miss -> drop to L%d (hold weight)" % s["level"], False
    return s, "miss@L3 -> exhausted, swap exercise", True


def apply_t3_anchor(st, completed_all, step):
    """Bodyweight-rep / time ladder (anchor + ratio). Returns (state, note, exhausted)."""
    s = dict(st)
    key = "anchor_reps" if "anchor_reps" in s else "anchor_sec"
    if completed_all:
        s[key] += step
        return s, "+%d %s" % (step, "rep" if key == "anchor_reps" else "s"), False
    if s["level"] < 3:
        s["level"] += 1
        return s, "miss -> drop to L%d" % s["level"], False
    return s, "miss@L3 -> exhausted, swap exercise", True


# --------------------------------------------------------------------------
# Prescription builders (what to actually do this session)
# --------------------------------------------------------------------------

def t1_prescription(lift, st):
    lvl = P.T1_LEVELS[st["level"]]
    w = st["weight"]
    wtxt = f"{w}lb" if w is not None else "??"
    return (f"{lift} / {lvl['sets']}x{lvl['reps']} (last set AMRAP) {wtxt} "
            f"/ {lvl['tempo']}  [L{st['level']}, src:{st['source']}]")


def t2_prescription(ex, st):
    lvl = P.T2_LEVELS[st["level"]]
    w = st["weight"]
    wtxt = f"{w}lb" if w is not None else "?? (needs init)"
    band = " (band assist — progression TBD)" if "(band)" in ex else ""
    return f"{ex} / {lvl['sets']}x{lvl['reps']} {wtxt}{band}  [L{st['level']}, src:{st['source']}]"


def _ratio_sets(anchor, level):
    r = P.T3_RATIOS[level]
    return [max(1, round(anchor * r[i] / r[0])) for i in range(3)]


def t3_prescription(ex, st):
    kind = P.t3_type(ex)
    if kind == "weighted":
        reps = P.T3_WEIGHTED_LEVELS[st["level"]]
        w = st["weight"]
        wtxt = f"{w}lb" if w is not None else "?? (needs init)"
        tempo = f" / {P.CALF_TEMPO}" if "Calf" in ex else ""
        return f"{ex} / 3 sets {reps[0]}/{reps[1]}/{reps[2]} {wtxt}{tempo}  [L{st['level']}, src:{st['source']}]"
    if kind == "bodyweight":
        sets = _ratio_sets(st["anchor_reps"], st["level"])
        return f"{ex} / 3 sets {sets[0]}/{sets[1]}/{sets[2]} reps BW  [L{st['level']}, anchor {st['anchor_reps']}]"
    sets = _ratio_sets(st["anchor_sec"], st["level"])
    return f"{ex} / 3 sets {sets[0]}/{sets[1]}/{sets[2]} sec  [L{st['level']}, anchor {st['anchor_sec']}s]"


def prehab_prescription(day_cfg, session_idx):
    variant = "A" if session_idx % 2 == 1 else "B"
    ex = day_cfg["prehab"][variant]
    if day_cfg["prehab"]["type"] == "reps":
        return f"{ex} / 1 set, target 30-50 reps (float weight)  [{variant}]"
    return f"{ex} / 1 set, hold for time (+1s each time)  [{variant}]"


def build_day_session(day, state, session_idx=1):
    cfg = P.DAYS[day]
    lines = {"t1": t1_prescription(cfg["t1"], state["t1"][cfg["t1"]]), "t2": [], "t3": []}
    for area in cfg["t2"]:
        ar = state["areas"][area]
        ex = ar["active_by_day"][day]
        lines["t2"].append((area, t2_prescription(ex, ar["per_exercise"][ex])))
    for area in cfg["t3"]:
        ar = state["areas"][area]
        ex = ar["active_by_day"][day]
        lines["t3"].append((area, t3_prescription(ex, ar["per_exercise"][ex])))
    lines["prehab"] = prehab_prescription(cfg, session_idx)
    return lines
