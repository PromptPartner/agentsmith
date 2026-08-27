#!/usr/bin/env python3
"""End-to-end consent migration checks against the canonical Python runtime."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "agentsmith.py"


class TrackerConsentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agentsmith consent ")
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.env = os.environ.copy()
        self.env.update(
            {
                "HOME": str(self.root / "home"),
                "USERPROFILE": str(self.root / "home"),
                "CODEX_HOME": str(self.root / "codex home"),
            }
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def install(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CORE), "install", "--agent", "codex", "--profile", "software-dev",
             "--assemble-only", "--target", str(self.project), *arguments],
            cwd=ROOT,
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def managed_text(self) -> str:
        text = (self.project / "AGENTS.md").read_text(encoding="utf-8")
        begin = text.index("<!-- BEGIN AGENTSMITH")
        end = text.index("<!-- END AGENTSMITH -->", begin)
        return text[begin:end]

    def test_tracker_name_defaults_to_ask_first(self) -> None:
        result = self.install("--tracker", "Linear")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        managed = self.managed_text()
        self.assertIn("The team's record is **Linear**", managed)
        self.assertIn("writes are NOT authorized", managed)
        self.assertNotIn("writes are authorized", managed)

    def test_explicit_opt_in_is_rendered_and_survives_idempotent_rerun(self) -> None:
        first = self.install("--tracker", "Linear", "--tracker-writes", "allowed")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        before = sorted(
            (path.relative_to(self.project), path.read_bytes())
            for path in self.project.rglob("*") if path.is_file()
        )
        second = self.install()
        after = sorted(
            (path.relative_to(self.project), path.read_bytes())
            for path in self.project.rglob("*") if path.is_file()
        )
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("writes are authorized", self.managed_text())
        self.assertEqual(before, after)

    def test_malformed_policy_is_rejected_before_writes(self) -> None:
        result = self.install("--tracker", "Linear", "--tracker-writes", "yes-please")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(self.project.iterdir()))

    def test_pre_consent_wording_recovers_tracker_but_fails_closed(self) -> None:
        legacy = """# Foreign project guidance

**Test Operator** is the lead. Role: **Founder**.

They decide direction and accept the risk.

**7. Track every defect.** File it in **Linear** — every bug or gap you find, even one you
fix immediately. Make agent work visible there.
"""
        (self.project / "AGENTS.md").write_text(legacy, encoding="utf-8")
        first = self.install()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        managed = self.managed_text()
        self.assertIn("The team's record is **Linear**", managed)
        self.assertIn("writes are NOT authorized", managed)
        self.assertNotIn("writes are authorized", managed)
        self.assertTrue((self.project / "AGENTS.md").read_text(encoding="utf-8").startswith(legacy.rstrip()))
        before = (self.project / "AGENTS.md").read_bytes()
        second = self.install()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(before, (self.project / "AGENTS.md").read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
