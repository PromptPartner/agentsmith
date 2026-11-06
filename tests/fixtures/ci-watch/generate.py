"""Write tests/fixtures/ci-watch/*.json: gh outputs in the shapes recorded from
PromptPartner/agentsmith on 2026-11-06 (gh 2.101.0), arranged per end state."""
import datetime as dt
import json
import sys
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)
REPO = "PromptPartner/agentsmith"
SHA = "884ab3cfbaf1b05e7557712c2108a99b0284c9fe"
BASE_SHA = "610914b5c8c24904de0259d70b74cb0d9b0289a4"
WORKFLOW = 365097755
START = "2026-11-06T15:00:00Z"


def ts(minutes: float) -> str:
    moment = dt.datetime(2026, 11, 6, 15, tzinfo=dt.timezone.utc) + dt.timedelta(minutes=minutes)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def pr(mergeable="MERGEABLE", state="BLOCKED", rollup="SUCCESS"):
    # statusCheckRollup is what an aggregate view reads; the watch must never trust it.
    return {"number": 67, "headRefOid": SHA, "baseRefName": "master", "state": "OPEN",
            "mergeable": mergeable, "mergeStateStatus": state,
            "statusCheckRollup": [{"__typename": "CheckRun", "name": "compatibility (ubuntu-latest)",
                                   "status": "COMPLETED", "conclusion": rollup}]}


def listed(run_id, event, status, conclusion="", attempt=1, created=0.5, updated=0.5):
    return {"attempt": attempt, "conclusion": conclusion, "createdAt": ts(created), "databaseId": run_id,
            "event": event, "headBranch": "fix/verify-git-env-isolation", "headSha": SHA, "name": "verify",
            "status": status, "updatedAt": ts(updated), "workflowDatabaseId": WORKFLOW, "workflowName": "verify"}


def step(number, name, conclusion="success", status="completed", start=1.0, end=1.1):
    return {"completedAt": ts(end) if status == "completed" else "0001-01-01T00:00:00Z",
            "conclusion": conclusion if status == "completed" else "", "name": name, "number": number,
            "startedAt": ts(start), "status": status}


def job(job_id, name, conclusion="success", status="completed", failed_step=None, start=1.0, end=5.0):
    steps = [step(1, "Set up job", start=start, end=start + 0.1),
             step(2, "Run actions/checkout@v7", start=start + 0.1, end=start + 0.2)]
    if failed_step == "Set up job":
        steps = [step(1, "Set up job", "failure", start=start, end=start + 0.1)]
    elif status != "completed":
        steps.append(step(3, "Python core compiles", status="in_progress", start=start + 0.2))
    else:
        steps.append(step(3, failed_step or "Python core compiles",
                          "failure" if failed_step else "success", start=start + 0.2, end=end))
    return {"completedAt": ts(end) if status == "completed" else "0001-01-01T00:00:00Z",
            "conclusion": conclusion if status == "completed" else "", "databaseId": job_id, "name": name,
            "startedAt": ts(start), "status": status, "steps": steps,
            "url": f"https://github.com/{REPO}/actions/runs/1/job/{job_id}"}


def view(run_id, event, status, conclusion, jobs, attempt=1, created=0.5, updated=5.0, sha=SHA, branch=None):
    return {"attempt": attempt, "conclusion": conclusion, "createdAt": ts(created), "event": event,
            "headBranch": branch or "fix/verify-git-env-isolation", "headSha": sha, "jobs": jobs,
            "status": status, "updatedAt": ts(updated), "workflowDatabaseId": WORKFLOW, "workflowName": "verify"}


UBUNTU, MAC = "compatibility (ubuntu-latest)", "compatibility (macos-latest)"


def passing_jobs(start=1.0, end=5.0, offset=0):
    return [job(500 + offset, UBUNTU, start=start, end=end), job(501 + offset, MAC, start=start, end=end)]


def failing_jobs(failed="Risk map contracts and byte-identical JSON", conclusion="failure", offset=0):
    return [job(500 + offset, UBUNTU, conclusion, failed_step=failed), job(501 + offset, MAC)]


def base(jobs_conclusion="success"):
    jobs = [job(900, UBUNTU, jobs_conclusion,
                failed_step="Risk map contracts and byte-identical JSON" if jobs_conclusion == "failure" else None),
            job(901, MAC)]
    return {"list": [{"databaseId": 7000, "headSha": BASE_SHA, "event": "push", "status": "completed",
                      "conclusion": "failure" if jobs_conclusion == "failure" else "success"}],
            "view": view(7000, "push", "completed", "failure" if jobs_conclusion == "failure" else "success",
                         jobs, sha=BASE_SHA, branch="master")}


def completed_failure(jobs, offset=0):
    return {"runs": [listed(100, "push", "completed", "failure", updated=5.0)],
            "views": {"100": view(100, "push", "completed", "failure", jobs)}}


