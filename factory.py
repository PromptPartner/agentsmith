#!/usr/bin/env python3
"""Readiness and numbers for autonomous runs, derived from what is already recorded.

Nothing here is a stored board: every report is computed from run state, `events.jsonl`, the
operator's own logs and read-only GitHub reads. `readiness` and `numbers` write nothing in the
repository or its Git folder (the checker preflight uses a throwaway system temporary folder) and switch
nothing on. The only writers are `export` (to a folder the operator names), the two operator
logs (`defect add`, `minutes add`) under the Git folder, and `intake` with a verdict: its record under
the Git folder and, when asked, one new `status: draft` spec. Intake reads GitHub and never writes to it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Iterable
import unicodedata

SCHEMA_VERSION = 1
# Below this many cases a number says "insufficient data" instead of a value that looks precise.
MIN_SAMPLE = 5
DEFAULT_WINDOW_DAYS = 28
TOUCH_EVENTS = ("run_escalated", "run_interrupted", "run_resumed")
TERMINAL = ("accepted", "escalated", "interrupted")
TIERS = ("A", "B", "C", "human")
PASSING = {"success", "skipped", "neutral"}
GITHUB_DEFAULT_TIMEOUT_MINUTES = 360
OPERATING_SYSTEMS = (("windows", ("windows",)), ("macos", ("macos", "mac-os", "osx")),
                     ("linux", ("ubuntu", "linux")))
REPOSITORY_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                  "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
                  "GIT_PREFIX", "GIT_IMPLICIT_WORK_TREE", "GIT_NAMESPACE")


class FactoryError(RuntimeError):
    pass


def git(repo: Path, *args: str, check: bool = True) -> str:
    # Hooks export GIT_DIR and friends; they would point `-C repo` at another repository.
    env = {key: value for key, value in os.environ.items() if key not in REPOSITORY_ENV}
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                            errors="replace", env=env, check=False)
    if check and result.returncode:
        raise FactoryError(f"git {args[0]} failed: {result.stderr.strip() or result.returncode}")
    return result.stdout.strip() if result.returncode == 0 else ""


def common_dir(repo: Path) -> Path:
    value = git(repo, "rev-parse", "--git-common-dir")
    path = Path(value)
    return (path if path.is_absolute() else repo / path).resolve()


def github_slug(repo: Path, remote: str = "origin") -> str | None:
    """owner/name of the target's GitHub remote, so CI is read for that repository and not for
    whatever repository the current folder belongs to. None when the remote is not on GitHub."""
    url = git(repo, "remote", "get-url", remote, check=False)
    match = re.fullmatch(r"(?:git@github\.com:|ssh://git@github\.com/|https://(?:[^@/]+@)?github\.com/)"
                         r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?", url)
    return match.group(1) if match else None


def factory_dir(repo: Path) -> Path:
    return common_dir(repo) / "agentsmith-factory"


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Records from a JSON-lines file; a line that is not a JSON object is skipped, not fatal."""
    if not path.is_file():
        return []
    records = []
    for line in path.read_bytes().decode("utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def load_runs(repo: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Every run's state and events. Unreadable runs are named, never guessed."""
    runs, unreadable = [], []
    root = common_dir(repo) / "agentsmith-runs"
    for folder in sorted(root.iterdir() if root.is_dir() else []):
        state_file = folder / "state.json"
        if folder.is_symlink() or not folder.is_dir() or not state_file.is_file():
            continue
        try:
            state = json.loads(state_file.read_bytes().decode("utf-8"))
        except (OSError, ValueError) as exc:
            unreadable.append(f"{folder.name}: {exc}")
            continue
        if not isinstance(state, dict):
            unreadable.append(f"{folder.name}: state is not a JSON object")
            continue
        runs.append({"id": folder.name, "folder": folder, "state": state,
                     "events": read_jsonl(folder / "events.jsonl")})
    return runs, unreadable


def window(since: str | None, now: datetime) -> tuple[datetime, datetime]:
    if since is None:
        return now - timedelta(days=DEFAULT_WINDOW_DAYS), now
    start = parse_time(since if "T" in since else since + "T00:00:00+00:00")
    if start is None:
        raise FactoryError(f"--since needs a date such as 2026-10-01, not {since!r}")
    if start > now:
        raise FactoryError(f"--since {since} is after now")
    return start, now


def within(value: Any, start: datetime, end: datetime) -> bool:
    """A record counts only inside [start, end]: before the window or in the future, it does not."""
    moment = parse_time(value)
    return moment is not None and start <= moment <= end


def number(name: str, n: int, value: Any, unit: str, start: datetime, end: datetime,
           detail: str = "", minimum: int = MIN_SAMPLE) -> dict[str, Any]:
    enough = n >= minimum
    return {"name": name, "n": n, "value": value if enough else None, "unit": unit,
            "status": "ok" if enough else "insufficient data",
            "window": {"since": start.isoformat(timespec="seconds"), "until": end.isoformat(timespec="seconds")},
            "detail": detail if enough else f"{n} case(s); at least {minimum} are needed" + (f"; {detail}" if detail else "")}


def touches(run: dict[str, Any]) -> int:
    return sum(1 for item in run["events"] if item.get("event") in TOUCH_EVENTS)


def red_time(ci_runs: list[dict[str, Any]], start: datetime, end: datetime,
             seeds: list[dict[str, Any]] = ()) -> float:
    """Seconds in [start, end] during which the latest completed run of any workflow was failing.
    `seeds` are the last runs before the window, so a workflow already red at its start counts."""
    ordered = sorted((run for run in ci_runs if parse_time(run.get("updated_at"))),
                     key=lambda run: parse_time(run["updated_at"]))
    failing: dict[Any, bool] = {}
    for run in sorted((run for run in seeds if parse_time(run.get("updated_at"))),
                      key=lambda run: parse_time(run["updated_at"])):
        failing[run.get("workflow_id") or run.get("name")] = run.get("conclusion") not in PASSING
    red, since = 0.0, start
    for run in ordered:
        moment = min(max(parse_time(run["updated_at"]), start), end)
        if any(failing.values()):
            red += (moment - since).total_seconds()
        since = moment
        failing[run.get("workflow_id") or run.get("name")] = run.get("conclusion") not in PASSING
    if any(failing.values()):
        red += (end - since).total_seconds()
    return max(0.0, red)


def numbers(repo: Path, *, since: str | None = None, now: datetime | None = None,
            ci_runs: list[dict[str, Any]] | None = None, ci_error: str | None = None,
            ci_seeds: list[dict[str, Any]] = ()) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    start, end = window(since, now)
    runs, unreadable = load_runs(repo)
    in_window = [run for run in runs if within(run["state"].get("started_at"), start, end)]
    finished = [run for run in in_window if run["state"].get("status") in TERMINAL]
    accepted = [run for run in in_window if run["state"].get("status") == "accepted"]
    clean = [run for run in accepted if touches(run) == 0]
    rows = [number("accepted without human rework", len(finished),
                   round(len(clean) / len(finished), 3) if finished else None, "share of finished runs",
                   start, end, f"{len(clean)} of {len(finished)} finished runs reached acceptance with no operator touch")]

    def tier(run: dict[str, Any]) -> str:
        risk = run["state"].get("risk")
        return risk.get("tier") if isinstance(risk, dict) and risk.get("tier") in TIERS else "unknown"

    warnings: list[str] = []

    def valid_rows(name: str, valid: Callable[[dict[str, Any]], bool]) -> list[dict[str, Any]]:
        """Operator logs are checked as they are read; an invalid row is skipped and counted."""
        rows_read = read_jsonl(factory_dir(repo) / f"{name}.jsonl")
        kept = [item for item in rows_read if valid(item)]
        if len(kept) < len(rows_read):
            warnings.append(f"skipped {len(rows_read) - len(kept)} invalid {name} row(s)")
        return kept

    def stamped(item: dict[str, Any]) -> bool:
        moment = parse_time(item.get("at"))
        return moment is not None and moment <= end

    defects = [item for item in valid_rows("defects", lambda item: stamped(item) and item.get("tier") in TIERS
                                           and isinstance(item.get("sha"), str)
                                           and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", item["sha"]) is not None)
               if within(item.get("at"), start, end)]
    per_tier = {}
    for name in (*TIERS, "unknown"):
        landed = sum(1 for run in accepted if tier(run) == name)
        found = sum(1 for item in defects if item.get("tier") == name)
        if landed or found:
            per_tier[name] = {"defects": found, "landed": landed,
                              "per_landed_change": round(found / landed, 3) if landed else None}
    rows.append(number("defects found after merge, per tier", len(accepted), per_tier, "defects per landed change",
                       start, end, f"{len(defects)} defect(s) logged against {len(accepted)} landed change(s)"))
    total_touches = sum(touches(run) for run in accepted)
    rows.append(number("operator touches per landed change", len(accepted),
                       round(total_touches / len(accepted), 3) if accepted else None, "touches", start, end,
                       f"{total_touches} escalation, interruption and resume event(s) in accepted runs"))
    minutes: dict[str, float] = {}
    for item in valid_rows("minutes", lambda item: stamped(item) and isinstance(item.get("run_id"), str)
                           and isinstance(item.get("minutes"), (int, float)) and not isinstance(item.get("minutes"), bool)
                           and 0 < item["minutes"] <= 24 * 60):
        minutes[item["run_id"]] = minutes.get(item["run_id"], 0.0) + float(item["minutes"])
    logged = [run for run in accepted if run["id"] in minutes]
    rows.append(number("human minutes per landed change", len(logged),
                       round(sum(minutes[run["id"]] for run in logged) / len(logged), 1) if logged else None,
                       "minutes", start, end, f"minutes logged for {len(logged)} of {len(accepted)} landed change(s)"))
    if ci_runs is None:
        rows.append({**number("time the default branch spends red", 0, None, "hours", start, end),
                     "status": "unavailable", "detail": f"cannot read CI: {ci_error or 'no CI data'}"})
    else:
        completed = [run for run in ci_runs if run.get("status") == "completed"]
        red = red_time(completed, start, end, list(ci_seeds))
        rows.append(number("time the default branch spends red", len(completed),
                           {"hours": round(red / 3600, 2), "share": round(red / max(1.0, (end - start).total_seconds()), 3)},
                           "hours and share of the window", start, end,
                           f"from {len(completed)} completed push run(s) on the default branch and the last run of "
                           "each workflow before the window; an upper bound, because a failing workflow counts as "
                           "red until its next run, however long pushes pause"))
    def spend_known(run: dict[str, Any]) -> bool:
        state = run["state"]
        return (not state.get("usage_accounting_incomplete")
                and all(isinstance(state.get(key), (int, float)) and not isinstance(state.get(key), bool)
                        and state[key] >= 0 for key in ("claude_cost_usd", "codex_tokens_used")))

    # Unknown spend is not zero: those runs are left out, and the number says how many.
    known = [run for run in in_window if spend_known(run)]
    known_accepted = [run for run in accepted if spend_known(run)]
    usd = sum(float(run["state"]["claude_cost_usd"]) for run in known)
    tokens = sum(int(run["state"]["codex_tokens_used"]) for run in known)
    unknown = len(in_window) - len(known)
    rows.append(number("spend per landed change", len(known_accepted),
                       {"claude_usd": round(usd / len(known_accepted), 2),
                        "codex_tokens": round(tokens / len(known_accepted))} if known_accepted else None,
                       "per landed change", start, end,
                       f"all known spend of {len(known)} run(s) in the window over {len(known_accepted)} landed "
                       f"change(s)" + (f"; {unknown} run(s) with unknown spend left out" if unknown else "")))
    return {"schema_version": SCHEMA_VERSION, "window": {"since": start.isoformat(timespec="seconds"),
                                                         "until": end.isoformat(timespec="seconds")},
            "minimum_sample": MIN_SAMPLE, "numbers": rows, "unreadable_runs": unreadable, "warnings": warnings}


# --- CI reads (read-only, through gh) ---------------------------------------------------------

def ci_runs(gh: Any, repo_slug: str, branch: str, since: datetime) -> list[dict[str, Any]]:
    """Completed push runs on the default branch since a date, every page, read-only."""
    return gh._pages(f"repos/{repo_slug}/actions/runs?branch={branch}&event=push&status=completed"
                     f"&created=%3E%3D{since.date().isoformat()}&per_page=100", "workflow_runs")


def ci_seed_runs(gh: Any, repo_slug: str, branch: str, since: datetime) -> list[dict[str, Any]]:
    """The latest completed push run of each workflow before the window: the state it opens with."""
    page = gh._json("api", f"repos/{repo_slug}/actions/runs?branch={branch}&event=push&status=completed"
                           f"&created=%3C{since.date().isoformat()}&per_page=100")
    if not isinstance(page, dict):
        raise FactoryError("gh api returned an unexpected shape for the runs before the window")
    latest: dict[Any, dict[str, Any]] = {}
    for run in page.get("workflow_runs") or []:
        key = run.get("workflow_id")
        if key not in latest or (run.get("updated_at") or "") > (latest[key].get("updated_at") or ""):
            latest[key] = run
    return list(latest.values())


def job_os(name: str) -> str | None:
    folded = name.casefold()
    return next((system for system, words in OPERATING_SYSTEMS if any(word in folded for word in words)), None)


def job_timeout(workflow: str, job_name: str) -> int | None:
    """The timeout-minutes that applies to a job, read from the workflow text: a literal, or the
    `matrix.os == 'x' && A || B` form. A job found without the key has GitHub's 360 minutes. None
    when the workflow, the job or the value cannot be read: headroom then fails closed."""
    blocks = re.split(r"\n  (?=[A-Za-z0-9_-]+:\s*\n)", workflow)
    best = None
    for block in blocks[1:]:
        name = re.search(r"\n    name:\s*(.+)", block)
        prefix = (name.group(1).split("${{")[0].strip().strip("'\"") if name else block.split(":", 1)[0])
        if prefix and job_name.startswith(prefix):
            best = block
            break
    if best is None:
        return None
    value = re.search(r"\n    timeout-minutes:\s*(.+)", best)
    if not value:
        return GITHUB_DEFAULT_TIMEOUT_MINUTES
    text = value.group(1).strip()
    if text.isdigit():
        return int(text)
    choice = re.fullmatch(r"\$\{\{\s*matrix\.os\s*==\s*'([^']+)'\s*&&\s*(\d+)\s*\|\|\s*(\d+)\s*\}\}", text)
    if choice:
        return int(choice.group(2)) if choice.group(1) in job_name else int(choice.group(3))
    return None


# --- readiness ---------------------------------------------------------------------------------

def check(name: str, passed: bool, evidence: str, next_step: str) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "evidence": evidence,
            "next_step": "none" if passed else next_step}


REFUSING_ACTIONS = {"prepare", "start", "resume", "graph", "calibrate"}


def refusal_holds(repo: Path, item: dict[str, Any], now: datetime) -> bool:
    """A kill-switch refusal record with its facts: the command, a run or graph id where one is
    refused, the marker at `.harness/AUTONOMY_PAUSED` of this checkout or its main checkout, the
    marker's modification time, which cannot be later than the refusal, and a time not in the future."""
    if item.get("event") != "autonomy_pause_refused" or item.get("action") not in REFUSING_ACTIONS:
        return False
    if item.get("action") != "calibrate" and not (isinstance(item.get("run_id"), str) and item["run_id"]):
        return False
    at = parse_time(item.get("at"))
    mtime = item.get("marker_mtime_ns")
    if at is None or at > now or isinstance(mtime, bool) or not isinstance(mtime, int) or mtime <= 0:
        return False
    if mtime > (at.timestamp() + 2) * 1e9:  # the marker existed before the refusal (2 s for clock rounding)
        return False
    marker = Path(str(item.get("marker", "")))
    roots = {repo.resolve(), common_dir(repo).parent.resolve()}
    return (marker.is_absolute() and marker.name.casefold() == "autonomy_paused"
            and marker.parent.name == ".harness" and marker.parent.parent.resolve() in roots)


def load_controller(repo: Path) -> Any:
    here = Path(__file__).resolve().parent
    for source in (here / "autonomous-run.py", here / "scripts" / "autonomous-run.py"):
        if source.is_file():
            spec = importlib.util.spec_from_file_location("agentsmith_controller_for_factory", source)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
    raise FactoryError("the autonomous-run controller is unavailable")


def readiness(repo: Path, *, controller: Any, gh: Any | None, manifest: dict[str, Any] | None, base: str,
              green_days: int = 7, headroom: float = 0.7, now: datetime | None = None,
              gh_error: str | None = None, repo_slug: str | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    checks = []
    base_commit = git(repo, "rev-parse", "--verify", "--quiet", base + "^{commit}", check=False)
    branch = base.split("/", 1)[1] if base.startswith("origin/") else base
    # 1-2. The default branch's CI: green for the stated period, and room under each job timeout.
    if gh is None:
        reason = f"cannot read CI: {gh_error or 'gh is unavailable'}"
        checks.append(check("default branch green", False, reason, "install gh and run `gh auth login`"))
        checks.append(check("CI headroom", False, reason, "install gh and run `gh auth login`"))
    else:
        try:
            slug = repo_slug or github_slug(repo)
            if slug is None:
                raise FactoryError("the target's origin remote is not a GitHub repository")
            runs = ci_runs(gh, slug, branch, now - timedelta(days=green_days))
            failing = [run for run in runs if run.get("conclusion") not in PASSING]
            green = bool(runs) and not failing
            evidence = (f"{len(runs)} completed push run(s) on {branch} in the last {green_days} day(s), "
                        f"{len(failing)} not green" + (f" (latest red: {failing[0].get('name')} at "
                                                       f"{failing[0].get('updated_at')})" if failing else ""))
            checks.append(check("default branch green", green, evidence,
                                f"keep {branch} green for {green_days} days; `agentsmith ci watch` names each failure"))
            latest: dict[Any, dict[str, Any]] = {}
            for run in sorted(runs, key=lambda item: item.get("updated_at") or ""):
                latest[run.get("workflow_id")] = run
            rows, tight = [], []
            for run in latest.values():
                workflow = git(repo, "show", f"{base_commit}:{run.get('path', '')}", check=False) if base_commit else ""
                for job in gh.attempt_jobs(slug, int(run["id"]), int(run.get("run_attempt") or 1)):
                    system = job_os(str(job.get("name")))
                    began, ended = parse_time(job.get("startedAt")), parse_time(job.get("completedAt"))
                    if system is None or not began or not ended or ended <= began:
                        continue
                    minutes = (ended - began).total_seconds() / 60
                    limit = job_timeout(workflow, str(job.get("name")))
                    if limit is None:
                        rows.append(f"{system} {job.get('name')}: {minutes:.0f} min, timeout unknown")
                        tight.append(rows[-1])
                        continue
                    rows.append(f"{system} {job.get('name')}: {minutes:.0f} of {limit} min")
                    if minutes >= headroom * limit:
                        tight.append(rows[-1])
            seen = {row.split(" ", 1)[0] for row in rows}
            missing = [system for system, _ in OPERATING_SYSTEMS if system not in seen]
            checks.append(check("CI headroom", not tight and not missing,
                                "; ".join(rows) + (f"; no job found for {', '.join(missing)}" if missing else "")
                                if rows else "no timed jobs found",
                                f"keep each job under {headroom:.0%} of its timeout-minutes"
                                + (f"; tight: {'; '.join(tight)}" if tight else "")))
        except Exception as exc:  # gh errors and unexpected shapes: the check fails, readiness goes on
            reason = f"cannot read CI: {exc}"
            checks.append(check("default branch green", False, reason, "check `gh auth status`, then retry"))
            checks.append(check("CI headroom", False, reason, "check `gh auth status`, then retry"))
    # 3-4. The checker: can it run here, and is it calibrated?
    checker = ((manifest or {}).get("roles") or {}).get("checker") or {}
    if not manifest:
        checks.append(check("checker can execute on this host", False, "no manifest names the checker",
                            "pass --manifest with a run manifest"))
        checks.append(check("checker calibration passed", False, "no manifest names the checker",
                            "pass --manifest with a run manifest"))
    else:
        try:
            controller.require_native_role_sandbox()
            controller.preflight_sandboxes(repo, manifest)
            checks.append(check("checker can execute on this host", True,
                                f"{checker.get('runtime')} checker and verifier sandboxes ran a command", ""))
        except Exception as exc:
            checks.append(check("checker can execute on this host", False, str(exc)[:300],
                                "run on macOS, or Linux with bubblewrap, where nested sandboxes are allowed"))
        status = controller.calibration_status(repo, checker)
        checks.append(check("checker calibration passed", status.get("status") == "passed",
                            f"{checker.get('runtime')} {checker.get('model')} ({checker.get('effort')}): "
                            f"{status.get('status')}" + (f" at {status['calibrated_at']}" if status.get("calibrated_at") else ""),
                            "run `autonomous-run.py calibrate <manifest>` with this checker"))
    # 5. The kill switch has been seen to stop work. A local log is evidence, not proof: each record
    # must carry the refusal's facts, and the facts that can be checked are.
    refusals = [item for item in read_jsonl(factory_dir(repo) / "events.jsonl") if refusal_holds(repo, item, now)]
    checks.append(check("kill switch tested", bool(refusals),
                        f"{len(refusals)} refusal(s) recorded with their facts"
                        + (f", latest {refusals[-1].get('at')} ({refusals[-1].get('action')})" if refusals else ""),
                        "create .harness/AUTONOMY_PAUSED, try a start, see it refused, then remove the file"))
    # 6-7. What the base commit carries.
    def at_base(path: str) -> str | None:
        if not base_commit:
            return None
        result = subprocess.run(["git", "-C", str(repo), "show", f"{base_commit}:{path}"], capture_output=True,
                                env={k: v for k, v in os.environ.items() if k not in REPOSITORY_ENV}, check=False)
        return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else None
    conf = at_base(".harness/verify.conf") or ""
    guarded = bool(re.search(r"^[^#\n]*::.*autonomous-run\.py check-specs", conf, re.MULTILINE))
    checks.append(check("pipeline guard in the verifier", guarded,
                        f".harness/verify.conf at {base} {'runs' if guarded else 'does not run'} check-specs",
                        "add a phase `pipeline-specs :: python3 .agentsmith/autonomous-run.py check-specs`"))
    policy, lenses = at_base(".harness/risk-policy.json"), at_base(".harness/lenses.json")
    policy_ok = False
    if policy is not None:
        try:
            import risk_map
            risk_map.load_policy(policy.encode("utf-8"))
            policy_ok = True
        except Exception:
            policy_ok = False
    checks.append(check("risk policy and lens file at the base", policy_ok and lenses is not None,
                        f"risk policy {'valid' if policy_ok else 'missing or invalid'}, lens file "
                        f"{'present' if lenses is not None else 'missing'} at {base}",
                        "commit .harness/risk-policy.json and .harness/lenses.json"))
    # 8. Receipts can leave the Git folder.
    try:
        exported = collect_export(repo)
        checks.append(check("receipts exportable", True, f"{len(exported['runs'])} run(s) readable for export", ""))
    except FactoryError as exc:
        checks.append(check("receipts exportable", False, str(exc), "repair or archive the unreadable run"))
    return {"schema_version": SCHEMA_VERSION, "base": base, "ready": all(item["status"] == "pass" for item in checks),
            "checks": checks}


# --- export and operator logs ---------------------------------------------------------------------

def collect_export(repo: Path) -> dict[str, Any]:
    runs, unreadable = load_runs(repo)
    if unreadable:
        raise FactoryError("cannot export unreadable runs: " + "; ".join(unreadable))
    exported = []
    for run in runs:
        receipts = {}
        for path in sorted(run["folder"].glob("attempt-*.json")):
            try:
                receipts[path.name] = json.loads(path.read_bytes().decode("utf-8"))
            except (OSError, ValueError) as exc:
                raise FactoryError(f"cannot export {run['id']}/{path.name}: {exc}") from None
        exported.append({"run_id": run["id"], "state": run["state"], "events": run["events"], "receipts": receipts})
    root = factory_dir(repo)
    return {"schema_version": SCHEMA_VERSION, "runs": exported,
            "factory": {name: read_jsonl(root / f"{name}.jsonl") for name in ("events", "defects", "minutes")}}


# Export redacts rather than refuses: the record is still useful with a secret-like value removed.
EXPORT_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("assigned secret", re.compile(r"(?i)\b[\w-]*(?:secret|token|password|passwd|api[_-]?key)[\w-]*"
                                   r"[\"' ]*[:=]\s*[\"']?[^\s\"',]{8,}")),
)


def home_pattern() -> re.Pattern[str] | None:
    """Match the home folder however a tool prints it: either separator, doubled when escaped, any
    letter case, with the `\\\\?\\` prefix or as Git Bash's `/c/`. Only whole folder names match."""
    homes = {str(Path.home()), str(Path.home().resolve()),
             os.environ.get("HOME", ""), os.environ.get("USERPROFILE", "")}
    spellings = []
    for home in homes:
        parts = [part for part in re.split(r"[\\/]+", home) if part]
        drive = re.fullmatch(r"([A-Za-z]):", parts[0]) if parts else None
        rest = parts[1:] if drive else parts
        if not rest:
            continue
        head = rf"(?:[\\/]{{2,4}}\?[\\/]{{1,2}})?(?:{drive[1]}:|/{drive[1]}(?=[\\/]))" if drive else ""
        spellings.append(head + "".join(r"[\\/]+" + re.escape(part) for part in rest))
    if not spellings:
        return None
    alternatives = "|".join(sorted(spellings, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w|[.-]\w)", re.IGNORECASE)


def redact(value: Any, patterns: tuple[tuple[str, re.Pattern[str]], ...], counter: list[int],
           home: re.Pattern[str] | None = None) -> Any:
    """Replace the home folder with ~ and secret-like text with a marker, in every string. The
    separator after the home folder stays as written, so `C:\\Users\\me\\x` becomes `~\\x`."""
    if isinstance(value, dict):
        return {key: redact(item, patterns, counter, home) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, patterns, counter, home) for item in value]
    if not isinstance(value, str):
        return value
    if home is not None:
        value, count = home.subn("~", value)
        counter[0] += count
    for name, pattern in patterns:
        value, count = pattern.subn(f"[redacted: {name}]", value)
        counter[0] += count
    return value


def export(repo: Path, target: Path,
           secret_patterns: tuple[tuple[str, re.Pattern[str]], ...] = ()) -> dict[str, Any]:
    """Write receipts out of the Git folder, with home paths and secret-like text redacted.
    `secret_patterns` adds the repository's own secret-scanner patterns to the built-in ones."""
    target = target.expanduser().resolve()
    if target == common_dir(repo) or target.is_relative_to(common_dir(repo)):
        raise FactoryError("export writes out of the Git folder: name a folder outside it")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise FactoryError(f"{target} exists and is not an empty folder")
    counter = [0]
    data = redact(collect_export(repo), (*EXPORT_SECRET_PATTERNS, *secret_patterns), counter, home_pattern())
    target.mkdir(parents=True, exist_ok=True)
    for run in data["runs"]:
        (target / f"run-{run['run_id']}.json").write_text(json.dumps(run, indent=2, sort_keys=True) + "\n",
                                                           encoding="utf-8")
    (target / "factory.json").write_text(json.dumps({**data["factory"], "redactions": counter[0]}, indent=2,
                                                    sort_keys=True) + "\n", encoding="utf-8")
    return {"target": str(target), "runs": len(data["runs"]), "redactions": counter[0]}


def append_log(repo: Path, name: str, record: dict[str, Any]) -> Path:
    root = factory_dir(repo)
    root.mkdir(exist_ok=True)
    path = root / f"{name}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return path


def add_defect(repo: Path, sha: str, tier: str, note: str = "", now: datetime | None = None) -> Path:
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):
        raise FactoryError("defect add needs the full commit SHA of the merged change, in lowercase hex")
    if tier not in TIERS:
        raise FactoryError(f"--tier must be one of {', '.join(TIERS)}")
    stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    return append_log(repo, "defects", {"at": stamp, "sha": sha, "tier": tier, "note": note})


