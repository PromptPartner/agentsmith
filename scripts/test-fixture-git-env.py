#!/usr/bin/env python3
"""Test fixtures keep their Git commands in their own temporary repositories, even when the test is
run from a hook, `git rebase --exec` or a wrapper that exports GIT_DIR and friends."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import _fixture_git  # noqa: E402

_fixture_git.isolate()
CLEAN_ENV = dict(os.environ)


class SentinelTests(unittest.TestCase):
    """Run real fixture-using tests with GIT_DIR pointing at a sentinel; the sentinel must not change."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agentsmith fixture env ")
        self.sentinel = Path(self.temporary.name) / "sentinel"
        subprocess.run(["git", "init", "-q", str(self.sentinel)], env=CLEAN_ENV, check=True)
        subprocess.run(["git", "-C", str(self.sentinel), "-c", "user.name=Sentinel", "-c", "user.email=user@example.com",
                        "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "sentinel"],
                       env=CLEAN_ENV, check=True)
        self.inherited = {**CLEAN_ENV, "GIT_DIR": str(self.sentinel / ".git"), "GIT_WORK_TREE": str(self.sentinel),
                          "GIT_INDEX_FILE": str(self.sentinel / ".git" / "index")}

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def snapshot(self) -> tuple[bytes, bytes, bytes]:
        git = ["git", "-C", str(self.sentinel)]
        refs = subprocess.run([*git, "for-each-ref", "--format=%(refname) %(objectname)"], env=CLEAN_ENV,
                              capture_output=True, check=True).stdout
        objects = subprocess.run([*git, "count-objects", "-v"], env=CLEAN_ENV, capture_output=True, check=True).stdout
        return (self.sentinel / ".git" / "config").read_bytes(), refs, objects

    def assert_untouched(self, command: list[str]) -> None:
        before = self.snapshot()
        result = subprocess.run(command, cwd=SCRIPTS.parent, env=self.inherited, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(self.snapshot(), before, result.stdout[-2000:] + result.stderr[-2000:])
        self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-2000:])

    def test_a_python_fixture_test_leaves_an_inherited_repository_alone(self) -> None:
        self.assert_untouched([sys.executable, str(SCRIPTS / "test-durable-checkpoints.py")])

    @unittest.skipIf(os.name == "nt" or shutil.which("bash") is None, "the shell tests run on POSIX")
    def test_a_shell_fixture_test_leaves_an_inherited_repository_alone(self) -> None:
        self.assert_untouched(["bash", str(SCRIPTS / "test-wayfinder-spec.sh")])


class CoverageTests(unittest.TestCase):
    def test_every_test_script_isolates_its_git_environment(self) -> None:
        # A new test script that forgets this would bring the hazard back; this check names it.
        missing = []
        for path in sorted(SCRIPTS.glob("test-*")):
            text = path.read_text(encoding="utf-8")
            if path.suffix == ".py" and not re.search(r"^_fixture_git\.isolate\(\)$", text, re.MULTILINE):
                missing.append(path.name)
            if path.suffix == ".sh" and '/_fixture_git.sh"' not in text:
                missing.append(path.name)
        self.assertEqual(missing, [])

    def test_the_shell_and_python_lists_agree(self) -> None:
        shell = (SCRIPTS / "_fixture_git.sh").read_text(encoding="utf-8")
        listed = set(re.findall(r"\bGIT_[A-Z_]+\b", shell.split("unset", 1)[1].split("\n\n", 1)[0]))
        self.assertEqual(listed, set(_fixture_git.REPOSITORY_ENV))

    def test_clean_env_drops_repository_variables_and_keeps_identity(self) -> None:
        env = _fixture_git.clean_git_env({"GIT_DIR": "x", "GIT_WORK_TREE": "y", "GIT_CONFIG_COUNT": "1",
                                          "GIT_CONFIG_KEY_0": "a", "GIT_CONFIG_VALUE_0": "b",
                                          "GIT_AUTHOR_NAME": "Kept", "PATH": "/bin"})
        self.assertEqual(env, {"GIT_AUTHOR_NAME": "Kept", "PATH": "/bin"})


if __name__ == "__main__":
    unittest.main()
