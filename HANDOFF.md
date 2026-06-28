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
| Differential eval harness | ✅ **ALL PASS** — controller collision (4 seeds×25), T1 ladder, T2 ladder+exhaust (`lifting/evals/differential.py`) |
| Real rotation/progression wired into generator | ✅ generator now emits oracle-validated scripts (per-group weights, T1 AMRAP ladder, T2/T3 ladder+exhaust cross-write, collision-aware controller) |
| Per-exercise seeded weights (prod) | ✅ Ripley seed → 0lb bodyweight → 45lb default (`generate(mode="prod")`) |
| Register 16 customs in Liftosaur (production) | ✅ all 16 via MCP `create_custom_exercise` (`lifting/evals/register_customs.py`) |
| **Program installed** | ✅ **"T1/T2/T3 Auto-Rotation" (id=svgippbw)** — NEW program, existing 9 untouched (`lifting/install.py`) |
| Prod program parses+runs (account context) | ✅ 50 KB, 0.74s, no error (REST playground + MCP `run_playground`) |
| In-app smoke test (Nate) | ⬜ verify runtime gating + log one real session (see §9) |
| Pending from Nate | confirm band-vs-rep progression for bodyweight T3; per-exercise bodyweight/time anchors; real seed weights for non-seeded pool lifts |

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
| **Differential vs oracle** (controller collision 4×25, T1 ladder, T2 ladder+exhaust) | ✅ **ALL PASS** | progression + rotation math is correct |
| Per-group weights `3x4 W,1x4+ W` | ✅ required | shared trailing weight after a comma (`3x4,1x4+ 100lb`) breaks the parser |
| `change_reps` moves target AND completed together | ⚠ | tests compare against a hardcoded `var.base`, not `reps` |
| `setVariationIndex` reads return the **pre-change** value | ⚠ writes deferred to script end | parse active level from the `!` marker, not `state.lvl` |
| Exercise name containing `(` | ❌ `parse_error` at the name | `prod_name()` strips parens (registered + referenced name must match) |
| Custom muscle names | validated vocabulary | `Rhomboids` invalid → use `Trapezius Lower/Middle Fibers`; types: core/pull/push/legs/upper/lower |
| Program-stats estimator | ⚠ does **not** run `update:` gating | reports inflated sets/min (~84/day); the real day view is gated — trust the app, not the estimate |

### MCP endpoint (account context — customs resolve here)
`POST https://www.liftosaur.com/mcp`, JSON-RPC `tools/call`, Bearer key, header
`Accept: application/json, text/event-stream`. Tools: `create_program`,
`update_program`, `get_program` (returns JSON wrapper `{id,name,text,...}` — use
`.text`), `delete_program`, `list_programs`, `run_playground`, `list_exercises`,
`create_custom_exercise` / `list_custom_exercises` / `update_` / `delete_`,
`get_history` / `create_history_record`, `*_gym` / `*_equipment`, `*_measurement`.

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
python3 -m lifting.evals.differential       # differential evals vs oracle (ALL PASS)
python3 -m lifting.evals.register_customs   # register/refresh the 16 custom exercises (idempotent)
python3 -m lifting.install                  # create the prod program (refuses if name exists)
python3 -m lifting.install --update         # overwrite the installed program in place
```

Playground call pattern: see `lifting/evals/` and §5 (POST programText + commands,
read updatedProgramText). MCP pattern (account context, customs resolve): JSON-RPC
`tools/call` to `https://www.liftosaur.com/mcp` with Bearer key — tools include
`create_program`, `update_program`, `get_program`, `run_playground`,
`create_custom_exercise`, `list_*`. Note `get_program` returns a JSON wrapper
`{id,name,text,...}` — use the `.text` field.

---

## 9. Remaining work / open issues

**Build + install are complete and validated.** What's left is in-app acceptance
and two intentional simplifications to confirm with Nate.

1. **In-app smoke test (critical — needs Nate's phone/app).** Open the installed
   program "T1/T2/T3 Auto-Rotation" and confirm:
   - **Runtime gating:** each day shows only the active rotation (~6-8 exercises),
     not all ~30 pool members. The `update: custom()` script sets `numberOfSets=0`
     for inactive ones (validated primitive, §5). ⚠️ The Liftosaur **program-stats
     estimator does NOT run `update:` scripts**, so it reports ~84 sets / ~446 min
     per day — that's a static-analysis artifact, not the real workout. Trust the
     actual day view, not the stats number.
   - **One logged session:** complete a T1 (AMRAP) + a T2 to L-up, and force a T2
     exhaust over a few sessions to watch the rotation advance. The progression
     math is oracle-validated, but the playground can't simulate a partial "miss"
     for a `completedReps >= reps` script, so a single real session is the final proof.
2. **Bands — decided, not yet wired.** Assisted Dip/Pull-Up/Chin-Up rotate **in the
   same pool** as their weighted siblings (so rotation is unchanged); only progression
   differs. To finish: (a) oracle steps assist DOWN `protocol.BANDS` per success →
   bodyweight → +weight; (b) generator emits an assist branch (Liftosaur assisting
   equipment / negative weight — needs a one-off playground test); (c) band suite in
   differential; (d) `install --update`. ~1-2 hr. All other T2/T3 use the weighted
   ladder; non-band bodyweight starts 0lb +5lb. Per-exercise bodyweight/time anchors
   still pending from Nate.
3. **Starting weights.** Seeded lifts use Ripley values; non-seeded weighted pool
   exercises default to **45lb** (placeholder to dial in-app on first exposure).
   Provide real seeds (or a KeyLifts pull) to replace the defaults.
4. **Prehab float** uses a simple ±5lb auto-adjust to hold 30-50 reps — confirm it
   matches intent; tempo/“+1s” variants are descriptive only.

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
- **Shipped (2026-06-28):** differential evals went green, the generator was wired
  to emit the validated scripts, all 16 customs were registered via MCP, and the
  program was installed as **"T1/T2/T3 Auto-Rotation" (id=svgippbw)** — a NEW program,
  leaving Nate's existing 9 untouched. Remaining work is in-app acceptance (§9), not
  build work. The build path (`protocol → engine/oracle → generate → install`) is
  fully reproducible via `python3 -m lifting.install`.
- **Controller named "Rotation Engine" (2026-06-28):** the carrier exercise (tag 999,
  1x1 0lb) is a registered custom so it's self-explanatory in the app. Eval mode keeps
  "Wrist Roller" for deterministic probes. Bands: assisted variants rotate in-pool —
  hybrid Option B kept as the documented revert path (`docs/integration-plan.md`).
