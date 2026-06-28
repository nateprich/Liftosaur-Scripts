# Liftosaur-Scripts

Deterministic, fully **in-app** implementation of Nate's custom strength protocol
(T1/T2/T3 with shared-pool exercise rotation) as a generated **Liftoscript**
program for [Liftosaur](https://www.liftosaur.com). Replaces an LLM-based trainer
agent ("Ripley") with rules that run inside the app — no server, no nightly job.

> **New here? Read [`HANDOFF.md`](HANDOFF.md) first.** It has the full state,
> empirical findings, and what to do next. This README is just orientation.

## Layout

```
lifting/
  protocol.py         # the protocol encoded as data — single source of truth for rules
  engine.py           # pure-Python deterministic engine = the EVAL ORACLE
  keylifts.py         # KeyLifts read-only client (historical starting weights)
  liftosaur_names.py  # protocol name -> Liftosaur exercise reference (+ customs)
  config.py           # API-key loader (env -> ./.env -> ~/Claude/.env)
  run.py              # CLI: derive weights, print Session 1, --selftest
  evals/
    generate.py       # emits the full Option-A Liftoscript program
docs/
  protocol.md         # the canonical protocol spec (rules)
  integration-plan.md # how Liftosaur is used (Option B/A history)
  eval-plan.md        # the build + eval plan being executed
```

## Quick start

```bash
cp .env.example .env   # fill in LIFTOSAUR_API_KEY (+ KEYLIFTS_API_KEY); or rely on ~/Claude/.env
python3 -m lifting.run --selftest          # verify the Python engine rules
python3 -c "import sys;sys.path.insert(0,'.');from lifting.evals import generate as G;print(len(G.generate()))"
```

Requires Python 3.9+ (stdlib only) and a **Liftosaur premium** account for the API.
