import tempfile
import unittest
from pathlib import Path

from collect_formal_opendev_sources import (
    catalog_for,
    dependent_source_frame,
    legacy_source_numbers,
    systematic_frame_sample,
)


class FormalOpenDevSourceCollectorTests(unittest.TestCase):
    def test_public_source_frame_can_be_excluded_from_later_wave(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source-events.jsonl"
            path.write_text(
                '{"source_change_family":"opendev-change-123-opening"}\n',
                encoding="utf-8",
            )
            self.assertIn(123, legacy_source_numbers([path]))

    def test_revealed_target_metadata_can_be_excluded_from_later_wave(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "target-changes.jsonl"
            path.write_text(
                '{"candidate_id":"case","targets":[{"number":456}]}\n',
                encoding="utf-8",
            )
            self.assertIn(456, legacy_source_numbers([path]))

    def test_dependent_orientation_keeps_one_source_per_component(self):
        dependents = [
            {"_number": 20, "created": "2024-01-02"},
            {"_number": 21, "created": "2024-01-03"},
            {"_number": 40, "created": "2024-02-02"},
        ]
        links = [
            (10, 20, "url-10"),
            (11, 20, "url-11"),
            (10, 21, "url-10"),
            (30, 40, "url-30"),
        ]
        frame = dependent_source_frame(dependents, links)
        self.assertEqual([20, 40], [row["source_pr"] for row in frame])
        self.assertEqual([10, 11], frame[0]["target_prs"])
        self.assertEqual(4, frame[0]["component_size"])

    def test_systematic_sample_excludes_legacy_sources(self):
        frame = [{"source_pr": number} for number in range(10)]
        selected = systematic_frame_sample(frame, 4, {1, 4, 8})
        self.assertEqual(4, len(selected))
        self.assertFalse({1, 4, 8} & {row["source_pr"] for row in selected})

    def test_catalog_assignment_uses_source_membership_only(self):
        catalogs = {
            "formal-openstack": {"repositories": ["openstack/nova"]},
            "formal-starlingx": {"repositories": ["starlingx/config"]},
        }
        self.assertEqual("formal-openstack", catalog_for("openstack/nova", catalogs))
        self.assertEqual("formal-starlingx", catalog_for("starlingx/config", catalogs))
        self.assertIsNone(catalog_for("example/other", catalogs))


if __name__ == "__main__":
    unittest.main()
