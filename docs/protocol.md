---
title: Lifting Protocol — Deterministic Engine Spec
tags: [fitness, training, protocol, automation, keylifts, liftosaur]
last_updated: 2026-06-28
---

# Lifting Protocol — Deterministic Engine Spec

Single source of truth for the deterministic nightly engine that replaces Ripley's
LLM-driven progression. The engine reads the logged workout, applies fixed rules,
and builds the next session. No judgment calls, no LLM in the progression path.

## 1. Philosophy & scope

- 4 fixed main lifts (T1); supplemental/accessory work (T2/T3) rotates through
  target-area pools.
- Fully deterministic: same inputs → same next workout.
- **No preplanned deloads.** The only weight reset is the T1 L3→L1 cycle. Real rest
  comes from vacations (organic). Program intensity is tuned so scheduled deloads
  aren't needed.
- Home gym: barbell, dumbbells, hex bar, bands, bench, blocks. No seated/donkey calf
  machine.

## 2. Weekly structure

4 training days, lifted ~3×/week — the 4-day cycle floats across the calendar (no
fixed weekday mapping). Each day: **1 × T1 + 2 × T2 (supersetted) + 4 × T3
accessories (supersetted) + 1 prehab finisher (solo).**

T2/T3 cells name the **target area**; the exercise is pulled from that area's rotation queue.

| Day | T1 | T2 (×2) | T3 accessories (×4) | Prehab finisher |
|---|---|---|---|---|
| 1 | Deadlift | Horizontal Push · Horizontal Pull | Posterior/Hinge · Core · Calves · Traps | Face Pull / Pull-Apart |
| 2 | Overhead Press | Hinge · Vertical Pull | Side Delts · Core · Triceps · Biceps | Dead Hang Stretch |
| 3 | Back Squat | Vertical Push · Horizontal Pull | Single-leg/Quad · Core · Calves · Traps | Lateral-Incline / Rear Lateral Raise |
| 4 | Bench Press | Squat/Lower · Vertical Pull | Chest · Core · Triceps · Biceps | Active Hang |

Each pattern is trained ~2×/week (once as a T1, once as a T2).

## 3. T1 — main lifts (4 fixed, tracked independently)

Lifts: **Back Squat, Deadlift, Bench Press, Overhead Press.** They never rotate.

| Level | Scheme (last set AMRAP) | Eccentric tempo |
|---|---|---|
| L1 | 4×4 | 3 s |
| L2 | 4×3 | 2 s |
| L3 | 4×2 | 1 s (controlled) |

Per-session progression, judged on the **AMRAP (last) set** vs the level's base reps (4/3/2):

- **0 extra reps** → drop to next level, **keep the same weight**.
- **1–4 extra reps** → **+5 lb**, stay at level.
- **≥5 extra reps** → **+10 lb**, stay at level.
- **Miss the base reps** on any straight set → drop to next level (treated as a stall).

**Cycle reset:** after **L3 stalls** → return to **L1 at 90% of the previous L1 peak**
(round to nearest 5 lb), then climb again.

- Rationale: every reset is judged L1-vs-L1 (same 4×4, same 3 s tempo), so the
  cross-level tempo differences never need a conversion factor. Deterministic; nets a
  new L1 PR most cycles.
- Tunable knob: deload depth (default 90%; tighten to 95% if too much is lost).

## 4. T2 — supplementals (rotate through target-area pools)

Rep ladder, **no AMRAP**: **L1 4×12 → L2 4×10 → L3 4×8.**

- Complete all reps at the weight → **+5 lb** (or one band level less assistance) next exposure.
- Miss → drop to next level, keep weight.
- Fail out of L3 → exercise exhausted; **swap to the next exercise in the area queue**.
- Return to a previously-used exercise → start **5 lb / 1 band below its last L1 (4×12) weight**.
- The 2 T2s are supersetted.

## 5. T3 — accessories (rotate) + prehab finisher (fixed)

Three progression types; each exercise is tagged. Same level-drop / swap-after-L3 /
return-below-L1 structure as T2.

- **Weighted** — ladder **L1 25/20/15 → L2 20/15/10 → L3 15/8/7** (per-set rep
  targets). +5 lb / 1 band when all sets+reps complete.
- **Bodyweight-rep** — ratio ladder (set 1 = anchor reps; sets 2–3 scale by the ratios
  below). **+1 rep** to the anchor per success; round.
- **Time-based** — ratio ladder (set 1 = anchor seconds; sets 2–3 scale by ratios).
  **+1 s** to the anchor per success. (e.g. Plank 20/16/12 → 20/15/10 → 20/10/9.)

