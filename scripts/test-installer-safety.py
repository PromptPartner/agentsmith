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


class InstallerFixture(unittest.TestCase):
    """An isolated HOME and CODEX_HOME so no fixture can reach the operator's real settings."""

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


class OwnershipTests(InstallerFixture):
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

    # A project install must never change the user's settings for every other project.
    def test_project_install_writes_claude_mode_to_project_settings_only(self) -> None:
        original = self.write_settings({"theme": "dark"})
        project = self.root / "project"
        project.mkdir()
        self.assert_ok(self.run_core(
            "install", "--agent", "claude", "--profile", "general-admin", "--target", str(project),
        ))
        home_data = json.loads(self.claude_settings.read_text(encoding="utf-8"))
        self.assertNotIn("permissions", home_data, "project install changed the user-global default mode")
        project_settings = project / ".claude" / "settings.json"
        project_data = json.loads(project_settings.read_text(encoding="utf-8"))
        self.assertEqual(project_data["permissions"]["defaultMode"], "acceptEdits")
        doctor = self.run_core("doctor", "--agent", "claude", "--target", str(project), "--json")
        self.assert_ok(doctor)
        safety = json.loads(doctor.stdout)["claude"]["safety"]
        self.assertEqual((safety["state"], Path(safety["path"])), ("cautious", project_settings))
        self.assert_ok(self.run_core("install", "--agent", "claude", "--uninstall", "--target", str(project)))
        self.assertFalse(project_settings.exists(), "uninstall kept the project settings file it created")
        self.assertNotIn("permissions", json.loads(self.claude_settings.read_text(encoding="utf-8")))
        self.assertEqual(json.loads(self.claude_settings.read_bytes()), json.loads(original))

    def test_project_trusted_claude_is_refused_before_any_write(self) -> None:
        project = self.root / "project"
        project.mkdir()
        result = self.run_core(
            "install", "--agent", "claude", "--profile", "general-admin", "--safety", "trusted",
            "--target", str(project),
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("bypassPermissions", result.stdout + result.stderr)
        self.assertEqual(list(project.iterdir()), [])
        self.assertFalse(self.claude_settings.exists())


class ContainmentTests(InstallerFixture):
    """#50b: one preflight refuses an escaping link before the first write; no write goes through a link."""

    def link(self, link: Path, destination: Path, *, directory: bool) -> None:
        link.parent.mkdir(parents=True, exist_ok=True)
        try:
            link.symlink_to(destination, target_is_directory=directory)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symbolic links unavailable: {exc}")

    def snapshot(self, root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*")) if path.is_file() and not path.is_symlink()
        }

    def assert_refused_before_writes(self, result, project: Path, outside: Path, before: dict) -> None:
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("symbolic link", result.stdout + result.stderr)
        self.assertFalse((project / "AGENTS.md").exists(), "instructions were written before the refusal")
        self.assertFalse((project / "CLAUDE.md").exists(), "instructions were written before the refusal")
        self.assertEqual(self.snapshot(outside), before, "a write reached the link's destination")
        self.assertFalse((self.home / ".agentsmith").exists(), "user-level state was written before the refusal")

    def test_project_links_out_of_the_target_are_refused_before_any_write(self) -> None:
        cases = {
            ".harness": ("--agent", "claude", "--profile", "general-admin"),
            ".agentsmith": ("--agent", "claude", "--profile", "general-admin"),
            ".claude": ("--agent", "claude", "--profile", "general-admin"),
            ".gemini": ("--agent", "gemini-cli", "--profile", "general-admin"),
            ".continue": ("--agent", "continue", "--profile", "general-admin"),
            "docs": ("--agent", "codex", "--profile", "general-admin"),
            ".codex": ("--agent", "codex", "--profile", "general-admin", "--with-mcp", "context7"),
        }
        for name, arguments in cases.items():
            with self.subTest(link=name):
                project = self.root / f"project {name}"
                outside = self.root / f"outside {name}"
                outside.mkdir()
                (outside / "sentinel.txt").write_text("keep\n", encoding="utf-8")
                self.link(project / name, outside, directory=True)
                before = self.snapshot(outside)
                result = self.run_core("install", "--target", str(project), *arguments)
                self.assert_refused_before_writes(result, project, outside, before)

    def test_runtime_file_link_out_of_the_target_is_refused(self) -> None:
        # KNOWN-ISSUES 2026-10-05: copy_runtime() copied through per-file links.
        project = self.root / "project"
        outside = self.root / "outside"
        outside.mkdir()
        victim = outside / "victim.py"
        victim.write_text("keep\n", encoding="utf-8")
        self.link(project / ".agentsmith" / "evaluate.py", victim, directory=False)
        before = self.snapshot(outside)
        result = self.run_core("install", "--target", str(project), "--agent", "codex", "--profile", "general-admin")
        self.assert_refused_before_writes(result, project, outside, before)

    def test_dangling_link_out_of_the_target_is_refused(self) -> None:
        project = self.root / "project"
        outside = self.root / "outside"
        outside.mkdir()
        self.link(project / "CLAUDE.md", outside / "not-yet-created.md", directory=False)
        result = self.run_core("install", "--target", str(project), "--agent", "claude", "--profile", "general-admin")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((project / "AGENTS.md").exists())

    def test_contained_links_are_replaced_not_written_through(self) -> None:
        project = self.root / "project"
        project.mkdir()
        notes = project / "notes.md"
        notes.write_text("my notes\n", encoding="utf-8")
        self.link(project / "CLAUDE.md", Path("notes.md"), directory=False)
        self.link(project / ".agentsmith" / "evaluate.py", Path("..") / "notes.md", directory=False)
        result = self.run_core("install", "--target", str(project), "--agent", "claude", "--profile", "general-admin")
        self.assert_ok(result)
        self.assertEqual(notes.read_text(encoding="utf-8"), "my notes\n")
        for path in (project / "CLAUDE.md", project / ".agentsmith" / "evaluate.py"):
            self.assertFalse(path.is_symlink(), path)
            self.assertTrue(path.is_file(), path)

    def test_global_link_out_of_home_is_refused_before_any_write(self) -> None:
        outside = self.root / "shared claude"
        outside.mkdir()
        self.link(self.home / ".claude", outside, directory=True)
        result = self.run_core("install", "--global", "--agent", "claude")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("symbolic link", result.stdout + result.stderr)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.home / ".agentsmith").exists())

    def test_global_link_out_of_codex_home_is_refused_before_any_write(self) -> None:
        self.codex_home.mkdir()
        outside = self.root / "outside rules.md"
        outside.write_text("keep\n", encoding="utf-8")
        self.link(self.codex_home / "AGENTS.md", outside, directory=False)
        result = self.run_core("install", "--global", "--agent", "claude,codex")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(outside.read_text(encoding="utf-8"), "keep\n")
        self.assertFalse((self.home / ".claude" / "CLAUDE.md").exists(), "Claude's rules were written first")

    def test_global_link_inside_home_is_allowed(self) -> None:
        dotfiles = self.home / "dotfiles" / "claude"
        dotfiles.mkdir(parents=True)
        self.link(self.home / ".claude", dotfiles, directory=True)
        self.assert_ok(self.run_core("install", "--global", "--agent", "claude", "--assemble-only"))
        self.assertTrue((dotfiles / "CLAUDE.md").is_file())


