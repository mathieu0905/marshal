import unittest

from collect_e2_candidate_snapshots import catalog_id, classify_resolution, collect


class E2CandidateSnapshotTests(unittest.TestCase):
    def test_catalog_reference_parser(self):
        self.assertEqual("example", catalog_id("candidate-repositories.json#example"))
        with self.assertRaises(ValueError):
            catalog_id("catalogs.json#example")

    def test_collection_does_not_read_labels(self):
        catalogs = {
            "example": {
                "repository_host": "opendev.org",
                "repositories": ["openstack/cinder", "openstack/nova"],
            }
        }
        assignments = [{
            "case_id": "e2-test",
            "candidate_repository_catalog": "candidate-repositories.json#example",
            "observation_cutoff": "2026-08-12T00:46:10Z",
        }]
        calls = []

        def resolver(project, repository, cutoff):
            calls.append((project, repository, cutoff))
            return {
                "repository": repository,
                "host": "opendev.org",
                "status": "available",
                "commit": "a" * 40,
                "committed_at": cutoff,
                "archive_url": "https://example.invalid/archive.tar.gz",
            }

        rows = collect(catalogs, assignments, 2, resolver=resolver)
        self.assertEqual(1, len(rows))
        self.assertEqual(2, len(rows[0]["repositories"]))
        self.assertEqual({"openstack/cinder", "openstack/nova"}, {
            call[1] for call in calls
        })

    def test_github_catalog_uses_github_host_selector(self):
        catalogs = {"example": {
            "repository_host": "github.com",
            "repositories": ["assertj/assertj-core"],
        }}
        assignments = [{
            "case_id": "e2-test",
            "candidate_repository_catalog": "candidate-repositories.json#example",
            "observation_cutoff": "2022-01-29T12:04:35Z",
        }]
        calls = []

        def resolver(project, repository, cutoff):
            calls.append((project, repository, cutoff))
            return {"repository": repository, "host": "github.com", "status": "available"}

        collect(catalogs, assignments, 1, resolver=resolver)
        self.assertEqual("rust", calls[0][0])

    def test_resume_reuses_terminal_rows_and_retries_only_failures(self):
        catalogs = {"example": {
            "repository_host": "github.com",
            "repositories": ["org/available", "org/retry"],
        }}
        assignments = [{
            "case_id": "e2-test",
            "candidate_repository_catalog": "candidate-repositories.json#example",
            "observation_cutoff": "2022-01-01T00:00:00Z",
        }]
        prior_rows = [{
            "case_id": "e2-test",
            "repositories": [
                {"repository": "org/available", "host": "github.com", "status": "available"},
                {"repository": "org/retry", "host": "github.com", "status": "fetch_failed"},
            ],
        }]
        calls = []

        def resolver(_project, repository, _cutoff):
            calls.append(repository)
            return {"repository": repository, "host": "github.com", "status": "available"}

        rows = collect(
            catalogs, assignments, 1, resolver=resolver, prior_rows=prior_rows
        )
        self.assertEqual(["org/retry"], calls)
        self.assertTrue(all(row["status"] == "available" for row in rows[0]["repositories"]))

    def test_missing_historical_repository_is_terminal_not_created_claim(self):
        result = classify_resolution({
            "repository": "old/repository",
            "host": "github.com",
            "status": "fetch_failed",
            "error": "gh: Not Found (HTTP 404)",
        })
        self.assertEqual("unavailable_at_collection", result["status"])
        self.assertIn("deletion, transfer, or rename", result["reason"])

    def test_empty_repository_is_terminal_unavailable(self):
        result = classify_resolution({
            "repository": "apache/incubator-eagle",
            "host": "github.com",
            "status": "fetch_failed",
            "error": "gh: Git Repository is empty. (HTTP 409)",
        })
        self.assertEqual("unavailable_at_collection", result["status"])
        self.assertIn("no commits", result["reason"])

    def test_access_blocked_repository_is_terminal_unavailable(self):
        result = classify_resolution({
            "repository": "blocked/repository",
            "host": "github.com",
            "status": "fetch_failed",
            "error": "gh: Repository access blocked (HTTP 403)",
        })
        self.assertEqual("unavailable_at_collection", result["status"])
        self.assertIn("access is blocked", result["reason"])

    def test_catalog_can_record_independently_confirmed_unavailable_root(self):
        catalogs = {"example": {
            "repository_host": "github.com",
            "repositories": ["old/repository"],
            "known_unavailable_repositories": {
                "old/repository": "GitHub repository API returned 404 during provenance resolution"
            },
        }}
        assignments = [{
            "case_id": "e2-test",
            "candidate_repository_catalog": "candidate-repositories.json#example",
            "observation_cutoff": "2022-01-01T00:00:00Z",
        }]

        def resolver(*_args):
            raise AssertionError("known unavailable repository should not be fetched")

        rows = collect(catalogs, assignments, 1, resolver=resolver)
        self.assertEqual(
            "unavailable_at_collection", rows[0]["repositories"][0]["status"]
        )

    def test_case_snapshot_override_recovers_deleted_canonical_repository(self):
        catalogs = {"example": {
            "repository_host": "github.com",
            "repositories": ["old/repository"],
            "known_unavailable_repositories": {
                "old/repository": "canonical repository was deleted"
            },
        }}
        assignments = [{
            "case_id": "e2-test",
            "candidate_repository_catalog": "candidate-repositories.json#example",
            "observation_cutoff": "2022-01-01T00:00:00Z",
            "candidate_snapshot_overrides": {
                "old/repository": {
                    "repository": "old/repository",
                    "host": "registry.example",
                    "status": "available",
                    "commit": "a" * 40,
                    "committed_at": "2021-12-01T00:00:00Z",
                    "archive_url": "https://registry.example/package.tgz",
                    "snapshot_source_kind": "published_source_artifact",
                }
            },
        }]

        def resolver(*_args):
            raise AssertionError("case snapshot override should not invoke resolver")

        rows = collect(catalogs, assignments, 1, resolver=resolver)
        recovered = rows[0]["repositories"][0]
        self.assertEqual("available", recovered["status"])
        self.assertEqual("published_source_artifact", recovered["snapshot_source_kind"])

    def test_case_snapshot_override_after_cutoff_is_rejected(self):
        catalogs = {"example": {
            "repository_host": "github.com",
            "repositories": ["old/repository"],
        }}
        assignments = [{
            "case_id": "e2-test",
            "candidate_repository_catalog": "candidate-repositories.json#example",
            "observation_cutoff": "2022-01-01T00:00:00Z",
            "candidate_snapshot_overrides": {
                "old/repository": {
                    "repository": "old/repository",
                    "host": "github.com",
                    "status": "available",
                    "commit": "a" * 40,
                    "committed_at": "2022-01-02T00:00:00Z",
                    "archive_url": "https://example.invalid/archive.tar.gz",
                }
            },
        }]
        with self.assertRaisesRegex(ValueError, "after cutoff"):
            collect(catalogs, assignments, 1, resolver=lambda *_args: {})


if __name__ == "__main__":
    unittest.main()
