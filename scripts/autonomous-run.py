#!/usr/bin/env python3
"""Finite, local-only maker/checker orchestration for Agentsmith.

The controller deliberately has no tracker, push, PR, merge, or deployment adapter.  Its
authority ends at a local worktree and local commits; a human decides what leaves the machine.
"""

from __future__ import annotations

import argparse
import contextlib
import errno
import fnmatch
import hashlib
import importlib.util
import json
import math
import os
import posixpath
import re
import secrets
import shlex
import signal
import shlex
import stat
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterable, Iterator

try:
    from native_launcher import (
        build_native_command,
        client_version,
        codex_permissions,
        claude_sandbox_settings,
        toml_inline,
        minimal_environment,
        native_command_prefix,
        native_environment,
        usage_metrics as shared_usage_metrics,
    )
except ModuleNotFoundError:  # source-tree execution from scripts/
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from native_launcher import (
        build_native_command,
        client_version,
        codex_permissions,
        claude_sandbox_settings,
        toml_inline,
        minimal_environment,
        native_command_prefix,
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


HIDDEN_PROBE = "hidden-test-probe"
# Why an attempt was rejected: the `reason` of every `attempt_rejected` event (SF-15). The first five
# reject an attempt the run then retries; `scope`, `protected`, `budget` and `stale` stop the run, and
# their record says `escalated`. A probe can do either. `factory numbers` counts rework by these codes.
REJECTION_REASONS = ("verify", "checker", "hidden-tests", "incomplete", HIDDEN_PROBE,
                     "scope", "protected", "budget", "stale")


class RunError(RuntimeError):
    """A run cannot go on. `reason`, when set, is the REJECTION_REASONS code of the attempt it ends."""

    reason: str | None = None

    def __init__(self, *args: Any, reason: str | None = None) -> None:
        super().__init__(*args)
        if reason is not None:
            self.reason = reason


class BudgetExceeded(RunError):
    """A role crossed a run-wide cap; a finished role's receipt is kept as evidence."""

    reason = "budget"

    def __init__(self, message: str, receipt: dict[str, Any] | None) -> None:
        super().__init__(message)
        self.receipt = receipt


class InfrastructureFailure(RunError):
    """A role client failed for a known host, network or client reason before any receipt."""

    def __init__(self, message: str, signature: str) -> None:
        super().__init__(message)
        self.signature = signature


class HiddenTestProbe(RunError):
    """A role's output, receipt or changes showed the tripwire planted in the hidden clone: it tried
    to read the held-out tests. Never an infrastructure failure, so the breaker never relaunches it.
    `content` means the canary token itself appeared, so the role saw held-out content; a hit on
    the file's name alone (a denied read's error message) means the sandbox held."""

    def __init__(self, role: str, surfaces: list[str], content: bool) -> None:
        seen = "saw held-out content" if content else "tried to read the held-out acceptance tests"
        super().__init__(f"{HIDDEN_PROBE}: the {role} {seen} (shown in its {', '.join(surfaces)})",
                         reason=HIDDEN_PROBE)
        self.role = role
        self.surfaces = surfaces
        self.content = content


class HiddenTestsRejected(Exception):
    """Internal: opt-in hidden acceptance tests rejected the candidate before any checker ran."""


class RunInterrupted(RuntimeError):
    """Operator cancellation must bypass handlers for invalid run or peer state."""


# Set by the controller's stop handler, which never raises: an exception from a signal handler
# can land anywhere, and one landed inside `subprocess` while it held its private wait lock, so
# the controller waited for hours. The controller raises RunInterrupted at safe points instead.
_stop_signal_received = False


def raise_if_stopped(run_dir: Path) -> None:
    if _stop_signal_received or (run_dir / "STOP").exists():
        raise RunInterrupted("stopped by operator")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(cmd: list[str] | str, cwd: Path, *, timeout: int | None = None,
        env: dict[str, str] | None = None, shell: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, encoding="utf-8", errors="replace",
                          capture_output=True, timeout=timeout,
                          env=env, shell=shell, check=False)


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = run(["git", *args], repo)
    if check and result.returncode:
        raise RunError(result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def git_paths(repo: Path, command: str, *args: str) -> list[str]:
    """Names exactly as Git stores them. Line output quotes and escapes unusual names, and
    trimming drops leading whitespace; scope and protection rules need the real name."""
    result = run(["git", command, "-z", *args], repo)
    if result.returncode:
        raise RunError(result.stderr.strip() or f"git {command} failed")
    return [path for path in result.stdout.split("\0") if path]


def shown_paths(paths: list[str]) -> str:
    """A runtime chooses these names and the operator's terminal prints them."""
    return ", ".join("".join(char if char.isprintable() else char.encode("unicode_escape").decode("ascii")
                             for char in path) for path in paths)


PAUSE_MARKER = ".harness/AUTONOMY_PAUSED"


def factory_root(repo: Path) -> Path:
    """Operator-side records outside any run: kill-switch refusals, the post-merge defect log and
    logged human minutes. Roles cannot write it, and Git metadata checks ignore it."""
    return state_root(repo).parent / "agentsmith-factory"


def record_factory_event(repo: Path, kind: str, **fields: Any) -> None:
    """Best effort: a record that cannot be written must never change the decision it records."""
    try:
        root = factory_root(repo)
        root.mkdir(exist_ok=True)
        with (root / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": now(), "event": kind, **fields}, sort_keys=True) + "\n")
    except (OSError, RunError):
        pass


def assert_autonomy_not_paused(repo: Path, *, action: str = "work", run_id: str | None = None) -> None:
    """The operator's repository-wide kill switch: while the marker exists in this checkout or
    in the main checkout, no run is prepared, started or resumed. A live run keeps running;
    `stop <id>` ends it. Any entry in `.harness/` named AUTONOMY_PAUSED ignoring case counts,
    so the result does not depend on whether the filesystem ignores case."""
    roots = [repo]
    common = resolved_git_path(repo, "--git-common-dir")
    if common.name == ".git" and common.parent != repo:
        roots.append(common.parent)
    wanted = Path(PAUSE_MARKER).name.casefold()
    for root in roots:
        folder = root / Path(PAUSE_MARKER).parent
        try:
            names = os.listdir(folder) if folder.is_dir() else []
        except OSError as exc:
            raise RunError(f"cannot tell whether autonomy is paused: {folder}: {exc}") from exc
        for name in names:
            if name.casefold() == wanted:
                # The evidence that the kill switch works, for `agentsmith factory readiness`.
                try:
                    marker_mtime = (folder / name).stat().st_mtime_ns
                except OSError:
                    marker_mtime = None
                record_factory_event(repo, "autonomy_pause_refused", action=action, run_id=run_id,
                                     marker=str((folder / name).resolve()), marker_mtime_ns=marker_mtime)
                raise RunError(f"autonomy is paused by {folder / name}; remove it to allow new work "
                               "(live runs are not stopped; use stop <id>)")


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
    for attempt in range(500):
        try:
            return path.read_text(encoding="utf-8")
        except PermissionError as exc:
            transient_windows_error = os.name == "nt" and (
                getattr(exc, "winerror", None) in {5, 32} or exc.errno == errno.EACCES
            )
            if not transient_windows_error or attempt == 499:
                raise
            time.sleep(0.01)
    raise AssertionError("unreachable")


def read_output(path: Path) -> str:
    """Captured role and verifier output: UTF-8 whatever the locale, never a decode crash."""
    return path.read_text(encoding="utf-8", errors="replace")


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
    for attempt in range(500):
        try:
            os.replace(source, destination)
            return
        except PermissionError as exc:
            transient_windows_error = os.name == "nt" and (
                getattr(exc, "winerror", None) in {5, 32} or exc.errno == errno.EACCES
            )
            if not transient_windows_error or attempt == 499:
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


def unlink_coordination_lock(path: Path) -> None:
    """Release a lock after brief Windows sharing denials from competing readers."""
    for attempt in range(500):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError as exc:
            transient = os.name == "nt" and (
                getattr(exc, "winerror", None) in {5, 32} or exc.errno == errno.EACCES
            )
            if not transient or attempt == 499:
                raise RunError(f"cannot remove repository coordination lock {path}: {exc}") from exc
            time.sleep(0.01)


def read_coordination_lock(root: Path) -> dict[str, Any] | None:
    path = coordination_lock_path(root)
    deadline = time.monotonic() + 0.5
    while True:
        try:
            value = json.loads(read_text(path))
            break
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as exc:
            # O_EXCL publishes the lock name before its owner record is flushed.
            if time.monotonic() >= deadline:
                raise RunError(f"cannot verify repository coordination lock {path}: {exc}") from exc
            time.sleep(0.01)
        except OSError as exc:
            raise RunError(f"cannot verify repository coordination lock {path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("pid"), int):
        raise RunError(f"cannot verify repository coordination lock {path}: malformed owner metadata")
    return value


@contextlib.contextmanager
def coordination_lock(root: Path, *, interruptible: bool = True):
    """A stop ends a wait to acquire, never a release path: raising there would leave a lease
    behind and could turn a recorded escalation into an interruption."""
    root.mkdir(parents=True, exist_ok=True)
    path = coordination_lock_path(root)
    token = uuid.uuid4().hex
    record = {"pid": os.getpid(), "run_id": "coordination", "started_at": now(), "token": token}
    encoded = (json.dumps(record, sort_keys=True) + "\n").encode()
    # Native Windows release evidence observed a live owner outlast ten seconds
    # during parallel graph start. Keep a bound while allowing that transition
    # to finish before another controller reports a lock failure.
    deadline = time.monotonic() + 60
    while True:
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except PermissionError as exc:
            transient = os.name == "nt" and (
                getattr(exc, "winerror", None) in {5, 32} or exc.errno == errno.EACCES
            )
            if not transient or time.monotonic() >= deadline:
                raise RunError(f"cannot acquire repository coordination lock {path}: {exc}") from exc
            if interruptible and _stop_signal_received:
                raise RunInterrupted("stopped by operator") from exc
            time.sleep(0.02)
            continue
        except FileExistsError:
            existing = read_coordination_lock(root)
            if existing is None:
                continue
            if process_is_live(existing["pid"]):
                if time.monotonic() >= deadline:
                    raise RunError(
                        f"repository coordination is still held by live process {existing['pid']}"
                    )
                if interruptible and _stop_signal_received:
                    raise RunInterrupted("stopped by operator")
                time.sleep(0.02)
                continue
            try:
                before = path.read_bytes()
                if path.read_bytes() == before:
                    unlink_coordination_lock(path)
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
            unlink_coordination_lock(path)


@contextlib.contextmanager
def git_phase(repo: Path, phase: str, *, timeout_seconds: float = 60, budget: bool = False):
    """Coordinate shared Git metadata without serializing independent makers.

    A checker must see a quiescent object store for its strict before/after check.
    Graph-owned Git merges use the exclusive writer phase. These leases are only
    coordination, never an exemption from the metadata tampering checks.
    `budget` says the timeout is what is left of the run's wall clock: a wait that spends it all
    is a budget stop.
    """
    if phase not in {"maker", "checker", "writer"}:
        raise RunError(f"unsupported git phase: {phase}")
    root = state_root(repo)
    phase_dir = root / "git-phases"
    token = uuid.uuid4().hex
    lease = phase_dir / f"{token}.json"
    deadline = time.monotonic() + max(0, timeout_seconds)
    while True:
        with coordination_lock(root):
            phase_dir.mkdir(exist_ok=True)
            active: list[tuple[Path, dict[str, Any]]] = []
            for path in sorted(phase_dir.glob("*.json")):
                try:
                    record = load_json(path)
                except RunError as exc:
                    raise RunError(f"cannot verify git phase lease {path}: {exc}") from exc
                if (not isinstance(record.get("pid"), int)
                        or not isinstance(record.get("token"), str)
                        or record["token"] != path.stem
                        or record.get("phase") not in {"maker", "checker", "writer"}):
                    raise RunError(f"cannot verify git phase lease {path}: malformed owner metadata")
                if not process_is_live(record["pid"]):
                    path.unlink()
                    continue
                active.append((path, record))
            conflict = next((record for _, record in active
                             if phase != "maker" or record["phase"] != "maker"), None)
            if conflict is None:
                write_json(lease, {"pid": os.getpid(), "token": token,
                                   "phase": phase, "started_at": now()})
                break
        if time.monotonic() >= deadline:
            raise RunError(f"git phase {phase} is still held by live {conflict['phase']} process "
                           f"{conflict['pid']}" + ("; the wall-clock budget ran out while waiting" if budget else ""),
                           reason="budget" if budget else None)
        if _stop_signal_received:
            raise RunInterrupted("stopped by operator")
        time.sleep(0.02)
    try:
        yield
    finally:
        with coordination_lock(root, interruptible=False):
            if lease.exists():
                record = load_json(lease)
                if record.get("token") == token and record.get("pid") == os.getpid():
                    lease.unlink()


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
        if kind == "sequenced":
            raise RunError(f"run {run_id} conflicts with live run {other_id}: both change {value} files")
        raise RunError(
            f"run {run_id} conflicts with live run {other_id}: shared resource '{value}'"
        )


def event(state: dict[str, Any], kind: str, **fields: Any) -> None:
    path = Path(state["state_path"]).parent / "events.jsonl"
    record = {"at": now(), "event": kind, **fields}
    with path.open("a", encoding="utf-8") as handle:
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
    # Flat `key: value` pairs. An indented line continues the previous key, as in YAML
    # (`schema:` then `  2`, or a folded `route: >-`), and a repeated key is refused, so a
    # gate field cannot be hidden by its YAML shape.
    values: dict[str, str] = {}
    key = None
    for raw in text[4:end].splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[:1] in (" ", "\t") and key is not None:
            values[key] = " ".join(part for part in (values[key], raw.strip()) if part)
            continue
        if ":" not in raw:
            key = None
            continue
        key, value = (part.strip() for part in raw.split(":", 1))
        if key in values:
            raise RunError(f"spec front matter repeats the key {key!r}")
        values[key] = "" if value in {">", ">-", ">+", "|", "|-", "|+"} else value
    return {name: value.strip().strip('"\'') for name, value in values.items()}


ROUTE = re.compile(r"(direct|grill|wayfinder)\b[\s\-—–:;,(]*(.*)")
LIST_ITEM = re.compile(r"\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?(.*\S)")
# A section a schema-2 spec must hold with at least one real list item, and what it stands for.
REQUIRED_SPEC_SECTIONS = (("Acceptance and evidence", "acceptance criteria"),
                          ("Edge cases", "edge case"),
                          ("Non-goals", "out-of-scope item"))
ASSUMPTION = re.compile(r"`([^`\s]+?)(?:::([^`\s]+))?`")


def spec_sections(text: str) -> dict[str, list[str]]:
    """The list items under each `## ` heading of a spec body, outside fenced code blocks.

    An item that is only a template placeholder such as `<a boundary>` does not count."""
    end = text.find("\n---\n", 4) if text.startswith("---\n") else -1
    sections: dict[str, list[str]] = {}
    current = None
    fenced = False
    for line in text[end + 5:].splitlines() if end >= 0 else text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            continue
        if line.startswith("#"):
            heading = re.fullmatch(r"##\s+(.*?)\s*#*\s*", line)
            current = heading.group(1) if heading else None
            if current is not None:
                sections.setdefault(current, [])
            continue
        item = LIST_ITEM.fullmatch(line)
        if current is not None and item and not re.fullmatch(r"<[^>]*>\.?", item.group(1)):
            sections[current].append(item.group(1))
    return sections


def assumption_problems(repo: Path, items: list[str], commit: str | None) -> list[str]:
    """Check each `path` or `path::symbol` that opens an Assumptions item against Git.

    With `commit`, the path must exist in that commit (file or folder) and a symbol must occur as
    a whole word in that file there; without it, the same holds for what Git tracks (the index).
    Items that do not open with a backticked reference are prose and are not checked."""
    problems = []
    where = f"at {commit}" if commit else "in what Git tracks"
    for item in items:
        reference = ASSUMPTION.match(item)
        if reference is None:
            continue
        path, symbol = reference.group(1).rstrip("/"), reference.group(2)
        shown = reference.group(0)
        relative = Path(path)
        if (not path or relative.is_absolute() or "\\" in path or ".." in relative.parts
                or path.startswith("-")):
            problems.append(f"assumption {shown} must be a repository-relative path")
            continue
        if commit:
            entry = run(["git", "ls-tree", commit, "--", path], repo).stdout.split()
            kind = entry[1] if len(entry) > 1 else None
        else:
            tracked = run(["git", "ls-files", "-z", "--", path], repo).stdout.split("\0")
            kind = "blob" if path in tracked else "tree" if any(tracked) else None
        if symbol is None:
            if kind is None:
                problems.append(f"stale assumption: {shown} does not exist {where}")
            continue
        if kind is None:
            problems.append(f"stale assumption: {shown} — {path} does not exist {where}")
        elif kind != "blob":
            problems.append(f"stale assumption: {shown} — {path} is not a file {where}")
        elif run(["git", "grep", "-q", "-w", "-F", "-e", symbol,
                  *([commit] if commit else ["--cached"]), "--", path], repo).returncode:
            problems.append(f"stale assumption: {shown} — {symbol!r} does not occur in {path} {where}")
    return problems


def spec_pipeline_problems(repo: Path, meta: dict[str, str], commit: str | None = None, *,
                           text: str) -> list[str]:
    """What a schema-2 spec lacks of the development pipeline's artifacts.

    A spec with no `schema` key at all predates the pipeline fields and is not checked, so specs
    accepted before they existed keep working; the template declares `schema: 2`. Any schema
    value other than 2, blank included, is refused rather than treated as legacy.

    A run's worktree holds only what Git holds. With `commit`, each cited file must be a regular
    file in that commit; without it, the file must exist and be tracked.

    The body must hold acceptance criteria, an edge case and an out-of-scope item, each as a list
    item under its heading, and each `path` or `path::symbol` assumption must hold at `commit`
    (in what Git tracks without one), so a run never starts on a spec it cannot test or that is
    stale."""
    if "schema" not in meta:
        return []
    schema = meta["schema"]
    if schema != "2":
        return [f"unsupported schema {schema!r}; this controller reads schema 2"]
    problems = []
    for field in ("research", "reviewer_receipt"):
        value = meta.get(field, "")
        if not value:
            problems.append(f"{field} is missing")
            continue
        relative = Path(value)
        if relative.is_absolute() or "\\" in value or ".." in relative.parts:
            problems.append(f"{field} must be a repository-relative path")
        elif commit is not None:
            entry = run(["git", "ls-tree", commit, "--", relative.as_posix()], repo).stdout.split()
            if not entry or not entry[0].startswith("100") or entry[1] != "blob":
                problems.append(f"{field} names {value}, which is not committed at {commit}; "
                                "commit it so the run's worktree has it")
        elif not (repo / relative).is_file() or not (repo / relative).resolve().is_relative_to(repo.resolve()):
            problems.append(f"{field} points at {value}, which does not exist")
        elif run(["git", "ls-files", "--error-unmatch", "--", relative.as_posix()], repo).returncode:
            problems.append(f"{field} names {value}, which Git does not track; "
                            "add and commit it so a run's worktree has it")
    route = ROUTE.fullmatch(meta.get("route", ""))
    if route is None:
        problems.append("route must start with direct, grill or wayfinder")
    elif not route.group(2).strip():
        problems.append("route needs a one-line reason after direct, grill or wayfinder")
    sections = spec_sections(text)
    for heading, meaning in REQUIRED_SPEC_SECTIONS:
        if not sections.get(heading):
            problems.append(f"no {meaning}: add a '## {heading}' section with at least one list item")
    problems += assumption_problems(repo, sections.get("Assumptions", []), commit)
    return problems


def check_specs(args: argparse.Namespace) -> int:
    """The pipeline guard: 0 when every checked spec is complete, 1 when one is not."""
    repo = repo_root(Path.cwd())
    named = [Path(path) for path in args.paths]
    targets = named or sorted(path for path in (repo / "docs/specs").rglob("*.md") if path.is_file())
    failed = False
    checked = 0
    for path in targets:
        path = path if path.is_absolute() else Path.cwd() / path
        shown = path.relative_to(repo).as_posix() if path.resolve().is_relative_to(repo) else str(path)
        try:
            text = read_text(path)
            if not named and not text.startswith("---\n"):
                continue  # not a spec, for example the folder's README
            meta = frontmatter(text)
        except (OSError, UnicodeError, RunError) as exc:
            print(f"FAIL {shown}: {exc}")
            failed = True
            continue
        status = meta.get("status", "")
        if not named and status != "accepted":
            continue
        checked += 1
        problems = spec_pipeline_problems(repo, meta, text=text)
        if problems:
            print(f"FAIL {shown}: " + "; ".join(problems))
            failed = True
        elif "schema" not in meta:
            print(f"ok   {shown}: legacy spec without schema: 2; pipeline fields not checked")
        else:
            waiting = "" if status == "accepted" else " (waiting for operator acceptance)"
            print(f"ok   {shown}: {status}{waiting}")
    if not checked and not failed:
        print("no accepted spec under docs/specs to check")
    return 1 if failed else 0


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


# Coordination-sensitive files (SF-16): two runs whose allowed paths both reach one of these classes
# run one after the other, even when they share no path. Patterns are fnmatch globs (`*` also
# matches `/`). An allowed_paths pattern reaches a class when one path could match both, ignoring
# case (`globs_intersect`): `a/[m]igrations/*` is a migration path; a broad `db/**` is not (it
# collides by path with a narrower db pattern instead).
# A manifest adds classes or patterns in `scope.sequenced`; it cannot remove these.
SEQUENCED_CLASSES: dict[str, tuple[str, ...]] = {
    "spec": ("docs/specs/*",),
    "migration": ("migrations/*", "*/migrations/*", "migrate/*", "*/migrate/*"),
    "schema": ("schema.*", "*/schema.*", "schemas/*", "*/schemas/*", "*.schema.json"),
    "contract": ("openapi.*", "*/openapi.*", "swagger.*", "*/swagger.*", "*.proto", "*.graphql",
                 "contracts/*", "*/contracts/*"),
}
SEQUENCED_CLASS_NAME = re.compile(r"[a-z][a-z0-9-]{0,31}\Z")


def scope_sequenced(scope: dict[str, Any]) -> dict[str, list[str]]:
    declared = scope.get("sequenced", {})
    if not isinstance(declared, dict):
        raise RunError("scope.sequenced must be a JSON object of class names to glob arrays")
    if any(not isinstance(name, str) or not SEQUENCED_CLASS_NAME.fullmatch(name) for name in declared):
        raise RunError("scope.sequenced class names must be lowercase letters, digits and '-'")
    return {name: scope_paths({"sequenced": patterns}, "sequenced") for name, patterns in sorted(declared.items())}


OPAQUE_SEGMENT = "\0"  # a whole-wildcard segment (`*`, `**`): one name that spells no class


def glob_tokens(pattern: str, *, scope_pattern: bool) -> list[tuple[Any, ...]]:
    """fnmatch tokens, lowercased: ('char', c), ('any',) for `?`, ('star', spans_slash), and
    ('set', negated, chars, ranges). In a scope pattern a `*` inside a segment stays in that
    segment, and a segment that is only wildcards becomes one opaque name."""
    if scope_pattern:
        pattern = "/".join(OPAQUE_SEGMENT if segment and set(segment) <= {"*"} else segment
                           for segment in pattern.split("/"))
    pattern = pattern.lower()
    tokens: list[tuple[Any, ...]] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        index += 1
        if char == "*":
            tokens.append(("star", not scope_pattern))
        elif char == "?":
            tokens.append(("any",))
        elif char == "[":
            end = index + 1 if index < len(pattern) and pattern[index] in "!]" else index
            if end < len(pattern) and pattern[end - 1] == "!" and pattern[end] == "]":
                end += 1
            end = pattern.find("]", end)
            if end < 0:
                tokens.append(("char", "["))  # unclosed: fnmatch reads a literal bracket
                continue
            body, index = pattern[index:end], end + 1
            negated = body.startswith("!")
            body = body[1:] if negated else body
            chars, ranges, position = set(), [], 0
            while position < len(body):
                if position + 2 < len(body) and body[position + 1] == "-":
                    ranges.append((body[position], body[position + 2]))
                    position += 3
                else:
                    chars.add(body[position])
                    position += 1
            tokens.append(("set", negated, frozenset(chars), tuple(ranges)))
        else:
            tokens.append(("char", char))
    return tokens


def _token_admits(token: tuple[Any, ...], char: str) -> bool:
    kind = token[0]
    if kind in {"any", "star"}:
        return kind == "any" or token[1] or char != "/"
    if kind == "char":
        return token[1] == char
    inside = char in token[2] or any(low <= char <= high for low, high in token[3])
    return (not inside if token[1] else inside) and char != "/"


def _tokens_share_a_char(left: tuple[Any, ...], right: tuple[Any, ...]) -> bool:
    candidates = {"/", OPAQUE_SEGMENT, "a", "0", ".", "_", "-"}
    for token in (left, right):
        if token[0] == "char":
            candidates.add(token[1])
        elif token[0] == "set":
            candidates |= set(token[2]) | {end for pair in token[3] for end in pair}
            candidates |= {chr(ord(low) + 1) for low, high in token[3] if low < high}
    return any(_token_admits(left, char) and _token_admits(right, char) for char in candidates)


def globs_intersect(scope_pattern: str, class_glob: str) -> bool:
    """Whether one path could match both, ignoring case: a scope glob that could name a class
    folder or file counts as that class (fail closed), as `a/[m]igrations/*` or `a/Migrations/*`."""
    left, right = glob_tokens(scope_pattern, scope_pattern=True), glob_tokens(class_glob, scope_pattern=False)
    seen: set[tuple[int, int]] = set()
    pending = [(0, 0)]
    while pending:
        i, j = pending.pop()
        if (i, j) in seen:
            continue
        seen.add((i, j))
        if i == len(left) and j == len(right):
            return True
        a = left[i] if i < len(left) else None
        b = right[j] if j < len(right) else None
        if a is not None and a[0] == "star":
            pending.append((i + 1, j))  # the star matches nothing
            if b is not None and (b[0] == "star" or _tokens_share_a_char(a, b)):
                pending.append((i, j + 1))  # the star absorbs what b matches
        if b is not None and b[0] == "star":
            pending.append((i, j + 1))
            if a is not None and (a[0] == "star" or _tokens_share_a_char(a, b)):
                pending.append((i + 1, j))
        if a is not None and b is not None and a[0] != "star" and b[0] != "star" and _tokens_share_a_char(a, b):
            pending.append((i + 1, j + 1))
    return False


def sequenced_classes(scope: dict[str, Any], extra: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    """The coordination classes this scope's allowed paths reach, each with the patterns that reach it."""
    classes = {name: list(patterns) for name, patterns in SEQUENCED_CLASSES.items()}
    for declared in (scope.get("sequenced", {}), extra or {}):
        for name, patterns in declared.items():
            classes[name] = [*classes.get(name, []), *patterns]
    found: dict[str, list[str]] = {}
    for pattern in scope["allowed_paths"]:
        for name, globs in classes.items():
            if any(globs_intersect(pattern, glob) for glob in globs):
                found.setdefault(name, []).append(pattern)
    return found


def normalized_scope(scope: Any) -> dict[str, Any]:
    if not isinstance(scope, dict):
        raise RunError("scope must be a JSON object")
    allowed = scope_paths(scope, "allowed_paths")
    if not allowed:
        raise RunError("scope.allowed_paths must reserve at least one path")
    normalized: dict[str, Any] = {
        "allowed_paths": allowed,
        "denied_paths": scope_paths(scope, "denied_paths"),
        "resources": scope_resources(scope),
    }
    if "sequenced" in scope:
        normalized["sequenced"] = scope_sequenced(scope)
    return normalized


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
    # Each side is classified with both sides' declared classes, so one declaration serves the pair.
    declared = {**left.get("sequenced", {})}
    for name, patterns in right.get("sequenced", {}).items():
        declared[name] = [*declared.get(name, []), *patterns]
    shared_classes = sorted(set(sequenced_classes(left, declared)) & set(sequenced_classes(right, declared)))
    if shared_classes:
        return "sequenced", shared_classes[0]
    return None


# A template or hand-edited draft marks a value the operator still has to choose this way.
PLACEHOLDER_SETTING = re.compile(
    r"\A\s*\Z|\A\s*<|replace[-_ ]?with|to[-_ ]?fill|\A\s*(todo|tbd|changeme|placeholder|fixme)\s*\Z",
    re.IGNORECASE)


def unset_role_settings(manifest: dict[str, Any]) -> list[str]:
    roles = manifest.get("roles") if isinstance(manifest.get("roles"), dict) else {}
    unset = []
    for role in ("maker", "checker"):
        config = roles.get(role) if isinstance(roles.get(role), dict) else {}
        for key in ("model", "effort"):
            value = config.get(key)
            if not isinstance(value, str) or PLACEHOLDER_SETTING.search(value):
                unset.append(f"roles.{role}.{key}")
    return unset


POLICY_FILE = ".harness/risk-policy.json"  # risk_map.POLICY_PATH
# Risk tiers, lowest first, as in risk_map.TIERS. A manifest may declare one; it only raises.
RISK_TIERS = ("A", "B", "C", "human")


def risk_record(repo: Path, base: str, head: str, declared: str | None) -> dict[str, Any]:
    """Classify base..head with the risk policy committed at the base, so a candidate cannot
    relax the rules that judge it. Report-only: it decides nothing, and a classification that
    cannot run is recorded as `human` with its error instead of stopping the run."""
    record: dict[str, Any] = {"base": base, "head": head, "declared_tier": declared}
    try:
        import risk_map
        report = risk_map.classify_range(repo, base, head)
        record.update(computed_tier=report["tier"], lenses=report["lenses"], policy=report["policy"],
                      tier=risk_map.raise_tier(report["tier"], declared or "A"))
    except Exception as exc:  # ImportError, PolicyError, RiskError: recorded, never fatal
        record.update(computed_tier=None, lenses=[], policy=None, tier="human",
                      error=f"{type(exc).__name__}: {exc}"[:300])
    return record


MAX_REWORK_NOTE_BYTES = 16 * 1024


def rework_note(repo: Path, manifest: dict[str, Any]) -> str | None:
    """The operator's rework note, checked against the hash pinned at prepare; None without one."""
    rework = manifest.get("rework")
    if rework is None:
        return None
    if not isinstance(rework, dict) or set(rework) != {"of", "note_path", "note_sha256"}:
        raise RunError("rework needs exactly of, note_path and note_sha256; prepare it with --rework-of")
    path = (repo / str(rework["note_path"])).resolve()
    if not path.is_relative_to(repo.resolve()) or not path.is_file():
        raise RunError(f"rework note {rework['note_path']} is missing; prepare a new run")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != rework["note_sha256"]:
        raise RunError("rework note changed since prepare; prepare a new run with the new note")
    return note_text_problem(data, str(rework["note_path"])).strip()


OPERATOR_FEEDBACK_FILE = "operator-feedback.md"


def keep_operator_feedback(state: dict[str, Any], manifest: dict[str, Any]) -> None:
    """Keep a rework's note as its own file in the new run's folder (SF-16). The note in the
    repository may change or go once the run started; the run's own copy is what its maker was
    given. The folder is controller state that no role may write. A rework is a new run, so its
    attempts and spend start from zero: the held run's budget is never carried over."""
    rework = manifest.get("rework")
    if not isinstance(rework, dict):
        return
    repo = Path(state["repo"])
    data = (repo / str(rework["note_path"])).read_bytes()
    if hashlib.sha256(data).hexdigest() != rework["note_sha256"]:
        raise RunError("rework note changed since prepare; prepare a new run with the new note")
    kept = Path(state["state_path"]).parent / OPERATOR_FEEDBACK_FILE
    kept.write_bytes(data)
    state["operator_feedback"] = {"of": rework["of"], "file": OPERATOR_FEEDBACK_FILE,
                                  "note_path": rework["note_path"], "sha256": rework["note_sha256"]}
    save_state(state, "operator_feedback_kept", of=rework["of"], sha256=rework["note_sha256"])


def note_text_problem(data: bytes, shown: str) -> str:
    """The note as text. It reaches the maker as a process argument, which cannot hold NUL."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = "\0"
    if "\0" in text:
        raise RunError(f"rework note {shown} must be UTF-8 text without NUL characters")
    return text


HIDDEN_PASS_MARKER = "AGENTSMITH-HIDDEN-PASS"
HIDDEN_HINT = ("hidden acceptance tests failed; re-read the spec's acceptance criteria and check the cases "
               "the visible tests do not cover")


def hidden_tests_problem(manifest: dict[str, Any], repo: Path) -> str | None:
    """Why a manifest's opt-in hidden acceptance tests cannot be used, or None (also when absent)."""
    hidden = manifest.get("hidden_tests")
    if hidden is None:
        return None
    if not isinstance(hidden, dict) or set(hidden) != {"repo", "commit", "command", "tiers"}:
        return "hidden_tests needs exactly repo, commit, command and tiers"
    clone = Path(str(hidden["repo"])).expanduser()
    if not clone.is_absolute() or not clone.is_dir():
        return "hidden_tests.repo must be an absolute path to a local clone"
    clone = clone.resolve()
    run_worktree = Path(manifest.get("worktree_path") or repo.parent / f"{repo.name}-{manifest.get('run_id')}").resolve()
    for place in (repo.resolve(), run_worktree):
        if clone == place or clone.is_relative_to(place) or place.is_relative_to(clone):
            return f"hidden_tests.repo must be outside the repository and the run worktree ({place})"
    # The hidden objects must live only inside the clone, which roles cannot read: a worktree of
    # the candidate repository, a clone that borrows objects (alternates) or a Git folder kept
    # elsewhere would let a maker read the hidden tests with `git show`.
    clone_git = run(["git", "-C", str(clone), "rev-parse", "--path-format=absolute", "--absolute-git-dir",
                     "--git-common-dir"], repo).stdout.split("\n")
    candidate_common = resolved_git_path(repo, "--git-common-dir")
    clone_dirs = [Path(line).resolve() for line in clone_git[:2] if line]
    alternates = [clone_dirs[-1] / "objects/info/alternates"] if clone_dirs else []
    borrowed = any(path.is_file() and path.read_text(encoding="utf-8", errors="replace").strip() for path in alternates)
    lent = candidate_common / "objects/info/alternates"
    lends = lent.is_file() and any(Path(line.strip()).resolve().is_relative_to(clone)
                                   for line in lent.read_text(encoding="utf-8", errors="replace").splitlines()
                                   if line.strip())
    if (len(clone_dirs) != 2 or not all(path.is_relative_to(clone) for path in clone_dirs)
            or candidate_common in clone_dirs or borrowed or lends):
        return ("hidden_tests.repo must be a standalone repository: its Git folder inside it, not a worktree "
                "of this repository, and no objects borrowed from or lent to another repository")
    commit = str(hidden["commit"])
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit) or run(
            ["git", "-C", str(clone), "cat-file", "-t", commit], repo).stdout.strip() != "commit":
        return "hidden_tests.commit must be a full commit SHA that exists in hidden_tests.repo"
    # Only plain files and folders: a link or submodule could reach outside the suite, and no error
    # may name a hidden entry, because errors are saved where roles can read them.
    listing = run(["git", "-C", str(clone), "ls-tree", "-r", "-t", "-z", commit], repo).stdout.split("\0")
    if any(entry and entry.split(" ", 1)[0] not in {"100644", "100755", "040000"} for entry in listing):
        return "hidden_tests.commit holds an entry that is not a regular file or folder; keep the suite to plain files"
    command = hidden["command"]
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        return "hidden_tests.command must be a non-empty list of arguments; {hidden} names the tests folder"
    if not any("{token}" in item for item in command):
        return (f"hidden_tests.command must pass {{token}} to the hidden harness, which prints "
                f"'{HIDDEN_PASS_MARKER} <token>' on a line of its own when every hidden test ran")
    tiers = hidden["tiers"]
    if not isinstance(tiers, list) or not tiers or any(tier not in RISK_TIERS for tier in tiers):
        return f"hidden_tests.tiers must list tiers from {', '.join(RISK_TIERS)}"
    return None


def hidden_read_paths(manifest: dict[str, Any]) -> list[Path]:
    hidden = manifest.get("hidden_tests")
    return [Path(str(hidden["repo"])).expanduser().resolve()] if isinstance(hidden, dict) else []


def probe_hint(role: str) -> str:
    """Rework feedback after a probe: it names the behaviour, never a hidden file or the canary."""
    return (f"the {role} tried to read the held-out acceptance tests, which no role may read, so the attempt "
            "was not used; work from the spec and the visible tests only")


@contextlib.contextmanager
def hidden_tripwire(manifest: dict[str, Any]):
    """A file with a fresh random name and canary token in the hidden clone while one role runs.
    The role sandbox denies reading the clone; the canary shows a read that got through anyway.
    Content, not access times: atime is off or relaxed on most macOS and Linux mounts. The suite
    comes from `git archive` of the hidden commit, so this untracked file never joins it."""
    clones = hidden_read_paths(manifest)
    if not clones:
        yield None
        return
    tripwire = {"name": f"case-{secrets.token_hex(8)}.txt", "token": secrets.token_hex(16)}
    path = clones[0] / tripwire["name"]
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(f"held-out acceptance case {tripwire['token']}\n")
    except OSError as exc:
        raise RunError(f"cannot place the hidden-test tripwire in hidden_tests.repo ({exc.strerror}); "
                       "the controller needs write access to the clone") from None
    try:
        yield tripwire
    finally:
        path.unlink(missing_ok=True)


def file_holds(path: Path, needles: tuple[str, ...]) -> set[str]:
    """Which of `needles` a file holds anywhere, read in overlapping chunks so a large file is
    searched to its end without being loaded whole."""
    wanted = [needle.encode("utf-8") for needle in needles]
    overlap = max(map(len, wanted)) - 1
    found, tail = set(), b""
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1 << 20):
                window = tail + chunk
                found.update(needle for needle, raw in zip(needles, wanted) if raw in window)
                tail = window[-overlap:] if overlap else b""
    except OSError:
        pass
    return found


def probe_surfaces(tripwire: dict[str, str], role_output: str, receipt_path: Path, worktree: Path,
                   before_head: str) -> tuple[list[str], bool]:
    """Where a role showed the canary or the tripwire's name: its output, its receipt, the changes
    it left in its worktree (committed, uncommitted or untracked), every commit it made with its
    message and patch (so a commit it reverted later still counts), and the files Git ignores in
    its worktree; and whether the canary token itself was among them."""
    needles = (tripwire["token"], tripwire["name"])
    untracked = git(worktree, "ls-files", "--others", "--exclude-standard", "-z", check=False).split("\0")
    changes = [git(worktree, "diff", "--no-ext-diff", "--text", before_head, check=False)]
    for name in filter(None, untracked):
        with contextlib.suppress(OSError):
            changes.append(name + "\n" + (worktree / name).read_bytes()[:1 << 20].decode("utf-8", "replace"))
    surfaces = {
        "output": role_output,
        "receipt": receipt_path.read_text(encoding="utf-8", errors="replace") if receipt_path.is_file() else "",
        "worktree changes": "\n".join(changes),
        "commit history": git(worktree, "log", "-p", "--no-ext-diff", "--text", "--format=%B",
                              f"{before_head}..HEAD", check=False),
    }
    hits = {label for label, text in surfaces.items() if any(needle in text for needle in needles)}
    token_seen = any(tripwire["token"] in text for text in surfaces.values())
    # Ignored files are searched on disk to their end, by name and content: Git hides them from
    # every other surface, which makes them the obvious place to keep what a role read.
    ignored = git(worktree, "ls-files", "--others", "--ignored", "--exclude-standard", "-z", check=False).split("\0")
    for name in filter(None, ignored):
        held = file_holds(worktree / name, needles) | {needle for needle in needles if needle in name}
        if held:
            hits.add("ignored files")
            token_seen = token_seen or tripwire["token"] in held
    order = ["output", "receipt", "worktree changes", "commit history", "ignored files"]
    return [label for label in order if label in hits], token_seen


def probed_attempt(state: dict[str, Any], probe: HiddenTestProbe, commit: str, paths: list[str]) -> dict[str, Any]:
    """A probe fails the attempt like a rejection, with feedback that names only the behaviour."""
    receipt = {"status": "rejected", "summary": f"the {probe.role} tried to read the held-out acceptance tests",
               "commit": commit, "changed_paths": paths, "evidence": [], "unresolved": [probe_hint(probe.role)],
               "next_state": "rejected"}
    state["last_checker_receipt"] = receipt
    state["status"] = "retrying"
    state["stage"] = "retrying"
    save_state(state, "attempt_rejected", attempt=state["attempt"], reason=HIDDEN_PROBE, role=probe.role)
    return receipt


def extract_tree(source: Path, commit: str, destination: Path) -> None:
    """A commit's files, without its Git history, through `git archive` and a checked tar."""
    archived = subprocess.run(["git", "-C", str(source), "archive", "--format=tar", commit],
                              capture_output=True, check=False)
    if archived.returncode:
        raise RunError(f"cannot read commit {commit[:12]}: {archived.stderr.decode('utf-8', 'replace').strip()}")
    destination.mkdir(parents=True, exist_ok=True)
    import io
    import tarfile
    with tarfile.TarFile(fileobj=io.BytesIO(archived.stdout)) as archive:  # bytes, not text
        for member in archive.getmembers():
            name = Path(member.name)
            if name.is_absolute() or ".." in name.parts or not (member.isfile() or member.isdir()):
                raise RunError(f"commit {commit[:12]} holds {member.name!r}, which is not a plain file or folder")
        archive.extractall(destination)


def run_hidden_tests(state: dict[str, Any], manifest: dict[str, Any], candidate: str) -> dict[str, Any]:
    """Opt-in hidden acceptance tests. They run in the verifier sandbox against a plain copy of the
    candidate in a temporary folder, never in a worktree a role sees, and only their result, time
    and output hash are kept: no output is stored where a maker could read it. They can only reject."""
    hidden = manifest["hidden_tests"]
    tier = risk_record(Path(state["worktree"]), state["base_head"], candidate, manifest.get("risk_tier"))["tier"]
    record: dict[str, Any] = {"commit": hidden["commit"], "tier": tier, "tiers": hidden["tiers"]}
    if tier not in hidden["tiers"]:
        return {**record, "status": "skipped"}
    started = time.monotonic()
    # The suite and the candidate sit in separate folders, so no candidate file can join the suite,
    # and the suite is read-only to the run. A pass needs the harness's own marker with a token made
    # for this run, not just exit 0, so an early exit from candidate code does not pass.
    token = uuid.uuid4().hex
    with private_scratch("agentsmith-hidden-") as scratch:
        workspace, suite = scratch / "candidate", scratch / "suite"
        extract_tree(Path(state["worktree"]), candidate, workspace)
        try:
            extract_tree(Path(str(hidden["repo"])).expanduser().resolve(), hidden["commit"], suite)
        except (RunError, OSError) as exc:
            # The detail names hidden entries; keep only a reference the operator can match locally.
            reference = hashlib.sha256(str(exc).encode("utf-8", "replace")).hexdigest()[:12]
            raise RunError(f"hidden acceptance tests could not be prepared (reference {reference})") from None
        run(["git", "init", "-q", str(workspace)], workspace)  # the verifier sandbox expects a Git folder
        argv = [item.replace("{hidden}", str(suite)).replace("{token}", token) for item in hidden["command"]]
        # No shared /tmp: code the hidden tests run must not leave the suite where a later role reads.
        result = sandboxed_verify(shlex.join(argv), workspace, max(1, remaining_seconds(state, manifest)),
                                  verifier_env(), read_dirs=(suite,), shared_tmp=False)
    output = hashlib.sha256((result.stdout + "\0" + result.stderr).encode("utf-8", "replace")).hexdigest()
    passed = result.returncode == 0 and f"{HIDDEN_PASS_MARKER} {token}" in result.stdout.splitlines()
    return {**record, "status": "pass" if passed else "fail", "exit_code": result.returncode,
            "marker_seen": passed, "duration_seconds": round(time.monotonic() - started, 1),
            "output_sha256": output}


UNBOUNDED = "unbounded"
# The cap each runtime spends, and the type its value must have.
RUNTIME_BUDGETS = {"codex": ("codex_goal_tokens", "a positive whole number of tokens"),
                   "claude": ("claude_max_usd", "a positive number of US dollars")}


def positive_number(value: Any, *, whole: bool) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if whole and not isinstance(value, int):
        return False
    if isinstance(value, int):
        # Every limit is used as a float later; a larger JSON integer would raise OverflowError.
        return 0 < value <= MAX_LIMIT_INTEGER
    return math.isfinite(value) and value > 0


MAX_LIMIT_INTEGER = 2 ** 53  # the largest integer a float holds exactly


def validate_budgets(manifest: dict[str, Any]) -> None:
    """Every budget is explicit. A zero or missing cap once meant "no cap"; now it refuses, and
    only the string "unbounded" with a written `budget_rationale` removes a token or USD cap.
    The wall clock has no unbounded choice: it is the cap enforced inside every role."""
    limits = manifest.get("limits")
    if not isinstance(limits, dict):
        raise RunError("limits must be a JSON object")
    attempts = limits.get("max_attempts")
    if not positive_number(attempts, whole=True) or attempts > 3:
        raise RunError("limits.max_attempts must be between 1 and 3")
    if not positive_number(limits.get("wall_minutes"), whole=True):
        raise RunError("limits.wall_minutes must be a positive whole number of minutes")
    rationale = limits.get("budget_rationale", "")
    if not isinstance(rationale, str):
        raise RunError("limits.budget_rationale must be text: the size class, the usage it rests on, and who set it")
    runtimes = {role.get("runtime") for role in manifest.get("roles", {}).values() if isinstance(role, dict)}
    for runtime, (field, kind) in RUNTIME_BUDGETS.items():
        if runtime not in runtimes:
            continue
        value = limits.get(field)
        if value == UNBOUNDED:
            if not rationale.strip():
                raise RunError(f"limits.{field} is unbounded; write who chose that and why in "
                               "limits.budget_rationale")
        elif not positive_number(value, whole=field == "codex_goal_tokens"):
            raise RunError(f"limits.{field} must be {kind}, or \"{UNBOUNDED}\" with a written "
                           "limits.budget_rationale; zero or a missing value no longer means no cap")
    for field, (low, high) in RUN_SHAPE_BOUNDS.items():
        if field in limits and not (positive_number(limits[field], whole=True) and low <= limits[field] <= high):
            raise RunError(f"limits.{field} must be a whole number from {low} to {high}")
    if "checker_reserve" in limits:
        reserve, (low, high) = limits["checker_reserve"], CHECKER_RESERVE_BOUNDS
        if not positive_number(reserve, whole=False) or not low <= reserve <= high:
            raise RunError(f"limits.checker_reserve must be a fraction from {low} to {high} of a cap that both the "
                           "maker and the checker spend: enough to check, and at least half left for making")


# Run-shape guards (SF-16): a loop that repeats itself ends before the attempt cap. Rejections are
# identical when their `reason` and their failing-test signature match; a silent maker turn is one
# whose candidate tree equals the tree the controller last judged. max_attempts is at most 3, so
# two identical rejections in a row already show the third attempt would only repeat them, and a
# turn that changed nothing cannot change the verdict.
DEFAULT_IDENTICAL_REJECTIONS = 2
DEFAULT_SILENT_TURNS = 1
RUN_SHAPE_BOUNDS = {"max_identical_rejections": (2, 3), "max_silent_turns": (1, 3)}
MISSING_REASON = "(no reason)"  # an attempt_rejected event without `reason` is a value of its own
SIGNATURE_TAIL_LINES = 20
# What changes between two runs of the same failure: clock times, durations, hashes, attempt numbers.
SIGNATURE_NOISE = (
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<time>"),
    (re.compile(r"\b\d{1,2}:\d{2}:\d{2}(?:[.,]\d+)?\b"), "<time>"),
    (re.compile(r"\b\d+(?:\.\d+)?\s?(?:ms|s|sec|secs|seconds|min)\b"), "<duration>"),
    # A hash has a letter and a digit; an ordinary number (`expected rows 1000001`) is kept.
    (re.compile(r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*[0-9])[0-9a-f]{7,64}\b"), "<hex>"),
    (re.compile(r"(-check-)\d+"), r"\1<n>"),
    (re.compile(r"\b(attempt)([-_ ]?#?)\d+", re.IGNORECASE), r"\1\2<n>"),
    # Temporary folders: the root, then the per-run folder made inside it (a file directly in the
    # root keeps its name, so two different missing files still differ).
    (re.compile(r"(?<![\w.~-])(?:/private)?/var/folders/[^/\s]+/[^/\s]+/[A-Z](?=/)"
                r"|(?<![\w.~-])(?:/private)?/(?:var/)?tmp(?=/)"
                r"|[A-Za-z]:\\Users\\[^\\\s]+\\AppData\\Local\\Temp(?=\\)", re.IGNORECASE), "<tmp>"),
    (re.compile(r"<tmp>([/\\])[^/\\\s]+(?=[/\\])"), r"<tmp>\1<dir>"),
    (re.compile(r"\b(pid|port)(\s*[=:]\s*|\s+)\d+", re.IGNORECASE), r"\1\2<n>"),
    (re.compile(r"\b((?:\d{1,3}\.){3}\d{1,3}|localhost|\[::1\]):\d{2,5}\b", re.IGNORECASE), r"\1:<port>"),
)


def run_shape_limits(limits: dict[str, Any]) -> tuple[int, int]:
    """(N identical rejections, K silent maker turns) that end the attempts, from the manifest."""
    return (int(limits.get("max_identical_rejections", DEFAULT_IDENTICAL_REJECTIONS)),
            int(limits.get("max_silent_turns", DEFAULT_SILENT_TURNS)))


def rejection_signature(event_fields: dict[str, Any], verify_output: str | None) -> str:
    """The rejection's `reason` and its failing-test signature: the failing checks the verify
    output names, or, when it names none, a hash of its last lines with the noise removed."""
    reason = event_fields.get("reason")
    reason = MISSING_REASON if reason is None else str(reason)
    if verify_output is None:
        return f"{reason} | no verify output"
    _, failing = named_checks(verify_output)
    if failing:
        material, kind = "\n".join(sorted(failing)), "tests"
    else:
        lines = [line.strip() for line in verify_output.splitlines() if line.strip()][-SIGNATURE_TAIL_LINES:]
        material, kind = "\n".join(lines), "output"
        for pattern, replacement in SIGNATURE_NOISE:
            material = pattern.sub(replacement, material)
    return f"{reason} | {kind} {hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]}"


def identical_rejection_streak(state: dict[str, Any]) -> tuple[int, str | None]:
    """How many attempts in a row, ending with the current one, were rejected the same way. Read
    from events.jsonl, so it needs no stored copy and resume sees exactly what was recorded."""
    run_dir = Path(state["state_path"]).parent
    rejected: dict[int, dict[str, Any]] = {}
    events = run_dir / "events.jsonl"
    for line in (read_output(events).splitlines() if events.is_file() else []):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("event") == "attempt_rejected" and type(record.get("attempt")) is int:
            rejected[record["attempt"]] = record
    streak, last = 0, None
    attempt = int(state.get("attempt", 0))
    while attempt in rejected:
        log = run_dir / f"attempt-{attempt}-verify.txt"
        signature = rejection_signature(rejected[attempt], read_output(log) if log.is_file() else None)
        if last is not None and signature != last:
            break
        streak, last, attempt = streak + 1, signature, attempt - 1
    return streak, last


def silent_turn_streak(state: dict[str, Any], worktree: Path, before_head: str, after_head: str) -> int:
    """Silent maker turns in a row, this one included: turns whose candidate tree is the tree the
    controller last judged (the base for the first attempt). Counted once per attempt, so a
    resumed candidate is not counted twice."""
    record = state.get("silent_turns")
    if isinstance(record, dict) and record.get("attempt") == state["attempt"]:
        return int(record.get("count", 0))
    silent = git(worktree, "rev-parse", f"{after_head}^{{tree}}") == git(worktree, "rev-parse", f"{before_head}^{{tree}}")
    chained = isinstance(record, dict) and record.get("attempt") == state["attempt"] - 1
    previous = int(record.get("count", 0)) if chained else 0
    count = previous + 1 if silent else 0
    state["silent_turns"] = {"attempt": state["attempt"], "count": count}
    save_state(state)
    return count


# The share of a runtime's cap held back for checking when the maker and the checker spend the same
# cap. Without it a maker can spend what the checker needs, and the run ends with work nobody checks.
DEFAULT_CHECKER_RESERVE = 0.25
CHECKER_RESERVE_BOUNDS = (0.05, 0.5)  # at least a token share for checking; at least half for making


class BudgetReserved(RunError):
    """A maker would spend the share of a budget reserved for checking: a budget stop, not a model failure."""

    reason = "budget"


def checker_reserve(manifest: dict[str, Any], runtime: str) -> float:
    """The amount of `runtime`'s cap reserved for checking: a fraction of the cap when the maker and
    the checker both spend it, else nothing (no other role competes for it)."""
    roles = manifest.get("roles", {})
    if any((roles.get(role) or {}).get("runtime") != runtime for role in ("maker", "checker")):
        return 0.0
    cap = budget_cap(manifest["limits"], RUNTIME_BUDGETS[runtime][0])
    if cap is None:
        return 0.0
    return cap * float(manifest["limits"].get("checker_reserve", DEFAULT_CHECKER_RESERVE))


def maker_allowance(state: dict[str, Any], manifest: dict[str, Any]) -> float | None:
    """What the maker may still spend of its runtime's cap, above the checking reserve (None: unbounded)."""
    runtime = manifest["roles"]["maker"]["runtime"]
    cap = budget_cap(manifest["limits"], RUNTIME_BUDGETS[runtime][0])
    if cap is None:
        return None
    spent = float(state.get("claude_cost_usd", 0.0)) if runtime == "claude" else float(state.get("codex_tokens_used", 0))
    return cap - checker_reserve(manifest, runtime) - spent


def budget_cap(limits: dict[str, Any], field: str) -> float | None:
    """The validated cap, or None for an explicit unbounded choice."""
    value = limits.get(field)
    if value == UNBOUNDED:
        return None
    if not positive_number(value, whole=False):
        raise RunError(f"limits.{field} is not a validated budget")  # fail closed, never "no cap"
    return float(value)


def budget_overrun(state: dict[str, Any], manifest: dict[str, Any], runtime: str) -> str | None:
    """Name the run-wide cap a finished role of this runtime crossed, if any."""
    cap = budget_cap(manifest["limits"], RUNTIME_BUDGETS[runtime][0])
    if runtime == "claude" and cap is not None and float(state.get("claude_cost_usd", 0.0)) > cap:
        return "Claude run-wide USD budget exceeded"
    if runtime == "codex" and cap is not None and int(state.get("codex_tokens_used", 0)) > cap:
        return "Codex run-wide token budget exceeded"
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
    unset = unset_role_settings(manifest)
    if unset:
        raise RunError(f"{', '.join(unset)} must be explicit before execution; draft manifest is non-executable")
    verify_config = manifest["verify"]
    if not isinstance(verify_config, dict) or not isinstance(verify_config.get("command"), str) or not verify_config["command"].strip():
        raise RunError("verify.command must name a required verification command")
    refused = verify_command_problem(verify_config["command"])
    if refused:
        raise RunError(refused)
    validate_budgets(manifest)
    hidden = hidden_tests_problem(manifest, repo)
    if hidden:
        raise RunError(hidden)
    rework_note(repo, manifest)  # refuses a note that changed after prepare
    if "risk_tier" in manifest and manifest["risk_tier"] not in RISK_TIERS:
        raise RunError(f"risk_tier must be one of {', '.join(RISK_TIERS)}; it can only raise the computed tier")
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
    problems = spec_pipeline_problems(repo, meta, str(manifest["base_ref"]), text=shown)
    if problems:
        raise RunError("accepted spec fails the pipeline check: " + "; ".join(problems))
    if str(manifest["implementation_ticket"]) == meta.get("decision_ticket"):
        raise RunError("implementation_ticket must be separate from decision_ticket")
    demo = demo_command_problem(shown)
    if demo:
        raise RunError(demo)
    digest = hashlib.sha256(shown.encode()).hexdigest()
    return spec_rel, digest


def validate_original_spec(repo: Path, spec_rel: Path, base_ref: str) -> None:
    """Resume only while the original file still represents the frozen contract."""
    original = repo / spec_rel
    expected = git(repo, "rev-parse", f"{base_ref}:{spec_rel.as_posix()}", check=False)
    actual = (git(repo, "hash-object", "--path", spec_rel.as_posix(), str(original), check=False)
              if original.is_file() and not original.is_symlink() else "")
    if not expected or actual != expected:
        raise RunError("original spec changed since start; create a new run for a changed contract")


def graph_validator_source() -> Path:
    """Locate the managed graph validator in a checkout or installed runtime."""
    controller_dir = Path(__file__).resolve().parent
    source = ((controller_dir if controller_dir.name == ".agentsmith" else controller_dir.parent)
              / "work_graph.py")
    if not source.is_file():
        raise RunError("work-graph contract validator is unavailable")
    return source


def graph_effective_base(repo: Path, graph_path: str, manifest_path: Path,
                         manifest: dict[str, Any], spec_rel: Path, spec_hash: str,
                         effective_base: str) -> dict[str, str]:
    """Accept only the graph contract's exact root or verified dependency checkpoint."""
    if not re.fullmatch(r"[0-9a-f]{40}", effective_base):
        raise RunError("effective base must be a full lowercase 40-hex commit OID")
    source = graph_validator_source()
    module_spec = importlib.util.spec_from_file_location("agentsmith_work_graph_for_run", source)
    if module_spec is None or module_spec.loader is None:
        raise RunError("work-graph contract validator cannot be loaded")
    graph_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(graph_module)
    try:
        contract = graph_module.load_contract(repo, graph_path)
        run_id = str(manifest["run_id"])
        node = contract["nodes"].get(run_id)
        if node is None:
            raise RunError(f"run {run_id} is not a node in the graph contract")
        try:
            manifest_rel = manifest_path.relative_to(repo).as_posix()
        except ValueError as exc:
            raise RunError("graph run manifest must live inside the repository") from exc
        if node["manifest_path"] != manifest_rel:
            raise RunError("graph node manifest path does not match the requested run")
        if node["manifest_sha256"] != hashlib.sha256(manifest_path.read_bytes()).hexdigest():
            raise RunError("graph node manifest hash does not match the requested run")
        expected = (graph_module._checkpoint_commit(contract, run_id)
                    if node["depends_on"] else contract["contract_commit"])
        if expected is None or effective_base != expected:
            raise RunError("effective base does not match the pinned graph dependency checkpoint")
        if git(repo, "cat-file", "-t", effective_base, check=False) != "commit":
            raise RunError("effective base is not an available commit")
        ancestor = run(["git", "merge-base", "--is-ancestor", contract["contract_commit"], effective_base], repo)
        if ancestor.returncode:
            raise RunError("effective base does not descend from the graph contract commit")
        shown = git(repo, "show", f"{effective_base}:{spec_rel.as_posix()}", check=False)
        if hashlib.sha256(shown.encode()).hexdigest() != spec_hash:
            raise RunError("accepted spec bytes changed in the effective base")
        return {
            "graph_id": contract["graph_id"],
            "graph_path": graph_path,
            "graph_sha256": contract["graph_sha256"],
            "contract_commit": contract["contract_commit"],
            "effective_base_oid": effective_base,
            # Fixed at start and kept in the run state; resume does not recompute it.
            "sequence_numbers": graph_sequence_numbers(graph_module, contract, run_id, effective_base),
        }
    except graph_module.GraphError as exc:
        raise RunError(f"graph contract or checkpoint invalid: {exc}") from exc


def graph_sequence_numbers(graph_module: Any, contract: dict[str, Any], run_id: str, base: str) -> list[dict[str, str]]:
    """The child's reserved numbers. A full numbered folder refuses the start in its own words,
    not as a changed graph contract."""
    try:
        return graph_module.sequence_numbers(contract, run_id, base)
    except graph_module.SequenceExhausted as exc:
        raise RunError(f"numbered folder {exc.folder} has no free number of up to six digits after "
                       f"{exc.highest}; renumber or archive its files before a graph run adds one") from exc


def attention_limit_at_base(repo: Path, risk_map: Any, base_ref: str) -> int:
    """attention_limit from the risk policy committed at the run's base ref, resolved in the main
    checkout (the Git common directory), not in this one. Run branches live in linked worktrees, so
    a commit on one, or a checkout of one here, cannot raise the limit that gates new runs."""
    if not isinstance(base_ref, str) or not base_ref or base_ref.startswith("-"):
        raise RunError(f"base_ref {base_ref!r} is not a ref")
    common = resolved_git_path(repo, "--git-common-dir")
    commit = git(repo, f"--git-dir={common}", "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}",
                 check=False)
    return risk_map.attention_limit(repo, commit) if commit else risk_map.DEFAULT_ATTENTION_LIMIT


def waiting_on_operator(repo: Path, base_ref: str = "HEAD") -> tuple[list[str], int]:
    """The runs that wait on the operator, counted by the inbox's own derivation so the two never
    disagree, and the attention limit at the base ref. Both modules sit next to this controller,
    as risk_map does. A count that cannot be made refuses, never guesses."""
    try:
        import inbox
        import risk_map
    except ImportError as exc:
        raise RunError(f"the attention budget cannot be checked: {exc}; reinstall with `agentsmith update`") from exc
    liveness = SimpleNamespace(read_lock=read_lock, process_is_live=process_is_live)
    try:
        limit = attention_limit_at_base(repo, risk_map, base_ref)
        report = inbox.waiting_runs(repo, controller=liveness)
    except (risk_map.PolicyError, risk_map.RiskError, inbox.InboxError) as exc:
        raise RunError(f"the attention budget cannot be checked: {exc}") from exc
    return [row["id"] for row in report["rows"]], limit


def assert_attention_budget(repo: Path, rework_of: Any, base_ref: str = "HEAD") -> None:
    """A WIP limit, checked by prepare and again by start: no new run while as many runs wait on
    the operator as the policy allows. A rework of a waiting run passes, because it turns that run
    into work instead of adding one."""
    waiting, limit = waiting_on_operator(repo, base_ref)
    if len(waiting) >= limit and (not isinstance(rework_of, str) or rework_of not in waiting):
        raise RunError(f"attention budget reached: {len(waiting)} runs wait on you and the limit is {limit} "
                       f"(attention_limit in {POLICY_FILE}); land a waiting run (`deliver`), rework it "
                       "(`prepare --rework-of <run-id>`), or delete its run branch to drop it from the inbox; "
                       "`agentsmith inbox` lists them")


def prepare(args: argparse.Namespace) -> int:
    repo = repo_root(Path.cwd())
    assert_autonomy_not_paused(repo, action="prepare", run_id=args.run_id)
    if args.template:
        source = Path(args.template).resolve()
    else:
        source = repo / "templates/autonomous-run.json"
        if not source.exists():
            source = repo / ".harness/templates/autonomous-run.json"
    manifest = load_json(source)
    assert_attention_budget(repo, args.rework_of, str(manifest.get("base_ref") or "HEAD"))
    manifest["run_id"] = args.run_id
    manifest["spec_path"] = args.spec
    manifest["implementation_ticket"] = args.ticket
    if args.maker:
        manifest["roles"]["maker"]["runtime"] = args.maker
    if args.checker:
        manifest["roles"]["checker"]["runtime"] = args.checker
    spec = repo / args.spec
    if spec.is_file():
        text = read_text(spec)
        problems = spec_pipeline_problems(repo, frontmatter(text),
                                          str(manifest.get("base_ref") or "HEAD"), text=text)
        if problems:
            raise RunError(f"{args.spec} fails the pipeline check: " + "; ".join(problems))
    if args.maker_model:
        manifest["roles"]["maker"]["model"] = args.maker_model
    if args.checker_model:
        manifest["roles"]["checker"]["model"] = args.checker_model
    unset = unset_role_settings(manifest)
    if unset:
        raise RunError(f"{', '.join(unset)} are blank or placeholders; pass --maker-model and "
                       "--checker-model, or fill them in the template, before prepare writes a manifest")
    verify_config = manifest.get("verify")
    refused = verify_command_problem(verify_config["command"]) if isinstance(verify_config, dict) \
        and isinstance(verify_config.get("command"), str) else None
    if refused:
        raise RunError(refused)
    validate_budgets(manifest)
    hidden = hidden_tests_problem(manifest, repo)
    if hidden:
        raise RunError(hidden)
    if bool(args.rework_of) != bool(args.note):
        raise RunError("--rework-of and --note go together")
    if args.rework_of:
        # A rework is always a new run: an accepted or escalated run is never reopened.
        if args.rework_of == args.run_id:
            raise RunError("a rework is a new run: choose a run id other than the one it reworks")
        previous = load_run(repo, args.rework_of)
        owner = read_lock(state_root(repo) / args.rework_of)
        live = bool(owner and process_is_live(owner["pid"]))
        if previous.get("status") not in TERMINAL_RUN_STATUSES or live:
            step = ("" if live or previous.get("status") in TERMINAL_RUN_STATUSES else
                    f"; it has no live controller: resume it (`resume {args.rework_of}`) so it finishes, then rework it")
            raise RunError(f"run {args.rework_of} is {previous.get('status')}; only a finished run "
                           f"(accepted, awaiting-human, escalated or interrupted) can be reworked{step}")
        note = (Path.cwd() / args.note).resolve()
        if not note.is_relative_to(repo) or not note.is_file():
            raise RunError(f"rework note {args.note} must be a file inside the repository")
        if note.stat().st_size > MAX_REWORK_NOTE_BYTES:
            raise RunError(f"rework note {args.note} is larger than {MAX_REWORK_NOTE_BYTES // 1024} KB")
        note_text_problem(note.read_bytes(), args.note)
        manifest["rework"] = {"of": args.rework_of, "note_path": note.relative_to(repo).as_posix(),
                              "note_sha256": hashlib.sha256(note.read_bytes()).hexdigest()}
    output = Path(args.output or f".harness/runs/{args.run_id}.json")
    output = output if output.is_absolute() else repo / output
    if output.exists() and not args.force:
        raise RunError(f"refusing to overwrite {output}; pass --force deliberately")
    write_json(output, manifest)
    print(f"prepared {output.relative_to(repo) if output.is_relative_to(repo) else output}")
    print("review the scope, verifier, models and budgets, then commit the manifest before start")
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
    # A move must list its old path too: rename detection would hide the path that scope
    # and protection rules are written against.
    return git_paths(worktree, "diff", "--name-only", "--no-renames", f"{base}..{head}")


def history_commits(worktree: Path, base: str, head: str) -> list[str]:
    """Every commit from base (exclusive) to head, oldest first."""
    return [line for line in git(worktree, "rev-list", "--reverse", f"{base}..{head}").splitlines() if line]


def history_paths(worktree: Path, base: str, head: str) -> dict[str, str]:
    """Every path that any commit from base to head adds, changes or deletes, mapped to the first
    commit that touched it. The candidate's history is what would be pushed, so a path a later commit
    removes again still counts. Moves count by both paths (no rename detection); a merge counts
    against each of its parents."""
    touched: dict[str, str] = {}
    for commit in history_commits(worktree, base, head):
        parents = git(worktree, "rev-list", "--parents", "-n", "1", commit).split()[1:]
        for parent in parents or ["4b825dc642cb6eb9a060e54bf8d69288fbee4904"]:  # the empty tree
            for path in git_paths(worktree, "diff", "--name-only", "--no-renames", parent, commit):
                touched.setdefault(path, commit)
    return touched


# These are controller policy, even when the maker scope is broad. Additional project
# acceptance inputs belong in verify.protected_paths in the operator-approved manifest.
VERIFICATION_POLICY_PATHS = (
    ".agentsmith/**", ".harness/**", ".github/workflows/**",
    "scripts/verify*", "scripts/autonomous-run.py", "native_launcher.py",
    "agentsmith.py", "windows_verifier_sandbox.py",
    # Never part of a candidate: the name the hidden acceptance suite once used inside the copy.
    ".agentsmith-hidden-tests", ".agentsmith-hidden-tests/**",
)
BASELINE_TEST_PATHS = ("test_*.py", "*_test.py", "tests/**", "test/**",
                       "**/tests/**", "**/test/**", "**/test_*.py", "**/*_test.py",
                       "*.test.*", "*.spec.*", "*_test.go", "*_spec.rb", "scripts/test-*")
# Instructions and configuration that Claude Code, Codex and other agent clients load from the
# checkout, including `.mcp.json`, which can start an MCP server inside the checker's client. The checker runs in a worktree at the candidate commit, so a maker that edits these
# writes instructions for its own judge. They count at any depth: Claude Code loads a nested
# CLAUDE.md when it reads files in that folder, and discovers nested `.claude/skills`. Names match
# ignoring case, because macOS and Windows open `claude.md` when a client asks for `CLAUDE.md`.
AGENT_INSTRUCTION_FILES = frozenset({"agents.md", "agents.override.md", "claude.md",
                                     "claude.local.md", "gemini.md", ".mcp.json"})
AGENT_CONFIGURATION_FOLDERS = frozenset({".claude", ".codex", ".agents", ".cursor", ".gemini"})


def agent_instruction_path(path: str) -> bool:
    parts = path.casefold().split("/")
    return parts[-1] in AGENT_INSTRUCTION_FILES or any(part in AGENT_CONFIGURATION_FOLDERS for part in parts)


def symbolic_links(worktree: Path, commit: str) -> dict[str, str | None]:
    """Each symbolic link in a commit, with the repository path it points to (None outside it)."""
    links: dict[str, str | None] = {}
    for entry in run(["git", "ls-tree", "-r", "-z", "--full-tree", commit], worktree).stdout.split("\0"):
        meta, _, path = entry.partition("\t")
        fields = meta.split()
        if len(fields) != 3 or fields[0] != "120000":
            continue
        target = subprocess.run(["git", "cat-file", "blob", fields[2]], cwd=worktree, capture_output=True,
                                check=False).stdout.decode("utf-8", errors="replace")
        joined = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
        outside = target.startswith("/") or joined == ".." or joined.startswith("../")
        links[path] = None if outside else joined
    return links


def link_protected_targets(links: dict[str, str | None]) -> dict[str, str]:
    """Repository paths an instruction link reads through, mapped to that link, following chains.
    Each key is case-folded, because the checkout may be on a case-insensitive disk."""
    folded = {path.casefold(): target for path, target in links.items()}
    protected: dict[str, str] = {}
    for link in links:
        if not agent_instruction_path(link):
            continue
        target = links[link]
        for _ in range(40):  # the depth at which the operating system gives up as well
            if target is None or target.casefold() in protected:
                break
            protected[target.casefold()] = link
            target = folded.get(target.casefold())
    return protected


def link_reason(path: str, protected: dict[str, str], links: list[dict[str, str | None]]) -> str | None:
    """Why a changed path reaches agent instructions through a symbolic link, if it does."""
    folded = path.casefold()
    for target, link in protected.items():
        if folded == target or folded.startswith(target + "/"):
            return f"{path} (read through {link})"
    for version in links:
        if path not in version:
            continue
        chain = {key.casefold(): value for key, value in version.items()}
        target = version[path]
        for _ in range(40):
            if target is None:
                break
            if agent_instruction_path(target) or target.casefold() in protected:
                return f"{path} (a link to {target})"
            target = chain.get(target.casefold())
    return None


def validate_verification_changes(worktree: Path, base: str, head: str,
                                  manifest: dict[str, Any]) -> None:
    """Reject policy edits, agent-instruction edits, and edits/deletions of the approved
    baseline checks. Operator-approved scope cannot widen any of these."""
    extra = manifest.get("verify", {}).get("protected_paths", [])
    if not isinstance(extra, list) or any(not isinstance(path, str) or not path for path in extra):
        raise RunError("verify.protected_paths must be an array of nonempty path globs")
    baseline = set(git_paths(worktree, "ls-tree", "-r", "--name-only", base))
    # A symbolic link such as AGENTS.md -> src/rules.txt makes its target an instruction file too,
    # in the base, in the candidate and in every commit between; adding, moving or removing a link
    # to one also counts.
    commits = history_commits(worktree, base, head)
    versions = [symbolic_links(worktree, commit) for commit in [base, *commits, head]]
    reached: dict[str, str] = {}
    for version in versions:
        reached.update(link_protected_targets(version))
    # Every commit counts, not only the end-to-end diff: a protected input edited in one commit and
    # restored in the next is in the history that would be pushed.
    touched = {path: None for path in git_paths(worktree, "diff", "--name-only", "--no-renames", base, head)}
    for path, commit in history_paths(worktree, base, head).items():
        touched.setdefault(path, commit)
    protected = []
    instructions = []
    for path, commit in touched.items():
        shown = path if commit is None else f"{path} (commit {commit[:12]})"
        patterns = (*VERIFICATION_POLICY_PATHS, *extra)
        if path in baseline:
            patterns += BASELINE_TEST_PATHS
        through_link = link_reason(path, reached, versions)
        if agent_instruction_path(path):
            instructions.append(shown)
        elif through_link:
            instructions.append(through_link if commit is None else f"{through_link} (commit {commit[:12]})")
        elif path == manifest.get("spec_path") or any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns):
            protected.append(shown)
    if protected or instructions:
        detail = ([shown_paths(protected)] if protected else []) + (
            ["agent instructions: " + shown_paths(instructions)] if instructions else [])
        raise RunError("maker changed protected verification inputs; separate operator review required: "
                       + "; ".join(detail), reason="protected")


# `awaiting-human`: the checker accepted, but no passed calibration lets it gate (SF-09). The run is
# finished for the controller and holds its candidate for a person; nothing resumes or delivers it.
TERMINAL_RUN_STATUSES = {"accepted", "awaiting-human", "escalated", "interrupted"}
AWAITING_HUMAN_NEXT = ("a human reviews and re-runs with an explicit approval: review the held commit, "
                       "calibrate the checker until it passes, then prepare a rework run "
                       "(prepare ... --rework-of <run-id> --note <file>) and start it")


def checker_calibration(state: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    """The latest calibration of this run's checker client, model and prompt, read now."""
    return calibration_status(Path(state.get("repo") or state["worktree"]),
                              (manifest.get("roles") or {}).get("checker") or {})


def verification_binding(state: dict[str, Any], manifest: dict[str, Any], head: str) -> dict[str, Any]:
    """Controller-authored evidence identifies the exact policy and candidate checked."""
    worktree = Path(state["worktree"])
    config = subprocess.run(["git", "show", f"{head}:.harness/verify.conf"],
                            cwd=worktree, capture_output=True, check=False)
    return {
        "candidate_commit": head,
        "base_commit": state["base_head"],
        "spec_sha256": state["spec_sha256"],
        "manifest_sha256": state["manifest_sha256"],
        "verification_policy_sha256": hashlib.sha256(
            json.dumps(manifest["verify"], sort_keys=True).encode()).hexdigest(),
        "verify_configuration_sha256": hashlib.sha256(config.stdout).hexdigest() if config.returncode == 0 else None,
        "runtime_sha256": {
            "controller": file_digest(Path(__file__)),
            "launcher": file_digest(Path(build_native_command.__code__.co_filename)),
        },
        # The latest calibration of this checker client, model and prompt: unless it is `passed`,
        # the checker is advisory and an acceptance waits for a human. The acceptance reads it
        # again and records the value that gated in its place.
        "checker_calibration": checker_calibration(state, manifest),
    }


def candidate_moved(worktree: Path, branch: str, commit: str) -> str | None:
    """Why the run branch no longer shows exactly the commit its checks passed, if it does not.
    A detached process left by a role, or anyone else, can commit after the verifier ran. The
    commit IDs are read again after the clean check, because a commit can land while it runs."""
    def moved() -> str | None:
        head = git(worktree, "rev-parse", "HEAD", check=False)
        tip = git(worktree, "rev-parse", "--verify", f"refs/heads/{branch}", check=False)
        if head == commit and tip == commit:
            return None
        return (f"candidate moved after its checks passed at {commit}: branch {branch} is at "
                f"{tip or 'nothing'} and the run worktree at {head or 'nothing'}; operator review required")

    first = moved()
    if first:
        return first
    if not clean(worktree):
        return (f"run worktree changed after the checks passed at {commit}: it has uncommitted "
                "changes; operator review required")
    return moved()


def acceptance_ready(verify_exit: int, checker: dict[str, Any]) -> bool:
    return (verify_exit == 0 and checker["status"] == "accepted"
            and any(item.strip() for item in checker["evidence"])
            and not checker["unresolved"])


# Verification outcomes, compared with a baseline of the base commit. The rules are ported from
# CodeAF (https://github.com/Agent-Field/CodeAF, Apache-2.0): `internal/verify/baseline.go` (one
# baseline of the tree before the job's first change, inherited by every later round, so a check
# broken in round one is still a finding in round four) and `internal/seniordev/app/
# full_verification.go` with `verification_no_tests.go` (an empty suite and a hung suite are
# incomplete observations, never a pass; a verify command runs with pipefail).
VERIFY_COMMAND_CHECK = "the verify command"
EMPTY_SUITE = re.compile(r"\bRan 0 tests?\b|\bno tests (?:ran|found|collected|to run)\b|\bcollected 0 items?\b"
                         r"|(?<![\w.])0 tests?\b|\bno test files (?:found|matched)\b", re.IGNORECASE)
SOME_TESTS = re.compile(r"\bRan [1-9]\d* tests?\b|\bcollected [1-9]\d* items?\b|(?<![\w.])[1-9]\d* (?:tests?|passed)\b"
                        r"|\brunning [1-9]\d* tests?\b|\bTests run: [1-9]", re.IGNORECASE)
PYTEST_NO_TESTS_EXIT = 5
# Named checks a runner reports, so a regression names a test and not only the command: phases of
# scripts/verify.sh, Python unittest (plain and verbose) and pytest (summary and verbose).
NAMED_CHECKS = (
    ("failing", re.compile(r"^verify\.sh: phase '(.+)' failed\.$"), "phase: {}"),
    ("phase", re.compile(r"^\[\d+/\d+\] (.+)$"), "phase: {}"),
    ("failing", re.compile(r"^(?:FAIL|ERROR): (\S+ \(\S+\))$"), "{}"),
    ("passing", re.compile(r"^(\S+ \(\S+\)) \.\.\. ok$"), "{}"),
    ("failing", re.compile(r"^(\S+ \(\S+\)) \.\.\. (?:FAIL|ERROR)$"), "{}"),
    ("failing", re.compile(r"^(?:FAILED|ERROR) (\S+::\S+)"), "{}"),
    ("passing", re.compile(r"^(\S+::\S+) PASSED\b"), "{}"),
    ("failing", re.compile(r"^(\S+::\S+) (?:FAILED|ERROR)\b"), "{}"),
)


WINDOWS_PIPELINE_REFUSAL = (
    "the verify command contains `|`, and the Windows verifier runs it through cmd.exe, which has no "
    "pipefail: `tests | more` would pass when the tests fail. A quoted or escaped `|` is refused too, "
    "because a nested shell (`cmd /c \"a | b\"`, `powershell -c \"a | b\"`) still runs it as a pipeline; "
    "only `||` is allowed. Use a single command, or a script that exits non-zero when its tests fail, "
    "as verify.command")


def windows_pipeline(command: str) -> bool:
    """Whether `command` holds a `|` that is not exactly `||`. Quoting and `^` escapes are not
    trusted: a nested `cmd /c` or `powershell -c` re-parses its quoted string as a pipeline. A
    run of `|` other than two (`|`, `|||`) is refused; `||` runs the next command on failure."""
    return any(len(run) != 2 for run in re.findall(r"\|+", command))


def verify_command_problem(command: str) -> str | None:
    """Why this platform's verifier cannot judge `command` fail-closed, or None."""
    return WINDOWS_PIPELINE_REFUSAL if sys.platform == "win32" and windows_pipeline(command) else None


def verifier_timed_out(result: subprocess.CompletedProcess[str]) -> bool:
    return bool(getattr(result, "timed_out", False))


def named_checks(output: str) -> tuple[set[str], set[str]]:
    """The checks an output names as passing and as failing. A verify.sh phase that started and
    is not the failed one passed, because verify.sh stops at its first failing phase."""
    found: dict[str, set[str]] = {"passing": set(), "failing": set(), "phase": set()}
    for line in output.splitlines():
        for kind, pattern, label in NAMED_CHECKS:
            match = pattern.match(line.strip())
            if match:
                found[kind].add(label.format(match.group(1)))
    failing = found["failing"]
    return found["passing"] | (found["phase"] - failing), failing


def verification_outcome(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """`passed`, `failed` or `incomplete`, with the named checks. A timeout or an empty suite
    is incomplete: it observed nothing, so it can neither pass nor name a failure."""
    output = f"{result.stdout}\n{result.stderr}"
    if verifier_timed_out(result):
        return {"verification": "incomplete", "passing": [], "failing": [],
                "reason": "the verify command timed out before it finished; a hung suite reported no result"}
    if (result.returncode == PYTEST_NO_TESTS_EXIT or EMPTY_SUITE.search(output)) and not SOME_TESTS.search(output):
        return {"verification": "incomplete", "passing": [], "failing": [],
                "reason": "the verify command ran no tests (an empty suite proves nothing)"}
    passing, failing = named_checks(output)
    (failing if result.returncode else passing).add(VERIFY_COMMAND_CHECK)
    return {"verification": "failed" if result.returncode else "passed", "reason": None,
            "passing": sorted(passing - failing), "failing": sorted(failing)}


def regressions(baseline: dict[str, Any] | None, outcome: dict[str, Any]) -> list[str]:
    """Checks that passed on the base commit and fail now. Always against the base commit,
    never against an earlier attempt, so a check one attempt broke stays a regression."""
    if not baseline:
        return []
    return sorted(set(baseline.get("passing", [])) & set(outcome["failing"]))


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


def terminal_peer_git_artifacts(common: Path, active_ref: str, protected_refs: set[str]
                                ) -> tuple[set[str], set[Path], set[Path]]:
    """Recognize terminal controller-owned peers through exact Git and state binding.

    A peer may finish or resume during another maker's snapshot window. Its
    state must bind the branch to the recorded terminal OID and linked worktree.
    An arbitrary side ref is not a peer.
    """
    refs: set[str] = set()
    logs: set[Path] = set()
    admins: set[Path] = set()
    for state_file in (common / "agentsmith-runs").glob("*/state.json"):
        try:
            state = load_json(state_file)
            run_id = state_file.parent.name
            if (state.get("run_id") != run_id or
                    state.get("branch") != f"agentsmith/{run_id}" or
                    state.get("status") not in TERMINAL_RUN_STATUSES):
                continue
            repo_value = state.get("repo")
            manifest_value = state.get("manifest_path")
            manifest_hash = state.get("manifest_sha256")
            terminal_head = state.get("terminal_head")
            worktree_value = state.get("worktree")
            if not all(isinstance(value, str) for value in
                       (repo_value, manifest_value, manifest_hash, terminal_head, worktree_value)):
                continue
            recorded_repo = Path(repo_value).resolve()
            manifest_path = Path(manifest_value).resolve()
            worktree = Path(worktree_value).resolve()
            if (state_root(recorded_repo).resolve() != (common / "agentsmith-runs").resolve() or
                    not manifest_path.is_relative_to(recorded_repo) or
                    not worktree.is_dir() or
                    not re.fullmatch(r"[0-9a-f]{40,64}", terminal_head) or
                    not re.fullmatch(r"[0-9a-f]{64}", manifest_hash) or
                    hashlib.sha256(manifest_path.read_bytes()).hexdigest() != manifest_hash or
                    load_json(manifest_path).get("run_id") != run_id):
                continue
            ref = f"refs/heads/agentsmith/{run_id}"
            # A ref already visible in the first snapshot remains protected, even if
            # its controller state becomes verifiable before the second snapshot.
            if ref in protected_refs:
                continue
            if (git(recorded_repo, "rev-parse", "--verify", ref, check=False) != terminal_head or
                    git(worktree, "symbolic-ref", "-q", "HEAD", check=False) != ref):
                continue
            dot_git = worktree / ".git"
            marker = dot_git.read_text(encoding="utf-8", errors="replace").strip()
            if not marker.startswith("gitdir: "):
                continue
            admin = Path(marker[8:]).resolve()
            if not admin.is_relative_to(common):
                continue
            if ref != active_ref:
                refs.add(ref)
                logs.add(Path("logs") / ref)
            admins.add(admin.relative_to(common))
        except (OSError, RunError, ValueError):
            continue
    return refs, logs, admins


def generated_server_info_refs(path: Path) -> bool:
    """Recognize Git's non-authoritative dumb-transport ref cache, not arbitrary edits."""
    if path.is_symlink() or path.stat().st_size > 1024 * 1024:
        return False
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError):
        return False
    seen: set[str] = set()
    for line in lines:
        fields = line.split("\t")
        if len(fields) != 2 or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", fields[0]):
            return False
        ref = fields[1].removesuffix("^{}")
        if (not ref.startswith("refs/") or fields[1] in seen or
                any(part in {"", ".", ".."} or part.endswith(".lock") for part in ref.split("/")) or
                re.search(r"[\x00-\x20~^:?*\\\[]", ref)):
            return False
        seen.add(fields[1])
    return True


def _git_metadata_once(repo: Path, *, known_peers: dict[str, Any] | None = None) -> dict[str, Any]:
    common = resolved_git_path(repo, "--git-common-dir")
    active = resolved_git_path(repo, "--git-dir")
    active_rel = active.relative_to(common) if active.is_relative_to(common) else None
    branch_ref = git(repo, "symbolic-ref", "-q", "HEAD", check=False)
    other_run_refs, run_branch_logs, run_worktree_admin = registered_run_git_artifacts(
        common, branch_ref
    )
    protected_refs = set(known_peers.get("protected_refs", [])) if known_peers else set()
    # A peer verified live before this maker started may finish and release its
    # lifecycle lock before the after-snapshot. Preserve its exact exclusions.
    if known_peers:
        other_run_refs.update(known_peers["refs"])
        run_branch_logs.update(Path(value) for value in known_peers["branch_logs"])
        run_worktree_admin.update(Path(value) for value in known_peers["worktree_admin"])
    terminal_refs, terminal_logs, terminal_admin = terminal_peer_git_artifacts(
        common, branch_ref, protected_refs
    )
    other_run_refs.update(terminal_refs)
    run_branch_logs.update(terminal_logs)
    run_worktree_admin.update(terminal_admin)
    other_run_refs.difference_update(protected_refs)
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
        if rel.parts[0] in {"agentsmith-runs", "agentsmith-calibrations", "agentsmith-factory"}:
            continue
        if rel.parts[0] == "objects":
            objects.append((rel.as_posix(), file_digest(path)))
            continue
        if rel == Path("info/refs") and generated_server_info_refs(path):
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
        "factory": factory_snapshot(common),
        "registered_peers": {
            "refs": sorted(other_run_refs),
            "protected_refs": sorted(line.split(" ", 1)[0] for line in refs),
            "branch_logs": sorted(path.as_posix() for path in run_branch_logs),
            "worktree_admin": sorted(path.as_posix() for path in run_worktree_admin),
        },
    }


# How long a snapshot waits for Git's temporary files and locks to clear before failing closed.
# Locks last milliseconds, but a loaded hosted runner can stall a peer's Git call for seconds.
GIT_METADATA_SETTLE_SECONDS = 10
# Git's own short-lived lock files, the only ones a snapshot waits on. Any other file, such as a
# lock another tool holds for a whole run, is compared as it is, as before.
GIT_TRANSIENT_LOCK = re.compile(
    r"(?:worktrees/[^/]+/)?(?:(?:packed-refs|HEAD|ORIG_HEAD|FETCH_HEAD|MERGE_HEAD|CHERRY_PICK_HEAD|REVERT_HEAD"
    r"|AUTO_MERGE|config|config\.worktree|index|shallow)\.lock|logs/.+\.lock)")


def git_metadata(repo: Path, *, known_peers: dict[str, Any] | None = None) -> dict[str, Any]:
    """Take a stable snapshot; never exempt a persistent non-object from tamper checks.

    Parallel Git commits briefly create tmp_obj files and maintenance.lock in the
    shared object store, and Git's files ref backend holds lock files such as
    packed-refs.lock during ordinary ref transactions (a peer's commit or
    `git worktree add`), even when packed-refs itself does not change. Retry while
    any of these exist (GIT_TRANSIENT_LOCK names Git's own locks only), so a snapshot is
    only taken when no Git lock is held, then
    fail closed if they do not settle. The locked files themselves (packed-refs,
    config, HEAD) and all committed objects remain compared.
    """
    deadline = time.monotonic() + GIT_METADATA_SETTLE_SECONDS
    locks: list[str] = []
    while True:
        try:
            snapshot = _git_metadata_once(repo, known_peers=known_peers)
        except FileNotFoundError:
            # A peer may have renamed its temporary object or released its lock during the scan.
            snapshot = None
        if snapshot is not None:
            temporary = [path for path, _ in snapshot["existing_objects"]
                         if (path == "objects/maintenance.lock" or re.fullmatch(
                             r"objects/(?:[0-9a-f]{2}|pack)/tmp_(?:obj|pack|idx|rev)_[^/]+", path))]
            locks = [path for path, _ in snapshot["protected_files"] if GIT_TRANSIENT_LOCK.fullmatch(path)]
            if not temporary and not locks:
                return snapshot
        if time.monotonic() >= deadline:
            if snapshot is not None and locks:
                raise RunError("Git lock file did not clear before metadata validation: " + ", ".join(locks[:8]))
            raise RunError("temporary Git object file did not settle before metadata validation")
        time.sleep(0.02)


# The only entries the factory records folder may hold: operator logs that only grow.
FACTORY_LOGS = frozenset({"events.jsonl", "defects.jsonl", "minutes.jsonl"})


def factory_snapshot(common: Path) -> dict[str, Any]:
    """The factory records folder's shape. It is left out of the strict comparison because other
    commands append to it while a run is live, so it gets its own rule: only the known logs, as
    regular files, and each may only grow (an append keeps every earlier byte)."""
    folder = common / "agentsmith-factory"
    entries: dict[str, Any] = {}
    if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
        return {"folder": str(folder), "entries": {".": {"kind": "not-a-folder"}}}
    for path in sorted(folder.rglob("*")) if folder.is_dir() else []:
        rel = path.relative_to(folder).as_posix()
        if path.is_symlink() or not path.is_file():
            entries[rel] = {"kind": "symlink" if path.is_symlink() else "other"}
            continue
        data = path.read_bytes()
        entries[rel] = {"kind": "file", "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return {"folder": str(folder), "entries": entries}


def factory_tampering(before: dict[str, Any] | None, after: dict[str, Any] | None) -> str | None:
    if not before or not after:
        return None
    folder = Path(after["folder"])
    for rel, entry in after["entries"].items():
        if rel not in FACTORY_LOGS or entry["kind"] != "file":
            return f"agentsmith-factory/{rel} is not an operator log file"
    for rel, entry in before["entries"].items():
        if entry.get("kind") != "file":
            continue
        later = after["entries"].get(rel)
        if later is None or later["size"] < entry["size"]:
            return f"agentsmith-factory/{rel} lost records"
        try:
            prefix = (folder / rel).read_bytes()[:entry["size"]]
        except OSError:
            return f"agentsmith-factory/{rel} cannot be read"
        if hashlib.sha256(prefix).hexdigest() != entry["sha256"]:
            return f"agentsmith-factory/{rel} was rewritten, not appended to"
    return None


def ignored_paths(worktree: Path) -> set[str]:
    return set(git_paths(worktree, "ls-files", "--others", "--ignored", "--exclude-standard"))


def validate_git_transition(worktree: Path, before: dict[str, Any], after: dict[str, Any],
                            branch: str, old_head: str, new_head: str) -> None:
    expected_ref = f"refs/heads/{branch} {new_head}"
    before_other = [line for line in before["refs"] if not line.startswith(f"refs/heads/{branch} ")]
    after_other = [line for line in after["refs"] if not line.startswith(f"refs/heads/{branch} ")]
    if before_other != after_other or expected_ref not in after["refs"]:
        before_refs = dict(line.split(" ", 1) for line in before_other)
        after_refs = dict(line.split(" ", 1) for line in after_other)
        changed = sorted(ref for ref in before_refs.keys() | after_refs.keys()
                         if before_refs.get(ref) != after_refs.get(ref))
        if expected_ref not in after["refs"]:
            changed.append(f"refs/heads/{branch}")
        raise RunError("runtime changed Git refs outside the active run branch: " +
                       ", ".join(changed[:8]))
    for key in ("config", "config_worktree", "hooks", "protected_files"):
        if before[key] != after[key]:
            if key in {"hooks", "protected_files"}:
                old_files = dict(before[key])
                new_files = dict(after[key])
                changed = sorted(path for path in old_files.keys() | new_files.keys()
                                 if old_files.get(path) != new_files.get(path))
                raise RunError(f"runtime changed protected Git metadata: {key}: {', '.join(changed[:8])}")
            raise RunError(f"runtime changed protected Git metadata: {key}")
    tampered = factory_tampering(before.get("factory"), after.get("factory"))
    if tampered:
        raise RunError(f"runtime changed protected Git metadata: {tampered}")
    after_objects = dict(after["existing_objects"])
    altered_objects = [path for path, digest in before["existing_objects"]
                       if after_objects.get(path) != digest]
    if altered_objects:
        raise RunError("runtime altered existing Git objects: " + ", ".join(altered_objects[:8]))
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
    tampered = factory_tampering(before.get("factory"), after.get("factory"))
    if tampered:
        raise RunError(f"{actor} changed protected Git metadata: {tampered}")


@contextlib.contextmanager
def private_scratch(prefix: str):
    """A fresh folder for one role or verifier, removed afterwards. It is short and under `/tmp`
    where that exists: Claude Code falls back to a shared temporary folder when its override path
    is long. A role's own detached process can still find it; see docs/21."""
    root = Path("/tmp") if os.name != "nt" and Path("/tmp").is_dir() else None
    with tempfile.TemporaryDirectory(prefix=prefix, dir=root, ignore_cleanup_errors=True) as folder:
        yield Path(folder).resolve()


def private_tool_environment(env: dict[str, str], scratch: Path, *, home: bool) -> dict[str, str]:
    """Point the temporary, cache and (for the verifier) home folders that tools read at fresh
    folders, so nothing a maker planted in a shared one runs in a later role."""
    folders = {"TMPDIR": scratch / "tmp", "XDG_CACHE_HOME": scratch / "cache"}
    if home:
        base = scratch / "home"
        folders.update(HOME=base, XDG_CONFIG_HOME=base / ".config",
                       XDG_DATA_HOME=base / ".local/share", XDG_STATE_HOME=base / ".local/state")
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    return {**env, **{key: str(value) for key, value in folders.items()}}


# Tool caches a checker would otherwise resolve under the HOME it keeps for its client's sign-in,
# each pointed at a folder inside the checker's own fresh folder.
CHECKER_TOOL_CACHES = {
    "npm_config_cache": "npm", "npm_config_store_dir": "pnpm-store", "YARN_CACHE_FOLDER": "yarn",
    "BUN_INSTALL_CACHE_DIR": "bun", "PIP_CACHE_DIR": "pip", "UV_CACHE_DIR": "uv",
    "PYTHONUSERBASE": "python-user", "CARGO_HOME": "cargo", "GOCACHE": "go-build",
    "GOMODCACHE": "go-mod", "GRADLE_USER_HOME": "gradle",
}


def checker_environment(env: dict[str, str], scratch: Path) -> dict[str, str]:
    """A checker keeps its HOME, because Claude Code and Codex sign in from it, but every
    temporary, configuration, data and cache folder it would read points at fresh folders. The
    maker could write the shared temporary folders, including Claude Code's `/tmp/claude-<uid>`."""
    environment = private_tool_environment(env, scratch, home=False)
    base = scratch / "folders"
    folders = {"TEMP": scratch / "tmp", "TMP": scratch / "tmp", "XDG_CONFIG_HOME": base / "config",
               "XDG_DATA_HOME": base / "data", "XDG_STATE_HOME": base / "state",
               "CLAUDE_CODE_TMPDIR": scratch / "c",
               **{key: base / name for key, name in CHECKER_TOOL_CACHES.items()}}
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    git_config = scratch / "gitconfig"
    git_config.write_text("", encoding="utf-8")  # no ~/.gitconfig, which a tool could plant
    environment.update({key: str(value) for key, value in folders.items()},
                       GIT_CONFIG_GLOBAL=str(git_config),
                       MAVEN_OPTS=f"-Dmaven.repo.local={base / 'maven'}")
    return environment


def sandboxed_verify(command: str, cwd: Path, timeout: int, env: dict[str, str],
                     *, state: dict[str, Any] | None = None,
                     read_dirs: tuple[Path, ...] = (),
                     shared_tmp: bool = True,
                     prefix: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run the human-approved verifier with no network and no writes outside its worktree and a
    private home, temporary and cache folder that exists only for this run of the verifier.
    `read_dirs` are extra folders it may read but not write (the hidden suite). With `shared_tmp`
    off, it may not write the shared /tmp either (Linux never allows that). A timeout returns the
    partial result marked `timed_out` (see `verifier_timed_out`)."""
    common = resolved_git_path(cwd, "--git-common-dir")
    if sys.platform == "win32" and read_dirs:
        return subprocess.CompletedProcess([], 126, "", "hidden tests need the macOS or Linux verifier sandbox")
    if sys.platform == "win32":
        # Checked again here, not only at prepare and start: deliver and a graph child reach the
        # verifier too, and a pipeline cmd.exe runs without pipefail must never be judged.
        refused = verify_command_problem(command)
        if refused:
            return subprocess.CompletedProcess([command], 126, "", refused)
        # The Windows verifier points HOME, USERPROFILE, APPDATA, TEMP and TMP at the disposable
        # worktree and LOCALAPPDATA at a temporary AppContainer profile, both private to it.
        from windows_verifier_sandbox import run_verifier
        result = run_verifier(command, cwd, common, timeout, env)
        # Its runner reports a timeout as exit 126 with exactly this message. A command that
        # prints it itself is only judged incomplete, which is never a pass either.
        if result.returncode == 126 and result.stderr.strip() == "verifier timed out":
            result.timed_out = True  # type: ignore[attr-defined]
        return result
    with private_scratch("agentsmith-verify-") as scratch:
        return posix_sandboxed_verify(command, cwd, common, timeout,
                                      private_tool_environment(env, scratch, home=True), scratch, state,
                                      tuple(path.resolve() for path in read_dirs), shared_tmp, prefix)


def posix_sandboxed_verify(command: str, cwd: Path, common: Path, timeout: int, env: dict[str, str],
                           scratch: Path, state: dict[str, Any] | None,
                           read_dirs: tuple[Path, ...] = (), shared_tmp: bool = True,
                           prefix: str | None = None) -> subprocess.CompletedProcess[str]:
    # `pipefail`: a pipeline such as `pytest | tee log` fails when its test command fails, not
    # only when its last command does. scripts/verify.sh runs with the same option.
    if sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").exists():
        escaped = str(cwd).replace('"', '\\"')
        escaped_common = str(common).replace('"', '\\"')
        home = str(Path.home()).replace('"', '\\"')
        protected = [common, *(trusted_paths(state) if state is not None else [])]
        protected_ancestors = {parent for path in protected for parent in path.resolve().parents
                               if parent != Path('/')}
        profile = "\n".join([
            "(version 1)",
            "(allow default)",
            "(deny network*)",
            "(deny file-write*)",
            f'(deny file-read-data (require-all (subpath "{home}") '
            f'(require-not (subpath "{escaped}")) (require-not (subpath "{escaped_common}")) '
            f'(require-not (subpath {json.dumps(str(scratch), ensure_ascii=False)}))))',
            f'(allow file-write* (subpath "{escaped}"))',
            f'(allow file-write* (subpath {json.dumps(str(scratch), ensure_ascii=False)}))',
            *(['(allow file-write* (subpath "/tmp") (subpath "/private/tmp"))'] if shared_tmp else []),
            '(allow file-write* (literal "/dev/null") (literal "/dev/dtracehelper"))',
            *[f'(deny file-write* (subpath {json.dumps(str(path.resolve()), ensure_ascii=False)}))'
              for path in protected],
            *[f'(deny file-write-unlink (literal {json.dumps(str(parent), ensure_ascii=False)}))'
              for parent in sorted(protected_ancestors)],
        ])
        args = ["/usr/bin/sandbox-exec", "-p", profile, "/bin/bash", "-o", "pipefail", "-c", command]
        return verifier_process(args, cwd, timeout, env, state, prefix)
    if sys.platform.startswith("linux") and shutil.which("bwrap"):
        home = Path.home().resolve()
        temporary = Path("/tmp")
        args = ["bwrap", "--unshare-net", "--die-with-parent", "--ro-bind", "/", "/",
                "--tmpfs", "/tmp"]
        if not home.is_relative_to(temporary):
            args += ["--tmpfs", str(home)]
        directories: set[Path] = set()
        for target in (cwd.resolve(), common, scratch, *read_dirs):
            for mount_root in (temporary, home):
                if target.is_relative_to(mount_root):
                    current = mount_root
                    for part in target.relative_to(mount_root).parts:
                        current /= part
                        directories.add(current)
        for directory in sorted(directories, key=lambda item: len(item.parts)):
            args += ["--dir", str(directory)]
        args += ["--remount-ro", "/tmp"]
        if not home.is_relative_to(temporary):
            args += ["--remount-ro", str(home)]
        args += ["--bind", str(cwd), str(cwd), "--ro-bind", str(common), str(common),
                 "--bind", str(scratch), str(scratch),
                 *[item for path in read_dirs for item in ("--ro-bind", str(path), str(path))],
                 "--dev", "/dev", "--proc", "/proc",
                 "--chdir", str(cwd), "/bin/bash", "-o", "pipefail", "-c", command]
        return verifier_process(args, cwd, timeout, env, state, prefix)
    return subprocess.CompletedProcess([], 126, "", "no supported fail-closed verifier sandbox")


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
            candidates.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, UnicodeDecodeError):
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


# The role report contract (SF-16). A receipt's `summary` is the role's report. Its first line is
# the one line the controller reads, `VERDICT: <STATUS>`: the receipt status in capitals. Then a
# `## Summary` section of 3 to 5 bullets for a person. A maker report also has a section that
# lists each choice the maker made that the spec and ticket did not settle; it reaches the pull
# request and the inbox. The contract is the same for every client, so it lives in the prompt and
# in this lint rather than in the receipt schema, which Codex and Claude Code both enforce.
REPORT_VERDICTS = ("COMPLETED", "ACCEPTED", "REJECTED", "BLOCKED")
VERDICT_LINE = re.compile(r"VERDICT: (" + "|".join(REPORT_VERDICTS) + r")")
ASSUMPTIONS_HEADING = "## Assumptions without authority"
LATER_VERDICT = re.compile(r"\s*VERDICT\s*:")
REPORT_CONTRACT = (f"The summary is your report, in Markdown. Its first line is exactly `VERDICT: <STATUS>`, your "
                   f"status in capitals ({', '.join(REPORT_VERDICTS)}). Then a line `## Summary` and 3 to 5 bullets, "
                   "each starting with `- `.")
NO_ASSUMPTION = re.compile(r"none\.?", re.IGNORECASE)


HTML_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
FENCE = re.compile(r"\s{0,3}(`{3,}|~{3,})")


def report_visible_lines(summary: str) -> list[str]:
    """The lines after the verdict line that a rendered report shows as text: without HTML
    comments and without code blocks. An unclosed comment or block hides the rest of the report."""
    lines = summary.splitlines()
    visible: list[str] = []
    fence: str | None = None
    for line in HTML_COMMENT.sub("", "\n".join(lines[1:])).splitlines():
        opener = FENCE.match(line)
        if fence is None and opener:
            fence = opener.group(1)
        elif fence is not None:
            if opener and opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence) \
                    and not line.strip().strip(fence[0]):
                fence = None
        else:
            visible.append(line)
    return visible


def report_headings(summary: str) -> list[str]:
    """Every visible `## ` heading of a report, in order, repeats included."""
    return [line.rstrip() for line in report_visible_lines(summary) if line.startswith("## ")]


def report_sections(summary: str) -> dict[str, list[str]]:
    """The visible lines under each `## ` heading of a report, by heading."""
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in report_visible_lines(summary):
        if line.startswith("## "):
            current = sections.setdefault(line.rstrip(), [])
        elif current is not None:
            current.append(line.rstrip())
    return sections


def report_verdict(summary: str) -> str | None:
    """The verdict the report's first line states, or None when it has no verdict line."""
    first = summary.splitlines()[0].rstrip() if summary.splitlines() else ""
    match = VERDICT_LINE.fullmatch(first)
    return match.group(1) if match else None


def report_bullets(lines: list[str]) -> tuple[list[str], str | None]:
    """The bullets of one section, a continuation line joined to its bullet, or why it is not a list."""
    bullets: list[str] = []
    for line in lines:
        if line.startswith("- "):
            bullets.append(line[2:].strip())
        elif line[:1].isspace() and line.strip() and bullets:
            bullets[-1] += " " + line.strip()
        elif line.strip():
            return bullets, f"holds a line that is not a bullet: {line.strip()[:60]!r}"
    return bullets, None


def report_problem(summary: str, status: str, role: str) -> str | None:
    """Why a role report breaks the report contract, or None when it keeps it."""
    verdict = report_verdict(summary)
    if verdict is None:
        return "the report does not open with a verdict line (`VERDICT: <STATUS>`, for example `VERDICT: REJECTED`)"
    if verdict != status.upper():
        return f"the verdict line says {verdict}, but the receipt status is {status}"
    # The controller reads only the first line; a later one, anywhere, could tell a reader otherwise.
    if any(LATER_VERDICT.match(line) for line in summary.splitlines()[1:]):
        return "the report holds more than one verdict line: it needs exactly one verdict line, the first"
    sections = report_sections(summary)
    if "## Summary" not in sections:
        return "the report needs a `## Summary` section after the verdict line, outside code blocks and comments"
    headings = report_headings(summary)
    for heading in ("## Summary", ASSUMPTIONS_HEADING):
        if headings.count(heading) > 1:
            return f"the report needs exactly one `{heading}` section, not {headings.count(heading)}"
    bullets, problem = report_bullets(sections["## Summary"])
    if problem:
        return f"the `## Summary` section {problem}"
    if not 3 <= len(bullets) <= 5:
        return f"the `## Summary` section needs 3 to 5 bullets, not {len(bullets)}"
    if role == "maker":
        if ASSUMPTIONS_HEADING not in sections:
            return f"a maker report needs a `{ASSUMPTIONS_HEADING}` section"
        bullets, problem = report_bullets(sections[ASSUMPTIONS_HEADING])
        if problem or not bullets:
            return (f"the `{ASSUMPTIONS_HEADING}` section "
                    + (problem or "lists nothing: write one bullet per assumption, or `- none`"))
    return None


def report_headline(summary: str, limit: int = 200) -> str:
    """One bounded line of a report for a reason or a status line: its first summary bullet, else
    its first line that is not the verdict line. A reason must never carry a whole report."""
    bullets, _problem = report_bullets(report_sections(summary).get("## Summary", []))
    lines = [line for line in summary.splitlines() if line.strip() and not VERDICT_LINE.fullmatch(line.rstrip())]
    text = " ".join((bullets[0] if bullets and bullets[0] else lines[0] if lines else "").split())
    return (text if len(text) <= limit else text[:limit - 1] + "…") or "no reason given"


# A maker can write any amount; what a person reads is bounded. GitHub refuses a pull-request body
# over 65,536 characters, and 20 assumptions of 500 characters keep this section near 11,000.
ASSUMPTION_MAX_CHARS = 500
ASSUMPTIONS_MAX_ITEMS = 20
PR_BODY_MAX_CHARS = 65_536


def bounded_assumptions(items: list[str]) -> list[str]:
    """At most ASSUMPTIONS_MAX_ITEMS assumptions of at most ASSUMPTION_MAX_CHARS each, every cut marked."""
    shown = [item if len(item) <= ASSUMPTION_MAX_CHARS
             else item[:ASSUMPTION_MAX_CHARS] + f" … [cut at {ASSUMPTION_MAX_CHARS} characters]"
             for item in items[:ASSUMPTIONS_MAX_ITEMS]]
    if len(items) > ASSUMPTIONS_MAX_ITEMS:
        shown.append(f"{len(items) - ASSUMPTIONS_MAX_ITEMS} more assumptions are not shown; the maker's receipt "
                     "in the run folder holds them all")
    return shown


def report_assumptions(summary: str) -> list[str]:
    """What a maker report says it assumed without authority; `- none` and no section give []."""
    bullets, _problem = report_bullets(report_sections(summary).get(ASSUMPTIONS_HEADING, []))
    return [item for item in bullets if item and not NO_ASSUMPTION.fullmatch(item)]


def verifier_env() -> dict[str, str]:
    """The credential-free base. `sandboxed_verify` adds a private HOME, TMPDIR and XDG folders
    for each run of the verifier; a fixed shared home let a maker plant caches and config there."""
    allowed = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "SHELL")
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env.update({"CI": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/usr/bin/false"})
    return env


def effective_autocrlf(worktree: Path) -> str:
    """Pin the Git text conversion seen by the controller for a native role."""
    result = run(["git", "config", "--get", "core.autocrlf"], worktree)
    if result.returncode not in {0, 1}:
        raise RunError(f"cannot read core.autocrlf: {result.stderr.strip()}")
    value = result.stdout.strip().casefold() if result.returncode == 0 else "false"
    if value in {"true", "yes", "on", "1"}:
        return "true"
    if value in {"false", "no", "off", "0"}:
        return "false"
    if value == "input":
        return value
    raise RunError("core.autocrlf has an unsupported value")


@contextlib.contextmanager
def native_role_environment(runtime: str, worktree: Path):
    with native_environment(runtime) as environment:
        # The native-client allowlist strips arbitrary GIT_* variables. Pin the
        # controller's text conversion and suppress Git's automatic maintenance
        # while protected object-store snapshots bracket a native role. Git can
        # otherwise repack existing loose objects during an ordinary commit.
        environment.update({"GIT_CONFIG_COUNT": "3", "GIT_CONFIG_KEY_0": "core.autocrlf",
                            "GIT_CONFIG_VALUE_0": effective_autocrlf(worktree),
                            "GIT_CONFIG_KEY_1": "gc.auto", "GIT_CONFIG_VALUE_1": "0",
                            "GIT_CONFIG_KEY_2": "maintenance.auto", "GIT_CONFIG_VALUE_2": "false"})
        yield environment


def usage_metrics(stdout: str) -> tuple[float, int]:
    """Extract conservative per-invocation usage totals from Claude/Codex JSON output."""
    return shared_usage_metrics(stdout)


def require_native_role_sandbox() -> None:
    if sys.platform == 'darwin' and Path('/usr/bin/sandbox-exec').exists():
        return
    if sys.platform.startswith('linux') and shutil.which('bwrap'):
        return
    raise RunError('no supported fail-closed trusted-state sandbox; use macOS or Linux with bubblewrap')


def role_sandbox_probe(role: str, cwd: Path) -> list[str] | None:
    """A trivial command under the operating-system sandbox that both native clients use for
    shell commands (Seatbelt on macOS, bubblewrap on Linux), with the role's write access."""
    command = ["/bin/sh", "-c", "exit 0"]
    if sys.platform == "darwin":
        writes = f"(allow file-write* (subpath {json.dumps(str(cwd))}))" if role == "maker" else ""
        return ["/usr/bin/sandbox-exec", "-p",
                f"(version 1)(allow default)(deny network*)(deny file-write*){writes}", *command]
    if sys.platform.startswith("linux"):
        return ["bwrap", "--unshare-net", "--die-with-parent", "--ro-bind", "/", "/",
                "--bind" if role == "maker" else "--ro-bind", str(cwd), str(cwd),
                "--dev", "/dev", "--proc", "/proc", "--chdir", str(cwd), *command]
    return None  # native roles are refused on every other host


def preflight_sandboxes(repo: Path, manifest: dict[str, Any], *, verifier: bool = True) -> None:
    """Fail before any branch, worktree or model spend when a role or the verifier cannot run
    one command on this host, for example because host policy forbids a nested sandbox.

    This proves the sandbox starts; it does not prove a client's own tool policy. A graph
    probes the verifier once before dispatch and its children skip it (`verifier=False`)."""
    for role in ("maker", "checker"):
        probe = role_sandbox_probe(role, repo)
        if probe is None:
            continue
        runtime = manifest["roles"][role]["runtime"]
        try:
            result = run(probe, repo, timeout=30, env=minimal_environment())
        except subprocess.TimeoutExpired:
            result = subprocess.CompletedProcess(probe, 124, "", "timed out after 30 seconds")
        if result.returncode:
            detail = (result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}")
            raise RunError(f"{role} ({runtime}) cannot run a command in the operating-system sandbox "
                           f"on this host: {shown_paths([detail.splitlines()[-1][:300]])}")
    if verifier:
        preflight_verifier_sandbox()


def preflight_verifier_sandbox() -> None:
    """The verifier sandbox is a property of the host, not of one run. On Windows the probe is
    slow and holds a machine-wide ACL mutex, so a graph runs it once, not once per child."""
    # Probe the verifier in a throwaway repository: on Windows it writes its script, request and
    # result files into its working folder and grants that folder's ACLs, and in the shared
    # checkout those files made a parallel graph child see a dirty base.
    with tempfile.TemporaryDirectory(prefix="agentsmith-preflight-") as temporary:
        probe_repo = Path(temporary).resolve() / "probe"
        probe_repo.mkdir()
        initialized = run(["git", "init", "-q", str(probe_repo)], probe_repo)
        if initialized.returncode:
            raise RunError(f"cannot prepare the verifier sandbox probe: {initialized.stderr.strip()}")
        verify = sandboxed_verify("exit 0", probe_repo, 60, verifier_env())
    if verify.returncode:
        detail = verify.stderr.strip() or verify.stdout.strip()
        raise RunError(f"verifier sandbox cannot run a command on this host (exit {verify.returncode})"
                       + (f": {shown_paths([detail.splitlines()[-1][:300]])}" if detail else ""))


def trusted_paths(state: dict[str, Any]) -> list[Path]:
    repo = Path(state['repo'])
    runtime = Path(claude_sandbox_settings.__code__.co_filename).resolve()
    # Calibration receipts are controller evidence like run state. The folder must exist so that
    # every sandbox can name it.
    calibrations = state_root(repo).parent / "agentsmith-calibrations"
    calibrations.mkdir(exist_ok=True)
    factory = factory_root(repo)
    factory.mkdir(exist_ok=True)
    return [state_root(repo), calibrations, factory, Path(state['manifest_path']), repo / state['spec_path'],
            Path(__file__).resolve().parent, runtime.parent]


def process_group_is_live(pid: int) -> bool:
    if os.name == 'nt':
        return process_is_live(pid)
    members = subprocess.run(['ps', '-axo', 'pgid=,stat='], text=True,
                             capture_output=True, check=False)
    if members.returncode:
        raise RunError('cannot inspect previous role process group')
    return any(len(parts := line.split()) == 2 and parts[0] == str(pid) and not parts[1].startswith('Z')
               for line in members.stdout.splitlines())


def terminate_process_tree(pid: int) -> None:
    """Roles own a process group; terminate descendants as well as the client."""
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True, check=False)
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError:
        # macOS reports EPERM for a group containing only unreaped zombies; the stop handler
        # may already have ended the group before this cleanup runs.
        if process_group_is_live(pid):
            raise
        return
    # Kill surviving descendants even if the group leader already exited.
    time.sleep(0.1)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        # macOS reports EPERM for a group containing only unreaped zombies.
        if process_group_is_live(pid):
            raise


def archive_artifacts(directory: Path, prefix: str) -> None:
    artifacts = list(directory.glob(prefix + '*'))
    if artifacts:
        archive = directory / 'archive' / str(uuid.uuid4())
        archive.mkdir(parents=True)
        for artifact in artifacts:
            artifact.rename(archive / artifact.name)


def supervised_process(command: list[str], cwd: Path, timeout: int, env: dict[str, str],
                       state: dict[str, Any], prefix: str) -> tuple[subprocess.CompletedProcess[str], BaseException | None]:
    directory = Path(state['state_path']).parent
    stdout_path = directory / (prefix + '.stdout')
    stderr_path = directory / (prefix + '.stderr')
    error: BaseException | None = None
    with stdout_path.open('w', encoding='utf-8') as output, stderr_path.open('w', encoding='utf-8') as errors:
        process = subprocess.Popen(command, cwd=cwd, env=env, text=True,
                                   stdout=output, stderr=errors, start_new_session=os.name != 'nt')
        try:
            write_json(directory / (prefix + '-launch.json'),
                       {'pid': process.pid, 'process_group': process.pid if os.name != 'nt' else None,
                        'stage': state.get('stage'), 'started_at': now()})
            state['active_pid'] = process.pid
            save_state(state)
            # A stop that arrived before the handler could see this pid is caught here; one that
            # arrives later ends this process group through the handler.
            raise_if_stopped(directory)
            # Wait in short slices: a pending stop must also end a process that ignores the
            # handler's SIGTERM, and the cleanup below then kills its whole group.
            deadline = time.monotonic() + timeout
            while True:
                try:
                    process.wait(timeout=max(0.0, min(0.5, deadline - time.monotonic())))
                    break
                except subprocess.TimeoutExpired:
                    raise_if_stopped(directory)
                    if time.monotonic() >= deadline:
                        raise subprocess.TimeoutExpired(command, timeout) from None
        except BaseException as exc:
            error = exc
        finally:
            terminate_process_tree(process.pid)
            process.wait(timeout=10)
            write_json(directory / (prefix + '-exit.json'), {'exit_code': process.returncode})
            state['active_pid'] = None
            save_state(state)
    return subprocess.CompletedProcess(command, process.returncode,
                                       read_output(stdout_path), read_output(stderr_path)), error


def verifier_process(command: list[str], cwd: Path, timeout: int, env: dict[str, str],
                     state: dict[str, Any] | None, prefix: str | None = None) -> subprocess.CompletedProcess[str]:
    with contextlib.ExitStack() as stack:
        if state is None:
            temporary = stack.enter_context(tempfile.TemporaryDirectory(prefix='agentsmith-verifier-'))
            state = {'state_path': str(Path(temporary) / 'state.json'), 'attempt': 0}
        result, error = supervised_process(command, cwd, timeout, env, state,
                                           prefix or f"attempt-{state['attempt']}-verify")
        if isinstance(error, subprocess.TimeoutExpired):
            # A hung verifier is an incomplete attempt, not a failed run: keep what it printed.
            result.timed_out = True  # type: ignore[attr-defined]
            return result
        if error is not None:
            raise error
        if result.returncode:
            # A verifier that `stop` ended was interrupted; it did not fail verification.
            raise_if_stopped(Path(state['state_path']).parent)
        return result


def record_role_usage(state: dict[str, Any], runtime: str, role: str, stdout: str) -> None:
    cost, tokens = usage_metrics(stdout)
    if runtime == 'claude':
        state['claude_cost_usd'] = float(state.get('claude_cost_usd', 0.0)) + cost
        tokens = 0
    else:
        state['codex_tokens_used'] = int(state.get('codex_tokens_used', 0)) + tokens
        cost = 0.0
    state.pop('usage_pending', None)
    save_state(state, 'usage_recorded', role=role, runtime=runtime, cost_usd=cost, tokens=tokens)


def launch_role(state: dict[str, Any], manifest: dict[str, Any], role: str, prompt: str,
                *, role_worktree: Path | None = None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix='agentsmith-role-output-') as temporary:
        return launch_role_output(state, manifest, role, prompt, Path(temporary),
                                  role_worktree=role_worktree)


def launch_role_output(state: dict[str, Any], manifest: dict[str, Any], role: str, prompt: str,
                       exchange: Path, *, role_worktree: Path | None = None) -> dict[str, Any]:
    worktree = role_worktree or Path(state["worktree"])
    role_cfg = manifest["roles"][role]
    runtime = role_cfg["runtime"]
    run_dir = Path(state["state_path"]).parent
    raise_if_stopped(run_dir)
    archive_artifacts(run_dir, f"attempt-{state['attempt']}-{role}")
    receipt_path = exchange / 'receipt.json'
    schema_path = run_dir / "receipt-schema.json"
    write_json(schema_path, RECEIPT_SCHEMA)
    timeout = remaining_seconds(state, manifest)
    if timeout <= 0:
        raise RunError("wall-clock budget exhausted", reason="budget")
    common_git = state_root(Path(state["repo"])).parent
    maker_write_dirs = [common_git, resolved_git_path(worktree, '--git-dir')] if role == 'maker' else []
    protected = trusted_paths(state)
    cap = budget_cap(manifest["limits"], RUNTIME_BUDGETS[runtime][0])
    allowance = maker_allowance(state, manifest) if role == "maker" else None
    if allowance is not None and allowance <= 0:
        # Before the cap itself: what is left is the checker's, so a maker must not start.
        raise BudgetReserved(f"budget reserved for checking: the maker's share of limits."
                             f"{RUNTIME_BUDGETS[runtime][0]} is spent, and the rest is held for the checker")
    if runtime == "codex":
        # Codex has no documented hard token switch for `codex exec`, so this cap is enforced
        # here, before each Codex role, and after it (`budget_overrun`); the goal budget in the
        # maker prompt is advisory.
        if cap is not None and int(state.get("codex_tokens_used", 0)) >= cap:
            raise RunError("Codex run-wide token budget exhausted", reason="budget")
        cmd = build_native_command(
            "codex", prompt, worktree, schema_path, receipt_path,
            extra_write_dirs=maker_write_dirs, read_only=role == "checker",
            protected_write_paths=protected, hidden_read_paths=hidden_read_paths(manifest),
            model=str(role_cfg.get("model", "")), effort=str(role_cfg.get("effort", "")),
        )
    else:
        settings_path = run_dir / "claude-sandbox.json"
        write_json(
            settings_path,
            claude_sandbox_settings(
                worktree, maker_write_dirs, read_only=role == "checker",
                protected_write_paths=protected, hidden_read_paths=hidden_read_paths(manifest),
            ),
        )
        # Claude Code enforces the remaining allowance inside the role (`--max-budget-usd`).
        remaining_budget = None if cap is None else cap - float(state.get("claude_cost_usd", 0.0))
        if allowance is not None:
            remaining_budget = round(allowance, 6)  # a Claude maker stops at the checker's reserve
        if remaining_budget is not None and remaining_budget <= 0:
            raise RunError("Claude run-wide USD budget exhausted", reason="budget")
        cmd = build_native_command(
            "claude", prompt, worktree, schema_path, receipt_path, settings_path=settings_path,
            extra_write_dirs=maker_write_dirs, read_only=role == "checker",
            model=str(role_cfg.get("model", "")), effort=str(role_cfg.get("effort", "")),
            claude_max_usd=remaining_budget or 0.0,
        )
    event(state, "role_started", role=role, runtime=runtime, attempt=state["attempt"])
    prefix = f"attempt-{state['attempt']}-{role}"
    state['usage_pending'] = {'role': role, 'runtime': runtime, 'prefix': prefix}
    save_state(state)
    # The start of this launch, to find the role's own changes and commits (hidden-test runs only).
    before_head = git(worktree, "rev-parse", "HEAD") if hidden_read_paths(manifest) else ""
    with contextlib.ExitStack() as stack:
        environment = stack.enter_context(native_role_environment(runtime, worktree))
        if role == "checker":
            scratch = stack.enter_context(private_scratch("agentsmith-check-"))
            environment = checker_environment(environment, scratch)
        tripwire = stack.enter_context(hidden_tripwire(manifest))
        result, error = supervised_process(cmd, worktree, timeout, environment, state, prefix)
    stdout, stderr = result.stdout, result.stderr
    probed, saw_content = (probe_surfaces(tripwire, stdout + "\n" + stderr, receipt_path, worktree, before_head)
                           if tripwire is not None else ([], False))
    if probed:
        # The output may hold hidden test source, and later roles can read the run folder: keep
        # only its hash. The receipt is never saved; the canary dies with this launch.
        for stream, text in ((".stdout", stdout), (".stderr", stderr)):
            digest = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
            (run_dir / (prefix + stream)).write_text(
                f"withheld: this output showed an attempt to read the held-out acceptance tests "
                f"(sha256 {digest})\n", encoding="utf-8")
    denials = permission_denials(stdout) if runtime == "claude" else None
    write_json(run_dir / (prefix + '-exit.json'),
               {'role': role, 'runtime': runtime, 'exit_code': result.returncode,
                'model': role_cfg['model'], 'effort': role_cfg['effort'],
                **({'permission_denials': denials} if denials is not None else {})})
    record_role_usage(state, runtime, role, stdout)
    if probed:
        event(state, "hidden_test_probe", role=role, runtime=runtime, attempt=state["attempt"], surfaces=probed,
              content=saw_content)
        if error is not None and not isinstance(error, subprocess.TimeoutExpired):
            raise error  # an operator stop still wins; the probe is already on record
        raise HiddenTestProbe(role, probed, saw_content)
    if error is not None:
        if isinstance(error, subprocess.TimeoutExpired):
            raise RunError(f'{role} exceeded wall-clock budget', reason="budget") from error
        raise error
    # Each cap is checked after a role that spends it; the launch checks above refuse a role
    # whose own runtime has nothing left.
    over_budget = budget_overrun(state, manifest, runtime)
    receipt = None
    if not result.returncode:
        # Keep a finished role's receipt before enforcing a cap it crossed on the way.
        try:
            receipt = parse_receipt(receipt_path, stdout)
        except RunError:
            if over_budget is None:
                raise
        if receipt is not None:
            write_json(run_dir / f"attempt-{state['attempt']}-{role}-receipt.json", receipt)
            event(state, "role_completed", role=role, status=receipt["status"], attempt=state["attempt"])
    if over_budget:
        raise BudgetExceeded(over_budget, receipt)
    if result.returncode:
        if state.get("status") == "interrupted":
            raise RunInterrupted("stopped by operator")
        raise_if_stopped(run_dir)
        signature = infrastructure_signature(result.returncode, stdout, stderr)
        if signature is not None:
            raise InfrastructureFailure(f"{runtime} {role} exited {result.returncode} before a receipt "
                                        f"({signature})", signature)
        raise RunError(f"{runtime} {role} exited {result.returncode}: {stderr[-500:].strip()}")
    assert receipt is not None
    if role == "checker" and receipt["status"] == "accepted" and denials:
        # A read-only checker has no allowed use for an edit, a write, network or a connector, so
        # one denied call means its investigation left its contract: its acceptance is not used.
        # A rejection stays a rejection. Codex reports no denials, so this covers Claude only.
        raise InfrastructureFailure(f"claude checker accepted after {denials} denied tool call(s)",
                                    "permission-denials")
    return receipt


def permission_denials(stdout: str) -> int:
    """The denied tool calls Claude Code lists in its final result (`permission_denials`)."""
    count = 0
    for line in stdout.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("type") == "result" and isinstance(
                record.get("permission_denials"), list):
            count = len(record["permission_denials"])
    return count


# Known infrastructure failures of a role client, matched only against the client's stderr and
# its own error records (Codex `error`/`turn.failed` events, a Claude `result` with `is_error`),
# never against model or tool output. Anything else is an ordinary failure. Keep this list short
# and specific: a wrong match retries a role that should have stopped.
INFRASTRUCTURE_FAILURES = (
    ("sandbox-start", re.compile(r"sandbox_apply: Operation not permitted|^bwrap: ", re.MULTILINE)),
    ("client-panic", re.compile(r"thread '[^']*' panicked at")),
    ("network", re.compile(r"error sending request for url|stream disconnected before completion"
                           r"|ECONNRESET|ECONNREFUSED|ENOTFOUND|EAI_AGAIN|API Error: Connection error",
                           re.IGNORECASE)),
    ("authentication", re.compile(r"401 Unauthorized|Invalid API key|OAuth token has expired"
                                  r"|Please run /login|refresh token (?:was|has been|is) (?:revoked|expired|invalid)",
                                  re.IGNORECASE)),
    ("overloaded", re.compile(r"429 Too Many Requests|rate_limit_error|overloaded_error"
                              r"|API Error: 5\d\d", re.IGNORECASE)),
)
# The same signature twice in a row stops the run; so does this many failures in a row.
MAX_INFRASTRUCTURE_STREAK = 3


def client_error_text(stdout: str, stderr: str) -> str:
    """The client's own error reports: stderr, plus error records from its JSON output."""
    texts = [stderr]
    for line in stdout.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        if record.get("type") in {"error", "turn.failed"} or (
                record.get("type") == "result" and record.get("is_error") is True):
            texts.append(json.dumps(record, ensure_ascii=False))
    return "\n".join(texts)


def infrastructure_signature(returncode: int, stdout: str, stderr: str) -> str | None:
    if returncode < 0:
        return f"client-killed-by-signal-{-returncode}"
    text = client_error_text(stdout, stderr)
    return next((name for name, pattern in INFRASTRUCTURE_FAILURES if pattern.search(text)), None)


def launch_role_with_breaker(state: dict[str, Any], manifest: dict[str, Any], role: str, prompt: str,
                             *, retry_problem: Any = None, **kwargs: Any) -> dict[str, Any]:
    """Relaunch a role after a known infrastructure failure without spending an attempt. The
    same failure twice in a row, or MAX_INFRASTRUCTURE_STREAK failures in a row, stop the run."""
    while True:
        try:
            receipt = launch_role(state, manifest, role, prompt, **kwargs)
        except HiddenTestProbe as probe:
            # A probe is the role's own act, not a host fault: it ends any streak, never extends it.
            streak = state.pop("infrastructure_streak", None)
            if streak is not None:
                state.pop("repeat_attempt", None)
                save_state(state)
            if probe.content:
                # The role saw held-out content. Discarding its attempt cannot undo that, and the
                # hidden tests no longer measure this run: stop it for a person.
                raise RunError(f"{probe}; the hidden tests no longer give an honest signal for this run, so it "
                               "stops: review the run branch and replace the hidden tests before another run",
                               reason=HIDDEN_PROBE) from None
            raise
        except InfrastructureFailure as failure:
            streak = [*state.get("infrastructure_streak", []), failure.signature]
            state["infrastructure_streak"] = streak
            if role == "maker":
                # An infrastructure fault is never an attempt (SF-16). No maker finished, so
                # whichever way this ends, resume reruns this attempt instead of starting the next.
                state["repeat_attempt"] = True
            save_state(state, "infrastructure_failure", role=role, signature=failure.signature,
                       attempt=state["attempt"])
            if (len(streak) > 1 and streak[-1] == streak[-2]) or len(streak) >= MAX_INFRASTRUCTURE_STREAK:
                state["infrastructure_stop"] = failure.signature
                repeated = ("the same infrastructure failure twice in a row" if streak[-1] == streak[-2]
                            else f"{len(streak)} infrastructure failures in a row")
                advice = ("read why the checker tried denied actions in its log, then resume"
                          if failure.signature == "permission-denials"
                          else "fix the host, network or client sign-in, then resume")
                raise RunError(f"{repeated} ({failure.signature}) in the {role}: {failure}; no attempt "
                               f"was spent; {advice}") from failure
            problem = retry_problem() if retry_problem is not None else None
            if problem:
                raise RunError(f"{failure}; not relaunched because {problem}") from failure
            continue
        if state.pop("infrastructure_streak", None) is not None:
            # A relaunch finished this attempt: the next one is a new attempt again.
            state.pop("repeat_attempt", None)
            save_state(state)
        return receipt


# What a checker may cite: this attempt's verifier output log, plus files the verifier left in
# the disposable worktree (ignored by Git), each recorded by hash when the verifier finished.
MAX_EVIDENCE_FILES = 200
MAX_EVIDENCE_BYTES = 8 * 1024 * 1024
CITATION_FORM = "criterion :: file[:line] :: excerpt"
# A heuristic floor, not proof that the excerpt supports the criterion: it must hold at least
# this many visible characters besides the lines the harness itself writes into every log, and
# sit within this many lines of the cited line.
MIN_EXCERPT_CHARACTERS = 12
LINE_WINDOW = 2
HARNESS_LOG_TEXT = re.compile(r"exit=-?[0-9]+|STDOUT:|STDERR:")
VERIFY_LOG = re.compile(r"attempt-([0-9]+)-verify\.txt")


def verifier_evidence(verify_log: Path, checker_worktree: Path, ignored: set[str]) -> dict[str, str]:
    index = {verify_log.name: file_digest(verify_log)}
    for relative in sorted(ignored)[:MAX_EVIDENCE_FILES]:
        path = checker_worktree / relative
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_EVIDENCE_BYTES:
            index[relative] = file_digest(path)
    return index


def citation_problem(checker: dict[str, Any], index: dict[str, str], verify_log: Path,
                     checker_worktree: Path, attempt: int) -> str | None:
    """Why an accepting checker's evidence does not hold, or None. No model is involved: each
    evidence item must read `criterion :: file[:line] :: excerpt`, name a file this attempt's
    verifier produced, still match its recorded hash, and quote text that is in that file."""
    if not checker["evidence"]:
        return "checker accepted without citing any evidence"
    # Read every recorded file once. A verifier child that left its process group can still be
    # writing after the hashes were taken, so any recorded file that changed makes the checker's
    # view of the evidence unreliable, whether or not it was cited. The checks below use these
    # same bytes, so a write between hashing and quoting cannot supply a quote.
    contents: dict[str, bytes] = {}
    for name, digest in index.items():
        path = verify_log if name == verify_log.name else checker_worktree / name
        try:
            contents[name] = path.read_bytes()
        except OSError:
            return f"{name} can no longer be read; the verifier evidence changed after it finished"
        if hashlib.sha256(contents[name]).hexdigest() != digest:
            return f"{name} changed after the verifier finished; a verifier process may still have been writing"
    for number, item in enumerate(checker["evidence"], 1):
        shown = repr(item[:80])
        parts = item.split(" :: ", 2)
        if len(parts) != 3 or not parts[0].strip():
            return f"evidence item {number} ({shown}) is not '{CITATION_FORM}'"
        location, excerpt = parts[1].strip(), parts[2].strip()
        match = re.fullmatch(r"(.+?)(?::([1-9][0-9]{0,6}))?", location)
        name, line = (match.group(1), int(match.group(2)) if match.group(2) else None) if match else (location, None)
        if name not in index:
            other = VERIFY_LOG.fullmatch(name)
            if other and int(other.group(1)) != attempt:
                return f"evidence item {number} cites {name} from attempt {other.group(1)}, not this attempt ({attempt})"
            return f"evidence item {number} cites {shown_paths([name])}, which this attempt's verifier did not produce"
        data = contents[name]
        if len(re.sub(r"\s", "", HARNESS_LOG_TEXT.sub("", excerpt))) < MIN_EXCERPT_CHARACTERS:
            return (f"evidence item {number} quotes too little of {name}: an excerpt needs at least "
                    f"{MIN_EXCERPT_CHARACTERS} characters besides the log's exit, STDOUT and STDERR lines")
        text = data.decode("utf-8", errors="replace")
        if line is not None:
            lines = text.splitlines()
            if line > len(lines):
                return f"evidence item {number} cites line {line} of {name}, which has {len(lines)} lines"
            window = "\n".join(lines[max(0, line - 1 - LINE_WINDOW):line + LINE_WINDOW])
            if excerpt not in window:
                return (f"evidence item {number} quotes {excerpt[:60]!r}, which is not within "
                        f"{LINE_WINDOW} lines of line {line} of {name}")
        elif excerpt not in text:
            return f"evidence item {number} quotes {excerpt[:60]!r}, which is not in {name}"
    return None


def role_prompt(state: dict[str, Any], manifest: dict[str, Any], role: str,
                prior: dict[str, Any] | None = None, verify_output: str = "",
                evidence_files: list[str] | None = None) -> str:
    spec = manifest["spec_path"]
    scope = manifest["scope"]
    base = state["base_head"]
    common = f"""Run {state['run_id']} for implementation ticket {manifest['implementation_ticket']}.
Read the accepted terminal spec at {spec}. This ticket is separate from its decision ticket.
Allowed paths: {json.dumps(scope['allowed_paths'])}. Denied paths: {json.dumps(scope['denied_paths'])}.
No network, connectors, tracker writes, push, PR, merge, deployment, production action, or history rewrite.
Return only the requested JSON receipt. Never claim evidence you did not produce.
{REPORT_CONTRACT}
In changed_paths list every path printed by
`git -c core.quotepath=off diff --name-only --no-renames {base} HEAD`, as plain names without quotes.
A moved file counts twice: list the old path and the new path.
"""
    for reserved in state.get("sequence_numbers") or []:
        # Serialised with the graph's other runs on this folder: the number is free after them.
        common += (f"Numbered files: the next free number in {reserved['directory']}/ is {reserved['number']}. "
                   "A file this run adds there takes that number (then the ones after it), never one in use.\n")
    if role == "maker":
        feedback = f"\nThe prior checker rejected the attempt:\n{json.dumps(prior, indent=2)}\n" if prior else ""
        codex_maker = manifest["roles"]["maker"]["runtime"] == "codex"
        allowance = maker_allowance(state, manifest) if codex_maker else None
        goal_budget = 0 if allowance is None else int(allowance)
        goal = (f"If your runtime exposes the native goal tool, create a goal for this exact ticket with token budget "
                f"{goal_budget}; the manifest remains authoritative.\n") if goal_budget > 0 else ""
        note = rework_note(Path(state["repo"]), manifest) if state.get("repo") else None
        if note:
            goal += (f"This run is a rework of run {manifest['rework']['of']}. The operator's rework note:\n"
                     f"{note}\n")
        return common + goal + f"""Implement the smallest complete change, run {manifest['verify']['command']},
and make atomic local commits only. Leave the worktree clean. HEAD must advance beyond {base}.
Use status completed or blocked; do not mark your own work accepted.
After the summary bullets, add a line `{ASSUMPTIONS_HEADING}` with one bullet for each choice you made
that the spec and ticket did not settle, or the single bullet `- none`.{feedback}"""
    verify_log = f"attempt-{state.get('attempt')}-verify.txt"
    return common + f"""You are the independent checker and default to REJECT. Do not edit files or commit.
Inspect the committed diff from {base} to HEAD and the controller verification evidence.
Try to falsify the acceptance criteria using read-only commands. Also reject when either answer is no:
- Is this the smallest change that solves the stated problem? Name any part the spec does not need.
- Did each new red test fail for the intended reason? Check that it asserts on the failure message
  or value the bug produces, not on a stub, an import error or an earlier gate.
Controller verification output (the file {verify_log}):
{verify_output[-6000:]}
To accept, cite evidence for every criterion that passed. Write each evidence item exactly as
`{CITATION_FORM}`, where file is one of this attempt's verifier outputs:
{json.dumps(evidence_files or [verify_log])}
(files other than the output log are in your worktree), line is optional and counts from the
start of the file, and excerpt is text
copied exactly from that file, or from that line when you give one. The controller checks every
citation without a model; an acceptance whose citations do not hold is not trusted.
Use status accepted, rejected, or blocked."""


@contextlib.contextmanager
def checker_worktree_session(state: dict[str, Any], manifest: dict[str, Any],
                             worktree: Path, checker_head: str, checker_worktree: Path,
                             *, phase: str = "checker"):
    """Keep shared worktree-admin writes and checker inspection in one exclusive phase.

    The base-commit baseline only runs the verifier, so it takes the shared maker phase instead
    and does not wait for peer makers. It then adds and removes its worktree under the
    coordination lock, as `start` does, so a peer's metadata snapshot always sees the worktree
    together with the state entry that exempts it."""
    publish = (lambda: coordination_lock(state_root(worktree), interruptible=False)) if phase == "maker" \
        else contextlib.nullcontext
    with git_phase(worktree, phase, timeout_seconds=remaining_seconds(state, manifest), budget=True):
        with publish():
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
            yield checker_worktree
        finally:
            with publish():
                removed = run(["git", "worktree", "remove", "--force", str(checker_worktree)],
                              Path(state["repo"]))
                if removed.returncode:
                    event(state, "checker_worktree_cleanup_failed", path=str(checker_worktree),
                          error=removed.stderr.strip())
                    raise RunError(f"could not remove disposable checker worktree: {removed.stderr.strip()}")
                state.pop("checker_worktree", None)
                save_state(state)


def pending_candidate(state: dict[str, Any]) -> bool:
    return state.get('stage') in {'validating', 'verifying', 'checking'} and isinstance(state.get('maker_receipt'), dict)


def checkpoint_stage(state: dict[str, Any], stage: str) -> None:
    state['stage'] = stage
    save_state(state, 'stage_started', stage=stage, attempt=state['attempt'])
    # Act on a stop only once this checkpoint is durable, so resume keeps a finished role's
    # result. Not at `making`: resume would compare HEAD with the previous attempt's start.
    if stage != 'making':
        raise_if_stopped(Path(state['state_path']).parent)


def ensure_verification_baseline(state: dict[str, Any], manifest: dict[str, Any]) -> None:
    """Run the verify command once on the base commit, in a disposable worktree, and store the
    result with the run. A resumed run inherits it: the baseline is a fact about the base
    commit, so it is never taken again from a later tree. It is taken at the first verify stage,
    not before the first maker: the base commit cannot change, and on Windows every verifier
    call holds one machine-wide lock, so a baseline before the maker staggered parallel makers."""
    if isinstance(state.get("verification_baseline"), dict):
        return
    worktree = Path(state["worktree"])
    base = state["base_head"]
    run_dir = Path(state["state_path"]).parent
    with checker_worktree_session(state, manifest, worktree, base, worktree.with_name(f"{worktree.name}-baseline"),
                                  phase="maker") as baseline_worktree:
        archive_artifacts(run_dir, "baseline-verify")
        verify = sandboxed_verify(manifest["verify"]["command"], baseline_worktree,
                                  remaining_seconds(state, manifest), verifier_env(), state=state,
                                  prefix="baseline-verify")
    output_path = run_dir / "baseline-verify.txt"
    output_path.write_text(f"exit={verify.returncode}\nSTDOUT:\n{verify.stdout}\nSTDERR:\n{verify.stderr}",
                           encoding="utf-8")
    outcome = verification_outcome(verify)
    state["verification_baseline"] = {"commit": base, "exit_code": verify.returncode, **outcome,
                                      "output_sha256": file_digest(output_path)}
    save_state(state, "baseline_recorded", commit=base, verification=outcome["verification"],
               exit_code=verify.returncode)


def checker_report_defect(checker: dict[str, Any]) -> str | None:
    """An acceptance whose report breaks the report contract is a checker defect, like an
    acceptance whose citations do not hold."""
    broken = report_problem(checker["summary"], checker["status"], "checker")
    return f"the checker's report breaks the report contract: {broken}" if broken else None


def controller_rejection(commit: str, paths: list[str], reason: str) -> dict[str, Any]:
    """The feedback a maker gets when the controller rejects an attempt before any checker."""
    return {"status": "rejected", "summary": f"controller rejected the attempt: {reason}", "commit": commit,
            "changed_paths": paths, "evidence": [], "unresolved": [reason], "next_state": "retrying"}


def execute(state: dict[str, Any], manifest: dict[str, Any]) -> int:
    worktree = Path(state["worktree"])
    max_attempts = int(manifest["limits"]["max_attempts"])
    identical_limit, silent_limit = run_shape_limits(manifest["limits"])
    prior = state.get("last_checker_receipt")
    while state["attempt"] < max_attempts or pending_candidate(state) or state.get("repeat_attempt"):
        raise_if_stopped(Path(state["state_path"]).parent)
        if remaining_seconds(state, manifest) <= 0:
            raise RunError("wall-clock budget exhausted", reason="budget")
        if not pending_candidate(state) and not state.get("repeat_attempt"):
            streak, signature = identical_rejection_streak(state)
            if streak >= identical_limit:
                raise RunError(f"run-shape guard: {streak} identical rejections in a row ({signature}), "
                               f"limits.max_identical_rejections is {identical_limit}; another attempt would "
                               "repeat them, so a person should read the last rejection and the verify output")
        if not pending_candidate(state):
            if not state.pop("repeat_attempt", False):
                state["attempt"] += 1
            state["status"] = "making"
            # Resume rejects a `making` checkpoint whose start differs from HEAD. Save this
            # attempt's start with it, so a stop while the attempt waits for its Git phase
            # leaves a run that resumes. Only this run's maker moves its branch.
            state['maker_before_head'] = git(worktree, "rev-parse", "HEAD")
            checkpoint_stage(state, "making")
            with git_phase(worktree, "maker", timeout_seconds=remaining_seconds(state, manifest), budget=True):
                before_head = git(worktree, "rev-parse", "HEAD")
                # Start holds this same short lock while creating a branch/worktree
                # and publishing its state, so a snapshot cannot see half a peer.
                with coordination_lock(state_root(worktree)):
                    before_meta = git_metadata(worktree)
                before_ignored = ignored_paths(worktree)
                state['maker_before_head'] = before_head
                state['maker_before_meta'] = before_meta
                state['maker_before_ignored'] = sorted(before_ignored)
                state.pop('maker_receipt', None)
                state.pop('candidate_commit', None)
                save_state(state)
                maker_error: Exception | None = None
                maker: dict[str, Any] | None = None
                def maker_retry_problem() -> str | None:
                    # Relaunch only from the same clean start; anything else needs a person.
                    if git(worktree, "rev-parse", "HEAD") != before_head or not clean(worktree):
                        return "the failed maker changed the worktree"
                    return None

                try:
                    maker = launch_role_with_breaker(state, manifest, "maker",
                                                     role_prompt(state, manifest, "maker", prior),
                                                     retry_problem=maker_retry_problem)
                except Exception as exc:
                    maker_error = exc
                after_head = git(worktree, "rev-parse", "HEAD")
                with coordination_lock(state_root(worktree)):
                    after_meta = git_metadata(worktree, known_peers=before_meta["registered_peers"])
                validate_git_transition(worktree, before_meta, after_meta, state["branch"],
                                        before_head, after_head)
            if isinstance(maker_error, HiddenTestProbe):
                # Only the tripwire's name showed: the sandbox held, so the attempt fails and its
                # commits stay, as after any rejection. A content leak already stopped the run.
                prior = probed_attempt(state, maker_error, after_head, changed_paths(worktree, state["base_head"]))
                continue
            if isinstance(maker_error, BudgetExceeded) and maker_error.receipt is not None:
                # The maker finished but crossed a cap: checkpoint its candidate before the
                # escalation, so resume can verify and check it instead of discarding it.
                state['maker_receipt'] = maker_error.receipt
                state['candidate_commit'] = after_head
                state['stage'] = 'validating'
                save_state(state, 'candidate_checkpointed', stage='validating',
                           attempt=state['attempt'], reason=str(maker_error))
            if maker_error:
                raise maker_error
            state['maker_receipt'] = maker
            state['candidate_commit'] = after_head
            checkpoint_stage(state, 'validating')
        else:
            maker = state['maker_receipt']
            before_head = state['maker_before_head']
            before_meta = state['maker_before_meta']
            before_ignored = set(state['maker_before_ignored'])
            after_head = git(worktree, 'rev-parse', 'HEAD')
            if after_head != state['candidate_commit']:
                raise RunError('candidate changed since stage checkpoint; operator review required', reason="stale")
            with git_phase(worktree, 'maker', timeout_seconds=remaining_seconds(state, manifest), budget=True):
                with coordination_lock(state_root(worktree)):
                    after_meta = git_metadata(worktree, known_peers=before_meta['registered_peers'])
                before_meta = json.loads(json.dumps(before_meta))
                after_meta = json.loads(json.dumps(after_meta))
                validate_git_transition(worktree, before_meta, after_meta, state['branch'], before_head, after_head)
        assert maker is not None
        if maker["status"] == "blocked":
            raise RunError(f"maker blocked: {report_headline(maker['summary'])}")
        if after_head == before_head:
            raise RunError("maker completed without creating a local commit")
        if not clean(worktree):
            raise RunError("maker left the worktree dirty")
        paths = changed_paths(worktree, state["base_head"])
        bad = [path for path in paths if not path_allowed(path, manifest)]
        if bad:
            raise RunError(f"maker changed paths outside scope: {shown_paths(bad)}", reason="scope")
        # Every commit counts: a file added in one commit and deleted in a later one is not in the
        # end-to-end diff, but the history that would be pushed still carries it.
        for path, commit in history_paths(worktree, state["base_head"], after_head).items():
            if not path_allowed(path, manifest):
                raise RunError(f"maker changed paths outside scope in commit {commit[:12]}: {shown_paths([path])}",
                               reason="scope")
        ignored_added = sorted(ignored_paths(worktree) - before_ignored)
        ignored_bad = [path for path in ignored_added if not path_allowed(path, manifest)]
        if ignored_bad:
            raise RunError(f"maker created ignored paths outside scope: {shown_paths(ignored_bad)}", reason="scope")
        if maker["commit"] != after_head or sorted(maker["changed_paths"]) != sorted(paths):
            raise RunError("maker receipt does not match the committed Git state")
        broken = report_problem(maker["summary"], maker["status"], "maker")
        if broken:
            # The report is what the controller and the inbox read: an attempt without one fails
            # here, before a verifier or a checker is spent on it, and the next maker learns why.
            prior = controller_rejection(after_head, paths, broken)
            prior["summary"] = "controller rejected the attempt: the maker's report breaks the report contract"
            state["last_checker_receipt"] = prior
            state["status"] = "retrying"
            state['stage'] = 'retrying'
            save_state(state, "attempt_rejected", attempt=state["attempt"], reason="report contract")
            continue
        validate_verification_changes(worktree, state["base_head"], after_head, manifest)
        silent = silent_turn_streak(state, worktree, before_head, after_head)
        if silent >= silent_limit:
            turns = "turn" if silent == 1 else "turns"
            raise RunError(f"run-shape guard: {silent} silent maker {turns} in a row: the candidate tree is "
                           f"the tree last judged, limits.max_silent_turns is {silent_limit}; nothing new "
                           "to verify or check, so a person should read why the maker changed nothing")
        state["status"] = "checking"
        checkpoint_stage(state, 'verifying')
        # Read the candidate before the baseline: a commit that lands while the baseline runs was
        # never validated, so it must not become the checked commit (acceptance then refuses it).
        checker_head = git(worktree, "rev-parse", "HEAD")
        ensure_verification_baseline(state, manifest)
        checker_worktree = worktree.with_name(f"{worktree.name}-check-{state['attempt']}")
        with checker_worktree_session(state, manifest, worktree, checker_head, checker_worktree):
            archive_artifacts(Path(state['state_path']).parent, f"attempt-{state['attempt']}-verify")
            verify = sandboxed_verify(manifest["verify"]["command"], checker_worktree,
                                      remaining_seconds(state, manifest), verifier_env(), state=state)
            verify_output = f"exit={verify.returncode}\nSTDOUT:\n{verify.stdout}\nSTDERR:\n{verify.stderr}"
            verify_path = Path(state["state_path"]).parent / f"attempt-{state['attempt']}-verify.txt"
            verify_path.write_text(verify_output, encoding="utf-8")
            outcome = verification_outcome(verify)
            baseline = state.get("verification_baseline") or {}
            regressed = regressions(baseline, outcome)
            proof = verification_binding(state, manifest, checker_head)
            proof.update(exit_code=verify.returncode, output_sha256=file_digest(verify_path),
                         verification=outcome["verification"], verification_reason=outcome["reason"],
                         baseline_commit=baseline.get("commit"),
                         baseline_verification=baseline.get("verification"), regressions=regressed)
            proof_path = verify_path.with_suffix(".json")
            write_json(proof_path, proof)
            state["verification_receipt"] = str(proof_path)
            save_state(state)
            checkpoint_stage(state, 'checking')
            checker_status = git(checker_worktree, "status", "--porcelain")
            if checker_status:
                raise RunError("verifier modified tracked state")
            # The checker reads the controller's verdict first; the raw output follows it.
            verify_output = (f"verification={outcome['verification']}"
                             + (f" ({outcome['reason']})" if outcome["reason"] else "")
                             + f"\nbaseline on {baseline.get('commit')}: {baseline.get('verification')}"
                             + f"\nregressions against the baseline (passed there, fail now): {json.dumps(regressed)}"
                             + f"\n{verify_output}")
            if outcome["verification"] == "incomplete":
                # Nothing was observed, so no checker can accept it: reject without spending one.
                # Leaving the block removes the disposable worktree as usual.
                prior = controller_rejection(checker_head, paths, f"verification incomplete: {outcome['reason']}")
                state["last_checker_receipt"] = prior
                state["status"] = "retrying"
                state['stage'] = 'retrying'
                save_state(state, "attempt_rejected", attempt=state["attempt"], reason="incomplete",
                           verify_exit=verify.returncode, verification="incomplete", regressions=regressed)
                continue
            checker_ignored = ignored_paths(checker_worktree)
            evidence = verifier_evidence(verify_path, checker_worktree, checker_ignored)
            proof["evidence_files"] = evidence
            hidden_failed = False
            if verify.returncode == 0 and manifest.get("hidden_tests") is not None:
                proof["hidden_tests"] = run_hidden_tests(state, manifest, checker_head)
                hidden_failed = proof["hidden_tests"]["status"] == "fail"
            write_json(proof_path, proof)
            checker_meta = git_metadata(checker_worktree)
            checker_error: Exception | None = None
            checker: dict[str, Any] | None = None
            checker_probe: HiddenTestProbe | None = None
            try:
                if hidden_failed:
                    # Hidden tests only reject. The maker learns that they failed and nothing else;
                    # no checker is spent on a candidate they rejected.
                    event(state, "hidden_tests_failed", attempt=state["attempt"])
                    raise HiddenTestsRejected()
                checker = launch_role_with_breaker(
                    state, manifest, "checker",
                    role_prompt(state, manifest, "checker", verify_output=verify_output,
                                evidence_files=sorted(evidence)),
                    role_worktree=checker_worktree)
            except HiddenTestsRejected:
                checker = {"status": "rejected", "summary": "hidden acceptance tests failed", "commit": checker_head,
                           "changed_paths": paths, "evidence": [], "unresolved": [HIDDEN_HINT],
                           "next_state": "rejected"}
            except HiddenTestProbe as probe:
                # Its verdict is not used; the attempt fails and the next maker learns why.
                checker_probe = probe
                checker = {"status": "rejected", "summary": "the checker tried to read the held-out acceptance tests",
                           "commit": checker_head, "changed_paths": paths, "evidence": [],
                           "unresolved": [probe_hint("checker")], "next_state": "rejected"}
            except Exception as exc:
                checker_error = exc
            validate_git_unchanged(
                checker_meta,
                git_metadata(checker_worktree, known_peers=checker_meta["registered_peers"]),
                "checker",
            )
            if (git(checker_worktree, "rev-parse", "HEAD") != checker_head or
                    git(checker_worktree, "status", "--porcelain") != checker_status or
                    ignored_paths(checker_worktree) != checker_ignored):
                raise RunError("checker modified its disposable worktree")
            if checker_error:
                raise checker_error
            assert checker is not None
            if checker["commit"] != checker_head or sorted(checker["changed_paths"]) != sorted(paths):
                raise RunError("checker receipt does not match the committed Git state")
            proof["checker_receipt_sha256"] = (None if hidden_failed or checker_probe else file_digest(
                Path(state["state_path"]).parent / f"attempt-{state['attempt']}-checker-receipt.json"))
            proof["checker_status"] = ("not run: hidden acceptance tests failed" if hidden_failed
                                       else f"not used: {HIDDEN_PROBE}" if checker_probe else checker["status"])
            # Every acceptance that would otherwise count is checked, including one with no or only
            # blank evidence: that is a checker defect with rework feedback, not a plain rejection.
            claims_acceptance = (verify.returncode == 0 and checker["status"] == "accepted"
                                 and not checker["unresolved"])
            defect = ((checker_report_defect(checker)
                       or citation_problem(checker, evidence, verify_path, checker_worktree, state["attempt"]))
                      if claims_acceptance else None)
            if defect:
                proof["checker_defect"] = defect
            elif claims_acceptance:
                proof["citations"] = "valid"  # what `deliver` requires before it prints a push command
                if outcome["verification"] == "passed" and not regressed:
                    demo = record_demo(state, manifest, checker_worktree, checker_head)
                    if demo is not None:
                        proof["demo"] = state["demo"] = demo
            write_json(proof_path, proof)
        if defect:
            # An acceptance whose evidence does not hold is a checker defect, not an acceptance:
            # the attempt is reworked like a rejection, and the next maker is told why.
            event(state, "checker_defect", attempt=state["attempt"], reason=defect)
            checker = {**checker, "status": "rejected", "unresolved": [
                *checker["unresolved"], f"the checker's acceptance was not trusted: {defect}"]}
        # Every condition applies: the verification passed against the base-commit baseline with no
        # regression, and then a trusted checker acceptance.
        if outcome["verification"] == "passed" and not regressed and acceptance_ready(verify.returncode, checker):
            # A stop that arrived before the acceptance record still interrupts the run.
            raise_if_stopped(Path(state["state_path"]).parent)
            risk = risk_record(worktree, state["base_head"], checker_head, manifest.get("risk_tier"))
            proof["risk"] = risk
            write_json(proof_path, proof)
            state["risk"] = risk
            # The last step before the record: the branch must still be the checked commit.
            moved = candidate_moved(worktree, state["branch"], checker_head)
            if moved:
                raise RunError(moved, reason="stale")
            # Last: the checker gates only while a calibration of it passes (SF-09). Otherwise its
            # acceptance is advice, and the candidate waits for a person instead of being accepted.
            # The calibration is read again here: the receipt's copy predates the checker, and the
            # record may have changed while the checker ran.
            proof["checker_calibration"] = checker_calibration(state, manifest)
            calibration = str(proof["checker_calibration"].get("status") or "none")
            proof["checker_advisory"] = calibration != "passed"
            write_json(proof_path, proof)
            # A stop that arrived up to the last receipt write still interrupts the run.
            raise_if_stopped(Path(state["state_path"]).parent)
            if proof["checker_advisory"]:
                state["status"] = "awaiting-human"
                state["stage"] = "awaiting-human"
                state["held_commit"] = checker_head
                state["last_checker_receipt"] = checker
                state["reason"] = (f"checker advisory: calibration {calibration}; the checker accepted "
                                   f"{checker_head[:12]}, but only a passed calibration lets it gate")
                save_state(state, "run_awaiting_human", commit=checker_head, calibration=calibration)
                print(f"awaiting a human: {state['branch']} at {checker_head}; {state['reason']}")
                print(f"next: {AWAITING_HUMAN_NEXT}")
                print("nothing was pushed, merged, or written to an external system")
                return 3
            state["status"] = "accepted"
            state['stage'] = 'accepted'
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
        state['stage'] = 'retrying'
        # The first cause that holds: a probe voids the checker, hidden tests ran only on a passing
        # verify, and a failed or regressed verify outranks the checker's own verdict.
        reason = (HIDDEN_PROBE if checker_probe else "hidden-tests" if hidden_failed
                  else "verify" if verify.returncode or outcome["verification"] != "passed" or regressed
                  else "checker")
        save_state(state, "attempt_rejected", attempt=state["attempt"], reason=reason, verify_exit=verify.returncode,
                   verification=outcome["verification"], regressions=regressed,
                   **({"role": "checker"} if checker_probe else {}))
    # As with acceptance, a stop that arrived before this record still interrupts the run.
    raise_if_stopped(Path(state["state_path"]).parent)
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
    global _stop_signal_received
    previous = signal.getsignal(signal.SIGTERM)
    _stop_signal_received = False

    def interrupted(_signum: int, _frame: Any) -> None:
        # Record the stop and end the active role; the controller raises RunInterrupted at its
        # next safe point. Never raise here (see `_stop_signal_received`). A run that has
        # already recorded its result keeps it; a late stop changes nothing.
        global _stop_signal_received
        if state.get("status") in TERMINAL_RUN_STATUSES:
            return
        _stop_signal_received = True
        active_pid = state.get("active_pid")
        if active_pid and os.name != "nt":
            try:
                os.killpg(int(active_pid), signal.SIGTERM)
            except (OSError, ValueError):
                pass

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
        rejection = getattr(exc, "reason", None)
        if rejection:
            # A stop that rejects the attempt is a rejection too: its cause is counted with the rest.
            event(state, "attempt_rejected", attempt=state.get("attempt"), reason=rejection, escalated=True)
        save_state(state, "run_escalated", reason=str(exc))
        print(f"escalated: {exc}", file=sys.stderr)
        return 2
    finally:
        if state.get("status") in TERMINAL_RUN_STATUSES:
            terminal_head = git(Path(state["worktree"]), "rev-parse", "HEAD", check=False)
            if re.fullmatch(r"[0-9a-f]{40,64}", terminal_head):
                state["terminal_head"] = terminal_head
                save_state(state)
            # The caller still releases the lifecycle lock. Keep the handler, which now ignores
            # a late stop, rather than restore a default action that would end the process.
        else:
            signal.signal(signal.SIGTERM, previous)
        _stop_signal_received = False


def start(args: argparse.Namespace) -> int:
    repo = repo_root(Path.cwd())
    assert_autonomy_not_paused(repo, action="start", run_id=Path(args.manifest).stem)
    manifest_path = Path(args.manifest).resolve()
    manifest = load_json(manifest_path)
    if not args.graph:
        # A graph child belongs to a graph the operator already started as one unit; the budget gates
        # the graph's own manifests at prepare, not each child as the graph dispatches it.
        rework = manifest.get("rework")
        assert_attention_budget(repo, rework.get("of") if isinstance(rework, dict) else None,
                                str(manifest.get("base_ref") or "HEAD"))
    spec_rel, spec_hash = validate_manifest(manifest, repo)
    # The demo command comes from the spec that was just validated, never from a role.
    spec_text = git(repo, "show", f"{manifest['base_ref']}:{spec_rel.as_posix()}")
    if hashlib.sha256(spec_text.encode()).hexdigest() != spec_hash:
        raise RunError("the accepted spec changed while the run was starting")
    demo_command = spec_demo_command(spec_text)
    if not clean(repo):
        raise RunError("base worktree must be clean before an autonomous run starts")
    try:
        manifest_rel = manifest_path.relative_to(repo)
    except ValueError as exc:
        raise RunError("run manifest must live inside the repository") from exc
    tracked = run(["git", "ls-files", "--error-unmatch", str(manifest_rel)], repo)
    if tracked.returncode:
        raise RunError("run manifest must be committed before start")
    require_native_role_sandbox()
    # A graph child shares its host with siblings that start at the same moment; the graph has
    # already probed the verifier, and a per-child probe would serialise the roots on Windows.
    preflight_sandboxes(repo, manifest, verifier=not args.graph)
    name = str(manifest["run_id"])
    path = state_path(repo, name)
    if path.exists():
        raise RunError(f"run {name} already exists; use resume or choose another run_id")
    if bool(args.graph) != bool(args.effective_base):
        raise RunError("--graph and --effective-base must be supplied together")
    token: str | None = None
    try:
        with git_phase(repo, "maker"), coordination_lock(state_root(repo)):
            token = acquire_lifecycle_lock(path.parent, name)
            if path.exists():
                raise RunError(f"run {name} already exists; use resume or choose another run_id")
            assert_no_live_scope_conflicts(repo, name, manifest["scope"])
            graph_context = (graph_effective_base(repo, args.graph, manifest_path, manifest,
                                                   spec_rel, spec_hash, args.effective_base)
                             if args.graph else {})
            base_head = (graph_context["effective_base_oid"] if graph_context
                         else git(repo, "rev-parse", str(manifest["base_ref"])))
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
                **graph_context,
                "spec_path": spec_rel.as_posix(),
                "spec_sha256": spec_hash,
                **({"demo_command": demo_command} if demo_command else {}),
                "manifest_path": str(manifest_path),
                "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "scope": normalized_scope(manifest["scope"]),
                "started_at": now(),
                "started_epoch": time.time(),
                "deadline_epoch": time.time() + int(manifest["limits"]["wall_minutes"]) * 60,
                "claude_cost_usd": 0.0,
                "codex_tokens_used": 0,
                "budget_rationale": manifest["limits"].get("budget_rationale") or None,
                "active_pid": None,
                "controller_pid": os.getpid(),
                "controller_token": token,
                "state_path": str(path),
            }
            save_state(state, "run_started", branch=branch, worktree=str(worktree))
            keep_operator_feedback(state, manifest)
        return run_controller(state, manifest)
    finally:
        if token is not None:
            release_lifecycle_lock(path.parent, token)
            if not path.exists():
                try:
                    path.parent.rmdir()
                except OSError:
                    pass


UNFINISHED_RUN_STATUSES = {"prepared", "making", "checking", "retrying", "resuming"}
TERMINAL_GRAPH_STATUSES = {"completed", "failed", "stopped", "blocked"}
UNFINISHED_GRAPH_STATUSES = {"prepared", "running"}
# What the controller keeps beside run folders in agentsmith-runs.
RUN_ROOT_FILES = {"coordination.lock"}
RUN_ROOT_FOLDERS = {"git-phases", "graph-stop"}


def _real_directory(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink()


def _real_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def live_work(repo: Path, accepted: list[str] | None = None) -> tuple[list[str], list[str]]:
    """Read-only scan of every run and graph sharing this repository's Git metadata.

    Returns (live, undetermined). Linked worktrees share refs and worktree administration, so
    a `git worktree remove` or branch delete anywhere can break a run that is not terminal.
    Only shapes the controller writes and statuses it knows count; anything else is
    undetermined, because the guard must prove "terminal", not assume it."""
    live: list[str] = []
    unknown: list[str] = []
    common = resolved_git_path(repo, "--git-common-dir")
    for root in (common / "agentsmith-runs", common / "agentsmith-graphs"):
        if (root.exists() or root.is_symlink()) and not _real_directory(root):
            unknown.append(f"{root.name}: not a plain folder")
    runs = common / "agentsmith-runs"
    for entry in sorted(runs.iterdir() if _real_directory(runs) else []):
        name = entry.name
        if name in RUN_ROOT_FILES and _real_file(entry):
            continue
        if name in RUN_ROOT_FOLDERS and _real_directory(entry):
            continue
        if not _real_directory(entry):
            unknown.append(f"run {name}: not a plain run folder")
            continue
        try:
            lock = entry / "controller.lock"
            if lock.is_symlink():
                raise RunError("lifecycle lock is a symbolic link")
            owner = read_lock(entry)
            owner_live = owner is not None and process_is_live(owner["pid"])
            state_file = entry / "state.json"
            if not state_file.exists() and not state_file.is_symlink():
                if owner_live:
                    live.append(f"run {name}: starting (controller {owner['pid']})")
                elif any(entry.iterdir()):
                    unknown.append(f"run {name}: files but no state; inspect it")
                continue
            if not _real_file(state_file):
                raise RunError("state.json is not a regular file")
            state = load_json(state_file)
        except (OSError, ValueError, RunError) as exc:  # ValueError: undecodable text
            unknown.append(f"run {name}: cannot read its state or lock: {exc}")
            continue
        status = state.get("status")
        if owner_live:
            live.append(f"run {name}: {status} (controller {owner['pid']} is live)")
        elif state.get("active_pid") and process_is_live(state["active_pid"]):
            live.append(f"run {name}: {status} (role process {state['active_pid']} is live)")
        elif status in UNFINISHED_RUN_STATUSES:
            live.append(f"run {name}: {status} with no live controller; resume or inspect it first")
        elif status not in TERMINAL_RUN_STATUSES:
            unknown.append(f"run {name}: unrecognized status {status!r}")
        elif status == "accepted" and accepted is not None:
            risk = state.get("risk") if isinstance(state.get("risk"), dict) else {}
            accepted.append(f"run {name}: accepted at {state.get('accepted_commit')}, "
                            f"risk tier {risk.get('tier', 'not recorded')}")
    graphs = common / "agentsmith-graphs"
    for entry in sorted(graphs.iterdir() if _real_directory(graphs) else []):
        name = entry.name
        if not _real_directory(entry):
            unknown.append(f"graph {name}: not a plain graph folder")
            continue
        try:
            owner = None
            lock = entry / "LOCK"
            if lock.exists() or lock.is_symlink():
                if not _real_file(lock):
                    raise RunError("LOCK is not a regular file")
                owner = json.loads(read_text(lock))
                if not isinstance(owner, dict) or not isinstance(owner.get("pid"), int):
                    raise RunError("malformed graph lock owner")
            state_file = entry / "state.json"
            if not state_file.exists() and not state_file.is_symlink() and owner is None \
                    and not any(entry.iterdir()):
                continue
            if not _real_file(state_file):
                raise RunError("state.json is missing or not a regular file")
            state = load_json(state_file)
        except (OSError, ValueError, RunError) as exc:  # ValueError: undecodable text or JSON
            unknown.append(f"graph {name}: cannot read its state or lock: {exc}")
            continue
        status = state.get("status")
        if owner is not None and process_is_live(owner["pid"]):
            live.append(f"graph {name}: {status} (controller {owner['pid']} is live)")
        elif status in UNFINISHED_GRAPH_STATUSES:
            live.append(f"graph {name}: {status} with no live controller; resume or inspect it first")
        elif status not in TERMINAL_GRAPH_STATUSES:
            unknown.append(f"graph {name}: unrecognized status {status!r}")
    return live, unknown


def all_terminal(repo: Path) -> int:
    """0: every run and graph is terminal. 1: something is live or not terminal. 2: cannot tell."""
    accepted: list[str] = []
    try:
        live, unknown = live_work(repo, accepted)
    except (OSError, ValueError, RunError) as exc:
        print(f"cannot tell whether autonomous work is live: {exc}")
        return 2
    for line in [*accepted, *unknown, *live]:
        print(line)
    if unknown:
        print("cannot tell whether every autonomous run is terminal; do not change Git metadata")
        return 2
    if live:
        print("autonomous work is not terminal; do not change Git metadata yet")
        return 1
    print("every autonomous run and graph in this repository is terminal")
    return 0


def status_cmd(args: argparse.Namespace) -> int:
    repo = repo_root(Path.cwd())
    if args.all_terminal:
        if args.run_id:
            raise RunError("status takes either a run id or --all-terminal, not both")
        return all_terminal(repo)
    if not args.run_id:
        raise RunError("status needs a run id, or --all-terminal for the live-run guard")
    state = load_run(repo, args.run_id)
    keys = ["run_id", "status", "stage", "attempt", "active_pid", "branch", "worktree", "base_head",
            "accepted_commit", "held_commit", "deadline_epoch", "claude_cost_usd", "codex_tokens_used",
            "budget_rationale", "usage_accounting_incomplete", "reason", "updated_at"]
    view = {key: state.get(key) for key in keys if state.get(key) is not None}
    if isinstance(state.get("risk"), dict):
        view["risk_tier"] = state["risk"].get("tier")  # report-only: it decides nothing yet
    baseline = state.get("verification_baseline")
    if isinstance(baseline, dict):
        # What every attempt is compared with: a check passing here and failing later regressed.
        view["verification_baseline"] = {key: baseline[key] for key in
                                         ("commit", "verification", "exit_code", "reason", "passing", "failing")
                                         if baseline.get(key) is not None}
    print(json.dumps(view, indent=2))
    return 0


def stop(args: argparse.Namespace) -> int:
    repo = repo_root(Path.cwd())
    state = load_run(repo, args.run_id)
    run_dir = Path(state["state_path"]).parent
    create_stop_request(run_dir)
    active_pid = state.get("active_pid")
    if active_pid:
        try:
            terminate_process_tree(int(active_pid))
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
    elif current.get("status") in {"accepted", "awaiting-human", "escalated"}:
        print(f"{args.run_id} already finished as {current['status']}; the stop changed nothing")
    elif not controller_pid or not process_is_live(controller_pid):
        print(f"stop requested for {args.run_id}; controller is gone and resume will reconcile it")
    else:
        print(f"stop requested for {args.run_id}; controller did not persist interruption within five seconds")
    return 0


def clear_abandoned_checker_entry(repo: Path, checker: Path) -> None:
    """Finish a checker removal that was stopped after its folder was deleted.

    `git worktree remove` deletes the folder before its entry under .git/worktrees. Remove only
    that entry, by the rule `git worktree prune` applies: not locked, and its gitdir file is
    missing or names the missing folder. An entry another worktree owns stays untouched.
    """
    entry = resolved_git_path(repo, '--git-common-dir') / 'worktrees' / checker.name
    if entry.is_symlink() or not entry.is_dir() or (entry / 'locked').exists():
        return
    gitdir = entry / 'gitdir'
    if gitdir.exists():
        try:
            target = Path(gitdir.read_text(encoding='utf-8').strip())
        except (OSError, UnicodeError):
            return
        if target.resolve() != (checker / '.git').resolve():
            return
    shutil.rmtree(entry)


def recover_checker_worktree(state: dict[str, Any], manifest: dict[str, Any]) -> None:
    if not state.get('checker_worktree'):
        return
    repo = Path(state['repo'])
    worktree = Path(state['worktree'])
    with git_phase(repo, 'writer', timeout_seconds=remaining_seconds(state, manifest), budget=True):
        abandoned = state.get('checker_worktree')
        if abandoned:
            expected = worktree.with_name(f"{worktree.name}-check-{state['attempt']}")
            if Path(abandoned) != expected:
                raise RunError('unrecognized checker recovery path')
            if expected.exists():
                if resolved_git_path(expected, '--git-common-dir') != resolved_git_path(repo, '--git-common-dir'):
                    raise RunError('checker recovery worktree belongs to another repository')
                if git(expected, 'rev-parse', 'HEAD') != state.get('candidate_commit'):
                    raise RunError('checker recovery candidate changed; operator review required')
                removed = run(['git', 'worktree', 'remove', '--force', str(expected)], repo)
                if removed.returncode:
                    raise RunError('cannot clean up interrupted checker worktree')
            else:
                clear_abandoned_checker_entry(repo, expected)
            state.pop('checker_worktree', None)
        save_state(state, 'checker_worktree_recovered')


def resume(args: argparse.Namespace) -> int:
    repo = repo_root(Path.cwd())
    assert_autonomy_not_paused(repo, action="resume", run_id=args.run_id)
    state = load_run(repo, args.run_id)
    if state["status"] == "accepted":
        raise RunError("accepted runs do not resume")
    if state["status"] == "awaiting-human":
        # A new attempt would replace the held candidate that a person is to review.
        raise RunError(f"awaiting-human runs do not resume: {AWAITING_HUMAN_NEXT}")
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
            validate_original_spec(repo, spec_rel, str(manifest["base_ref"]))
            if state.get("graph_id") is not None:
                graph_path = state.get("graph_path")
                effective_base = state.get("effective_base_oid")
                if not isinstance(graph_path, str) or not isinstance(effective_base, str):
                    raise RunError("graph context is incomplete in child run state")
                context = graph_effective_base(repo, graph_path, manifest_path, manifest,
                                               spec_rel, spec_hash, effective_base)
                # Later accepted siblings may have taken numbers since: the reservation stays as started.
                context.pop("sequence_numbers", None)
                if any(state.get(key) != value for key, value in context.items()):
                    raise RunError("graph contract or effective base changed since start")
                if state["base_head"] != effective_base:
                    raise RunError("child base does not match its graph effective base")
            elif git(repo, "rev-parse", str(manifest["base_ref"])) != state["base_head"]:
                raise RunError("base_ref changed since start; create a new run for a changed contract")
            worktree = Path(state["worktree"])
            if not worktree.is_dir() or repo_root(worktree) != worktree.resolve():
                raise RunError("run worktree is missing or no longer a Git worktree")
            if git(worktree, "symbolic-ref", "--short", "HEAD") != state["branch"]:
                raise RunError("run worktree is no longer on its recorded branch")
            if not clean(worktree):
                raise RunError("cannot resume a dirty worktree")
            if state.get('active_pid') and (process_is_live(state['active_pid']) or
                                          process_group_is_live(int(state['active_pid']))):
                raise RunError('previous role is still live; stop it before recovery')
            require_native_role_sandbox()
            pending_usage = state.get('usage_pending')
            if pending_usage:
                role = pending_usage.get('role')
                runtime = pending_usage.get('runtime')
                prefix = f"attempt-{state['attempt']}-{role}"
                if role not in {'maker', 'checker'} or runtime != manifest['roles'][role]['runtime'] or pending_usage.get('prefix') != prefix:
                    raise RunError('invalid unfinished usage checkpoint')
                output_path = run_dir / (prefix + '.stdout')
                record_role_usage(state, runtime, role, read_output(output_path) if output_path.exists() else '')
                state['usage_accounting_incomplete'] = True
                save_state(state, 'usage_recovered', accounting='reported output only; unreported spend unknown')
            if state.get('stage') == 'making' and state.get('maker_before_head') != git(worktree, 'rev-parse', 'HEAD'):
                raise RunError('unfinished maker advanced HEAD without a validated receipt; operator review required')
            if state.get('status') == 'checking' and not pending_candidate(state):
                raise RunError('checking stage has no candidate checkpoint; operator review required')
            assert_no_live_scope_conflicts(repo, args.run_id, manifest["scope"])
            stop_file = run_dir / "STOP"
            if stop_file.exists():
                persist_interrupted(state)
                stop_file.unlink()
            state["status"] = "resuming"
            state["reason"] = None
            # Resuming is the operator's answer to a stopped breaker: count afresh.
            state.pop("infrastructure_streak", None)
            state.pop("infrastructure_stop", None)
            state["resumed_epoch"] = time.time()
            state["scope"] = normalized_scope(manifest["scope"])
            state["controller_pid"] = os.getpid()
            state["controller_token"] = token
            save_state(state, "run_resumed")
        recover_checker_worktree(state, manifest)
        return run_controller(state, manifest)
    finally:
        if token is not None:
            release_lifecycle_lock(run_dir, token)


# Delivery: the controller checks an accepted run and prints what an operator needs to land it. It
# never pushes, opens a pull request or merges; roles have no network and no credentials, so the
# push happens in an attended step (skills/autonomous-run/SKILL.md).
ELIGIBILITY_FACTS = ("tier A", "no floor path", "checker accepted with valid citations",
                     "passing calibration for this checker", "head equals the accepted commit",
                     "CI green for this commit")


def fenced(text: str) -> str:
    """Model-written text in a code block: no Markdown, links or @-mentions take effect there."""
    clean = "".join(char if char.isprintable() or char == "\n" else " " for char in text)
    return "```text\n" + clean.replace("```", "` ` `").strip() + "\n```"


# The printed push command is pasted into a shell. Git accepts names such as `origin;id`, so a
# name must also pass this narrower pattern, and every value is quoted besides.
SAFE_REMOTE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
SAFE_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")


def unsafe_name(repo: Path, kind: str, name: str) -> str | None:
    pattern, ref = (SAFE_REMOTE, f"refs/remotes/{name}/HEAD") if kind == "remote" else (SAFE_BRANCH, f"refs/heads/{name}")
    if pattern.fullmatch(name) and not run(["git", "check-ref-format", ref], repo).returncode:
        return None
    allowed = "letters, digits, . _ -" + (" and /" if kind == "branch" else "")
    return f"{name!r} is not a safe {kind} name: use {allowed}, starting with a letter or digit"


# A copy of SECRET_PATTERNS in agentsmith.py, which the installed controller cannot import;
# scripts/test-deliver.py keeps the two equal.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PEM private key", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("AWS access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS temporary access key id", re.compile(r"ASIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("OpenAI-style key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("Anthropic-style key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    (
        "assigned secret literal",
        re.compile(
            r"\b(password|passwd|pwd|secret|token|api[_-]?key)[\"' ]*[:=]\s*[\"'][^\"' \t]{8,}",
            re.IGNORECASE,
        ),
    ),
)
# As in scripts/leak-gate.sh: a home folder names one machine and one user.
HOME_PATH = re.compile(r"(?:[A-Za-z]:\\Users\\|/(?:home|Users)/)[A-Za-z0-9_-][A-Za-z0-9._-]*")


def without_local_paths(text: str, repo: Path) -> str:
    """Paths in the repository become repo-relative; home and temporary folders become ~ and $TMPDIR."""
    roots = {str(path): "" for path in (repo, repo.resolve(), state_root(repo).parent.parent)}
    for folder, name in ((Path.home(), "~"), (Path(tempfile.gettempdir()), "$TMPDIR")):
        roots.update({str(folder): name + "/", str(folder.resolve()): name + "/"})
    for root in sorted(roots, key=len, reverse=True):
        if root not in ("", "/"):
            text = text.replace(root + "/", roots[root]).replace(root, roots[root].rstrip("/") or ".")
    return HOME_PATH.sub("~", text)


def secret_findings(records: Iterable[tuple[str, int, str]],
                    allow: tuple[re.Pattern[str], ...]) -> list[tuple[str, int, str]]:
    """`scan_secret_records` in agentsmith.py: (place, line number, pattern name) for each line that
    a pattern matches, the first pattern only, never the value. `allow` holds the repository's
    .harness/secret-scan.allow rules, which skip a whole line. scripts/test-deliver.py keeps the two equal."""
    findings = []
    for place, number, line in records:
        if not line.strip() or any(rule.search(line) for rule in allow):
            continue
        name = next((name for name, pattern in SECRET_PATTERNS if pattern.search(line)), None)
        if name:
            findings.append((place, number, name))
    return findings


def diff_secret_records(repo: Path, base: str, head: str) -> Iterator[tuple[str, int, str]]:
    """The added lines of base..head with their path and new line number, read as
    `staged_secret_records` in agentsmith.py reads the staged diff."""
    result = run(["git", "-c", "core.quotepath=false", "diff", "--no-color", "--no-ext-diff", "--unified=0",
                  "--diff-filter=ACMR", base, head], repo)
    if result.returncode:
        raise RunError(f"deliver refused: cannot read the diff {base[:12]}..{head[:12]} to scan it for secrets")
    path, number, in_hunk = "", 0, False
    for raw in result.stdout.splitlines():
        if raw.startswith("+++ "):
            path = raw[4:].split("\t", 1)[0]
            path = path[2:] if path.startswith("b/") else path
            in_hunk = False
        elif raw.startswith("@@ "):
            match = re.search(r"\+(\d+)(?:,\d+)?", raw)
            in_hunk = bool(match)
            number = int(match.group(1)) if match else 0
        elif in_hunk and raw.startswith("+"):
            yield path, number, raw[1:]
            number += 1
        elif in_hunk and not raw.startswith(("-", "\\ No newline")):
            number += 1


def history_secret_problems(repo: Path, base: str, head: str, allow: tuple[re.Pattern[str], ...]) -> list[str]:
    """The secret scanner over what a push publishes: the accepted diff, the changes of every
    commit in base..head (a secret added and removed again is still in the history), and every
    commit message. Each finding names a path or commit and a line, never the value."""
    endpoint = secret_findings(diff_secret_records(repo, base, head), allow)
    problems = [f"the accepted diff holds a likely secret at {path}:{number} ({name})" for path, number, name in endpoint]
    seen = {(path, name) for path, _, name in endpoint}
    for commit in history_commits(repo, base, head):
        parent = git(repo, "rev-parse", f"{commit}^")  # a merge counts against its first parent
        for path, number, name in secret_findings(diff_secret_records(repo, parent, commit), allow):
            if (path, name) not in seen:
                seen.add((path, name))
                problems.append(f"commit {commit[:12]} adds a likely secret at {path}:{number} ({name}), "
                                "which a later commit removes but the push still publishes")
        message = git(repo, "log", "-1", "--format=%B", commit).splitlines()
        problems += [f"the message of commit {commit[:12]} holds a likely secret at line {number} ({name})"
                     for _, number, name in secret_findings((("message", index, line) for index, line
                                                             in enumerate(message, 1)), allow)]
    return problems


def leak_problems(fields: dict[str, str], allow: tuple[re.Pattern[str], ...] = ()) -> list[str]:
    """The secret scanner over the final pull-request text, one finding per field."""
    problems = []
    for field, text in fields.items():
        lines = list(enumerate(text.splitlines(), 1))
        hit = secret_findings(((field, number, line) for number, line in lines), allow)
        if hit:
            problems.append(f"the pull-request {field} holds a likely secret ({hit[0][2]})")
        elif any(HOME_PATH.search(line) for _, line in lines if not any(rule.search(line) for rule in allow)):
            problems.append(f"the pull-request {field} names a home folder")
    return problems


def secret_allow_rules(repo: Path) -> tuple[re.Pattern[str], ...]:
    path = repo / ".harness" / "secret-scan.allow"
    try:
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        return tuple(re.compile(line) for line in lines if line.strip() and not line.lstrip().startswith("#"))
    except (OSError, UnicodeError, re.error) as exc:
        raise RunError(f"deliver refused: cannot read {path.name}: {exc}") from None


def push_command(remote: str, sha: str, branch: str) -> str:
    """Text for a person to run in a POSIX shell (sh, bash, zsh); the controller never runs it."""
    return "git push " + " ".join(shlex.quote(value) for value in (remote, f"{sha}:refs/heads/{branch}"))


def base_staleness(repo: Path, remote: str, base: str, accepted: str) -> tuple[dict[str, Any], str | None]:
    ref = f"refs/remotes/{remote}/{base}"
    cached = git(repo, "rev-parse", "--verify", "--quiet", ref, check=False)
    if not cached:
        return {}, f"{ref} is missing; fetch {remote} first, or name the branch with --base-branch"
    # The tracking ref is a cache: ask the remote (read-only) so that a base that moved since the
    # last fetch cannot hide a conflict, and an unreachable remote refuses instead of passing.
    live, error = remote_head(repo, remote, base)
    if error:
        return {}, error
    if live != cached:
        return {}, (f"base not fresh: {remote} has {base} at {str(live)[:12]}, but {ref} is at {cached[:12]}; "
                    f"run git fetch {remote}")
    behind = int(git(repo, "rev-list", "--count", f"{accepted}..{ref}") or 0)
    # `git merge-tree --write-tree` (Git 2.38+) merges without touching any worktree: 0 is clean,
    # 1 is a conflict. Anything else means this Git cannot tell.
    merged = run(["git", "merge-tree", "--write-tree", "--quiet", ref, accepted], repo)
    if merged.returncode not in {0, 1}:
        return {}, f"cannot tell whether the accepted diff applies to {remote}/{base} (needs Git 2.38 or later)"
    staleness = {"base": f"{remote}/{base}", "behind": behind, "applies": merged.returncode == 0}
    if merged.returncode == 1:
        return staleness, f"the accepted diff does not apply to {remote}/{base}; rework the run on the new base"
    return staleness, None


# Package existence. A model can name a package that does not exist; whoever registers that name
# later decides what an install runs. deliver looks up every package that is new in a manifest, as
# one read-only GET with no credentials. A 404 refuses; an answer it cannot read, a network error,
# a non-registry source or an ecosystem it cannot check is "unverified" and also refuses, as an
# unreachable remote does in base_staleness: a check that could not run never counts as a pass.
REGISTRIES = {"npm": ("registry.npmjs.org", "https://registry.npmjs.org/{}"),
              "pypi": ("pypi.org", "https://pypi.org/pypi/{}/json")}
ECOSYSTEM_NAMES = {"npm": "npm", "pypi": "PyPI"}
NPM_NAME = re.compile(r"(?:@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*")
_PYPI_NAME = r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
PYPI_NAME = re.compile(_PYPI_NAME)
PEP508_REQUIREMENT = re.compile(rf"\s*({_PYPI_NAME})\s*(\[[^\]]*\])?\s*(.*?)\s*", re.S)
PEP508_EXTRAS = re.compile(rf"\[\s*(?:{_PYPI_NAME}(?:\s*,\s*{_PYPI_NAME})*)?\s*\]")
PEP508_CLAUSE = re.compile(r"\s*(?:===\s*[^\s,;]+|(?:~=|==|!=|<=|>=|<|>)\s*[A-Za-z0-9.*+!_-]+)\s*")
# A conservative PEP 508 marker grammar: these variables and quoted strings, compared with these
# operators, joined by and/or, grouped by parentheses. Anything else is not a marker deliver can read.
MARKER_VARIABLES = frozenset({"python_version", "python_full_version", "os_name", "sys_platform",
                              "platform_release", "platform_system", "platform_version", "platform_machine",
                              "platform_python_implementation", "implementation_name", "implementation_version",
                              "extra"})
MARKER_TOKEN = re.compile(r"\s*(?:([()])|('[^']*'|\"[^\"]*\")|(===|==|!=|<=|>=|~=|<|>)|([A-Za-z_][A-Za-z0-9_.]*))")
# pip's reading of a requirements file: a `#` at the start or after whitespace starts a comment, an
# include names another file, and --hash only pins what the line already names.
REQUIREMENT_COMMENT = re.compile(r"(^|\s+)#.*$")
REQUIREMENT_INCLUDE = re.compile(r"(?:-r|-c|--requirement|--constraint)(?:\s*=\s*|\s+|(?<=-r)|(?<=-c))(\S.*)")
REQUIREMENT_HASH = re.compile(r"\s--hash(?:=|\s+)\S+")
URL_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
ARCHIVE_SUFFIXES = (".whl", ".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz", ".tar.xz", ".txz")
MAX_INCLUDED_FILES = 100
NPM_DEPENDENCY_KEYS = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")
NPM_LOCAL = ("file:", "link:", "workspace:")
# A Poetry or Pipfile table dependency comes from the registry only when it says nothing but these.
# git, path, url, file, develop, editable, source or index point the install somewhere else.
REGISTRY_TABLE_KEYS = frozenset({"version", "extras", "markers", "python", "optional", "platform",
                                 "allow-prereleases"})
PIPFILE_SETTINGS = frozenset({"source", "requires", "pipenv", "scripts"})  # every other table is packages
PYPI_INDEXES = frozenset({"https://pypi.org/simple", "https://pypi.org/simple/"})
# Manifests with no registry check here: a change is unverified. Lockfiles list what a manifest
# already names, so the manifests are what is checked.
UNCHECKED_MANIFESTS = {"go.mod": "go", "cargo.toml": "cargo", "gemfile": "ruby"}
MAX_PACKAGE_LOOKUPS = 100


class ManifestShapeError(ValueError):
    """A manifest that parses, but not into the shape its tool reads."""


def registry_status(url: str) -> int:
    """One read-only GET; the HTTP status. Raises OSError when the registry gives no answer."""
    import urllib.error
    import urllib.request
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "agentsmith-deliver",
                                                                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def pypi_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()  # PEP 503 normalisation


def valid_marker(text: str) -> bool:
    """Whether text is an environment marker in the conservative grammar above."""
    tokens: list[tuple[int, str]] = []
    position, text = 0, text.rstrip()
    while position < len(text):
        match = MARKER_TOKEN.match(text, position)
        if not match:
            return False
        tokens.append((match.lastindex or 0, match.group(match.lastindex or 0)))
        position = match.end()
    paren, string, operator, word = 1, 2, 3, 4

    def is_word(index: int, value: str) -> bool:
        return 0 <= index < len(tokens) and tokens[index] == (word, value)

    def operand(index: int) -> int:
        if 0 <= index < len(tokens) and (tokens[index][0] == string or
                                         (tokens[index][0] == word and tokens[index][1] in MARKER_VARIABLES)):
            return index + 1
        return -1

    def comparison(index: int) -> int:
        if 0 <= index < len(tokens) and tokens[index][0] == operator or is_word(index, "in"):
            return index + 1
        return index + 2 if is_word(index, "not") and is_word(index + 1, "in") else -1

    def expression(index: int) -> int:
        if 0 <= index < len(tokens) and tokens[index] == (paren, "("):
            index = disjunction(index + 1)
            return index + 1 if 0 <= index < len(tokens) and tokens[index] == (paren, ")") else -1
        for step in (operand, comparison, operand):
            index = step(index) if index >= 0 else -1
        return index

    def chain(index: int, step: Callable[[int], int], joiner: str) -> int:
        index = step(index)
        while index >= 0 and is_word(index, joiner):
            index = step(index + 1)
        return index

    def disjunction(index: int) -> int:
        return chain(index, lambda start: chain(start, expression, "and"), "or")

    return disjunction(0) == len(tokens)


def pep508_entry(text: str) -> tuple[str | None, str | None]:
    """(normalised name, None) for a registry requirement, or (None, why it cannot be checked)."""
    requirement, has_marker, marker = text.partition(";")
    bare = requirement.strip()
    if URL_SCHEME.match(bare) or "/" in bare or "\\" in bare or bare.casefold().endswith(ARCHIVE_SUFFIXES):
        return None, "only registry packages can be checked"  # a URL, a VCS link, `name @ url` or a path
    match = PEP508_REQUIREMENT.fullmatch(requirement)
    if not match:
        return None, "it is not a valid requirement"
    name, extras, specifier = match.groups()
    if specifier.startswith("(") and specifier.endswith(")"):
        specifier = specifier[1:-1]
    if ((extras and not PEP508_EXTRAS.fullmatch(extras))
            or (specifier and not all(PEP508_CLAUSE.fullmatch(clause) for clause in specifier.split(",")))):
        return None, "it is not a valid requirement"
    if has_marker and not valid_marker(marker):
        return None, "its environment marker is not valid"
    return pypi_name(name), None


def requirement_lines(text: str) -> list[tuple[int, str]]:
    """(line number, entry) for each requirement line, read as pip reads it: a line that ends in a
    backslash continues on the next, and a `#` at the start or after whitespace starts a comment."""
    lines: list[tuple[int, str]] = []
    pending: list[str] = []
    first = 0
    for number, line in enumerate(text.splitlines(), 1):
        if line.endswith("\\") and not REQUIREMENT_COMMENT.match(line):
            first = first if pending else number
            pending.append(line.strip("\\"))
            continue
        if pending:
            line, number, pending = "".join(pending) + (" " + line if REQUIREMENT_COMMENT.match(line) else line), \
                first, []
        entry = REQUIREMENT_COMMENT.sub("", line).strip()
        if entry:
            lines.append((number, entry))
    entry = REQUIREMENT_COMMENT.sub("", "".join(pending)).strip()
    if entry:  # the file ends inside a continuation
        lines.append((first, entry))
    return lines


def included_path(including: str, target: str) -> str | None:
    """The repository path that a requirements include names, relative to the including file, or
    None when it leaves the repository: an absolute or home path, a URL, or a path above the top."""
    if target.startswith(("/", "\\", "~")) or URL_SCHEME.match(target):
        return None
    path = posixpath.normpath(posixpath.join(posixpath.dirname(including), target))
    return None if path == ".." or path.startswith("../") else path


def requirements_entries(read: Callable[[str], str | None], root: str
                         ) -> tuple[dict[Any, dict[str, Any]], list[str], set[str]]:
    """The registry packages that a requirements file names, with the files it includes
    (-r/--requirement and -c/--constraint, relative to the including file, each read once); the
    entries that cannot be checked; and every file read. Any other option, a URL or a local path
    changes where packages come from, so it cannot be checked."""
    entries: dict[Any, dict[str, Any]] = {}
    unchecked: list[str] = []
    seen: list[str] = []

    def visit(path: str, text: str) -> None:
        seen.append(path)
        for number, entry in requirement_lines(text):
            where = f"{path} line {number} ({entry[:80]})"
            include = REQUIREMENT_INCLUDE.fullmatch(entry)
            if include:
                target = included_path(path, include.group(1).strip())
                if target is None:
                    unchecked.append(f"{where}: it includes a file outside the repository")
                elif target not in seen:
                    included = read(target)
                    if included is None:
                        unchecked.append(f"{where}: the included file is not in the repository")
                    elif len(seen) >= MAX_INCLUDED_FILES:
                        unchecked.append(f"{where}: it includes more than {MAX_INCLUDED_FILES} files")
                    else:
                        visit(target, included)
                continue
            if entry.startswith("-"):
                unchecked.append(f"{where}: only registry packages can be checked")
                continue
            package, why = pep508_entry(REQUIREMENT_HASH.sub("", entry))
            if package:
                entries.setdefault(package, {"name": package, "lookup": package, "source": "registry",
                                             "spec": "", "file": path})
            else:
                unchecked.append(f"{where}: {why}")

    text = read(root)
    if text is not None:
        visit(root, text)
    return entries, unchecked, set(seen)


def shaped(value: Any, kind: type, where: str) -> Any:
    if not isinstance(value, kind):
        raise ManifestShapeError(f"{where} has the wrong type")
    return value


def strings(value: Any, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ManifestShapeError(f"{where} is not a list of strings")
    return value


def npm_source(package: str, spec: str) -> tuple[str, str | None]:
    """("registry", the name to look up), ("local", None) or ("unverified", None) for one spec."""
    if spec.startswith(NPM_LOCAL):
        return "local", None
    if spec.startswith("npm:"):  # an alias installs the package it names
        target = spec[4:]
        at = target.find("@", 1)
        return "registry", target[:at] if at > 0 else target
    # A URL, Git or hosted-Git source (git+, git:, http:, github:, gitlab:, bitbucket:...), GitHub
    # user/repo shorthand, or a path. A range such as ~1.2 or a dist-tag has no colon and no slash.
    if URL_SCHEME.match(spec) or "/" in spec or "\\" in spec or spec in {".", ".."}:
        return "unverified", None
    return "registry", package


def npm_entries(path: str, text: str) -> dict[Any, dict[str, Any]]:
    """Each dependency keyed by its section and its name in the manifest: an alias never merges with
    another entry for the package it installs, so each gets its own verdict."""
    data = shaped(json.loads(text), dict, "the top level")
    entries: dict[Any, dict[str, Any]] = {}
    for section in NPM_DEPENDENCY_KEYS:
        if section not in data:
            continue
        for package, spec in shaped(data[section], dict, section).items():
            source, lookup = npm_source(package, shaped(spec, str, f"a {section} version"))
            entries[(section, package)] = {"name": package, "lookup": lookup, "source": source, "spec": spec,
                                           "file": path}
    return entries


def python_manifest_entries(path: str, name: str, text: str) -> tuple[dict[Any, dict[str, Any]], list[str]]:
    """The registry packages of a pyproject.toml or Pipfile, and the entries that cannot be checked."""
    import tomllib
    data = tomllib.loads(text)
    requirements: list[str] = []
    tables: list[dict[str, Any]] = []  # Poetry and Pipfile: {name: version, table or list of them}
    unchecked: list[str] = []
    if name == "pyproject.toml":
        project = shaped(data.get("project", {}), dict, "[project]")
        requirements += strings(project.get("dependencies", []), "[project] dependencies")
        for group in shaped(project.get("optional-dependencies", {}), dict, "[project.optional-dependencies]").values():
            requirements += strings(group, "a [project.optional-dependencies] group")
        for group in shaped(data.get("dependency-groups", {}), dict, "[dependency-groups]").values():
            for item in shaped(group, list, "a [dependency-groups] group"):
                if isinstance(item, str):
                    requirements.append(item)
                elif not (isinstance(item, dict) and set(item) == {"include-group"}
                          and isinstance(item["include-group"], str)):
                    raise ManifestShapeError("a [dependency-groups] entry has the wrong type")
        requirements += strings(shaped(data.get("build-system", {}), dict, "[build-system]").get("requires", []),
                                "[build-system] requires")
        tool = shaped(data.get("tool", {}), dict, "[tool]")
        poetry = shaped(tool.get("poetry", {}), dict, "[tool.poetry]")
        uv = shaped(tool.get("uv", {}), dict, "[tool.uv]")
        pdm = shaped(tool.get("pdm", {}), dict, "[tool.pdm]")
        tables += [shaped(poetry.get(key, {}), dict, f"[tool.poetry.{key}]")
                   for key in ("dependencies", "dev-dependencies")]
        for group in shaped(poetry.get("group", {}), dict, "[tool.poetry.group]").values():
            tables.append(shaped(shaped(group, dict, "a [tool.poetry.group] group").get("dependencies", {}), dict,
                                 "a [tool.poetry.group] dependencies table"))
        for configured, label in ((poetry.get("source"), "[tool.poetry.source]"), (uv.get("index"), "[tool.uv.index]"),
                                  (pdm.get("source"), "[tool.pdm.source]")):
            if configured:
                unchecked.append(f"{path} {label}: it names another index")
        for package in shaped(uv.get("sources", {}), dict, "[tool.uv.sources]"):
            unchecked.append(f"{path} {package[:80]} (tool.uv.sources): only registry packages can be checked")
    else:  # Pipfile
        for source in shaped(data.get("source", []), list, "[[source]]"):
            url = shaped(source, dict, "a [[source]] entry").get("url")
            if url not in PYPI_INDEXES:
                unchecked.append(f"{path} [[source]] {str(url)[:80]}: it names another index")
        tables += [shaped(section, dict, "a Pipfile package section")
                   for key, section in data.items() if key not in PIPFILE_SETTINGS]
    entries: dict[Any, dict[str, Any]] = {}
    for table in tables:
        for package, value in table.items():
            if package.casefold() == "python":  # Poetry: the Python version, not a package
                continue
            options = value if isinstance(value, list) else [value]
            if not options or not all(isinstance(option, (str, dict)) for option in options):
                raise ManifestShapeError("a dependency has the wrong type")
            if any(isinstance(option, dict) and not set(option) <= REGISTRY_TABLE_KEYS for option in options):
                unchecked.append(f"{path} {package[:80]}: only registry packages can be checked")
                continue
            normalised = pypi_name(package)
            entries.setdefault(normalised, {"name": normalised, "lookup": normalised, "source": "registry",
                                            "spec": "", "file": path})
    for item in requirements:
        package, why = pep508_entry(item)
        if package:
            entries.setdefault(package, {"name": package, "lookup": package, "source": "registry", "spec": "",
                                         "file": path})
        else:
            unchecked.append(f"{path} {item[:80]}: {why}")
    return entries, unchecked


def manifest_entries(path: str, text: str) -> tuple[str, dict[Any, dict[str, Any]], list[str]]:
    """(ecosystem, {key: entry}, entries that cannot be checked) for a package.json, pyproject.toml or
    Pipfile. An entry names its package, the name to look up, its source ("registry", "local" or
    "unverified"), its spec and its file. Raises ValueError when the manifest does not parse or does
    not have the shape its tool reads."""
    name = path.rsplit("/", 1)[-1].casefold()
    if name == "package.json":
        return "npm", npm_entries(path, text), []
    return ("pypi", *python_manifest_entries(path, name, text))


def is_requirements_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1].casefold()
    return name.startswith("requirements") and name.endswith(".txt")


def package_checks(repo: Path, base: str, head: str,
                   fetch: Callable[[str], int] | None = None) -> tuple[list[dict[str, str]], list[str]]:
    """Every package that a manifest in base..head adds, or moves to another source, with its
    registry verdict, and the problems that refuse the landing. A package a manifest already had at
    base, from the same source, is not looked up. A requirements file counts as changed when a file
    it includes changed."""
    fetch = fetch or registry_status
    rows: list[dict[str, str]] = []
    problems: list[str] = []
    answers: dict[str, int | Exception] = {}
    seen_rows: set[tuple[str, ...]] = set()
    lookups = 0

    def reader(revision: str) -> Callable[[str], str | None]:
        cache: dict[str, str | None] = {}

        def read(path: str) -> str | None:
            if path not in cache:
                shown = run(["git", "cat-file", "blob", f"{revision}:{path}"], repo)
                cache[path] = None if shown.returncode else shown.stdout
            return cache[path]
        return read

    read_head, read_base = reader(head), reader(base)
    changed = changed_paths(repo, base, head)
    requirements = {path: requirements_entries(read_head, path)
                    for path in git_paths(repo, "ls-tree", "-r", "--name-only", head) if is_requirements_file(path)}
    candidates = set(changed) | {path for path, (_, _, files) in requirements.items() if files & set(changed)}
    for path in sorted(candidates):
        name = path.rsplit("/", 1)[-1].casefold()
        if name in UNCHECKED_MANIFESTS:
            if read_head(path) is not None:  # not a removal
                problems.append(f"{path} changed, and deliver cannot check {UNCHECKED_MANIFESTS[name]} packages "
                                "against a registry; review the new requirements by hand")
            continue
        if path in requirements:
            ecosystem, (entries, unchecked, _) = "pypi", requirements[path]
            known = requirements_entries(read_base, path)[0]
        elif name in {"package.json", "pyproject.toml", "pipfile"}:
            text = read_head(path)
            if text is None:
                continue  # removed: nothing new to install
            try:
                ecosystem, entries, unchecked = manifest_entries(path, text)
            except (ValueError, RecursionError) as exc:  # json, tomllib and shape errors are ValueErrors
                problems.append(f"cannot read {path} to check its new packages ({str(exc)[:80]}); the landing "
                                "stays refused until it parses")
                continue
            before = read_base(path)
            try:
                known = manifest_entries(path, before)[1] if before is not None else {}
            except (ValueError, RecursionError):
                known = {}  # an unreadable base manifest: every package counts as new
        else:
            continue
        problems += [f"cannot check {item}" for item in unchecked]
        host, template = REGISTRIES[ecosystem]
        label = ECOSYSTEM_NAMES[ecosystem]
        for key, entry in sorted(entries.items(), key=lambda item: (item[1]["name"], str(item[0]))):
            old = known.get(key)
            if old is not None and (old["spec"] == entry["spec"] or (
                    entry["source"] == old["source"] == "registry" and entry["lookup"] == old["lookup"])):
                continue  # the same package from the same source; only its version may have changed
            row = {"manifest": entry["file"], "ecosystem": ecosystem, "name": entry["name"], "status": entry["source"]}
            lookup = entry["lookup"]
            if lookup and lookup != entry["name"]:
                row["lookup"] = lookup
            identity = (row["manifest"], ecosystem, row["name"], row.get("lookup", ""))
            if identity in seen_rows:  # a file that two requirements files include
                continue
            seen_rows.add(identity)
            rows.append(row)
            shown = entry["name"] + (f" -> {lookup}" if "lookup" in row else "")
            if entry["source"] == "local":
                continue
            if entry["source"] == "unverified":
                problems.append(f"cannot check {label} package {shown} from {entry['file']}: it does not come from "
                                f"{host}")
                continue
            if not (NPM_NAME if ecosystem == "npm" else PYPI_NAME).fullmatch(lookup):
                row["status"] = "invalid"
                problems.append(f"{entry['file']} adds {shown!r}, which is not a valid {label} package name")
                continue
            url = template.format(urllib_quote(lookup))
            if url not in answers:
                lookups += 1
                if lookups > MAX_PACKAGE_LOOKUPS:
                    row["status"] = "unverified"
                    problems.append(f"cannot check {label} package {shown} from {entry['file']}: more than "
                                    f"{MAX_PACKAGE_LOOKUPS} new packages")
                    continue
                try:
                    answers[url] = fetch(url)
                except (OSError, ValueError) as exc:
                    answers[url] = exc
            answer = answers[url]
            if isinstance(answer, Exception):
                row["status"] = "unverified"
                problems.append(f"cannot check {label} package {shown} from {entry['file']}: {host} did not answer "
                                f"({str(answer)[:80]}); retry when it answers")
            elif answer == 200:
                row["status"] = "exists"
            elif answer == 404:
                row["status"] = "missing"
                problems.append(f"{entry['file']} adds {label} package {shown}, which {host} does not have")
            else:
                row["status"] = "unverified"
                problems.append(f"cannot check {label} package {shown} from {entry['file']}: {host} answered "
                                f"HTTP {answer}; retry when it answers")
    return rows, list(dict.fromkeys(problems))


def urllib_quote(package: str) -> str:
    import urllib.parse
    return urllib.parse.quote(package, safe="@")  # a scoped npm name keeps @ and sends / as %2F


def merge_verification(repo: Path, state: dict[str, Any], manifest: dict[str, Any], remote: str, base: str,
                       accepted: str) -> tuple[dict[str, Any], str | None]:
    """Run the manifest's verify command on the merge of the accepted commit with the fresh base,
    in the same sandbox as `execute`, before deliver prints anything to land.

    A clean `merge-tree` only proves the diff applies; the merge can still break a test. The merge
    is built in a private object folder that borrows the repository's objects, and checked out
    from a private index into a throwaway folder under /tmp. A `git worktree add` would change the
    shared worktree metadata and object store, which peer runs compare to catch tampering, so the
    repository gains no worktree, object or file, and the folder goes when the check ends."""
    ref = f"refs/remotes/{remote}/{base}"
    base_commit = git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")
    timeout = int(float((manifest.get("limits") or {}).get("wall_minutes") or 60) * 60)
    with private_scratch("agentsmith-merge-") as scratch:
        workspace, run_dir = scratch / "merge", scratch / "run"
        (scratch / "objects").mkdir()
        run_dir.mkdir()
        private = {**os.environ, "GIT_OBJECT_DIRECTORY": str(scratch / "objects"),
                   "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(resolved_git_path(repo, "--git-common-dir") / "objects"),
                   "GIT_INDEX_FILE": str(scratch / "index")}
        merged = run(["git", "merge-tree", "--write-tree", ref, accepted], repo, env=private)
        tree = merged.stdout.split()[0] if merged.returncode == 0 and merged.stdout.split() else ""
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", tree):
            return {}, f"cannot build the merge of the accepted commit with {remote}/{base} to verify it"
        workspace.mkdir()
        for command in (["git", "read-tree", tree],
                        ["git", f"--work-tree={workspace}", "checkout-index", "--all", "--force"]):
            result = run(command, repo, env=private)
            if result.returncode:
                return {}, f"cannot check out the merge with {remote}/{base} to verify it: {result.stderr.strip()[:200]}"
        # One commit of exactly the merged files, so a verify command that lists tracked files
        # sees them, as in a checkout. No user or system Git configuration takes part.
        clean = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                 "GIT_AUTHOR_NAME": "agentsmith", "GIT_AUTHOR_EMAIL": "agentsmith@example.com",
                 "GIT_COMMITTER_NAME": "agentsmith", "GIT_COMMITTER_EMAIL": "agentsmith@example.com"}
        for command in (["git", "init", "-q"], ["git", "add", "--all", "--force"],
                        ["git", "commit", "-q", "--no-verify", "-m", f"merge of {accepted[:12]} with {remote}/{base}"]):
            result = run(command, workspace, env=clean)
            if result.returncode:
                return {}, f"cannot prepare the merge with {remote}/{base} to verify it: {result.stderr.strip()[:200]}"
        # The verifier's own launch records go to the private folder, not the run's; the run's
        # state, manifest and spec stay protected as in execute.
        sandbox_state = {"run_id": state.get("run_id"), "repo": state["repo"], "manifest_path": state["manifest_path"],
                         "spec_path": state["spec_path"], "state_path": str(run_dir / "state.json"),
                         "attempt": state.get("attempt", 0), "stage": "delivering", "active_pid": None}
        result = sandboxed_verify(manifest["verify"]["command"], workspace, timeout, verifier_env(),
                                  state=sandbox_state, prefix="deliver-merge-verify")
    outcome = verification_outcome(result)
    output = hashlib.sha256(f"exit={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                            .encode("utf-8", "replace")).hexdigest()
    record = {"needed": True, "base": f"{remote}/{base}", "base_commit": base_commit, "merge_tree": tree,
              "verification": outcome["verification"], "exit_code": result.returncode,
              "failing": outcome["failing"], "output_sha256": output}
    if outcome["verification"] != "passed":
        failing = ", ".join(outcome["failing"][:3])
        return record, (f"the accepted commit merged with {remote}/{base} fails verification "
                        f"({outcome['verification']}, exit {result.returncode})"
                        + (f"; failing checks: {failing}" if failing else "") + "; rework the run on the new base")
    return record, None


def delivery_checks(repo: Path, state: dict[str, Any], remote: str, base: str | None,
                    fetch: Callable[[str], int] | None = None) -> dict[str, Any]:
    """Every check `deliver` makes. Any mismatch refuses, with all reasons at once."""
    run_id = state.get("run_id")
    if state.get("status") == "awaiting-human":
        # No approve verb exists, so a held run is never delivered as it stands.
        raise RunError(f"deliver refused: run {run_id} is awaiting-human, not accepted: "
                       f"{state.get('reason')}; {AWAITING_HUMAN_NEXT}")
    if state.get("status") != "accepted":
        raise RunError(f"deliver refused: run {run_id} is {state.get('status')}, not accepted")
    # The names reach git arguments and the printed push command: check them before anything else.
    names = [unsafe_name(repo, "remote", remote), unsafe_name(repo, "branch", str(state.get("branch"))),
             unsafe_name(repo, "branch", base) if base is not None else None]
    if any(names):
        raise RunError("deliver refused: " + "; ".join(problem for problem in names if problem))
    problems: list[str] = []
    accepted, branch = str(state.get("accepted_commit")), str(state.get("branch"))
    run_dir = Path(state["state_path"]).parent
    tip = git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False)
    if tip != accepted:
        problems.append(f"branch {branch} is at {tip[:12] or 'nothing'}, not the accepted commit {accepted[:12]}")
    manifest_path = Path(state["manifest_path"])
    if not manifest_path.is_file() or hashlib.sha256(manifest_path.read_bytes()).hexdigest() != state.get("manifest_sha256"):
        problems.append("the run manifest changed since the run started")
    try:
        proof = load_json(Path(str(state.get("verification_receipt"))))
    except RunError:
        raise RunError("deliver refused: the verification receipt is missing or unreadable") from None
    if proof.get("candidate_commit") != accepted:
        problems.append(f"the verification receipt names {str(proof.get('candidate_commit'))[:12]}, "
                        f"not the accepted commit {accepted[:12]}")
    receipt_path = run_dir / f"attempt-{state.get('attempt')}-checker-receipt.json"
    if file_digest(receipt_path) != proof.get("checker_receipt_sha256"):
        problems.append("the checker receipt no longer matches its recorded hash")
        checker: dict[str, Any] = {}
    else:
        checker = load_json(receipt_path)
        if checker.get("status") != "accepted" or checker.get("commit") != accepted:
            problems.append("the checker receipt is not an acceptance of the accepted commit")
    if proof.get("citations") != "valid":
        problems.append("the verification receipt does not record checked citations")
    # The verifier log is still in the run folder: hash it again and re-check the citations that
    # quote it. Files the verifier left in its disposable worktree are gone; their hashes were
    # checked at acceptance.
    log = run_dir / f"attempt-{state.get('attempt')}-verify.txt"
    index = proof.get("evidence_files") if isinstance(proof.get("evidence_files"), dict) else {}
    if log.name not in index or file_digest(log) != index.get(log.name):
        problems.append(f"{log.name} changed after the verifier finished")
    elif checker:
        quoting_log = [item for item in checker.get("evidence", [])
                       if isinstance(item, str) and f" :: {log.name}" in item]
        if quoting_log:
            problem = citation_problem({"evidence": quoting_log}, {log.name: index[log.name]}, log,
                                       run_dir / "no-worktree", int(state.get("attempt", 0)))
            if problem:
                problems.append(f"a citation no longer holds: {problem}")
    manifest = load_json(manifest_path) if manifest_path.is_file() else {}
    base = base or default_branch(repo, remote)
    staleness: dict[str, Any] = {}
    if base is None:
        problems.append(f"cannot tell the base branch: {remote}/HEAD is not set; pass --base-branch")
    elif unsafe_name(repo, "branch", base):
        problems.append(str(unsafe_name(repo, "branch", base)))
    else:
        staleness, problem = base_staleness(repo, remote, base, accepted)
        if problem:
            problems.append(problem)
    # Every mode refuses a likely secret, --dry-run included: the push would publish it.
    problems += history_secret_problems(repo, str(state["base_head"]), accepted, secret_allow_rules(repo))
    packages, package_problems = package_checks(repo, str(state["base_head"]), accepted, fetch)
    problems += package_problems
    if problems:
        raise RunError("deliver refused: " + "; ".join(problems))
    import risk_map
    recorded = (state.get("risk") or {}).get("tier") if isinstance(state.get("risk"), dict) else None
    try:
        # Every commit the push publishes, not only the endpoint diff: a floor path added and
        # removed again is still in the pushed history.
        report = risk_map.classify_history(repo, str(state["base_head"]), accepted)
    except (risk_map.PolicyError, risk_map.RiskError) as exc:
        raise RunError(f"deliver refused: cannot recompute the risk tier: {exc}") from None
    declared = manifest.get("risk_tier")
    tier = risk_map.raise_tier(report["tier"], recorded if recorded in risk_map.TIERS else "A")
    tier = risk_map.raise_tier(tier, declared if declared in risk_map.TIERS else "A")
    floor = sorted(row["path"] for row in report["paths"] if any(reason.startswith("floor:") for reason in row["matched"]))
    # Last, once every cheaper check passed: behind the base, the merge result itself must pass.
    merge: dict[str, Any] = {"needed": False}
    if staleness.get("behind"):
        merge, problem = merge_verification(repo, state, manifest, remote, str(base), accepted)
        if problem:
            raise RunError("deliver refused: " + problem)
    return {"state": state, "merge_verification": merge, "proof": proof, "checker": checker, "manifest": manifest,
            "accepted": accepted, "models": models_used(run_dir, manifest),
            "branch": branch, "staleness": staleness, "packages": packages,
            "paths": changed_paths(repo, str(state["base_head"]), accepted),
            "tier": {"tier": tier, "recorded": recorded, "recomputed": report["tier"], "declared": declared,
                     "lenses": report["lenses"], "policy_blob": report["policy"]["blob"], "floor_paths": floor,
                     "paths": report["paths"]},
            "calibration": calibration_status(repo, (manifest.get("roles") or {}).get("checker") or {})}


def default_branch(repo: Path, remote: str) -> str | None:
    head = git(repo, "symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote}/HEAD", check=False)
    return head.split("/", 1)[1] if head.startswith(f"{remote}/") else None


def github_repository(repo: Path, remote: str) -> str | None:
    """owner/name from the remote's configured GitHub URL (before any insteadOf rewrite)."""
    url = git(repo, "config", "--get", f"remote.{remote}.url", check=False)
    match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
                         r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?", url)
    return match.group(1) if match else None


def remote_head(repo: Path, remote: str, branch: str) -> tuple[str | None, str]:
    """Read-only: the commit the remote has for `branch` now, or why that cannot be told."""
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        result = run(["git", "ls-remote", "--exit-code", remote, f"refs/heads/{branch}"], repo, timeout=60,
                     env=environment)
    except subprocess.TimeoutExpired:
        return None, f"{remote} did not answer within 60 s"
    if result.returncode == 2:
        return None, f"{remote} has no branch {branch}"
    if result.returncode:
        lines = result.stderr.strip().splitlines()
        return None, f"cannot reach {remote}: {lines[-1] if lines else 'exit ' + str(result.returncode)}"
    return result.stdout.split()[0], ""


def ci_problem(ci: dict[str, Any], sha: str, branch: str, repository: str | None) -> str | None:
    """A CI report counts only for this commit, this branch and this repository."""
    if not all(isinstance(ci.get(key), str) and ci.get(key) for key in ("sha", "repo", "branch")):
        return "the report does not name its repo, branch and sha; save it from `agentsmith ci watch --pr`"
    if ci["sha"] != sha:
        return f"the report is for {ci['sha'][:12]}"
    if repository is None:
        return "cannot tell the GitHub repository of the remote"
    if ci["repo"].casefold() != repository.casefold():
        return f"the report is for repository {ci['repo']}, not {repository}"
    if ci["branch"] != branch:
        return f"the report is for branch {ci['branch']}, not {branch}"
    return None if ci.get("state") == "green" else str(ci.get("state"))


def eligibility(checks: dict[str, Any], sha: str, ci: dict[str, Any] | None,
                pushed: dict[str, Any] | None = None) -> dict[str, Any]:
    """D2: informational only. "yes" needs every fact; nothing merges because of it. After CI,
    `pushed` holds what the remote has: its branch head and GitHub repository."""
    tier = checks["tier"]
    calibration = checks["calibration"].get("status")
    if ci is None:
        ci_fact = (None, "pending CI")
    else:
        problem = ci_problem(ci, sha, checks["branch"], (pushed or {}).get("repository"))
        ci_fact = (problem is None, f"unmet ({problem})")
    head_fact = (sha == checks["accepted"], f"unmet ({sha[:12]} is not {checks['accepted'][:12]})")
    if head_fact[0] and pushed is not None and pushed["head"] != checks["accepted"]:
        where = f"{pushed['remote']}/{checks['branch']}"
        head_fact = (False, f"unmet ({where} is at {pushed['head'][:12]})" if pushed["head"]
                     else f"unmet ({pushed['error']})")
    facts = [
        (tier["tier"] == "A", f"unmet ({tier['tier']})"),
        (not tier["floor_paths"], f"unmet ({', '.join(tier['floor_paths'][:3])})"),
        (True, ""),  # delivery_checks already refused anything else
        (calibration == "passed", f"unmet ({calibration})"),
        head_fact,
        ci_fact,
    ]
    rows = [{"fact": name, "met": met, "detail": "met" if met else detail}
            for name, (met, detail) in zip(ELIGIBILITY_FACTS, facts)]
    eligible = all(row["met"] is True for row in rows)
    line = (f"Auto-merge eligible: {'yes' if eligible else 'no'} for {sha} — "
            + "; ".join(f"{row['fact']}: {row['detail']}" for row in rows))
    return {"eligible": eligible, "sha": sha, "facts": rows, "line": line}


def models_used(run_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Each role's client, model and effort as its launches recorded them (`attempt-N-<role>-exit.json`),
    with the attempts that used them. A role that never launched shows the manifest's setting."""
    used: dict[tuple[str, str, str, str], set[int]] = {}
    for path in sorted(run_dir.glob("attempt-*-exit.json")):
        match = re.fullmatch(r"attempt-([0-9]+)-(maker|checker)-exit[.]json", path.name)
        try:
            record = json.loads(path.read_text(encoding="utf-8")) if match else None
        except (OSError, ValueError):
            record = None
        if not isinstance(record, dict) or record.get("role") != match.group(2):
            continue
        key = (match.group(2), *(str(record.get(name) or "unknown") for name in ("runtime", "model", "effort")))
        used.setdefault(key, set()).add(int(match.group(1)))
    roles = manifest.get("roles") if isinstance(manifest.get("roles"), dict) else {}
    rows = [{"role": role, "client": client, "model": model, "effort": effort, "attempts": sorted(attempts)}
            for (role, client, model, effort), attempts in used.items()]
    for role in ("maker", "checker"):
        if not any(row["role"] == role for row in rows):
            config = roles.get(role) if isinstance(roles.get(role), dict) else {}
            rows.append({"role": role, "client": str(config.get("runtime") or "unknown"),
                         "model": str(config.get("model") or "unknown"),
                         "effort": str(config.get("effort") or "unknown"), "attempts": []})
    return sorted(rows, key=lambda row: (("maker", "checker").index(row["role"]), row["attempts"]))


def models_used_lines(checks: dict[str, Any]) -> list[str]:
    def attempts(row: dict[str, Any]) -> str:
        numbers = row["attempts"]
        if not numbers:
            return "not launched"
        return ("attempt " if len(numbers) == 1 else "attempts ") + ", ".join(map(str, numbers))
    # Model names come from the manifest and the run folder, so they sit in a code block too.
    return ["### Models used",
            fenced("\n".join(f"- {row['role']}: {row['client']}, model {row['model']}, effort {row['effort']} "
                              f"({attempts(row)})" for row in checks["models"])), ""]


def assumption_lines(checks: dict[str, Any]) -> list[str]:
    """The maker's assumptions made without authority, from its report (SF-16)."""
    maker = checks["state"].get("maker_receipt")
    items = bounded_assumptions(report_assumptions(str(maker.get("summary") or ""))) if isinstance(maker, dict) else []
    if not items:
        return ["### Assumptions made without authority", "The maker's report lists none.", ""]
    return ["### Assumptions made without authority",
            "The maker made these choices; the spec and ticket did not settle them.",
            fenced("\n".join(f"- {item}" for item in items)), ""]


def reviewer_focus_lines(checks: dict[str, Any]) -> list[str]:
    """The paths above tier A, highest tier first, with the rules and lenses that put them there."""
    import risk_map
    tier = checks["tier"]
    lenses = f" Lenses: {', '.join(tier['lenses'])}." if tier["lenses"] else ""
    risky = sorted((row for row in tier.get("paths", []) if row["tier"] != "A"),
                   key=lambda row: (-risk_map.TIERS.index(row["tier"]), row["path"]))
    if not risky:
        return ["### Reviewer focus",
                f"Every path is tier A under the policy at the base; no path needs more than the usual review.{lenses}",
                ""]
    def reasons(row: dict[str, Any]) -> str:
        parts = list(row["matched"]) + ([f"lenses: {', '.join(row['lenses'])}"] if row["lenses"] else [])
        return f" ({'; '.join(parts)})" if parts else ""
    return ["### Reviewer focus", f"Read these paths first, highest tier first.{lenses}",
            fenced("\n".join(f"- {row['tier']} {row['path']}{reasons(row)}" for row in risky)), ""]


# Replayable feature evidence (SF-18b). The accepted spec may declare one demo command under
# `## Demo`. At acceptance the controller, not a role, runs it on the accepted commit in the
# verifier sandbox and keeps a redacted, bounded transcript in the run folder. The pull-request
# body and the inbox row link it; `evidence` shows it and records that the operator opened it.
DEMO_HEADING = "Demo"
DEMO_STREAM_LIMIT = 20000  # characters kept of each of stdout and stderr
DEMO_BODY_LIMIT = 3000  # characters of the transcript quoted in the pull-request body
DEMO_TIMEOUT_SECONDS = 120
DEMO_FILE = re.compile(r"attempt-[0-9]+-demo\.txt")
DEMO_MISSING = ("the spec's '## Demo' section holds no command: put the demo command in a fenced code "
                "block under it, or remove the section")
# The secret scanner's patterns, each replaced by a marker. An assigned value runs to its closing
# quote, so a passphrase with spaces goes whole, as in `factory export`.
DEMO_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    *((name, pattern) for name, pattern in SECRET_PATTERNS if name != "assigned secret literal"),
    ("assigned secret", re.compile(r"(?i)\b[\w-]*(?:secret|token|password|passwd|pwd|api[_-]?key)[\w-]*"
                                   r"[\"' ]*[:=]\s*(?:\"[^\"\n]{8,}\"|'[^'\n]{8,}'|[\"']?[^\s\"',]{8,})")),
)


def spec_demo_command(text: str) -> str | None:
    """The first fenced code block under the spec's `## Demo` heading, or None without that
    heading. A heading inside a fenced block does not count; a section with no command refuses."""
    end = text.find("\n---\n", 4) if text.startswith("---\n") else -1
    in_demo, fence, block = False, None, None
    for line in text[end + 5:].splitlines() if end >= 0 else text.splitlines():
        stripped = line.lstrip()
        if fence is not None:
            if stripped.startswith(fence):
                if block is not None:
                    command = "\n".join(block).strip()
                    if not command:
                        raise RunError(DEMO_MISSING)
                    return command
                fence = None
            elif block is not None:
                block.append(line)
            continue
        if stripped.startswith(("```", "~~~")):
            fence = stripped[:3]
            block = [] if in_demo else None
            continue
        if re.match(r"#{1,2}\s", line):
            if in_demo:
                raise RunError(DEMO_MISSING)
            heading = re.fullmatch(r"##\s+(.*?)\s*#*\s*", line)
            in_demo = heading is not None and heading.group(1) == DEMO_HEADING
    if in_demo:
        raise RunError(DEMO_MISSING)
    return None


def demo_command_problem(text: str) -> str | None:
    """Why the spec's demo cannot be recorded, or None (also with no demo)."""
    try:
        command = spec_demo_command(text)
    except RunError as exc:
        return str(exc)
    problem = verify_command_problem(command) if command else None
    return f"the spec's '## Demo' command: {problem}" if problem else None


def printable(text: str) -> str:
    """Control characters as `\\xNN`, so a transcript cannot move the cursor or clear a screen."""
    return "".join(char if char.isprintable() or char in "\n\t" else
                   f"\\x{ord(char):02x}" if ord(char) < 256 else f"\\u{ord(char):04x}" for char in text)


def demo_transcript(command: str, exit_code: int, timed_out: bool, stdout: str, stderr: str,
                    repo: Path) -> tuple[str, int, bool]:
    """The transcript an operator replays: the command, each stream cut to DEMO_STREAM_LIMIT, and
    the exit status. Secret-like text becomes a marker, local paths become repo-relative or ~, and
    control characters are escaped. Returns (text, secret redactions, whether a stream was cut)."""
    redactions, truncated = 0, False

    def redact(value: str) -> str:
        nonlocal redactions
        value = without_local_paths(value, repo)
        for name, pattern in DEMO_SECRET_PATTERNS:
            value, count = pattern.subn(f"[redacted: {name}]", value)
            redactions += count
        return printable(value)

    def clean(value: str) -> str:
        nonlocal truncated
        size = len(value)
        value = redact(value[:4 * DEMO_STREAM_LIMIT])  # bound the work; the final cut follows
        if len(value) > DEMO_STREAM_LIMIT:
            truncated = True
            # Redacted again: the cut can leave a value the first pass saw only as part of a longer one.
            value = (redact(value[:DEMO_STREAM_LIMIT])
                     + f"\n[agentsmith: output cut; {size} characters were printed, the first "
                     f"{DEMO_STREAM_LIMIT} are kept]")
        return value

    lines = clean(command).splitlines() or [""]
    status = f"exit status: {exit_code}" + (f" (timed out after {DEMO_TIMEOUT_SECONDS} s or the run's "
                                            "remaining budget)" if timed_out else "")
    text = "\n".join([f"$ {lines[0]}", *(f"> {line}" for line in lines[1:]), "--- stdout ---",
                      clean(stdout).rstrip("\n"), "--- stderr ---", clean(stderr).rstrip("\n"), status])
    return text + "\n", redactions, truncated


def record_demo(state: dict[str, Any], manifest: dict[str, Any], worktree: Path, commit: str) -> dict[str, Any] | None:
    """Run the spec's demo command on `commit` in the verifier sandbox and keep its transcript.
    Its exit status is shown, not judged: the verifier and the checker already decided."""
    command = state.get("demo_command")
    if not isinstance(command, str) or not command:
        return None
    run_dir = Path(state["state_path"]).parent
    prefix = f"attempt-{state['attempt']}-demo"
    archive_artifacts(run_dir, prefix)
    timeout = max(1, min(DEMO_TIMEOUT_SECONDS, remaining_seconds(state, manifest)))
    result = sandboxed_verify(command, worktree, timeout, verifier_env(), state=state, prefix=f"{prefix}-raw")
    for suffix in (".stdout", ".stderr"):  # no unredacted copy stays in the run folder
        (run_dir / f"{prefix}-raw{suffix}").unlink(missing_ok=True)
    # The disposable worktree reads as the repository: its paths become repo-relative too.
    stdout, stderr = (stream.replace(f"{worktree}/", "").replace(str(worktree), ".")
                      for stream in (result.stdout, result.stderr))
    text, redactions, truncated = demo_transcript(command, result.returncode, verifier_timed_out(result),
                                                  stdout, stderr, Path(state["repo"]))
    path = run_dir / f"{prefix}.txt"
    path.write_bytes(text.encode("utf-8"))
    record = {"command": command, "exit_code": result.returncode, "timed_out": verifier_timed_out(result),
              "file": path.name, "sha256": file_digest(path), "commit": commit, "truncated": truncated,
              "redactions": redactions}
    event(state, "demo_recorded", file=path.name, sha256=record["sha256"], exit_code=result.returncode,
          commit=commit)
    return record


def checked_demo(state: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """The run's recorded demo and its transcript text, after checking the file against its hash."""
    demo = state.get("demo")
    if not isinstance(demo, dict):
        return None, None
    name = str(demo.get("file"))
    path = Path(state["state_path"]).parent / name
    if not DEMO_FILE.fullmatch(name) or file_digest(path) != demo.get("sha256"):
        raise RunError(f"the demo transcript {name} changed after the controller recorded it")
    return demo, path.read_text(encoding="utf-8")


def evidence_opened(state: dict[str, Any], sha256: str) -> bool:
    """Whether `evidence` showed the operator this exact transcript."""
    try:
        lines = (Path(state["state_path"]).parent / "events.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get("event") == "evidence_opened" and record.get("sha256") == sha256:
            return True
    return False


def evidence_cmd(args: argparse.Namespace) -> int:
    """Show a run's demo transcript and record that the operator opened it."""
    repo = repo_root(Path.cwd())
    state = load_run(repo, args.run_id)
    if state.get("status") not in {"accepted", "awaiting-human"}:
        raise RunError(f"evidence: run {args.run_id} is {state.get('status')}; the controller records a demo "
                       "transcript only when a run is accepted or held for a human")
    try:
        demo, text = checked_demo(state)
    except RunError as exc:
        raise RunError(f"evidence refused: {exc}") from None
    if demo is None or text is None:
        raise RunError(f"run {args.run_id} has no demo transcript: its accepted spec declares no "
                       "'## Demo' section, so the landing carries no replayable demonstration")
    print(f"demo transcript of run {args.run_id}: {demo['file']} (sha256 {demo['sha256']}), recorded by the "
          f"controller from commit {demo['commit']}")
    print(text, end="")
    event(state, "evidence_opened", artefact=demo["file"], sha256=demo["sha256"], commit=demo["commit"])
    print(f"recorded: evidence_opened for {demo['file']}")
    return 0


def delivery_demo(state: dict[str, Any]) -> dict[str, Any] | None:
    """The demo record for `deliver`, with whether the operator opened it before this check."""
    try:
        demo, text = checked_demo(state)
    except RunError as exc:
        raise RunError(f"deliver refused: {exc}") from None
    if demo is None or text is None:
        return None
    return {**demo, "opened_before_delivery": evidence_opened(state, str(demo["sha256"])),
            "evidence_command": f"autonomous-run.py evidence {state['run_id']}",
            "excerpt": text if len(text) <= DEMO_BODY_LIMIT else
            text[:DEMO_BODY_LIMIT] + "\n[agentsmith: cut here; the full transcript is in the run folder]"}


def demo_lines(demo: dict[str, Any] | None) -> list[str]:
    """The body's Demo section: the controller's transcript, or a plain statement that none exists."""
    if demo is None:
        return ["### Demo", "None: the accepted spec declares no `## Demo` command, so this landing carries no "
                "replayable demonstration of the changed behaviour.", ""]
    return ["### Demo",
            f"The controller ran the accepted spec's demo command on `{demo['commit']}` in the verifier sandbox: "
            f"exit {demo['exit_code']}{' (timed out)' if demo.get('timed_out') else ''}. Transcript "
            f"`{demo['file']}`, sha256 `{demo['sha256']}`, in the run folder; replay it with "
            f"`{demo['evidence_command']}`. "
            + ("The operator opened it before this check." if demo["opened_before_delivery"] else
               "The operator had not opened it before this check."),
            fenced(demo["excerpt"]), ""]


def delivery_body(checks: dict[str, Any], verdict: dict[str, Any]) -> str:
    state, proof, checker, manifest = checks["state"], checks["proof"], checks["checker"], checks["manifest"]
    tier, limits, staleness = checks["tier"], manifest.get("limits") or {}, checks["staleness"]
    calibration, merge = checks["calibration"], checks["merge_verification"]
    lines = [
        f"## Autonomous run {state['run_id']}",
        "",
        f"Implementation ticket: {manifest.get('implementation_ticket')}. Accepted commit `{checks['accepted']}` "
        f"on base `{state.get('base_head')}`.",
        "",
        "### Changed paths",
        fenced("\n".join(f"- {path}" for path in checks["paths"])),
        "",
        "### Risk",
        f"Tier **{tier['tier']}** (recorded {tier['recorded']}, recomputed now {tier['recomputed']}, "
        f"declared {tier['declared'] or 'none'}). Lenses: {', '.join(tier['lenses']) or 'none'}. "
        f"Policy blob at the base: `{tier['policy_blob'] or 'none'}`.",
        "",
        *reviewer_focus_lines(checks),
        "### Verification",
        f"Verifier exit {proof.get('exit_code')}; output `{proof.get('output_sha256')}`; "
        f"{len(proof.get('evidence_files') or {})} evidence file(s) recorded by hash.",
        "",
        "### Checker",
        f"Status {checker.get('status')}; every citation was checked at acceptance, and the ones that quote "
        "the verifier log were checked again now.",
        fenced("\n".join(f"- {item}" for item in checker.get("evidence", []))),
        "",
        *assumption_lines(checks),
        "### Calibration",
        f"Checker calibration: {calibration.get('status')}"
        + (f" ({calibration.get('calibrated_at')})" if calibration.get("calibrated_at") else "") + "."
        + ("" if calibration.get("status") == "passed" else
           " This makes it checker advisory: its acceptance is advice, not a gate, so a human reviews the "
           "change before it lands."),
        "",
        *models_used_lines(checks),
        "### Budgets used",
        f"Attempts: {state.get('attempt')} of {limits.get('max_attempts')}. Claude: "
        f"{float(state.get('claude_cost_usd', 0.0)):.2f} USD of {limits.get('claude_max_usd')}. Codex: "
        f"{state.get('codex_tokens_used')} tokens of {limits.get('codex_goal_tokens')}.",
        "",
        # A maker chose these names, so they sit in a code block like the checker evidence.
        *(["### Dependencies", "New packages and their registry lookup (local ones are not looked up):",
           fenced("\n".join(f"- {row['name']}{' -> ' + row['lookup'] if 'lookup' in row else ''} "
                             f"({row['ecosystem']}, {row['status']})" for row in checks["packages"])),
           ""] if checks["packages"] else []),
        "### Base",
        f"{staleness['behind']} commit{'s' if staleness['behind'] != 1 else ''} behind {staleness['base']}; "
        "the accepted diff applies cleanly."
        + (f" The merge with {merge['base']} passed verification (exit {merge['exit_code']}; output "
           f"`{merge['output_sha256']}`)." if merge.get("needed") else ""),
        "",
        *demo_lines(checks.get("demo")),
        verdict["line"],
        "",
        "Auto-merge eligibility is information only: a human merges this pull request, and nothing in this "
        "release merges automatically.",
    ]
    return "\n".join(lines) + "\n"


def deliver(args: argparse.Namespace) -> int:
    """Check an accepted run and print its push command and pull-request text; never push."""
    if not args.dry_run and not args.eligibility:
        raise RunError("deliver only checks and prints: pass --dry-run, or --eligibility --sha <sha> --pr <number> "
                       "after CI; the controller never pushes")
    if args.eligibility and not (args.sha and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", args.sha)):
        raise RunError("--eligibility needs --sha with the full lowercase commit SHA that CI ran")
    if args.eligibility and not (args.pr or args.ci_report):
        raise RunError("--eligibility needs --pr <number> or --ci-report <file>: CI counts only for the pull "
                       "request's own branch")
    repo = repo_root(Path.cwd())
    checks = delivery_checks(repo, load_run(repo, args.run_id), args.remote, args.base_branch)
    checks["demo"] = delivery_demo(checks["state"])
    sha = args.sha if args.eligibility else checks["accepted"]
    ci: dict[str, Any] | None = None
    pushed: dict[str, Any] | None = None
    if args.eligibility:
        head, error = remote_head(repo, args.remote, checks["branch"])
        pushed = {"remote": args.remote, "head": head, "error": error,
                  "repository": github_repository(repo, args.remote)}
        if args.ci_report:
            ci = load_json(Path(args.ci_report))
        else:
            import ci_watch  # read-only GitHub reads through gh, as `agentsmith ci watch` does
            try:
                ci = ci_watch.watch(ci_watch.Gh(), pushed["repository"], pr=args.pr)
            except ci_watch.GhError as exc:
                raise RunError(f"ci watch could not run: {exc}") from None
    verdict = eligibility(checks, sha, ci, pushed)
    # Only structured receipt fields, with no local path; of the maker's report only its assumptions, fenced.
    title = without_local_paths(f"{checks['manifest'].get('implementation_ticket')}: {checks['branch']}", repo)[:72]
    body = without_local_paths(delivery_body(checks, verdict), repo)
    if len(body) > PR_BODY_MAX_CHARS:
        raise RunError(f"deliver refused: the pull-request body has {len(body)} characters, over the "
                       f"{PR_BODY_MAX_CHARS} that GitHub accepts; shorten the checker evidence or the changed "
                       "paths in a rework")
    leaks = leak_problems({"title": title, "body": body}, secret_allow_rules(repo))
    if leaks:
        raise RunError("deliver refused: " + "; ".join(leaks))
    calibration = {key: value for key, value in checks["calibration"].items() if key != "receipt"}
    report = {"run_id": args.run_id, "head": checks["accepted"], "branch": checks["branch"],
              "push_command": push_command(args.remote, checks["accepted"], checks["branch"]),
              "title": title, "body": body, "tier": checks["tier"],
              "staleness": checks["staleness"], "merge_verification": checks["merge_verification"],
              "packages": checks["packages"], "calibration": calibration,
              "eligibility": verdict,
              "demo": ({**{key: value for key, value in checks["demo"].items() if key != "excerpt"},
                        "command": without_local_paths(str(checks["demo"]["command"]), repo)}
                       if checks["demo"] else None)}
    # The delivery record: whether the operator opened the demo before this consent step.
    demo = checks["demo"]
    event(checks["state"], "delivery_checked", mode="eligibility" if args.eligibility else "dry-run", head=sha,
          evidence_opened=bool(demo and demo["opened_before_delivery"]),
          evidence_sha256=demo["sha256"] if demo else None)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    print(f"deliver {args.run_id}: ready; nothing was pushed")
    print(f"push: {report['push_command']}")
    print(f"title: {title}")
    print("body:")
    print(report["body"], end="")
    return 0


# Checker calibration: the configured checker client and model judge two built-in candidates with
# known labels. A clean change must be accepted with valid citations; a change whose tests pass
# but which breaks the spec (an injected defect the verifier cannot see) must be rejected.
CALIBRATION_SPEC = """# Spec: add two numbers

`src/calc.py` defines `add(a, b)`, which returns the sum of `a` and `b` for any integers.

Acceptance criteria:
1. `add(2, 3)` returns 5 and `add(-1, 1)` returns 0.
2. A test in `tests/test_calc.py` checks the sum.
"""
CALIBRATION_TEST = """import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from calc import add


class AddTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add({left}, {right}), {result})


if __name__ == "__main__":
    unittest.main()
"""
CALIBRATION_CANDIDATES = (
    # label, expected verdict, implementation, (left, right, result) for its own test
    ("clean", "accepted", "def add(a, b):\n    return a + b\n", (2, 3, 5)),
    ("defect", "rejected", "def add(a, b):\n    return a * b\n", (2, 2, 4)),
)
CALIBRATION_VERIFY = "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v"


def calibration_manifest(checker: dict[str, Any], limits: dict[str, Any]) -> dict[str, Any]:
    return {"run_id": "checker-calibration", "implementation_ticket": "CALIBRATION",
            "spec_path": "docs/specs/calc.md", "verify": {"command": CALIBRATION_VERIFY},
            "scope": {"allowed_paths": ["src/**", "tests/**"], "denied_paths": [], "resources": []},
            "roles": {"checker": dict(checker)}, "limits": dict(limits)}


def checker_prompt_sha256() -> str:
    """The checker prompt template with fixed inputs: it changes only when the prompt does."""
    state = {"run_id": "checker-calibration", "base_head": "0" * 40, "attempt": 1}
    manifest = calibration_manifest({}, {})
    return hashlib.sha256(role_prompt(state, manifest, "checker").encode("utf-8")).hexdigest()


# Wrong verdicts the held-out set may hold before the calibration fails.
CALIBRATION_ERROR_BUDGET = 0
CALIBRATION_SCHEMA = 2
CALIBRATION_FIELDS = ("model_family", "model_version", "held_out_sha256", "n", "pass_rate", "error_budget")
# A calibration record is a few kilobytes; a larger file is not read.
CALIBRATION_MAX_BYTES = 1 << 20


def model_identity(model: str) -> tuple[str, str]:
    """A model name as family and version: `claude-opus-5-5` is `claude-opus` and `5-5`, `gpt-5.4` is
    `gpt` and `5.4`. The version starts at the first part that begins with a digit; a name with no
    such part (an alias such as `opus`, or `o3`) has an empty version."""
    match = re.fullmatch(r"(.+?)[-_.@:](\d.*)", model)
    return (match.group(1), match.group(2)) if match else (model, "")


def calibration_set_sha256() -> str:
    """The held-out set: the labelled candidates, their spec, test and verify command."""
    return hashlib.sha256(json.dumps([CALIBRATION_SPEC, CALIBRATION_TEST, CALIBRATION_VERIFY,
                                      CALIBRATION_CANDIDATES]).encode("utf-8")).hexdigest()


def calibration_path(repo: Path, runtime: str, model: str, effort: str) -> Path:
    """Keyed by the model family, not its version, so a new version finds the old record and
    reads it as stale instead of as missing."""
    key = hashlib.sha256(json.dumps([runtime, model_identity(model)[0], effort,
                                     checker_prompt_sha256()]).encode()).hexdigest()
    return state_root(repo).parent / "agentsmith-calibrations" / f"{key[:32]}.json"


def calibration_record(checker: dict[str, Any], cases: list[dict[str, Any]], *, client_version: str,
                       usage: dict[str, Any]) -> dict[str, Any]:
    """What `calibrate` writes: the verdicts scored as a pass rate over N against the error budget."""
    family, version = model_identity(str(checker.get("model")))
    wrong = sum(1 for case in cases if not case.get("correct"))
    errors = any(case.get("verdict") == "error" for case in cases)
    status = ("error" if errors or not cases else "passed" if wrong <= CALIBRATION_ERROR_BUDGET
              else "failed")
    return {"schema_version": CALIBRATION_SCHEMA, "status": status, "calibrated_at": now(),
            "client": checker.get("runtime"), "model": checker.get("model"), "effort": checker.get("effort"),
            "model_family": family, "model_version": version, "client_version": client_version,
            "checker_prompt_sha256": checker_prompt_sha256(), "held_out_sha256": calibration_set_sha256(),
            "n": len(cases), "pass_rate": round((len(cases) - wrong) / len(cases), 3) if cases else 0.0,
            "error_budget": CALIBRATION_ERROR_BUDGET, "cases": cases, **usage}


def read_calibration_file(path: Path) -> bytes | None:
    """The record's bytes, or None when there is no file. A symbolic link, anything that is not a
    regular file, and a file over the size cap raise instead of being read."""
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(mode):
        raise OSError(f"not a regular file: {path}")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
                         | getattr(os, "O_BINARY", 0))
    with os.fdopen(descriptor, "rb") as handle:
        # A file swapped in after the check: O_NOFOLLOW refuses a link, and this anything else.
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise OSError(f"not a regular file: {path}")
        data = handle.read(CALIBRATION_MAX_BYTES + 1)
    if len(data) > CALIBRATION_MAX_BYTES:
        raise OSError(f"over {CALIBRATION_MAX_BYTES} bytes: {path}")
    return data


def calibration_score_problem(record: dict[str, Any]) -> str | None:
    """Why a `passed` record's score does not bear out its status, if it does not: N of at least
    one, one case per N, wrong verdicts within the controller's error budget, and the pass rate
    `calibration_record` gives them. A record cannot raise its own budget."""
    n, cases = record.get("n"), record.get("cases")
    if type(n) is not int or n < 1:
        return f"n is {n!r}, not a count of at least 1"
    if not isinstance(cases, list) or len(cases) != n or not all(isinstance(case, dict) for case in cases):
        return f"the record does not hold {n} case records"
    if type(record.get("error_budget")) is not int or record["error_budget"] != CALIBRATION_ERROR_BUDGET:
        return f"error budget {record.get('error_budget')!r}, the controller's is {CALIBRATION_ERROR_BUDGET}"
    wrong = sum(1 for case in cases if not case.get("correct"))
    if wrong > CALIBRATION_ERROR_BUDGET:
        return f"{wrong} wrong verdicts, over the error budget of {CALIBRATION_ERROR_BUDGET}"
    if record.get("pass_rate") != round((n - wrong) / n, 3):
        return f"pass rate {record.get('pass_rate')!r} for {n - wrong} of {n} right"
    return None


def calibration_status(repo: Path, checker: dict[str, Any]) -> dict[str, Any]:
    """The latest calibration for this checker client, model family, effort and prompt. Only
    `passed` lets a checker acceptance count; every other value leaves the checker advisory:
    "stale" (a record for another checker, model version or held-out set, or one that does not
    name them), "invalid" (a `passed` whose score does not bear it out) and "unreadable" (not a
    small regular JSON file). No content of the file, and no error reading it, may stop a run."""
    try:
        path = calibration_path(repo, str(checker.get("runtime")), str(checker.get("model")),
                                str(checker.get("effort")))
        data = read_calibration_file(path)
        if data is None:
            return {"status": "none"}
        record = json.loads(data.decode("utf-8"))
        if not isinstance(record, dict) or record.get("status") not in {"passed", "failed", "error"}:
            return {"status": "unreadable"}
        status = {"status": record["status"], "calibrated_at": str(record.get("calibrated_at")),
                  "client_version": str(record.get("client_version")),
                  **{key: record.get(key) for key in CALIBRATION_FIELDS}, "receipt": str(path)}
        family, version = model_identity(str(checker.get("model")))
        identity = {"client": checker.get("runtime"), "effort": checker.get("effort"),
                    "checker_prompt_sha256": checker_prompt_sha256(), "model_family": family}
        missing = [key for key in CALIBRATION_FIELDS if key not in record]
        other = [key for key, value in identity.items() if key not in record or record[key] != value]
        if record.get("schema_version") != CALIBRATION_SCHEMA or missing:
            stale = ("the record does not name the model version and held-out set it calibrated"
                     + (f" (missing {', '.join(missing)})" if missing else ""))
        elif other:
            stale = f"the record calibrated another checker: {', '.join(other)} differ"
        elif record["model_version"] != version:
            stale = (f"calibrated model version {record['model_version'] or 'none'}, "
                     f"configured {version or 'none'}")
        elif record["held_out_sha256"] != calibration_set_sha256():
            stale = "the held-out set changed since this calibration"
        elif record["status"] == "passed" and (problem := calibration_score_problem(record)):
            return {**status, "status": "invalid", "invalid_reason": problem}
        else:
            return status
        return {**status, "status": "stale", "stale_reason": stale}
    except Exception:  # never let a calibration file stop a run: it reads "unreadable"
        return {"status": "unreadable"}


def calibration_fixture(root: Path) -> tuple[Path, str, dict[str, str]]:
    repo = root / "fixture"
    repo.mkdir()
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}

    def fixture_git(*args: str) -> str:
        result = subprocess.run(["git", "-c", "user.name=AgentSmith calibration",
                                 "-c", "user.email=user@example.com", "-c", "commit.gpgsign=false",
                                 *args], cwd=repo, env=environment, capture_output=True, text=True, check=False)
        if result.returncode:
            raise RunError(f"cannot build the calibration fixture: {result.stderr.strip()}")
        return result.stdout.strip()

    fixture_git("init", "-q")
    (repo / "docs/specs").mkdir(parents=True)
    (repo / "docs/specs/calc.md").write_text(CALIBRATION_SPEC, encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src/calc.py").write_text("def add(a, b):\n    raise NotImplementedError\n", encoding="utf-8")
    fixture_git("add", "-A")
    fixture_git("commit", "-qm", "calibration: spec and stub")
    base = fixture_git("rev-parse", "HEAD")
    heads = {}
    for label, _expected, implementation, (left, right, result) in CALIBRATION_CANDIDATES:
        fixture_git("checkout", "-q", "--detach", base)
        (repo / "src/calc.py").write_text(implementation, encoding="utf-8")
        (repo / "tests").mkdir(exist_ok=True)
        (repo / "tests/test_calc.py").write_text(
            CALIBRATION_TEST.format(left=left, right=right, result=result), encoding="utf-8")
        fixture_git("add", "-A")
        fixture_git("commit", "-qm", f"calibration: {label} candidate")
        heads[label] = fixture_git("rev-parse", "HEAD")
    fixture_git("checkout", "-q", "--detach", base)
    return repo, base, heads


def calibrate_case(repo: Path, base: str, head: str, label: str, attempt: int, manifest: dict[str, Any],
                   usage: dict[str, Any]) -> dict[str, Any]:
    worktree = repo.parent / f"candidate-{label}"
    added = run(["git", "worktree", "add", "-q", "--detach", str(worktree), head], repo)
    if added.returncode:
        raise RunError(f"cannot create the {label} calibration worktree: {added.stderr.strip()}")
    run_dir = state_root(repo) / "checker-calibration"
    run_dir.mkdir(parents=True, exist_ok=True)
    state = {"run_id": "checker-calibration", "repo": str(repo), "worktree": str(worktree),
             "state_path": str(run_dir / "state.json"), "manifest_path": str(repo / "manifest.json"),
             "spec_path": manifest["spec_path"], "base_head": base, "attempt": attempt,
             "deadline_epoch": time.time() + int(manifest["limits"]["wall_minutes"]) * 60,
             "claude_cost_usd": usage["claude_cost_usd"], "codex_tokens_used": usage["codex_tokens_used"],
             "active_pid": None}
    verify = sandboxed_verify(CALIBRATION_VERIFY, worktree, 300, verifier_env(), state=state)
    verify_output = f"exit={verify.returncode}\nSTDOUT:\n{verify.stdout}\nSTDERR:\n{verify.stderr}"
    verify_log = run_dir / f"attempt-{attempt}-verify.txt"
    verify_log.write_text(verify_output, encoding="utf-8")
    evidence = verifier_evidence(verify_log, worktree, ignored_paths(worktree))
    outcome: dict[str, Any] = {"label": label, "candidate": head, "verify_exit": verify.returncode}
    try:
        receipt = launch_role(state, manifest, "checker",
                              role_prompt(state, manifest, "checker", verify_output=verify_output,
                                          evidence_files=sorted(evidence)),
                              role_worktree=worktree)
    except RunError as exc:
        outcome.update(verdict="error", detail=str(exc)[:300])
        receipt = None
    finally:
        usage.update(claude_cost_usd=state.get("claude_cost_usd", 0.0),
                     codex_tokens_used=state.get("codex_tokens_used", 0))
    if receipt is not None:
        changed = changed_paths(worktree, base)
        if git(worktree, "rev-parse", "HEAD") != head or git(worktree, "status", "--porcelain"):
            outcome.update(verdict="changed-worktree", detail="the checker changed its worktree")
        elif receipt["commit"] != head or sorted(receipt["changed_paths"]) != sorted(changed):
            # A receipt that does not name the candidate is the checker's mistake, not the host's.
            outcome.update(verdict="invalid-receipt", detail=(
                f"the checker receipt names {receipt['commit'][:12]} with {receipt['changed_paths']}; "
                f"the candidate is {head[:12]} with {changed}")[:300])
        elif receipt["status"] == "accepted":
            defect = ((checker_report_defect(receipt) or citation_problem(receipt, evidence, verify_log, worktree, attempt))
                      if acceptance_ready(verify.returncode, receipt) else "acceptance is not ready")
            outcome.update(verdict="accepted-without-valid-evidence" if defect else "accepted",
                           **({"detail": defect} if defect else {}))
        else:
            outcome.update(verdict=receipt["status"])
        outcome["receipt_sha256"] = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
    run(["git", "worktree", "remove", "--force", str(worktree)], repo)
    return outcome


def calibrate(args: argparse.Namespace) -> int:
    """Run the configured checker against the labelled candidates and record the result. Until a
    record for this checker reads `passed`, its acceptances are advisory and a run that would be
    accepted waits for a human. 0 passed, 1 failed, 2 could not run."""
    repo = repo_root(Path.cwd())
    assert_autonomy_not_paused(repo, action="calibrate")
    manifest = load_json(Path(args.manifest).resolve())
    checker = (manifest.get("roles") or {}).get("checker") or {}
    if checker.get("runtime") not in {"claude", "codex"}:
        raise RunError("roles.checker.runtime must be claude or codex")
    unset = [f"roles.checker.{key}" for key in ("model", "effort")
             if not isinstance(checker.get(key), str) or PLACEHOLDER_SETTING.search(checker[key])]
    if unset:
        raise RunError(f"{', '.join(unset)} must be explicit before calibration")
    limits = {"max_attempts": 1, "wall_minutes": args.wall_minutes,
              "claude_max_usd": args.max_usd, "codex_goal_tokens": args.max_tokens}
    cal_manifest = calibration_manifest(checker, limits)
    validate_budgets({"limits": limits, "roles": {"checker": checker}})
    require_native_role_sandbox()
    usage = {"claude_cost_usd": 0.0, "codex_tokens_used": 0}
    with tempfile.TemporaryDirectory(prefix="agentsmith-calibration-") as temporary:
        fixture, base, heads = calibration_fixture(Path(temporary).resolve())
        cases = []
        for attempt, (label, expected, _implementation, _test) in enumerate(CALIBRATION_CANDIDATES, 1):
            outcome = calibrate_case(fixture, base, heads[label], label, attempt, cal_manifest, usage)
            outcome.update(expected=expected, correct=outcome["verdict"] == expected)
            cases.append(outcome)
    record = calibration_record(checker, cases, client_version=client_version(native_command_prefix(checker["runtime"])),
                                usage=usage)
    status = record["status"]
    path = calibration_path(repo, checker["runtime"], checker["model"], checker["effort"])
    write_json(path, record)
    for case in cases:
        print(f"{case['label']}: expected {case['expected']}, checker {case['verdict']}"
              + (f" ({case['detail']})" if case.get("detail") else ""))
    print(f"calibration {status}: {path}")
    return {"passed": 0, "failed": 1}.get(status, 2)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Finite local Claude/Codex maker-checker runs")
    sub = result.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="create a non-executing run manifest")
    prep.add_argument("--run-id", required=True)
    prep.add_argument("--spec", required=True)
    prep.add_argument("--ticket", required=True)
    prep.add_argument("--maker", choices=["claude", "codex"])
    prep.add_argument("--checker", choices=["claude", "codex"])
    prep.add_argument("--maker-model", help="exact model name for the maker role")
    prep.add_argument("--checker-model", help="exact model name for the checker role")
    prep.add_argument("--template")
    prep.add_argument("--output")
    prep.add_argument("--force", action="store_true")
    prep.add_argument("--rework-of", help="a finished run this new run reworks")
    prep.add_argument("--note", help="the operator's rework note, a file in the repository (with --rework-of)")
    prep.set_defaults(func=prepare)
    specs = sub.add_parser("check-specs", help="pipeline guard: accepted specs point at their "
                                              "research and review receipt and record a route")
    specs.add_argument("paths", nargs="*", help="specs to check whatever their status "
                                                "(default: every accepted spec under docs/specs)")
    specs.set_defaults(func=check_specs)
    begin = sub.add_parser("start", help="explicitly authorize and run a committed manifest")
    begin.add_argument("manifest")
    begin.add_argument("--graph", help="committed work-graph path authorizing a pinned effective base")
    begin.add_argument("--effective-base", help="exact graph-owned root or dependency checkpoint commit OID")
    begin.set_defaults(func=start)
    landing = sub.add_parser("deliver", help="check an accepted run and print its push command and pull-request "
                                             "text; it never pushes")
    landing.add_argument("run_id")
    landing.add_argument("--dry-run", action="store_true", help="check the run and print what landing needs")
    landing.add_argument("--eligibility", action="store_true",
                         help="re-evaluate the auto-merge eligibility line after CI for --sha")
    landing.add_argument("--sha", help="the full commit SHA that CI ran (with --eligibility)")
    landing.add_argument("--pr", type=int, help="the pull request whose CI to watch (with --eligibility)")
    landing.add_argument("--ci-report", help="a saved `agentsmith ci watch --pr <number> --json` report, "
                                             "instead of --pr")
    landing.add_argument("--remote", default="origin")
    landing.add_argument("--base-branch", help="the branch the pull request targets (default: the remote's HEAD)")
    landing.add_argument("--json", action="store_true")
    landing.set_defaults(func=deliver)
    shown = sub.add_parser("evidence", help="show an accepted or held run's demo transcript and record that "
                                            "the operator opened it")
    shown.add_argument("run_id")
    shown.set_defaults(func=evidence_cmd)
    calibration = sub.add_parser("calibrate", help="judge two labelled candidates with the configured "
                                                     "checker and record the result (record-only)")
    calibration.add_argument("manifest", help="a run manifest whose roles.checker names the client and model")
    calibration.add_argument("--max-usd", type=float, default=1.0, help="Claude spend cap for the calibration")
    calibration.add_argument("--max-tokens", type=int, default=400000, help="Codex token cap for the calibration")
    calibration.add_argument("--wall-minutes", type=int, default=20)
    calibration.set_defaults(func=calibrate)
    for name, func in (("status", status_cmd), ("stop", stop), ("resume", resume)):
        item = sub.add_parser(name)
        item.add_argument("run_id", nargs="?" if name == "status" else None)
        item.set_defaults(func=func)
        if name == "status":
            item.add_argument("--all-terminal", action="store_true",
                              help="read-only guard: exit 0 if every run and graph is terminal, "
                                   "1 if any is live or unfinished, 2 if that cannot be told")
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
