#!/usr/bin/env python3
"""Factory readiness and numbers from fixture runs, events and recorded gh output. No network."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import ci_watch  # noqa: E402
import factory  # noqa: E402

CONTROLLER = factory.load_controller(ROOT)

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
CLEAN_ENV = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
POLICY = json.dumps({"schema_version": 1, "rules": [{"paths": ["src/**"], "tier": "B"}]})
WORKFLOW = """name: verify
on: push
jobs:
  compatibility:
    name: compatibility (${{ matrix.os }})
    timeout-minutes: ${{ matrix.os == 'windows-latest' && 45 || 20 }}
    steps: []
"""


def stamp(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).isoformat(timespec="seconds").replace("+00:00", "Z")


class FakeRunner:
    """Serves recorded gh output by the endpoint it asks for, like `gh` would."""

    def __init__(self, runs: list[dict], jobs: dict[int, list[dict]]):
        self.runs, self.jobs, self.calls = runs, jobs, []

    def __call__(self, argv, **_kwargs):
        self.calls.append(argv)
        assert argv[0] == "gh" and argv[1] in {"repo", "api"}, argv
        if argv[1] == "repo":
            payload = {"nameWithOwner": "owner/project"}
        elif "/jobs" in argv[-1]:
            run_id = int(argv[-1].split("/runs/")[1].split("/")[0])
            payload = [{"total_count": len(self.jobs.get(run_id, [])), "jobs": self.jobs.get(run_id, [])}]
        else:
            assert "branch=main&event=push&status=completed" in argv[-1], argv
            payload = [{"total_count": len(self.runs), "workflow_runs": self.runs}]
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")


def ci_run(run_id: int, conclusion: str, hours_ago: float, workflow: int = 1) -> dict:
    return {"id": run_id, "run_attempt": 1, "status": "completed", "conclusion": conclusion, "workflow_id": workflow,
            "name": "verify", "path": ".github/workflows/verify.yml", "created_at": stamp(hours_ago + 0.5),
            "updated_at": stamp(hours_ago)}


def job(name: str, minutes: float) -> dict:
    return {"id": hash(name) % 100000, "name": name, "status": "completed", "conclusion": "success",
            "started_at": stamp(5), "completed_at": (NOW - timedelta(hours=5) + timedelta(minutes=minutes))
            .isoformat(timespec="seconds").replace("+00:00", "Z"), "steps": []}


class FactoryTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="agentsmith factory ")
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name).resolve() / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Harness Test")
        self.git("config", "user.email", "user@example.com")
        (self.repo / ".harness").mkdir()
        (self.repo / ".harness/verify.conf").write_text(
            "pipeline-specs :: python3 .agentsmith/autonomous-run.py check-specs\n", encoding="utf-8")
        (self.repo / ".harness/risk-policy.json").write_text(POLICY, encoding="utf-8")
        (self.repo / ".harness/lenses.json").write_text('{"schema_version": 1, "lenses": []}\n', encoding="utf-8")
        (self.repo / ".github/workflows").mkdir(parents=True)
        (self.repo / ".github/workflows/verify.yml").write_text(WORKFLOW, encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.git("remote", "add", "origin", "https://github.com/owner/project.git")
        self.runs = self.repo / ".git/agentsmith-runs"

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.repo, env=CLEAN_ENV, text=True, capture_output=True,
                              check=True).stdout.strip()

    def add_run(self, run_id: str, status: str, *, hours_ago: float = 24, touches: int = 0, tier: str = "B",
            usd: float = 1.0, tokens: int = 1000) -> None:
        folder = self.runs / run_id
        folder.mkdir(parents=True)
        state = {"run_id": run_id, "status": status, "started_at": stamp(hours_ago), "claude_cost_usd": usd,
                 "codex_tokens_used": tokens, "risk": {"tier": tier}}
        (folder / "state.json").write_text(json.dumps(state), encoding="utf-8")
        events = [{"event": "run_started"}] + [{"event": "run_escalated"}, {"event": "run_resumed"}][:touches] + (
            [{"event": "run_accepted"}] if status == "accepted" else [])
        (folder / "events.jsonl").write_text("".join(json.dumps(item) + "\n" for item in events), encoding="utf-8")
        (folder / "attempt-1-verify.json").write_text('{"exit_code": 0}', encoding="utf-8")

    def number(self, report: dict, name: str) -> dict:
        return next(row for row in report["numbers"] if row["name"] == name)

    # --- the six numbers ---------------------------------------------------------------------

    def test_the_six_numbers_from_runs_events_logs_and_ci(self) -> None:
        for index in range(6):
            self.add_run(f"ok-{index}", "accepted", touches=1 if index == 0 else 0, tier="A" if index < 2 else "B",
                     usd=2.0, tokens=500)
        self.add_run("stuck", "escalated", touches=1, usd=4.0, tokens=1000)
        self.add_run("stopped", "interrupted", usd=0.0, tokens=0)
        self.add_run("old", "accepted", hours_ago=24 * 60)  # outside the default 28-day window
        sha = "a" * 40
        factory.add_defect(self.repo, sha, "B", "regression in parser", now=NOW - timedelta(days=1))
        for index in range(5):
            factory.add_minutes(self.repo, f"ok-{index}", 12, now=NOW)
        ci = [ci_run(1, "success", 48), ci_run(2, "failure", 30), ci_run(3, "success", 24),
              ci_run(4, "failure", 10, workflow=2), ci_run(5, "success", 7, workflow=2)]
        report = factory.numbers(self.repo, now=NOW, ci_runs=ci)
        share = self.number(report, "accepted without human rework")
        self.assertEqual((share["status"], share["n"], share["value"]), ("ok", 8, round(5 / 8, 3)))
        defects = self.number(report, "defects found after merge, per tier")
        self.assertEqual(defects["value"], {"A": {"defects": 0, "landed": 2, "per_landed_change": 0.0},
                                            "B": {"defects": 1, "landed": 4, "per_landed_change": 0.25}})
        touches = self.number(report, "operator touches per landed change")
        self.assertEqual((touches["n"], touches["value"]), (6, round(1 / 6, 3)))
        minutes = self.number(report, "human minutes per landed change")
        self.assertEqual((minutes["n"], minutes["value"]), (5, 12.0))
        red = self.number(report, "time the default branch spends red")
        self.assertEqual(red["value"]["hours"], 9.0)  # 30 h -> 24 h ago, and 10 h -> 7 h ago
        spend = self.number(report, "spend per landed change")
        self.assertEqual(spend["value"], {"claude_usd": round(16.0 / 6, 2), "codex_tokens": round(4000 / 6)})
        for row in report["numbers"]:
            self.assertEqual(row["window"], report["window"], row["name"])
            self.assertIn("n", row)

    def test_too_few_cases_say_insufficient_data(self) -> None:
        for index in range(3):
            self.add_run(f"few-{index}", "accepted")
        report = factory.numbers(self.repo, now=NOW, ci_runs=[ci_run(1, "success", 3)])
        for name in ("accepted without human rework", "operator touches per landed change",
                     "spend per landed change", "human minutes per landed change",
                     "time the default branch spends red", "defects found after merge, per tier"):
            row = self.number(report, name)
            self.assertEqual((row["status"], row["value"]), ("insufficient data", None), name)
            self.assertIn("at least 5 are needed", row["detail"])
        self.assertIn("insufficient data", factory.render(report))

    def test_the_window_and_unreadable_runs_are_stated(self) -> None:
        self.add_run("recent", "accepted", hours_ago=2)
        self.add_run("before", "accepted", hours_ago=24 * 10)
        (self.runs / "broken").mkdir()
        (self.runs / "broken/state.json").write_text("{", encoding="utf-8")
        report = factory.numbers(self.repo, since="2026-11-01", now=NOW, ci_runs=None, ci_error="gh is not installed")
        self.assertEqual(report["window"]["since"], "2026-11-01T00:00:00+00:00")
        self.assertEqual(self.number(report, "spend per landed change")["n"], 1)
        red = self.number(report, "time the default branch spends red")
        self.assertEqual((red["status"], red["detail"]), ("unavailable", "cannot read CI: gh is not installed"))
        self.assertEqual(len(report["unreadable_runs"]), 1)
        with self.assertRaisesRegex(factory.FactoryError, "--since needs a date"):
            factory.numbers(self.repo, since="last week", now=NOW, ci_runs=[])

    def test_operator_logs_validate_their_input(self) -> None:
        with self.assertRaisesRegex(factory.FactoryError, "full commit SHA"):
            factory.add_defect(self.repo, "abc123", "B")
        with self.assertRaisesRegex(factory.FactoryError, "--tier must be one of"):
            factory.add_defect(self.repo, "a" * 40, "D")
        with self.assertRaisesRegex(factory.FactoryError, "more than 0"):
            factory.add_minutes(self.repo, "run", 0)
        path = factory.add_defect(self.repo, "b" * 40, "human", "found in review")
        self.assertEqual(path.parent, self.repo / ".git/agentsmith-factory")

    # --- export -----------------------------------------------------------------------------

    def test_export_writes_receipts_out_of_the_git_folder_only(self) -> None:
        self.add_run("one", "accepted")
        target = self.repo.parent / "export"
        factory.export(self.repo, target)
        exported = json.loads((target / "run-one.json").read_text(encoding="utf-8"))
        self.assertEqual(exported["receipts"], {"attempt-1-verify.json": {"exit_code": 0}})
        self.assertTrue((target / "factory.json").is_file())
        with self.assertRaisesRegex(factory.FactoryError, "out of the Git folder"):
            factory.export(self.repo, self.repo / ".git/export")
        with self.assertRaisesRegex(factory.FactoryError, "not an empty folder"):
            factory.export(self.repo, target)

    def test_export_redacts_home_paths_and_secret_like_text(self) -> None:
        import agentsmith
        self.add_run("leaky", "accepted")
        state_path = self.runs / "leaky/state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        token = "ghp_" + "a" * 36
        state.update(worktree=str(Path.home() / "projects/client-repo-leaky"),
                     reason=f"token = '{token}' and synthetic-secret=FAKE_TEST_VALUE_12345")
        state_path.write_text(json.dumps(state), encoding="utf-8")
        target = self.repo.parent / "export"
        summary = factory.export(self.repo, target)
        text = (target / "run-leaky.json").read_text(encoding="utf-8")
        self.assertNotIn(str(Path.home()), text)
        self.assertIn("~/projects/client-repo-leaky", text)
        self.assertNotIn(token, text)
        self.assertNotIn("FAKE_TEST_VALUE_12345", text)
        self.assertIn("[redacted:", text)
        self.assertGreaterEqual(summary["redactions"], 2)
        self.assertEqual(json.loads((target / "factory.json").read_text(encoding="utf-8"))["redactions"],
                         summary["redactions"])

    # --- readiness ----------------------------------------------------------------------------

    def refuse_once(self) -> None:
        """A real kill-switch drill: the controller refuses a start while the marker exists."""
        marker = self.repo / ".harness/AUTONOMY_PAUSED"
        marker.touch()
        try:
            with self.assertRaises(CONTROLLER.RunError):
                CONTROLLER.assert_autonomy_not_paused(self.repo, action="start", run_id="drill")
        finally:
            marker.unlink()

    def kill_switch(self, *events: dict) -> dict:
        log = self.repo / ".git/agentsmith-factory/events.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("".join(json.dumps(item) + "\n" for item in events), encoding="utf-8")
        report = self.readiness_without_drill()
        return next(item for item in report["checks"] if item["name"] == "kill switch tested")

    def readiness_without_drill(self) -> dict:
        values = self.ready_inputs(drill=False)
        gh = ci_watch.Gh(runner=FakeRunner(values["runs"], values["jobs"]), which=lambda _: "gh")
        return factory.readiness(self.repo, controller=values["controller"], gh=gh, manifest=values["manifest"],
                                 base="main", now=datetime.now(timezone.utc))

    def test_a_forged_kill_switch_record_is_not_evidence(self) -> None:
        self.refuse_once()
        real = json.loads((self.repo / ".git/agentsmith-factory/events.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(self.kill_switch(real)["status"], "pass")
        forged = [
            {"event": "autonomy_pause_refused"},
            {**real, "marker": str(self.repo.parent / "elsewhere/AUTONOMY_PAUSED")},
            {**real, "marker_mtime_ns": None},
            {**real, "marker_mtime_ns": int((NOW + timedelta(days=1)).timestamp() * 1e9)},
            {**real, "action": "fly"},
            {**real, "run_id": ""},
            {**real, "at": "2099-01-01T00:00:00+00:00"},
        ]
        for event in forged:
            with self.subTest(event=event):
                result = self.kill_switch(event)
                self.assertEqual(result["status"], "fail", result)
                self.assertIn("0 refusal(s) recorded with their facts", result["evidence"])

    def ready_inputs(self, drill: bool = True, **changes) -> dict:
        jobs = {9: [job("compatibility (windows-latest)", 20), job("compatibility (macos-latest)", 8),
                    job("compatibility (ubuntu-latest)", 6)]}
        runs = [ci_run(9, "success", 6)]
        controller = SimpleNamespace(require_native_role_sandbox=lambda: None,
                                     preflight_sandboxes=lambda *_args, **_kwargs: None,
                                     calibration_status=lambda *_args: {"status": "passed",
                                                                        "calibrated_at": "2026-11-05T09:00:00+00:00"})
        if drill:
            self.refuse_once()
        values = {"runs": runs, "jobs": jobs, "controller": controller,
                  "manifest": {"roles": {"checker": {"runtime": "claude", "model": "m", "effort": "high"}}}}
        values.update(changes)
        return values

    def readiness(self, **changes) -> dict:
        values = self.ready_inputs(**changes)
        gh = ci_watch.Gh(runner=FakeRunner(values["runs"], values["jobs"]), which=lambda _: "gh")
        return factory.readiness(self.repo, controller=values["controller"], gh=values.get("gh", gh),
                                 manifest=values["manifest"], base="main", now=datetime.now(timezone.utc),
                                 gh_error=values.get("gh_error"))

    def failing(self, report: dict) -> dict[str, str]:
        return {item["name"]: item["evidence"] for item in report["checks"] if item["status"] != "pass"}

    def test_readiness_passes_only_when_every_check_has_evidence(self) -> None:
        report = self.readiness()
        self.assertEqual(self.failing(report), {})
        self.assertTrue(report["ready"])
        headroom = next(item for item in report["checks"] if item["name"] == "CI headroom")
        self.assertIn("windows compatibility (windows-latest): 20 of 45 min", headroom["evidence"])
        self.assertIn("linux compatibility (ubuntu-latest): 6 of 20 min", headroom["evidence"])
        self.assertEqual(len(report["checks"]), 8)

    def test_each_readiness_check_fails_with_its_reason_and_a_next_step(self) -> None:
        def broken_preflight(*_args, **_kwargs):
            raise RuntimeError("maker (codex) cannot run a command in the operating-system sandbox")
        cases = {
            "default branch green": dict(runs=[ci_run(9, "success", 6), ci_run(8, "failure", 30)]),
            "CI headroom": dict(jobs={9: [job("compatibility (windows-latest)", 40), job("compatibility (macos-latest)", 8),
                                          job("compatibility (ubuntu-latest)", 6)]}),
            "checker can execute on this host": dict(controller=SimpleNamespace(
                require_native_role_sandbox=lambda: None, preflight_sandboxes=broken_preflight,
                calibration_status=lambda *_args: {"status": "passed"})),
            "checker calibration passed": dict(controller=SimpleNamespace(
                require_native_role_sandbox=lambda: None, preflight_sandboxes=lambda *_a, **_k: None,
                calibration_status=lambda *_args: {"status": "failed"})),
        }
        for name, change in cases.items():
            with self.subTest(check=name):
                report = self.readiness(**change)
                self.assertIn(name, self.failing(report))
                self.assertFalse(report["ready"])
                failed = next(item for item in report["checks"] if item["name"] == name)
                self.assertNotEqual(failed["next_step"], "none")
        missing_os = self.readiness(jobs={9: [job("compatibility (windows-latest)", 20)]})
        self.assertIn("no job found for macos, linux", self.failing(missing_os)["CI headroom"])
        offline = self.readiness(gh=None, gh_error="gh is not installed")
        self.assertEqual(self.failing(offline)["default branch green"], "cannot read CI: gh is not installed")
        unnamed = self.readiness(manifest=None)
        self.assertIn("checker calibration passed", self.failing(unnamed))

    def test_readiness_reads_the_base_commit_and_the_kill_switch_record(self) -> None:
        (self.repo / ".harness/lenses.json").unlink()
        (self.repo / ".harness/verify.conf").write_text("tests :: python3 -m unittest\n", encoding="utf-8")
        (self.repo / ".harness/risk-policy.json").write_text("{not json", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-qm", "base without guard, lenses or a valid policy")
        values = self.ready_inputs()
        (self.repo / ".git/agentsmith-factory/events.jsonl").unlink()
        gh = ci_watch.Gh(runner=FakeRunner(values["runs"], values["jobs"]), which=lambda _: "gh")
        report = factory.readiness(self.repo, controller=values["controller"], gh=gh, manifest=values["manifest"],
                                   base="main", now=NOW)
        failing = self.failing(report)
        self.assertIn("kill switch tested", failing)
        self.assertIn("does not run check-specs", failing["pipeline guard in the verifier"])
        self.assertIn("risk policy missing or invalid, lens file missing", failing["risk policy and lens file at the base"])
        (self.runs / "broken").mkdir(parents=True)
        (self.runs / "broken/state.json").write_text("{", encoding="utf-8")
        report = factory.readiness(self.repo, controller=values["controller"], gh=gh, manifest=values["manifest"],
                                   base="main", now=NOW)
        self.assertIn("cannot export unreadable runs", self.failing(report)["receipts exportable"])

    def test_readiness_and_numbers_write_nothing(self) -> None:
        self.add_run("one", "accepted")
        values = self.ready_inputs()
        gh = ci_watch.Gh(runner=FakeRunner(values["runs"], values["jobs"]), which=lambda _: "gh")

        def snapshot() -> dict[str, bytes]:
            return {str(path): path.read_bytes() for path in self.repo.rglob("*") if path.is_file()}

        before = snapshot()
        factory.readiness(self.repo, controller=values["controller"], gh=gh, manifest=values["manifest"],
                          base="main", now=NOW)
        factory.numbers(self.repo, now=NOW, ci_runs=[])
        self.assertEqual(snapshot(), before)

    @unittest.skipIf(os.name == "nt", "the fake gh is a POSIX script")
    def test_the_cli_reads_ci_for_the_target_not_the_current_folder(self) -> None:
        self.add_run("one", "accepted")
        self.git("remote", "set-url", "origin", "git@github.com:owner/target-project.git")
        bin_dir = self.repo.parent / "bin"
        bin_dir.mkdir()
        calls = self.repo.parent / "gh-calls.log"
        (bin_dir / "gh").write_text(f"""#!{sys.executable}
