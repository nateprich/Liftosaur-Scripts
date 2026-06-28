"""
KeyLifts read-only client + starting-weight derivation.

Reads KEYLIFTS_API_KEY from the repo .env (no external deps). Fetches the
workout history (GET /api/v1/workouts) and computes, per exercise, the most
recent working-set weight and the all-time max — used to seed the engine.
"""

import json
import urllib.request
import urllib.error

from . import config

API_BASE = "https://keylifts.com/api/v1"


def load_env_key(name="KEYLIFTS_API_KEY"):
    """Resolve the key via config (env var -> repo .env -> ~/Claude/.env)."""
    return config.load_key(name)


def fetch_workouts(api_key=None, cache="/tmp/klw.json", use_cache_on_fail=True):
    """Return the list of workout dicts. Falls back to a local cache on error."""
    api_key = api_key or load_env_key()
    if api_key:
        req = urllib.request.Request(
            f"{API_BASE}/workouts",
            headers={
                "Authorization": f"Bearer {api_key}",
                # Cloudflare 403s the default Python user-agent; mimic a browser.
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/124.0 Safari/537.36",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                if cache:
                    try:
                        with open(cache, "w") as f:
                            json.dump(data, f)
                    except OSError:
                        pass
                return data.get("data", [])
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            if not (use_cache_on_fail and os.path.exists(cache)):
                raise
            print(f"[keylifts] live fetch failed ({e}); using cache {cache}")
    if cache and os.path.exists(cache):
        with open(cache) as f:
            return json.load(f).get("data", [])
    raise RuntimeError("No KeyLifts API key and no cache available")


def _working_sets(exercise):
    """Non-warmup sets with a positive weight."""
    out = []
    for s in exercise.get("exercise_sets", []):
        if s.get("type") != "warmup" and (s.get("weight") or 0) > 0:
            out.append(s)
    return out


def derive_from_keylifts(workouts):
    """
    Per logged exercise name: {recent_weight, recent_date, max_weight, n_sessions}.
    Uses the top working-set weight in each session.
    """
    by_name = {}
    for w in workouts:
        date = w.get("date_started") or ""
        for ex in w.get("exercises", []):
            name = ex.get("name")
            sets = _working_sets(ex)
            if not name or not sets:
                continue
            top = max(s.get("weight") or 0 for s in sets)
            rec = by_name.setdefault(name, {"recent_weight": 0, "recent_date": "",
                                            "max_weight": 0, "n_sessions": 0})
            rec["n_sessions"] += 1
            rec["max_weight"] = max(rec["max_weight"], top)
            if date > rec["recent_date"]:
                rec["recent_date"] = date
                rec["recent_weight"] = top
    return by_name
