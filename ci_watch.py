"""Report-only CI watch for one commit (standard library only; GitHub through the `gh` CLI).

The watch checks merge conflicts first, then follows the workflow runs registered for the exact
head SHA. It never reads an aggregate check view: right after a push that view can report green
before the real run exists. It stops at one wall-clock cap and ends in exactly one named state.
It never fixes, pushes, comments, labels or reruns; every gh call it makes is a read.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import time
from typing import Any, Callable

SCHEMA_VERSION = 1
# state: (exit code, next step). {sha}, {base}, {job}, {run}, {repo}, {minutes} are filled in per report.
STATES: dict[str, tuple[int, str]] = {
    "green": (0, "Every run for {sha} passed; the pull request waits for a human merge."),
    "red-at-diff": (10, "Job '{job}' fails on this change; read gh run view {run} --repo {repo} --log-failed, fix the change, do not rerun."),
    "red-on-base": (11, "Job '{job}' also fails on {base}'s latest run; fix or report {base} first, this change is not the cause."),
    "flaky": (12, "Job '{job}' passed on another attempt of this commit; record it as flaky and ask the operator before any rerun."),
    "environment": (13, "Job '{job}' failed in runner setup or hit a hosted limit, not in the tests; check GitHub's status, then ask the operator before any rerun."),
    "runner-stalled": (14, "Run {run} made no progress for {minutes} minutes; check the runner queue on GitHub, the watch cancelled nothing."),
    "no-run-registered": (15, "No workflow run exists for {sha}; check that the push reached GitHub and that a workflow triggers on it."),
    "conflict": (16, "The pull request conflicts with {base}; resolve the conflict and push before any run counts."),
    "cap-reached": (17, "Runs were still going after {minutes} minutes; run the watch again later."),
}
# Most actionable first: when jobs fail for different reasons, the report names the first.
FAILURE_ORDER = ("red-at-diff", "red-on-base", "environment", "flaky")
PASSING = {"success", "skipped", "neutral"}
ENVIRONMENT_CONCLUSIONS = {"timed_out", "startup_failure", "cancelled", "stale"}
# A first failing step that only prepares the runner: the project's own commands never ran.
SETUP_STEP = re.compile(r"(Set up job|Set up runner|Initialize containers|Run actions/(checkout|setup-[a-z-]+|cache|"
                        r"download-artifact|upload-artifact)@.*)\Z")
REGISTRATION_SECONDS = 300
NO_TIME = "0001-01-01T00:00:00Z"
RUN_FIELDS = "databaseId,attempt,status,conclusion,event,headSha,workflowDatabaseId,workflowName,createdAt,updatedAt"


class GhError(RuntimeError):
    """gh is missing, not logged in, or a read failed."""


class Gh:
    """Thin read-only adapter over the gh CLI. `runner` and `which` are injectable for tests."""

    def __init__(self, runner: Callable[..., Any] = subprocess.run,
                 which: Callable[[str], str | None] = shutil.which) -> None:
        self.runner, self.which = runner, which

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        try:
            return self.runner(["gh", *args], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GhError(f"gh {' '.join(args[:2])} failed: {exc}") from None

    def _json(self, *args: str) -> Any:
        result = self._run(*args)
        if result.returncode:
            lines = (result.stderr or "").strip().splitlines()
            raise GhError(f"gh {' '.join(args[:2])} failed: {lines[-1] if lines else 'exit ' + str(result.returncode)}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            raise GhError(f"gh {' '.join(args[:2])} returned no JSON") from None

    def check(self) -> None:
        if not self.which("gh"):
            raise GhError("GitHub CLI (gh) is not installed; install it from https://cli.github.com, "
                          "then run `gh auth login`")
        if self._run("auth", "status").returncode:
            raise GhError("gh is not logged in to GitHub; run `gh auth login` and try again")

    def repo(self) -> str:
        return self._json("repo", "view", "--json", "nameWithOwner")["nameWithOwner"]

    def default_branch(self, repo: str) -> str:
        return self._json("repo", "view", repo, "--json", "defaultBranchRef")["defaultBranchRef"]["name"]

    def pr(self, repo: str, number: int) -> dict[str, Any]:
        return self._json("pr", "view", str(number), "--repo", repo, "--json",
                          "headRefOid,baseRefName,mergeable,mergeStateStatus,state")

    def runs(self, repo: str, sha: str) -> list[dict[str, Any]]:
        return self._json("run", "list", "--repo", repo, "--commit", sha, "--limit", "100", "--json", RUN_FIELDS)

    def run(self, repo: str, run_id: int) -> dict[str, Any]:
        return self._json("run", "view", str(run_id), "--repo", repo, "--json", RUN_FIELDS.replace("databaseId,", "") + ",jobs")

    def attempt_jobs(self, repo: str, run_id: int, attempt: int) -> list[dict[str, Any]]:
        # GET only. The REST shape is snake_case; return the shape `gh run view --json jobs` uses.
        jobs = self._json("api", f"repos/{repo}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")["jobs"]
        return [{"databaseId": job.get("id"), "name": job.get("name"), "status": job.get("status"),
                 "conclusion": job.get("conclusion") or "", "startedAt": job.get("started_at") or NO_TIME,
                 "completedAt": job.get("completed_at") or NO_TIME, "steps": job.get("steps") or []} for job in jobs]

    def base_run(self, repo: str, branch: str, workflow_id: int) -> dict[str, Any] | None:
        listed = self._json("run", "list", "--repo", repo, "--branch", branch, "--workflow", str(workflow_id),
                            "--event", "push", "--status", "completed", "--limit", "1", "--json",
                            "databaseId,headSha,conclusion")
        return self.run(repo, listed[0]["databaseId"]) if listed else None


def _seconds(stamp: str | None) -> float | None:
    if not stamp or stamp == NO_TIME:
        return None
    return dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()


def last_progress(view: dict[str, Any]) -> float:
    """The latest moment anything in the run started, finished or changed."""
    stamps = [view.get("createdAt"), view.get("updatedAt")]
    for job in view.get("jobs") or []:
        stamps += [job.get("startedAt"), job.get("completedAt")]
        for step in job.get("steps") or []:
            stamps += [step.get("startedAt"), step.get("completedAt")]
    return max(value for value in map(_seconds, stamps) if value is not None)


def _failing(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [job for job in jobs if job.get("status") == "completed" and job.get("conclusion") not in PASSING]


def _category(job: dict[str, Any], view: dict[str, Any], others: list[dict[str, Any]],
              base: dict[str, Any] | None) -> str:
    if job.get("conclusion") in ENVIRONMENT_CONCLUSIONS:
        return "environment"
    failed = [step for step in job.get("steps") or [] if step.get("conclusion") not in PASSING | {None, ""}]
    if failed and SETUP_STEP.fullmatch(failed[0].get("name", "")):
        return "environment"
    if base and any(other.get("name") == job.get("name") and other.get("conclusion") == "failure"
                    for other in base.get("jobs") or []):
        return "red-on-base"
    # Flaky without rerunning: the same job passed on an earlier attempt of this run, or in another run
    # of the same workflow and event for this commit (a pull_request run tests a merge, so not that one).
    if any(other.get("name") == job.get("name") and other.get("conclusion") == "success" for other in others):
        return "flaky"
    return "red-at-diff"


def watch(gh: Gh, repo: str | None, *, pr: int | None = None, sha: str | None = None,
          base: str | None = None, cap_seconds: float = 3600, stall_seconds: float = 1800,
          poll_seconds: float = 30, now: Callable[[], float] = time.time,
          sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """Watch until one end state. Exactly one of `pr` and `sha` is given."""
    if (pr is None) == (sha is None):
        raise ValueError("watch needs exactly one of pr and sha")
    gh.check()
    repo = repo or gh.repo()
    started = now()
    runs_report: list[dict[str, Any]] = []

    def finish(state: str, job: str = "", run: Any = "", minutes: float = 0) -> dict[str, Any]:
        code, template = STATES[state]
        return {"schema_version": SCHEMA_VERSION, "state": state, "exit_code": code,
                "next_step": template.format(sha=sha, base=base, job=job, run=run, repo=repo, minutes=int(minutes)),
                "repo": repo, "pr": pr, "sha": sha, "base": base,
                "elapsed_seconds": int(now() - started), "runs": runs_report}

    if pr is not None:
        while True:
            info = gh.pr(repo, pr)
            base = base or info.get("baseRefName")
            sha = info.get("headRefOid")
            if info.get("mergeable") == "CONFLICTING" or info.get("mergeStateStatus") == "DIRTY":
                return finish("conflict")
            if info.get("mergeable") != "UNKNOWN":
                break
            # GitHub computes mergeability after a push; wait for it rather than guess.
            if now() - started >= cap_seconds:
                return finish("cap-reached", minutes=cap_seconds / 60)
            sleep(poll_seconds)
    base = base or gh.default_branch(repo)
    while True:
        moment = now()
        runs = sorted((run for run in gh.runs(repo, sha) if run.get("headSha") == sha),
                      key=lambda run: run["databaseId"])
        views = {run["databaseId"]: gh.run(repo, run["databaseId"]) for run in runs}
        runs_report[:] = [{"id": run_id, "workflow": view.get("workflowName"), "event": view.get("event"),
                           "attempt": view.get("attempt"), "status": view.get("status"),
                           "conclusion": view.get("conclusion") or "", "failing_jobs": []}
                          for run_id, view in views.items()]
        elapsed = moment - started
        if not runs:
            if elapsed >= min(REGISTRATION_SECONDS, cap_seconds):
                return finish("no-run-registered")
        elif all(view.get("status") == "completed" for view in views.values()):
            return _completed(gh, repo, views, runs_report, base, finish)
        else:
            for run_id, view in views.items():
                if view.get("status") != "completed" and moment - last_progress(view) > stall_seconds:
                    return finish("runner-stalled", run=run_id, minutes=(moment - last_progress(view)) / 60)
        if elapsed >= cap_seconds:
            return finish("cap-reached", minutes=cap_seconds / 60)
        sleep(poll_seconds)


def _completed(gh: Gh, repo: str, views: dict[int, dict[str, Any]], runs_report: list[dict[str, Any]],
               base: str, finish: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    base_runs: dict[Any, dict[str, Any] | None] = {}
    found: list[tuple[str, str, int]] = []
    for row, (run_id, view) in zip(runs_report, views.items()):
        jobs = view.get("jobs") or []
        failing = _failing(jobs)
        if not failing and view.get("conclusion") in PASSING:
            continue
        workflow = view.get("workflowDatabaseId")
        if workflow not in base_runs:
            base_runs[workflow] = gh.base_run(repo, base, workflow)
        others = [job for attempt in range(1, int(view.get("attempt") or 1))
                  for job in gh.attempt_jobs(repo, run_id, attempt)]
        others += [job for other_id, other in views.items() if other_id != run_id
                   and other.get("workflowDatabaseId") == workflow and other.get("event") == view.get("event")
                   for job in other.get("jobs") or []]
        if not failing:
            # The run failed without a failing job (for example startup_failure): nothing of ours ran.
            row["failing_jobs"].append({"id": None, "name": view.get("workflowName"), "category": "environment"})
            found.append(("environment", view.get("workflowName") or "", run_id))
        for job in failing:
            category = _category(job, view, others, base_runs[workflow])
            row["failing_jobs"].append({"id": job.get("databaseId"), "name": job.get("name"), "category": category})
            found.append((category, job.get("name") or "", run_id))
    if not found:
        return finish("green")
    category, job, run_id = min(found, key=lambda item: (FAILURE_ORDER.index(item[0]), item[2], item[1]))
    return finish(category, job=job, run=run_id)


def to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, sort_keys=True, ensure_ascii=True) + "\n"


def render_text(report: dict[str, Any]) -> str:
    target = f"PR #{report['pr']} " if report["pr"] is not None else ""
    lines = [f"state: {report['state']} (exit {report['exit_code']})",
             f"commit: {target}{report['sha']} on {report['repo']}, base {report['base']}",
             f"next: {report['next_step']}"]
    for run in report["runs"]:
        lines.append(f"  run {run['id']} {run['workflow']} ({run['event']}, attempt {run['attempt']}): "
                     f"{run['conclusion'] or run['status']}")
        for job in run["failing_jobs"]:
            lines.append(f"    {job['category']}: {job['name']}")
    return "\n".join(lines) + "\n"