class RulebookTests(InstallerFixture):
    """A project carries one managed rulebook: AGENTS.md. Claude's CLAUDE.md imports it."""

    CORE_HEADING = "## The Principle Rules"

    def install_project(self, project: Path, *arguments: str) -> None:
        project.mkdir(exist_ok=True)
        self.assert_ok(self.run_core(
            "install", "--agent", "claude,codex", "--profile", "general-admin", "--assemble-only",
            "--target", str(project), *arguments,
        ))

    def test_claude_copy_imports_agents_md_instead_of_a_second_rulebook(self) -> None:
        project = self.root / "project"
        self.install_project(project)
        agents = (project / "AGENTS.md").read_text(encoding="utf-8")
        claude = (project / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn(self.CORE_HEADING, agents)
        self.assertNotIn(self.CORE_HEADING, claude)
        self.assertIn("@AGENTS.md", claude.splitlines())
        self.assertIn("Generated. Profiles: general-admin. core=true.", claude)

    def test_existing_unmarked_claude_md_keeps_its_text_and_gains_only_the_import(self) -> None:
        project = self.root / "project"
        project.mkdir()
        own = "# Team notes\n\nRun make test before every commit.\n"
        (project / "CLAUDE.md").write_text(own, encoding="utf-8")
        self.install_project(project)
        claude = (project / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertTrue(claude.startswith(own))
        self.assertNotIn(self.CORE_HEADING, claude)
        self.assertIn("@AGENTS.md", claude.splitlines())
        combined = claude + (project / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(combined.count(self.CORE_HEADING), 1, "two managed rulebooks in one project")

    def test_rerun_doctor_and_profile_switch_keep_the_import(self) -> None:
        project = self.root / "project"
        self.install_project(project)
        before = {name: (project / name).read_bytes() for name in ("AGENTS.md", "CLAUDE.md")}
        self.install_project(project)
        self.assertEqual({name: (project / name).read_bytes() for name in before}, before, "rerun is not idempotent")
        doctor = self.run_core("doctor", "--agent", "claude", "--target", str(project), "--json")
        self.assert_ok(doctor)
        codes = {warning["code"] for warning in json.loads(doctor.stdout)["claude"]["warnings"]}
        self.assertNotIn("conflicting-generator-metadata", codes)
        self.assert_ok(self.run_core("profiles", "switch", "--target", str(project), "--profile", "software-dev"))
        claude = (project / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("Generated. Profiles: software-dev. core=true.", claude)
        self.assertNotIn(self.CORE_HEADING, claude)
        self.assertIn("@AGENTS.md", claude.splitlines())

    def test_global_claude_rules_stay_complete(self) -> None:
        self.assert_ok(self.run_core("install", "--global", "--agent", "claude", "--assemble-only"))
        self.assertIn(self.CORE_HEADING, (self.home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
