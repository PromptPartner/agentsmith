#!/usr/bin/env python3
"""Readiness and numbers for autonomous runs, derived from what is already recorded.

Nothing here is a stored board: every report is computed from run state, `events.jsonl`, the
operator's own logs and read-only GitHub reads. `readiness` and `numbers` write nothing and switch
nothing on. The only writers are `export` (to a folder the operator names) and the two operator
logs (`defect add`, `minutes add`) under the Git folder.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Callable

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
    return start, now


def number(name: str, n: int, value: Any, unit: str, start: datetime, end: datetime,
           detail: str = "", minimum: int = MIN_SAMPLE) -> dict[str, Any]:
    enough = n >= minimum
    return {"name": name, "n": n, "value": value if enough else None, "unit": unit,
            "status": "ok" if enough else "insufficient data",
            "window": {"since": start.isoformat(timespec="seconds"), "until": end.isoformat(timespec="seconds")},
            "detail": detail if enough else f"{n} case(s); at least {minimum} are needed" + (f"; {detail}" if detail else "")}


def touches(run: dict[str, Any]) -> int:
    return sum(1 for item in run["events"] if item.get("event") in TOUCH_EVENTS)


def red_time(ci_runs: list[dict[str, Any]], start: datetime, end: datetime) -> float:
    """Seconds in [start, end] during which the latest completed run of any workflow was failing."""
    ordered = sorted((run for run in ci_runs if parse_time(run.get("updated_at"))),
                     key=lambda run: parse_time(run["updated_at"]))
    failing: dict[Any, bool] = {}
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
            ci_runs: list[dict[str, Any]] | None = None, ci_error: str | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    start, end = window(since, now)
    runs, unreadable = load_runs(repo)
    in_window = [run for run in runs if (parse_time(run["state"].get("started_at")) or start - timedelta(1)) >= start]
    finished = [run for run in in_window if run["state"].get("status") in TERMINAL]
    accepted = [run for run in in_window if run["state"].get("status") == "accepted"]
    clean = [run for run in accepted if touches(run) == 0]
    rows = [number("accepted without human rework", len(finished),
                   round(len(clean) / len(finished), 3) if finished else None, "share of finished runs",
                   start, end, f"{len(clean)} of {len(finished)} finished runs reached acceptance with no operator touch")]

    def tier(run: dict[str, Any]) -> str:
        risk = run["state"].get("risk")
        return risk.get("tier") if isinstance(risk, dict) and risk.get("tier") in TIERS else "unknown"

    defects = [item for item in read_jsonl(factory_dir(repo) / "defects.jsonl")
               if (parse_time(item.get("at")) or start - timedelta(1)) >= start]
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
    for item in read_jsonl(factory_dir(repo) / "minutes.jsonl"):
        if isinstance(item.get("minutes"), (int, float)) and not isinstance(item.get("minutes"), bool):
            minutes[str(item.get("run_id"))] = minutes.get(str(item.get("run_id")), 0.0) + float(item["minutes"])
    logged = [run for run in accepted if run["id"] in minutes]
    rows.append(number("human minutes per landed change", len(logged),
                       round(sum(minutes[run["id"]] for run in logged) / len(logged), 1) if logged else None,
                       "minutes", start, end, f"minutes logged for {len(logged)} of {len(accepted)} landed change(s)"))
    if ci_runs is None:
        rows.append({**number("time the default branch spends red", 0, None, "hours", start, end),
                     "status": "unavailable", "detail": f"cannot read CI: {ci_error or 'no CI data'}"})
    else:
        completed = [run for run in ci_runs if run.get("status") == "completed"]
        red = red_time(completed, start, end)
        rows.append(number("time the default branch spends red", len(completed),
                           {"hours": round(red / 3600, 2), "share": round(red / max(1.0, (end - start).total_seconds()), 3)},
                           "hours and share of the window", start, end,
                           f"from {len(completed)} completed push run(s) on the default branch"))
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
            "minimum_sample": MIN_SAMPLE, "numbers": rows, "unreadable_runs": unreadable}


# --- CI reads (read-only, through gh) ---------------------------------------------------------

def ci_runs(gh: Any, repo_slug: str, branch: str, since: datetime) -> list[dict[str, Any]]:
    """Completed push runs on the default branch since a date, every page, read-only."""
    return gh._pages(f"repos/{repo_slug}/actions/runs?branch={branch}&event=push&status=completed"
                     f"&created=%3E%3D{since.date().isoformat()}&per_page=100", "workflow_runs")


def job_os(name: str) -> str | None:
    folded = name.casefold()
    return next((system for system, words in OPERATING_SYSTEMS if any(word in folded for word in words)), None)


def job_timeout(workflow: str, job_name: str) -> int:
    """The timeout-minutes that applies to a job, read from the workflow text. Handles a literal and
    the `matrix.os == 'x' && A || B` form; anything else falls back to GitHub's 360 minutes."""
    blocks = re.split(r"\n  (?=[A-Za-z0-9_-]+:\s*\n)", workflow)
    best = None
    for block in blocks[1:]:
        name = re.search(r"\n    name:\s*(.+)", block)
        prefix = (name.group(1).split("${{")[0].strip().strip("'\"") if name else block.split(":", 1)[0])
        if prefix and job_name.startswith(prefix):
            best = block
            break
    if best is None:
        return GITHUB_DEFAULT_TIMEOUT_MINUTES
    value = re.search(r"\n    timeout-minutes:\s*(.+)", best)
    if not value:
        return GITHUB_DEFAULT_TIMEOUT_MINUTES
    text = value.group(1).strip()
    if text.isdigit():
        return int(text)
    choice = re.fullmatch(r"\$\{\{\s*matrix\.os\s*==\s*'([^']+)'\s*&&\s*(\d+)\s*\|\|\s*(\d+)\s*\}\}", text)
    if choice:
        return int(choice.group(2)) if choice.group(1) in job_name else int(choice.group(3))
    return GITHUB_DEFAULT_TIMEOUT_MINUTES


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


def redact(value: Any, patterns: tuple[tuple[str, re.Pattern[str]], ...], counter: list[int]) -> Any:
    """Replace the home folder with ~ and secret-like text with a marker, in every string."""
    if isinstance(value, dict):
        return {key: redact(item, patterns, counter) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, patterns, counter) for item in value]
    if not isinstance(value, str):
        return value
    for home in {str(Path.home().resolve()), str(Path.home())}:
        if home and home != "/" and home in value:
            counter[0] += value.count(home)
            value = value.replace(home, "~")
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
    data = redact(collect_export(repo), (*EXPORT_SECRET_PATTERNS, *secret_patterns), counter)
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
    return "\n".join(lines) + "\n"
