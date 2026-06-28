---
title: Option A (Full In-App) — Build & Eval Plan
tags: [fitness, training, liftosaur, liftoscript, evals, rotation]
last_updated: 2026-06-28
---

# Option A — Full In-App Rotation: Build & Eval Plan

**Goal:** implement the entire protocol — T1/T2/T3 progression *and* shared-pool
rotation with cross-day collision avoidance — as a single **generated Liftoscript
program** that runs 100% in-app. No Python engine in the loop, no nightly job.
**Build only after the eval suite below passes.**

## 0. What's already proven (playground, 2026-06-28)

| Primitive | Result |
|---|---|
| Basic progression runs (`lp`) | ✅ |
| `numberOfSets = 0` hides an exercise | ✅ |
| Cross-exercise **read** (`state[tag].x`) | ❌ (we design around it) |
| Cross-exercise **write** (`state[tag].x = …`) | ✅ |
| `update: custom()` self-gates sets from own state | ✅ |
| Same-session cross-write visibility to controller | ✅ |
| Collision-aware advance (2-day pool, skip Day-2's active) | ✅ end-to-end |

The core mechanic works. The risk is now **scale and edge cases**, which is what
this plan stress-tests.

## 1. Architecture of the generated program

- **Pool exercises** — each appears on every day it can land; an `update: custom()`
  zeroes its sets unless its own per-day active flag (`a1/a2/a3/a4`) is set.
- **Controller exercise** (one, completed every session — piggybacks on a T1) holds
  all `area × day` active indices, the collision logic, and processes exhaustion
  flags written to it by pool exercises.
- **Per-exercise progression** — set-variations for ladders + `progress: custom()`
  for AMRAP/weight/level/reset; T2/T3 set `exhausted` → the controller rotates.
- **Generation** — `scripts/lifting/` emits the whole program from `protocol.py`.
  Nate never hand-edits Liftoscript; protocol changes → regenerate.

## 2. Method — differential testing against the Python engine

The existing, already-tested Python engine (`scripts/lifting/`) is the **oracle**.
For every scenario we drive the *same* inputs through:
- **(a)** the Liftosaur program via chained `POST /playground` calls, and
- **(b)** the Python engine,

and assert **identical state** (active exercise per slot, level, weight) at every
step. Any divergence is a bug in the generated Liftoscript.

## 3. Pre-requisite gates (must clear before generation)

- **P1 — Exercise registration (per Nate: register, never swap).** REST has no
  custom-exercise endpoint (confirmed 404). Path: the **MCP `create_custom_exercise`**
  tool (JSON-RPC with the `lftsk` key); fallback = one-time creation in the app.
  - Enumerate all ~60 protocol exercises → playground-parse each → list unknowns
    (already know "Dumbbell Row" is one) → register every unknown as a custom →
    re-parse until zero unknowns.
- **P2 — Weight re-seed on swap.** Controller cross-writes the incoming exercise's
  start weight into a state var; the exercise self-applies `last_L1 − 5` at L1.
  Validate the round-trip.
- **P3 — 4-day multi-skip collision.** A Core swap may need to skip up to 3 active
  exercises. Liftoscript loops are array-only (no `while`), so the skip must be
  **unrolled** (N bounded checks). Validate it never collides and never deadlocks.
- **P4 — Pending inputs from Nate:** band progression list; per-exercise anchors
  for bodyweight-rep + time T3.

## 4. Eval suite

### Tier 0 — Primitives (regression)
Re-assert all of §0 on every run (guards against Liftosaur behavior changes).

### Tier 1 — Per-exercise progression (each vs Python oracle)
- **T1 ladder:** AMRAP 0/1-4/≥5 → drop / +5 / +10; full L1→L2→L3→**90% reset** cycle.
- **T2 ladder:** +5 on completion; level drops on miss; `exhausted` set at L3 miss.
- **T3 weighted:** `25/20/15 → 20/15/10 → 15/8/7` ladder.
- **T3 bodyweight-rep:** anchor + ratio sets; +1 rep/success; level drops.
- **T3 time:** anchor + ratio; +1 s/success.
- **Prehab float:** +weight at ≥50 reps, −weight at <30; time +1 s; A/B alternation by day.
- **Band-assisted:** assistance reduced one level on success (gets harder).

### Tier 2 — Rotation
- 1-day area: plain advance, no collision.
- 2-day area: skip the 1 colliding exercise (the proven case, generalized).
- **4-day area (Core): skip up to 3** colliding exercises — the stress case for P3.
- Re-seed: incoming exercise starts at `last_L1 − 5`, level 1.
- Re-entry: an exercise that previously exhausted comes back around at `last_L1 − 5`.
- **Simultaneous exhaustion:** two slots finish L3 in the same session.
- Deadlock guard: pool == days (should never happen, pool ≥ days+1) — assert no corruption.

### Tier 3 — Differential long-run (the real stress test)
- Generate a **seeded pseudo-random** sequence of **≥200 sessions** across all 4
  days, with varied performance (hit / miss / AMRAP extras).
- Run the identical sequence through the Liftosaur program (chained playground) and
  the Python oracle.
- **Assert Liftosaur == oracle at every step** (active exercise, level, weight, per slot).
- Repeat across a **seed sweep** (≥10 seeds) to exercise many rotation orders.

### Tier 4 — Integrity & limits
- Full ~60-exercise + controller program **parses and runs** in the playground.
- State-variable count / script-length / program-size limits not exceeded.
- Playground latency acceptable for a full session.
- **Idempotency:** replaying the same session produces no extra state change.
- **Deviation handling:** Nate logs a different weight, skips an exercise, or does
  an extra set — the program must not corrupt rotation state.

## 5. Pass / fail gates

- All Tier 0–2 evals pass.
- Tier 3 matches the oracle at **100% of steps**, ≥200 sessions × ≥10 seeds.
- Full program parses + runs within the latency budget.
- **Zero unknown exercises** (every name built-in or registered as custom).

## 6. Harness

`scripts/lifting/evals/`:
- `generate.py` — emit the full Liftoscript program from `protocol.py`.
- `playground.py` — chained `POST /playground` runner (feeds updatedProgramText forward).
- `oracle.py` — drives the Python engine over the same sequence.
- `differential.py` — runs both, diffs state per step, reports first divergence.
- Seeded scenario generator; reuses the real KeyLifts/Ripley-derived starting weights.

## 7. Build & rollout (only after gates are green)

1. Register all custom exercises (P1).
2. Generate the program; `POST /programs` as a **new** Liftosaur program (don't touch
   the existing 8).
3. **Shadow week:** run it in-app alongside current KeyLifts logging; compare.
4. Cut over logging to Liftosaur.
5. Keep the Python engine as the **oracle / regression harness**, out of the live loop.

## 8. Risks & open questions

- Liftoscript **program-size / script-length limits** with ~60 exercises + a large
  controller — the biggest unknown; Tier 4 probes it early.
- **Multi-skip correctness** for 4-day pools (P3) — unrolled, easy to get subtly wrong.
- **Custom-exercise creation path** (P1) — MCP vs app; resolve first.
- **Simultaneous multi-write ordering** into the controller in one session.
- **Debugging is `print`-only** — hence the differential oracle is essential.
- Re-seed and re-entry weight math must match the engine exactly.
