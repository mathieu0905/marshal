"""Central DB-path resolution, shared by the CLI, the FastAPI dashboard, and the worker.

Precedence:
  1. $MARSHAL_DB — explicit override, always wins.
  2. The live workspace checkout's db (~/workspace/marshal/marshal.db) if it exists —
     the database the marshal skill actually writes to.
  3. $MARSHAL_HOME/marshal.db (MARSHAL_HOME defaults to this checkout's root) —
     the local fallback (e.g. the plugin copy's demo db).
"""
import os
from pathlib import Path


def marshal_home() -> Path:
    env = os.environ.get("MARSHAL_HOME")
    if env:
        return Path(env)
    # this file is <home>/src/marshal_core/config.py
    return Path(__file__).resolve().parents[2]


def db_url() -> str:
    if os.environ.get("MARSHAL_DB"):
        return os.environ["MARSHAL_DB"]
    live = Path.home() / "workspace" / "marshal" / "marshal.db"
    if live.exists():
        return f"sqlite:///{live}"
    return f"sqlite:///{marshal_home() / 'marshal.db'}"
