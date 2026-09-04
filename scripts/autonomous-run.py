#!/usr/bin/env python3
"""Finite, local-only maker/checker orchestration for Agentsmith.

The controller deliberately has no tracker, push, PR, merge, or deployment adapter.  Its
authority ends at a local worktree and local commits; a human decides what leaves the machine.
"""

from __future__ import annotations

import argparse
import contextlib
import fnmatch
import hashlib
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from native_launcher import (
        build_native_command,
        claude_sandbox_settings,
        minimal_environment,
        native_environment,
        usage_metrics as shared_usage_metrics,
    )
except ModuleNotFoundError:  # source-tree execution from scripts/
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from native_launcher import (
        build_native_command,
        claude_sandbox_settings,
        minimal_environment,
        native_environment,
        usage_metrics as shared_usage_metrics,
    )


SCHEMA_VERSION = 1
RECEIPT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["completed", "accepted", "rejected", "blocked"]},
        "summary": {"type": "string"},
        "commit": {"type": "string"},
        "changed_paths": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "unresolved": {"type": "array", "items": {"type": "string"}},
        "next_state": {"type": "string"},
    },
    "required": ["status", "summary", "commit", "changed_paths", "evidence", "unresolved", "next_state"],
}


class RunError(RuntimeError):
    pass


