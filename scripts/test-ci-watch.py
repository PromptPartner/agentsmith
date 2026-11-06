#!/usr/bin/env python3
"""CI watch contracts: one named end state per watch, from the runs registered for the exact head
SHA, read-only against GitHub. The gh calls are served from fixtures in tests/fixtures/ci-watch."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import ci_watch  # noqa: E402

CORE = ROOT / "agentsmith.py"
FIXTURES = ROOT / "tests" / "fixtures" / "ci-watch"
DOC = ROOT / "docs" / "30-ci-watch.md"
CLEAN_ENV = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
# The only gh verbs the watch may use. Everything else could change GitHub.
READ_ONLY = {("auth", "status"), ("repo", "view"), ("pr", "view"), ("run", "list"), ("run", "view")}


class FakeGh:
    """Serves one fixture's recorded gh output by argv, and records every call."""

    def __init__(self, fixture: dict) -> None:
        self.fixture = fixture
        self.calls: list[list[str]] = []
        self.pr_index = 0
        self.poll_index = -1

    def __call__(self, argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        verb = tuple(argv[1:3])
        fixture = self.fixture
        if verb == ("auth", "status"):
            return self.reply("")
        if verb == ("repo", "view"):
            return self.reply({"nameWithOwner": fixture["repo"], "defaultBranchRef": {"name": fixture["default_branch"]}})
        if verb == ("pr", "view"):
            value = fixture["pr"][min(self.pr_index, len(fixture["pr"]) - 1)]
            self.pr_index += 1
            return self.reply(value)
        if verb == ("run", "list") and "--commit" in argv:
            self.poll_index = min(self.poll_index + 1, len(fixture["polls"]) - 1)
            limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 20
            return self.reply([camel_run(run) for run in fixture["polls"][self.poll_index]["runs"]][:limit])
        if argv[1] == "api" and "/actions/runs?head_sha=" in argv[-1]:
            self.poll_index = min(self.poll_index + 1, len(fixture["polls"]) - 1)
            poll = fixture["polls"][self.poll_index]
            runs = poll["runs"]
            total = poll.get("registered", len(runs))
            pages = [runs[start:start + 100] for start in range(0, len(runs), 100)] or [[]]
            return self.reply([{"total_count": total, "workflow_runs": page} for page in pages])
        if verb == ("run", "list") and "--branch" in argv:
            return self.reply(fixture["base"]["list"])
        if verb == ("run", "view"):
            run_id = argv[3]
            if run_id == str(fixture["base"]["list"][0]["databaseId"]):
                return self.reply(fixture["base"]["view"])
            return self.reply(fixture["polls"][max(self.poll_index, 0)]["views"][run_id])
        if argv[1] == "api" and "/actions/workflows/" in argv[-1]:
            listed = fixture["base"]["list"]
            return self.pages([{"total_count": len(listed),
                                "workflow_runs": [{"id": run["databaseId"], "head_sha": run["headSha"],
                                                   "status": run["status"], "conclusion": run["conclusion"],
                                                   "run_attempt": 1} for run in listed]}], argv)
        if argv[1] == "api":
            run_id, attempt = argv[-1].split("?")[0].split("/")[5:8:2]
            key = f"{run_id}/{attempt}"
            if key in fixture["attempts"]:
                return self.pages(fixture["attempts"][key], argv)
            if fixture["base"]["list"] and run_id == str(fixture["base"]["list"][0]["databaseId"]):
                view = fixture["base"]["view"]
            else:
                view = fixture["polls"][max(self.poll_index, 0)]["views"][run_id]
            jobs = [rest_job(job) for job in view["jobs"]]
            return self.pages([{"total_count": len(jobs), "jobs": jobs}], argv)
        raise AssertionError(f"unexpected gh call: {argv}")

    def pages(self, pages: list, argv: list[str]) -> subprocess.CompletedProcess[str]:
        # Like gh: --paginate --slurp returns every page in an array; without it, only the first page.
        return self.reply(pages if "--slurp" in argv else pages[0])

    @staticmethod
    def reply(value: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, value if isinstance(value, str) else json.dumps(value), "")


def camel_run(run: dict) -> dict:
    """The same run as `gh run list --json` shows it."""
    return {"attempt": run["run_attempt"], "conclusion": run["conclusion"] or "", "createdAt": run["created_at"],
            "databaseId": run["id"], "event": run["event"], "headBranch": run["head_branch"], "headSha": run["head_sha"],
            "name": run["name"], "status": run["status"], "updatedAt": run["updated_at"],
            "workflowDatabaseId": run["workflow_id"], "workflowName": run["name"]}


def rest_job(job: dict) -> dict:
    """The same job as GET .../attempts/{n}/jobs shows it."""
    snake = lambda value: None if value == "0001-01-01T00:00:00Z" else value  # noqa: E731
    return {"id": job["databaseId"], "name": job["name"], "status": job["status"], "conclusion": job["conclusion"] or None,
            "started_at": snake(job["startedAt"]), "completed_at": snake(job["completedAt"]),
            "steps": [{"name": step["name"], "number": step["number"], "status": step["status"],
                       "conclusion": step["conclusion"] or None, "started_at": snake(step["startedAt"]),
                       "completed_at": snake(step["completedAt"])} for step in job["steps"]]}


class Clock:
    def __init__(self, start: str) -> None:
        self.value = dt.datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def run_fixture(name: str) -> tuple[dict, FakeGh, dict]:
    fixture = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    fake, clock = FakeGh(fixture), Clock(fixture["start"])
    gh = ci_watch.Gh(runner=fake, which=lambda _: "/usr/bin/gh")
    report = ci_watch.watch(
        gh, fixture["repo"], pr=67 if fixture["mode"] == "pr" else None,
        sha=fixture["sha"] if fixture["mode"] == "sha" else None,
        cap_seconds=fixture["cap_minutes"] * 60, stall_seconds=fixture["stall_minutes"] * 60,
        poll_seconds=fixture["poll_seconds"], now=clock.now, sleep=clock.sleep)
    return fixture, fake, report


class StateTests(unittest.TestCase):
    def test_every_fixture_ends_in_its_expected_state(self) -> None:
        names = sorted(path.stem for path in FIXTURES.glob("*.json"))
        covered = set()
        for name in names:
            with self.subTest(fixture=name):
                fixture, fake, report = run_fixture(name)
                self.assertEqual((report["state"], report["exit_code"]),
                                 (fixture["expect"]["state"], fixture["expect"]["exit"]), report)
                self.assertTrue(report["next_step"] and "\n" not in report["next_step"])
                for argv in fake.calls:
                    self.assertEqual(argv[0], "gh")
                    if argv[1] == "api":
                        # GET only: no method override and no request fields.
                        self.assertFalse({"-X", "--method", "-f", "-F", "--field", "--raw-field", "--input"} & set(argv), argv)
                    else:
                        self.assertIn(tuple(argv[1:3]), READ_ONLY, argv)
                covered.add(report["state"])
        self.assertEqual(covered, set(ci_watch.STATES))

    def test_conflict_is_decided_before_any_run_is_read(self) -> None:
        _, fake, report = run_fixture("conflict")
        self.assertEqual(report["state"], "conflict")
        self.assertFalse([argv for argv in fake.calls if argv[1] == "run"])

    def test_aggregate_check_view_is_never_consulted(self) -> None:
        fixture, fake, report = run_fixture("aggregate-green-trap")
        self.assertEqual(fixture["pr"][0]["statusCheckRollup"][0]["conclusion"], "SUCCESS")
        self.assertEqual(report["state"], "red-at-diff")
        flattened = " ".join(" ".join(argv) for argv in fake.calls)
        self.assertNotIn("statusCheckRollup", flattened)
        self.assertNotIn(" checks", flattened)
        # It kept polling through the polls with no run instead of reporting the empty list as green.
        self.assertGreaterEqual(len([argv for argv in fake.calls if "head_sha=" in argv[-1]]), 4)

    def test_runs_for_other_commits_are_ignored(self) -> None:
        fixture = json.loads((FIXTURES / "green.json").read_text(encoding="utf-8"))
        for poll in fixture["polls"]:
            for run in poll["runs"]:
                run["head_sha"] = "0" * 40
        fake, clock = FakeGh(fixture), Clock(fixture["start"])
        report = ci_watch.watch(ci_watch.Gh(runner=fake, which=lambda _: "gh"), fixture["repo"], pr=67,
                                cap_seconds=120, stall_seconds=1800, poll_seconds=30, now=clock.now, sleep=clock.sleep)
        self.assertEqual(report["state"], "no-run-registered")

    def test_cap_holds_across_slow_reads(self) -> None:
        # Each gh call takes 40 s here; the watch must stop at the 60 s cap, not after the reads.
        fixture = json.loads((FIXTURES / "green.json").read_text(encoding="utf-8"))
        clock = Clock(fixture["start"])
        started = clock.now()
        timeouts = []

        class SlowGh(FakeGh):
            def __call__(self, argv, **kwargs):
                timeouts.append((kwargs.get("timeout"), 60 - (clock.now() - started)))
                clock.sleep(40)
                return super().__call__(argv, **kwargs)
        report = ci_watch.watch(ci_watch.Gh(runner=SlowGh(fixture), which=lambda _: "gh"), fixture["repo"], pr=67,
                                cap_seconds=60, stall_seconds=1800, poll_seconds=30, now=clock.now, sleep=clock.sleep)
        self.assertEqual(report["state"], "cap-reached", report)
        self.assertLessEqual(report["elapsed_seconds"], 60 + 40)
        for timeout, remaining in timeouts:
            self.assertLessEqual(timeout, max(1, remaining) + 1e-6)

    def test_a_read_that_outlasts_the_cap_ends_as_cap_reached(self) -> None:
        fixture = json.loads((FIXTURES / "green.json").read_text(encoding="utf-8"))
        clock = Clock(fixture["start"])

        class HangingGh(FakeGh):
            def __call__(self, argv, **kwargs):
                if "--commit" in argv or (argv[1] == "api" and "head_sha" in argv[-1]):
                    clock.sleep(kwargs["timeout"])
                    raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
                return super().__call__(argv, **kwargs)
        report = ci_watch.watch(ci_watch.Gh(runner=HangingGh(fixture), which=lambda _: "gh"), fixture["repo"], pr=67,
                                cap_seconds=60, stall_seconds=1800, poll_seconds=30, now=clock.now, sleep=clock.sleep)
        self.assertEqual(report["state"], "cap-reached", report)
        self.assertLessEqual(report["elapsed_seconds"], 61)

    def many_runs(self, failing_last: bool, registered: int | None = None) -> dict:
        fixture = json.loads((FIXTURES / "red-at-diff.json").read_text(encoding="utf-8"))
        poll = fixture["polls"][0]
        template_run, passing_view = poll["runs"][0], json.loads(json.dumps(poll["views"]["100"]))
        for job in passing_view["jobs"]:
            job["conclusion"] = "success"
            for step in job["steps"]:
                step["conclusion"] = "success"
        passing_view["conclusion"] = "success"
        # The passing runs belong to another workflow, so they do not make the failure look flaky.
        passing_view["workflowDatabaseId"] = template_run["workflow_id"] + 1
        runs, views = [], {}
        for index in range(101):
            run_id = 1000 + index
            failing = failing_last and index == 100
            runs.append({**template_run, "id": run_id, "conclusion": "failure" if failing else "success",
                         "workflow_id": template_run["workflow_id"] + (0 if failing else 1)})
            views[str(run_id)] = poll["views"]["100"] if failing else passing_view
        fixture["polls"] = [{"runs": runs, "views": views, **({"registered": registered} if registered else {})}]
        return fixture

    def watch_fixture(self, fixture: dict) -> dict:
        clock = Clock(fixture["start"])
        return ci_watch.watch(ci_watch.Gh(runner=FakeGh(fixture), which=lambda _: "gh"), fixture["repo"], pr=67,
                              cap_seconds=600, stall_seconds=1800, poll_seconds=30, now=clock.now, sleep=clock.sleep)

    def test_every_registered_run_is_read_past_one_hundred(self) -> None:
        # The 101st run fails; a watch that reads only 100 runs reports green.
        self.assertEqual(self.watch_fixture(self.many_runs(failing_last=True))["state"], "red-at-diff")

    def test_a_partial_run_list_fails_closed(self) -> None:
        with self.assertRaisesRegex(ci_watch.GhError, "read 101 of 102"):
            self.watch_fixture(self.many_runs(failing_last=False, registered=102))

    def test_pr_watch_ignores_runs_of_the_same_sha_from_another_branch_or_fork(self) -> None:
        # The same commit can be pushed to an unrelated branch or a fork; those runs do not test this PR.
        for field, value in (("head_branch", "someone-else"), ("head_repository", {"full_name": "fork/agentsmith"})):
            with self.subTest(field=field):
                fixture = json.loads((FIXTURES / "green.json").read_text(encoding="utf-8"))
                for poll in fixture["polls"]:
                    for run in poll["runs"]:
                        run[field] = value
                self.assertEqual(self.watch_fixture(fixture)["state"], "no-run-registered")
        fixture = json.loads((FIXTURES / "green.json").read_text(encoding="utf-8"))
        for poll in fixture["polls"]:
            for run in poll["runs"]:
                run["head_repository"] = {"full_name": "promptpartner/AgentSmith"}  # names ignore case
        self.assertEqual(self.watch_fixture(fixture)["state"], "green")

    def test_exit_codes_are_distinct_and_documented(self) -> None:
        codes = [ci_watch.STATES[state][0] for state in ci_watch.STATES]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(ci_watch.STATES["green"][0], 0)
        doc = DOC.read_text(encoding="utf-8")
        for state, (code, _) in ci_watch.STATES.items():
            with self.subTest(state=state):
                self.assertIn(f"| `{state}` | {code} |", doc)

    def test_report_json_is_sorted_ascii(self) -> None:
        _, _, report = run_fixture("green")
        text = ci_watch.to_json(report)
        self.assertEqual(json.loads(text), report)
        self.assertEqual(text, json.dumps(report, sort_keys=True, ensure_ascii=True) + "\n")


class GhTests(unittest.TestCase):
    def test_missing_gh_fails_with_a_clear_message(self) -> None:
        with self.assertRaisesRegex(ci_watch.GhError, "GitHub CLI .gh. is not installed"):
            ci_watch.Gh(runner=lambda *a, **k: None, which=lambda _: None).check()

    def test_unauthenticated_gh_fails_with_a_clear_message(self) -> None:
        def runner(argv, **_):
            return subprocess.CompletedProcess(argv, 1, "", "You are not logged into any GitHub hosts.")
        with self.assertRaisesRegex(ci_watch.GhError, "gh auth login"):
            ci_watch.Gh(runner=runner, which=lambda _: "gh").check()

    def test_attempt_jobs_are_read_from_every_page_and_normalised(self) -> None:
        fixture = json.loads((FIXTURES / "flaky.json").read_text(encoding="utf-8"))
        jobs = ci_watch.Gh(runner=FakeGh(fixture), which=lambda _: "gh").attempt_jobs(fixture["repo"], 100, 1)
        self.assertEqual([job["name"] for job in jobs], ["compatibility (macos-latest)", "compatibility (ubuntu-latest)"])
        self.assertEqual((jobs[1]["conclusion"], jobs[1]["completedAt"]), ("success", "2026-11-06T15:04:00Z"))

    def test_a_partial_job_list_fails_closed(self) -> None:
        fixture = json.loads((FIXTURES / "flaky.json").read_text(encoding="utf-8"))
        fixture["attempts"]["100/1"][1]["jobs"] = []
        with self.assertRaisesRegex(ci_watch.GhError, "read 1 of 2 jobs"):
            ci_watch.Gh(runner=FakeGh(fixture), which=lambda _: "gh").attempt_jobs(fixture["repo"], 100, 1)


class CliTests(unittest.TestCase):
    def cli(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(CORE), "ci", "watch", *args], capture_output=True, text=True,
                              env=env or CLEAN_ENV, timeout=60)

    def test_cli_without_gh_exits_2_and_names_the_fix(self) -> None:
        with tempfile.TemporaryDirectory() as empty:
            result = self.cli("--sha", "a" * 40, "--repo", "owner/name", env={**CLEAN_ENV, "PATH": empty})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("gh", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_cli_rejects_a_short_sha_and_needs_one_target(self) -> None:
        short = self.cli("--sha", "abc123", "--repo", "owner/name")
        self.assertEqual(short.returncode, 2)
        self.assertIn("full 40- or 64-character", short.stderr)
        missing = self.cli("--repo", "owner/name")
        self.assertEqual(missing.returncode, 2)
        self.assertIn("--pr", missing.stderr)
        self.assertNotIn("unrecognized arguments", short.stderr + missing.stderr)

    def test_cli_help_lists_states_and_exit_codes(self) -> None:
        result = self.cli("--help", env={**CLEAN_ENV, "COLUMNS": "400"})
        self.assertEqual(result.returncode, 0, result.stderr)
        for state, (code, _) in ci_watch.STATES.items():
            self.assertIn(f"{state}={code}", " ".join(result.stdout.split()))


if __name__ == "__main__":
    unittest.main()