def add_minutes(repo: Path, run_id: str, minutes: float, now: datetime | None = None) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise FactoryError("minutes add needs a run id")
    if not 0 < minutes <= 24 * 60:
        raise FactoryError("minutes must be more than 0 and at most one day")
    stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    return append_log(repo, "minutes", {"at": stamp, "run_id": run_id, "minutes": minutes})


def render(report: dict[str, Any]) -> str:
    if "checks" in report:
        lines = [f"readiness: {'ready' if report['ready'] else 'not ready'} (base {report['base']})"]
        for item in report["checks"]:
            lines.append(f"  {item['status']:<4} {item['name']}: {item['evidence']}")
            if item["status"] != "pass":
                lines.append(f"       next: {item['next_step']}")
        return "\n".join(lines) + "\n"
    lines = [f"numbers from {report['window']['since']} to {report['window']['until']} "
             f"(at least {report['minimum_sample']} cases per number)"]
    for row in report["numbers"]:
        value = row["value"] if row["status"] == "ok" else row["status"]
        lines.append(f"  {row['name']}: {json.dumps(value) if isinstance(value, (dict, list)) else value} "
                     f"[n={row['n']}] {row['detail']}")
    for name in report.get("unreadable_runs", []):
        lines.append(f"  unreadable run: {name}")
    for warning in report.get("warnings", []):
        lines.append(f"  warning: {warning}")
    return "\n".join(lines) + "\n"


