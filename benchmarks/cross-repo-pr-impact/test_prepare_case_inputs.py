import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from prepare_case_inputs import cache_case_archives, extract_archive


class PrepareCaseInputsTests(unittest.TestCase):
    def test_archives_only_accepts_an_exact_cached_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "org__repo" / "abc.tar.gz"
            archive.parent.mkdir()
            with tarfile.open(archive, "w:gz") as bundle:
                payload = b"value\n"
                member = tarfile.TarInfo("wrapper/value.txt")
                member.size = len(payload)
                bundle.addfile(member, io.BytesIO(payload))
            snapshot = {
                "repositories": [{
                    "repository": "org/repo",
                    "commit": "abc",
                    "archive_url": "https://invalid.example/unused.tar.gz",
                    "status": "available",
                }]
            }

            count = cache_case_archives(snapshot, root, workers=2)

        self.assertEqual(1, count)

    def test_extract_skips_absolute_link_but_keeps_code_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "snapshot.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                payload = b"class Example {}\n"
                code = tarfile.TarInfo("wrapper/src/Example.java")
                code.size = len(payload)
                bundle.addfile(code, io.BytesIO(payload))
                link = tarfile.TarInfo("wrapper/CMakeLists.txt")
                link.type = tarfile.SYMTYPE
                link.linkname = "/opt/ros/share/catkin/cmake/toplevel.cmake"
                bundle.addfile(link)
            destination = root / "output"
            extract_archive(archive, destination)
            self.assertEqual(
                "class Example {}\n",
                (destination / "src/Example.java").read_text(encoding="utf-8"),
            )
            self.assertFalse((destination / "CMakeLists.txt").exists())


if __name__ == "__main__":
    unittest.main()
