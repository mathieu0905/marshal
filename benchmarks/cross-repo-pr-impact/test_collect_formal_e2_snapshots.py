import tempfile
import unittest
import os
import subprocess
from pathlib import Path

from collect_formal_e2_snapshots import collect_checkpointed, local_git_resolver, FIRST_PARENT_RULE


class FormalE2SnapshotTests(unittest.TestCase):
    def test_later_merge_does_not_expose_early_dated_branch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / 'org__repo.git'
            subprocess.run(['git', 'init', '--initial-branch=master', str(repo)], check=True, capture_output=True)
            def git(*args, day=1):
                environment = {**os.environ, 'GIT_AUTHOR_DATE': f'2024-01-{day:02d}T00:00:00Z',
                               'GIT_COMMITTER_DATE': f'2024-01-{day:02d}T00:00:00Z'}
                return subprocess.check_output(['git', '-C', str(repo), '-c', 'user.name=Snapshot Test',
                    '-c', 'user.email=snapshot@example.test', *args], env=environment, stderr=subprocess.DEVNULL, text=True).strip()
            (repo / 'base').write_text('base')
            git('add', 'base')
            git('commit', '-m', 'base')
            git('branch', 'topic')
            (repo / 'main').write_text('main')
            git('add', 'main')
            git('commit', '-m', 'main', day=2)
            expected = git('rev-parse', 'HEAD')
            git('checkout', 'topic')
            (repo / 'future').write_text('not on master at cutoff')
            git('add', 'future')
            git('commit', '-m', 'topic', day=3)
            git('checkout', 'master')
            git('merge', '--no-ff', 'topic', '-m', 'late merge', day=10)
            # The production resolver receives a bare Git-directory path.
            resolver_root = root / 'mirrors'
            resolver_root.mkdir()
            subprocess.run(['git', 'clone', '--bare', str(repo), str(resolver_root / 'org__repo.git')], check=True, capture_output=True)
            result = local_git_resolver(resolver_root)('', 'org/repo', '2024-01-05T00:00:00Z')
            self.assertEqual(result['commit'], expected)

    def test_first_parent_mode_recollects_old_terminal_checkpoint(self):
        assignment = {'case_id': 'a', 'candidate_repository_catalog': 'candidate-repositories.json#c', 'observation_cutoff': '2024-01-01T00:00:00Z'}
        calls = []
        def fake(catalogs, selected, workers, prior_rows=None):
            calls.append(prior_rows)
            return [{'case_id': 'a', 'repositories': [{'repository': 'org/repo', 'status': 'available'}]}]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            collect_checkpointed({'c': {}}, [assignment], output, 1, fake)
            collect_checkpointed({'c': {}}, [assignment], output, 1, fake, resolution_rule=FIRST_PARENT_RULE)
            collect_checkpointed({'c': {}}, [assignment], output, 1, fake, resolution_rule=FIRST_PARENT_RULE)
        self.assertEqual(calls, [None, None])

    def test_checkpoint_resumes_terminal_cases(self):
        assignments = [
            {"case_id": "a", "candidate_repository_catalog": "candidate-repositories.json#c", "observation_cutoff": "2024-01-01T00:00:00Z"},
            {"case_id": "b", "candidate_repository_catalog": "candidate-repositories.json#c", "observation_cutoff": "2024-01-02T00:00:00Z"},
        ]
        calls = []

        def fake(catalogs, selected, workers, prior_rows=None):
            case_id = selected[0]["case_id"]
            calls.append(case_id)
            return [{
                "case_id": case_id,
                "repositories": [{"repository": "org/repo", "status": "available"}],
            }]

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            first = collect_checkpointed({"c": {}}, assignments, output, 1, fake)
            second = collect_checkpointed({"c": {}}, assignments, output, 1, fake)
        self.assertEqual(["a", "b"], calls)
        self.assertEqual(2, first["completed_case_count"])
        self.assertEqual(2, second["completed_case_count"])

    def test_checkpoint_writes_completed_batches(self):
        assignments = [
            {"case_id": letter, "candidate_repository_catalog": "candidate-repositories.json#c", "observation_cutoff": "2024-01-01T00:00:00Z"}
            for letter in ("a", "b", "c")
        ]
        calls = []

        def fake(catalogs, selected, workers, prior_rows=None):
            calls.append([row["case_id"] for row in selected])
            return [{
                "case_id": row["case_id"],
                "repositories": [{"repository": "org/repo", "status": "available"}],
            } for row in selected]

        with tempfile.TemporaryDirectory() as temporary:
            metrics = collect_checkpointed(
                {"c": {}}, assignments, Path(temporary), 1, fake, case_batch_size=2
            )
        self.assertEqual([["a", "b"], ["c"]], calls)
        self.assertEqual(3, metrics["completed_case_count"])


if __name__ == "__main__":
    unittest.main()
