#!/usr/bin/env python3
"""`autonomous-run deliver`: real accepted runs with fake clients, a local bare origin, no network."""

from __future__ import annotations

import _fixture_git  # first: keeps every Git fixture out of an inherited repository
_fixture_git.isolate()
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parent.parent
CONTROLLER_PATH = ROOT / "scripts" / "autonomous-run.py"
GOLDEN = ROOT / "tests" / "fixtures" / "deliver"
SPEC = importlib.util.spec_from_file_location("agentsmith_deliver_controller", CONTROLLER_PATH)
assert SPEC and SPEC.loader
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)

FAKE_CLIENT = textwrap.dedent('''\
    import json, pathlib, re, subprocess, sys
    argv = sys.argv[1:]
    prompt = argv[-1]
    receipt_path = pathlib.Path(argv[argv.index("-o") + 1]) if "-o" in argv else None
    checker = "You are the independent checker" in prompt
    if not checker and "Fixture: commit a floor path first" in pathlib.Path("docs/specs/task.md").read_text():
        pathlib.Path("secrets").mkdir(exist_ok=True)
        pathlib.Path("secrets/fixture.txt").write_text("TEST_ONLY_NOT_A_CREDENTIAL\\n", encoding="utf-8")
        subprocess.run(["git", "add", "secrets/fixture.txt"], check=True)
        subprocess.run(["git", "commit", "-qm", "fixture: floor path"], check=True)
        subprocess.run(["git", "rm", "-q", "secrets/fixture.txt"], check=True)
    spec = pathlib.Path("docs/specs/task.md").read_text()
    # Assembled at run time, so this file never holds a secret-shaped literal.
    token = "gh" + "p_" + "Z9y8" * 9
    if not checker and "Fixture: secret added then removed" in spec:
        pathlib.Path("src").mkdir(exist_ok=True)
        pathlib.Path("src/old.txt").write_text("key = '" + token + "'\\n", encoding="utf-8")
        subprocess.run(["git", "add", "src/old.txt"], check=True)
        subprocess.run(["git", "commit", "-qm", "fixture: secret"], check=True)
        subprocess.run(["git", "rm", "-q", "src/old.txt"], check=True)
    if not checker and "Fixture: add dependencies" in spec:
        pathlib.Path("package.json").write_text(json.dumps(
            {"dependencies": {"left-pad": "1.3.0", "leftpad-invented-zz9": "^1.0.0"}}), encoding="utf-8")
        subprocess.run(["git", "add", "package.json"], check=True)
    if not checker:
        pathlib.Path("src").mkdir(exist_ok=True)
        body = "fixed\\n" + ("note = 1\\nauth = '" + token + "'\\n" if "Fixture: seed a secret" in spec else "")
        pathlib.Path("src/change.txt").write_text(body, encoding="utf-8")
        subprocess.run(["git", "add", "src/change.txt"], check=True)
        message = "fix: bounded fixture change"
        if "Fixture: secret in a commit message" in spec:
            message += "\\n\\nused " + token + " to test"
        subprocess.run(["git", "commit", "-qm", message], check=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    log = re.search(r"attempt-[0-9]+-verify[.]txt", prompt)
    evidence = (["fixture verification passed :: " + log.group(0) + " :: fixture verification passed"]
                if checker else ["maker ran the fixture verification"])
    status = "accepted" if checker else "completed"
    receipt = {"status": status, "summary": "Make src/change.txt hold the fixed value; ping @someone",
               "commit": commit, "evidence": evidence,
               "changed_paths": ["src/change.txt"] + (["package.json"] if "Fixture: add dependencies" in spec else []),
               "unresolved": [], "next_state": status}
    if receipt_path is not None:
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 3}}))
    else:
        print(json.dumps({"type": "result", "total_cost_usd": 0.25, "structured_output": receipt}))
''')

# A read-only gh: one pull request whose head is the accepted commit on agentsmith/deliver, one green run.
FAKE_GH = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, pathlib, sys
    args = sys.argv[1:]
    with (pathlib.Path(__file__).parent / "gh.log").open("a", encoding="utf-8") as log:
        log.write(json.dumps(args) + "\\n")
    run = {"id": 101, "name": "verify", "workflow_id": 1, "head_sha": "@SHA@", "head_branch": "agentsmith/deliver",
           "head_repository": {"full_name": "fixture/deliver"}, "status": "completed", "conclusion": "success",
           "event": "pull_request", "run_attempt": 1}
    job = {"id": 201, "name": "test", "status": "completed", "conclusion": "success", "steps": []}
    if args[:2] == ["auth", "status"]:
        print("logged in")
    elif args[:2] == ["repo", "view"]:
        print(json.dumps({"nameWithOwner": "fixture/deliver", "defaultBranchRef": {"name": "main"}}))
    elif args[:2] == ["pr", "view"]:
        print(json.dumps({"headRefOid": "@SHA@", "headRefName": "agentsmith/deliver", "baseRefName": "main",
                          "mergeable": "MERGEABLE", "headRepository": {"nameWithOwner": "fixture/deliver"}}))
    elif args[:1] == ["api"] and "/actions/runs?" in args[-1]:
        print(json.dumps([{"workflow_runs": [run], "total_count": 1}]))
    elif args[:1] == ["api"] and "/jobs?" in args[-1]:
        print(json.dumps([{"jobs": [job], "total_count": 1}]))
    else:
        sys.exit("fake gh refuses: " + " ".join(args))
