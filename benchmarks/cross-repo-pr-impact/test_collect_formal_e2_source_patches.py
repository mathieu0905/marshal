import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collect_formal_e2_source_patches import collect_patch


class FormalE2SourcePatchTests(unittest.TestCase):
    @patch("collect_formal_e2_source_patches.download")
    def test_removes_gerrit_message_metadata(self, mocked_download):
        import base64

        payload = base64.b64encode(
            b"Subject: change\nDepends-On: hidden\n\ndiff --git a/a b/a\n--- a/a\n+++ b/a\n"
        )
        mocked_download.side_effect = lambda url, destination: destination.write_bytes(payload)
        event = {"candidate_id": "formal-opendev-1", "opening": {"number": 1}}
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = collect_patch(event, output)
            content = (output / "formal-opendev-1.patch").read_bytes()
        self.assertEqual("available", result["status"])
        self.assertTrue(content.startswith(b"diff --git"))
        self.assertNotIn(b"Depends-On", content)


if __name__ == "__main__":
    unittest.main()