# --- intake: one GitHub issue, read only, sanitised, with the operator's verdict ----------------

VERDICTS = ("ACCEPT", "ACCEPT-RESCOPED", "NEEDS-INFO", "REJECT")
# Where the operating system can open relative to a folder handle (POSIX), the draft is written by
# walking from the repository root without following links; elsewhere (Windows) by checking again.
DIR_FD = os.open in os.supports_dir_fd and os.mkdir in os.supports_dir_fd
ISSUE_FIELDS = "number,title,body,author,url"
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
BIDI = {0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}
ZERO_WIDTH = {0x200B, 0x200C, 0x200D, *range(0x2060, 0x2065), 0xFEFF}
# The whole tag block, unassigned codes too: none of it is visible, and it can spell hidden ASCII.
TAGS = set(range(0xE0000, 0xE0080))
# Variation selectors (category Mn, not Cf) can encode hidden bytes; dropping U+FE0F only loses an
# emoji's presentation hint.
VARIATION_SELECTORS = {*range(0xFE00, 0xFE10), *range(0xE0100, 0xE01F0)}


def hidden_kind(char: str) -> str | None:
    """Why a character is removed, or None to keep it. Newline and tab are the only controls kept."""
    code = ord(char)
    if code in ZERO_WIDTH:
        return "zero-width"
    if code in BIDI:
        return "bidi-control"
    if code in TAGS:
        return "tag-character"
    if code in VARIATION_SELECTORS:
        return "variation-selector"
    category = unicodedata.category(char)
    if category == "Cf":
        return "other-format"
    if category == "Cc" and char not in "\n\t":
        return "control"
    return None


