#!/usr/bin/env python3
"""Record native work-graph lifecycle checks and bind three hosts to one Git tree."""

from __future__ import annotations

import argparse
import builtins
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = ("macos", "linux", "windows")
PHASES = (
    ("contracts", "scripts/test-work-graph-contracts.py", 6),
    ("status", "scripts/test-work-graph-status.py", 6),
    ("base", "scripts/test-autonomous-graph-base.py", 6),
    ("cli", "scripts/test-work-graph-cli-surface.py", 2),
    ("coordination", "scripts/test-autonomous-state.py", 20),
    ("secret-scan", "scripts/test-secret-scan.py", 10),
    ("lifecycle", "scripts/test-work-graph-dispatch.py", 10),
)
SECURITY_COVERAGE = (
    "command-injection", "path-traversal", "symlink-escape", "plan-state-tampering",
    "ref-mutation", "config-hook-mutation", "object-store-mutation", "secret-redaction",
    "foreign-file-preservation", "cross-worktree-interference", "source-retention",
    "authority-boundary",
)
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
TEST_RESULT = re.compile(r"Ran (\d+) tests? in ")
FAILED_TEST = re.compile(r"(?m)^(?:FAIL|ERROR): (test_[A-Za-z0-9_]{1,128}) \([A-Za-z0-9_.]+\)\r?$")


class EvidenceError(RuntimeError):
    pass


def environment() -> dict[str, str]:
    value = os.environ.copy()
    for key in tuple(value):
        if key.startswith(("GIT_", "PYTHON")):
            value.pop(key)
    value.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_GLOBAL=os.devnull,
                 GIT_CONFIG_NOSYSTEM="1", GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    return value


def git(*args: str) -> str:
    # Match actions/checkout's Windows CRLF normalization without trusting global config.
    result = subprocess.run(["git", "-c", "core.autocrlf=true", *args], cwd=ROOT,
                            env=environment(), capture_output=True, check=False)
    if result.returncode:
        raise EvidenceError(f"Git observation failed: {' '.join(args)}")
    return result.stdout.decode("utf-8", errors="replace").strip()


def checked_output(path: Path, root: Path) -> Path:
    lexical_root = Path(os.path.abspath(root.expanduser()))
    lexical_path = Path(os.path.abspath(path.expanduser()))
    if not lexical_root.is_dir():
        raise EvidenceError("output root must be an existing directory")
    try:
        relative = lexical_path.relative_to(lexical_root)
    except ValueError as exc:
        raise EvidenceError("output must stay inside output root") from exc
    if relative == Path(".") or not relative.name:
        raise EvidenceError("output must name a file")
    current = lexical_root
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink() or not current.is_dir():
            raise EvidenceError("output parent must be an existing real directory")
    output = lexical_root.resolve() / relative
    if output.exists() or output.is_symlink():
        raise EvidenceError("refusing to overwrite evidence")
    if output.resolve().is_relative_to(ROOT.resolve()):
        raise EvidenceError("evidence output must be outside the repository")
    return output


def write_json(path: Path, value: dict[str, Any]) -> None:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() or path.is_symlink():
            raise EvidenceError("refusing to overwrite evidence")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def failure_labels(stderr: str) -> list[str]:
    """Expose bounded unittest names, never exception messages or raw process output."""
    return sorted(set(FAILED_TEST.findall(stderr)))[:8]


def failure_diagnostics(stage: str, stderr: str) -> list[dict[str, Any]]:
    """Extract only trusted unittest coordinates; discard traceback paths and messages."""
    if stage not in {label for label, _, _ in PHASES}:
        raise EvidenceError("unknown native phase")
    script = next(path for label, path, _ in PHASES if label == stage).split("/")[-1]
    headers = list(FAILED_TEST.finditer(stderr))
    failures: list[dict[str, Any]] = []
    for index, header in enumerate(headers[:8]):
        name = header.group(1)
        block = stderr[header.end():headers[index + 1].start() if index + 1 < len(headers) else len(stderr)]
        line = None
        for frame in re.finditer(r'(?m)^\s*File "([^"\r\n]+)", line ([1-9][0-9]{0,5}), in (test_[A-Za-z0-9_]{1,128})\r?$', block):
            if re.split(r"[\\/]", frame.group(1))[-1] == script and frame.group(3) == name:
                line = int(frame.group(2))
        exception = "unknown"
        for candidate in re.findall(r"(?m)^([A-Za-z_][A-Za-z0-9_]{0,63})(?::|$)", block):
            value = getattr(builtins, candidate, None)
            if isinstance(value, type) and issubclass(value, BaseException):
                exception = candidate
        failures.append({"test": name, "stage": stage, "line": line, "exception": exception})
    return failures


