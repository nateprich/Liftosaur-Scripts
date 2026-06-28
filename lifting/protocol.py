"""
Lifting protocol encoded as data — the single programmatic source of truth.

Mirrors areas/physical-health/exercise/lifting-protocol.md. If the spec changes,
update both. The engine (engine.py) reads everything from here; no rules are
hard-coded elsewhere.
"""

# --------------------------------------------------------------------------
# T1 — fixed main lifts
# --------------------------------------------------------------------------

T1_LIFTS = ["Back Squat", "Deadlift", "Bench Press", "Overhead Press"]

# Rep-stage ladder. base = straight-set reps (also the AMRAP-set target).
T1_LEVELS = {
    1: {"sets": 4, "reps": 4, "tempo": "3s ecc", "ecc_sec": 3},
    2: {"sets": 4, "reps": 3, "tempo": "2s ecc", "ecc_sec": 2},
    3: {"sets": 4, "reps": 2, "tempo": "1s ecc", "ecc_sec": 1},
}

# Progression off the AMRAP (last) set, judged vs the level base reps.
T1_INCREMENT_SMALL = 5    # lb, when 1-4 extra reps
T1_INCREMENT_BIG = 10     # lb, when >= 5 extra reps
T1_BIG_THRESHOLD = 5      # extra reps to earn the big jump
T1_RESET_FACTOR = 0.90    # on L3 stall -> L1 at 90% of previous L1 peak

# --------------------------------------------------------------------------
# T2 — supplementals (rotate through area pools)
# --------------------------------------------------------------------------

T2_LEVELS = {1: {"sets": 4, "reps": 12}, 2: {"sets": 4, "reps": 10}, 3: {"sets": 4, "reps": 8}}
T2_INCREMENT = 5          # lb per full completion (or one band level less assistance)
T2_RETURN_DROP = 5        # lb below last L1 weight when an exercise re-enters rotation

# --------------------------------------------------------------------------
# T3 — accessories (rotate) + prehab finisher (fixed)
# --------------------------------------------------------------------------

# Weighted T3: explicit per-set rep targets per level.
T3_WEIGHTED_LEVELS = {1: [25, 20, 15], 2: [20, 15, 10], 3: [15, 8, 7]}
T3_WEIGHTED_INCREMENT = 5

# Bodyweight-rep and time-based T3: ratio ladder, set 1 = anchor, sets 2-3 scale.
T3_RATIOS = {1: [5, 4, 3], 2: [4, 3, 2], 3: [2, 1, 0.9]}
T3_REP_ANCHOR_STEP = 1    # +1 rep to anchor per success
T3_TIME_ANCHOR_STEP = 1   # +1 s to anchor per success

# Prehab finishers (1 set, float). Reps: hold a 30-50 band by floating weight.
PREHAB_REP_HIGH = 50      # >= this -> add weight
PREHAB_REP_LOW = 30       # < this -> drop weight
PREHAB_TIME_STEP = 1      # +1 s vs last completed set

# --------------------------------------------------------------------------
# Rotation pools (ordered queues). list order = rotation order.
# --------------------------------------------------------------------------

T2_POOLS = {
    "Horizontal Push": ["Incline Bench", "Assisted Dip (band)"],
    "Vertical Push": ["Seated BB Shoulder Press", "Seated DB Shoulder Press"],
    "Horizontal Pull": ["Pendlay Row", "Straight-Back Seated Row",
                         "Bent-Over Row", "Underhand Bent-Over Row"],
    "Vertical Pull": ["Lat Pulldown", "Assisted Pull-Up (band)",
                      "Assisted Chin-Up (band)", "Underhand Pulldown"],
    "Hinge": ["Romanian Deadlift", "Sumo Deadlift"],
    "Squat/Lower": ["Front Squat", "Safety Bar Squat"],
}

T3_POOLS = {
    "Posterior/Hinge": ["Straight-Leg Deadlift", "Hip Thrust"],
    "Single-leg/Quad": ["Bulgarian Split Squat", "Step Up"],
    "Calves": ["Standing Calf Raise", "Single-Leg Standing Calf Raise",
               "Deficit Standing Calf Raise", "Bent-Knee (Soleus) Calf Raise"],
    "Traps": ["Barbell Shrug", "Kelso Shrug", "Dumbbell Shrug", "Hex-Bar Shrug"],
    "Chest": ["Fly", "Incline Fly"],
    "Side Delts": ["Lateral Raise", "Lean-In DB Lateral Raise"],
    "Triceps": ["Standing Triceps Ext", "Lying Triceps Ext",
                "Tricep Pushdown", "Kickback"],
    "Biceps": ["Alternating Curl", "Zottman Curl", "Cable Curl", "Biceps Curl"],
    "Core": ["Ab Wheel Rollout", "Russian Twist", "Plank", "Crunch",
             "Dragon Flag", "Corkscrew", "Side Plank", "Bicycle Crunch"],
}