def sanitise(text: str) -> tuple[str, dict[str, Any]]:
    """Text without invisible characters and HTML comments, and a report of what was removed:
    kinds and counts only, never the removed text. Characters go first, so a marker split by a
    zero-width character is still a comment; comments are removed until none is left, and an
    unclosed `<!--` hides everything after it when rendered, so that is removed too."""
    removed: dict[str, int] = {}
    kept = []
    text = text.replace("\r\n", "\n")
    for char in text:
        kind = hidden_kind(char)
        if kind is None:
            kept.append(char)
        else:
            removed[kind] = removed.get(kind, 0) + 1
    clean = "".join(kept)
    while True:
        clean, count = COMMENT.subn("", clean)
        if not count:
            break
        removed["html-comment"] = removed.get("html-comment", 0) + count
    if "<!--" in clean:
        removed["html-comment"] = removed.get("html-comment", 0) + 1
        clean = clean[:clean.index("<!--")]
    return clean, {"removed": removed, "characters_removed": len(text) - len(clean)}


def issue_number(reference: str, slug: str) -> int:
    """The issue number from `7`, `#7` or the issue's URL in the origin repository."""
    number = re.fullmatch(r"#?([1-9][0-9]{0,9})", reference.strip())
    if number:
        return int(number.group(1))
    url = re.fullmatch(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/issues/([1-9][0-9]{0,9})/?",
                       reference.strip())
    if url:
        if url.group(1).casefold() != slug.casefold():
            raise FactoryError(f"issue {reference} is not in {slug}, the origin remote's repository")
        return int(url.group(2))
    raise FactoryError(f"intake needs an issue number or URL of {slug}, not {reference!r}")


