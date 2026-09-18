import unittest

from readiness import ready


class ReadinessTests(unittest.TestCase):
    def test_every_check_must_pass(self) -> None:
        self.assertFalse(ready({"tests": True, "review": False}))


if __name__ == "__main__":
    unittest.main()
