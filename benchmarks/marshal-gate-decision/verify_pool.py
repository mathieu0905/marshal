#!/usr/bin/env python3
"""Verify every accepted or rejected construction attempt in the local pool."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verify_case import verify


_REJECTION_REASONS = {
    "generator_missed_gold_test",
    "incomplete_selected_invariant_execution",
}


def verify_pool(cases_root: Path) -> dict:
    accepted = []
    rejected = []
    for case_dir in sorted(path for path in cases_root.iterdir() if path.is_dir()):
        public_case = case_dir / "public" / "case.json"
        gold = case_dir / "private" / "gold.json"
        rejection_path = case_dir / "rejection.json"
        if public_case.is_file() or gold.is_file():
            assert public_case.is_file() and gold.is_file(), \
                f"partial accepted case: {case_dir}"
            assert not rejection_path.exists(), f"accepted case also rejected: {case_dir}"
            accepted.append(verify(public_case, gold, None))
            continue
        assert rejection_path.is_file(), f"case attempt has no outcome: {case_dir}"
        rejection = json.loads(rejection_path.read_text(encoding="utf-8"))
        reason = (
            rejection.get("reason")
            or rejection.get("rejection_reason")
            or rejection.get("reason_code")
        )
        assert reason in _REJECTION_REASONS, \
            f"unknown rejection reason {reason!r}: {rejection_path}"
        pack_path = case_dir / "public" / "domain-pack.json"
        assert pack_path.is_file(), f"rejection lacks generated pack: {case_dir}"
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        assert pack["construction"]["outcome_inputs_read"] is False
        rejected.append({"case_id": case_dir.name, "reason": reason})

    return {
        "schema_version": "marshal-gate-pool-verification-1",
        "accepted": accepted,
        "rejected": rejected,
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "formal_benchmark": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "cases_root",
        type=Path,
        nargs="?",
        default=Path(__file__).resolve().parent / "cases",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_pool(args.cases_root)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
