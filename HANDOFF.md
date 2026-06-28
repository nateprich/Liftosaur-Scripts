# HANDOFF — Liftosaur-Scripts

_Last updated: 2026-06-28. Read this top to bottom before touching anything._

This document is the single source of resume context. If you are a fresh agent,
everything you need to continue is here or in `docs/`.

---

## 1. Mission

Nate runs a custom strength program. He wants it to **run itself inside the
Liftosaur app** with zero ongoing server/LLM dependency, replacing a prior
LLM-based trainer agent ("Ripley"). The program has unusual rules (per-lift rep
ladders with tempo, AMRAP-driven loading, and **shared-pool exercise rotation with
cross-day collision avoidance**).

**Decision (locked): Option A — full in-app.** A Python generator emits one
self-contained Liftoscript program. After it's installed in Liftosaur, the app
runs all progression AND rotation natively. The Python code is a build tool +
**eval oracle**, not a runtime dependency.

(Option B = hybrid, where a nightly Python job does the rotation, was the prior
plan and remains the fallback if Option A evals fail. See `docs/integration-plan.md`.)

---

## 2. Status dashboard

| Item | State |
|---|---|
| Protocol fully specified | ✅ `docs/protocol.md` |
| Liftoscript feasibility (primitives) | ✅ proven in playground (see §5) |
| Collision-aware rotation works in-app | ✅ 2-day end-to-end + **4-day multi-skip vs oracle** (`lifting/evals/rotation_poc.py`) |
| Exercise name resolution (58 names) | ✅ 19 known, 23 canonical maps, 16 customs |
| Full-program generator | ✅ `lifting/evals/generate.py` |
| **Tier-4 size probe (make-or-break)** | ✅ **PASSED — 37 KB / 108 listings parses+runs 0.7s** |
| Differential eval harness | ⬜ TODO (next) |
| Real rotation/progression wired into generator | ⬜ TODO (generator currently uses *representative* scripts) |
| Tier 0-3 evals vs oracle | ⬜ TODO |
| Register 16 customs in Liftosaur (production) | ⬜ TODO (MCP; not needed for evals) |
| Pending from Nate | band progression list; per-exercise bodyweight/time anchors |

---

## 3. The protocol (summary — full spec in `docs/protocol.md`)

- **4 days**, 4 fixed **T1** main lifts (Back Squat, Deadlift, Bench, Overhead Press).
  T1 ladder: `L1 4x4 (3s ecc) → L2 4x3 (2s) → L3 4x2 (1s)`, last set AMRAP.
  AMRAP extra reps: `0 → drop a level (keep weight); 1-4 → +5lb; ≥5 → +10lb`.
  L3 stall → reset to **L1 at 90% of previous L1 peak**.
- **T2** supplementals: `4x12 → 4x10 → 4x8`, +5lb on completion, drop level on miss,
  **exhaust at L3 → rotate to next pool exercise**.
- **T3** accessories: weighted `25/20/15 → 20/15/10 → 15/8/7`; bodyweight-rep + time
  use an anchor+ratio ladder (`5/4/3, 4/3/2, 2/1/.9`). Calves use 3s/3s tempo.
- **Rotation:** each target area is a queue shared across the days it appears on.
  Each day holds its own active exercise; when one exhausts, advance to the next
  queue entry **not active on another day** (collision avoidance). Re-entry starts
  at `last_L1 − 5`.
- **Prehab finishers**: fixed per-day A/B, float weight to hold 30-50 reps (or +1s).

Pools, day formula, and exact rules are all in `lifting/protocol.py` (the
machine-readable source) and `docs/protocol.md` (prose).

---

## 4. Architecture of the generated program (Option A)

- Every pool exercise is **listed on every day** its slot appears, each with an
  `update: custom()` that zeroes its sets unless its own per-day active flag
  (`a1..a4`) is set.
- A **single centralized controller exercise** ("Wrist Roller", tag 999, in no
  pool) holds ALL `area×day` rotation indices as state vars, processes exhaustion,
  and **cross-writes** each pool exercise's active flag. One controller is required
  because cross-exercise *reads* don't work (see §5) — all rotation state must live
  in one exercise so its script can read its own state.
- T1 uses set-variations for the ladder + a `progress: custom()` for AMRAP/reset.
- The Python `engine.py` reproduces all rules and is the **oracle** the generated
  program is differentially tested against.

---

## 5. Empirical findings (VERIFIED in the Liftosaur playground — do not re-derive)

| Capability | Result | Implication |
|---|---|---|
| `lp`/basic progression runs in playground | ✅ | mechanics confirmed |
| Cross-exercise **WRITE** `state[tag].x = v` | ✅ | controller can push flags |
| Cross-exercise **READ** `state[tag].x` | ❌ returns nothing | **must centralize all state in one controller** |
| `numberOfSets = 0` | ✅ hides an exercise (`0x5`) | the gating lever |
| `update: custom()` self-gates from own state | ✅ (`setIndex==0`) | per-day visibility |
| Same-session cross-write visible to controller | ✅ | controller reacts same session, no lag |
| Collision-aware rotation, 2-day + 4-day pools | ✅ end-to-end | rotation is fully in-app-able |
| 4-day multi-skip (unrolled, no `while`) vs oracle | ✅ 6-step sequence all match | the riskiest rotation case is solid |
| `set_state_variable` *command* timing | ⚠ applies **+1 session late** | drive exhaustion via exercise progress (own `completedReps` or cross-write), NOT the command |
| Full program (108 listings, 37 KB, big controller) | ✅ parses+runs 0.7s | **no size ceiling — Option A viable** |
| REST custom-exercise endpoint | ❌ 404 | register customs via MCP or app |

