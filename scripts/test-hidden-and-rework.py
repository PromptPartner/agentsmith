#!/usr/bin/env python3
"""Hidden acceptance tests (opt-in) and rework notes: real runs with fake clients, no network."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parent.parent
CONTROLLER_PATH = ROOT / "scripts" / "autonomous-run.py"
SPEC = importlib.util.spec_from_file_location("agentsmith_hidden_controller", CONTROLLER_PATH)
assert SPEC and SPEC.loader
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)
SECRET = "SECRET-ORACLE-7f3a"

# The fake client logs every prompt it gets, so a test can show what a maker saw.
FAKE_CLIENT = textwrap.dedent('''\
    import json, pathlib, re, subprocess, sys
    argv = sys.argv[1:]
    prompt = argv[-1]
    root = pathlib.Path(__file__).resolve().parent
    with (root / "prompts.log").open("a", encoding="utf-8") as log:
        log.write(json.dumps(prompt) + "\\n")
    receipt_path = pathlib.Path(argv[argv.index("-o") + 1]) if "-o" in argv else None
    checker = "You are the independent checker" in prompt
    if not checker:
        pathlib.Path("src").mkdir(exist_ok=True)
        count = len(list(pathlib.Path("src").glob("change*.txt")))
        pathlib.Path(f"src/change{count}.txt").write_text("fixed\\n", encoding="utf-8")
        subprocess.run(["git", "add", "src"], check=True)
        subprocess.run(["git", "commit", "-qm", "fix: fixture change"], check=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    base = re.search(r"--no-renames ([0-9a-f]{40}) HEAD", prompt).group(1)
    changed = subprocess.run(["git", "diff", "--name-only", "--no-renames", base, "HEAD"], check=True,
                             capture_output=True, text=True).stdout.split()
    log = re.search(r"attempt-[0-9]+-verify[.]txt", prompt)
    evidence = (["fixture verification passed :: " + log.group(0) + " :: fixture verification passed"]
                if checker else ["maker ran the fixture verification"])
    status = "accepted" if checker else "completed"
    receipt = {"status": status, "summary": "fixture", "commit": commit, "changed_paths": changed,
               "evidence": evidence, "unresolved": [], "next_state": status}
    if receipt_path is not None:
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 3}}))
    else:
        print(json.dumps({"type": "result", "total_cost_usd": 0.25, "structured_output": receipt}))
''')


def sandbox_available() -> bool:
    if sys.platform == "darwin":
        return Path("/usr/bin/sandbox-exec").exists()
    return sys.platform.startswith("linux") and shutil.which("bwrap") is not None


class Fixture(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="agentsmith hidden ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.fake = self.root / "fake"
        (self.fake / "codex-home").mkdir(parents=True)
        (self.fake / "codex-home/auth.json").write_text('{"auth_mode":"chatgpt"}', encoding="utf-8")
        (self.fake / "agent.py").write_text(FAKE_CLIENT, encoding="utf-8")
        self.env.update(AGENTSMITH_CODEX_BIN=str(self.fake / "agent.py"),
                        AGENTSMITH_CLAUDE_BIN=str(self.fake / "agent.py"), CODEX_HOME=str(self.fake / "codex-home"))
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git(self.repo, "init", "-q", "-b", "main")
        self.git(self.repo, "config", "user.name", "Harness Test")
        self.git(self.repo, "config", "user.email", "user@example.com")
        (self.repo / "docs/specs").mkdir(parents=True)
        (self.repo / "docs/specs/task.md").write_text(
            "---\nstatus: accepted\ndecision_ticket: DEC-1\naccepted_by: Test Operator\n"
            "accepted_at: 2026-11-06\n---\n# Spec\nMake src/change0.txt hold the fixed value.\n", encoding="utf-8")
        (self.repo / ".harness/runs").mkdir(parents=True)
        (self.repo / ".harness/risk-policy.json").write_text(json.dumps(
            {"schema_version": 1, "rules": [{"paths": ["src/**"], "tier": "C"}]}), encoding="utf-8")
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-qm", "test: base")

    def git(self, repo: Path, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=repo, env=self.env, text=True, capture_output=True,
                              check=True).stdout.strip()

    def manifest(self, run_id: str, **fields) -> dict:
        value = json.loads((ROOT / "templates/autonomous-run.json").read_text(encoding="utf-8"))
        value.update(run_id=run_id, spec_path="docs/specs/task.md", implementation_ticket="IMP-1")
        for role in value["roles"].values():
            role["model"] = "fixture-model"
        value["scope"]["allowed_paths"] = ["src/**"]
        value["verify"]["command"] = 'test -f src/change0.txt && echo "fixture verification passed"'
        value["limits"].update(max_attempts=2, wall_minutes=5)
        value.update(fields)
        return value

    def commit_manifest(self, run_id: str, **fields) -> None:
        (self.repo / f".harness/runs/{run_id}.json").write_text(json.dumps(self.manifest(run_id, **fields), indent=2) + "\n",
                                                                encoding="utf-8")
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-qm", f"test: {run_id} contract")

    def controller(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(CONTROLLER_PATH), *args], cwd=self.repo, env=self.env, text=True,
                              capture_output=True, check=False)

    def state(self, run_id: str) -> dict:
        return json.loads((self.repo / ".git/agentsmith-runs" / run_id / "state.json").read_text(encoding="utf-8"))

    def prompts(self) -> list[str]:
        log = self.fake / "prompts.log"
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


@unittest.skipUnless(sandbox_available(), "a real run needs the macOS or Linux role sandbox")
class HiddenTestsTests(Fixture):
    def hidden_repo(self, expected: str = "fixed") -> tuple[Path, str]:
        hidden = self.root / "private-hidden-tests"
        hidden.mkdir()
        self.git(hidden, "init", "-q", "-b", "main")
        (hidden / "check.sh").write_text(
            f"# {SECRET}: human-written acceptance check\ngrep -q '^{expected}$' src/change0.txt\n", encoding="utf-8")
        self.git(hidden, "add", ".")
        self.git(hidden, "-c", "user.name=Hidden", "-c", "user.email=user@example.com", "commit", "-qm", "hidden")
        return hidden, self.git(hidden, "rev-parse", "HEAD")

    def hidden(self, hidden: Path, commit: str, tiers=("C",)) -> dict:
        return {"hidden_tests": {"repo": str(hidden), "commit": commit, "command": ["sh", "{hidden}/check.sh"],
                                 "tiers": list(tiers)}}

    def proof(self, run_id: str, attempt: int = 1) -> dict:
        return json.loads((self.repo / f".git/agentsmith-runs/{run_id}/attempt-{attempt}-verify.json").read_text(
            encoding="utf-8"))

    def test_passing_hidden_tests_are_recorded_and_the_checker_still_decides(self) -> None:
        hidden, commit = self.hidden_repo()
        self.commit_manifest("pass", **self.hidden(hidden, commit))
        started = self.controller("start", ".harness/runs/pass.json")
        self.assertEqual(started.returncode, 0, started.stderr)
        record = self.proof("pass")["hidden_tests"]
        self.assertEqual((record["status"], record["tier"], record["commit"]), ("pass", "C", commit))
        self.assertGreaterEqual(record["duration_seconds"], 0)
        self.assertIn("output_sha256", record)
        self.assertTrue(any("You are the independent checker" in prompt for prompt in self.prompts()))

    def test_failing_hidden_tests_reject_with_a_generic_hint_only(self) -> None:
        hidden, commit = self.hidden_repo(expected="a different value")
        self.commit_manifest("fail", **self.hidden(hidden, commit))
        started = self.controller("start", ".harness/runs/fail.json")
        self.assertNotEqual(started.returncode, 0)
        state = self.state("fail")
        self.assertEqual((state["status"], state["attempt"]), ("escalated", 2))
        self.assertNotIn("accepted_commit", state)
        self.assertEqual(self.proof("fail", 2)["hidden_tests"]["status"], "fail")
        makers = [prompt for prompt in self.prompts() if "independent checker" not in prompt]
        self.assertEqual(len(makers), 2)
        self.assertIn("hidden acceptance tests failed", makers[1])
        for prompt in self.prompts():
            self.assertNotIn(SECRET, prompt)
            self.assertNotIn(str(hidden), prompt)
            self.assertNotIn("check.sh", prompt)
        # The checker never ran on a candidate that the hidden tests rejected.
        self.assertFalse(any("independent checker" in prompt for prompt in self.prompts()))
        run_files = " ".join(path.read_text(encoding="utf-8", errors="replace")
                             for path in (self.repo / ".git/agentsmith-runs/fail").glob("*") if path.is_file())
        self.assertNotIn(SECRET, run_files, "no hidden content or output in files a maker can read")

    def test_a_tier_outside_the_list_skips_the_hidden_tests_and_says_so(self) -> None:
        hidden, commit = self.hidden_repo(expected="a different value")
        self.commit_manifest("skip", **self.hidden(hidden, commit, tiers=("A",)))
        started = self.controller("start", ".harness/runs/skip.json")
        self.assertEqual(started.returncode, 0, started.stderr)
        record = self.proof("skip")["hidden_tests"]
        self.assertEqual((record["status"], record["tier"], record["tiers"]), ("skipped", "C", ["A"]))

    def test_the_hidden_clone_must_exist_at_that_commit_and_stay_outside_the_run(self) -> None:
        hidden, commit = self.hidden_repo()
        self.commit_manifest("missing", **self.hidden(hidden, "f" * 40))
        refused = self.controller("start", ".harness/runs/missing.json")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("hidden_tests.commit", refused.stderr)
        self.assertFalse((self.repo / ".git/agentsmith-runs/missing/state.json").exists())
        inside = self.repo / "hidden-inside"
        shutil.copytree(hidden, inside)
        template = self.root / "template.json"
        template.write_text(json.dumps(self.manifest("x", **self.hidden(inside, commit))), encoding="utf-8")
        prepared = self.controller("prepare", "--run-id", "inside", "--spec", "docs/specs/task.md", "--ticket",
                                   "IMP-2", "--template", str(template))
        self.assertNotEqual(prepared.returncode, 0)
        self.assertIn("hidden_tests.repo must be outside", prepared.stderr)

    def test_roles_cannot_read_the_hidden_clone(self) -> None:
        hidden = Path("/hidden/clone")
        claude = CONTROLLER.claude_sandbox_settings(self.repo, hidden_read_paths=[hidden])
        self.assertIn(str(hidden), claude["sandbox"]["filesystem"]["denyRead"])
        self.assertIn(f"Read(/{hidden}/**)", claude["permissions"]["deny"])
        codex = CONTROLLER.codex_permissions(self.repo, hidden_read_paths=[hidden])
        self.assertEqual(codex["filesystem"][str(hidden)], "none")


class HiddenCloneTests(Fixture):
    """The hidden clone must be a standalone repository: nothing a role can read may hold its objects."""

    def commit_hidden(self, repo: Path) -> str:
        (repo / "check.sh").write_text(f"# {SECRET}\nexit 1\n", encoding="utf-8")
        self.git(repo, "add", "check.sh")
        self.git(repo, "-c", "user.name=Hidden", "-c", "user.email=user@example.com", "commit", "-qm", "hidden")
        return self.git(repo, "rev-parse", "HEAD")

    def problem(self, clone: Path, commit: str) -> str | None:
        hidden = {"repo": str(clone), "commit": commit, "command": ["sh", "{hidden}/check.sh", "{token}"],
                  "tiers": ["C"]}
        return CONTROLLER.hidden_tests_problem(self.manifest("x", hidden_tests=hidden), self.repo)

    def test_a_worktree_of_the_candidate_repository_is_refused(self) -> None:
        clone = self.root / "external-hidden-worktree"
        self.git(self.repo, "worktree", "add", "-q", "-b", "hidden-suite", str(clone))
        commit = self.commit_hidden(clone)
        self.assertEqual(self.git(self.repo, "show", f"{commit}:check.sh").splitlines()[0], f"# {SECRET}",
                         "the candidate repository can read this commit")
        self.assertIn("standalone", self.problem(clone, commit) or "")

    def test_a_clone_that_borrows_objects_or_keeps_its_git_folder_elsewhere_is_refused(self) -> None:
        borrowing = self.root / "borrowing"
        subprocess.run(["git", "clone", "-q", "--shared", str(self.repo), str(borrowing)], env=self.env, check=True)
        self.assertIn("standalone", self.problem(borrowing, self.commit_hidden(borrowing)) or "")
        separate = self.root / "separate"
        subprocess.run(["git", "init", "-q", "--separate-git-dir", str(self.root / "elsewhere.git"), str(separate)],
                       env=self.env, check=True)
        self.assertIn("standalone", self.problem(separate, self.commit_hidden(separate)) or "")
        standalone = self.root / "standalone"
        subprocess.run(["git", "init", "-q", str(standalone)], env=self.env, check=True)
        self.assertIsNone(self.problem(standalone, self.commit_hidden(standalone)))


class ReworkNoteTests(Fixture):
    NOTE = "Keep the fixed value, but also handle an empty file: the operator saw it fail in review."

    def finished_run(self, run_id: str, status: str) -> None:
        folder = self.repo / ".git/agentsmith-runs" / run_id
        folder.mkdir(parents=True)
        (folder / "state.json").write_text(json.dumps({"run_id": run_id, "status": status}), encoding="utf-8")

    def prepare(self, run_id: str, rework_of: str, note: str = "notes/rework.md") -> subprocess.CompletedProcess[str]:
        template = self.root / "template.json"
        template.write_text(json.dumps(self.manifest("x")), encoding="utf-8")
        return self.controller("prepare", "--run-id", run_id, "--spec", "docs/specs/task.md", "--ticket", "IMP-2",
                               "--template", str(template), "--rework-of", rework_of, "--note", note)

    def write_note(self, text: str | None = None) -> None:
        (self.repo / "notes").mkdir(exist_ok=True)
        (self.repo / "notes/rework.md").write_text(text or self.NOTE + "\n", encoding="utf-8")

    def test_a_rework_is_a_new_run_with_the_note_pinned_by_hash(self) -> None:
        self.finished_run("first", "accepted")
        self.write_note()
        prepared = self.prepare("second", "first")
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        manifest = json.loads((self.repo / ".harness/runs/second.json").read_text(encoding="utf-8"))
        digest = hashlib.sha256((self.repo / "notes/rework.md").read_bytes()).hexdigest()
        self.assertEqual(manifest["rework"], {"of": "first", "note_path": "notes/rework.md", "note_sha256": digest})
        self.assertEqual(json.loads((self.repo / ".git/agentsmith-runs/first/state.json").read_text())["status"],
                         "accepted", "the accepted run is never reopened")

    @unittest.skipUnless(sandbox_available(), "a real run needs the macOS or Linux role sandbox")
    def test_the_maker_receives_the_note_and_a_changed_note_refuses(self) -> None:
        self.finished_run("first", "escalated")
        self.write_note()
        self.assertEqual(self.prepare("second", "first").returncode, 0)
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-qm", "test: rework contract")
        started = self.controller("start", ".harness/runs/second.json")
        self.assertEqual(started.returncode, 0, started.stderr)
        maker = next(prompt for prompt in self.prompts() if "independent checker" not in prompt)
        self.assertIn(self.NOTE, maker)
        self.assertIn("rework of run first", maker)
        self.write_note("A different instruction.\n")
        self.assertEqual(self.prepare("third", "first").returncode, 0)
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-qm", "test: third")
        self.write_note("Edited after prepare.\n")
        refused = self.controller("start", ".harness/runs/third.json")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("rework note changed since prepare", refused.stderr)
        self.assertFalse((self.repo / ".git/agentsmith-runs/third/state.json").exists())

    def test_only_a_finished_run_can_be_reworked_and_never_in_place(self) -> None:
        self.write_note()
        self.finished_run("busy", "making")
        refused = self.prepare("next", "busy")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("run busy is making; only a finished run", refused.stderr)
        refused = self.prepare("next", "unknown")
        self.assertIn("no run state for unknown", refused.stderr)
        self.finished_run("done", "accepted")
        refused = self.prepare("done", "done")
        self.assertIn("a rework is a new run", refused.stderr)
        refused = self.prepare("next", "done", note="notes/missing.md")
        self.assertIn("rework note", refused.stderr)
        self.assertFalse((self.repo / ".harness/runs/next.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
