import unittest

from prepare_historical_constraints import derive


class HistoricalConstraintTests(unittest.TestCase):
    def test_local_projects_are_removed_by_normalized_name(self):
        kept, removed = derive(
            ["tooz===4.2.0\n", "etcd3gw===2.1.0\n", "oslo.utils===6.3.0\n"],
            {"Tooz", "etcd3gw"},
        )
        self.assertEqual(["oslo.utils===6.3.0\n"], kept)
        self.assertEqual(2, len(removed))


if __name__ == "__main__":
    unittest.main()
