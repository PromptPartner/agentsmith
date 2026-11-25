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
    if checker and verdict == "accepted" and plan.get("cite") == "shown":
        # What a careful checker does: quote every line the prompt shows as that file's text.
        shown = prompt.split("(the file " + log.group(0) + "):\\n", 1)[1].split("\\nTo accept", 1)[0]
        evidence = ["shown line :: " + log.group(0) + " :: " + line.strip() for line in shown.splitlines()
                    if len(re.sub(r"exit=-?[0-9]+|STDOUT:|STDERR:|\\s", "", line)) >= 12]
    receipt = {"status": verdict, "summary": ("VERDICT: " + verdict.upper() + "\\n## Summary\\n- fixture change\\n"
                          "- ran the verifier\\n- nothing else"
                          + ("" if checker else "\\n## Assumptions without authority\\n- none")), "commit": commit, "changed_paths": changed,
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

    def plan(self, maker: list[str], checker: str = "accepted", **extra: str) -> None:
        (self.fake / "plan.json").write_text(json.dumps({"maker": maker, "checker": checker, **extra}),
                                             encoding="utf-8")

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


@unittest.skipUnless(sandbox_available(), "a real run needs the macOS or Linux role sandbox")
class CheckerPromptCitationRunTests(RunFixture):
    def test_every_line_the_prompt_shows_as_the_verify_log_can_be_cited_from_it(self) -> None:
        # Demo lap-01-r3 (2026-11-24): the checker accepted, quoting the controller's
        # "regressions against the baseline" line, which the prompt showed under the verify log's
        # name but which is not in that file. The citation check then threw the acceptance away.
        self.plan(["change"], cite="shown")
        self.commit_manifest("cite", max_attempts=1)
        result = self.controller("start", ".harness/runs/cite.json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.state("cite")["status"], "accepted")
        self.assertEqual([item for item in self.events("cite") if item["event"] == "checker_defect"], [])


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

    def output(self, line: str) -> str:
        return f"exit=1\nSTDOUT:\n{line}\nSTDERR:\n"

    def test_ordinary_numbers_in_the_output_are_kept(self) -> None:
        signature = CONTROLLER.rejection_signature
        for first, second in (("E expected rows 1000001", "E expected rows 1000002"),
                              ("E expected rows 1000000", "E expected rows 2000000"),
                              ("E got 42 items", "E got 43 items")):
            with self.subTest(first=first):
                self.assertNotEqual(signature({}, self.output(first)), signature({}, self.output(second)))
        # A hash is still volatile noise: it has a letter and a digit.
        self.assertEqual(signature({}, self.output("E broke at commit 3f9a2c1d")),
                         signature({}, self.output("E broke at commit 0be4d77a")))

    def test_temporary_paths_processes_ports_and_attempt_numbers_are_noise(self) -> None:
        signature = CONTROLLER.rejection_signature
        for first, second in (
                ("E assertion failed: /tmp/tmpAbcX/input.txt", "E assertion failed: /tmp/tmpQrsY/input.txt"),
                ("E missing /private/var/folders/wg/2q3j1tp_n4vj/T/tmpk2j9_x1q/out.json",
                 "E missing /var/folders/ab/zz81klq0xyz1/T/tmp93hd02lm/out.json"),
                ("E missing /tmp/agentsmith-role-output-3kd8s2/receipt.json",
                 "E missing /tmp/agentsmith-role-output-p01xzq/receipt.json"),
                (r"E missing C:\Users\user\AppData\Local\Temp\tmpa1b2c3\x.txt",
                 r"E missing C:\Users\user\AppData\Local\Temp\tmpz9y8x7\x.txt"),
                ("E server pid=1234 port=49152 unavailable", "E server pid=5678 port=50341 unavailable"),
                ("E cannot reach 127.0.0.1:49152", "E cannot reach 127.0.0.1:50341"),
                ("E build failed on attempt 1", "E build failed on attempt 2"),
                ("E build failed (Attempt #1)", "E build failed (Attempt #2)")):
            with self.subTest(first=first):
                self.assertEqual(signature({}, self.output(first)), signature({}, self.output(second)))
        # What is not volatile still tells two failures apart.
        for first, second in (("E assertion failed: /tmp/tmpAbcX/input.txt", "E assertion failed: /tmp/tmpAbcX/other.txt"),
                              ("E server pid=1234 port=49152 unavailable", "E server pid=1234 port=49152 refused"),
                              ("E build failed on attempt 1", "E lint failed on attempt 1"),
                              # A project folder named tmp is not a temporary folder.
                              ("E missing src/tmp/a/x.txt", "E missing src/tmp/b/x.txt")):
            with self.subTest(first=first, second=second):
                self.assertNotEqual(signature({}, self.output(first)), signature({}, self.output(second)))

    def test_the_guard_limits_are_bounded_whole_numbers(self) -> None:
        manifest = json.loads((ROOT / "templates/autonomous-run.json").read_text(encoding="utf-8"))
        CONTROLLER.validate_budgets(manifest)
        self.assertEqual(CONTROLLER.run_shape_limits(manifest["limits"]),
                         (CONTROLLER.DEFAULT_IDENTICAL_REJECTIONS, CONTROLLER.DEFAULT_SILENT_TURNS))
        for field, value in (("max_identical_rejections", 1), ("max_identical_rejections", 4),
                             ("max_identical_rejections", 2.0), ("max_silent_turns", 0),
                             ("max_silent_turns", True), ("max_silent_turns", "2"),
                             # A JSON integer too large for a float is refused, not an OverflowError.
                             ("max_identical_rejections", 10 ** 400), ("max_silent_turns", 10 ** 400),
                             ("max_attempts", 10 ** 400), ("codex_goal_tokens", 10 ** 400)):
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

    def rework(self, run_id: str, of: str) -> None:
        """Prepare and commit a rework of `of`: a new run with its own events.jsonl and state."""
        (self.repo / "notes").mkdir(exist_ok=True)
        (self.repo / "notes/rework.md").write_text("Look at the failing test again.\n", encoding="utf-8")
        template = self.root / "template.json"
        template.write_text((self.repo / f".harness/runs/{of}.json").read_text(encoding="utf-8"), encoding="utf-8")
        prepared = self.controller("prepare", "--run-id", run_id, "--spec", "docs/specs/task.md", "--ticket", "IMP-2",
                                   "--template", str(template), "--rework-of", of, "--note", "notes/rework.md")
        self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-qm", f"test: {run_id} rework contract")

    def test_a_rework_starts_both_guard_counts_at_zero(self) -> None:
        # The rework of a run the identical-rejection guard stopped gets its own two rejections.
        self.plan(["change"], checker="rejected")
        self.commit_manifest("stuck", verify=self.SAME_FAILURE, max_attempts=3)
        self.assertEqual(self.controller("start", ".harness/runs/stuck.json").returncode, 2)
        self.rework("unstuck", "stuck")
        result = self.controller("start", ".harness/runs/unstuck.json")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        state = self.state("unstuck")
        self.assertEqual((state["status"], state["attempt"]), ("escalated", 2))
        self.assertIn("2 identical rejections in a row", state["reason"])
        self.assertEqual(self.launches(), ["maker", "checker"] * 4)
        # The rework of a run the silent-turn guard stopped is judged on its own first turn.
        (self.fake / "launches.log").unlink()
        self.plan(["empty", "change"])
        self.commit_manifest("silent", max_attempts=3)
        self.assertEqual(self.controller("start", ".harness/runs/silent.json").returncode, 2)
        self.assertEqual(self.state("silent")["silent_turns"], {"attempt": 1, "count": 1})
        self.rework("spoken", "silent")
        result = self.controller("start", ".harness/runs/spoken.json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = self.state("spoken")
        self.assertEqual((state["status"], state["attempt"], state["silent_turns"]),
                         ("accepted", 1, {"attempt": 1, "count": 0}))

    def test_silent_turns_are_counted_in_a_row_up_to_the_configured_limit(self) -> None:
        self.plan(["empty"], checker="rejected")
        self.commit_manifest("quiet", max_attempts=3, max_silent_turns=2)
        result = self.controller("start", ".harness/runs/quiet.json")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        state = self.state("quiet")
        self.assertEqual((state["status"], state["attempt"]), ("escalated", 2))
        self.assertIn("2 silent maker turns in a row", state["reason"])
        self.assertEqual(self.launches(), ["maker", "checker", "maker"])


def scope(*paths: str, **extra: object) -> dict:
    return {"allowed_paths": list(paths), "denied_paths": [], "resources": [], **extra}


class SequencedResourceTests(unittest.TestCase):
    def test_shared_coordination_files_collide_even_without_shared_paths(self) -> None:
        collision = CONTROLLER.scope_collision
        for left, right, expected in (
            (scope("services/a/migrations/*"), scope("services/b/migrations/*"), "migration"),
            (scope("migrations/0002_a.sql"), scope("migrations/0003_b.sql"), "migration"),
            (scope("db/a/schema.sql"), scope("db/b/schema.sql"), "schema"),
            (scope("api/a.proto"), scope("api/b.proto"), "contract"),
            (scope("svc/a/openapi.yaml"), scope("svc/b/openapi.yaml"), "contract"),
            (scope("docs/specs/a.md"), scope("docs/specs/b.md"), "spec"),
            # A class the project adds; either side's declaration classifies both sides.
            (scope("docs/adr/0002-a.md", sequenced={"adr": ["docs/adr/*"]}), scope("docs/adr/0003-b.md"), "adr"),
        ):
            with self.subTest(left=left["allowed_paths"], right=right["allowed_paths"]):
                self.assertEqual(collision(left, right), ("sequenced", expected))
                self.assertEqual(collision(right, left), ("sequenced", expected))
        # Shared paths and shared resources are reported as before.
        self.assertEqual(collision(scope("db/migrations/*"), scope("db/migrations/*"))[0], "path")
        for left, right in ((scope("src/a/**"), scope("src/b/**")),
                            (scope("src/a/**"), scope("services/b/migrations/*")),
                            (scope("docs/**", "tests/**"), scope("src/**"))):
            with self.subTest(left=left["allowed_paths"], right=right["allowed_paths"]):
                self.assertIsNone(collision(left, right))

    def test_a_glob_that_could_name_a_class_folder_counts_as_that_class(self) -> None:
        collision = CONTROLLER.scope_collision
        for left in ("a/[m]igrations/*", "a/Migrations/*", "a/MIGRATE/*", "a/mig*/0002.sql", "a/?igrations/*",
                     "a/[!x]igrations/*", "a/*ations/*"):
            with self.subTest(left=left):
                self.assertEqual(collision(scope(left), scope("b/migrations/*")), ("sequenced", "migration"))
        self.assertEqual(collision(scope("api/[a-c].PROTO"), scope("lib/x.proto")), ("sequenced", "contract"))
        self.assertEqual(collision(scope("svc/a/Schema.SQL"), scope("svc/b/schema.sql")), ("sequenced", "schema"))
        # A glob that cannot spell the class folder or name stays out of it.
        for left in ("a/[!m]igrations/*", "a/mig[0-9]/*", "a/src/*.py"):
            with self.subTest(left=left):
                self.assertIsNone(collision(scope(left), scope("b/migrations/*")))
        # A segment that is only a wildcard is a broad scope, not a class path (a known limit).
        self.assertIsNone(collision(scope("src/a/**"), scope("src/b/**")))
        self.assertIsNone(collision(scope("a/**/0002.sql"), scope("b/migrations/0003.sql")))

    def test_a_declared_class_is_checked_like_any_scope_path(self) -> None:
        for value, message in (({"ADR": ["docs/adr/*"]}, "class names"), ({"adr": "docs/adr/*"}, "array"),
                               ({"adr": ["/abs/*"]}, "repository-relative"), ([], "JSON object")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(CONTROLLER.RunError, message):
                    CONTROLLER.normalized_scope(scope("src/**", sequenced=value))
        self.assertNotIn("sequenced", CONTROLLER.normalized_scope(scope("src/**")))
        self.assertEqual(CONTROLLER.normalized_scope(scope("src/**", sequenced={"adr": ["docs/adr/*"]}))["sequenced"],
                         {"adr": ["docs/adr/*"]})

    def test_a_live_run_on_the_same_class_refuses_the_second_start(self) -> None:
        with mock.patch.object(CONTROLLER, "state_root") as root:
            run_dir = mock.MagicMock()
            run_dir.name, run_dir.is_dir.return_value = "first", True
            root.return_value.exists.return_value = True
            root.return_value.iterdir.return_value = [run_dir]
            with mock.patch.object(CONTROLLER, "read_lock", return_value={"pid": 1}), \
                    mock.patch.object(CONTROLLER, "process_is_live", return_value=True), \
                    mock.patch.object(CONTROLLER, "live_run_scope",
                                      return_value=("first", CONTROLLER.normalized_scope(scope("a/migrations/*")))):
                with self.assertRaisesRegex(CONTROLLER.RunError,
                                            "run second conflicts with live run first: both change migration files"):
                    CONTROLLER.assert_no_live_scope_conflicts(Path("."), "second", scope("b/migrations/*"))

    def test_the_reserved_number_reaches_both_role_prompts(self) -> None:
        state = {"run_id": "b", "base_head": "a" * 40, "attempt": 1, "claude_cost_usd": 0.0,
                 "sequence_numbers": [{"directory": "db/migrations", "number": "0003"}]}
        manifest = json.loads((ROOT / "templates/autonomous-run.json").read_text(encoding="utf-8"))
        manifest.update(spec_path="docs/specs/task.md", implementation_ticket="IMP-1")
        for role in ("maker", "checker"):
            with self.subTest(role=role):
                prompt = CONTROLLER.role_prompt(state, manifest, role)
                self.assertIn("the next free number in db/migrations/ is 0003", prompt)
        self.assertNotIn("next free number", CONTROLLER.role_prompt({**state, "sequence_numbers": []}, manifest, "maker"))

    def test_the_next_free_number_follows_the_widest_existing_name(self) -> None:
        sys.path.insert(0, str(ROOT))
        import work_graph
        number = work_graph.next_sequence_number
        self.assertEqual(number(["0001_init.sql", "0002_users.sql", "README.md"]), "0003")
        self.assertEqual(number(["V1__init.sql", "V12__x.sql"]), "13")
        self.assertEqual(number(["0009-a.md", "0010-b.md"]), "0011")
        # Past six digits the next number would not read as numbered, so the next run would hand it
        # out again: the reservation is refused instead of ever giving a duplicate.
        self.assertEqual(number(["999998_x.sql"]), "999999")
        with self.assertRaisesRegex(work_graph.GraphError,
                                    "db/migrations has no free number of up to six digits after 999999"):
            number(["000001_a.sql", "999999_init.sql"], folder="db/migrations")
        # Timestamps and unnumbered files are not a sequence: nothing is reserved.
        self.assertIsNone(number(["20261124093000_init.rb", "schema.sql"]))
        self.assertIsNone(number([]))


def git_in(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True).stdout.strip()


class SequencedGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="agentsmith sequenced graph ")
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name).resolve() / "repo"
        self.repo.mkdir()
        git_in(self.repo, "init", "-q")
        git_in(self.repo, "config", "user.name", "Harness Test")
        git_in(self.repo, "config", "user.email", "user@example.com")
        (self.repo / "docs/specs").mkdir(parents=True)
        (self.repo / "docs/specs/accepted.md").write_text(
            "---\nstatus: accepted\ndecision_ticket: DEC-1\naccepted_by: Test Operator\n"
            "accepted_at: 2026-11-24\n---\n# Fixture\n", encoding="utf-8")
        for directory in ("services/a/migrations", "services/b/migrations", "db/migrations"):
            (self.repo / directory).mkdir(parents=True)
            (self.repo / directory / "0001_init.sql").write_text("-- base\n", encoding="utf-8")

    def graph(self, scopes: dict[str, list[str]]) -> str:
        nodes = []
        for run_id, paths in scopes.items():
            manifest = json.loads((ROOT / "templates/autonomous-run.json").read_text(encoding="utf-8"))
            for role in manifest["roles"].values():
                role["model"] = "fixture-model"
            manifest.update(run_id=run_id, spec_path="docs/specs/accepted.md", implementation_ticket=f"IMP-{run_id}")
            manifest["scope"]["allowed_paths"] = paths
            manifest["scope"]["denied_paths"] = [".git/**"]
            path = self.repo / ".harness/runs" / f"{run_id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
            path.write_bytes(payload)
            nodes.append({"run_id": run_id, "manifest_path": path.relative_to(self.repo).as_posix(),
                          "manifest_sha256": hashlib.sha256(payload).hexdigest(), "depends_on": []})
        graph = {"schema_version": 1, "graph_id": "sequenced", "max_parallel": 2,
                 "integration_order": list(scopes), "nodes": nodes}
        (self.repo / ".harness/work-graph.json").write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
        git_in(self.repo, "add", ".")
        git_in(self.repo, "commit", "-qm", "test: graph")
        return ".harness/work-graph.json"

    def test_two_migration_runs_in_different_folders_are_serialised(self) -> None:
        graph = self.graph({"a": ["services/a/**"], "b": ["services/b/**"]})
        result = subprocess.run([sys.executable, str(ROOT / "agentsmith.py"), "graph", "status", "--graph", graph,
                                 "--target", str(self.repo), "--json"], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        nodes = {node["run_id"]: node for node in json.loads(result.stdout)["nodes"]}
        # `services/a/**` is a broad pattern: it is not read as a migration path, so these two run together.
        self.assertEqual((nodes["a"]["status"], nodes["b"]["status"]), ("ready", "ready"))
        git_in(self.repo, "rm", "-rq", ".harness")
        git_in(self.repo, "commit", "-qm", "test: drop graph")
        graph = self.graph({"a": ["services/a/src/**", "services/a/migrations/*"],
                            "b": ["services/b/src/**", "services/b/migrations/*"]})
        result = subprocess.run([sys.executable, str(ROOT / "agentsmith.py"), "graph", "status", "--graph", graph,
                                 "--target", str(self.repo), "--json"], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        nodes = {node["run_id"]: node for node in json.loads(result.stdout)["nodes"]}
        self.assertEqual((nodes["a"]["status"], nodes["b"]["status"]), ("ready", "conflicting"))
        self.assertEqual(nodes["b"]["reason"], "sequenced conflict with a: migration")

    def test_a_bracket_glob_on_a_migration_folder_waits_for_its_sibling(self) -> None:
        graph = self.graph({"a": ["services/a/[m]igrations/*"], "b": ["services/b/migrations/*"]})
        result = subprocess.run([sys.executable, str(ROOT / "agentsmith.py"), "graph", "status", "--graph", graph,
                                 "--target", str(self.repo), "--json"], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        nodes = {node["run_id"]: node for node in json.loads(result.stdout)["nodes"]}
        self.assertEqual((nodes["a"]["status"], nodes["b"]["status"]), ("ready", "conflicting"))

    def test_a_run_reserves_the_next_number_after_its_base(self) -> None:
        sys.path.insert(0, str(ROOT))
        import work_graph
        self.graph({"a": ["db/migrations/*"], "b": ["src/**"]})
        contract = work_graph.load_contract(self.repo, ".harness/work-graph.json")
        commit = contract["contract_commit"]
        self.assertEqual(work_graph.sequence_numbers(contract, "a", commit),
                         [{"directory": "db/migrations", "number": "0002"}])
        self.assertEqual(work_graph.sequence_numbers(contract, "b", commit), [])

    def test_a_full_numbered_folder_refuses_the_child_start_by_name(self) -> None:
        (self.repo / "db/migrations/999999_last.sql").write_text("-- full\n", encoding="utf-8")
        self.graph({"a": ["db/migrations/*"]})
        sys.path.insert(0, str(ROOT))
        import work_graph
        contract = work_graph.load_contract(self.repo, ".harness/work-graph.json")
        with self.assertRaisesRegex(work_graph.GraphError, "no free number of up to six digits"):
            work_graph.sequence_numbers(contract, "a", contract["contract_commit"])
        reason = work_graph.child_failure_reason(
            None, 2, "error: numbered folder db/migrations has no free number of up to six digits after 999999")
        self.assertIn("refusal=sequence-exhausted", reason)


if __name__ == "__main__":
    unittest.main()