Level ratios (set1 / set2 / set3), set 1 anchored:

| Level | Ratio |
|---|---|
| L1 | 5 / 4 / 3 |
| L2 | 4 / 3 / 2 |
| L3 | 2 / 1 / 0.9 |

**Calves special:** all calf work uses **3 s up / 3 s down** tempo (doubles as calf/Achilles prehab).

T3 accessories are supersetted; the prehab finisher is performed solo.

### Prehab finishers — permanent per-day A/B fixtures (NOT in the rotation system)

1 set each, **alternate A/B every time that day recurs**. Never swap out.

- Rep-based: float the weight — **+weight at 50 reps, −weight below 30** (hold 30–50).
- Time-based: **+1 s vs the last completed set.**

| Day | A | B |
|---|---|---|
| 1 | Face Pull | Pull-Apart |
| 2 | Dead Hang Stretch | (same) |
| 3 | Lateral-Incline Raise | Rear Lateral Raise |
| 4 | Active Hang | (same) |

## 6. Target-area rotation pools

Each area is **one ordered queue** (list order = rotation order). Each day that calls
an area holds its **own active exercise**; when an exercise fails out, the slot
advances to the next queue entry **not currently active on another day**. Minimum pool
= (number of days the area appears on) + 1 — satisfied for all areas.

### T2 pools

| Area | Days | Pool (rotation order) |
|---|---|---|
| Horizontal Push | 1 | Incline Bench · Assisted Dip (band) |
| Vertical Push | 1 | Seated BB Shoulder Press · Seated DB Shoulder Press |
| Horizontal Pull | 2 | Pendlay Row · Straight-Back Seated Row · Bent-Over Row · Underhand Bent-Over Row |
| Vertical Pull | 2 | Lat Pulldown · Assisted Pull-Up (band) · Assisted Chin-Up (band) · Underhand Pulldown |
| Hinge | 1 | Romanian DL · Sumo DL |
| Squat / Lower | 1 | Front Squat · Safety Bar Squat |

### T3 pools

| Area | Days | Type | Pool (rotation order) |
|---|---|---|---|
| Posterior / Hinge | 1 | weighted | Straight-Leg DL · Hip Thrust |
| Single-leg / Quad | 1 | weighted | Bulgarian Split Squat · Step Up |
| Calves | 2 | weighted (3s/3s) | Standing Calf · Single-Leg Standing Calf · Deficit Standing Calf · Bent-Knee (Soleus) Calf |
| Traps | 2 | weighted | Barbell Shrug · Kelso Shrug · Dumbbell Shrug · Hex-Bar Shrug |
| Chest | 1 | weighted | Fly · Incline Fly |
| Side Delts | 1 | weighted | Lateral Raise · Lean-In DB Lateral Raise |
| Triceps | 2 | weighted | Standing Tri Ext · Lying Tri Ext · Tricep Pushdown · Kickback |
| Biceps | 2 | weighted | Alternating Curl · Zottman Curl · Cable Curl · Biceps Curl |
| Core | 4 | mixed | Ab Wheel · Russian Twist · Plank · Crunch · Dragon Flag · Corkscrew · Side Plank · Bicycle Crunch |

**Core order** is sequenced so consecutive picks hit different regions
(anti-extension → rotation → flexion → lateral, cycling cleanly 8→1).

**T3 type tags** — Core bodyweight-rep: Ab Wheel, Crunch, Dragon Flag, Corkscrew,
Bicycle Crunch. Time-based: Plank, Side Plank. Loaded-by-default (flip if trained
bodyweight): Russian Twist, Step-Up, Bulgarian Split Squat, Hip Thrust.

## 7. Engine state model

- Per **T1 lift**: `{ level, weight, prev_L1_peak }`
- Per **T2/T3 area**: `{ queue: [...], active_by_day: { day: exercise }, per_exercise: { level, load, last_L1_load } }`
- Per **prehab fixture**: `{ ab_toggle, load_or_time }`

Nightly run: read last session → match logged sets to the issued prescription → apply
the rules above → persist new state → emit next session.

## 8. Open items

- **Band progression list** (lightest → heaviest assistance) for the band-assisted
  lifts (Assisted Dip, Assisted Pull-Up, Assisted Chin-Up) — *pending from Nate.*
- **Initialization weights** for each T1 and each starting T2/T3 exercise. Seed
  reference (from existing `Program-Config.md`, may be stale): est. max Squat 250 /
  Deadlift 250 / Bench 185 / OHP 95.
- **I/O decision (parked):** read source (KeyLifts read-only vs Liftosaur) and where
  the next session is delivered (texted vs written into Liftosaur as Liftoscript).
