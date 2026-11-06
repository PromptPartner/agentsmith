"""Operator inbox: everything that waits on the operator, derived on every call (standard library).

Rows come from autonomous-run and work-graph state under the Git common directory, from specs and
run manifests in the repository, and, with --issues, from open GitHub issues read through `gh`.
Each row is re-checked against Git; a row whose claim Git contradicts is dropped with a warning.
Listing writes nothing. Claims are the one write: operator input kept under the Git common
directory, never in the tracked tree and never on GitHub.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Callable

SCHEMA_VERSION = 1
KIND_ORDER = ("escalated", "dead", "interrupted", "accepted", "integration", "manifest", "spec", "untriaged")
TERMINAL_RUN = {"accepted", "escalated", "interrupted"}
UNFINISHED_RUN = {"prepared", "making", "checking", "retrying", "resuming"}
CLOSED_SPEC = {"accepted", "superseded", "rejected", "withdrawn", "done", "archived"}
RUN_ROOT_ENTRIES = {"coordination.lock", "git-phases", "graph-stop"}
# `git rev-parse --local-env-vars`: inherited ones would point Git at another repository.
REPOSITORY_ENV = {"GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
                  "GIT_OBJECT_DIRECTORY", "GIT_DIR", "GIT_WORK_TREE", "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE",
                  "GIT_INDEX_FILE", "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE", "GIT_PREFIX",
                  "GIT_SHALLOW_FILE", "GIT_COMMON_DIR"}
OID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


class InboxError(RuntimeError):
    """The repository cannot be read."""


class GhError(RuntimeError):
    """gh is missing, not logged in, or a read failed."""


class ClaimError(RuntimeError):
    """A claim cannot be taken or released."""


class Gh:
    """Thin read-only adapter over the gh CLI; `runner` and `which` are injectable for tests."""

    def __init__(self, runner: Callable[..., Any] = subprocess.run,
                 which: Callable[[str], str | None] = shutil.which) -> None:
        self.runner, self.which = runner, which

    def _run(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        try:
            return self.runner(["gh", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GhError(f"gh {' '.join(args[:2])} failed: {exc}") from None

    def _json(self, cwd: Path, *args: str) -> Any:
        result = self._run(cwd, *args)
        if result.returncode:
            lines = (result.stderr or "").strip().splitlines()
            raise GhError(f"gh {' '.join(args[:2])} failed: {lines[-1] if lines else 'exit ' + str(result.returncode)}")
        try:
            return json.loads(result.stdout) if result.stdout.strip() else None
        except json.JSONDecodeError:
            raise GhError(f"gh {' '.join(args[:2])} returned no JSON") from None

    def check(self, cwd: Path) -> None:
        if not self.which("gh"):
            raise GhError("GitHub CLI (gh) is not installed; --issues needs it: install it from "
                          "https://cli.github.com, then run `gh auth login`")
        if self._run(cwd, "auth", "status").returncode:  # prints text, not JSON
            raise GhError("gh is not logged in to GitHub; run `gh auth login` and try again")

    def repo(self, cwd: Path) -> str:
        return self._json(cwd, "repo", "view", "--json", "nameWithOwner")["nameWithOwner"]

    def issues(self, cwd: Path, repo: str) -> list[dict[str, Any]]:
        return self._json(cwd, "issue", "list", "--repo", repo, "--state", "open", "--limit", "200",
                          "--json", "number,title,createdAt,labels,url") or []

    def pr_heads(self, cwd: Path, repo: str) -> set[str]:
        prs = self._json(cwd, "pr", "list", "--repo", repo, "--state", "open", "--limit", "200",
                         "--json", "number,headRefOid") or []
        return {pr["headRefOid"] for pr in prs if isinstance(pr.get("headRefOid"), str)}


def _env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in REPOSITORY_ENV}
    env["GIT_OPTIONAL_LOCKS"] = "0"  # no index refresh or other opportunistic writes
    return env


def _git(repo: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, env=_env(), timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InboxError(f"git failed: {exc}") from None
    return result.stdout.decode("utf-8", "replace").strip() if result.returncode == 0 else None


def _commit(repo: Path, oid: Any) -> bool:
    return isinstance(oid, str) and OID.fullmatch(oid) is not None and _git(repo, "cat-file", "-e", f"{oid}^{{commit}}") is not None


def _branch(repo: Path, name: Any) -> str | None:
    if not isinstance(name, str) or not name or name.startswith("-"):
        return None
    return _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}^{{commit}}")


def _contains(repo: Path, commit: str, tip: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", commit, tip],
                          capture_output=True, env=_env(), timeout=60).returncode == 0


def _seconds(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        moment = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (moment if moment.tzinfo else moment.replace(tzinfo=dt.timezone.utc)).timestamp()


def age_text(seconds: int) -> str:
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def _controller() -> Any | None:
    here = Path(__file__).resolve().parent
    for source in (here / "autonomous-run.py", here / "scripts" / "autonomous-run.py"):
        if source.is_file():
            sys.dont_write_bytecode = True  # listing must not leave compiled files behind
            spec = importlib.util.spec_from_file_location("agentsmith_finite_run_for_inbox", source)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
    return None


def _frontmatter_status(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    for line in text[4:end if end >= 0 else len(text)].splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "status":
            return value.strip()
    return ""


def _one_line(text: Any) -> str:
    return " ".join(str(text).split())


class _Collector:
    def __init__(self, repo: Path, now: Callable[[], float], gh: Gh | None, repo_name: str | None,
                 base: str | None) -> None:
        self.repo, self.now, self.gh, self.repo_name, self.base = repo, now(), gh, repo_name, base
        common = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
        if common is None:
            raise InboxError(f"{repo} is not a Git repository")
        self.common = Path(common)
        self.rows: list[dict[str, Any]] = []
        self.warnings: list[str] = []
        self.pr_heads: set[str] = set()
        self.origin_base = self._origin_base()

    def _origin_base(self) -> str | None:
        names = [f"refs/remotes/origin/{self.base}"] if self.base else []
        if not names:
            head = _git(self.repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
            names = [head] if head else ["refs/remotes/origin/main", "refs/remotes/origin/master"]
        for name in names:
            oid = _git(self.repo, "rev-parse", "--verify", "--quiet", f"{name}^{{commit}}")
            if oid:
                return oid
        self.warnings.append("no origin base branch found; accepted work cannot be checked as landed, so all of it is listed")
        return None

    def _landed(self, commit: str) -> bool:
        return bool(self.origin_base and _contains(self.repo, commit, self.origin_base)) or commit in self.pr_heads

    def _tier(self, base: Any, head: Any) -> str | None:
        if not (_commit(self.repo, base) and _commit(self.repo, head)) or base == head:
            return None
        try:
            import risk_map
            return risk_map.classify_range(self.repo, base, head)["tier"]
        except Exception as exc:  # a tier is a column; its failure must not hide the row
            self.warnings.append(f"tier unavailable for {str(head)[:12]}: {exc}")
            return None

    def add(self, kind: str, item_id: str, since: float | None, next_step: str, tier: str | None = None) -> None:
        age = max(0, int(self.now - since)) if since is not None else None
        self.rows.append({"kind": kind, "id": item_id, "age_seconds": age,
                          "age": age_text(age) if age is not None else "?", "tier": tier,
                          "next_step": _one_line(next_step)})

    def runs(self) -> None:
        root = self.common / "agentsmith-runs"
        if not root.is_dir():
            return
        controller = None
        for entry in sorted(root.iterdir()):
            if entry.name in RUN_ROOT_ENTRIES or not entry.is_dir() or entry.is_symlink():
                continue
            state_file = entry / "state.json"
            if not state_file.exists():
                continue  # a start in progress, or nothing yet
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
                if not isinstance(state, dict):
                    raise ValueError("state is not an object")
                controller = controller or _controller()
                if controller is None:
                    raise ValueError("the autonomous-run controller is not installed, so liveness is unknown")
                owner = controller.read_lock(entry)
            except Exception as exc:
                self.warnings.append(f"run {entry.name}: dropped, its state cannot be read: {_one_line(exc)}")
                continue
            try:
                self._run_row(entry.name, state, owner, controller)
            except Exception as exc:  # one malformed run must not hide every other row
                self.warnings.append(f"run {entry.name}: dropped, its state holds unexpected values: {_one_line(exc)}")

    def _run_row(self, name: str, state: dict[str, Any], owner: dict[str, Any] | None, controller: Any) -> None:
        status, branch = state.get("status"), state.get("branch")
        if not isinstance(status, str):
            raise ValueError(f"status is {type(status).__name__}, not text")
        if (owner and controller.process_is_live(owner.get("pid"))) or \
                (state.get("active_pid") and controller.process_is_live(state.get("active_pid"))):
            return  # running: it waits on nobody yet
        since = _seconds(state.get("updated_at")) or _seconds(state.get("started_at"))
        tip = _branch(self.repo, branch)
        base = state.get("base_head")
        if status == "accepted":
            commit = state.get("accepted_commit")
            if not _commit(self.repo, commit):
                self.warnings.append(f"run {name}: dropped, accepted commit {str(commit)[:12]} is not in this repository")
            elif tip is None:
                self.warnings.append(f"run {name}: dropped, branch {branch} is gone")
            elif not _contains(self.repo, commit, tip):
                self.warnings.append(f"run {name}: dropped, branch {branch} no longer contains accepted commit {commit[:12]}")
            elif not self._landed(commit):
                self.add("accepted", name, since, f"review accepted commit {commit[:12]} on {branch}, then push it "
                         "and open a pull request; nothing lands by itself", self._tier(base, commit))
            return
        if status not in TERMINAL_RUN and status not in UNFINISHED_RUN:
            self.warnings.append(f"run {name}: dropped, unknown status {status!r}")
            return
        if tip is None:
            self.warnings.append(f"run {name}: dropped, {status} but branch {branch} is gone")
            return
        if not _commit(self.repo, base):
            self.warnings.append(f"run {name}: dropped, base commit {str(base)[:12]} is not in this repository")
            return
        reason = state.get("reason") or "no reason recorded"
        if status == "escalated":
            self.add("escalated", name, since, f"escalated: {reason}; read the run evidence, fix the spec or "
                     f"manifest, then resume {name} or start a new run", self._tier(base, tip))
        elif status == "interrupted":
            self.add("interrupted", name, since, f"interrupted ({reason}); resume {name} or discard the run",
                     self._tier(base, tip))
        else:
            self.add("dead", name, since, f"{status} with no live controller or role process; inspect it, "
                     f"then resume {name}", self._tier(base, tip))

    def integrations(self) -> None:
        root = self.common / "agentsmith-graphs"
        for path in sorted(root.glob("*/integration-candidate.json")) if root.is_dir() else []:
            graph = path.parent.name
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                commit, branch = record["candidate_commit"], record["candidate_branch"]
            except Exception as exc:
                self.warnings.append(f"graph {graph}: dropped, its integration candidate cannot be read: {_one_line(exc)}")
                continue
            tip = _branch(self.repo, branch)
            if not _commit(self.repo, commit):
                self.warnings.append(f"graph {graph}: dropped, candidate commit {str(commit)[:12]} is not in this repository")
            elif tip is None or not _contains(self.repo, commit, tip):
                self.warnings.append(f"graph {graph}: dropped, branch {branch} no longer holds candidate {commit[:12]}")
            elif not self._landed(commit):
                self.add("integration", graph, _seconds(record.get("created_at")),
                         f"review integration candidate {commit[:12]} on {branch} and approve it by merging "
                         "it yourself; nothing merges automatically", self._tier(record.get("base_oid"), commit))

    def _files(self, folder: str, suffix: str) -> dict[str, tuple[bytes, bool]]:
        """{path: (content, committed unchanged)} from HEAD and the working tree, read-only."""
        found: dict[str, tuple[bytes, bool]] = {}
        listing = _git(self.repo, "ls-tree", "--name-only", "HEAD", f"{folder}/") or ""
        for path in listing.splitlines():
            if path.endswith(suffix):
                blob = subprocess.run(["git", "-C", str(self.repo), "cat-file", "blob", f"HEAD:{path}"],
                                      capture_output=True, env=_env(), timeout=60).stdout
                found[path] = (blob, True)
        directory = self.repo / folder
        for file in sorted(directory.glob(f"*{suffix}")) if directory.is_dir() else []:
            if file.is_file() and not file.is_symlink():
                path = f"{folder}/{file.name}"
                content = file.read_bytes()
                found[path] = (content, path in found and found[path][0] == content)
        return found

    def _since(self, path: str, committed: bool) -> float | None:
        if committed:
            stamp = _git(self.repo, "log", "-1", "--format=%ct", "HEAD", "--", path)
            return float(stamp) if stamp else None
        try:
            return (self.repo / path).stat().st_mtime
        except OSError:
            return None

    def specs_and_manifests(self) -> None:
        specs = {}
        for path, (content, committed) in self._files("docs/specs", ".md").items():
            status = _frontmatter_status(content.decode("utf-8", "replace"))
            if status is None:
                continue  # not a spec, for example the folder's README
            specs[path] = status
            if status not in CLOSED_SPEC:
                self.add("spec", path, self._since(path, committed),
                         f"status {status or 'missing'}: review it; only the operator accepts a spec "
                         "(status: accepted, accepted_by, accepted_at)" + ("" if committed else "; commit it first"))
        runs = self.common / "agentsmith-runs"
        for path, (content, committed) in self._files(".harness/runs", ".json").items():
            try:
                manifest = json.loads(content.decode("utf-8"))
                run_id, spec = manifest.get("run_id"), manifest.get("spec_path")
            except Exception as exc:
                self.warnings.append(f"manifest {path}: dropped, it is not valid JSON: {_one_line(exc)}")
                continue
            if isinstance(run_id, str) and run_id and (runs / run_id / "state.json").exists():
                continue  # already started; the run row speaks for it
            if not committed:
                step = "commit the reviewed manifest before any run can use it"
            elif specs.get(spec) != "accepted":
                step = f"waits for spec {spec} ({specs.get(spec, 'not found')}) to be accepted"
            else:
                step = f"review scope and limits, then start it: autonomous-run.py start {path}"
            self.add("manifest", path, self._since(path, committed), step)

    def issues(self) -> None:
        assert self.gh is not None
        self.gh.check(self.repo)
        name = self.repo_name or self.gh.repo(self.repo)
        self.pr_heads = self.gh.pr_heads(self.repo, name)
        open_issues = self.gh.issues(self.repo, name)
        claims = read_claims(self.repo)
        numbers = set()
        for issue in open_issues:
            number = issue.get("number")
            numbers.add(number)
            labels = {str(label.get("name", "")).casefold() for label in issue.get("labels") or []}
            if "bug" in labels:
                disposition = "direct (a bug: confirm a reproduction first)"
            elif labels & {"enhancement", "feature"}:
                disposition = "grill or wayfinder (shape the change first)"
            else:
                disposition = "read and route (direct, grill or wayfinder)"
            claim = claims.get(number)
            owned = (f"claimed {claim.get('claimed_at', '')[:10]}" if claim
                     else f"claim it with `agentsmith inbox claim {number}`")
            self.add("untriaged", f"#{number}", _seconds(issue.get("createdAt")),
                     f"{_one_line(issue.get('title', ''))[:80]} - draft disposition: {disposition}; {owned}; "
                     "nothing is written to GitHub")
        for number in sorted(set(claims) - numbers):
            self.warnings.append(f"claim #{number}: not an open issue on {name}; release it with "
                                 f"`agentsmith inbox release {number}`")


def collect(repo: Path, *, now: Callable[[], float] = lambda: dt.datetime.now(dt.timezone.utc).timestamp(),
            gh: Gh | None = None, repo_name: str | None = None, base: str | None = None) -> dict[str, Any]:
    """Derive the inbox. With `gh`, also read open issues and pull requests (read-only)."""
    collector = _Collector(Path(repo), now, gh, repo_name, base)
    if gh is not None:
        collector.issues()  # first: open pull-request heads decide which accepted commits are waiting
    collector.runs()
    collector.integrations()
    collector.specs_and_manifests()
    rows = sorted(collector.rows, key=lambda row: (KIND_ORDER.index(row["kind"]), -(row["age_seconds"] or 0), row["id"]))
    return {"schema_version": SCHEMA_VERSION, "rows": rows, "warnings": collector.warnings}


def _claims_dir(repo: Path) -> Path:
    common = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common is None:
        raise ClaimError(f"{repo} is not a Git repository")
    return Path(common) / "agentsmith-inbox" / "claims"


def read_claims(repo: Path) -> dict[int, dict[str, Any]]:
    directory = _claims_dir(repo)
    claims = {}
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        try:
            claims[int(path.stem)] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return claims


def _issue_number(issue: Any) -> int:
    try:
        number = int(str(issue).lstrip("#"))
    except ValueError:
        number = 0
    if number <= 0:
        raise ClaimError(f"an issue number is a positive integer, not {issue!r}")
    return number


def claim(repo: Path, issue: Any, *, now: Callable[[], float] = lambda: dt.datetime.now(dt.timezone.utc).timestamp()) -> Path:
    """Claim one issue locally. A second claim on the same issue is refused."""
    number = _issue_number(issue)
    directory = _claims_dir(Path(repo))
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{number}.json"
    record = {"issue": number, "claimed_at": dt.datetime.fromtimestamp(now(), dt.timezone.utc).isoformat(timespec="seconds"),
              "by": _git(Path(repo), "config", "user.name")}
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        raise ClaimError(f"#{number} is already claimed; release it first with `agentsmith inbox release {number}`") from None
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return path


def release(repo: Path, issue: Any) -> None:
    number = _issue_number(issue)
    try:
        (_claims_dir(Path(repo)) / f"{number}.json").unlink()
    except FileNotFoundError:
        raise ClaimError(f"#{number} is not claimed") from None


def to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, sort_keys=True, ensure_ascii=True) + "\n"


def render_text(report: dict[str, Any]) -> str:
    if not report["rows"]:
        lines = ["Nothing waits on you."]
    else:
        width = max(len(row["id"]) for row in report["rows"])
        lines = [f"{'KIND':<12} {'ID':<{width}} {'AGE':>4} {'TIER':<5} NEXT"]
        lines += [f"{row['kind']:<12} {row['id']:<{width}} {row['age']:>4} {row['tier'] or '-':<5} {row['next_step']}"
                  for row in report["rows"]]
    lines += [f"warning: {warning}" for warning in report["warnings"]]
    return "\n".join(lines) + "\n"
