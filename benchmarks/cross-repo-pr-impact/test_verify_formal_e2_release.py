import datetime as dt
import unittest

from verify_formal_e2_release import timestamp


class FormalE2ReleaseVerifierTests(unittest.TestCase):
    def test_normalizes_opendev_timestamp(self):
        value = timestamp("2025-01-02 03:04:05.000000000")
        self.assertEqual(dt.UTC, value.tzinfo)
        self.assertEqual(2025, value.year)


if __name__ == "__main__":
    unittest.main()
