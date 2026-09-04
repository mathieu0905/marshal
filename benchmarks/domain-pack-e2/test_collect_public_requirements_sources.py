from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import collect_public_requirements_sources as collector  # noqa: E402
from collect_public_requirements_sources import (  # noqa: E402
    AUTHORING_INFLUENCE,
    fetch_requirements_source_openings,
    load_excluded_source_numbers,
    public_source_row,
    select_source_openings,
)


def _opening(number: int, created_at: str = "2026-01-01 00:00:00.000000000") -> dict:
    return {
        "provider": "gerrit",
        "repository": "openstack/requirements",
        "number": number,
        "change_id": f"I{number}",
        "url": f"https://review.opendev.org/c/openstack/requirements/+/{number}",
        "created_at": created_at,
        "branch": "master",
        "subject": "Update a constraint",
        "base_commit": "a" * 40,
        "head_commit": "b" * 40,
        "changed_paths": ["upper-constraints.txt"],
    }


def test_public_frame_contains_no_target_identifier_or_repository() -> None:
    public = public_source_row(_opening(123456))
    serialized = json.dumps(public, sort_keys=True)

    assert "target" not in serialized.lower()
    assert "dependent_change" not in serialized
    assert public["opening"]["repository"] == "openstack/requirements"


def test_all_authoring_sources_and_extra_jsonl_are_excluded(tmp_path: Path) -> None:
    authoring = json.loads(AUTHORING_INFLUENCE.read_text(encoding="utf-8"))
    authoring_numbers = {
        int(identifier.removeprefix("formal-opendev-"))
        for identifier in authoring["source_change_ids"]
    }
    extra = tmp_path / "extra-exclusions.jsonl"
    extra.write_text(
        '{"source_change_id":"formal-opendev-123456"}\n', encoding="utf-8"
    )
    excluded = load_excluded_source_numbers(AUTHORING_INFLUENCE, [extra])

    openings = [_opening(number) for number in sorted(authoring_numbers | {123456, 999999})]
    selected = select_source_openings(openings, excluded)

    assert 849284 in authoring_numbers
    assert authoring_numbers <= excluded
    assert [opening["number"] for opening in selected] == [999999]


def test_project_query_prefilter_prevents_non_requirements_fetch(monkeypatch) -> None:
    fetched: list[int] = []

    def fake_fetch(number: int) -> dict:
        fetched.append(number)
        return _opening(number)

    monkeypatch.setattr(collector, "fetch_source_opening", fake_fetch)
    openings, failures = fetch_requirements_source_openings(
        lead_source_numbers={101, 202, 303},
        requirements_change_numbers={202},
        workers=1,
    )

    assert fetched == [202]
    assert [opening["number"] for opening in openings] == [202]
    assert failures == []