def intake_verdict(verdict: str | None, left_out: Iterable[str] = (), questions: Iterable[str] = (),
                   reason: str | None = None, draft_spec: str | None = None) -> dict[str, Any] | None:
    """The operator's verdict with exactly its own fields, or None to only show the issue."""
    left_out, questions = list(left_out), list(questions)
    given = {"--left-out": bool(left_out), "--question": bool(questions), "--reason": reason is not None,
             "--draft-spec": draft_spec is not None}
    if verdict is None:
        for flag, present in given.items():
            if present:
                raise FactoryError(f"{flag} needs --verdict")
        return None
    if verdict not in VERDICTS:
        raise FactoryError(f"--verdict must be one of {', '.join(VERDICTS)}")
    owners = {"--left-out": "ACCEPT-RESCOPED", "--question": "NEEDS-INFO", "--reason": "REJECT"}
    for flag, owner in owners.items():
        if given[flag] and verdict != owner:
            raise FactoryError(f"{flag} belongs to {owner}, not {verdict}")
    if draft_spec is not None and verdict not in ("ACCEPT", "ACCEPT-RESCOPED"):
        raise FactoryError(f"--draft-spec needs ACCEPT or ACCEPT-RESCOPED, not {verdict}")
    items = lambda values: [" ".join(value.split()) for value in values if value.strip()]  # noqa: E731
    if verdict == "ACCEPT-RESCOPED":
        if not items(left_out):
            raise FactoryError("ACCEPT-RESCOPED must name what was left out: pass --left-out at least once")
        return {"verdict": verdict, "left_out": items(left_out)}
    if verdict == "NEEDS-INFO":
        if not items(questions):
            raise FactoryError("NEEDS-INFO must ask something: pass --question at least once")
        return {"verdict": verdict, "questions": items(questions)}
    if verdict == "REJECT":
        if not (reason or "").strip():
            raise FactoryError("REJECT needs a reason: pass --reason")
        return {"verdict": verdict, "reason": " ".join(reason.split())}
    return {"verdict": verdict}


