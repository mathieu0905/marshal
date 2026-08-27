import unittest

from run_formal_e2_python_replay import extract_failure_signature


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

    def test_does_not_treat_test_summary_as_signature(self) -> None:
        self.assertIsNone(extract_failure_signature("Ran: 12 tests\n - Failed: 1\n"))


if __name__ == "__main__":
    unittest.main()