### Playground API (the eval workhorse)
`POST https://www.liftosaur.com/api/v1/playground`
Body: `{"programText": "...", "day": 1, "week": 1, "commands": [...]}`
Returns `{"data": {"workout": "...", "updatedProgramText": "..."}}`.
- **Commands need spaces**: `"complete_set(1, 1)"`, `"change_reps(1, 4, 9)"`,
  `"change_weight(1, 1, 185lb)"`, `"finish_workout()"`. (No-space forms silently
  no-op — this cost an hour.)
- `updatedProgramText` reflects post-workout state incl. state-var values — diff it.
- A program with all-inactive gated exercises still returns 200 (empty workout).

### Other API endpoints (premium key)
- `GET /api/v1/programs` — list (Nate has 8 existing; don't clobber them).
- `GET /api/v1/programs/<id>` / `PUT /api/v1/programs/<id>` `{name,text}`.
- `POST /api/v1/programs` `{name,text}` — create new.
- `GET /api/v1/history` — empty until Nate logs in Liftosaur.

### Gotchas
- **Cloudflare 403s the default Python user-agent.** Always send a browser UA
  (`Mozilla/5.0 ... Chrome/124.0`). `keylifts.py` already does.
- **This machine's shell sometimes loses `curl`/`head` from PATH.** Prefix commands
  with `export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"`,
  or just use `python3` + `urllib` (more reliable).

---

## 6. Keys & environment

- Keys live in **`~/Claude/.env`** (gitignored, NOT in this repo):
  `LIFTOSAUR_API_KEY` (lftsk_…) and `KEYLIFTS_API_KEY` (kl_…).
- `lifting/config.py` resolves keys in order: env var → this repo's `.env` →
  `~/Claude/.env`. So scripts work on this machine without copying secrets.
- A fresh machine: `cp .env.example .env` and fill in.
- **Never commit `.env` or raw key values.**

---

## 7. Exercise name resolution (`lifting/liftosaur_names.py`)

58 protocol exercises → 19 already known + 23 CANONICAL maps (same movement, correct
Liftosaur name — e.g. Back Squat→Squat, Lying Triceps Ext→Skullcrusher) + 16
CUSTOM. Per Nate: never silently swap a *different* movement; same-movement variants
use canonical names, genuinely-absent ones become customs.

- **Evals** use a known PLACEHOLDER for each custom (so the playground parses).
  `liftosaur_ref(name, mode="eval")`.
- **Production** uses the real custom name (`mode="prod"`) after registering it.
- The 16 customs (must register for production): Active Hang, Dead Hang Stretch,
  Pull-Apart, Lateral-Incline Raise, Lean-In DB Lateral Raise, Kelso Shrug,
  Hex-Bar Shrug, Corkscrew, Dragon Flag, Bent-Knee (Soleus) Calf Raise, Deficit
  Standing Calf Raise, Single-Leg Standing Calf Raise, Underhand Pulldown,
  Underhand Bent-Over Row, Alternating Curl, Zottman Curl.

---

## 8. How to run

```bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
python3 -m lifting.run --selftest          # Python engine self-test (rules + rotation)
python3 -m lifting.run                      # derive starting weights + Session 1
python3 - <<'PY'                            # size probe
import sys; sys.path.insert(0,'.')
from lifting.evals import generate as G
print(len(G.generate(mode='eval')), 'bytes')
PY
```

Playground call pattern: see `lifting/evals/` and §5. Re-use the helper shape from
the probe scripts (POST programText + commands, read updatedProgramText).

---

## 9. Remaining work (in order)

1. **Differential harness** (`lifting/evals/`): `playground.py` (chain sessions:
   feed `updatedProgramText` forward), `oracle.py` (drive `engine.py` over the same
   inputs), `differential.py` (diff state per step; report first divergence).
2. **Wire the REAL rules into `generate.py`.** It currently emits *representative*
   scripts (valid + correct size, not exact). Replace with:
   - T1 set-variation ladder + AMRAP/+5/+10/90%-reset progress.
   - T2/T3 ladders + exhaustion cross-write to the controller (`state[999].sN_ex = 1`).
   - Controller: real collision-aware advance (skip up to 3 for 4-day Core — note
     Liftoscript has no `while`, so **unroll** the skip), re-seed `last_L1 − 5`.
   - Prehab float; calf 3s/3s tempo (descriptions); band-assist (assisting equipment).
3. **Run Tier 0-3 evals** against the oracle (see `docs/eval-plan.md`). Gate:
   100% step-match over ≥200 sessions × ≥10 seeds.
4. **Register the 16 customs** (production). REST has no endpoint (404). Use the
   **MCP `create_custom_exercise`** tool (server `https://www.liftosaur.com/mcp`,
   JSON-RPC, Bearer lftsk key) or one-time app creation. Then `generate(mode="prod")`.
5. **Install**: `POST /programs` a NEW program (don't touch the existing 8),
   shadow-run vs current logging, then cut over.

Commit frequently (small logical commits) so progress survives context limits.

---

## 10. Decision log

- **Why Option A over B:** rotation is provably doable in-app (§5), and the size
  probe passed, so the whole protocol can live in Liftosaur with no server. B (a
  nightly Python rotation job) remains the fallback if eval correctness can't be
  reached. The marginal complexity of A is absorbed by *generating* the Liftoscript.
- **Why a centralized controller:** cross-exercise reads don't work, so collision
  avoidance (which needs to see other days' active exercise) must read from one
  exercise's own state. Cross-*writes* work, so the controller pushes flags outward.
- **Source of truth:** `lifting/protocol.py` for rules; this repo is now the
  canonical home for the build (originals were authored under `~/Claude/scripts/lifting`
  and `~/Claude/areas/physical-health/exercise/`).
