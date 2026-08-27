import io
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from run_formal_e2_candidate_code_blind import (
    rank_case,
    scan_archive,
    scan_commit,
    select_query_terms,
)


class FormalE2CandidateCodeBlindTests(unittest.TestCase):
    def test_query_terms_use_only_visible_input_and_patch(self):
        item = {"source": {
            "subject": "Rename WidgetParser entry point",
            "changed_paths": ["src/widget_parser.py"],
        }}
        terms = select_query_terms(item, "+def parse_widget(value):\n", limit=8)
        self.assertIn("widget", terms)
        self.assertIn("parser", terms)
        self.assertNotIn("source", terms)

    def test_scan_commit_counts_real_git_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(["git", "-C", str(repository), "config", "user.name", "test"], check=True)
            subprocess.run(["git", "-C", str(repository), "config", "user.email", "test@example.test"], check=True)
            (repository / "widget.py").write_text("def parse_widget():\n    return 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "widget.py"], check=True)
            subprocess.run(["git", "-C", str(repository), "commit", "-qm", "fixture"], check=True)
            commit = subprocess.check_output(
                ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True
            ).strip()
            scan = scan_commit(repository / ".git", commit, ["parse_widget"])
        self.assertEqual("available", scan["status"])
        self.assertEqual(1, scan["files_read"])
        self.assertEqual(1, scan["matched_query_terms"])
        self.assertEqual(["widget.py"], scan["paths"])

    def test_scan_archive_counts_exact_snapshot_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "snapshot.tar.gz"
            content = b"def parse_widget():\n    return 1\n"
            with tarfile.open(archive, "w:gz") as handle:
                member = tarfile.TarInfo("repo-commit/widget.py")
                member.size = len(content)
                handle.addfile(member, io.BytesIO(content))
            scan = scan_archive(archive, "commit", ["parse_widget"])
        self.assertEqual("available", scan["status"])
        self.assertEqual(1, scan["files_read"])
        self.assertEqual(1, scan["matched_query_terms"])
        self.assertEqual(["widget.py"], scan["paths"])

    def test_scan_archive_reads_selected_members_in_archive_order(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "snapshot.tar.gz"
            with tarfile.open(archive, "w:gz") as handle:
                for name in ("z.java", "a.java", "m.java"):
                    content = f"class {name[0].upper()} {{ parse_widget(); }}\n".encode()
                    member = tarfile.TarInfo(f"repo-commit/{name}")
                    member.size = len(content)
                    handle.addfile(member, io.BytesIO(content))

            offsets = []
            original = tarfile.TarFile.extractfile

            def record_offset(handle, member):
                offsets.append(member.offset_data)
                return original(handle, member)

            with mock.patch.object(tarfile.TarFile, "extractfile", record_offset):
                scan = scan_archive(archive, "commit", ["parse_widget"])

        self.assertEqual("available", scan["status"])
        self.assertEqual(sorted(offsets), offsets)

    def test_rank_case_excludes_source_and_reads_available_candidates(self):
        item = {
            "case_id": "case-1",
            "source": {
                "repository": "org/source",
                "subject": "Change WidgetParser",
                "changed_paths": ["widget.py"],
            },
        }
        snapshot = {"repositories": [
            {"repository": "org/source", "status": "available", "commit": "a"},
            {"repository": "org/target", "status": "available", "commit": "b"},
            {"repository": "org/future", "status": "not_created_by_cutoff"},
        ]}
        with tempfile.TemporaryDirectory() as directory:
            patch_dir = Path(directory)
            (patch_dir / "case-1.patch").write_text("+WidgetParser\n", encoding="utf-8")

            def scanner(mirror, commit, query):
                self.assertEqual("b", commit)
                return {
                    "status": "available", "tracked_file_count": 4,
                    "files_read": 4, "text_files_read": 4, "bytes_read": 80,
                    "matched_query_terms": 2, "matching_token_count": 3,
                    "paths": ["test_widget.py"], "path_query_overlap": 1,
                }

            prediction, diagnostic = rank_case(
                item, snapshot, patch_dir, Path(directory) / "mirrors", 5, 1, scanner
            )
        self.assertEqual("org/target", prediction["targets"][0]["repository"])
        self.assertTrue(diagnostic["candidate_code_read"])
        self.assertEqual(1, diagnostic["candidate_repositories_read"])


if __name__ == "__main__":
    unittest.main()
