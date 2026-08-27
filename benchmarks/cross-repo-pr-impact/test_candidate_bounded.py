#!/usr/bin/env python3
"""Tests for candidate-bounded audit, grouping, and code ranking."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from candidate_bounded_foundation import (
    allocate_proposed_splits,
    audit_catalogs,
    build_group_and_split_manifests,
    load_cases,
    validate_cinder_e2,
)
from candidate_code_ranker import normalize_score, rank_case
from prepare_case_inputs import cached_archive
from select_development_slice import evenly_spaced, select_slice
from materialize_data_ready_set import snapshot_readiness
from verify_final_e1_dataset import select_verified


def sample_case(case_id: str, project: str, target: str) -> dict:
    return {
        "case_id": case_id,
        "project": project,
        "source": {
            "repository": f"{project}/source",
            "base_commit": f"{case_id}-base",
            "candidate_commit": f"{case_id}-candidate",
        },
        "relations": [{
            "source_repository": f"{project}/source",
            "target_repository": target,
            "relation_kind": "runtime_api_contract",
        }],
        "targets": [{
            "repository": target,
            "impact_kind": "runtime_api_contract",
            "changed_paths": ["src/client.py"],
        }],
    }


class CandidateBoundedFoundationTests(unittest.TestCase):
    def test_rebuilt_catalogs_match_independent_source_snapshots(self) -> None:
        dataset_root = Path(__file__).resolve().parent
        audit = audit_catalogs(dataset_root, load_cases(dataset_root))
        eligible = {
            row["project"] for row in audit if row["current_formal_eligible"]
        }
        self.assertEqual(eligible, {"ethereum", "opentelemetry", "rust"})

    def test_project_groups_do_not_cross_proposed_splits(self) -> None:
        cases = [
            sample_case("a1", "a", "a/client"),
            sample_case("a2", "a", "a/other"),
            sample_case("b1", "b", "b/client"),
        ]
        audit = [
            {"project": "a", "current_formal_eligible": False},
            {"project": "b", "current_formal_eligible": False},
        ]
        groups, splits, summary = build_group_and_split_manifests(cases, audit)
        self.assertEqual(len(groups), 3)
        a_splits = {
            row["proposed_split_after_catalog_rebuild"]
            for row in splits if row["project"] == "a"
        }
        self.assertEqual(len(a_splits), 1)
        self.assertTrue(summary["leakage_free"])

    def test_singletons_are_forced_to_development(self) -> None:
        assigned = allocate_proposed_splits({"large": 9, "single": 1}, {"single"})
        self.assertEqual(assigned["single"], "development")

    def test_strict_cinder_e2_requires_all_three_arms(self) -> None:
        summary = {"arms": {
            "a0": {"result": "pass", "target_repair": False, "alembic": "old"},
            "a1": {"result": "expected_failure", "target_repair": False, "alembic": "new"},
            "a2": {"result": "pass", "target_repair": True, "alembic": "new"},
        }}
        self.assertTrue(validate_cinder_e2(summary))
        summary["arms"]["a0"]["result"] = "fail"
        self.assertFalse(validate_cinder_e2(summary))


class CandidateCodeRankerTests(unittest.TestCase):
    def test_ranker_reads_candidate_code_and_prefers_rare_patch_term(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case_dir = Path(temporary) / "case-1"
            repositories = case_dir / "repositories"
            matching = repositories / "org__matching"
            other = repositories / "org__other"
            matching.mkdir(parents=True)
            other.mkdir(parents=True)
            (case_dir / "input.json").write_text(
                json.dumps({"case_id": "case-1", "source": {"repository": "org/source"}}),
                encoding="utf-8",
            )
            (case_dir / "source.patch").write_text(
                "+ def resolveBasemapCatalog():\n", encoding="utf-8"
            )
            (matching / "catalog.py").write_text(
                "def resolve_basemap_catalog(): pass\n", encoding="utf-8"
            )
            (other / "unrelated.py").write_text(
                "def render_dashboard(): pass\n", encoding="utf-8"
            )
            prediction, diagnostics = rank_case(case_dir, top_k=1)
            self.assertEqual(prediction["targets"][0]["repository"], "org/matching")
            self.assertEqual(prediction["targets"][0]["execution_result"], "not_assessed")
            self.assertGreater(diagnostics["candidate_repositories_read"], 0)
            self.assertFalse(diagnostics["label_inputs_read"])

    def test_sqrt_file_normalization_attenuates_large_repository_score(self) -> None:
        self.assertEqual(normalize_score(20.0, 100, "sqrt_files"), 2.0)
        self.assertEqual(normalize_score(20.0, 100, "none"), 20.0)


class PreparationCacheTests(unittest.TestCase):
    def test_archive_cache_reuses_repository_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            snapshot = {
                "commit": "abc123",
                "archive_url": "https://example.invalid/archive.tar.gz",
            }
            with patch("prepare_case_inputs.download") as download_mock:
                download_mock.side_effect = lambda _url, destination: destination.write_bytes(b"archive")
                first = cached_archive("org/repo", snapshot, cache)
                second = cached_archive("org/repo", snapshot, cache)
            self.assertEqual(first, second)
            self.assertEqual(first.read_bytes(), b"archive")
            self.assertEqual(download_mock.call_count, 1)


class DevelopmentSliceTests(unittest.TestCase):
    def test_even_spacing_includes_temporal_endpoints(self) -> None:
        items = [{"case_id": str(index)} for index in range(5)]
        self.assertEqual(
            [item["case_id"] for item in evenly_spaced(items, 3)],
            ["0", "2", "4"],
        )

    def test_selection_uses_only_catalog_time_and_case_id(self) -> None:
        inputs = [
            {
                "case_id": case_id,
                "candidate_repository_catalog": "candidate-repositories.json#demo",
                "observation_cutoff": cutoff,
                "ignored_label": label,
            }
            for case_id, cutoff, label in (
                ("later", "2025-02-01T00:00:00Z", "target-a"),
                ("early", "2025-01-01T00:00:00Z", "target-b"),
                ("latest", "2025-03-01T00:00:00Z", "target-c"),
            )
        ]
        selected = select_slice(inputs, {"demo": 2})
        self.assertEqual([item["case_id"] for item in selected], ["early", "latest"])


class DataReadySetTests(unittest.TestCase):
    def test_snapshot_readiness_requires_exact_catalog_and_nonfailure_statuses(self) -> None:
        ready = snapshot_readiness({"org/a", "org/b"}, {"repositories": [
            {"repository": "org/a", "status": "available"},
            {"repository": "org/b", "status": "not_created_by_cutoff"},
        ]})
        self.assertTrue(ready["snapshot_complete"])
        failed = snapshot_readiness({"org/a"}, {"repositories": [
            {"repository": "org/a", "status": "fetch_failed"},
        ]})
        self.assertFalse(failed["snapshot_complete"])


class FinalE1SelectionTests(unittest.TestCase):
    @staticmethod
    def verified_row(
        case_id: str, project: str, source_number: int, target_number: int
    ) -> dict:
        return {
            "case_id": case_id,
            "project": project,
            "verification_status": "verified",
            "source_repository": f"{project}/spec",
            "source_pull_request": source_number,
            "target_local_audits": [{
                "repository": f"{project}/client",
                "pull_request": target_number,
            }],
        }

    def test_verified_reserve_replaces_failed_preferred_within_project(self) -> None:
        rows = [
            self.verified_row("a-preferred", "a", 1, 11),
            self.verified_row("a-reserve", "a", 2, 12),
            self.verified_row("b-preferred", "b", 3, 13),
        ]
        rows[0]["verification_status"] = "rejected"
        selected, conflicts, backfills = select_verified(
            rows,
            ["a-preferred", "a-reserve", "b-preferred"],
            ["a-preferred", "b-preferred"],
            {"a": 1, "b": 1},
        )
        self.assertEqual(
            [item["case_id"] for item in selected], ["b-preferred", "a-reserve"]
        )
        self.assertEqual(conflicts, [])
        self.assertEqual(backfills, {"a": 1})

    def test_duplicate_target_pr_is_not_admitted_twice(self) -> None:
        first = self.verified_row("first", "a", 1, 11)
        duplicate = self.verified_row("duplicate", "a", 2, 11)
        reserve = self.verified_row("reserve", "a", 3, 12)
        selected, conflicts, backfills = select_verified(
            [first, duplicate, reserve],
            ["first", "duplicate", "reserve"],
            ["first", "duplicate"],
            {"a": 2},
        )
        self.assertEqual([item["case_id"] for item in selected], ["first", "reserve"])
        self.assertEqual(conflicts[0]["case_id"], "duplicate")
        self.assertEqual(backfills, {"a": 1})


if __name__ == "__main__":
    unittest.main()