def native_platform() -> str:
    system = platform.system().lower()
    value = {"darwin": "macos", "linux": "linux", "windows": "windows"}.get(system)
    if value is None:
        raise EvidenceError(f"unsupported native platform: {system}")
    return value


def record(output: Path, output_root: Path, expected_commit: str) -> None:
    output = checked_output(output, output_root)
    commit = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    if not HEX40.fullmatch(expected_commit) or commit != expected_commit or not HEX40.fullmatch(tree):
        raise EvidenceError("checkout does not match expected commit")
    if git("status", "--porcelain=v1", "--untracked-files=all"):
        raise EvidenceError("native report requires a clean checkout")
    phase_results: list[dict[str, Any]] = []
    status = "passed"
    for label, script, minimum in PHASES:
        completed = subprocess.run([sys.executable, script], cwd=ROOT, env=environment(),
                                   capture_output=True, check=False)
        stderr = completed.stderr.decode("utf-8", errors="replace")
        matches = TEST_RESULT.findall(stderr)
        count = int(matches[-1]) if matches else 0
        phase_results.append({"label": label, "command": ["python", script],
                              "exit_code": completed.returncode, "tests_run": count,
                              "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
                              "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
                              "failures": failure_diagnostics(label, stderr)})
        if completed.returncode or count < minimum or not re.search(r"(?m)^OK(?:\s|$)", stderr) or "skipped=" in stderr:
            for failure in phase_results[-1]["failures"]:
                print(f"native phase {failure['stage']} failed test: {failure['test']} "
                      f"line={failure['line']} exception={failure['exception']}", file=sys.stderr)
            if "skipped=" in stderr:
                print(f"native phase {label} contains skipped tests", file=sys.stderr)
            status = "failed"
            break
    dirty_after = bool(git("status", "--porcelain=v1", "--untracked-files=all"))
    if dirty_after:
        status = "failed"
    payload = {"schema_version": 1, "evidence_kind": "agentsmith-work-graph-native-platform",
               "status": status, "platform": native_platform(), "git_commit": commit, "git_tree": tree,
               "dirty_before": False, "dirty_after": dirty_after,
               "python_version": platform.python_version(), "recorded_at": timestamp(),
               "phases": phase_results, "external_write_used": False}
    write_json(output, payload)
    if status != "passed":
        raise EvidenceError(f"native work-graph phase failed; inspect report: {output}")
    print(output)


REPORT_KEYS = {"schema_version", "evidence_kind", "status", "platform", "git_commit", "git_tree",
               "dirty_before", "dirty_after", "python_version", "recorded_at", "phases",
               "external_write_used"}
PHASE_KEYS = {"label", "command", "exit_code", "tests_run", "stdout_sha256", "stderr_sha256", "failures"}


def read_report(path: Path) -> tuple[dict[str, Any], str]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
        raise EvidenceError(f"report must be a regular file under 1 MB: {path}")
    raw = path.read_bytes()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"invalid UTF-8 JSON report: {path}") from exc
    if not isinstance(payload, dict) or set(payload) != REPORT_KEYS:
        raise EvidenceError(f"invalid report shape: {path}")
    return payload, hashlib.sha256(raw).hexdigest()