def draft_spec_path(repo: Path, value: str, cwd: Path) -> Path:
    """Where a new draft spec may go: inside the repository, outside its Git folder, not existing."""
    candidate = Path(value).expanduser()
    candidate = candidate if candidate.is_absolute() else cwd / candidate
    if candidate.is_symlink() or candidate.exists():
        raise FactoryError(f"refusing to overwrite: {value} exists")
    resolved, root = candidate.resolve(), repo.resolve()
    if not resolved.is_relative_to(root):
        raise FactoryError(f"the draft spec must be inside the repository, not {value}")
    if resolved.is_relative_to(common_dir(repo)) or ".git" in resolved.relative_to(root).parts:
        raise FactoryError(f"the draft spec must not be in the Git folder: {value}")
    return resolved


def write_draft(root: Path, relative: Path, text: str) -> None:
    """Create `relative` under `root` exclusively. The path was checked before the issue was read, and
    a folder can be swapped for a link since; the write itself must not follow one.

    With folder handles (POSIX): open the root, then each folder with O_NOFOLLOW relative to its
    parent, creating a missing one, and create the file with O_EXCL | O_NOFOLLOW in the last one.
    Without them (Windows): resolve the parent again just before the exclusive create. A window
    remains there between that check and the create; KNOWN-ISSUES.md records it."""
    parts = relative.parts
    if not parts or any(part in ("", ".", "..") or part.casefold() == ".git" for part in parts):
        raise FactoryError(f"the draft spec must be a plain path inside the repository, outside .git: {relative}")
    changed = f"the folders of {relative.as_posix()} changed while intake ran (a folder is now a link); nothing written"
    if not DIR_FD:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        parent = target.parent.resolve()
        if parent != (root / relative.parent) or not parent.is_relative_to(root):
            raise FactoryError(changed)
        try:
            with target.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        except FileExistsError:
            raise FactoryError(f"refusing to overwrite: {relative.as_posix()} exists") from None
        return
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    folder_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow | getattr(os, "O_CLOEXEC", 0)
    handles = [os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0))]
    try:
        for name in parts[:-1]:
            try:
                handles.append(os.open(name, folder_flags, dir_fd=handles[-1]))
            except FileNotFoundError:
                try:
                    os.mkdir(name, 0o755, dir_fd=handles[-1])
                except FileExistsError:
                    pass  # made meanwhile: the open below decides whether it is a real folder
                try:
                    handles.append(os.open(name, folder_flags, dir_fd=handles[-1]))
                except OSError:
                    raise FactoryError(changed) from None
            except OSError:  # ELOOP or ENOTDIR: a link or a file where a folder was checked
                raise FactoryError(changed) from None
        try:
            fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow | getattr(os, "O_CLOEXEC", 0),
                         0o644, dir_fd=handles[-1])
        except FileExistsError:
            raise FactoryError(f"refusing to overwrite: {relative.as_posix()} exists") from None
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        except BaseException:
            os.unlink(parts[-1], dir_fd=handles[-1])  # no half-written draft is left behind
            raise
    finally:
        for handle in reversed(handles):
            os.close(handle)


