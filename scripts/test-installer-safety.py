#!/usr/bin/env python3
"""Behavioral tests: install and uninstall touch only what AgentSmith owns, inside its roots."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "agentsmith.py"


class InstallerSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agentsmith installer ü ")
        self.root = Path(self.temporary.name).resolve()
        self.home = self.root / "home with spaces"
        self.codex_home = self.root / "codex home"
        self.home.mkdir()
        self.env = os.environ.copy()
        self.env.update({
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "CODEX_HOME": str(self.codex_home),
            "PYTHONIOENCODING": "utf-8",
        })
        # The operator's own client settings must not redirect fixture writes.
        for name in ("PI_CODING_AGENT_DIR", "XDG_CONFIG_HOME"):
            self.env.pop(name, None)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_core(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CORE), *arguments], cwd=self.root, env=self.env,
            text=True, encoding="utf-8", errors="replace", capture_output=True, check=False,
        )

    def assert_ok(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @property
    def claude_settings(self) -> Path:
        return self.home / ".claude" / "settings.json"

    def write_settings(self, data: dict) -> bytes:
        self.claude_settings.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data).encode("utf-8")
        self.claude_settings.write_bytes(payload)
        return payload

    def default_mode(self) -> object:
        data = json.loads(self.claude_settings.read_text(encoding="utf-8"))
        return data.get("permissions", {}).get("defaultMode", "<absent>")

    # #50a: uninstall must remove only what the install record says AgentSmith wrote.
    def test_global_uninstall_after_assemble_only_keeps_user_settings_byte_identical(self) -> None:
        original = self.write_settings({"permissions": {"defaultMode": "acceptEdits"}})
        self.assert_ok(self.run_core("install", "--global", "--assemble-only", "--agent", "claude"))
        self.assert_ok(self.run_core("install", "--global", "--uninstall", "--agent", "claude"))
        self.assertTrue(self.claude_settings.is_file(), "a user-owned settings file was deleted")
        self.assertEqual(self.claude_settings.read_bytes(), original)

    def test_global_uninstall_removes_the_mode_agentsmith_wrote(self) -> None:
        self.write_settings({"theme": "dark"})
        self.assert_ok(self.run_core("install", "--global", "--agent", "claude", "--profile", "general-admin"))
        self.assertEqual(self.default_mode(), "acceptEdits")
        self.assert_ok(self.run_core("install", "--global", "--uninstall", "--agent", "claude"))
        data = json.loads(self.claude_settings.read_text(encoding="utf-8"))
        self.assertEqual(data, {"theme": "dark"})

    def test_global_uninstall_restores_the_users_earlier_mode(self) -> None:
        self.write_settings({"permissions": {"defaultMode": "plan"}})
        self.assert_ok(self.run_core("install", "--global", "--agent", "claude", "--profile", "general-admin"))
        self.assertEqual(self.default_mode(), "acceptEdits")
        self.assert_ok(self.run_core("install", "--global", "--uninstall", "--agent", "claude"))
        self.assertEqual(self.default_mode(), "plan")

    def test_global_uninstall_preserves_a_mode_the_user_changed_after_install(self) -> None:
        self.assert_ok(self.run_core("install", "--global", "--agent", "claude", "--profile", "general-admin"))
        data = json.loads(self.claude_settings.read_text(encoding="utf-8"))
        data["permissions"]["defaultMode"] = "bypassPermissions"
        self.claude_settings.write_text(json.dumps(data), encoding="utf-8")
        result = self.run_core("install", "--global", "--uninstall", "--agent", "claude")
        self.assert_ok(result)
        self.assertEqual(self.default_mode(), "bypassPermissions")
        self.assertIn("changed since install", result.stderr)


if __name__ == "__main__":
    unittest.main()
