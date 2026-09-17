#!/usr/bin/env python3
"""Cross-platform contract tests for the installed context-budget hook."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "agentsmith.py"


class ContextBudgetNudgeTests(unittest.TestCase):
    @staticmethod
    def isolated_environment(root: Path) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(root / "home"),
                "USERPROFILE": str(root / "home"),
                "CODEX_HOME": str(root / "codex-home"),
                "TMPDIR": str(root / "tmp"),
                "TEMP": str(root / "tmp"),
                "TMP": str(root / "tmp"),
            }
        )
        return env

    def run_hook(
        self,
        root: Path,
        *,
        used: str = "60",
        threshold: str | None = None,
        session_id: str = "session-1",
        stale: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        if re.fullmatch(r"[A-Za-z0-9._-]{1,128}", session_id):
            signal = root / f"claude-ctx-{session_id}.pct"
            signal.write_text(used, encoding="utf-8")
            if stale:
                old = time.time() - 600
                os.utime(signal, (old, old))
        env = os.environ.copy()
        env.update({"TMPDIR": str(root), "TEMP": str(root), "TMP": str(root)})
        env.pop("HANDOFF_PCT_THRESHOLD", None)
        if threshold is not None:
            env["HANDOFF_PCT_THRESHOLD"] = threshold
        return subprocess.run(
            [sys.executable, str(CORE), "hook", "context-budget-nudge"],
            cwd=ROOT,
            env=env,
            input=json.dumps({"hook_event_name": "Stop", "session_id": session_id}),
            text=True,
            capture_output=True,
            check=False,
        )

    def test_no_threshold_means_no_percentage_automation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith context hook ") as raw:
            result = self.run_hook(Path(raw), used="99")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")

    def test_explicit_threshold_controls_a_neutral_once_per_session_cue(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith context hook ") as raw:
            root = Path(raw)
            below = self.run_hook(root, used="59", threshold="60", session_id="below")
            self.assertEqual(below.stdout, "")

            boundary = self.run_hook(root, used="60", threshold="60", session_id="boundary")
            self.assertEqual(boundary.returncode, 0, boundary.stderr)
            payload = json.loads(boundary.stdout)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("60% used", payload["reason"])
            self.assertIn("configured handoff cue", payload["reason"])

            repeat = self.run_hook(root, used="61", threshold="60", session_id="boundary")
            self.assertEqual(repeat.stdout, "")

    def test_bad_or_stale_inputs_fail_open(self) -> None:
        cases = (
            {"threshold": "not-a-number"},
            {"threshold": "0"},
            {"threshold": "101"},
            {"threshold": "60", "used": "not-a-percentage"},
            {"threshold": "60", "used": "61", "stale": True},
            {"threshold": "60", "used": "61", "session_id": "../../unsafe"},
        )
        for index, case in enumerate(cases):
            with self.subTest(case=case), tempfile.TemporaryDirectory(
                prefix=f"agentsmith context hook {index} "
            ) as raw:
                result = self.run_hook(Path(raw), **case)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")

    def test_operator_surfaces_do_not_restore_a_universal_threshold(self) -> None:
        surfaces = (
            ROOT / "hooks" / "context-budget-nudge.sh",
            ROOT / "hooks" / "README.md",
            ROOT / "config" / "statusline-command.sh",
            ROOT / "docs" / "02-your-first-hour.md",
            ROOT / "docs" / "05-operating-modes.md",
            ROOT / "docs" / "17-troubleshooting.md",
            ROOT / "docs" / "19-glossary.md",
        )
        forbidden = (
            "HANDOFF_PCT_THRESHOLD:-30",
            "default **30%",
            "hand off at ~25",
            "around **25",
            "sweet spot is",
            "while the model is still sharp",
        )
        for path in surfaces:
            content = path.read_text(encoding="utf-8")
            for phrase in forbidden:
                with self.subTest(path=path, phrase=phrase):
                    self.assertNotIn(phrase, content)

    def test_installed_runtime_consumes_the_statusline_signal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith installed context hook ") as raw:
            root = Path(raw)
            project = root / "project"
            project.mkdir()
            (root / "tmp").mkdir()
            env = self.isolated_environment(root)
            installed = subprocess.run(
                [
                    sys.executable,
                    str(CORE),
                    "install",
                    "--agent",
                    "claude",
                    "--profile",
                    "general-admin",
                    "--target",
                    str(project),
                    "--with-handoff-hooks",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)

            settings = json.loads((root / "home" / ".claude" / "settings.json").read_text())
            statusline_command = settings["statusLine"]["command"]
            stop_command = settings["hooks"]["Stop"][0]["hooks"][0]["command"]
            rendered = subprocess.run(
                statusline_command,
                cwd=ROOT,
                env=env,
                input=json.dumps(
                    {
                        "cwd": str(project),
                        "session_id": "installed-session",
                        "context_window": {"used_percentage": 60},
                    }
                ),
                text=True,
                capture_output=True,
                shell=True,
                check=False,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertIn("ctx:60%", rendered.stdout)

            env["HANDOFF_PCT_THRESHOLD"] = "60"
            stopped = subprocess.run(
                stop_command,
                cwd=project,
                env=env,
                input=json.dumps({"hook_event_name": "Stop", "session_id": "installed-session"}),
                text=True,
                capture_output=True,
                shell=True,
                check=False,
            )
            self.assertEqual(stopped.returncode, 0, stopped.stderr)
            self.assertEqual(json.loads(stopped.stdout)["decision"], "block")


if __name__ == "__main__":
    unittest.main()