def read_issue(gh: Any, repo: Path, slug: str, number: int) -> dict[str, Any]:
    """One `gh issue view`, the only call intake makes; an answer that is not that issue is refused."""
    if not gh.which("gh"):
        raise FactoryError("GitHub CLI (gh) is not installed; intake reads the issue with it: install it "
                           "from https://cli.github.com, then run `gh auth login`")
    try:
        data = gh._json(repo, "issue", "view", str(number), "--repo", slug, "--json", ISSUE_FIELDS)
    except RuntimeError as exc:  # inbox.GhError: gh failed, or printed no JSON
        raise FactoryError(str(exc)) from None
    if not isinstance(data, dict):
        raise FactoryError("gh issue view returned an unexpected shape")
    url = data.get("url")
    if isinstance(url, str) and re.fullmatch(rf"https://github\.com/{re.escape(slug)}/pull/{number}/?", url,
                                             re.IGNORECASE):
        raise FactoryError(f"#{number} in {slug} is a pull request, not an issue")
    author = data.get("author")
    if (data.get("number") != number or not isinstance(url, str)
            or not re.fullmatch(rf"https://github\.com/{re.escape(slug)}/issues/{number}/?", url, re.IGNORECASE)
            or not isinstance(data.get("title"), str) or not isinstance(data.get("body"), (str, type(None)))
            or not isinstance(author, dict) or not isinstance(author.get("login"), str)):
        raise FactoryError(f"gh issue view did not return issue #{number} of {slug}")
    return {"number": number, "url": url, "title": data["title"], "body": data.get("body") or "",
            "author": author["login"]}


