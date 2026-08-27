import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collect_formal_e2_candidate_mirrors import (
    catalog_repositories,
    clone_repository,
    repository_path,
)


class FormalE2CandidateMirrorTests(unittest.TestCase):
    def test_catalog_union_is_sorted_and_deduplicated(self):
        catalogs = {
            "a": {"repositories": ["org/z", "org/a"]},
            "b": {"repositories": ["org/a", "org/b"]},
        }
        self.assertEqual(
            ["org/a", "org/b", "org/z"], catalog_repositories(catalogs)
        )

    def test_repository_path_is_unambiguous_for_catalog_names(self):
        self.assertEqual(
            "openstack__cinder.git",
            repository_path(Path("mirrors"), "openstack/cinder").name,
        )

    def test_complete_existing_mirror_is_reused_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = repository_path(root, "org/repo")
            destination.mkdir()
            with patch(
                "collect_formal_e2_candidate_mirrors.is_complete_mirror",
                return_value=True,
            ), patch("collect_formal_e2_candidate_mirrors.subprocess.run") as run:
                row = clone_repository("org/repo", root)
            self.assertEqual("available", row["status"])
            self.assertEqual("reused", row["network_action"])
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
