#!/usr/bin/env python3
"""Behavioral tests for the canonical cross-platform secret scanner."""

from __future__ import annotations

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
SHELL_LAUNCHER = ROOT / "scripts" / "secret-scan.sh"


def secret_shapes() -> list[tuple[str, str]]:
    """Assemble inert shape fixtures only at runtime; never track a secret-shaped literal."""
    return [
        ("PEM private key", "-----BEGIN RSA PRIV" + "ATE KEY-----"),
        ("AWS access key id", "AKIA" + "ABCDEFGHIJKLMNOP"),
        ("AWS temporary access key id", "ASIA" + "ABCDEFGHIJKLMNOP"),
        ("GitHub token", "ghp_" + "abcdefghijklmnopqrstuvwxyz1234"),
        ("Slack token", "xoxb" + "-1234567890abcdef"),
        ("OpenAI-style key", "sk-" + "abcdefghijklmnopqrstuvwxyz12"),
        ("Anthropic-style key", "sk-ant-" + "abcdefghijklmnopqrstuvwxyz12"),
        ("Google API key", "AIza" + "01234567890123456789012345678901234"),
        ("assigned secret literal", "pass" + 'word = "correcthorsebattery"'),
    ]


def run_scan(*arguments: str, cwd: Path = ROOT, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CORE), "secret-scan", *arguments],
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )


def git(repo: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True)


