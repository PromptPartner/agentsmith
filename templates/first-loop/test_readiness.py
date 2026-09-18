import unittest

from readiness import is_ready


class ReadinessTests(unittest.TestCase):
    def test_all_checks_pass_is_ready(self) -> None:
        self.assertTrue(is_ready({"tests": True, "security_review": True}))

    def test_partial_checks_are_not_ready(self) -> None:
        self.assertFalse(is_ready({"tests": True, "security_review": False}))


if __name__ == "__main__":
    unittest.main()
