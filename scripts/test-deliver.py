#!/usr/bin/env python3
"""`autonomous-run deliver`: real accepted runs with fake clients, a local bare origin, no network."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
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
    if not checker:
        pathlib.Path("src").mkdir(exist_ok=True)
        pathlib.Path("src/change.txt").write_text("fixed\\n", encoding="utf-8")
        subprocess.run(["git", "add", "src/change.txt"], check=True)
        subprocess.run(["git", "commit", "-qm", "fix: bounded fixture change"], check=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    log = re.search(r"attempt-[0-9]+-verify[.]txt", prompt)
    evidence = (["fixture verification passed :: " + log.group(0) + " :: fixture verification passed"]
                if checker else ["maker ran the fixture verification"])
    status = "accepted" if checker else "completed"
    receipt = {"status": status, "summary": "Make src/change.txt hold the fixed value; ping @someone",
               "commit": commit, "changed_paths": ["src/change.txt"], "evidence": evidence,
               "unresolved": [], "next_state": status}
    if receipt_path is not None:
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 3}}))
    else:
        print(json.dumps({"type": "result", "total_cost_usd": 0.25, "structured_output": receipt}))
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

    def accepted_run(self, *, policy_tier: str = "B", declared: str | None = None, run_id: str = "deliver") -> Path:
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
            "accepted_at: 2026-11-06\n---\n# Spec\nMake src/change.txt hold the fixed value.\n", encoding="utf-8")
        (repo / "README.md").write_text("fixture\n", encoding="utf-8")
        (repo / ".harness").mkdir()
        (repo / ".harness/risk-policy.json").write_text(json.dumps(
            {"schema_version": 1, "rules": [{"paths": ["src/**"], "tier": policy_tier, "lenses": ["code"]}]}),
            encoding="utf-8")
        manifest = json.loads((ROOT / "templates/autonomous-run.json").read_text(encoding="utf-8"))
        manifest.update(run_id=run_id, spec_path="docs/specs/task.md", implementation_ticket="IMP-7")
        for role in manifest["roles"].values():
            role["model"] = "fixture-model"
        manifest["scope"]["allowed_paths"] = ["src/**"]
        manifest["verify"]["command"] = ('test -f src/change.txt && '
                                         'echo "fixture verification passed for src/change.txt"')
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
        started = subprocess.run([sys.executable, str(CONTROLLER_PATH), "start", f".harness/runs/{run_id}.json"],
                                 cwd=repo, env=self.env, text=True, capture_output=True, check=False)
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
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
        result = self.deliver(repo, "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["push_command"], f"git push origin {accepted}:refs/heads/agentsmith/deliver")
        self.assertEqual(report["head"], accepted)
        self.assertEqual(report["staleness"], {"base": "origin/main", "behind": 0, "applies": True})
        self.assertEqual(report["tier"]["tier"], "B")
        self.assertFalse(report["eligibility"]["eligible"])
        self.assert_golden(report["body"], "eligible-no.md")
        self.assertNotIn(str(self.root), result.stdout, "the body must not name a local path")
        # The text form shows the same body and the exact push command.
        text = self.deliver(repo, "--dry-run")
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn(f"git push origin {accepted}:refs/heads/agentsmith/deliver", text.stdout)
        self.assertIn(report["body"], text.stdout)

    def test_eligibility_after_ci_is_yes_only_when_every_fact_is_met(self) -> None:
        repo = self.accepted_run(policy_tier="A")
        accepted = self.state(repo)["accepted_commit"]
        CONTROLLER.write_json(CONTROLLER.calibration_path(repo, "claude", "fixture-model", "high"),
                              {"status": "passed", "calibrated_at": "2026-11-06T09:00:00+00:00",
                               "client_version": "fixture"})
        reports = {}
        for state in ("green", "red-at-diff", "flaky"):
            path = self.root / f"ci-{state}.json"
            path.write_text(json.dumps({"state": state, "sha": accepted, "exit_code": 0}), encoding="utf-8")
            reports[state] = path
        result = self.deliver(repo, "--eligibility", "--sha", accepted, "--ci-report", str(reports["green"]), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["eligibility"]["eligible"], report["eligibility"])
        self.assert_golden(report["body"], "eligible-yes.md")
        # Before CI the same run is "pending CI", so not eligible yet.
        pending = json.loads(self.deliver(repo, "--dry-run", "--json").stdout)
        self.assertFalse(pending["eligibility"]["eligible"])
        self.assertIn("CI green for this commit: pending CI", pending["eligibility"]["line"])
        for state in ("red-at-diff", "flaky"):
            with self.subTest(ci=state):
                again = json.loads(self.deliver(repo, "--eligibility", "--sha", accepted, "--ci-report",
                                                str(reports[state]), "--json").stdout)
                self.assertFalse(again["eligibility"]["eligible"])
                self.assertIn(f"CI green for this commit: unmet ({state})", again["eligibility"]["line"])
        # A report about another commit, or a SHA that is not the accepted commit, is not CI for this head.
        other = self.root / "ci-other.json"
        other.write_text(json.dumps({"state": "green", "sha": "f" * 40}), encoding="utf-8")
        again = json.loads(self.deliver(repo, "--eligibility", "--sha", accepted, "--ci-report", str(other),
                                        "--json").stdout)
        self.assertIn("CI green for this commit: unmet (the report is for ffffffffffff)", again["eligibility"]["line"])
        moved = self.deliver(repo, "--eligibility", "--sha", "e" * 40, "--ci-report", str(reports["green"]), "--json")
        self.assertIn("head equals the accepted commit: unmet", json.loads(moved.stdout)["eligibility"]["line"])
        self.assertFalse(json.loads(moved.stdout)["eligibility"]["eligible"])

    def test_each_eligibility_fact_is_listed_met_or_unmet(self) -> None:
        repo = self.accepted_run(policy_tier="B")
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

    def test_staleness_counts_commits_behind_the_base(self) -> None:
        repo = self.accepted_run()
        clone = self.root / "other"
        subprocess.run(["git", "clone", "-q", str(self.root / "origin.git"), str(clone)], env=self.env, check=True)
        (clone / "README.md").write_text("moved on\n", encoding="utf-8")
        self.git(clone, "-c", "user.name=Other", "-c", "user.email=user@example.com", "commit", "-qam", "base moves")
        self.git(clone, "push", "-q", "origin", "main")
        self.git(repo, "fetch", "-q", "origin")
        report = json.loads(self.deliver(repo, "--dry-run", "--json").stdout)
        self.assertEqual(report["staleness"], {"base": "origin/main", "behind": 1, "applies": True})
        self.assertIn("1 commit behind origin/main", report["body"])

    # --- refusals ----------------------------------------------------------------------------

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

    def test_refuses_when_the_base_branch_is_unknown(self) -> None:
        repo = self.accepted_run()
        self.refused(repo, "refs/remotes/origin/release is missing", "--base-branch", "release")

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


class LandingContractTests(unittest.TestCase):
    """The attended landing step: the controller prints, a person approves, the skill pushes."""

    def test_the_controller_has_no_push_or_pull_request_code_path(self) -> None:
        source = CONTROLLER_PATH.read_text(encoding="utf-8")
        self.assertNotRegex(source, r'\[\s*"git"\s*,\s*"push"')
        self.assertNotRegex(source, r'\[\s*"gh"\s*,\s*"pr"')
        self.assertNotIn("network_access=true", source)

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
