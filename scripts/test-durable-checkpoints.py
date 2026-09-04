#!/usr/bin/env python3
"""Regression checks for durable recovery and dynamic investigation guidance."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "agentsmith.py"
RECOVERY_FIELDS = (
    "Exact objective",
    "Repository / worktree",
    "Protected-state hashes",
    "Branch / commit",
    "External identifiers",
    "Completed verification",
    "Active external operation",
    "Next read-only recovery command",
    "Remaining authorized writes",
    "Stop conditions",
    "Skipped validation",
)


class DurableCheckpointTests(unittest.TestCase):
    def test_handoff_scaffold_serializes_recovery_checkpoint_fields(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith durable checkpoint ") as temporary:
            target = Path(temporary) / "project"
            target.mkdir()
            subprocess.run(["git", "-C", str(target), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(target), "config", "user.name", "Checkpoint Test"], check=True)
            subprocess.run(["git", "-C", str(target), "config", "user.email", "test@example.com"], check=True)
            (target / "tracked.txt").write_text("tracked\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(target), "add", "."], check=True)
            subprocess.run(["git", "-C", str(target), "commit", "-qm", "test: fixture"], check=True)
            result = subprocess.run(
                [sys.executable, str(CORE), "handoff", "MIGRATION-1", "--target", str(target)],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            handoffs = list((target / ".harness" / "handoffs").glob("handoff-*.md"))
            self.assertEqual(len(handoffs), 1)
            text = handoffs[0].read_text(encoding="utf-8")
            self.assertIn(str(target.resolve()), text)
            for field in RECOVERY_FIELDS:
                self.assertIn(field, text)

    def test_search_absence_gate_is_dynamic_and_generated_adapters_remain_outputs(self) -> None:
        skill = (ROOT / "skills" / "new-feedback" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("untruncated", skill)
        self.assertIn("count-based", skill)
        self.assertNotIn("search returned no visible match", (ROOT / "core" / "40-subagents-and-tools.md").read_text(encoding="utf-8").casefold())

        with tempfile.TemporaryDirectory(prefix="agentsmith generated checkpoint ") as temporary:
            target = Path(temporary) / "project"
            target.mkdir()
            environment = os.environ.copy()
            environment.update({
                "HOME": str(Path(temporary) / "home"),
                "USERPROFILE": str(Path(temporary) / "home"),
                "CODEX_HOME": str(Path(temporary) / "codex"),
            })
            result = subprocess.run(
                [
                    sys.executable, str(CORE), "install", "--agent", "native", "--profile", "software-dev",
                    "--assemble-only", "--with-skills", "--target", str(target),
                ],
                cwd=ROOT, env=environment, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((target / "AGENTS.md").read_bytes(), (target / "CLAUDE.md").read_bytes())
            self.assertEqual(
                (target / ".agents" / "skills" / "new-feedback" / "SKILL.md").read_bytes(),
                (target / ".claude" / "skills" / "new-feedback" / "SKILL.md").read_bytes(),
            )
            self.assertTrue((target / ".harness" / "templates" / "integration-checkpoint.md").is_file())
            instructions = (target / "AGENTS.md").read_text(encoding="utf-8")
            self.assertNotIn("MCP/integration validation checkpoint", instructions)
            self.assertFalse((target / ".git" / "hooks").exists())

    def test_narrow_project_authority_has_a_bounded_pattern_not_a_universal_grant(self) -> None:
        safety = (ROOT / "docs" / "15-safety-model.md").read_text(encoding="utf-8")
        core = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "core").glob("*.md"))
        for guard in (
            "exact system and permitted actions",
            "read-only diagnosis first",
            "missing credentials",
            "surprising external state",
            "destructive recovery",
            "production or customer data",
            "scope expansion",
            "another runner",
        ):
            self.assertIn(guard, safety)
        self.assertIn("explicit operator instruction", safety)
        self.assertNotIn("project-ci-1", core)

    def test_existing_devops_gate_checks_external_function_not_process_existence(self) -> None:
        profile = (ROOT / "profiles" / "devops-setup.md").read_text(encoding="utf-8")
        self.assertIn("reachable from outside the box", profile)
        self.assertIn('not when `docker ps` shows "running"', profile)
        self.assertIn("curl the real URL", profile)


if __name__ == "__main__":
    unittest.main(verbosity=2)
