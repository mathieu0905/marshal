#!/usr/bin/env python3
"""Run one existing project command and persist its unmodified process evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        raise SystemExit("a command is required after --")
    environment = os.environ.copy()
    for item in args.env:
        key, separator, value = item.partition("=")
        if not separator or not key:
            raise SystemExit(f"invalid --env value: {item}")
        environment[key] = value
    started_at = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    started = time.monotonic()
    result = subprocess.run(
        command,
        cwd=args.cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        check=False,
    )
    finished_at = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "command.log").write_text(result.stdout, encoding="utf-8")
    summary = {
        "schema_version": "1.0",
        "command": command,
        "cwd": str(args.cwd.resolve()),
        "environment_overrides": dict(item.split("=", 1) for item in args.env),
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": time.monotonic() - started,
        "exit_code": result.returncode,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