class SecretScanTests(unittest.TestCase):
    def test_all_nine_shapes_are_named_and_redacted_on_stdin(self) -> None:
        for pattern_name, value in secret_shapes():
            with self.subTest(pattern=pattern_name):
                result = run_scan("-", input_text=value + "\n")
                combined = result.stdout + result.stderr
                self.assertEqual(result.returncode, 1, combined)
                self.assertIn("<stdin>:1", combined)
                self.assertIn(pattern_name, combined)
                self.assertIn("[REDACTED]", combined)
                self.assertNotIn(value, combined)

    def test_clean_prose_environment_reference_and_short_value_pass(self) -> None:
        clean = "\n".join(
            [
                "This document explains how we rotate the password safely.",
                "export API_KEY=${API_KEY:?set me}",
                'token = "abc"',
                "",
            ]
        )
        result = run_scan("-", input_text=clean)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("clean", result.stdout.casefold())

    def test_file_mode_reports_each_path_and_line_without_values(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith scanner files ") as temporary:
            root = Path(temporary)
            first = root / "one file.txt"
            second = root / "ünicode.txt"
            first_value = secret_shapes()[1][1]
            second_value = secret_shapes()[4][1]
            first.write_text("clean\n" + first_value + "\n", encoding="utf-8")
            second.write_text(second_value + "\n", encoding="utf-8")
            result = run_scan(str(first), str(second), cwd=root)
            combined = result.stdout + result.stderr
            self.assertEqual(result.returncode, 1, combined)
            self.assertIn(f"{first}:2", combined)
            self.assertIn(f"{second}:1", combined)
            self.assertNotIn(first_value, combined)
            self.assertNotIn(second_value, combined)

    def test_allow_rules_suppress_only_matching_lines(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith scanner allow ") as temporary:
            repo = Path(temporary)
            git(repo, "init", "-q")
            allowed_value = secret_shapes()[1][1]
            blocked_value = secret_shapes()[2][1]
            fixture = repo / "fixture.txt"
            fixture.write_text(allowed_value + "\n" + blocked_value + "\n", encoding="utf-8")
            allow = repo / ".harness" / "secret-scan.allow"
            allow.parent.mkdir()
            allow.write_text("^" + re.escape(allowed_value) + "$\n", encoding="utf-8")
            result = run_scan(str(fixture), cwd=repo)
            combined = result.stdout + result.stderr
            self.assertEqual(result.returncode, 1, combined)
            self.assertNotIn("AWS access key id", combined)
            self.assertIn("AWS temporary access key id", combined)

    def test_default_scans_only_staged_added_lines_with_unicode_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith scanner staged ") as temporary:
            repo = Path(temporary)
            git(repo, "init", "-q")
            git(repo, "config", "user.name", "Scanner Test")
            git(repo, "config", "user.email", "user@example.com")
            baseline = repo / "baseline.txt"
            baseline.write_text("clean\n", encoding="utf-8")
            git(repo, "add", "baseline.txt")
            git(repo, "commit", "-qm", "baseline")

            value = secret_shapes()[3][1]
            staged = repo / "späce name.txt"
            staged.write_text("clean\n" + value + "\n", encoding="utf-8")
            git(repo, "add", staged.name)
            result = run_scan(cwd=repo)
            combined = result.stdout + result.stderr
            self.assertEqual(result.returncode, 1, combined)
            self.assertIn(f"{staged.name}:2", combined)
            self.assertNotIn(value, combined)

    def test_staged_deletion_is_clean(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith scanner deletion ") as temporary:
            repo = Path(temporary)
            git(repo, "init", "-q")
            git(repo, "config", "user.name", "Scanner Test")
            git(repo, "config", "user.email", "user@example.com")
            fixture = repo / "removed.txt"
            fixture.write_text(secret_shapes()[5][1] + "\n", encoding="utf-8")
            git(repo, "add", fixture.name)
            git(repo, "commit", "-qm", "runtime fixture")
            fixture.unlink()
            git(repo, "add", "-u")
            result = run_scan(cwd=repo)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_all_scans_tracked_worktree_not_only_staged_content(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith scanner all ") as temporary:
            repo = Path(temporary)
            git(repo, "init", "-q")
            git(repo, "config", "user.name", "Scanner Test")
            git(repo, "config", "user.email", "user@example.com")
            fixture = repo / "tracked.txt"
            fixture.write_text("clean\n", encoding="utf-8")
            git(repo, "add", fixture.name)
            git(repo, "commit", "-qm", "baseline")
            value = secret_shapes()[6][1]
            fixture.write_text(value + "\n", encoding="utf-8")
            default = run_scan(cwd=repo)
            whole_tree = run_scan("--all", cwd=repo)
            self.assertEqual(default.returncode, 0, default.stdout + default.stderr)
            self.assertEqual(whole_tree.returncode, 1, whole_tree.stdout + whole_tree.stderr)
            self.assertIn("tracked.txt:1", whole_tree.stdout + whole_tree.stderr)
            self.assertNotIn(value, whole_tree.stdout + whole_tree.stderr)

    def test_foreign_pre_commit_hook_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith scanner hook ") as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            git(project, "init", "-q")
            hook = project / ".git" / "hooks" / "pre-commit"
            hook.write_text("#!/bin/sh\necho foreign-hook\n", encoding="utf-8")
            before = hook.read_bytes()
            env = os.environ.copy()
            env.update({
                "HOME": str(root / "home"),
                "USERPROFILE": str(root / "home"),
                "CODEX_HOME": str(root / "codex home"),
            })
            install = subprocess.run(
                [
                    sys.executable,
                    str(CORE),
                    "install",
                    "--agent",
                    "native",
                    "--profile",
                    "general-admin",
                    "--with-hooks",
                    "--target",
                    str(project),
                ],
                cwd=project,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
            self.assertEqual(hook.read_bytes(), before)
            self.assertIn("foreign pre-commit hook preserved", install.stderr)

    @unittest.skipIf(os.name == "nt", "POSIX compatibility launcher is not a native Windows surface")
    def test_shell_compatibility_launcher_delegates_to_python(self) -> None:
        value = secret_shapes()[7][1]
        result = subprocess.run(
            ["bash", str(SHELL_LAUNCHER), "-"],
            cwd=ROOT,
            input=value + "\n",
            text=True,
            capture_output=True,
            check=False,
        )
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1, combined)
        self.assertIn("Google API key", combined)
        self.assertNotIn(value, combined)

    def test_tracked_tree_scan_stays_within_pre_commit_speed_bound(self) -> None:
        started = time.monotonic()
        result = run_scan("--all", cwd=ROOT)
        elapsed = time.monotonic() - started
        self.assertIn(result.returncode, {0, 1}, result.stdout + result.stderr)
        self.assertLessEqual(elapsed, 15.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
