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
            return self.reply(fixture["polls"][self.poll_index]["runs"])
        if verb == ("run", "list") and "--branch" in argv:
            return self.reply(fixture["base"]["list"])
        if verb == ("run", "view"):
            run_id = argv[3]
            if run_id == str(fixture["base"]["list"][0]["databaseId"]):
                return self.reply(fixture["base"]["view"])
            return self.reply(fixture["polls"][max(self.poll_index, 0)]["views"][run_id])
        if argv[1] == "api":
            key = "/".join(argv[2].split("?")[0].split("/")[5:8:2])
            return self.reply(fixture["attempts"][key])
        raise AssertionError(f"unexpected gh call: {argv}")

    @staticmethod
    def reply(value: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, value if isinstance(value, str) else json.dumps(value), "")


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
        self.assertGreaterEqual(len([argv for argv in fake.calls if "--commit" in argv]), 4)

    def test_runs_for_other_commits_are_ignored(self) -> None:
        fixture = json.loads((FIXTURES / "green.json").read_text(encoding="utf-8"))
        for poll in fixture["polls"]:
            for run in poll["runs"]:
                run["headSha"] = "0" * 40
        fake, clock = FakeGh(fixture), Clock(fixture["start"])
        report = ci_watch.watch(ci_watch.Gh(runner=fake, which=lambda _: "gh"), fixture["repo"], pr=67,
                                cap_seconds=120, stall_seconds=1800, poll_seconds=30, now=clock.now, sleep=clock.sleep)
        self.assertEqual(report["state"], "no-run-registered")

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

    def test_attempt_jobs_are_normalised_to_run_view_shape(self) -> None:
        fixture = json.loads((FIXTURES / "flaky.json").read_text(encoding="utf-8"))
        jobs = ci_watch.Gh(runner=FakeGh(fixture), which=lambda _: "gh").attempt_jobs(fixture["repo"], 100, 1)
        self.assertEqual(jobs[0]["name"], "compatibility (ubuntu-latest)")
        self.assertEqual((jobs[0]["conclusion"], jobs[0]["completedAt"]), ("success", "2026-11-06T15:04:00Z"))


if __name__ == "__main__":
    unittest.main()
