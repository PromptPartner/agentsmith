#!/usr/bin/env python3
"""Feedback and handoff scaffolds: every copy (CLI, shell script, template) carries the same contract."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "agentsmith.py"
# Windows runners may resolve `bash` to WSL; the shell scaffolds are covered on POSIX.
POSIX_SHELL = os.name != "nt" and shutil.which("bash") is not None
HANDOFF_HEADINGS = (
    "## Verified this session",
    "## Carried over, not re-verified",
    "## Open questions — default if unanswered",
    "## Kickoff prompt for a fresh chat",
)


class ScaffoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agentsmith scaffolds ")
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        (self.project / "scripts").mkdir(parents=True)
        self.env = os.environ.copy()
        home = self.root / "home"
        home.mkdir()
        self.env.update({"HOME": str(home), "USERPROFILE": str(home), "CODEX_HOME": str(home / ".codex")})

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(CORE), *arguments, "--target", str(self.project)],
                              cwd=self.project, env=self.env, text=True, capture_output=True, check=False)

    def shell(self, script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        # The shell scaffolds write next to their own folder, so run a copy inside the fixture project.
        copy = self.project / "scripts" / script
        shutil.copy2(ROOT / "scripts" / script, copy)
        return subprocess.run(["bash", str(copy), *arguments], cwd=self.project, env=self.env,
                              text=True, capture_output=True, check=False)

    def record_hooks(self, enabled: bool) -> None:
        state = self.project / ".agentsmith" / "state.json"
        state.parent.mkdir(exist_ok=True)
        state.write_text(json.dumps({"schema_version": 1, "installation": {"capabilities": {"hooks": enabled}}},
                                    indent=2), encoding="utf-8")

    def only_file(self, folder: str) -> str:
        [path] = sorted(path for path in (self.project / folder).glob("*.md") if path.name != "README.md")
        text = path.read_text(encoding="utf-8")
        path.unlink()
        return text

    def test_handoff_template_cli_and_script_separate_verified_from_carried_over(self) -> None:
        texts = {"template": (ROOT / "templates" / "handoff-memory.md").read_text(encoding="utf-8")}
        self.assertEqual(self.cli("handoff", "ITEM-1").returncode, 0)
        texts["cli"] = self.only_file(".harness/handoffs")
        if POSIX_SHELL:
            self.assertEqual(self.shell("handoff.sh", "ITEM-1").returncode, 0)
            texts["script"] = self.only_file(".harness/handoffs")
        for source, text in texts.items():
            for heading in HANDOFF_HEADINGS:
                self.assertIn(heading, text, source)
            self.assertIn("```", text.split("## Kickoff prompt for a fresh chat", 1)[1], source)

    def test_handoff_skill_scans_the_note_for_secrets_before_saving(self) -> None:
        skill = (ROOT / "skills" / "handoff" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("agentsmith secret-scan", skill)
        for heading in ("Verified this session", "Carried over, not re-verified", "Open questions"):
            self.assertIn(heading, skill)

    def feedback_texts(self) -> dict[str, str]:
        texts = {}
        self.assertEqual(self.cli("new-feedback", "lost a lesson").returncode, 0)
        texts["cli"] = self.only_file("docs/feedback")
        if POSIX_SHELL:
            self.assertEqual(self.shell("new-feedback.sh", "lost a lesson").returncode, 0)
            texts["script"] = self.only_file("docs/feedback")
        return texts

    def test_feedback_record_has_a_machine_readable_surface_line(self) -> None:
        for source, text in self.feedback_texts().items():
            self.assertRegex(text, r"(?m)^- \*\*Surface:\*\* ", source)
            self.assertIn("verify:", text, source)
            self.assertIn("file:", text, source)

    def test_feedback_advice_follows_the_recorded_hooks_capability(self) -> None:
        self.record_hooks(False)
        for source, text in self.feedback_texts().items():
            self.assertIn("does not run hooks", text, source)
            self.assertIn("verify phase or a lint check", text, source)
        self.record_hooks(True)
        for source, text in self.feedback_texts().items():
            self.assertIn("This install runs hooks", text, source)

    def test_first_feedback_record_creates_the_review_line_doctor_reads(self) -> None:
        self.assertEqual(self.cli("new-feedback", "first lesson").returncode, 0)
        readme = self.project / "docs" / "feedback" / "README.md"
        self.assertRegex(readme.read_text(encoding="utf-8"), r"(?m)^_Last harness review: ")
        readme.write_text("# Own guide\n_Last harness review: 2026-01-01_\n", encoding="utf-8")
        self.assertEqual(self.cli("new-feedback", "second lesson").returncode, 0)
        self.assertEqual(readme.read_text(encoding="utf-8"), "# Own guide\n_Last harness review: 2026-01-01_\n")

    def test_feedback_guide_names_the_current_doctor_command(self) -> None:
        guide = (ROOT / "docs" / "feedback" / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("setup.sh --doctor", guide)
        self.assertIn("agentsmith doctor", guide)
        self.assertIn("**Surface:**", guide)


if __name__ == "__main__":
    unittest.main(verbosity=2)
