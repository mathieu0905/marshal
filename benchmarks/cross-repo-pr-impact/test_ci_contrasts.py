from __future__ import annotations

import unittest
from unittest import mock

from materialize_causal_pilot import accepted_job_record, snapshot
from verify_ci_contrasts import (
    commits_for_change,
    inventory_items,
    verify_candidate,
    verify_times,
)


class InventoryTests(unittest.TestCase):
    def test_reads_only_structured_zuul_items(self) -> None:
        inventory = """
all:
  vars:
    unrelated:
      change: '12'
      commit_id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    zuul:
      items:
        - change: '12'
          commit_id: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
        - change: '13'
          commit_id: cccccccccccccccccccccccccccccccccccccccc
"""
        items = inventory_items(inventory)
        self.assertEqual(
            commits_for_change(items, 12),
            {"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
        )


class TransitionTimeTests(unittest.TestCase):
    def test_target_revision_may_follow_source_retry_revision(self) -> None:
        checks, _ = verify_times(
            "2026-08-17 09:32:24.000000000",
            "2026-08-18 15:55:32.000000000",
            "2026-08-18 18:11:40.000000000",
            {
                "start_time": "2026-08-17T09:42:09",
                "end_time": "2026-08-17T10:07:44",
            },
            {
                "start_time": "2026-08-19T10:12:49",
                "end_time": "2026-08-19T12:48:29",
            },
        )
        self.assertTrue(all(checks.values()))

    def test_dependency_uploaded_before_failure_finishes_is_not_clean_contrast(self) -> None:
        checks, _ = verify_times(
            "2026-08-17 09:32:24.000000000",
            "2026-08-17 09:55:00.000000000",
            "2026-08-17 09:50:00.000000000",
            {
                "start_time": "2026-08-17T09:42:09",
                "end_time": "2026-08-17T10:07:44",
            },
            {
                "start_time": "2026-08-17T10:12:49",
                "end_time": "2026-08-17T12:48:29",
            },
        )
        self.assertFalse(checks["dependency_added_after_failure"])


class CandidateJobRetentionTests(unittest.TestCase):
    @mock.patch("verify_ci_contrasts.target_detail")
    @mock.patch("verify_ci_contrasts.code_diff", return_value=b"same patch")
    @mock.patch("verify_ci_contrasts.verify_contrast")
    def test_preserves_every_composition_verified_job(
        self,
        verify_contrast_mock: mock.Mock,
        _code_diff_mock: mock.Mock,
        target_detail_mock: mock.Mock,
    ) -> None:
        target_detail_mock.return_value = {
            "project": "target/repository",
            "created": "2026-08-20 00:00:00.000000000",
            "subject": "companion fix",
        }
        verified_template = {
            "status": "composition_verified",
            "tenant": "openstack",
            "target_commit": "c" * 40,
            "target_revision_created": "2026-08-20 00:00:00.000000000",
            "failure_build_uuid": "failure",
            "failure_log_url": "https://logs.example/failure/",
            "success_build_uuid": "success",
            "success_log_url": "https://logs.example/success/",
            "times": {},
            "time_checks": {},
            "inventory_checks": {},
            "buildset_ref_patchsets": {},
        }
        verify_contrast_mock.side_effect = [
            {**verified_template, "job": "unrelated-job"},
            {**verified_template, "job": "semantically-aligned-job"},
        ]
        candidate = {
            "source_repository": "source/repository",
            "source_pr": 10,
            "source_created": "2026-08-19 00:00:00.000000000",
            "source_subject": "source change",
            "before_revision": {
                "number": 1,
                "sha": "a" * 40,
                "created": "2026-08-19 00:00:00.000000000",
            },
            "after_revision": {
                "number": 2,
                "sha": "b" * 40,
                "created": "2026-08-20 01:00:00.000000000",
            },
            "added_dependency_prs": [20],
            "same_job_contrasts": [
                {"job": "unrelated-job"},
                {"job": "semantically-aligned-job"},
            ],
        }

        result = verify_candidate(candidate)

        self.assertEqual(result["composition_verified_job_count"], 2)
        self.assertEqual(
            [item["job"] for item in result["composition_verified_jobs"]],
            ["unrelated-job", "semantically-aligned-job"],
        )

    def test_materialization_selects_the_semantically_accepted_job(self) -> None:
        record = {
            "source_pr": 10,
            "job": "unrelated-job",
            "failure_build_uuid": "failure-unrelated",
            "success_build_uuid": "success-unrelated",
            "composition_verified_jobs": [
                {
                    "job": "unrelated-job",
                    "failure_build_uuid": "failure-unrelated",
                    "success_build_uuid": "success-unrelated",
                },
                {
                    "job": "semantically-aligned-job",
                    "failure_build_uuid": "failure-aligned",
                    "success_build_uuid": "success-aligned",
                },
            ],
        }
        review = {
            "job_reviews": [
                {
                    "job": "unrelated-job",
                    "failure_build_uuid": "failure-unrelated",
                    "success_build_uuid": "success-unrelated",
                    "decision": "rejected",
                },
                {
                    "job": "semantically-aligned-job",
                    "failure_build_uuid": "failure-aligned",
                    "success_build_uuid": "success-aligned",
                    "decision": "accepted",
                    "primary_for_materialization": True,
                },
                {
                    "job": "corroborating-job",
                    "failure_build_uuid": "failure-corroborating",
                    "success_build_uuid": "success-corroborating",
                    "decision": "accepted",
                },
            ]
        }

        selected = accepted_job_record(record, review)

        self.assertEqual(selected["job"], "semantically-aligned-job")
        self.assertEqual(selected["failure_build_uuid"], "failure-aligned")
        self.assertEqual(selected["success_build_uuid"], "success-aligned")


class InventorySnapshotTests(unittest.TestCase):
    @mock.patch("materialize_causal_pilot.github_commit")
    def test_github_inventory_commit_uses_github_archive(
        self, github_commit_mock: mock.Mock
    ) -> None:
        github_commit_mock.return_value = {
            "commit": {"committer": {"date": "2026-08-10T12:00:00Z"}}
        }
        projects = {
            "novnc/novnc": {
                "canonical_hostname": "github.com",
                "commit": "a" * 40,
            }
        }

        result = snapshot("novnc/novnc", "2026-08-11T00:00:00Z", projects)

        self.assertEqual(result["host"], "github.com")
        self.assertEqual(result["committed_at"], "2026-08-10T12:00:00Z")
        self.assertEqual(
            result["archive_url"],
            "https://github.com/novnc/novnc/archive/" + "a" * 40 + ".tar.gz",
        )


if __name__ == "__main__":
    unittest.main()