''')

HEX40 = re.compile(r"\b[0-9a-f]{40}\b")
HEX64 = re.compile(r"\b[0-9a-f]{64}\b")
STAMP = re.compile(r"\b20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9:]{8}\+00:00\b")


def normalized(text: str) -> str:
    return STAMP.sub("<time>", HEX64.sub("<sha256>", HEX40.sub("<commit>", text)))


def sandbox_available() -> bool:
    if sys.platform == "darwin":
        return Path("/usr/bin/sandbox-exec").exists()
    return sys.platform.startswith("linux") and shutil.which("bwrap") is not None


@unittest.skipUnless(sandbox_available(), "a real run needs the macOS or Linux role sandbox")
class DeliverTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="agentsmith deliver ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        fake = self.root / "fake"
        (fake / "codex-home").mkdir(parents=True)
        (fake / "codex-home/auth.json").write_text('{"auth_mode":"chatgpt"}', encoding="utf-8")
        (fake / "agent.py").write_text(FAKE_CLIENT, encoding="utf-8")
        self.env.update(AGENTSMITH_CODEX_BIN=str(fake / "agent.py"), AGENTSMITH_CLAUDE_BIN=str(fake / "agent.py"),
                        CODEX_HOME=str(fake / "codex-home"))

    def git(self, repo: Path, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=repo, env=self.env, text=True, capture_output=True,
                              check=True).stdout.strip()

    def calibrate(self, repo: Path) -> None:
        """A passed calibration of the fixture checker, as `calibrate` writes it."""
        checker = {"runtime": "claude", "model": "fixture-model", "effort": "high"}
        cases = [{"label": "clean", "expected": "accepted", "verdict": "accepted", "correct": True},
                 {"label": "defect", "expected": "rejected", "verdict": "rejected", "correct": True}]
        CONTROLLER.write_json(CONTROLLER.calibration_path(repo, "claude", "fixture-model", "high"),
                              CONTROLLER.calibration_record(checker, cases, client_version="fixture",
                                                            usage={"claude_cost_usd": 0.0, "codex_tokens_used": 0}))

    def uncalibrate(self, repo: Path) -> None:
        CONTROLLER.calibration_path(repo, "claude", "fixture-model", "high").unlink()

    def accepted_run(self, *, policy_tier: str = "B", declared: str | None = None, run_id: str = "deliver",
                     spec_note: str = "", allowed_paths: tuple[str, ...] = ("src/**",),
                     verify: str = "test -f src/change.txt", calibrated: bool = True) -> Path:
        origin = self.root / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], env=self.env, check=True)
        repo = self.root / "repo"
        repo.mkdir()
        self.git(repo, "init", "-q", "-b", "main")
        self.git(repo, "config", "user.name", "Harness Test")
        self.git(repo, "config", "user.email", "user@example.com")
        (repo / "docs/specs").mkdir(parents=True)
        (repo / "docs/specs/task.md").write_text(
            "---\nstatus: accepted\ndecision_ticket: DEC-1\naccepted_by: Test Operator\n"
            "accepted_at: 2026-11-06\n---\n# Spec\nMake src/change.txt hold the fixed value.\n" + spec_note,
            encoding="utf-8")
        (repo / "README.md").write_text("fixture\n", encoding="utf-8")
        (repo / ".harness").mkdir()
        (repo / ".harness/risk-policy.json").write_text(json.dumps(
            {"schema_version": 1, "rules": [{"paths": ["src/**"], "tier": policy_tier, "lenses": ["code"]}]}),
            encoding="utf-8")
        manifest = json.loads((ROOT / "templates/autonomous-run.json").read_text(encoding="utf-8"))
        manifest.update(run_id=run_id, spec_path="docs/specs/task.md", implementation_ticket="IMP-7")
        for role in manifest["roles"].values():
            role["model"] = "fixture-model"
        manifest["scope"]["allowed_paths"] = list(allowed_paths)
        manifest["verify"]["command"] = verify + ' && echo "fixture verification passed for src/change.txt"'
        manifest["limits"].update(max_attempts=3, wall_minutes=5,
                                  budget_rationale="size S fixture; set by Test Operator")
        if declared:
            manifest["risk_tier"] = declared
        (repo / ".harness/runs").mkdir()
        (repo / f".harness/runs/{run_id}.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-qm", "test: accepted contract")
        self.git(repo, "remote", "add", "origin", str(origin))
        self.git(repo, "push", "-q", "origin", "main")
        self.git(repo, "fetch", "-q", "origin")
        self.git(repo, "remote", "set-head", "origin", "main")
        if calibrated:
            self.calibrate(repo)
        started = subprocess.run([sys.executable, str(CONTROLLER_PATH), "start", f".harness/runs/{run_id}.json"],
                                 cwd=repo, env=self.env, text=True, capture_output=True, check=False)
        # Without a passed calibration the checker is advisory: its acceptance waits for a human.
        self.assertEqual(started.returncode, 0 if calibrated else 3, started.stdout + started.stderr)
        return repo

    def deliver(self, repo: Path, *args: str, run_id: str = "deliver") -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(CONTROLLER_PATH), "deliver", run_id, *args],
                              cwd=repo, env=self.env, text=True, capture_output=True, check=False)

    def state(self, repo: Path, run_id: str = "deliver") -> dict:
        return json.loads((repo / ".git/agentsmith-runs" / run_id / "state.json").read_text(encoding="utf-8"))

    def refused(self, repo: Path, reason: str, *args: str) -> None:
        result = self.deliver(repo, "--dry-run", *args)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("deliver refused", result.stderr)
        self.assertIn(reason, result.stderr)
        self.assertNotIn("git push", result.stdout)

    def assert_golden(self, text: str, name: str) -> None:
        if os.environ.get("AGENTSMITH_WRITE_GOLDEN") == "1":  # review the diff before committing
            (GOLDEN / name).write_text(normalized(text), encoding="utf-8")
        expected = (GOLDEN / name).read_text(encoding="utf-8")
        self.assertEqual(normalized(text), expected)

    # --- a ready delivery ----------------------------------------------------------------------

    def test_dry_run_prints_the_push_command_and_a_body_built_from_receipts(self) -> None:
        repo = self.accepted_run()
        accepted = self.state(repo)["accepted_commit"]
        # The calibration is gone since the acceptance: the body says the checker is now advisory.
        self.uncalibrate(repo)
        result = self.deliver(repo, "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["push_command"], f"git push origin {accepted}:refs/heads/agentsmith/deliver")
        self.assertEqual(report["head"], accepted)
        self.assertEqual(report["staleness"], {"base": "origin/main", "behind": 0, "applies": True})
        self.assertEqual(report["tier"]["tier"], "B")
        self.assertFalse(report["eligibility"]["eligible"])
        self.assertIn("checker advisory", report["body"])
        self.assert_golden(report["body"], "eligible-no.md")
        self.assertNotIn(str(self.root), result.stdout, "the body must not name a local path")
        # The text form shows the same body and the exact push command.
        text = self.deliver(repo, "--dry-run")
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn(f"git push origin {accepted}:refs/heads/agentsmith/deliver", text.stdout)
        self.assertIn(report["body"], text.stdout)

    def pushed_and_calibrated(self) -> tuple[Path, str]:
        """An A-tier accepted run, calibrated, pushed to a remote that reads as github.com/fixture/deliver."""
        repo = self.accepted_run(policy_tier="A")
        accepted = self.state(repo)["accepted_commit"]
        # Git rewrites the GitHub address to the local bare origin, so nothing reaches the network.
        self.git(repo, "config", f"url.{self.root / 'origin.git'}.insteadOf", "https://github.com/fixture/deliver.git")
        self.git(repo, "remote", "set-url", "origin", "https://github.com/fixture/deliver.git")
        self.git(repo, "push", "-q", "origin", f"{accepted}:refs/heads/agentsmith/deliver")
        return repo, accepted

    def ci_report(self, accepted: str, name: str, **fields: object) -> str:
        report = {"state": "green", "sha": accepted, "repo": "fixture/deliver", "branch": "agentsmith/deliver",
                  "pr": 7, "exit_code": 0, **fields}
        path = self.root / f"ci-{name}.json"
        path.write_text(json.dumps({key: value for key, value in report.items() if value is not None}),
                        encoding="utf-8")
        return str(path)

    def eligibility_line(self, repo: Path, *args: str) -> str:
        result = self.deliver(repo, "--eligibility", *args, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["eligibility"]["line"]

    def test_eligibility_after_ci_is_yes_only_when_every_fact_is_met(self) -> None:
        repo, accepted = self.pushed_and_calibrated()
        result = self.deliver(repo, "--eligibility", "--sha", accepted, "--ci-report",
                              self.ci_report(accepted, "green"), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["eligibility"]["eligible"], report["eligibility"])
        self.assertNotIn("checker advisory", report["body"])
        self.assert_golden(report["body"], "eligible-yes.md")
        # Before CI the same run is "pending CI", so not eligible yet.
        pending = json.loads(self.deliver(repo, "--dry-run", "--json").stdout)
        self.assertFalse(pending["eligibility"]["eligible"])
        self.assertIn("CI green for this commit: pending CI", pending["eligibility"]["line"])
        for state in ("red-at-diff", "flaky"):
            with self.subTest(ci=state):
                line = self.eligibility_line(repo, "--sha", accepted, "--ci-report",
                                             self.ci_report(accepted, state, state=state))
                self.assertIn("Auto-merge eligible: no", line)
                self.assertIn(f"CI green for this commit: unmet ({state})", line)
        # A report about another commit, or a SHA that is not the accepted commit, is not CI for this head.
        line = self.eligibility_line(repo, "--sha", accepted, "--ci-report", self.ci_report(accepted, "other", sha="f" * 40))
        self.assertIn("CI green for this commit: unmet (the report is for ffffffffffff)", line)
        line = self.eligibility_line(repo, "--sha", "e" * 40, "--ci-report", self.ci_report(accepted, "green"))
        self.assertIn("Auto-merge eligible: no", line)
        self.assertIn("head equals the accepted commit: unmet", line)

    def test_eligibility_needs_ci_for_this_branch_and_repository(self) -> None:
        repo, accepted = self.pushed_and_calibrated()
        for name, fields, detail in (
                ("foreign-repo", {"repo": "unrelated/other"}, "the report is for repository unrelated/other"),
                ("other-branch", {"branch": "unrelated-branch"}, "the report is for branch unrelated-branch"),
                ("saved-without-fields", {"repo": None, "branch": None}, "the report does not name its repo")):
            with self.subTest(report=name):
                line = self.eligibility_line(repo, "--sha", accepted, "--ci-report", self.ci_report(accepted, name, **fields))
                self.assertIn("Auto-merge eligible: no", line)
                self.assertIn(f"CI green for this commit: unmet ({detail}", line)

    def test_eligibility_needs_the_remote_branch_at_the_accepted_commit(self) -> None:
        repo, accepted = self.pushed_and_calibrated()
        clone = self.root / "other"
        subprocess.run(["git", "clone", "-q", str(self.root / "origin.git"), str(clone)], env=self.env, check=True)
        self.git(clone, "-c", "user.name=Other", "-c", "user.email=user@example.com", "commit", "-q",
                 "--allow-empty", "-m", "force-pushed head")
        self.git(clone, "push", "-q", "--force", "origin", "HEAD:refs/heads/agentsmith/deliver")
        moved = self.git(clone, "rev-parse", "HEAD")
        line = self.eligibility_line(repo, "--sha", accepted, "--ci-report", self.ci_report(accepted, "green"))
        self.assertIn("Auto-merge eligible: no", line)
        self.assertIn(f"head equals the accepted commit: unmet (origin/agentsmith/deliver is at {moved[:12]})", line)

    def test_eligibility_reads_ci_for_the_pull_request_through_gh(self) -> None:
        repo, accepted = self.pushed_and_calibrated()
        fake = self.root / "bin"
        fake.mkdir()
        (fake / "gh").write_text(FAKE_GH.replace("@SHA@", accepted), encoding="utf-8")
        (fake / "gh").chmod(0o755)
        env = {**self.env, "PATH": f"{fake}{os.pathsep}{self.env['PATH']}"}

        def eligibility(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run([sys.executable, str(CONTROLLER_PATH), "deliver", "deliver", "--eligibility", "--sha",
                                   accepted, *args, "--json"], cwd=repo, env=env, text=True, capture_output=True)

        refused = eligibility()
        self.assertEqual(refused.returncode, 2)
        self.assertIn("--eligibility needs --pr <number> or --ci-report", refused.stderr)
        result = eligibility("--pr", "7")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["eligibility"]["eligible"], result.stdout)
        calls = [json.loads(line) for line in (fake / "gh.log").read_text(encoding="utf-8").splitlines()]
        self.assertIn(["pr", "view", "7", "--repo", "fixture/deliver"], [call[:5] for call in calls])
        self.assertFalse([call for call in calls if call[:2] in (["pr", "create"], ["pr", "merge"])])

    def test_each_eligibility_fact_is_listed_met_or_unmet(self) -> None:
        repo = self.accepted_run(policy_tier="B")
        self.uncalibrate(repo)
        line = json.loads(self.deliver(repo, "--dry-run", "--json").stdout)["eligibility"]["line"]
        accepted = self.state(repo)["accepted_commit"]
        self.assertTrue(line.startswith(f"Auto-merge eligible: no for {accepted} — "), line)
        for fact in ("tier A: unmet (B)", "no floor path: met", "checker accepted with valid citations: met",
                     "passing calibration for this checker: unmet (none)",
                     "head equals the accepted commit: met", "CI green for this commit: pending CI"):
            self.assertIn(fact, line)

    def test_the_tier_is_recomputed_and_can_only_rise(self) -> None:
        repo = self.accepted_run(policy_tier="C")
        path = repo / ".git/agentsmith-runs/deliver/state.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["risk"]["tier"] = "A"  # a record that claims less than the policy gives
        path.write_text(json.dumps(state), encoding="utf-8")
        tier = json.loads(self.deliver(repo, "--dry-run", "--json").stdout)["tier"]
        self.assertEqual((tier["recorded"], tier["recomputed"], tier["tier"]), ("A", "C", "C"))

    def move_base(self, name: str, text: str) -> str:
        """Another clone pushes one commit to origin/main, and the run's repository fetches it."""
        clone = self.root / "other"
        subprocess.run(["git", "clone", "-q", str(self.root / "origin.git"), str(clone)], env=self.env, check=True)
        (clone / name).write_text(text, encoding="utf-8")
        self.git(clone, "add", name)
        self.git(clone, "-c", "user.name=Other", "-c", "user.email=user@example.com", "commit", "-qm", "base moves")
        self.git(clone, "push", "-q", "origin", "main")
        self.git(self.root / "repo", "fetch", "-q", "origin")
        return self.git(clone, "rev-parse", "HEAD")

    def git_footprint(self, repo: Path) -> tuple[str, str]:
        return self.git(repo, "worktree", "list", "--porcelain"), self.git(repo, "count-objects", "-v")

    def test_staleness_counts_commits_behind_the_base(self) -> None:
        repo = self.accepted_run()
        moved = self.move_base("README.md", "moved on\n")
        before = self.git_footprint(repo)
        report = json.loads(self.deliver(repo, "--dry-run", "--json").stdout)
        self.assertEqual(report["staleness"], {"base": "origin/main", "behind": 1, "applies": True})
        self.assertIn("1 commit behind origin/main", report["body"])
        # Behind the base, the merge result itself is verified, and the receipt says so.
        merge = report["merge_verification"]
        self.assertEqual((merge["base_commit"], merge["verification"], merge["exit_code"]), (moved, "passed", 0))
        self.assertRegex(merge["output_sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("The merge with origin/main passed verification (exit 0", report["body"])
        self.assertEqual(self.git_footprint(repo), before, "deliver adds no worktree and no object to the repository")

    def test_a_merge_result_that_fails_verification_refuses(self) -> None:
        # The accepted diff applies cleanly, and each side passes on its own; only the merge fails.
        repo = self.accepted_run(verify="test -f src/change.txt && test ! -f BREAKS_MERGE")
        self.move_base("BREAKS_MERGE", "a base change that the accepted commit never saw\n")
        before = self.git_footprint(repo)
        self.refused(repo, "the accepted commit merged with origin/main fails verification (failed, exit 1)")
        self.assertEqual(self.git_footprint(repo), before)

    def test_no_merge_is_verified_when_the_accepted_commit_is_on_the_base(self) -> None:
        repo = self.accepted_run()
        report = json.loads(self.deliver(repo, "--dry-run", "--json").stdout)
        self.assertEqual(report["merge_verification"], {"needed": False})

    def add_evidence(self, repo: Path, *items: str) -> None:
        """Extra checker evidence that quotes no log, so only its hash binds it, as at acceptance."""
        run_dir = repo / ".git/agentsmith-runs/deliver"
        receipt = run_dir / "attempt-1-checker-receipt.json"
        value = json.loads(receipt.read_text(encoding="utf-8"))
        value["evidence"] += list(items)
        receipt.write_text(json.dumps(value), encoding="utf-8")
        proof_path = Path(self.state(repo)["verification_receipt"])
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        proof["checker_receipt_sha256"] = hashlib.sha256(receipt.read_bytes()).hexdigest()
        proof_path.write_text(json.dumps(proof), encoding="utf-8")

    def test_the_pull_request_text_names_no_local_path_and_no_model_summary(self) -> None:
        repo = self.accepted_run()
        # Split so that the leak gate, which scans this file, does not read them as real home folders.
        mac_home, linux_home = "/Users/" + "alice", "/home/" + "alice"
        path = repo / ".git/agentsmith-runs/deliver/state.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["maker_receipt"]["summary"] = f"see {mac_home}/private/strategy.md @alice private-doc:BOARD-42"
        path.write_text(json.dumps(state), encoding="utf-8")
        self.add_evidence(repo, f"edited :: {repo}/src/change.txt", f"notes in {linux_home}/notes.md")
        result = self.deliver(repo, "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        text = report["title"] + "\n" + report["body"]
        for private in (mac_home, linux_home, "@alice", "private-doc:BOARD-42", "strategy.md"):
            self.assertNotIn(private, text)
        self.assertIn("edited :: src/change.txt", report["body"])
        self.assertIn("notes in ~/notes.md", report["body"])
        self.assertIn("- src/change.txt", report["body"], "the body lists the changed paths Git reports")
        self.assertNotIn(str(self.root), result.stdout, "neither the text nor the JSON names a local path")

    def test_refuses_pull_request_text_that_holds_a_likely_secret(self) -> None:
        repo = self.accepted_run()
        self.add_evidence(repo, "token seen: " + "gh" + "p_" + "A1b2" * 9)
        self.refused(repo, "the pull-request body holds a likely secret (GitHub token)")

    def test_the_tier_counts_every_commit_that_the_push_publishes(self) -> None:
        # The scope check reads every commit, so the floor path must be in scope for the run to be
        # accepted at all; the tier must still count it although the final tree no longer has it.
        repo = self.accepted_run(policy_tier="A", spec_note="Fixture: commit a floor path first.\n",
                                 allowed_paths=("src/**", "secrets/**"))
        state = self.state(repo)
        history = self.git(repo, "rev-list", "--count", f"{state['base_head']}..{state['accepted_commit']}")
        self.assertEqual(history, "2", "the maker committed a floor path, then removed it")
        report = json.loads(self.deliver(repo, "--dry-run", "--json").stdout)
        self.assertEqual((report["tier"]["tier"], report["tier"]["floor_paths"]), ("human", ["secrets/fixture.txt"]))
        self.assertIn("no floor path: unmet (secrets/fixture.txt)", report["eligibility"]["line"])

    # --- refusals ----------------------------------------------------------------------------

    def test_a_secret_in_the_accepted_diff_blocks_a_dry_run(self) -> None:
        repo = self.accepted_run(spec_note="Fixture: seed a secret.\n")
        result = self.deliver(repo, "--dry-run", "--json")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("deliver refused: the accepted diff holds a likely secret at src/change.txt:3 (GitHub token)",
                      result.stderr)
        self.assertNotIn("Z9y8", result.stdout + result.stderr, "the report names the line, never the value")
        self.assertNotIn("git push", result.stdout)
        # An allow rule in the operator's checkout covers a genuine inert fixture, as for secret-scan.
        (repo / ".harness/secret-scan.allow").write_text("^auth = 'ghp_Z9y8\n", encoding="utf-8")
        self.assertEqual(self.deliver(repo, "--dry-run").returncode, 0)

    def test_an_invented_package_refuses_the_landing(self) -> None:
        repo = self.accepted_run(spec_note="Fixture: add dependencies.\n", allowed_paths=("src/**", "package.json"))
        asked: list[str] = []

        def registry(found: set[str]):
            def fetch(url: str) -> int:
                asked.append(url)
                return 200 if any(url.endswith("/" + name) for name in found) else 404
            return fetch

        state = CONTROLLER.load_run(repo, "deliver")
        with self.assertRaises(CONTROLLER.RunError) as refused:
            CONTROLLER.delivery_checks(repo, state, "origin", None, fetch=registry({"left-pad"}))
        self.assertIn("package.json adds npm package leftpad-invented-zz9, which registry.npmjs.org does not have",
                      str(refused.exception))
        self.assertNotIn("left-pad,", str(refused.exception))
        self.assertEqual(sorted(asked), ["https://registry.npmjs.org/left-pad",
                                         "https://registry.npmjs.org/leftpad-invented-zz9"])
        checks = CONTROLLER.delivery_checks(repo, state, "origin", None,
                                            fetch=registry({"left-pad", "leftpad-invented-zz9"}))
        self.assertEqual([(row["name"], row["status"]) for row in checks["packages"]],
                         [("left-pad", "exists"), ("leftpad-invented-zz9", "exists")])
        self.assertEqual(checks["tier"]["recomputed"], "human", "package.json matches no rule of this policy")
        body = CONTROLLER.delivery_body(checks, CONTROLLER.eligibility(checks, checks["accepted"], None))
        self.assertIn("### Dependencies\nNew packages and their registry lookup (local ones are not looked up):\n"
                      "```text\n- left-pad (npm, exists)\n- leftpad-invented-zz9 (npm, exists)\n```", body)

    def test_a_secret_that_a_later_commit_removes_still_blocks(self) -> None:
        repo = self.accepted_run(spec_note="Fixture: secret added then removed.\n")
        state = self.state(repo)
        first = self.git(repo, "rev-list", "--reverse", f"{state['base_head']}..{state['accepted_commit']}").split()[0]
        self.refused(repo, f"commit {first[:12]} adds a likely secret at src/old.txt:1 (GitHub token), "
                           "which a later commit removes but the push still publishes")

    def test_a_secret_in_a_commit_message_blocks_a_dry_run(self) -> None:
        repo = self.accepted_run(spec_note="Fixture: secret in a commit message.\n")
        accepted = self.state(repo)["accepted_commit"]
        result = self.deliver(repo, "--dry-run")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(f"the message of commit {accepted[:12]} holds a likely secret at line 3 (GitHub token)",
                      result.stderr)
        self.assertNotIn("Z9y8", result.stdout + result.stderr)


    def test_deliver_never_pushes(self) -> None:
        repo = self.accepted_run()
        result = self.deliver(repo)
        self.assertEqual(result.returncode, 2)
        self.assertIn("the controller never pushes", result.stderr)

    def test_refuses_a_run_that_was_not_accepted(self) -> None:
        repo = self.accepted_run()
        path = repo / ".git/agentsmith-runs/deliver/state.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["status"] = "escalated"
        path.write_text(json.dumps(state), encoding="utf-8")
        self.refused(repo, "run deliver is escalated, not accepted")

    def test_an_uncalibrated_checker_holds_the_run_and_deliver_refuses_it(self) -> None:
        # SF-09: a real run with no calibration record ends awaiting-human, never accepted. Its
        # receipt says the checker was advisory, and deliver names the step a human takes.
        repo = self.accepted_run(calibrated=False)
        state = self.state(repo)
        self.assertEqual(state["status"], "awaiting-human")
        self.assertNotIn("accepted_commit", state)
        self.assertEqual(state["held_commit"], self.git(repo, "rev-parse", "agentsmith/deliver"))
        proof = json.loads(Path(state["verification_receipt"]).read_text(encoding="utf-8"))
        self.assertIs(proof["checker_advisory"], True)
        self.assertEqual(proof["checker_calibration"], {"status": "none"})
        self.refused(repo, "run deliver is awaiting-human, not accepted")
        result = self.deliver(repo, "--dry-run")
        self.assertIn("checker advisory", result.stderr)
        self.assertIn("a human reviews and re-runs with an explicit approval", result.stderr)

    def test_refuses_when_the_branch_moved(self) -> None:
        repo = self.accepted_run()
        worktree = Path(self.state(repo)["worktree"])
        self.git(worktree, "commit", "-q", "--allow-empty", "-m", "unverified")
        self.refused(repo, "branch agentsmith/deliver is at")

    def test_refuses_when_the_proof_names_another_commit(self) -> None:
        repo = self.accepted_run()
        proof_path = Path(self.state(repo)["verification_receipt"])
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        proof["candidate_commit"] = "d" * 40
        proof_path.write_text(json.dumps(proof), encoding="utf-8")
        self.refused(repo, "verification receipt names dddddddddddd")

    def test_refuses_when_the_checker_receipt_changed(self) -> None:
        repo = self.accepted_run()
        receipt = repo / ".git/agentsmith-runs/deliver/attempt-1-checker-receipt.json"
        value = json.loads(receipt.read_text(encoding="utf-8"))
        value["summary"] = "edited after acceptance"
        receipt.write_text(json.dumps(value), encoding="utf-8")
        self.refused(repo, "checker receipt no longer matches its recorded hash")

    def test_refuses_when_the_manifest_changed(self) -> None:
        repo = self.accepted_run()
        path = repo / ".harness/runs/deliver.json"
        path.write_text(path.read_text(encoding="utf-8").replace("IMP-7", "IMP-8"), encoding="utf-8")
        self.refused(repo, "manifest changed since the run started")

    def test_refuses_when_the_verifier_evidence_changed(self) -> None:
        repo = self.accepted_run()
        log = repo / ".git/agentsmith-runs/deliver/attempt-1-verify.txt"
        log.write_text(log.read_text(encoding="utf-8") + "appended later\n", encoding="utf-8")
        self.refused(repo, "attempt-1-verify.txt changed after the verifier finished")

    def test_refuses_an_acceptance_whose_citations_were_never_checked(self) -> None:
        repo = self.accepted_run()
        proof_path = Path(self.state(repo)["verification_receipt"])
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        proof.pop("citations")
        proof_path.write_text(json.dumps(proof), encoding="utf-8")
        self.refused(repo, "the verification receipt does not record checked citations")

    def test_refuses_a_remote_or_branch_name_that_a_shell_would_run(self) -> None:
        repo = self.accepted_run()
        # Git accepts both names; printed into a push command, each would run printf.
        remote = "origin;printf${IFS}INJECTED;#"
        self.git(repo, "remote", "add", remote, str(self.root / "origin.git"))
        self.git(repo, "fetch", "-q", remote)
        self.git(repo, "remote", "set-head", remote, "main")
        self.refused(repo, "is not a safe remote name", "--remote", remote)
        self.refused(repo, "is not a safe branch name", "--base-branch", "main;id")
        branch = "agentsmith/deliver;printf${IFS}INJECTED"
        self.git(repo, "update-ref", f"refs/heads/{branch}", self.state(repo)["accepted_commit"])
        path = repo / ".git/agentsmith-runs/deliver/state.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["branch"] = branch
        path.write_text(json.dumps(state), encoding="utf-8")
        self.refused(repo, "is not a safe branch name")

    def test_refuses_when_the_base_branch_is_unknown(self) -> None:
        repo = self.accepted_run()
        self.refused(repo, "refs/remotes/origin/release is missing", "--base-branch", "release")

    def test_refuses_a_base_that_was_not_fetched_since_the_remote_moved(self) -> None:
        repo = self.accepted_run()
        clone = self.root / "other"
        subprocess.run(["git", "clone", "-q", str(self.root / "origin.git"), str(clone)], env=self.env, check=True)
        (clone / "src").mkdir()
        (clone / "src/change.txt").write_text("conflicting value\n", encoding="utf-8")
        self.git(clone, "add", ".")
        self.git(clone, "-c", "user.name=Other", "-c", "user.email=user@example.com", "commit", "-qm", "conflict")
        self.git(clone, "push", "-q", "origin", "main")
        # The cached origin/main still predates the conflict, so it would read as applying cleanly.
        self.refused(repo, "base not fresh: origin has main at")
        self.assertIn("run git fetch origin", self.deliver(repo, "--dry-run").stderr)

    def test_refuses_when_the_remote_cannot_be_reached(self) -> None:
        repo = self.accepted_run()
        self.git(repo, "remote", "set-url", "origin", str(self.root / "missing.git"))
        self.refused(repo, "cannot reach origin")

    def test_refuses_when_the_accepted_diff_no_longer_applies(self) -> None:
        repo = self.accepted_run()
        clone = self.root / "other"
        subprocess.run(["git", "clone", "-q", str(self.root / "origin.git"), str(clone)], env=self.env, check=True)
        (clone / "src").mkdir()
        (clone / "src/change.txt").write_text("conflicting value\n", encoding="utf-8")
        self.git(clone, "add", ".")
        self.git(clone, "-c", "user.name=Other", "-c", "user.email=user@example.com", "commit", "-qm", "conflict")
        self.git(clone, "push", "-q", "origin", "main")
        self.git(repo, "fetch", "-q", "origin")
        self.refused(repo, "the accepted diff does not apply to origin/main")


class PackageExistenceTests(unittest.TestCase):
    """New packages in a manifest are looked up in their registry, read-only; the fetcher is injected."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="agentsmith packages ")
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.git("init", "-q", "-b", "main")
        self.base = self.commit({
            "package.json": json.dumps({"dependencies": {"left-pad": "1.3.0"}}),
            "requirements.txt": "requests==2.32.0\n",
            "pyproject.toml": '[project]\nname = "x"\ndependencies = ["attrs>=23"]\n'})

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.com", "-c",
                               "commit.gpgsign=false", *args], cwd=self.repo, env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, files: dict[str, str]) -> str:
        for name, text in files.items():
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text(text, encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "change")
        return self.git("rev-parse", "HEAD")

    def check(self, head: str, answers: dict[str, object]) -> tuple[list[dict], list[str]]:
        def fetch(url: str) -> int:
            answer = answers.get(url, 404)
            if isinstance(answer, Exception):
                raise answer
            return int(answer)  # type: ignore[call-overload]
        return CONTROLLER.package_checks(self.repo, self.base, head, fetch)

    def test_new_packages_are_looked_up_and_an_invented_one_refuses(self) -> None:
        head = self.commit({
            "package.json": json.dumps({"dependencies": {"left-pad": "1.3.0", "@types/node": "^20"},
                                        "devDependencies": {"invented-js-zz9": "1.0.0", "aliased": "npm:chalk@5",
                                                            "local": "file:../local", "ws": "workspace:*"}}),
            "requirements.txt": "requests==2.32.0\n# a comment\n-r other.txt\nFlask[async]>=2.0 ; python_version > '3.8'\n"
                                "invented_py.zz9==1\n",
            "other.txt": "rich\n",
            "pyproject.toml": '[project]\nname = "x"\ndependencies = ["attrs>=23", "rich"]\n'
                              '[project.optional-dependencies]\ndev = ["pytest>=8"]\n'})
        rows, problems = self.check(head, {
            "https://registry.npmjs.org/@types%2Fnode": 200, "https://registry.npmjs.org/chalk": 200,
            "https://pypi.org/pypi/flask/json": 200, "https://pypi.org/pypi/rich/json": 200,
            "https://pypi.org/pypi/pytest/json": 200})
        self.assertEqual(sorted((row["manifest"], row["ecosystem"], row["name"], row["status"]) for row in rows), [
            ("other.txt", "pypi", "rich", "exists"),
            ("package.json", "npm", "@types/node", "exists"), ("package.json", "npm", "aliased", "exists"),
            ("package.json", "npm", "invented-js-zz9", "missing"),
            ("package.json", "npm", "local", "local"), ("package.json", "npm", "ws", "local"),
            ("pyproject.toml", "pypi", "pytest", "exists"), ("pyproject.toml", "pypi", "rich", "exists"),
            ("requirements.txt", "pypi", "flask", "exists"), ("requirements.txt", "pypi", "invented-py-zz9", "missing")])
        self.assertEqual(problems, [
            "package.json adds npm package invented-js-zz9, which registry.npmjs.org does not have",
            "requirements.txt adds PyPI package invented-py-zz9, which pypi.org does not have"])

    def test_a_package_that_cannot_be_checked_is_unverified_and_refuses(self) -> None:
        head = self.commit({
            "requirements.txt": "requests==2.32.0\nslowpkg\ngit+https://example.com/x.git#egg=x\n",
            "services/go.mod": "module example.com/x\n\nrequire example.com/y v1.0.0\n",
            "package.json": "{not json"})
        rows, problems = self.check(head, {"https://pypi.org/pypi/slowpkg/json": OSError("timed out")})
        statuses = {(row["manifest"], row["name"]): row["status"] for row in rows}
        self.assertEqual(statuses[("requirements.txt", "slowpkg")], "unverified")
        self.assertEqual(problems, [
            "cannot read package.json to check its new packages (Expecting property name enclosed in double "
            "quotes: line 1 column 2 (char 1)); the landing stays refused until it parses",
            "cannot check requirements.txt line 3 (git+https://example.com/x.git#egg=x): only registry "
            "packages can be checked",
            "cannot check PyPI package slowpkg from requirements.txt: pypi.org did not answer (timed out); "
            "retry when it answers",
            "services/go.mod changed, and deliver cannot check go packages against a registry; "
            "review the new requirements by hand"])
        self.assertTrue(all(row["status"] != "exists" for row in rows if row["name"] in {"slowpkg"}))

    def test_a_requirements_option_that_leaves_the_registry_is_unverified(self) -> None:
        head = self.commit({"requirements.txt": "requests==2.32.0\n--extra-index-url https://example.com/simple\n"
                                                "-e ./vendored\n-c constraints.txt\n"})
        _, problems = self.check(head, {})
        self.assertEqual(problems, [
            "cannot check requirements.txt line 2 (--extra-index-url https://example.com/simple): only registry "
            "packages can be checked",
            "cannot check requirements.txt line 3 (-e ./vendored): only registry packages can be checked",
            "cannot check requirements.txt line 4 (-c constraints.txt): the included file is not in the repository"])

    def test_an_unchanged_or_removed_dependency_needs_no_lookup(self) -> None:
        head = self.commit({"package.json": json.dumps({"dependencies": {}}), "README.md": "x\n"})

        def fetch(url: str) -> int:
            raise AssertionError(f"no lookup expected, got {url}")
        self.assertEqual(CONTROLLER.package_checks(self.repo, self.base, head, fetch), ([], []))

    # --- requirements files: includes, continuations, comments, markers --------------------------

    def test_an_included_requirements_file_is_read_and_its_new_packages_are_looked_up(self) -> None:
        head = self.commit({"requirements.txt": "requests==2.32.0\n-r deps.txt\n",
                            "deps.txt": "imaginary-sf13-unpublished==1\n--requirement=sub/more.txt\n",
                            "sub/more.txt": "-c ../deps.txt\nrich\n"})  # a cycle back to deps.txt ends
        rows, problems = self.check(head, {"https://pypi.org/pypi/rich/json": 200})
        self.assertEqual(sorted((row["manifest"], row["name"], row["status"]) for row in rows), [
            ("deps.txt", "imaginary-sf13-unpublished", "missing"), ("sub/more.txt", "rich", "exists")])
        self.assertEqual(problems, ["deps.txt adds PyPI package imaginary-sf13-unpublished, which pypi.org does "
                                    "not have"])

    def test_a_change_to_an_already_included_file_is_checked(self) -> None:
        self.base = self.commit({"requirements.txt": "requests==2.32.0\n-r deps.txt\n", "deps.txt": "attrs\n"})
        head = self.commit({"deps.txt": "attrs\ninvented-in-include-zz9\n"})
        rows, problems = self.check(head, {})
        self.assertEqual([(row["manifest"], row["name"], row["status"]) for row in rows],
                         [("deps.txt", "invented-in-include-zz9", "missing")])
        self.assertEqual(len(problems), 1)

    def test_an_include_that_leaves_the_repository_or_is_missing_is_unverified(self) -> None:
        head = self.commit({"requirements.txt": "requests==2.32.0\n-r ../outside.txt\n-r /etc/reqs.txt\n"
                                                "-r https://example.com/r.txt\n-c gone.txt\n-rsub\n"
                                                "./vendored/pkg\nlocal.whl\n--trusted-host example.com\n"
                                                "-i https://example.com/simple\n-f ./wheels\n",
                            "sub/x.txt": "attrs\n"})
        _, problems = self.check(head, {})
        self.assertEqual(problems, [
            "cannot check requirements.txt line 2 (-r ../outside.txt): it includes a file outside the repository",
            "cannot check requirements.txt line 3 (-r /etc/reqs.txt): it includes a file outside the repository",
            "cannot check requirements.txt line 4 (-r https://example.com/r.txt): it includes a file outside the "
            "repository",
            "cannot check requirements.txt line 5 (-c gone.txt): the included file is not in the repository",
            "cannot check requirements.txt line 6 (-rsub): the included file is not in the repository",
            "cannot check requirements.txt line 7 (./vendored/pkg): only registry packages can be checked",
            "cannot check requirements.txt line 8 (local.whl): only registry packages can be checked",
            "cannot check requirements.txt line 9 (--trusted-host example.com): only registry packages can be checked",
            "cannot check requirements.txt line 10 (-i https://example.com/simple): only registry packages can be "
            "checked",
            "cannot check requirements.txt line 11 (-f ./wheels): only registry packages can be checked"])

    def test_continued_lines_are_joined_and_comments_stripped_as_pip_does(self) -> None:
        head = self.commit({"requirements.txt": "requests==2.32.0\nflask \\\n  >=2.0 \\\n  ,<4\nrich\t# a tab comment\n"
                                                "# a comment line \\\nnot#a-comment-zz9\n"})
        rows, problems = self.check(head, {"https://pypi.org/pypi/flask/json": 200,
                                           "https://pypi.org/pypi/rich/json": 200})
        self.assertEqual(sorted(row["name"] for row in rows), ["flask", "rich"])
        self.assertEqual(problems, ["cannot check requirements.txt line 7 (not#a-comment-zz9): it is not a valid "
                                    "requirement"])

    def test_an_invalid_environment_marker_or_specifier_is_unverified(self) -> None:
        head = self.commit({"requirements.txt": (
            "requests==2.32.0\n"
            "flask; this is not a marker\n"
            "rich ; python_version >= \"3.9\" and (sys_platform == 'linux' or extra == \"x\")\n"
            "attrs ; os_name not in 'nt'\n"
            "pytest ; \n"
            "click ; python_version >= \"3.9\" or\n"
            "black >= 23 garbage\n"
            "ruff[a b]\n"
            "mypy (>=1.0, <2)\n")})
        rows, problems = self.check(head, {f"https://pypi.org/pypi/{name}/json": 200
                                           for name in ("attrs", "mypy", "rich")})
        self.assertEqual(sorted((row["name"], row["status"]) for row in rows),
                         [("attrs", "exists"), ("mypy", "exists"), ("rich", "exists")])
        self.assertEqual(problems, [
            "cannot check requirements.txt line 2 (flask; this is not a marker): its environment marker is not valid",
            "cannot check requirements.txt line 5 (pytest ;): its environment marker is not valid",
            "cannot check requirements.txt line 6 (click ; python_version >= \"3.9\" or): its environment marker is "
            "not valid",
            "cannot check requirements.txt line 7 (black >= 23 garbage): it is not a valid requirement",
            "cannot check requirements.txt line 8 (ruff[a b]): it is not a valid requirement"])

    # --- pyproject.toml and Pipfile: table dependencies and sources -------------------------------

    def test_a_poetry_or_pipfile_dependency_from_outside_the_registry_is_unverified(self) -> None:
        head = self.commit({
            "pyproject.toml": '[project]\nname = "x"\ndependencies = ["attrs>=23"]\n'
                              '[tool.poetry.dependencies]\npython = "^3.12"\n'
                              'fromgit = {git = "https://example.com/evil.git"}\n'
                              'frompath = {path = "../evil", develop = true}\n'
                              'fromindex = {version = "^1", source = "private"}\n'
                              'fine = {version = "^2", extras = ["socks"], markers = "python_version >= \'3.9\'"}\n'
                              'several = [{version = "<2", python = "<3.10"}, {url = "https://example.com/a.whl"}]\n'
                              '[tool.poetry.group.dev.dependencies]\nplain = "^1"\n',
            "Pipfile": '[[source]]\nurl = "https://pypi.org/simple"\nverify_ssl = true\nname = "pypi"\n'
                       '[packages]\npipgit = {git = "https://example.com/evil.git", editable = true}\n'
                       'pipok = {version = "*", extras = ["x"]}\nstar = "*"\n'
                       '[dev-packages]\npipfile = {file = "https://example.com/a.whl"}\n'})
        rows, problems = self.check(head, {"https://pypi.org/pypi/fine/json": 200,
                                           "https://pypi.org/pypi/plain/json": 200,
                                           "https://pypi.org/pypi/pipok/json": 200,
                                           "https://pypi.org/pypi/star/json": 200})
        self.assertEqual(sorted((row["manifest"], row["name"], row["status"]) for row in rows), [
            ("Pipfile", "pipok", "exists"), ("Pipfile", "star", "exists"),
            ("pyproject.toml", "fine", "exists"), ("pyproject.toml", "plain", "exists")])
        self.assertEqual(sorted(problems), sorted([
            "cannot check Pipfile pipfile: only registry packages can be checked",
            "cannot check Pipfile pipgit: only registry packages can be checked",
            "cannot check pyproject.toml fromgit: only registry packages can be checked",
            "cannot check pyproject.toml fromindex: only registry packages can be checked",
            "cannot check pyproject.toml frompath: only registry packages can be checked",
            "cannot check pyproject.toml several: only registry packages can be checked"]))

    def test_another_python_index_or_source_table_is_unverified(self) -> None:
        head = self.commit({
            "pyproject.toml": '[project]\nname = "x"\ndependencies = ["attrs>=23", "requests @ https://e.com/r.whl"]\n'
                              '[tool.uv.sources]\nattrs = {git = "https://example.com/attrs.git"}\n'
                              '[[tool.uv.index]]\nurl = "https://example.com/simple"\n'
                              '[[tool.poetry.source]]\nname = "private"\nurl = "https://example.com/simple"\n',
            "Pipfile": '[[source]]\nurl = "https://example.com/simple"\nname = "private"\n[packages]\n'})
        _, problems = self.check(head, {})
        self.assertEqual(sorted(problems), sorted([
            "cannot check Pipfile [[source]] https://example.com/simple: it names another index",
            "cannot check pyproject.toml [tool.poetry.source]: it names another index",
            "cannot check pyproject.toml [tool.uv.index]: it names another index",
            "cannot check pyproject.toml attrs (tool.uv.sources): only registry packages can be checked",
            "cannot check pyproject.toml requests @ https://e.com/r.whl: only registry packages can be checked"]))

    def test_a_manifest_of_the_wrong_shape_is_a_controlled_refusal(self) -> None:
        for path, text in [("pyproject.toml", 'project = "oops"\n'),
                           ("pyproject.toml", '[project]\nname = "x"\ndependencies = "requests"\n'),
                           ("pyproject.toml", '[project.optional-dependencies]\ndev = "pytest"\n'),
                           ("pyproject.toml", 'tool = 1\n'),
                           ("pyproject.toml", '[tool.poetry]\ndependencies = ["requests"]\n'),
                           ("pyproject.toml", '[tool.poetry.dependencies]\nrequests = 5\n'),
                           ("pyproject.toml", '[build-system]\nrequires = [1]\n'),
                           ("pyproject.toml", '[dependency-groups]\ndev = [{other = "x"}]\n'),
                           ("Pipfile", 'packages = ["requests"]\n'),
                           ("Pipfile", 'source = "https://pypi.org/simple"\n'),
                           ("package.json", json.dumps(["chalk"])),
                           ("package.json", json.dumps({"dependencies": ["chalk"]})),
                           ("package.json", json.dumps({"dependencies": None})),
                           ("package.json", json.dumps({"dependencies": {"chalk": 5}}))]:
            with self.subTest(path=path, text=text):
                head = self.commit({path: text})
                rows, problems = self.check(head, {})
                self.base = head  # the next case changes only its own file
                self.assertEqual(rows, [])
                self.assertEqual(len(problems), 1, problems)
                self.assertRegex(problems[0], rf"^cannot read {re.escape(path)} to check its new packages \(.+\); "
                                              "the landing stays refused until it parses$")

    # --- package.json: sources, aliases --------------------------------------------------------

    def test_an_existing_npm_package_that_moves_to_another_source_is_checked(self) -> None:
        self.base = self.commit({"package.json": json.dumps({"dependencies": {
            "a": "4", "b": "4", "c": "4", "d": "4", "e": "4", "f": "4", "g": "4", "h": "4", "i": "4", "k": "4",
            "m": "npm:chalk@4", "same-git": "git+https://example.com/s.git"}})})
        head = self.commit({"package.json": json.dumps({"dependencies": {
            "a": "https://example.com/a.tgz", "b": "git+ssh://git@example.com/b.git", "c": "github:user/c",
            "d": "user/d#v1", "e": "gitlab:user/e", "f": "bitbucket:user/f", "g": "git://example.com/g.git",
            "h": "http://example.com/h.tgz", "i": "~4.1.0", "k": "file:../k", "m": "npm:other-pkg@1",
            "same-git": "git+https://example.com/s.git"}})})
        rows, problems = self.check(head, {"https://registry.npmjs.org/other-pkg": 200})
        self.assertEqual(sorted((row["name"], row["status"]) for row in rows), [
            ("a", "unverified"), ("b", "unverified"), ("c", "unverified"), ("d", "unverified"),
            ("e", "unverified"), ("f", "unverified"), ("g", "unverified"), ("h", "unverified"),
            ("k", "local"), ("m", "exists")])
        self.assertEqual(sorted(problems), sorted(
            f"cannot check npm package {name} from package.json: it does not come from registry.npmjs.org"
            for name in "abcdefgh"))

    def test_an_npm_alias_never_hides_another_entry_for_the_same_package(self) -> None:
        head = self.commit({"package.json": json.dumps({
            "dependencies": {"left-pad": "1.3.0", "a": "npm:chalk@5", "chalk": "git+https://example.com/evil.git"},
            "devDependencies": {"b": "npm:@scope/chalk"}})})
        rows, problems = self.check(head, {"https://registry.npmjs.org/chalk": 200,
                                           "https://registry.npmjs.org/@scope%2Fchalk": 200})
        self.assertEqual(sorted((row["name"], row.get("lookup"), row["status"]) for row in rows), [
            ("a", "chalk", "exists"), ("b", "@scope/chalk", "exists"), ("chalk", None, "unverified")])
        self.assertEqual(problems, ["cannot check npm package chalk from package.json: it does not come from "
                                    "registry.npmjs.org"])

    def test_a_name_that_cannot_be_a_package_is_never_sent(self) -> None:
        head = self.commit({"package.json": json.dumps({"dependencies": {"../../etc": "1", "a b": "1"}})})
        rows, problems = self.check(head, {})
        self.assertEqual([row["status"] for row in rows], ["invalid", "invalid"])
        self.assertEqual(len(problems), 2)
        self.assertIn("is not a valid npm package name", problems[0])


def command_words(node: ast.AST) -> list[str]:
    """The literal words of a command argument. A string counts only when it reads as a command
    (one word, or starting with `git ` or `gh `), so a message that mentions git push does not."""
    if isinstance(node, (ast.List, ast.Tuple)):
        return [word for item in node.elts for word in command_words(item)]
    if isinstance(node, ast.Starred):
        return command_words(node.value)
    if isinstance(node, ast.JoinedStr):  # an f-string: its literal parts, with a gap for each value
        text = "".join(part.value if isinstance(part, ast.Constant) else " {} " for part in node.values)
    elif isinstance(node, ast.Constant) and isinstance(node.value, str):
        text = node.value
    else:
        return []
    words = text.split()
    return words if len(words) == 1 or words[:1] in (["git"], ["gh"]) else []


def push_or_pull_request_commands(source: str) -> list[tuple[int, str]]:
    """Every call, list or tuple whose literal words run `git ... push` or `gh ... pr create|merge`.
    A call counts its function name too, so a helper call such as git(repo, "push") is found."""
    found: dict[int, str] = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            words = [name] + [word for arg in [*node.args, *(item.value for item in node.keywords)]
                              for word in command_words(arg)]
        elif isinstance(node, (ast.List, ast.Tuple)):
            words = command_words(node)
        else:
            continue
        for index, word in enumerate(words):
            rest = words[index + 1:]
            pull_request = rest[rest.index("pr") + 1:] if word == "gh" and "pr" in rest else []
            if (word == "git" and "push" in rest) or {"create", "merge"} & set(pull_request):
                found.setdefault(node.lineno, " ".join(words))
                break
    return sorted(found.items())


class LandingContractTests(unittest.TestCase):
    """The attended landing step: the controller prints, a person approves, the skill pushes."""

    def test_the_push_command_quotes_every_value_for_a_posix_shell(self) -> None:
        command = CONTROLLER.push_command("my remote", "a" * 40, "agentsmith/x;id")
        self.assertEqual(shlex.split(command), ["git", "push", "my remote", "a" * 40 + ":refs/heads/agentsmith/x;id"])

    def test_the_leak_check_names_the_field_and_uses_the_secret_scanner_patterns(self) -> None:
        token = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
        self.assertEqual(CONTROLLER.leak_problems({"title": f"IMP-1 {token}", "body": "clean"}),
                         ["the pull-request title holds a likely secret (AWS access key id)"])
        self.assertEqual(CONTROLLER.leak_problems({"title": "IMP-1", "body": "clean"}), [])
        # The installed controller cannot import agentsmith.py, so it carries a copy; keep it equal.
        spec = importlib.util.spec_from_file_location("agentsmith_core_for_deliver", ROOT / "agentsmith.py")
        assert spec and spec.loader
        core = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(core)
        self.assertEqual([(name, pattern.pattern, pattern.flags) for name, pattern in CONTROLLER.SECRET_PATTERNS],
                         [(name, pattern.pattern, pattern.flags) for name, pattern in core.SECRET_PATTERNS])

    def core(self):
        spec = importlib.util.spec_from_file_location("agentsmith_core_for_scan", ROOT / "agentsmith.py")
        assert spec and spec.loader
        core = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(core)
        return core

    def test_the_diff_scan_finds_what_secret_scan_finds_in_the_same_change(self) -> None:
        # The installed controller cannot import agentsmith.py, so it carries the scanner's reading
        # of a diff. Stage one change and compare it with `agentsmith secret-scan` on the same bytes.
        core = self.core()
        with tempfile.TemporaryDirectory(prefix="agentsmith scan parity ") as temporary:
            repo = Path(temporary)
            env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
            git = lambda *args: subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.com",
                                                "-c", "commit.gpgsign=false", *args], cwd=repo, env=env,
                                               check=True, capture_output=True)
            git("init", "-q", "-b", "main")
            (repo / "kept.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
            git("add", ".")
            git("commit", "-qm", "base")
            key = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
            (repo / "kept.txt").write_text("one\n" + key + "\nthree\nfour " + key + "\n", encoding="utf-8")
            (repo / "new dir").mkdir()
            (repo / "new dir/a b.txt").write_text("x\n" + "pass" + 'word = "correcthorsebattery"\n',
                                                  encoding="utf-8")
            (repo / "allowed.txt").write_text("fixture " + key + "\n", encoding="utf-8")
            git("add", ".")
            allow = [re.compile("^fixture ")]
            expected = core.scan_secret_records(core.staged_secret_records(repo), allow)
            git("commit", "-qm", "change")
            found = CONTROLLER.secret_findings(CONTROLLER.diff_secret_records(repo, "HEAD~1", "HEAD"), tuple(allow))
            self.assertEqual(found, expected)
            self.assertEqual([(path, line) for path, line, _ in found],
                             [("kept.txt", 2), ("kept.txt", 4), ("new dir/a b.txt", 2)])
        records = [("f", 1, "clean"), ("f", 2, "token = 'abcdefghij'"), ("f", 3, "   ")]
        self.assertEqual(CONTROLLER.secret_findings(records, ()), core.scan_secret_records(records, []))

    def test_the_controller_has_no_push_or_pull_request_code_path(self) -> None:
        source = CONTROLLER_PATH.read_text(encoding="utf-8")
        self.assertEqual(push_or_pull_request_commands(source), [])
        self.assertNotIn("network_access=true", source)

    def test_the_guard_finds_a_push_or_pull_request_command_in_any_spelling(self) -> None:
        source = textwrap.dedent("""\
            import subprocess
            def forbidden(repo, remote):
                subprocess.run(['git', 'push', 'origin', 'HEAD'])
                subprocess.run(('gh', 'pr', 'create'))
                git(repo, "push", remote)
                command = ["gh", "pr", "merge", "7"]
                subprocess.run(f"git -C {repo} push", shell=True)
            def allowed(repo):
                git(repo, "ls-remote", "origin")
                subprocess.run(["gh", "pr", "view", "7"])
                raise RuntimeError("the controller never runs git push")
            """)
        self.assertEqual([line for line, _ in push_or_pull_request_commands(source)], [3, 4, 5, 6, 7])

    def test_the_skill_lands_the_exact_commit_after_one_question(self) -> None:
        skill = (ROOT / "skills/autonomous-run/SKILL.md").read_text(encoding="utf-8")
        section = skill.split("## Land an accepted run (attended)", 1)
        self.assertEqual(len(section), 2, "the skill needs the attended landing step")
        step = section[1].split("\n## ", 1)[0]
        for required in ("deliver <run-id> --dry-run", "Ask once", "git push origin <accepted-sha>:refs/heads/agentsmith/<run-id>",
                         "gh pr create", "--body-file", "agentsmith ci watch --pr <number>", "one end state",
                         "A human merges", "never merge"):
            self.assertIn(required, step)
        self.assertNotIn("never push, open a PR", skill, "the old blanket rule contradicts the landing step")

    def test_the_auto_merge_trial_is_designed_but_not_switched_on(self) -> None:
        docs = (ROOT / "docs/21-autonomous-runs.md").read_text(encoding="utf-8")
        section = docs.split("### A future auto-merge trial (not switched on)", 1)
        self.assertEqual(len(section), 2, "docs/21 needs the trial design")
        trial = section[1].split("\n## ", 1)[0]
        for parameter in ("one area", "path glob", "dated window", "four weeks", "no escaped defect",
                          ".harness/AUTOMERGE_PAUSED", "revert", "red", "Nothing in this release merges automatically"):
            self.assertIn(parameter.casefold(), trial.casefold())
        sources = [ROOT / "scripts/autonomous-run.py", ROOT / "work_graph.py", ROOT / "agentsmith.py"]
        for source in sources:
            self.assertNotIn("AUTOMERGE_PAUSED", source.read_text(encoding="utf-8"),
                             f"{source.name}: the trial is not switched on, so no code reads its kill switch")


if __name__ == "__main__":
    unittest.main(verbosity=2)
