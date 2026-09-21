#!/usr/bin/env python3
"""Work-graph command surface without launching agents or mutating Git."""

from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parent.parent


class WorkGraphSurfaceTests(unittest.TestCase):
    def test_dispatch_command_is_present(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "agentsmith.py"), "graph", "start", "--help"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("start", result.stdout.lower())

    def test_integration_command_is_present(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "agentsmith.py"), "graph", "integrate", "--help"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("integrate", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
