import unittest

from verify_formal_e2_blind_run import verify


class FormalE2BlindRunVerificationTests(unittest.TestCase):
    def fixture(self):
        inputs = [{"case_id": "c", "source": {"repository": "org/source"}}]
        snapshots = [{"case_id": "c", "repositories": [
            {"repository": "org/source", "status": "available"},
            {"repository": "org/target", "status": "available"},
        ]}]
        predictions = [{"case_id": "c", "targets": [{"repository": "org/target"}]}]
        diagnostics = [{
            "case_id": "c", "label_inputs_read": False, "candidate_code_read": True,
            "ranking": [{"repository": "org/target", "files_read": 2, "text_files_read": 2}],
        }]
        manifest = {"labels_read": False, "network_used": False, "candidate_code_read": True}
        return inputs, snapshots, predictions, diagnostics, manifest

    def test_accepts_complete_local_code_read(self):
        metrics = verify(*self.fixture(), "1 --- SIGCHLD {...} ---\n")
        self.assertTrue(metrics["blind_run_valid"])
        self.assertEqual(2, metrics["candidate_text_file_reads"])

    def test_rejects_network_syscall(self):
        with self.assertRaisesRegex(ValueError, "network syscall"):
            verify(*self.fixture(), '1 connect(3, {sa_family=AF_INET}, 16) = 0\n')

    def test_accepts_seccomp_enforcement_evidence(self):
        values = list(self.fixture())
        values[4]["network_enforcement"] = "libseccomp_inherited_syscall_filter"
        metrics = verify(*values, None, {
            "mechanism": "libseccomp_inherited_syscall_filter",
            "socket_probe_blocked": True,
            "socket_probe_errno": 1,
        })
        self.assertEqual("libseccomp_inherited_syscall_filter", metrics["network_isolation"])

    def test_rejects_zero_text_reads(self):
        values = list(self.fixture())
        values[3][0]["ranking"][0]["text_files_read"] = 0
        with self.assertRaisesRegex(ValueError, "zero candidate"):
            verify(*values, "")


if __name__ == "__main__":
    unittest.main()