class RunInterrupted(RunError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(cmd: list[str] | str, cwd: Path, *, timeout: int | None = None,
        env: dict[str, str] | None = None, shell: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout,
                          env=env, shell=shell, check=False)


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = run(["git", *args], repo)
    if check and result.returncode:
        raise RunError(result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def repo_root(path: Path) -> Path:
    result = run(["git", "rev-parse", "--show-toplevel"], path)
    if result.returncode:
        raise RunError("autonomous runs require a git repository")
    return Path(result.stdout.strip()).resolve()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_text(path))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RunError(f"{path} must contain a JSON object")
    return value


def read_text(path: Path) -> str:
    """Read a file while tolerating bounded Windows sharing races."""
    for attempt in range(100):
        try:
            return path.read_text(encoding="utf-8")
        except PermissionError as exc:
            transient_windows_error = os.name == "nt" and getattr(exc, "winerror", None) in {5, 32}
            if not transient_windows_error or attempt == 99:
                raise
            time.sleep(0.01)
    raise AssertionError("unreachable")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        replace_file(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def replace_file(source: Path, destination: Path) -> None:
    """Atomically replace a file, tolerating bounded Windows sharing races."""
    for attempt in range(100):
        try:
            os.replace(source, destination)
            return
        except PermissionError as exc:
            transient_windows_error = os.name == "nt" and getattr(exc, "winerror", None) in {5, 32}
            if not transient_windows_error or attempt == 99:
                raise
            time.sleep(0.01)


def process_is_live(pid: Any) -> bool:
    try:
        number = int(pid)
    except (TypeError, ValueError):
        return False
    if number <= 0:
        return False
    if os.name == "nt":
        return windows_process_is_live(number)
    try:
        os.kill(number, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def windows_process_is_live(pid: int) -> bool:
    """Query a Windows process without using os.kill(), which sends a real signal there."""
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    error_invalid_parameter = 87
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_process.restype = wintypes.HANDLE
    get_exit_code = kernel32.GetExitCodeProcess
    get_exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    get_exit_code.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    handle = open_process(process_query_limited_information, False, pid)
    if not handle:
        # ERROR_ACCESS_DENIED and unknown failures cannot prove the owner is gone. Fail closed
        # so an uncertain probe never lets another controller steal a potentially live lock.
        return ctypes.get_last_error() != error_invalid_parameter
    try:
        exit_code = wintypes.DWORD()
        if not get_exit_code(handle, ctypes.byref(exit_code)):
            return True
        return exit_code.value == still_active
    finally:
        close_handle(handle)


def lock_path(run_dir: Path) -> Path:
    return run_dir / "controller.lock"


def read_lock(run_dir: Path) -> dict[str, Any] | None:
    path = lock_path(run_dir)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunError(f"cannot verify lifecycle lock {path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("pid"), int):
        raise RunError(f"cannot verify lifecycle lock {path}: malformed owner metadata")
    return value


def acquire_lifecycle_lock(run_dir: Path, run_id: str) -> str:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = lock_path(run_dir)
    token = uuid.uuid4().hex
    record = {"pid": os.getpid(), "run_id": run_id, "started_at": now(), "token": token}
    encoded = (json.dumps(record, sort_keys=True) + "\n").encode()
    for _ in range(3):
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            existing = read_lock(run_dir)
            if existing is None:
                continue
            if process_is_live(existing["pid"]):
                raise RunError(
                    f"run {run_id} already has a live controller (pid {existing['pid']})"
                )
            try:
                before = path.read_bytes()
                if path.read_bytes() == before:
                    path.unlink(missing_ok=True)
            except FileNotFoundError:
                pass
            continue
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        return token
    raise RunError(f"could not acquire lifecycle lock for run {run_id}")


def release_lifecycle_lock(run_dir: Path, token: str) -> None:
    path = lock_path(run_dir)
    try:
        record = read_lock(run_dir)
    except RunError:
        return
    if record and record.get("token") == token:
        path.unlink(missing_ok=True)


def coordination_lock_path(root: Path) -> Path:
    return root / "coordination.lock"


def read_coordination_lock(root: Path) -> dict[str, Any] | None:
    path = coordination_lock_path(root)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunError(f"cannot verify repository coordination lock {path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("pid"), int):
        raise RunError(f"cannot verify repository coordination lock {path}: malformed owner metadata")
    return value


@contextlib.contextmanager
def coordination_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    path = coordination_lock_path(root)
    token = uuid.uuid4().hex
    record = {"pid": os.getpid(), "run_id": "coordination", "started_at": now(), "token": token}
    encoded = (json.dumps(record, sort_keys=True) + "\n").encode()
    deadline = time.monotonic() + 10
    while True:
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            existing = read_coordination_lock(root)
            if existing is None:
                continue
            if process_is_live(existing["pid"]):
                if time.monotonic() >= deadline:
                    raise RunError(
                        f"repository coordination is still held by live process {existing['pid']}"
                    )
                time.sleep(0.02)
                continue
            try:
                before = path.read_bytes()
                if path.read_bytes() == before:
                    path.unlink(missing_ok=True)
            except FileNotFoundError:
                pass
            continue
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        break
    try:
        yield
    finally:
        try:
            existing = read_coordination_lock(root)
        except RunError:
            existing = None
        if existing and existing.get("token") == token:
            path.unlink(missing_ok=True)


def create_stop_request(run_dir: Path) -> None:
    path = run_dir / "STOP"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(f"requested_at={now()}\n")
        handle.flush()
        os.fsync(handle.fileno())


def state_root(repo: Path) -> Path:
    common = git(repo, "rev-parse", "--git-common-dir")
    common_path = Path(common)
    if not common_path.is_absolute():
        common_path = (repo / common_path).resolve()
    return common_path / "agentsmith-runs"


def state_path(repo: Path, run_id: str) -> Path:
    return state_root(repo) / run_id / "state.json"


def live_run_scope(repo: Path, run_dir: Path, owner: dict[str, Any]) -> tuple[str, dict[str, list[str]]]:
    run_id = run_dir.name
    try:
        if owner.get("run_id") != run_id:
            raise RunError("lifecycle lock run_id does not match its directory")
        state_file = run_dir / "state.json"
        state = load_json(state_file)
        if state.get("run_id") != run_id:
            raise RunError("state run_id does not match its directory")
        if state.get("controller_pid") != owner.get("pid"):
            raise RunError("lifecycle lock pid does not match durable state")
        token = owner.get("token")
        if not isinstance(token, str) or not token or state.get("controller_token") != token:
            raise RunError("lifecycle lock token does not match durable state")
        manifest_value = state.get("manifest_path")
        if not isinstance(manifest_value, str):
            raise RunError("state has no manifest_path")
        manifest_path = Path(manifest_value).resolve()
        if not manifest_path.is_relative_to(repo):
            raise RunError("manifest path is outside the repository")
        expected_hash = state.get("manifest_sha256")
        if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise RunError("state has no valid manifest hash")
        if not manifest_path.is_file() or hashlib.sha256(manifest_path.read_bytes()).hexdigest() != expected_hash:
            raise RunError("manifest no longer matches durable state")
        manifest = load_json(manifest_path)
        if str(manifest.get("run_id")) != run_id:
            raise RunError("manifest run_id does not match durable state")
        return run_id, normalized_scope(manifest.get("scope"))
    except (OSError, RunError) as exc:
        raise RunError(f"cannot verify scope for live run {run_id}: {exc}") from exc


def assert_no_live_scope_conflicts(repo: Path, run_id: str, scope: Any) -> None:
    candidate = normalized_scope(scope)
    root = state_root(repo)
    if not root.exists():
        return
    for run_dir in sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.name):
        if run_dir.name == run_id:
            continue
        owner = read_lock(run_dir)
        if owner is None or not process_is_live(owner["pid"]):
            continue
        other_id, other_scope = live_run_scope(repo, run_dir, owner)
        collision = scope_collision(candidate, other_scope)
        if collision is None:
            continue
        kind, value = collision
        if kind == "path":
            raise RunError(
                f"run {run_id} conflicts with live run {other_id}: overlapping path scope '{value}'"
            )
        raise RunError(
            f"run {run_id} conflicts with live run {other_id}: shared resource '{value}'"
        )


def event(state: dict[str, Any], kind: str, **fields: Any) -> None:
    path = Path(state["state_path"]).parent / "events.jsonl"
    record = {"at": now(), "event": kind, **fields}
    with path.open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def save_state(state: dict[str, Any], kind: str | None = None, **fields: Any) -> None:
    state["updated_at"] = now()
    write_json(Path(state["state_path"]), state)
    if kind:
        event(state, kind, **fields)


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        raise RunError("spec must begin with YAML-style frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise RunError("spec frontmatter is not closed")
    values: dict[str, str] = {}
    for raw in text[4:end].splitlines():
        if not raw.strip() or raw.lstrip().startswith("#") or ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values


RESOURCE_KEY = re.compile(r"[a-z][a-z0-9_-]*:[a-z0-9][a-z0-9._/-]*\Z")


def scope_resources(scope: dict[str, Any]) -> list[str]:
    resources = scope.get("resources", [])
    if not isinstance(resources, list) or not all(isinstance(item, str) for item in resources):
        raise RunError("scope.resources must be an array of lowercase coordination keys")
    if any(not RESOURCE_KEY.fullmatch(item) for item in resources):
        raise RunError("scope.resources entries must match <kind>:<identifier> in lowercase")
    if len(resources) != len(set(resources)):
        raise RunError("scope.resources entries must be unique")
    return list(resources)


def scope_paths(scope: dict[str, Any], key: str) -> list[str]:
    paths = scope.get(key, [])
    if not isinstance(paths, list) or not all(isinstance(item, str) and item for item in paths):
        raise RunError(f"scope.{key} must be an array of repository-relative glob strings")
    for pattern in paths:
        parts = pattern.split("/")
        if pattern.startswith("/") or "\\" in pattern or "." in parts or ".." in parts:
            raise RunError(f"scope.{key} entries must be repository-relative POSIX globs")
    return list(paths)


def normalized_scope(scope: Any) -> dict[str, list[str]]:
    if not isinstance(scope, dict):
        raise RunError("scope must be a JSON object")
    allowed = scope_paths(scope, "allowed_paths")
    if not allowed:
        raise RunError("scope.allowed_paths must reserve at least one path")
    return {
        "allowed_paths": allowed,
        "denied_paths": scope_paths(scope, "denied_paths"),
        "resources": scope_resources(scope),
    }


def fixed_prefix(pattern: str) -> str:
    for index, segment in enumerate(pattern.split("/")):
        if any(marker in segment for marker in "*?["):
            literal = pattern.split("/")[:index]
            return "/".join(literal) if literal else "."
    return pattern.rstrip("/") or "."


def prefixes_overlap(left: str, right: str) -> bool:
    if left == "." or right == ".":
        return True
    left_parts = tuple(part for part in left.split("/") if part)
    right_parts = tuple(part for part in right.split("/") if part)
    shared = min(len(left_parts), len(right_parts))
    return left_parts[:shared] == right_parts[:shared]


def scope_collision(left_scope: Any, right_scope: Any) -> tuple[str, str] | None:
    left = normalized_scope(left_scope)
    right = normalized_scope(right_scope)
    for left_pattern in left["allowed_paths"]:
        left_prefix = fixed_prefix(left_pattern)
        for right_pattern in right["allowed_paths"]:
            right_prefix = fixed_prefix(right_pattern)
            if prefixes_overlap(left_prefix, right_prefix):
                if "." in {left_prefix, right_prefix}:
                    return "path", "."
                left_parts = left_prefix.split("/")
                right_parts = right_prefix.split("/")
                return "path", left_prefix if len(left_parts) <= len(right_parts) else right_prefix
    shared_resources = sorted(set(left["resources"]) & set(right["resources"]))
    if shared_resources:
        return "resource", shared_resources[0]
    return None


def validate_manifest(manifest: dict[str, Any], repo: Path) -> tuple[Path, str]:
    required = ["schema_version", "run_id", "spec_path", "implementation_ticket", "base_ref",
                "roles", "scope", "verify", "limits", "git", "external_writes"]
    missing = [key for key in required if key not in manifest]
    if missing:
        raise RunError(f"manifest missing: {', '.join(missing)}")
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise RunError(f"unsupported schema_version {manifest['schema_version']}")
    run_id = str(manifest["run_id"])
    if not run_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in run_id):
        raise RunError("run_id may contain only letters, digits, '-' and '_'")
    if not str(manifest["implementation_ticket"]).strip():
        raise RunError("implementation_ticket is required; a decision ticket is not executable work")
    if manifest["external_writes"] is not False:
        raise RunError("v1 requires external_writes=false")
    normalized_scope(manifest["scope"])
    git_policy = manifest["git"]
    expected = {"local_commits": True, "push": False, "merge": False, "history_rewrite": False}
    if any(git_policy.get(k) != v for k, v in expected.items()):
        raise RunError("git policy must allow local commits only and forbid push/merge/history rewrite")
    for role in ("maker", "checker"):
        config = manifest["roles"].get(role, {})
        if config.get("runtime") not in {"claude", "codex"}:
            raise RunError(f"roles.{role}.runtime must be claude or codex")
    limits = manifest["limits"]
    if not 1 <= int(limits.get("max_attempts", 0)) <= 3:
        raise RunError("limits.max_attempts must be between 1 and 3")
    if int(limits.get("wall_minutes", 0)) <= 0:
        raise RunError("limits.wall_minutes must be positive")
    spec_rel = Path(str(manifest["spec_path"]))
    if spec_rel.is_absolute() or ".." in spec_rel.parts or spec_rel.parts[:2] != ("docs", "specs"):
        raise RunError("spec_path must be a repository-relative path under docs/specs/")
    shown = git(repo, "show", f"{manifest['base_ref']}:{spec_rel.as_posix()}", check=False)
    if not shown:
        raise RunError("accepted spec must be committed at base_ref")
    meta = frontmatter(shown)
    if meta.get("status") != "accepted":
        raise RunError("spec status must be accepted; agents may only author draft specs")
    if not meta.get("accepted_by") or not meta.get("accepted_at"):
        raise RunError("accepted spec requires accepted_by and accepted_at")
    if not meta.get("decision_ticket"):
        raise RunError("accepted spec requires a decision_ticket reference")
    if str(manifest["implementation_ticket"]) == meta.get("decision_ticket"):
        raise RunError("implementation_ticket must be separate from decision_ticket")
    digest = hashlib.sha256(shown.encode()).hexdigest()
    return spec_rel, digest


def prepare(args: argparse.Namespace) -> int:
    repo = repo_root(Path.cwd())
    if args.template:
        source = Path(args.template).resolve()
    else:
        source = repo / "templates/autonomous-run.json"
        if not source.exists():
            source = repo / ".harness/templates/autonomous-run.json"
    manifest = load_json(source)
    manifest["run_id"] = args.run_id
    manifest["spec_path"] = args.spec
    manifest["implementation_ticket"] = args.ticket
    if args.maker:
        manifest["roles"]["maker"]["runtime"] = args.maker
    if args.checker:
        manifest["roles"]["checker"]["runtime"] = args.checker
    output = Path(args.output or f".harness/runs/{args.run_id}.json")
    output = output if output.is_absolute() else repo / output
    if output.exists() and not args.force:
        raise RunError(f"refusing to overwrite {output}; pass --force deliberately")
    write_json(output, manifest)
    print(f"prepared {output.relative_to(repo) if output.is_relative_to(repo) else output}")
    print("review and commit the manifest, then invoke 'start' explicitly to authorize execution")
    return 0


def clean(repo: Path) -> bool:
    return not git(repo, "status", "--porcelain")


def load_run(repo: Path, run_id: str) -> dict[str, Any]:
    path = state_path(repo, run_id)
    if not path.exists():
        raise RunError(f"no run state for {run_id}")
    return load_json(path)


def remaining_seconds(state: dict[str, Any], manifest: dict[str, Any]) -> int:
    return max(0, int(float(state["deadline_epoch"]) - time.time()))


def changed_paths(worktree: Path, base: str, head: str = "HEAD") -> list[str]:
    output = git(worktree, "diff", "--name-only", f"{base}..{head}")
    return [line for line in output.splitlines() if line]


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"


def resolved_git_path(repo: Path, argument: str) -> Path:
    raw = Path(git(repo, "rev-parse", argument))
    return raw.resolve() if raw.is_absolute() else (repo / raw).resolve()


def registered_run_git_artifacts(common: Path, active_ref: str) -> tuple[set[str], set[Path], set[Path]]:
    other_refs: set[str] = set()
    branch_logs: set[Path] = set()
    worktree_admin: set[Path] = set()
    runs = common / "agentsmith-runs"
    if not runs.is_dir():
        return other_refs, branch_logs, worktree_admin
    for state_file in runs.glob("*/state.json"):
        try:
            state = load_json(state_file)
            run_id = state_file.parent.name
            owner = read_lock(state_file.parent)
            if owner is None or not process_is_live(owner["pid"]):
                continue
            repo_value = state.get("repo")
            if not isinstance(repo_value, str):
                continue
            recorded_repo = Path(repo_value).resolve()
            if state_root(recorded_repo).resolve() != runs.resolve():
                continue
            verified_run_id, _ = live_run_scope(recorded_repo, state_file.parent, owner)
            if verified_run_id != run_id:
                continue
            branch = state.get("branch")
            if state.get("run_id") != run_id or branch != f"agentsmith/{run_id}":
                continue
            ref = f"refs/heads/{branch}"
            if ref != active_ref:
                other_refs.add(ref)
                branch_logs.add(Path("logs") / ref)
            candidates = [state.get("worktree"), state.get("checker_worktree")]
            for candidate in candidates:
                if not isinstance(candidate, str):
                    continue
                dot_git = Path(candidate) / ".git"
                if not dot_git.is_file():
                    continue
                marker = dot_git.read_text(encoding="utf-8", errors="replace").strip()
                if not marker.startswith("gitdir: "):
                    continue
                git_dir = Path(marker[8:]).resolve()
                if git_dir.is_relative_to(common):
                    worktree_admin.add(git_dir.relative_to(common))
        except (OSError, RunError):
            # Unverifiable state earns no exclusion. Its Git changes therefore remain protected
            # and make the caller fail closed instead of being mistaken for controller activity.
            continue
    return other_refs, branch_logs, worktree_admin


def git_metadata(repo: Path) -> dict[str, Any]:
    common = resolved_git_path(repo, "--git-common-dir")
    active = resolved_git_path(repo, "--git-dir")
    active_rel = active.relative_to(common) if active.is_relative_to(common) else None
    branch_ref = git(repo, "symbolic-ref", "-q", "HEAD", check=False)
    other_run_refs, run_branch_logs, run_worktree_admin = registered_run_git_artifacts(
        common, branch_ref
    )
    hooks: list[tuple[str, str]] = []
    hooks_dir = common / "hooks"
    if hooks_dir.is_dir():
        for path in sorted(item for item in hooks_dir.rglob("*") if item.is_file()):
            hooks.append((str(path.relative_to(hooks_dir)), file_digest(path)))
    protected: list[tuple[str, str]] = []
    objects: list[tuple[str, str]] = []
    branch_log = Path("logs") / branch_ref if branch_ref else None
    for path in sorted(item for item in common.rglob("*") if item.is_file()):
        rel = path.relative_to(common)
        if rel.parts[0] == "agentsmith-runs":
            continue
        if rel.parts[0] == "objects":
            objects.append((rel.as_posix(), file_digest(path)))
            continue
        if rel.parts[0] == "refs" or (branch_log and rel == branch_log) or rel in run_branch_logs:
            continue
        if active_rel and (rel == active_rel or active_rel in rel.parents):
            continue
        if any(rel == admin or admin in rel.parents for admin in run_worktree_admin):
            continue
        protected.append((rel.as_posix(), file_digest(path)))
    refs = [
        line for line in git(repo, "for-each-ref", "--format=%(refname) %(objectname)").splitlines()
        if line.split(" ", 1)[0] not in other_run_refs
    ]
    return {
        "refs": refs,
        "config": file_digest(common / "config"),
        "config_worktree": file_digest(common / "config.worktree"),
        "hooks": hooks,
        "protected_files": protected,
        "existing_objects": objects,
    }


def ignored_paths(worktree: Path) -> set[str]:
    output = git(worktree, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
    return {path for path in output.split("\0") if path}


def validate_git_transition(worktree: Path, before: dict[str, Any], after: dict[str, Any],
                            branch: str, old_head: str, new_head: str) -> None:
    expected_ref = f"refs/heads/{branch} {new_head}"
    before_other = [line for line in before["refs"] if not line.startswith(f"refs/heads/{branch} ")]
    after_other = [line for line in after["refs"] if not line.startswith(f"refs/heads/{branch} ")]
    if before_other != after_other or expected_ref not in after["refs"]:
        raise RunError("runtime changed Git refs outside the active run branch")
    for key in ("config", "config_worktree", "hooks", "protected_files"):
        if before[key] != after[key]:
            raise RunError(f"runtime changed protected Git metadata: {key}")
    after_objects = dict(after["existing_objects"])
    altered_objects = [path for path, digest in before["existing_objects"]
                       if after_objects.get(path) != digest]
    if altered_objects:
        raise RunError("runtime altered existing Git objects")
    before_object_paths = {path for path, _ in before["existing_objects"]}
    new_objects = set(after_objects) - before_object_paths
    invalid_objects = sorted(path for path in new_objects
                             if not re.fullmatch(r"objects/[0-9a-f]{2}/[0-9a-f]{38}", path))
    if invalid_objects:
        raise RunError(f"runtime created non-object files in Git's object store: {', '.join(invalid_objects)}")
    ancestor = run(["git", "merge-base", "--is-ancestor", old_head, new_head], worktree)
    if ancestor.returncode:
        raise RunError("maker history is not a fast-forward from the previous attempt")


def validate_git_unchanged(before: dict[str, Any], after: dict[str, Any], actor: str) -> None:
    for key in ("refs", "config", "config_worktree", "hooks", "protected_files", "existing_objects"):
        if before[key] != after[key]:
            raise RunError(f"{actor} changed protected Git metadata: {key}")


def sandboxed_verify(command: str, cwd: Path, timeout: int, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the human-approved verifier with no network and no writes outside its worktree."""
    common = resolved_git_path(cwd, "--git-common-dir")
    if sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").exists():
        escaped = str(cwd).replace('"', '\\"')
        escaped_common = str(common).replace('"', '\\"')
        home = str(Path.home()).replace('"', '\\"')
        profile = "\n".join([
            "(version 1)",
            "(allow default)",
            "(deny network*)",
            "(deny file-write*)",
            f'(deny file-read-data (require-all (subpath "{home}") '
            f'(require-not (subpath "{escaped}")) (require-not (subpath "{escaped_common}"))))',
            f'(allow file-write* (subpath "{escaped}"))',
            '(allow file-write* (subpath "/tmp") (subpath "/private/tmp"))',
            '(allow file-write* (literal "/dev/null") (literal "/dev/dtracehelper"))',
        ])
        return run(["/usr/bin/sandbox-exec", "-p", profile, "/bin/bash", "-c", command],
                   cwd, timeout=timeout, env=env)
    if sys.platform.startswith("linux") and shutil.which("bwrap"):
        home = Path.home().resolve()
        args = ["bwrap", "--unshare-net", "--die-with-parent", "--ro-bind", "/", "/",
                "--tmpfs", str(home)]
        directories: set[Path] = set()
        for target in (cwd.resolve(), common):
            if target.is_relative_to(home):
                current = home
                for part in target.relative_to(home).parts:
                    current /= part
                    directories.add(current)
        for directory in sorted(directories, key=lambda item: len(item.parts)):
            args += ["--dir", str(directory)]
        args += ["--bind", str(cwd), str(cwd), "--ro-bind", str(common), str(common),
                 "--tmpfs", "/tmp", "--dev", "/dev", "--proc", "/proc",
                 "--chdir", str(cwd), "/bin/bash", "-c", command]
        return run(args,
                   cwd, timeout=timeout, env=env)
    return subprocess.CompletedProcess([], 126, "", "no supported fail-closed verifier sandbox (macOS sandbox-exec or Linux bubblewrap)")


def path_allowed(path: str, manifest: dict[str, Any]) -> bool:
    scope = manifest["scope"]
    denied = scope.get("denied_paths", [])
    allowed = scope.get("allowed_paths", [])
    if any(fnmatch.fnmatch(path, pattern) or path == pattern.rstrip("/**") for pattern in denied):
        return False
    return bool(allowed) and any(fnmatch.fnmatch(path, pattern) or path == pattern.rstrip("/**") for pattern in allowed)


def receipt_from(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        if set(RECEIPT_SCHEMA["required"]).issubset(value):
            return value
        for key in ("structured_output", "result", "output", "message", "content", "item"):
            if key in value:
                found = receipt_from(value[key])
                if found:
                    return found
        for child in value.values():
            found = receipt_from(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in reversed(value):
            found = receipt_from(child)
            if found:
                return found
    elif isinstance(value, str):
        try:
            return receipt_from(json.loads(value))
        except json.JSONDecodeError:
            return None
    return None


def parse_receipt(path: Path, stdout: str) -> dict[str, Any]:
    candidates: list[Any] = []
    if path.exists():
        try:
            candidates.append(json.loads(path.read_text()))
        except json.JSONDecodeError:
            pass
    try:
        candidates.append(json.loads(stdout))
    except json.JSONDecodeError:
        for line in stdout.splitlines():
            try:
                candidates.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    for value in reversed(candidates):
        found = receipt_from(value)
        if found:
            if found.get("status") not in {"completed", "accepted", "rejected", "blocked"}:
                continue
            if not all(isinstance(found.get(key), str) for key in ("summary", "commit", "next_state")):
                continue
            if not all(isinstance(found.get(key), list) and
                       all(isinstance(item, str) for item in found[key])
                       for key in ("changed_paths", "evidence", "unresolved")):
                continue
            if set(found) != set(RECEIPT_SCHEMA["required"]):
                continue
            return found
    raise RunError("runtime emitted no schema-valid receipt")


def verifier_env() -> dict[str, str]:
    allowed = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TMPDIR", "SHELL")
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env.update({"HOME": "/tmp/agentsmith-verifier-home", "CI": "1",
                "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/usr/bin/false"})
    return env


def usage_metrics(stdout: str) -> tuple[float, int]:
    """Extract conservative per-invocation usage totals from Claude/Codex JSON output."""
    return shared_usage_metrics(stdout)


def launch_role(state: dict[str, Any], manifest: dict[str, Any], role: str, prompt: str,
                *, role_worktree: Path | None = None) -> dict[str, Any]:
    worktree = role_worktree or Path(state["worktree"])
    role_cfg = manifest["roles"][role]
    runtime = role_cfg["runtime"]
    run_dir = Path(state["state_path"]).parent
    stop_file = run_dir / "STOP"
    if stop_file.exists():
        raise RunInterrupted("stopped by operator")
    receipt_path = run_dir / f"attempt-{state['attempt']}-{role}-receipt.json"
    schema_path = run_dir / "receipt-schema.json"
    write_json(schema_path, RECEIPT_SCHEMA)
    timeout = remaining_seconds(state, manifest)
    if timeout <= 0:
        raise RunError("wall-clock budget exhausted")
    common_git = state_root(Path(state["repo"])).parent
    if runtime == "codex":
        token_budget = int(manifest["limits"].get("codex_goal_tokens", 0))
        if token_budget and int(state.get("codex_tokens_used", 0)) >= token_budget:
            raise RunError("Codex run-wide token budget exhausted")
        cmd = build_native_command(
            "codex", prompt, worktree, schema_path, receipt_path,
            extra_write_dirs=[common_git] if role == "maker" else [],
            model=str(role_cfg.get("model", "")), effort=str(role_cfg.get("effort", "")),
        )
    else:
        settings_path = run_dir / "claude-sandbox.json"
        write_json(
            settings_path,
            claude_sandbox_settings(
                worktree, [common_git] if role == "maker" else [], read_only=role == "checker",
            ),
        )
        budget = float(manifest["limits"].get("claude_max_usd", 0))
        remaining_budget = budget - float(state.get("claude_cost_usd", 0.0))
        if budget and remaining_budget <= 0:
            raise RunError("Claude run-wide USD budget exhausted")
        cmd = build_native_command(
            "claude", prompt, worktree, schema_path, receipt_path, settings_path=settings_path,
            extra_write_dirs=[common_git] if role == "maker" else [], read_only=role == "checker",
            model=str(role_cfg.get("model", "")), effort=str(role_cfg.get("effort", "")),
            claude_max_usd=max(0.0, remaining_budget),
        )
    event(state, "role_started", role=role, runtime=runtime, attempt=state["attempt"])
    with native_environment(runtime) as environment:
        process = subprocess.Popen(cmd, cwd=worktree, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=environment)
        if stop_file.exists():
            process.terminate()
            process.wait(timeout=10)
            raise RunInterrupted("stopped by operator")
        state["active_pid"] = process.pid
        save_state(state)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            raise RunError(f"{role} exceeded wall-clock budget")
        finally:
            if process.poll() is None and stop_file.exists():
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
            state["active_pid"] = None
            save_state(state)
    (run_dir / f"attempt-{state['attempt']}-{role}.stdout").write_text(stdout)
    (run_dir / f"attempt-{state['attempt']}-{role}.stderr").write_text(stderr)
    cost, tokens = usage_metrics(stdout)
    if runtime == "claude":
        state["claude_cost_usd"] = float(state.get("claude_cost_usd", 0.0)) + cost
        tokens = 0
    else:
        state["codex_tokens_used"] = int(state.get("codex_tokens_used", 0)) + tokens
        cost = 0.0
    save_state(state, "usage_recorded", role=role, runtime=runtime, cost_usd=cost, tokens=tokens)
    max_cost = float(manifest["limits"].get("claude_max_usd", 0))
    if max_cost and state["claude_cost_usd"] > max_cost:
        raise RunError("Claude run-wide USD budget exceeded")
    max_tokens = int(manifest["limits"].get("codex_goal_tokens", 0))
    if max_tokens and state["codex_tokens_used"] > max_tokens:
        raise RunError("Codex run-wide token budget exceeded")
    if process.returncode:
        if state.get("status") == "interrupted" or stop_file.exists():
            raise RunInterrupted("stopped by operator")
        raise RunError(f"{runtime} {role} exited {process.returncode}: {stderr[-500:].strip()}")
    receipt = parse_receipt(receipt_path, stdout)
    write_json(receipt_path, receipt)
    event(state, "role_completed", role=role, status=receipt["status"], attempt=state["attempt"])
    return receipt


def role_prompt(state: dict[str, Any], manifest: dict[str, Any], role: str,
                prior: dict[str, Any] | None = None, verify_output: str = "") -> str:
    spec = manifest["spec_path"]
    scope = manifest["scope"]
    base = state["base_head"]
    common = f"""Run {state['run_id']} for implementation ticket {manifest['implementation_ticket']}.
Read the accepted terminal spec at {spec}. This ticket is separate from its decision ticket.
Allowed paths: {json.dumps(scope['allowed_paths'])}. Denied paths: {json.dumps(scope['denied_paths'])}.
No network, connectors, tracker writes, push, PR, merge, deployment, production action, or history rewrite.
Return only the requested JSON receipt. Never claim evidence you did not produce.
"""
    if role == "maker":
        feedback = f"\nThe prior checker rejected the attempt:\n{json.dumps(prior, indent=2)}\n" if prior else ""
        goal_budget = int(manifest["limits"].get("codex_goal_tokens", 0)) - int(state.get("codex_tokens_used", 0))
        goal = (f"If your runtime exposes the native goal tool, create a goal for this exact ticket with token budget "
                f"{goal_budget}; the manifest remains authoritative.\n") if (
                    manifest["roles"]["maker"]["runtime"] == "codex" and goal_budget > 0) else ""
        return common + goal + f"""Implement the smallest complete change, run {manifest['verify']['command']},
and make atomic local commits only. Leave the worktree clean. HEAD must advance beyond {base}.
Use status completed or blocked; do not mark your own work accepted.{feedback}"""
    return common + f"""You are the independent checker and default to REJECT. Do not edit files or commit.
Inspect the committed diff from {base} to HEAD, rerun the real verification command yourself
({manifest['verify']['command']}), and try to falsify the acceptance criteria. Controller verification output:
{verify_output[-6000:]}
Use status accepted, rejected, or blocked."""


def execute(state: dict[str, Any], manifest: dict[str, Any]) -> int:
    worktree = Path(state["worktree"])
    max_attempts = int(manifest["limits"]["max_attempts"])
    prior = state.get("last_checker_receipt")
    while state["attempt"] < max_attempts:
        if (Path(state["state_path"]).parent / "STOP").exists():
            raise RunInterrupted("stopped by operator")
        if remaining_seconds(state, manifest) <= 0:
            raise RunError("wall-clock budget exhausted")
        state["attempt"] += 1
        state["status"] = "making"
        save_state(state, "attempt_started", attempt=state["attempt"])
        before_head = git(worktree, "rev-parse", "HEAD")
        before_meta = git_metadata(worktree)
        before_ignored = ignored_paths(worktree)
        maker_error: Exception | None = None
        maker: dict[str, Any] | None = None
        try:
            maker = launch_role(state, manifest, "maker", role_prompt(state, manifest, "maker", prior))
        except Exception as exc:
            maker_error = exc
        after_head = git(worktree, "rev-parse", "HEAD")
        validate_git_transition(worktree, before_meta, git_metadata(worktree), state["branch"],
                                before_head, after_head)
        if maker_error:
            raise maker_error
        assert maker is not None
        if maker["status"] == "blocked":
            raise RunError(f"maker blocked: {maker['summary']}")
        if after_head == before_head:
            raise RunError("maker completed without creating a local commit")
        if not clean(worktree):
            raise RunError("maker left the worktree dirty")
        paths = changed_paths(worktree, state["base_head"])
        bad = [path for path in paths if not path_allowed(path, manifest)]
        if bad:
            raise RunError(f"maker changed paths outside scope: {', '.join(bad)}")
        ignored_added = sorted(ignored_paths(worktree) - before_ignored)
        ignored_bad = [path for path in ignored_added if not path_allowed(path, manifest)]
        if ignored_bad:
            raise RunError(f"maker created ignored paths outside scope: {', '.join(ignored_bad)}")
        if maker["commit"] != after_head or sorted(maker["changed_paths"]) != sorted(paths):
            raise RunError("maker receipt does not match the committed Git state")
        state["status"] = "checking"
        save_state(state)
        checker_head = git(worktree, "rev-parse", "HEAD")
        checker_worktree = worktree.with_name(f"{worktree.name}-check-{state['attempt']}")
        if checker_worktree.exists():
            raise RunError(f"refusing to overwrite checker worktree {checker_worktree}")
        state["checker_worktree"] = str(checker_worktree)
        save_state(state)
        added = run(["git", "worktree", "add", "--detach", str(checker_worktree), checker_head],
                    Path(state["repo"]))
        if added.returncode:
            state.pop("checker_worktree", None)
            save_state(state)
            raise RunError(added.stderr.strip() or "checker worktree creation failed")
        try:
            verify = sandboxed_verify(manifest["verify"]["command"], checker_worktree,
                                      remaining_seconds(state, manifest), verifier_env())
            verify_output = f"exit={verify.returncode}\nSTDOUT:\n{verify.stdout}\nSTDERR:\n{verify.stderr}"
            verify_path = Path(state["state_path"]).parent / f"attempt-{state['attempt']}-verify.txt"
            verify_path.write_text(verify_output)
            checker_status = git(checker_worktree, "status", "--porcelain")
            if checker_status:
                raise RunError("verifier modified tracked state")
            checker_ignored = ignored_paths(checker_worktree)
            checker_meta = git_metadata(checker_worktree)
            checker_error: Exception | None = None
            checker: dict[str, Any] | None = None
            try:
                checker = launch_role(state, manifest, "checker",
                                      role_prompt(state, manifest, "checker", verify_output=verify_output),
                                      role_worktree=checker_worktree)
            except Exception as exc:
                checker_error = exc
            validate_git_unchanged(checker_meta, git_metadata(checker_worktree), "checker")
            if (git(checker_worktree, "rev-parse", "HEAD") != checker_head or
                    git(checker_worktree, "status", "--porcelain") != checker_status or
                    ignored_paths(checker_worktree) != checker_ignored):
                raise RunError("checker modified its disposable worktree")
            if checker_error:
                raise checker_error
            assert checker is not None
            if checker["commit"] != checker_head or sorted(checker["changed_paths"]) != sorted(paths):
                raise RunError("checker receipt does not match the committed Git state")
        finally:
            removed = run(["git", "worktree", "remove", "--force", str(checker_worktree)],
                          Path(state["repo"]))
            if removed.returncode:
                event(state, "checker_worktree_cleanup_failed", path=str(checker_worktree),
                      error=removed.stderr.strip())
                raise RunError(f"could not remove disposable checker worktree: {removed.stderr.strip()}")
            state.pop("checker_worktree", None)
            save_state(state)
        if verify.returncode == 0 and checker["status"] == "accepted":
            state["status"] = "accepted"
            state["accepted_commit"] = checker_head
            state["last_checker_receipt"] = checker
            save_state(state, "run_accepted", commit=checker_head)
            print(f"accepted locally: {state['branch']} at {checker_head}")
            print(f"worktree retained for human review: {worktree}")
            print("nothing was pushed, merged, or written to an external system")
            return 0
        prior = checker
        state["last_checker_receipt"] = checker
        state["status"] = "retrying"
        save_state(state, "attempt_rejected", attempt=state["attempt"], verify_exit=verify.returncode)
    state["status"] = "escalated"
    state["reason"] = f"attempt cap reached ({max_attempts})"
    save_state(state, "run_escalated", reason=state["reason"])
    print(state["reason"], file=sys.stderr)
    return 2


def persist_interrupted(state: dict[str, Any]) -> None:
    if state.get("status") == "interrupted":
        return
    state["status"] = "interrupted"
    state["reason"] = "stopped by operator"
    state["active_pid"] = None
    save_state(state, "run_interrupted", reason=state["reason"])


def run_controller(state: dict[str, Any], manifest: dict[str, Any]) -> int:
    previous = signal.getsignal(signal.SIGTERM)

    def interrupted(_signum: int, _frame: Any) -> None:
        raise RunInterrupted("stopped by operator")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        return execute(state, manifest)
    except RunInterrupted:
        persist_interrupted(state)
        print(f"interrupted: {state['run_id']}; use resume when ready", file=sys.stderr)
        return 130
    except (RunError, subprocess.TimeoutExpired) as exc:
        state["status"] = "escalated"
        state["reason"] = str(exc)
        save_state(state, "run_escalated", reason=str(exc))
        print(f"escalated: {exc}", file=sys.stderr)
        return 2
    finally:
        signal.signal(signal.SIGTERM, previous)


def start(args: argparse.Namespace) -> int:
    repo = repo_root(Path.cwd())
    manifest_path = Path(args.manifest).resolve()
    manifest = load_json(manifest_path)
    spec_rel, spec_hash = validate_manifest(manifest, repo)
    if not clean(repo):
        raise RunError("base worktree must be clean before an autonomous run starts")
    try:
        manifest_rel = manifest_path.relative_to(repo)
    except ValueError as exc:
        raise RunError("run manifest must live inside the repository") from exc
    tracked = run(["git", "ls-files", "--error-unmatch", str(manifest_rel)], repo)
    if tracked.returncode:
        raise RunError("run manifest must be committed before start")
    name = str(manifest["run_id"])
    path = state_path(repo, name)
    if path.exists():
        raise RunError(f"run {name} already exists; use resume or choose another run_id")
    token: str | None = None
    try:
        with coordination_lock(state_root(repo)):
            token = acquire_lifecycle_lock(path.parent, name)
            if path.exists():
                raise RunError(f"run {name} already exists; use resume or choose another run_id")
            assert_no_live_scope_conflicts(repo, name, manifest["scope"])
            base_head = git(repo, "rev-parse", str(manifest["base_ref"]))
            if (not git(repo, "config", "user.name", check=False)
                    or not git(repo, "config", "user.email", check=False)):
                raise RunError("git user.name and user.email must be configured before local commits")
            branch = f"agentsmith/{name}"
            default_worktree = repo.parent / f"{repo.name}-{name}"
            worktree = Path(manifest.get("worktree_path") or default_worktree).resolve()
            if worktree.exists() or git(repo, "show-ref", "--verify", f"refs/heads/{branch}", check=False):
                raise RunError(f"refusing to overwrite existing branch/worktree for {name}")
            created = run(["git", "worktree", "add", "-b", branch, str(worktree), base_head], repo)
            if created.returncode:
                raise RunError(created.stderr.strip() or "git worktree creation failed")
            state = {
                "schema_version": SCHEMA_VERSION,
                "run_id": name,
                "status": "prepared",
                "attempt": 0,
                "repo": str(repo),
                "worktree": str(worktree),
                "branch": branch,
                "base_head": base_head,
                "spec_path": spec_rel.as_posix(),
                "spec_sha256": spec_hash,
                "manifest_path": str(manifest_path),
                "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "scope": normalized_scope(manifest["scope"]),
                "started_at": now(),
                "started_epoch": time.time(),
                "deadline_epoch": time.time() + int(manifest["limits"]["wall_minutes"]) * 60,
                "claude_cost_usd": 0.0,
                "codex_tokens_used": 0,
                "active_pid": None,
                "controller_pid": os.getpid(),
                "controller_token": token,
                "state_path": str(path),
            }
            save_state(state, "run_started", branch=branch, worktree=str(worktree))
        return run_controller(state, manifest)
    finally:
        if token is not None:
            release_lifecycle_lock(path.parent, token)
            if not path.exists():
                try:
                    path.parent.rmdir()
                except OSError:
                    pass


def status_cmd(args: argparse.Namespace) -> int:
    repo = repo_root(Path.cwd())
    state = load_run(repo, args.run_id)
    keys = ["run_id", "status", "attempt", "active_pid", "branch", "worktree", "base_head",
            "accepted_commit", "deadline_epoch", "claude_cost_usd", "codex_tokens_used",
            "reason", "updated_at"]
    print(json.dumps({key: state.get(key) for key in keys if state.get(key) is not None}, indent=2))
    return 0


def stop(args: argparse.Namespace) -> int:
    repo = repo_root(Path.cwd())
    state = load_run(repo, args.run_id)
    run_dir = Path(state["state_path"]).parent
    create_stop_request(run_dir)
    active_pid = state.get("active_pid")
    if active_pid:
        try:
            os.kill(int(active_pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
    owner = read_lock(run_dir)
    controller_pid = owner.get("pid") if owner else None
    if controller_pid and process_is_live(controller_pid):
        try:
            os.kill(int(controller_pid), signal.SIGTERM)
        except ProcessLookupError:
            controller_pid = None
    deadline = time.monotonic() + 5
    while controller_pid and time.monotonic() < deadline:
        current = load_run(repo, args.run_id)
        if current.get("status") == "interrupted":
            print(f"stopped {args.run_id}; local worktree retained")
            return 0
        if not process_is_live(controller_pid):
            break
        time.sleep(0.05)
    current = load_run(repo, args.run_id)
    if current.get("status") == "interrupted":
        print(f"stopped {args.run_id}; local worktree retained")
    elif not controller_pid or not process_is_live(controller_pid):
        print(f"stop requested for {args.run_id}; controller is gone and resume will reconcile it")
    else:
        print(f"stop requested for {args.run_id}; controller did not persist interruption within five seconds")
    return 0


def resume(args: argparse.Namespace) -> int:
    repo = repo_root(Path.cwd())
    state = load_run(repo, args.run_id)
    if state["status"] == "accepted":
        raise RunError("accepted runs do not resume")
    run_dir = Path(state["state_path"]).parent
    token: str | None = None
    try:
        with coordination_lock(state_root(repo)):
            token = acquire_lifecycle_lock(run_dir, args.run_id)
            state = load_run(repo, args.run_id)
            manifest_path = Path(state["manifest_path"])
            manifest = load_json(manifest_path)
            if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != state["manifest_sha256"]:
                raise RunError("manifest changed since start; create a new run for a changed contract")
            spec_rel, spec_hash = validate_manifest(manifest, repo)
            if str(manifest["run_id"]) != state["run_id"]:
                raise RunError("manifest run_id no longer matches the durable run state")
            if spec_rel.as_posix() != state["spec_path"] or spec_hash != state["spec_sha256"]:
                raise RunError("spec changed since start; create a new run for a changed contract")
            if git(repo, "rev-parse", str(manifest["base_ref"])) != state["base_head"]:
                raise RunError("base_ref changed since start; create a new run for a changed contract")
            worktree = Path(state["worktree"])
            if not worktree.is_dir() or repo_root(worktree) != worktree.resolve():
                raise RunError("run worktree is missing or no longer a Git worktree")
            if git(worktree, "symbolic-ref", "--short", "HEAD") != state["branch"]:
                raise RunError("run worktree is no longer on its recorded branch")
            if not clean(worktree):
                raise RunError("cannot resume a dirty worktree")
            assert_no_live_scope_conflicts(repo, args.run_id, manifest["scope"])
            stop_file = run_dir / "STOP"
            if stop_file.exists():
                persist_interrupted(state)
                stop_file.unlink()
            state["status"] = "resuming"
            state["reason"] = None
            state["scope"] = normalized_scope(manifest["scope"])
            state["controller_pid"] = os.getpid()
            state["controller_token"] = token
            save_state(state, "run_resumed")
        return run_controller(state, manifest)
    finally:
        if token is not None:
            release_lifecycle_lock(run_dir, token)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Finite local Claude/Codex maker-checker runs")
    sub = result.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="create a non-executing run manifest")
    prep.add_argument("--run-id", required=True)
    prep.add_argument("--spec", required=True)
    prep.add_argument("--ticket", required=True)
    prep.add_argument("--maker", choices=["claude", "codex"])
    prep.add_argument("--checker", choices=["claude", "codex"])
    prep.add_argument("--template")
    prep.add_argument("--output")
    prep.add_argument("--force", action="store_true")
    prep.set_defaults(func=prepare)
    begin = sub.add_parser("start", help="explicitly authorize and run a committed manifest")
    begin.add_argument("manifest")
    begin.set_defaults(func=start)
    for name, func in (("status", status_cmd), ("stop", stop), ("resume", resume)):
        item = sub.add_parser(name)
        item.add_argument("run_id")
        item.set_defaults(func=func)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        return int(args.func(args))
    except RunError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
