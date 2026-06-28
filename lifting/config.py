"""Locate API keys without committing them.

Resolution order for a key name:
  1. process environment variable
  2. repo-local .env (this repo root)
  3. ~/Claude/.env  (same-machine fallback, where the live keys currently live)
"""

import os


def _env_files():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    return [os.path.join(repo, ".env"), os.path.expanduser("~/Claude/.env")]


def load_key(name):
    if os.environ.get(name):
        return os.environ[name]
    for path in _env_files():
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(name + "="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None