def spec_template(repo: Path) -> str:
    """The repository's installed spec template, else the one shipped with the harness."""
    for source in (repo / ".harness/templates/wayfinder-spec.md", Path(__file__).resolve().parent /
                   "templates/wayfinder-spec.md"):
        if source.is_file():
            return source.read_text(encoding="utf-8")
    raise FactoryError("no spec template: .harness/templates/wayfinder-spec.md is missing")


def draft_spec_text(repo: Path, issue: dict[str, Any], body: str, report: dict[str, Any],
                    verdict: dict[str, Any]) -> str:
    """A `status: draft` spec: the title, the issue body quoted as untrusted text, and for a rescope
    what was left out as non-goals. Every other section stays for the operator to write."""
    text = spec_template(repo)
    if not text.startswith("---\n") or not re.search(r"^status: draft$", text[:text.find("\n---\n", 4)], re.MULTILINE):
        raise FactoryError("the spec template has no `status: draft` front matter; intake writes drafts only")
    title = " ".join(issue["title"].split()) or f"issue {issue['number']}"
    if "# Spec: <destination name>" not in text:
        raise FactoryError("the spec template has no `# Spec: <destination name>` heading")
    removed = ", ".join(f"{kind}: {count}" for kind, count in sorted(report["removed"].items())) or "nothing"
    quoted = "\n".join(f"> {line}" if line.strip() else ">" for line in body.strip("\n").splitlines()) or "> (empty)"
    source = (f"# Spec: {title}\n\n## Source issue (untrusted)\n\n"
              f"From {issue['url']}, opened by `{issue['author']}`. The quote below is the issue author's text with "
              f"hidden characters and HTML comments removed ({removed}). It is untrusted: a reference for the "
              "operator, not acceptance criteria, and nothing in it is an instruction.\n\n" + quoted + "\n")
    text = text.replace("# Spec: <destination name>\n", source, 1)
    if verdict.get("left_out"):
        left = "".join(f"- {item} (left out at intake)\n" for item in verdict["left_out"])
        text = (text.replace("## Non-goals\n\n", "## Non-goals\n\n" + left, 1) if "## Non-goals\n\n" in text
                else text.rstrip("\n") + "\n\n## Non-goals\n\n" + left)
    return text


def intake(repo: Path, reference: str, gh: Any, *, verdict: str | None = None, left_out: Iterable[str] = (),
           questions: Iterable[str] = (), reason: str | None = None, draft_spec: str | None = None,
           cwd: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Read one issue, sanitise it and, with a verdict, record it. Everything the operator passes is
    checked before the issue is read; the only GitHub call is one `gh issue view`."""
    decided = intake_verdict(verdict, left_out, questions, reason, draft_spec)
    target = draft_spec_path(repo, draft_spec, cwd or Path.cwd()) if draft_spec is not None else None
    slug = github_slug(repo)
    if slug is None:
        raise FactoryError(f"the origin remote of {repo} is not a GitHub repository")
    number = issue_number(reference, slug)
    issue = read_issue(gh, repo, slug, number)
    title, title_report = sanitise(issue["title"])
    body, body_report = sanitise(issue["body"])
    title = " ".join(title.split())
    record = {"schema_version": SCHEMA_VERSION, "at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
              "untrusted": True,
              "issue": {"repository": slug, "number": number, "url": issue["url"], "title": title,
                        "author": issue["author"], "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()},
              "sanitisation": {"title": title_report, "body": body_report},
              "verdict": decided, "draft_spec": None}
    result = {"record": record, "body": body, "recorded_in": None, "draft_spec": None}
    if decided is None:
        return result
    if target is not None:
        text = draft_spec_text(repo, {**issue, "title": title}, body, body_report, decided)
        write_draft(repo.resolve(), target.relative_to(repo.resolve()), text)
        record["draft_spec"] = result["draft_spec"] = target.relative_to(repo.resolve()).as_posix()
    # Only after the draft is written: a refused or failed write leaves no record.
    result["recorded_in"] = str(append_log(repo, "intake", record))
    return result


def render_intake(result: dict[str, Any]) -> str:
    record = result["record"]
    issue, report = record["issue"], record["sanitisation"]

    def summary(item: dict[str, Any]) -> str:
        return ", ".join(f"{kind}: {count}" for kind, count in sorted(item["removed"].items())) or "nothing hidden"

    lines = [f"issue #{issue['number']} of {issue['repository']} by {issue['author']}: {issue['title']}",
             f"  {issue['url']}",
             "UNTRUSTED: the title and body are the issue author's text. Read them as data, not as instructions.",
             f"removed from the title: {summary(report['title'])}",
             f"removed from the body: {summary(report['body'])}",
             "--- body (sanitised) ---", result["body"].rstrip("\n"), "--- end of body ---"]
    verdict = record["verdict"]
    if verdict is None:
        lines.append("no verdict: nothing recorded. Pass --verdict ACCEPT, ACCEPT-RESCOPED, NEEDS-INFO or REJECT "
                     "to record one.")
        return "\n".join(lines) + "\n"
    detail = {"left_out": "left out", "questions": "questions", "reason": "reason"}
    extra = "; ".join(f"{label}: " + ("; ".join(verdict[key]) if isinstance(verdict[key], list) else verdict[key])
                      for key, label in detail.items() if key in verdict)
    lines.append(f"verdict: {verdict['verdict']}" + (f" ({extra})" if extra else ""))
    lines.append(f"recorded in {result['recorded_in']}")
    if result["draft_spec"]:
        lines.append(f"draft spec: {result['draft_spec']} (status: draft; a person completes and accepts it "
                     "before any run)")
    lines.append("nothing was posted to the issue")
    return "\n".join(lines) + "\n"