def write(name, description, expect, polls, pr_polls=(pr(),), base_run=None, attempts=None, mode="pr",
          cap=60, stall=30):
    data = {"description": description, "repo": REPO, "mode": mode, "sha": SHA, "start": START,
            "poll_seconds": 30, "cap_minutes": cap, "stall_minutes": stall, "pr": list(pr_polls),
            "default_branch": "master", "polls": polls, "base": base_run or base(), "attempts": attempts or {},
            "expect": expect}
    (OUT / f"{name}.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")


running = {"runs": [listed(100, "push", "in_progress", updated=1.0)],
           "views": {"100": view(100, "push", "in_progress", "", [job(500, UBUNTU, status="in_progress"),
                                                                    job(501, MAC, status="in_progress")],
                                 updated=1.0)}}
green_done = {"runs": [listed(100, "push", "completed", "success", updated=5.0),
                       listed(101, "pull_request", "completed", "success", updated=5.0)],
              "views": {"100": view(100, "push", "completed", "success", passing_jobs()),
                        "101": view(101, "pull_request", "completed", "success", passing_jobs(offset=10))}}

write("green", "GitHub is still computing mergeability, then both runs for the head SHA pass.",
      {"state": "green", "exit": 0}, [running, green_done], pr_polls=(pr("UNKNOWN", "UNKNOWN"), pr()))
write("aggregate-green-trap", "The PR's aggregate check view reports SUCCESS from an earlier head before any "
      "run exists for this SHA; the real run then fails.",
      {"state": "red-at-diff", "exit": 10},
      [{"runs": [], "views": {}}, {"runs": [], "views": {}}, running, completed_failure(failing_jobs())])
write("red-at-diff", "A test job fails on the head SHA and the same job passes on the base branch's latest run.",
      {"state": "red-at-diff", "exit": 10}, [completed_failure(failing_jobs())])
write("red-on-base", "The failing job also fails on the base branch's latest run of the same workflow.",
      {"state": "red-on-base", "exit": 11}, [completed_failure(failing_jobs())], base_run=base("failure"))
write("flaky", "Attempt 2 fails a job that passed in attempt 1 of the same run; nothing is rerun by the watch.",
      {"state": "flaky", "exit": 12},
      [{"runs": [listed(100, "push", "completed", "failure", attempt=2, updated=5.0)],
        "views": {"100": view(100, "push", "completed", "failure", failing_jobs(), attempt=2)}}],
      attempts={"100/1": {"total_count": 2, "jobs": [
          {"id": 400, "name": UBUNTU, "status": "completed", "conclusion": "success", "run_attempt": 1,
           "started_at": ts(1.0), "completed_at": ts(4.0), "steps": []},
          {"id": 401, "name": MAC, "status": "completed", "conclusion": "failure", "run_attempt": 1,
           "started_at": ts(1.0), "completed_at": ts(4.0), "steps": []}]}})
write("environment", "The runner failed in 'Set up job' before any project step ran.",
      {"state": "environment", "exit": 13}, [completed_failure(failing_jobs(failed="Set up job"))])
write("environment-timeout", "A job hit the hosted timeout (conclusion timed_out).",
      {"state": "environment", "exit": 13}, [completed_failure(failing_jobs(conclusion="timed_out"))])
stalled_view = view(100, "push", "queued", "", [], created=-40.0, updated=-40.0)
write("runner-stalled", "The run has been queued for 40 minutes with no job started.",
      {"state": "runner-stalled", "exit": 14},
      [{"runs": [listed(100, "push", "queued", created=-40.0, updated=-40.0)], "views": {"100": stalled_view}}])
write("no-run-registered", "No workflow run is ever registered for the head SHA.",
      {"state": "no-run-registered", "exit": 15}, [{"runs": [], "views": {}}], cap=3)
write("conflict", "The PR conflicts with its base; the watch must not look at runs.",
      {"state": "conflict", "exit": 16}, [green_done], pr_polls=(pr("CONFLICTING", "DIRTY"),))


def progressing(minute):
    return {"runs": [listed(100, "push", "in_progress", updated=minute)],
            "views": {"100": view(100, "push", "in_progress", "",
                                  [job(500, UBUNTU, status="in_progress", start=minute - 0.2),
                                   job(501, MAC, status="in_progress", start=minute - 0.2)], updated=minute)}}


write("cap-reached", "Runs keep making progress past a 2-minute cap.", {"state": "cap-reached", "exit": 17},
      [progressing(0.5 * index) for index in range(1, 8)], cap=2)
write("sha-mode-green", "Watching a bare SHA: no PR lookup, base from the repository's default branch.",
      {"state": "green", "exit": 0}, [green_done], pr_polls=(), mode="sha")