import json, sys
args = sys.argv[1:]
open({str(calls)!r}, "a").write(json.dumps(args) + "\\n")
if args[:2] == ["auth", "status"]:
    raise SystemExit(0)
if args[:2] == ["repo", "view"] and "nameWithOwner" in args:
    print(json.dumps({{"nameWithOwner": "someone/the-current-folder"}}))
elif args[:2] == ["repo", "view"]:
    print(json.dumps({{"defaultBranchRef": {{"name": "main"}}}}))
else:
    print(json.dumps([{{"total_count": 0, "workflow_runs": []}}]))
""", encoding="utf-8")
        (bin_dir / "gh").chmod(0o755)
        env = {**CLEAN_ENV, "PATH": str(bin_dir) + os.pathsep + CLEAN_ENV.get("PATH", "")}
        result = subprocess.run([sys.executable, str(ROOT / "agentsmith.py"), "factory", "numbers", "--json",
                                 "--target", str(self.repo)], cwd=ROOT, env=env, capture_output=True, text=True,
                                check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        logged = [json.loads(line) for line in calls.read_text(encoding="utf-8").splitlines()]
        api = [args for args in logged if args[0] == "api"]
        self.assertTrue(api and all("repos/owner/target-project/" in args[-1] for args in api), logged)
        self.assertFalse([args for args in logged if "nameWithOwner" in args], "the current folder's repository")

    def test_the_github_repository_comes_from_the_targets_origin(self) -> None:
        for url, slug in (("git@github.com:owner/name.git", "owner/name"), ("https://github.com/owner/name", "owner/name"),
                          ("ssh://git@github.com/owner/name.git", "owner/name"), ("https://gitlab.com/owner/name", None)):
            with self.subTest(url=url):
                self.git("remote", "remove", "origin") if self.git("remote") else None
                self.git("remote", "add", "origin", url)
                self.assertEqual(factory.github_slug(self.repo), slug)

    def test_the_cli_reports_without_gh(self) -> None:
        # gh with an empty configuration is not signed in, on every runner: the CI number says so.
        self.add_run("one", "accepted")
        gh_config = self.repo.parent / "gh-config"
        gh_config.mkdir()
        env = {key: value for key, value in CLEAN_ENV.items() if key not in {"GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN"}}
        env["GH_CONFIG_DIR"] = str(gh_config)
        result = subprocess.run([sys.executable, str(ROOT / "agentsmith.py"), "factory", "numbers", "--json",
                                 "--target", str(self.repo)], env=env, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        red = next(row for row in report["numbers"] if row["name"] == "time the default branch spends red")
        self.assertEqual(red["status"], "unavailable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