# T3 progression type per exercise. Default = "weighted".
T3_TYPES = {
    "Ab Wheel Rollout": "bodyweight", "Crunch": "bodyweight",
    "Dragon Flag": "bodyweight", "Corkscrew": "bodyweight",
    "Bicycle Crunch": "bodyweight",
    "Plank": "time", "Side Plank": "time",
    # loaded-by-default (flip to bodyweight if trained unloaded):
    "Russian Twist": "weighted", "Step Up": "weighted",
    "Bulgarian Split Squat": "weighted", "Hip Thrust": "weighted",
}

# Calves use a 3s up / 3s down tempo (doubles as prehab).
CALF_TEMPO = "3s up / 3s down"

def t3_type(exercise):
    return T3_TYPES.get(exercise, "weighted")

# --------------------------------------------------------------------------
# Day formula. T2/T3 cells name the target AREA; exercise comes from the queue.
# --------------------------------------------------------------------------

DAYS = {
    1: {"t1": "Deadlift",
        "t2": ["Horizontal Push", "Horizontal Pull"],
        "t3": ["Posterior/Hinge", "Core", "Calves", "Traps"],
        "prehab": {"A": "Face Pull", "B": "Pull-Apart", "type": "reps"}},
    2: {"t1": "Overhead Press",
        "t2": ["Hinge", "Vertical Pull"],
        "t3": ["Side Delts", "Core", "Triceps", "Biceps"],
        "prehab": {"A": "Dead Hang Stretch", "B": "Dead Hang Stretch", "type": "time"}},
    3: {"t1": "Back Squat",
        "t2": ["Vertical Push", "Horizontal Pull"],
        "t3": ["Single-leg/Quad", "Core", "Calves", "Traps"],
        "prehab": {"A": "Lateral-Incline Raise", "B": "Rear Lateral Raise", "type": "reps"}},
    4: {"t1": "Bench Press",
        "t2": ["Squat/Lower", "Vertical Pull"],
        "t3": ["Chest", "Core", "Triceps", "Biceps"],
        "prehab": {"A": "Active Hang", "B": "Active Hang", "type": "time"}},
}


def days_using_area(area):
    """Days (1-4) whose T2 or T3 slots call this target area."""
    out = []
    for d, cfg in DAYS.items():
        if area in cfg["t2"] or area in cfg["t3"]:
            out.append(d)
    return out


# --------------------------------------------------------------------------
# Name normalization: logged exercise names (KeyLifts / Ripley) -> protocol names
# --------------------------------------------------------------------------

NAME_MAP = {
    # T1
    "squat": "Back Squat", "back squat": "Back Squat",
    "deadlift": "Deadlift",
    "bench press": "Bench Press",
    "press": "Overhead Press", "overhead press": "Overhead Press",
    "overhead • press": "Overhead Press", "standing press": "Overhead Press",
    # common T2/T3 seen in KeyLifts history
    "incline • bench press": "Incline Bench", "incline bench press": "Incline Bench",
    "pendlay row": "Pendlay Row",
    "romanian deadlift": "Romanian Deadlift",
    "lat pulldown": "Lat Pulldown", "wide grip pulldown": "Lat Pulldown",
    "pulldown": "Lat Pulldown",
    "safety bar squat": "Safety Bar Squat",
    "front squat": "Front Squat",
    "hex bar deadlift": "Sumo Deadlift",  # historical heavy-pull variant (closest pool slot)
    "shrug": "Barbell Shrug",
    "face pull": "Face Pull",
    "bulgarian split squat": "Bulgarian Split Squat",
    "step up": "Step Up",
    "plank": "Plank",
    "ab wheel rollout": "Ab Wheel Rollout", "wheel rollout": "Ab Wheel Rollout",
}


def normalize(name):
    return NAME_MAP.get((name or "").strip().lower())


# --------------------------------------------------------------------------
# Ripley current-capacity seed (from Training-Log / Week-Plan, June 2026).
# Most recent real loads after the layoff restart — authoritative over stale
# KeyLifts maxes. Conservative on purpose; the AMRAP rule ramps fast if light.
# --------------------------------------------------------------------------

RIPLEY_SEED = {
    "Back Squat": 140,
    "Bench Press": 105,
    "Deadlift": 115,        # logged as light "movement practice" — will ramp quickly
    "Overhead Press": 55,
    "Lat Pulldown": 75,
    "Face Pull": 50,
    "Standing Calf Raise": 0,   # bodyweight, 3s/3s tempo
}

# Band-assisted lifts — progression list pending from Nate.
BAND_ASSISTED = ["Assisted Dip (band)", "Assisted Pull-Up (band)", "Assisted Chin-Up (band)"]
