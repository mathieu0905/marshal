import unittest
import subprocess
import tempfile
from pathlib import Path

from run_formal_e2_python_replay import extract_failure_signature, clone_checkout


class ExactCloneTests(unittest.TestCase):
    def test_clone_uses_exact_commit_and_rejects_typo_even_with_replay_ref(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(source), '-c', 'user.name=Test',
                    '-c', 'user.email=test@example.test', *args], text=True).strip()
            (source / 'data').write_text('original')
            git('add', 'data')
            git('commit', '-qm', 'original')
            original = git('rev-parse', 'HEAD')
            git('branch', 'replay-source-base', original)
            (source / 'data').write_text('newer')
            git('commit', '-qam', 'newer')
            clone_checkout(source, root / 'valid', original)
            self.assertEqual((root / 'valid/data').read_text(), 'original')
            typo = ('0' if original[0] != '0' else '1') + original[1:]
            with self.assertRaisesRegex(RuntimeError, 'exact replay commit is unavailable'):
                clone_checkout(source, root / 'invalid', typo)


class FailureSignatureTest(unittest.TestCase):
    def test_extracts_qualified_exception(self) -> None:
        output = "    webtest.app.AppError: Bad response: 400 Bad Request\n"
        self.assertEqual(
            "webtest.app.AppError: Bad response: 400 Bad Request",
            extract_failure_signature(output),
        )

    def test_extracts_command_parser_error(self) -> None:
        output = "check_parser: error: argument --ephemeral: Missing required keys size.\n"
        self.assertEqual(
            "check_parser: error: argument --ephemeral: Missing required keys size.",
            extract_failure_signature(output),
        )

    def test_extracts_policy_exception_before_secondary_logging_error(self) -> None:
        output = """Failed 1 tests - output below:
    oslo_policy.policy.PolicyNotAuthorized: secrets:post is disallowed by policy
    webob.exc.HTTPForbidden: Secret creation attempt not allowed
    AttributeError: 'NoneType' object has no attribute 'request'
"""
        self.assertEqual(
            "oslo_policy.policy.PolicyNotAuthorized: secrets:post is disallowed by policy",
            extract_failure_signature(output),
        )

    def test_extracts_bare_exception_from_stestr_failed_section(self) -> None:
        output = """Failed 1 tests - output below:
test.case
    fixtures._fixtures.timeout.TimeoutException
"""
        self.assertEqual(
            "fixtures._fixtures.timeout.TimeoutException",
            extract_failure_signature(output),
        )

    def test_ignores_bare_exception_without_stestr_failed_section(self) -> None:
        self.assertIsNone(
            extract_failure_signature("fixtures._fixtures.timeout.TimeoutException\n")
        )

    def test_does_not_treat_test_summary_as_signature(self) -> None:
        self.assertIsNone(extract_failure_signature("Ran: 12 tests\n - Failed: 1\n"))


if __name__ == "__main__":
    unittest.main()
