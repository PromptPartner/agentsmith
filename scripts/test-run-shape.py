#!/usr/bin/env python3
"""Run-shape guards (SF-16): real runs with fake clients and no network, plus unit fixtures.

- an infrastructure fault of a role client is never counted as an attempt;
- an attempt loop ends after N identical rejections or K silent maker turns;
- coordination-sensitive files (spec, migration, schema, contract) serialise runs, and a numbered
  resource gets the next free number.
"""

from __future__ import annotations

import _fixture_git  # first: keeps every Git fixture out of an inherited repository
_fixture_git.isolate()
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
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
CONTROLLER_PATH = ROOT / "scripts" / "autonomous-run.py"
SPEC = importlib.util.spec_from_file_location("agentsmith_run_shape_controller", CONTROLLER_PATH)
assert SPEC and SPEC.loader
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)

# The fake client follows `plan.json` beside it: `maker` is a list of actions, one per maker
# launch (the last one repeats), and `checker` is the checker's verdict. It logs each launch.
FAKE_CLIENT = textwrap.dedent('''\
    import json, pathlib, re, subprocess, sys
    argv = sys.argv[1:]
    prompt = argv[-1]
    root = pathlib.Path(__file__).resolve().parent
    plan = json.loads((root / "plan.json").read_text(encoding="utf-8"))
    receipt_path = pathlib.Path(argv[argv.index("-o") + 1]) if "-o" in argv else None
    checker = "You are the independent checker" in prompt
    role = "checker" if checker else "maker"
    with (root / "launches.log").open("a", encoding="utf-8") as log:
        log.write(role + "\\n")
    if not checker:
        count = sum(1 for line in (root / "launches.log").read_text().splitlines() if line == "maker")
        actions = plan["maker"]
        action = actions[min(count, len(actions)) - 1]
        if action == "infra-dirty":
            # A partial write, then the client loses its network before any receipt.
            pathlib.Path("src").mkdir(exist_ok=True)
            pathlib.Path("src/partial.txt").write_text("half\\n", encoding="utf-8")
            print(json.dumps({"type": "error", "message": "stream disconnected before completion"}))
            sys.exit(1)
        if action == "empty":
            subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "chore: nothing"], check=True)
        else:
            pathlib.Path("src").mkdir(exist_ok=True)
            pathlib.Path(f"src/change{count}.txt").write_text("fixed\\n", encoding="utf-8")
            subprocess.run(["git", "add", "src"], check=True)
            subprocess.run(["git", "commit", "-qm", "fix: fixture change"], check=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    base = re.search(r"--no-renames ([0-9a-f]{40}) HEAD", prompt).group(1)
    changed = subprocess.run(["git", "diff", "--name-only", "--no-renames", base, "HEAD"], check=True,
                             capture_output=True, text=True).stdout.split()
    log = re.search(r"attempt-[0-9]+-verify[.]txt", prompt)
    verdict = plan.get("checker", "accepted") if checker else "completed"
    evidence = (["fixture verification passed :: " + log.group(0) + " :: fixture verification passed"]
                if checker and verdict == "accepted" else ["fixture evidence"])
    receipt = {"status": verdict, "summary": "fixture", "commit": commit, "changed_paths": changed,
               "evidence": evidence, "unresolved": [] if verdict != "rejected" else ["still wrong"],
               "next_state": verdict}
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


class RunFixture(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="agentsmith run shape ")
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
            "accepted_at: 2026-11-24\n---\n# Spec\nAdd a change file under src.\n", encoding="utf-8")
        (self.repo / ".harness/runs").mkdir(parents=True)
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-qm", "test: base")
        # A passed calibration of the fixture checker, so its acceptances gate instead of waiting for a human.
        CONTROLLER.write_json(
            CONTROLLER.calibration_path(self.repo, "claude", "fixture-model", "high"),
            CONTROLLER.calibration_record(
                {"runtime": "claude", "model": "fixture-model", "effort": "high"},
                [{"label": "clean", "expected": "accepted", "verdict": "accepted", "correct": True},
                 {"label": "defect", "expected": "rejected", "verdict": "rejected", "correct": True}],
                client_version="fixture", usage={"claude_cost_usd": 0.0, "codex_tokens_used": 0}))

    def git(self, repo: Path, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=repo, env=self.env, text=True, capture_output=True,
                              check=True).stdout.strip()

    def plan(self, maker: list[str], checker: str = "accepted") -> None:
        (self.fake / "plan.json").write_text(json.dumps({"maker": maker, "checker": checker}), encoding="utf-8")

    def commit_manifest(self, run_id: str, verify: str = 'echo "fixture verification passed"',
                        **limits: object) -> None:
        value = json.loads((ROOT / "templates/autonomous-run.json").read_text(encoding="utf-8"))
        value.update(run_id=run_id, spec_path="docs/specs/task.md", implementation_ticket="IMP-1")
        for role in value["roles"].values():
            role["model"] = "fixture-model"
        value["scope"]["allowed_paths"] = ["src/**"]
        value["verify"]["command"] = verify
        value["limits"].update(wall_minutes=5, **limits)
        (self.repo / f".harness/runs/{run_id}.json").write_text(json.dumps(value, indent=2) + "\n",
                                                                encoding="utf-8")
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-qm", f"test: {run_id} contract")

    def controller(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(CONTROLLER_PATH), *args], cwd=self.repo, env=self.env, text=True,
                              capture_output=True, check=False, timeout=300)

    def state(self, run_id: str) -> dict:
        return json.loads((self.repo / ".git/agentsmith-runs" / run_id / "state.json").read_text(encoding="utf-8"))

    def events(self, run_id: str) -> list[dict]:
        path = self.repo / ".git/agentsmith-runs" / run_id / "events.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def launches(self) -> list[str]:
        log = self.fake / "launches.log"
        return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


class InfrastructureFaultTests(unittest.TestCase):
    def test_a_maker_fault_that_dirtied_the_worktree_still_reruns_the_same_attempt(self) -> None:
        def fault(*_args: object, **_kwargs: object) -> dict:
            raise CONTROLLER.InfrastructureFailure("codex maker exited 1 (network)", "network")

        for role, repeats in (("maker", True), ("checker", False)):
            with self.subTest(role=role):
                state = {"attempt": 1}
                with mock.patch.object(CONTROLLER, "launch_role", side_effect=fault), \
                        mock.patch.object(CONTROLLER, "save_state"):
                    with self.assertRaisesRegex(CONTROLLER.RunError, "not relaunched because"):
                        CONTROLLER.launch_role_with_breaker(
                            state, {}, role, "p", retry_problem=lambda: "the failed maker changed the worktree")
                # Only a maker's attempt is rerun this way: a checker's candidate stays pending.
                self.assertEqual(state.get("repeat_attempt", False), repeats)
        # A relaunch that finishes the attempt leaves no flag, so the next attempt gets a new number.
        outcomes = iter([CONTROLLER.InfrastructureFailure("codex maker exited 1 (network)", "network"),
                         {"status": "completed"}])

        def flaky(*_args: object, **_kwargs: object) -> dict:
            outcome = next(outcomes)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        state = {"attempt": 1}
        with mock.patch.object(CONTROLLER, "launch_role", side_effect=flaky), \
                mock.patch.object(CONTROLLER, "save_state"):
            self.assertEqual(CONTROLLER.launch_role_with_breaker(state, {}, "maker", "p"), {"status": "completed"})
        self.assertNotIn("repeat_attempt", state)


@unittest.skipUnless(sandbox_available(), "a real run needs the macOS or Linux role sandbox")
class InfrastructureFaultRunTests(RunFixture):
    def test_an_infrastructure_fault_never_spends_the_only_attempt(self) -> None:
        # The fault leaves a partial file, so the breaker cannot relaunch from a clean start and the
        # run stops for a person. Once the operator cleans up, resume reruns attempt 1: with one
        # attempt allowed, counting the fault would leave no attempt at all.
        self.plan(["infra-dirty", "change"])
        self.commit_manifest("infra", max_attempts=1)
        first = self.controller("start", ".harness/runs/infra.json")
        self.assertEqual(first.returncode, 2, first.stdout + first.stderr)
        self.assertIn("not relaunched because the failed maker changed the worktree", first.stderr)
        self.assertEqual(self.state("infra")["attempt"], 1)
        (Path(self.state("infra")["worktree"]) / "src/partial.txt").unlink()
        resumed = self.controller("resume", "infra")
        self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
        state = self.state("infra")
        self.assertEqual((state["status"], state["attempt"]), ("accepted", 1))
        self.assertEqual(self.launches(), ["maker", "maker", "checker"])


class RejectionSignatureTests(unittest.TestCase):
    def test_the_signature_is_the_reason_and_the_failing_tests_not_the_noise(self) -> None:
        signature = CONTROLLER.rejection_signature
        first = "exit=1\nSTDOUT:\nFAIL: test_value (tests.Case)\nRan 3 tests in 0.012s\nSTDERR:\n"
        later = "exit=1\nSTDOUT:\nFAIL: test_value (tests.Case)\nRan 3 tests in 1.250s\nSTDERR:\n"
        other = "exit=1\nSTDOUT:\nFAIL: test_other (tests.Case)\nRan 3 tests in 0.012s\nSTDERR:\n"
        self.assertEqual(signature({}, first), signature({}, later), "timings are not a new failure")
        self.assertNotEqual(signature({}, first), signature({}, other))
        self.assertNotEqual(signature({"reason": "verify"}, first), signature({"reason": "checker"}, first))
        # A rejection event without a reason is its own value, never a match for a reason code.
        self.assertNotEqual(signature({}, first), signature({"reason": "verify"}, first))
        self.assertEqual(signature({}, None), signature({}, None), "no verify output is a value too")
        self.assertNotEqual(signature({}, None), signature({}, first))
        # Without named failing tests, the normalised end of the output decides.
        tail = "exit=1\nSTDOUT:\nbuild broke at 2026-11-24T10:00:01Z in /tmp/w-check-1 (0.4s)\nSTDERR:\n"
        retry = "exit=1\nSTDOUT:\nbuild broke at 2026-11-24T10:07:42Z in /tmp/w-check-2 (1.9s)\nSTDERR:\n"
        self.assertEqual(signature({}, tail), signature({}, retry))
        self.assertNotEqual(signature({}, tail), signature({}, tail.replace("build broke", "lint broke")))

    def test_the_guard_limits_are_bounded_whole_numbers(self) -> None:
        manifest = json.loads((ROOT / "templates/autonomous-run.json").read_text(encoding="utf-8"))
        CONTROLLER.validate_budgets(manifest)
        self.assertEqual(CONTROLLER.run_shape_limits(manifest["limits"]),
                         (CONTROLLER.DEFAULT_IDENTICAL_REJECTIONS, CONTROLLER.DEFAULT_SILENT_TURNS))
        for field, value in (("max_identical_rejections", 1), ("max_identical_rejections", 4),
                             ("max_identical_rejections", 2.0), ("max_silent_turns", 0),
                             ("max_silent_turns", True), ("max_silent_turns", "2")):
            with self.subTest(field=field, value=value):
                limits = {**manifest["limits"], field: value}
                with self.assertRaisesRegex(CONTROLLER.RunError, f"limits.{field}"):
                    CONTROLLER.validate_budgets({**manifest, "limits": limits})
        limits = {**manifest["limits"], "max_identical_rejections": 3, "max_silent_turns": 2}
        CONTROLLER.validate_budgets({**manifest, "limits": limits})
        self.assertEqual(CONTROLLER.run_shape_limits(limits), (3, 2))


@unittest.skipUnless(sandbox_available(), "a real run needs the macOS or Linux role sandbox")
class RunShapeGuardRunTests(RunFixture):
    SAME_FAILURE = 'echo "FAIL: test_value (tests.Case)"; echo "Ran 1 test"; exit 1'

    def test_two_identical_rejections_end_the_attempts_before_the_cap(self) -> None:
        self.plan(["change"], checker="rejected")
        self.commit_manifest("stuck", verify=self.SAME_FAILURE, max_attempts=3)
        result = self.controller("start", ".harness/runs/stuck.json")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        state = self.state("stuck")
        self.assertEqual((state["status"], state["attempt"]), ("escalated", 2))
        self.assertIn("2 identical rejections in a row", state["reason"])
        self.assertIn("limits.max_identical_rejections", state["reason"])
        self.assertEqual(self.launches(), ["maker", "checker", "maker", "checker"])
        escalated = [item for item in self.events("stuck") if item["event"] == "run_escalated"]
        self.assertEqual(escalated[-1]["reason"], state["reason"])

    def test_rejections_that_change_keep_every_attempt(self) -> None:
        # Each attempt fails a different test, so the maker is moving: the cap, not the guard, ends it.
        self.plan(["change"], checker="rejected")
        self.commit_manifest("moving", verify='echo "FAIL: test_$(ls src | wc -l | tr -d " ") (tests.Case)"; '
                                              'echo "Ran 1 test"; exit 1', max_attempts=3)
        result = self.controller("start", ".harness/runs/moving.json")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        state = self.state("moving")
        self.assertEqual((state["status"], state["attempt"]), ("escalated", 3))
        self.assertEqual(state["reason"], "attempt cap reached (3)")

    def test_a_silent_maker_turn_ends_the_run_before_any_verifier_or_checker(self) -> None:
        self.plan(["empty"])
        self.commit_manifest("silent", max_attempts=3)
        result = self.controller("start", ".harness/runs/silent.json")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        state = self.state("silent")
        self.assertEqual((state["status"], state["attempt"]), ("escalated", 1))
        self.assertIn("1 silent maker turn in a row", state["reason"])
        self.assertEqual(self.launches(), ["maker"])
        self.assertFalse((self.repo / ".git/agentsmith-runs/silent/attempt-1-verify.txt").exists())

    def test_silent_turns_are_counted_in_a_row_up_to_the_configured_limit(self) -> None:
        self.plan(["empty"], checker="rejected")
        self.commit_manifest("quiet", max_attempts=3, max_silent_turns=2)
        result = self.controller("start", ".harness/runs/quiet.json")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        state = self.state("quiet")
        self.assertEqual((state["status"], state["attempt"]), ("escalated", 2))
        self.assertIn("2 silent maker turns in a row", state["reason"])
        self.assertEqual(self.launches(), ["maker", "checker", "maker"])


if __name__ == "__main__":
    unittest.main()
