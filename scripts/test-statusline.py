#!/usr/bin/env python3
"""Cross-platform contract tests for the default native status line."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "agentsmith.py"


class StatusLineTests(unittest.TestCase):
    @staticmethod
    def environment(root: Path) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(root / "home"),
                "USERPROFILE": str(root / "home"),
                "CODEX_HOME": str(root / "codex home"),
            }
        )
        return env

    def install(
        self, root: Path, *extra: str, project_name: str = "project"
    ) -> subprocess.CompletedProcess[str]:
        project = root / project_name
        project.mkdir(parents=True, exist_ok=True)
        return subprocess.run(
            [
                sys.executable,
                str(CORE),
                "install",
                "--agent",
                "native",
                "--profile",
                "general-admin",
                "--target",
                str(project),
                *extra,
            ],
            cwd=ROOT,
            env=self.environment(root),
            text=True,
            capture_output=True,
            check=False,
        )

    def doctor(self, root: Path, agent: str) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                str(CORE),
                "doctor",
                "--agent",
                agent,
                "--target",
                str(root / "project"),
                "--json",
            ],
            cwd=ROOT,
            env=self.environment(root),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_fresh_install_activates_claude_default_and_keeps_codex_native_default(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith statusline ") as raw:
            root = Path(raw)
            first = self.install(root)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)

            settings_path = root / "home" / ".claude" / "settings.json"
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            configured = settings.get("statusLine", {})
            helper = root / "home" / ".claude" / "agentsmith-statusline.py"
            self.assertEqual(configured.get("type"), "command")
            self.assertIn("agentsmith-statusline", configured.get("command", ""))
            self.assertTrue(helper.is_file())

            temp_dir = root / "status cache"
            temp_dir.mkdir()
            victim = root / "must-not-be-overwritten"
            signal_path = temp_dir / "claude-ctx-session-test_1.pct"
            if os.name != "nt":
                victim.write_text("foreign", encoding="utf-8")
                signal_path.symlink_to(victim)
            payload = {
                "workspace": {"current_dir": str(root / "project")},
                "model": {"display_name": "Test\nModel"},
                "context_window": {"used_percentage": 27.6},
                "session_id": "session-test_1",
            }
            render_env = os.environ.copy()
            render_env.update({"TMPDIR": str(temp_dir), "TEMP": str(temp_dir), "TMP": str(temp_dir)})
            rendered = subprocess.run(
                configured["command"],
                input=json.dumps(payload),
                env=render_env,
                text=True,
                capture_output=True,
                check=False,
                shell=True,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertIn("Test?Model", rendered.stdout)
            self.assertIn("ctx:28%", rendered.stdout)
            self.assertEqual(signal_path.read_text(), "27.6")
            if os.name != "nt":
                self.assertEqual(victim.read_text(encoding="utf-8"), "foreign")
                self.assertFalse(signal_path.is_symlink())
            self.assertEqual(len(rendered.stdout.splitlines()), 1)

            codex_path = root / "codex home" / "config.toml"
            codex = tomllib.loads(codex_path.read_text(encoding="utf-8"))
            self.assertNotIn("status_line", codex.get("tui", {}))

            before = {
                settings_path: settings_path.read_bytes(),
                helper: helper.read_bytes(),
                codex_path: codex_path.read_bytes(),
            }
            if os.name == "nt":
                wrapper = helper.with_suffix(".ps1")
                before[wrapper] = wrapper.read_bytes()
            second = self.install(root)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(before, {path: path.read_bytes() for path in before})

            removed = self.install(root, "--uninstall")
            self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
            remaining = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
            self.assertNotIn("statusLine", remaining)
            self.assertFalse(helper.exists())
            if os.name == "nt":
                self.assertFalse(wrapper.exists())

    def test_explicit_claude_and_codex_statusline_choices_are_preserved(self) -> None:
        for explicit in (
            {"type": "command", "command": "custom-status"},
            None,
            {},
        ):
            with self.subTest(explicit=explicit), tempfile.TemporaryDirectory(prefix="agentsmith custom statusline ") as raw:
                root = Path(raw)
                settings_path = root / "home" / ".claude" / "settings.json"
                settings_path.parent.mkdir(parents=True)
                settings_path.write_text(json.dumps({"statusLine": explicit, "foreign": 7}) + "\n", encoding="utf-8")
                codex_path = root / "codex home" / "config.toml"
                codex_path.parent.mkdir(parents=True)
                codex_path.write_text('[tui]\nstatus_line = []\nstatus_line_use_colors = false\n', encoding="utf-8")

                installed = self.install(root)
                self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
                codex = tomllib.loads(codex_path.read_text(encoding="utf-8"))
                self.assertIn("statusLine", settings)
                self.assertEqual(settings["statusLine"], explicit)
                self.assertEqual(settings["foreign"], 7)
                self.assertEqual(codex["tui"]["status_line"], [])
                self.assertFalse(codex["tui"]["status_line_use_colors"])
                self.assertFalse((root / "home" / ".claude" / "agentsmith-statusline.py").exists())

    def test_changed_managed_statusline_survives_uninstall(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith changed statusline ") as raw:
            root = Path(raw)
            installed = self.install(root)
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            settings_path = root / "home" / ".claude" / "settings.json"
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            settings["statusLine"] = {"type": "command", "command": "my-replacement"}
            settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
            helper = root / "home" / ".claude" / "agentsmith-statusline.py"
            helper.write_text(helper.read_text(encoding="utf-8") + "# local customization\n", encoding="utf-8")

            removed = self.install(root, "--uninstall")
            self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
            remaining = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(remaining["statusLine"]["command"], "my-replacement")
            self.assertTrue(helper.is_file())
            self.assertIn("local customization", helper.read_text(encoding="utf-8"))

    def test_foreign_helper_collision_is_preserved_and_owned_path_is_distinct(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith colliding statusline ") as raw:
            root = Path(raw)
            foreign = root / "home" / ".claude" / "agentsmith-statusline.py"
            foreign.parent.mkdir(parents=True)
            foreign.write_text("# foreign helper\n", encoding="utf-8")

            installed = self.install(root)
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            settings = json.loads((foreign.parent / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(foreign.read_text(encoding="utf-8"), "# foreign helper\n")
            managed = foreign.with_name("agentsmith-statusline-1.py")
            self.assertTrue(managed.is_file())
            state = json.loads((root / "home" / ".agentsmith" / "state.json").read_text(encoding="utf-8"))
            owned_files = state["native_statuslines"]["claude"]["files"]
            self.assertIn(str(managed), owned_files)
            if os.name == "nt":
                wrapper = foreign.with_name("agentsmith-statusline.ps1")
                self.assertIn(str(wrapper), owned_files)
                self.assertIn(wrapper.as_posix(), settings["statusLine"]["command"])
            else:
                self.assertIn(managed.as_posix(), settings["statusLine"]["command"])

            removed = self.install(root, "--uninstall")
            self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
            self.assertTrue(foreign.is_file())
            self.assertFalse(managed.exists())
            if os.name == "nt":
                self.assertFalse(wrapper.exists())

    def test_dry_run_is_write_free_and_uninstall_keeps_other_project_owner(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith shared statusline ") as raw:
            root = Path(raw)
            dry = self.install(root, "--dry-run")
            self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
            self.assertFalse((root / "home").exists())
            self.assertFalse((root / "codex home").exists())
            self.assertEqual(list((root / "project").iterdir()), [])

            first = self.install(root)
            second = self.install(root, project_name="project two")
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            settings_path = root / "home" / ".claude" / "settings.json"
            helper = root / "home" / ".claude" / "agentsmith-statusline.py"
            before = {
                path.relative_to(root): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            preview = self.install(root, "--uninstall", "--dry-run")
            after_preview = {
                path.relative_to(root): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
            self.assertEqual(before, after_preview)

            removed_first = self.install(root, "--uninstall")
            self.assertEqual(removed_first.returncode, 0, removed_first.stdout + removed_first.stderr)
            self.assertTrue(settings_path.is_file())
            self.assertTrue(helper.is_file())
            removed_second = self.install(root, "--uninstall", project_name="project two")
            self.assertEqual(removed_second.returncode, 0, removed_second.stdout + removed_second.stderr)
            remaining = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
            self.assertNotIn("statusLine", remaining)
            self.assertFalse(helper.exists())

    def test_doctor_detects_missing_helper_and_malformed_codex_statusline(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith statusline doctor ") as raw:
            root = Path(raw)
            installed = self.install(root)
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            helper = root / "home" / ".claude" / "agentsmith-statusline.py"
            helper.unlink()
            claude = self.doctor(root, "claude")["claude"]["statusline"]
            self.assertEqual(claude["state"], "stale")
            self.assertFalse(claude["active"])

            codex_path = root / "codex home" / "config.toml"
            codex_path.write_text('tui = "not-a-table"\n', encoding="utf-8")
            codex = self.doctor(root, "codex")["codex"]["statusline"]
            self.assertEqual(codex["state"], "malformed")
            self.assertFalse(codex["active"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
