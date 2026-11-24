#!/usr/bin/env python3
"""Hidden acceptance tests (opt-in) and rework notes: real runs with fake clients, no network."""

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
    # A probing role: once, it reads the hidden clone the manifest names and echoes what it read.
    plan_path = root / "probe.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else {}
    seen = ""
    if plan.get("role") == ("checker" if checker else "maker"):
        plan_path.unlink()
        manifests = [json.loads(path.read_text(encoding="utf-8")) for path in pathlib.Path(".harness/runs").glob("*.json")]
        clone = pathlib.Path(next(item for item in manifests if "hidden_tests" in item)["hidden_tests"]["repo"])
        seen = "".join(path.name + "\\n" + path.read_text(encoding="utf-8", errors="replace")
                       for path in sorted(clone.rglob("*")) if path.is_file() and ".git" not in path.parts)
        (root / "probe.log").write_text(seen, encoding="utf-8")
        # "names": show only a listing, as a denied read's error message would; else everything read.
        # "none": print nothing, as a role that keeps what it read to itself would.
        if plan.get("show") != "none":
            print("\\n".join(path.name for path in clone.iterdir()) if plan.get("show") == "names" else seen)
        if plan.get("stderr"):
            sys.stderr.write(plan["stderr"] + "\\n")
            sys.exit(plan.get("exit", 1))
    if not checker:
        pathlib.Path("src").mkdir(exist_ok=True)
        if seen and plan.get("commit"):
            pathlib.Path("src/notes.txt").write_text(seen, encoding="utf-8")
        # "revert": commit what it read, then delete it again, so the final diff is clean.
        if seen and plan.get("hide") == "revert":
            pathlib.Path("src/notes.txt").write_text(seen, encoding="utf-8")
            subprocess.run(["git", "add", "src"], check=True)
            subprocess.run(["git", "commit", "-qm", "chore: scratch notes"], check=True)
            pathlib.Path("src/notes.txt").unlink()
        # "ignored": keep what it read in a file the base's .gitignore hides from Git.
        if seen and plan.get("hide") == "ignored":
            pathlib.Path("src/cache.log").write_text(seen, encoding="utf-8")
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
    receipt = {"status": status, "summary": ("VERDICT: " + status.upper() + "\\n## Summary\\n- fixture change\\n- ran the verifier\\n- nothing else"
                          + ("" if checker else "\\n## Assumptions without authority\\n- none")), "commit": commit, "changed_paths": changed,
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
        (self.repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
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


class HiddenRepo(Fixture):
    def hidden_repo(self, expected: str = "fixed", no_marker: bool = False) -> tuple[Path, str]:
        hidden = self.root / "private-hidden-tests"
        hidden.mkdir()
        self.git(hidden, "init", "-q", "-b", "main")
        (hidden / "check.sh").write_text(
            f"# {SECRET}: human-written acceptance check\ngrep -q '^{expected}$' src/change0.txt || exit 1\n"
            + ("" if no_marker else 'echo "AGENTSMITH-HIDDEN-PASS $1"\n'), encoding="utf-8")
        self.git(hidden, "add", ".")
        self.git(hidden, "-c", "user.name=Hidden", "-c", "user.email=user@example.com", "commit", "-qm", "hidden")
        return hidden, self.git(hidden, "rev-parse", "HEAD")

    def hidden(self, hidden: Path, commit: str, tiers=("C",)) -> dict:
        return {"hidden_tests": {"repo": str(hidden), "commit": commit,
                                 "command": ["sh", "{hidden}/check.sh", "{token}"], "tiers": list(tiers)}}

    def proof(self, run_id: str, attempt: int = 1) -> dict:
        return json.loads((self.repo / f".git/agentsmith-runs/{run_id}/attempt-{attempt}-verify.json").read_text(
            encoding="utf-8"))


@unittest.skipUnless(sandbox_available(), "a real run needs the macOS or Linux role sandbox")
class HiddenTestsTests(HiddenRepo):
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

    def test_a_pass_needs_the_hidden_harness_marker_not_just_exit_zero(self) -> None:
        hidden, commit = self.hidden_repo(no_marker=True)
        self.commit_manifest("nomarker", **self.hidden(hidden, commit))
        started = self.controller("start", ".harness/runs/nomarker.json")
        self.assertNotEqual(started.returncode, 0)
        self.assertEqual(self.proof("nomarker")["hidden_tests"]["status"], "fail")

    def test_the_candidate_cannot_contribute_to_the_hidden_suite(self) -> None:
        manifest = self.manifest("x")
        manifest["scope"]["allowed_paths"] = ["src/**", ".agentsmith-hidden-tests/**"]
        base = self.git(self.repo, "rev-parse", "HEAD")
        planted = self.repo / ".agentsmith-hidden-tests"
        planted.mkdir()
        (planted / "test_aaa.py").write_text("import os\nos._exit(0)\n", encoding="utf-8")
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-qm", "candidate plants a hidden-suite file")
        with self.assertRaisesRegex(CONTROLLER.RunError, "protected verification inputs"):
            CONTROLLER.validate_verification_changes(self.repo, base, "HEAD", manifest)
        hidden, commit = self.hidden_repo()
        no_token = {"repo": str(hidden), "commit": commit, "command": ["sh", "{hidden}/check.sh"], "tiers": ["C"]}
        self.assertIn("{token}", CONTROLLER.hidden_tests_problem(self.manifest("x", hidden_tests=no_token), self.repo) or "")

    def test_the_hidden_run_cannot_leave_files_in_shared_temporary_folders(self) -> None:
        # Candidate code that the hidden tests run could copy the suite to /tmp for a later maker.
        drop = Path("/tmp") / f"agentsmith-hidden-drop-{os.getpid()}"
        self.addCleanup(lambda: drop.unlink(missing_ok=True))
        hidden, commit = self.hidden_repo()
        script = (hidden / "check.sh").read_text(encoding="utf-8")
        (hidden / "check.sh").write_text(f"cp \"$0\" {drop} 2>/dev/null\n" + script, encoding="utf-8")
        self.git(hidden, "add", ".")
        self.git(hidden, "-c", "user.name=Hidden", "-c", "user.email=user@example.com", "commit", "-qm", "drop")
        commit = self.git(hidden, "rev-parse", "HEAD")
        self.commit_manifest("drop", **self.hidden(hidden, commit))
        started = self.controller("start", ".harness/runs/drop.json")
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertFalse(drop.exists(), "the hidden run wrote into shared /tmp")
        self.assertEqual(self.proof("drop")["hidden_tests"]["status"], "pass")

    def test_roles_cannot_read_the_hidden_clone(self) -> None:
        hidden = Path("/hidden/clone")
        claude = CONTROLLER.claude_sandbox_settings(self.repo, hidden_read_paths=[hidden])
        self.assertIn(str(hidden), claude["sandbox"]["filesystem"]["denyRead"])
        self.assertIn(f"Read(/{hidden}/**)", claude["permissions"]["deny"])
        codex = CONTROLLER.codex_permissions(self.repo, hidden_read_paths=[hidden])
        self.assertEqual(codex["filesystem"][str(hidden)], "none")

    def test_codex_command_keeps_the_hidden_denial_without_protected_paths(self) -> None:
        # The plain `--sandbox` modes let a role read the whole disk, so a launch that names hidden
        # paths must use the permission profile even when no write path is protected.
        hidden = Path("/hidden/clone")
        command = CONTROLLER.build_native_command(
            "codex", "prompt", self.repo, self.repo / "schema.json", self.repo / "receipt.json",
            hidden_read_paths=[hidden])
        self.assertNotIn("--sandbox", command)
        profile = next(item for item in command if item.startswith("permissions="))
        self.assertIn(f'"{hidden}"="none"', profile)


@unittest.skipUnless(sandbox_available(), "a real run needs the macOS or Linux role sandbox")
class HiddenTestProbeTests(HiddenRepo):
    """A role that reads the hidden clone trips a per-run canary; the controller notices and fails the attempt."""

    def probe(self, role: str, **plan) -> None:
        (self.fake / "probe.json").write_text(json.dumps({"role": role, **plan}), encoding="utf-8")

    def events(self, run_id: str) -> list[dict]:
        path = self.repo / ".git/agentsmith-runs" / run_id / "events.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def canary(self) -> str:
        seen = (self.fake / "probe.log").read_text(encoding="utf-8")
        self.assertIn(SECRET, seen, "the probing role really read the hidden clone")
        # The only file the controller adds to the clone is the tripwire; its content is the canary.
        tracked = {"check.sh"}
        names = [line for line in seen.splitlines() if line and not line.startswith(("#", "grep", "echo"))]
        tripwires = [name for name in names if name not in tracked and name.strip()]
        self.assertTrue(tripwires, "no tripwire was in the hidden clone while the role ran")
        token = seen.split(tripwires[0] + "\n", 1)[1].splitlines()[0].split()[-1]
        self.assertRegex(token, r"^[0-9a-f]{32}$")
        return token

    def assert_nothing_leaked(self, run_id: str, hidden: Path, canary: str) -> None:
        for prompt in self.prompts():
            for secret in (SECRET, canary, str(hidden)):
                self.assertNotIn(secret, prompt)
        for path in (self.repo / ".git/agentsmith-runs" / run_id).rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8", errors="replace")
                self.assertNotIn(SECRET, text, f"hidden content kept in {path.name}")
                self.assertNotIn(canary, text, f"the canary is in {path.name}")
        self.assertEqual(self.git(hidden, "status", "--porcelain", "--untracked-files=all"), "",
                         "the tripwire was left in the hidden clone")

    def test_a_maker_that_shows_the_canary_stops_the_run(self) -> None:
        # It saw held-out content: no rework can make it unsee it, even with nothing committed.
        hidden, commit = self.hidden_repo()
        self.commit_manifest("probe", **self.hidden(hidden, commit))
        self.probe("maker")
        started = self.controller("start", ".harness/runs/probe.json")
        self.assertIn(SECRET, (self.fake / "probe.log").read_text(encoding="utf-8"), "the maker read the clone")
        state = self.state("probe")
        self.assertEqual((state["status"], state["attempt"]), ("escalated", 1), started.stderr)
        self.assertNotEqual(started.returncode, 0)
        self.assertIn("hidden-test-probe", state["reason"])
        probes = [item for item in self.events("probe") if item["event"] == "hidden_test_probe"]
        self.assertEqual([(item["role"], item["attempt"], item["content"]) for item in probes], [("maker", 1, True)])
        self.assertEqual(probes[0]["surfaces"], ["output"])
        self.assertEqual(len([prompt for prompt in self.prompts() if "independent checker" not in prompt]), 1)
        self.assertFalse(any(item["event"] == "infrastructure_failure" for item in self.events("probe")))
        canary = self.canary()
        self.assertNotIn(canary, started.stderr + started.stdout)
        self.assert_nothing_leaked("probe", hidden, canary)

    def test_a_maker_that_commits_what_it_read_stops_the_run(self) -> None:
        hidden, commit = self.hidden_repo()
        self.commit_manifest("committed", **self.hidden(hidden, commit))
        self.probe("maker", commit=True)
        started = self.controller("start", ".harness/runs/committed.json")
        canary = self.canary()
        self.assertNotEqual(started.returncode, 0)
        state = self.state("committed")
        self.assertEqual((state["status"], state["attempt"]), ("escalated", 1))
        self.assertIn("hidden-test-probe", state["reason"])
        self.assertNotIn(canary, started.stderr + started.stdout)
        probes = [item for item in self.events("committed") if item["event"] == "hidden_test_probe"]
        self.assertEqual(len(probes), 1)
        self.assertIn("worktree changes", probes[0]["surfaces"])

    def test_a_maker_that_commits_what_it_read_and_reverts_it_stops_the_run(self) -> None:
        # The final diff is clean, but the token is in the run's history: it was seen all the same.
        hidden, commit = self.hidden_repo()
        self.commit_manifest("reverted", **self.hidden(hidden, commit))
        self.probe("maker", show="none", hide="revert")
        started = self.controller("start", ".harness/runs/reverted.json")
        canary = self.canary()
        self.assertNotEqual(started.returncode, 0)
        state = self.state("reverted")
        self.assertEqual((state["status"], state["attempt"]), ("escalated", 1), started.stderr)
        self.assertIn("hidden-test-probe", state["reason"])
        self.assertNotIn(canary, started.stderr + started.stdout)
        probes = [item for item in self.events("reverted") if item["event"] == "hidden_test_probe"]
        self.assertEqual([(item["role"], item["content"]) for item in probes], [("maker", True)])
        self.assertIn("commit history", probes[0]["surfaces"])

    def test_a_maker_that_hides_what_it_read_in_an_ignored_file_stops_the_run(self) -> None:
        hidden, commit = self.hidden_repo()
        self.commit_manifest("ignored", **self.hidden(hidden, commit))
        self.probe("maker", show="none", hide="ignored")
        started = self.controller("start", ".harness/runs/ignored.json")
        canary = self.canary()
        self.assertNotEqual(started.returncode, 0)
        state = self.state("ignored")
        self.assertEqual((state["status"], state["attempt"]), ("escalated", 1), started.stderr)
        self.assertNotIn(canary, started.stderr + started.stdout)
        probes = [item for item in self.events("ignored") if item["event"] == "hidden_test_probe"]
        self.assertEqual([(item["role"], item["content"]) for item in probes], [("maker", True)])
        self.assertIn("ignored files", probes[0]["surfaces"])

    def test_a_maker_that_only_names_the_tripwire_fails_its_attempt(self) -> None:
        # Only the name reached its output, as from a denied read: nothing was learned, so rework.
        hidden, commit = self.hidden_repo()
        self.commit_manifest("named", **self.hidden(hidden, commit))
        self.probe("maker", show="names")
        started = self.controller("start", ".harness/runs/named.json")
        probes = [item for item in self.events("named") if item["event"] == "hidden_test_probe"]
        self.assertEqual([(item["role"], item["attempt"], item["content"]) for item in probes], [("maker", 1, False)])
        rejected = [item for item in self.events("named") if item["event"] == "attempt_rejected"]
        self.assertEqual(rejected[0].get("reason"), "hidden-test-probe")
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertEqual((self.state("named")["status"], self.state("named")["attempt"]), ("accepted", 2))
        makers = [prompt for prompt in self.prompts() if "independent checker" not in prompt]
        self.assertIn("tried to read the held-out acceptance tests", makers[1])
        self.assertFalse(any(item["event"] == "infrastructure_failure" for item in self.events("named")))
        self.assert_nothing_leaked("named", hidden, self.canary())

    def test_a_checker_probe_is_not_an_infrastructure_failure(self) -> None:
        # The probing checker exits like a network fault; it must not be relaunched as one.
        hidden, commit = self.hidden_repo()
        self.commit_manifest("checkprobe", **self.hidden(hidden, commit))
        self.probe("checker", show="names", stderr="Error: read ECONNRESET", exit=1)
        started = self.controller("start", ".harness/runs/checkprobe.json")
        canary = self.canary()
        events = self.events("checkprobe")
        self.assertFalse(any(item["event"] == "infrastructure_failure" for item in events), started.stderr)
        probes = [item for item in events if item["event"] == "hidden_test_probe"]
        self.assertEqual([(item["role"], item["attempt"]) for item in probes], [("checker", 1)])
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertEqual(self.state("checkprobe")["attempt"], 2)
        self.assertEqual(self.proof("checkprobe", 1)["checker_status"], "not used: hidden-test-probe")
        self.assertFalse((self.repo / ".git/agentsmith-runs/checkprobe/attempt-1-checker-receipt.json").exists())
        self.assert_nothing_leaked("checkprobe", hidden, canary)

    def test_a_checker_that_shows_the_canary_stops_the_run(self) -> None:
        hidden, commit = self.hidden_repo()
        self.commit_manifest("checkseen", **self.hidden(hidden, commit))
        self.probe("checker")
        started = self.controller("start", ".harness/runs/checkseen.json")
        state = self.state("checkseen")
        self.assertEqual((state["status"], state["attempt"]), ("escalated", 1), started.stderr)
        self.assertIn("hidden-test-probe", state["reason"])
        self.assert_nothing_leaked("checkseen", hidden, self.canary())

    def test_a_clean_run_trips_nothing_and_leaves_the_clone_as_it_was(self) -> None:
        hidden, commit = self.hidden_repo()
        self.commit_manifest("clean", **self.hidden(hidden, commit))
        started = self.controller("start", ".harness/runs/clean.json")
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertEqual(self.state("clean")["attempt"], 1)
        self.assertFalse(any(item["event"] == "hidden_test_probe" for item in self.events("clean")))
        self.assertEqual(self.git(hidden, "status", "--porcelain", "--untracked-files=all"), "")


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


class HiddenPolicyTests(Fixture):
    def test_the_macos_policy_for_hidden_runs_grants_no_shared_tmp(self) -> None:
        from unittest import mock
        captured = []

        def capture(args, *_rest):
            captured.append(args)
            return subprocess.CompletedProcess(args, 0, "", "")

        with mock.patch.object(CONTROLLER.sys, "platform", "darwin"), \
                mock.patch.object(CONTROLLER.Path, "exists", return_value=True), \
                mock.patch.object(CONTROLLER, "verifier_process", side_effect=capture):
            CONTROLLER.sandboxed_verify("true", self.repo, 10, CONTROLLER.verifier_env())
            CONTROLLER.sandboxed_verify("true", self.repo, 10, CONTROLLER.verifier_env(), shared_tmp=False)
        shared, private = (args[2] for args in captured)
        self.assertIn('(allow file-write* (subpath "/tmp") (subpath "/private/tmp"))', shared)
        self.assertNotIn('(subpath "/tmp")', private)


class HiddenNamesStayHiddenTests(Fixture):
    def test_a_hidden_entry_that_is_not_a_file_is_refused_without_naming_it(self) -> None:
        clone = self.root / "hidden"
        subprocess.run(["git", "init", "-q", str(clone)], env=self.env, check=True)
        (clone / "run.sh").write_text('echo "AGENTSMITH-HIDDEN-PASS $1"\n', encoding="utf-8")
        (clone / f"{SECRET}-CASE").symlink_to("run.sh")
        self.git(clone, "add", ".")
        self.git(clone, "-c", "user.name=Hidden", "-c", "user.email=user@example.com", "commit", "-qm", "hidden")
        commit = self.git(clone, "rev-parse", "HEAD")
        hidden = {"repo": str(clone), "commit": commit, "command": ["sh", "{hidden}/run.sh", "{token}"], "tiers": ["C"]}
        manifest = self.manifest("x", hidden_tests=hidden)
        problem = CONTROLLER.hidden_tests_problem(manifest, self.repo)
        self.assertIn("not a regular file", problem or "")
        self.assertNotIn(SECRET, problem or "")
        # Should the tree reach a run anyway, the error that lands in run state names nothing hidden.
        base = self.git(self.repo, "rev-parse", "HEAD")
        state = {"worktree": str(self.repo), "base_head": base, "deadline_epoch": __import__("time").time() + 60}
        with self.assertRaises(CONTROLLER.RunError) as raised:
            CONTROLLER.run_hidden_tests(state, {**manifest, "hidden_tests": {**hidden, "tiers": ["human", "C", "B", "A"]}},
                                        base)
        self.assertIn("hidden acceptance tests could not be prepared", str(raised.exception))
        self.assertNotIn(SECRET, str(raised.exception))


class ReworkNoteTests(Fixture):
    NOTE = "Keep the fixed value, but also handle an empty file: the operator saw it fail in review."

    def finished_run(self, run_id: str, status: str, **fields) -> None:
        folder = self.repo / ".git/agentsmith-runs" / run_id
        folder.mkdir(parents=True)
        (folder / "state.json").write_text(json.dumps({"run_id": run_id, "status": status, **fields}),
                                           encoding="utf-8")

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

    @unittest.skipUnless(sandbox_available(), "a real run needs the macOS or Linux role sandbox")
    def test_feedback_on_a_held_run_is_its_own_file_and_starts_a_fresh_attempt_budget(self) -> None:
        # SF-16: the held run spent its whole attempt budget; the operator's feedback starts a new run
        # with a full budget, and that run keeps the feedback in its own folder as its own file.
        self.finished_run("first", "awaiting-human", attempt=2, claude_cost_usd=9.5, codex_tokens_used=900)
        self.write_note()
        self.assertEqual(self.prepare("second", "first").returncode, 0)
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-qm", "test: rework contract")
        started = self.controller("start", ".harness/runs/second.json")
        self.assertEqual(started.returncode, 0, started.stderr)
        run = self.repo / ".git/agentsmith-runs/second"
        state = self.state("second")
        self.assertEqual((state["attempt"], state["claude_cost_usd"] < 1, state["codex_tokens_used"] < 900),
                         (1, True, True), "attempts and spend count from zero, not from the held run")
        kept = run / "operator-feedback.md"
        self.assertEqual(kept.read_text(encoding="utf-8"), self.NOTE + "\n")
        digest = hashlib.sha256(kept.read_bytes()).hexdigest()
        self.assertEqual(state["operator_feedback"], {"of": "first", "file": "operator-feedback.md",
                                                      "note_path": "notes/rework.md", "sha256": digest})
        events = [json.loads(line) for line in (run / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        [kept_event] = [record for record in events if record["event"] == "operator_feedback_kept"]
        self.assertEqual((kept_event["of"], kept_event["sha256"]), ("first", digest))
        self.assertEqual(json.loads((self.repo / ".git/agentsmith-runs/first/state.json").read_text())["attempt"], 2,
                         "the held run is never reopened")

    def test_a_note_must_be_text_without_nul(self) -> None:
        self.finished_run("done", "accepted")
        (self.repo / "notes").mkdir()
        for name, data in (("nul.md", b"fix it\x00 now\n"), ("binary.md", b"\xff\xfe\x00broken")):
            with self.subTest(note=name):
                (self.repo / "notes" / name).write_bytes(data)
                refused = self.prepare("next", "done", note=f"notes/{name}")
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn("must be UTF-8 text without NUL characters", refused.stderr)
                self.assertFalse((self.repo / ".harness/runs/next.json").exists())

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
