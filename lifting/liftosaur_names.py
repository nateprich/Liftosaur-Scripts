"""
Protocol exercise name -> Liftosaur exercise reference.

Three buckets (validated against the Liftosaur catalog + playground parser):
  - 19 names Liftosaur already knows (map to themselves).
  - 23 CANONICAL: same movement, Liftosaur's name/equipment (NOT a swap).
  - 16 CUSTOM: movements Liftosaur lacks, OR grip-variants that must stay distinct
    from their base for rotation (e.g. Underhand Pulldown vs Lat Pulldown). These
    get registered as custom exercises for production; for evals we use a distinct
    known PLACEHOLDER so the playground parses (we're testing the mechanic, not the
    movement).
"""

import re

CANONICAL = {
    "Ab Wheel Rollout": "Ab Wheel",
    "Back Squat": "Squat",
    "Barbell Shrug": "Shrug, Barbell",
    "Bent-Over Row": "Bent Over Row",
    "Biceps Curl": "Bicep Curl, Dumbbell",
    "Cable Curl": "Bicep Curl, Cable",
    "Dumbbell Shrug": "Shrug, Dumbbell",
    "Fly": "Chest Fly, Dumbbell",
    "Incline Bench": "Incline Bench Press",
    "Incline Fly": "Incline Chest Fly, Dumbbell",
    "Safety Bar Squat": "Safety Squat Bar Squat",
    "Seated BB Shoulder Press": "Seated Overhead Press",
    "Seated DB Shoulder Press": "Shoulder Press, Dumbbell",
    "Straight-Back Seated Row": "Seated Row",
    "Straight-Leg Deadlift": "Straight Leg Deadlift",
    "Tricep Pushdown": "Triceps Pushdown",
    "Standing Triceps Ext": "Triceps Extension",
    "Lying Triceps Ext": "Skullcrusher, Dumbbell",
    "Kickback": "Cable Kickback",
    "Assisted Pull-Up": "Pull Up",
    "Assisted Chin-Up": "Chin Up",
    "Assisted Dip": "Chest Dip",
    "Rear Lateral Raise": "Reverse Fly, Dumbbell",
}

# custom -> distinct known stand-in (eval mode only)
PLACEHOLDER = {
    "Active Hang": "Push Up",
    "Dead Hang Stretch": "Goblet Squat",
    "Pull-Apart": "Hammer Curl",
    "Lateral-Incline Raise": "Reverse Curl",
    "Lean-In DB Lateral Raise": "Wrist Curl",
    "Kelso Shrug": "Leg Extension",
    "Hex-Bar Shrug": "Lying Leg Curl",
    "Corkscrew": "Sit Up",
    "Dragon Flag": "Hanging Leg Raise",
    "Bent-Knee (Soleus) Calf Raise": "Good Morning",
    "Deficit Standing Calf Raise": "Lunge",
    "Single-Leg Standing Calf Raise": "Reverse Lunge",
    "Underhand Pulldown": "Glute Bridge",
    "Underhand Bent-Over Row": "Pullover",
    "Alternating Curl": "Upright Row",
    "Zottman Curl": "Box Squat",
}
CUSTOM = list(PLACEHOLDER)


def clean(name):
    """Strip the protocol-only '(band)' annotation."""
    return re.sub(r"\s*\(band\)", "", name).strip()


def prod_name(name):
    """Parser-safe registered/referenced name. Liftoscript can't reference an
    exercise whose name contains parentheses, so strip them (e.g.
    'Bent-Knee (Soleus) Calf Raise' -> 'Bent-Knee Soleus Calf Raise')."""
    n = clean(name).replace("(", "").replace(")", "")
    return re.sub(r"\s{2,}", " ", n).strip()


def liftosaur_ref(name, mode="eval"):
    """Resolve a protocol exercise name to a Liftosaur reference."""
    n = clean(name)
    if n in CANONICAL:
        return CANONICAL[n]
    if n in CUSTOM:
        return PLACEHOLDER[n] if mode == "eval" else prod_name(n)
    return n  # already a built-in