def validate_report(payload: dict[str, Any], path: Path) -> None:
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise EvidenceError(f"unsupported report schema: {path}")
    if payload["evidence_kind"] != "agentsmith-work-graph-native-platform" or payload["status"] != "passed":
        raise EvidenceError(f"native lifecycle did not pass: {path}")
    if payload["platform"] not in PLATFORMS:
        raise EvidenceError(f"unsupported report platform: {path}")
    if any(not isinstance(payload[key], str) or not HEX40.fullmatch(payload[key])
           for key in ("git_commit", "git_tree")):
        raise EvidenceError(f"invalid Git binding: {path}")
    if payload["dirty_before"] is not False or payload["dirty_after"] is not False:
        raise EvidenceError(f"dirty checkout: {path}")
    if payload["external_write_used"] is not False:
        raise EvidenceError(f"report has external writes: {path}")
    if not isinstance(payload["python_version"], str) or not payload["python_version"]:
        raise EvidenceError(f"missing Python version: {path}")
    try:
        moment = dt.datetime.fromisoformat(payload["recorded_at"].replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError) as exc:
        raise EvidenceError(f"invalid report timestamp: {path}") from exc
    if moment.tzinfo is None:
        raise EvidenceError(f"report timestamp has no timezone: {path}")
    phases = payload["phases"]
    if not isinstance(phases, list) or len(phases) != len(PHASES):
        raise EvidenceError(f"incomplete phase set: {path}")
    for phase, (label, script, minimum) in zip(phases, PHASES, strict=True):
        if not isinstance(phase, dict) or set(phase) != PHASE_KEYS:
            raise EvidenceError(f"invalid phase: {path}")
        if phase["label"] != label or phase["command"] != ["python", script]:
            raise EvidenceError(f"tampered phase command: {path}")
        if type(phase["exit_code"]) is not int or phase["exit_code"] != 0 or \
                type(phase["tests_run"]) is not int or phase["tests_run"] < minimum:
            raise EvidenceError(f"phase did not fully pass: {path}")
        if any(not isinstance(phase[key], str) or not HEX64.fullmatch(phase[key])
               for key in ("stdout_sha256", "stderr_sha256")):
            raise EvidenceError(f"invalid phase output hash: {path}")
        if phase["failures"] != []:
            raise EvidenceError(f"passing phase contains failure diagnostics: {path}")


def aggregate(reports: list[Path], output: Path, output_root: Path, expected_commit: str) -> None:
    output = checked_output(output, output_root)
    if not HEX40.fullmatch(expected_commit):
        raise EvidenceError("expected commit must be a full Git identifier")
    if len(reports) != len(PLATFORMS) or len({os.path.normcase(os.path.abspath(p)) for p in reports}) != 3:
        raise EvidenceError("exactly three distinct native reports are required")
    by_platform: dict[str, dict[str, Any]] = {}
    digests: dict[str, str] = {}
    for path in reports:
        payload, digest = read_report(path)
        validate_report(payload, path)
        name = payload["platform"]
        if name in by_platform:
            raise EvidenceError(f"duplicate native platform: {name}")
        by_platform[name] = payload
        digests[name] = digest
    if set(by_platform) != set(PLATFORMS):
        raise EvidenceError("Linux, macOS, and Windows reports are required")
    if {report["git_commit"] for report in by_platform.values()} != {expected_commit}:
        raise EvidenceError("native reports do not match expected commit")
    trees = {report["git_tree"] for report in by_platform.values()}
    if len(trees) != 1 or trees != {git("rev-parse", f"{expected_commit}^{{tree}}")}:
        raise EvidenceError("native reports do not bind to the expected Git tree")
    value = {"schema_version": 1, "evidence_kind": "agentsmith-work-graph-native-aggregate",
             "status": "passed", "git_commit": expected_commit, "git_tree": next(iter(trees)),
             "platforms": list(PLATFORMS), "report_sha256": {name: digests[name] for name in PLATFORMS},
             "security_coverage": list(SECURITY_COVERAGE), "recorded_at": timestamp(),
             "external_write_used": False}
    write_json(output, value)
    print(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    for action in ("record", "aggregate"):
        command = subparsers.add_parser(action)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--output-root", type=Path, required=True)
        command.add_argument("--expected-commit", required=True)
        if action == "aggregate":
            command.add_argument("--report", action="append", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "record":
            record(args.output, args.output_root, args.expected_commit)
        else:
            aggregate(args.report, args.output, args.output_root, args.expected_commit)
    except (EvidenceError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
