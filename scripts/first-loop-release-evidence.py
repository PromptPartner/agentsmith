#!/usr/bin/env python3
"""Record and aggregate native release evidence for the First Verified Loop."""

from __future__ import annotations

import argparse
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
PLATFORMS = ("linux", "macos", "windows")
SECURITY_COVERAGE = (
    "command-injection",
    "path-traversal",
    "symlink-escape",
    "plan-tampering",
    "secret-redaction",
    "foreign-file-preservation",
    "git-state-safety",
)
PHASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "python-core",
        (
            "python",
            "-m",
            "py_compile",
            "agentsmith.py",
            "scripts/generate-first-loop-proof.py",
            "scripts/first-loop-release-evidence.py",
            "scripts/test-first-verified-loop-contracts.py",
        ),
    ),
    ("first-verified-loop-contracts", ("python", "scripts/test-first-verified-loop-contracts.py")),
    ("agent-conformance", ("python", "scripts/test-agent-conformance.py", "--strict")),
    ("update", ("python", "scripts/test-update.py")),
    ("registry", ("python", "compatibility/test_registry.py")),
    ("doctor", ("python", "scripts/test-doctor.py")),
    ("secret-scan", ("python", "scripts/test-secret-scan.py")),
    ("verify-receipts", ("python", "scripts/test-verify-receipts.py")),
)
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceError(RuntimeError):
    pass


def clean_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith(("GIT_", "PYTHON")):
            environment.pop(key)
    environment.update(
        {
            "PYTHONUTF8": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return environment


def run(arguments: list[str], *, environment: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        arguments,
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git(arguments: list[str], *, environment: dict[str, str]) -> str:
    # actions/checkout may populate a Windows worktree with CRLF under a global
    # core.autocrlf setting. The evidence environment intentionally ignores
    # global Git config, so restate that normalization explicitly when reading
    # the checkout or every converted text file appears modified.
    result = run(["git", "-c", "core.autocrlf=true", *arguments], environment=environment)
    if result.returncode != 0:
        raise EvidenceError(f"Git observation failed: git {' '.join(arguments)}")
    return result.stdout.decode("utf-8", errors="replace").strip()


def dirty_paths(status: str) -> list[str]:
    return [line[3:] if len(line) > 3 else line for line in status.splitlines() if line]


def detected_platform() -> str:
    value = platform.system().lower()
    mapping = {"darwin": "macos", "linux": "linux", "windows": "windows"}
    if value not in mapping:
        raise EvidenceError(f"unsupported native platform: {value or 'unknown'}")
    return mapping[value]


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def validated_output_path(path: Path, output_root: Path) -> Path:
    lexical_root = absolute_lexical(output_root)
    lexical_path = absolute_lexical(path)
    if not lexical_root.exists() or not lexical_root.is_dir():
        raise EvidenceError(f"output root must be an existing directory: {lexical_root}")
    canonical_root = lexical_root.resolve()
    try:
        relative = lexical_path.relative_to(lexical_root)
    except ValueError as exc:
        raise EvidenceError("evidence output must stay inside --output-root") from exc
    if relative == Path(".") or not relative.name:
        raise EvidenceError("evidence output must name a file inside --output-root")
    current = lexical_root
    for component in relative.parts[:-1]:
        current = current / component
        if current.is_symlink():
            raise EvidenceError(f"refusing symlinked evidence output parent: {current}")
        if not current.is_dir():
            raise EvidenceError(f"evidence output parent must already exist: {current}")
    canonical_path = canonical_root / relative
    try:
        canonical_path.resolve(strict=False).relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        raise EvidenceError("evidence output must be outside the repository")
    return canonical_path


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise EvidenceError(f"refusing to overwrite evidence output: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def record(output: Path, output_root: Path, expected_commit: str | None) -> int:
    output = validated_output_path(output, output_root)
    environment = clean_environment()
    commit = git(["rev-parse", "HEAD"], environment=environment)
    tree = git(["rev-parse", "HEAD^{tree}"], environment=environment)
    if not HEX_40.fullmatch(commit) or not HEX_40.fullmatch(tree):
        raise EvidenceError("Git returned an invalid commit or tree identifier")
    if expected_commit is not None and commit != expected_commit:
        raise EvidenceError("checked-out commit does not match the workflow commit")
    status_before = git(["status", "--porcelain=v1", "--untracked-files=all"], environment=environment)
    dirty_before = bool(status_before)
    if dirty_before:
        observed = ", ".join(dirty_paths(status_before)[:20])
        raise EvidenceError(
            f"native evidence must be recorded from a clean Git checkout; changed paths: {observed}"
        )

    phase_results: list[dict[str, Any]] = []
    status = "passed"
    for label, portable_command in PHASES:
        actual = [sys.executable if item == "python" else item for item in portable_command]
        completed = run(actual, environment=environment)
        phase_results.append(
            {
                "label": label,
                "command": list(portable_command),
                "exit_code": completed.returncode,
                "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
            }
        )
        if completed.returncode != 0:
            status = "failed"
            break

    status_after = git(["status", "--porcelain=v1", "--untracked-files=all"], environment=environment)
    dirty_after = bool(status_after)
    if dirty_after:
        status = "failed"
    payload = {
        "schema_version": 1,
        "evidence_kind": "agentsmith-first-verified-loop-native-platform",
        "status": status,
        "platform": detected_platform(),
        "git_commit": commit,
        "git_tree": tree,
        "dirty_before": dirty_before,
        "dirty_after": dirty_after,
        "python_version": platform.python_version(),
        "recorded_at": now_utc(),
        "phases": phase_results,
        "security_coverage": list(SECURITY_COVERAGE),
        "network_used": False,
        "external_write_used": False,
    }
    atomic_json(output, payload)
    if status != "passed":
        failed = next((phase["label"] for phase in phase_results if phase["exit_code"] != 0), None)
        changed = ", ".join(dirty_paths(status_after)[:20])
        reason = f"phase {failed} failed" if failed else f"the verification run changed: {changed}"
        raise EvidenceError(reason)
    print(output)
    return 0


REPORT_KEYS = {
    "schema_version",
    "evidence_kind",
    "status",
    "platform",
    "git_commit",
    "git_tree",
    "dirty_before",
    "dirty_after",
    "python_version",
    "recorded_at",
    "phases",
    "security_coverage",
    "network_used",
    "external_write_used",
}
PHASE_KEYS = {"label", "command", "exit_code", "stdout_sha256", "stderr_sha256"}


def read_report(path: Path) -> tuple[dict[str, Any], str]:
    if path.is_symlink() or not path.is_file():
        raise EvidenceError(f"report is not a regular file: {path}")
    raw = path.read_bytes()
    if len(raw) > 1_000_000:
        raise EvidenceError(f"report exceeds the size limit: {path}")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"report is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(payload, dict) or set(payload) != REPORT_KEYS:
        raise EvidenceError(f"report shape is invalid: {path}")
    return payload, hashlib.sha256(raw).hexdigest()


def validate_report(payload: dict[str, Any], path: Path) -> None:
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise EvidenceError(f"unsupported report schema: {path}")
    if payload["evidence_kind"] != "agentsmith-first-verified-loop-native-platform":
        raise EvidenceError(f"wrong evidence kind: {path}")
    if payload["status"] != "passed":
        raise EvidenceError(f"native report did not pass: {path}")
    if payload["platform"] not in PLATFORMS:
        raise EvidenceError(f"unsupported report platform: {path}")
    if not isinstance(payload["git_commit"], str) or not HEX_40.fullmatch(payload["git_commit"]):
        raise EvidenceError(f"invalid Git binding: {path}")
    if not isinstance(payload["git_tree"], str) or not HEX_40.fullmatch(payload["git_tree"]):
        raise EvidenceError(f"invalid Git binding: {path}")
    if payload["dirty_before"] is not False or payload["dirty_after"] is not False:
        raise EvidenceError(f"native report came from a dirty checkout: {path}")
    if not isinstance(payload["python_version"], str) or not payload["python_version"]:
        raise EvidenceError(f"missing Python version: {path}")
    try:
        recorded_at = dt.datetime.fromisoformat(payload["recorded_at"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise EvidenceError(f"invalid report timestamp: {path}") from exc
    if recorded_at.tzinfo is None:
        raise EvidenceError(f"report timestamp has no timezone: {path}")
    phases = payload["phases"]
    if not isinstance(phases, list) or [item.get("label") for item in phases if isinstance(item, dict)] != [
        label for label, _ in PHASES
    ]:
        raise EvidenceError(f"native report phase set is incomplete or reordered: {path}")
    for phase, (_, expected_command) in zip(phases, PHASES, strict=True):
        if not isinstance(phase, dict) or set(phase) != PHASE_KEYS:
            raise EvidenceError(f"invalid phase record: {path}")
        if type(phase["exit_code"]) is not int or phase["exit_code"] != 0:
            raise EvidenceError(f"phase did not pass: {path}")
        if not isinstance(phase["command"], list) or not phase["command"] or not all(
            isinstance(item, str) and item for item in phase["command"]
        ):
            raise EvidenceError(f"invalid phase command: {path}")
        if phase["command"] != list(expected_command):
            raise EvidenceError(f"native report command set was tampered with: {path}")
        stdout_hash = phase["stdout_sha256"]
        stderr_hash = phase["stderr_sha256"]
        if not isinstance(stdout_hash, str) or not HEX_64.fullmatch(stdout_hash):
            raise EvidenceError(f"invalid phase output hash: {path}")
        if not isinstance(stderr_hash, str) or not HEX_64.fullmatch(stderr_hash):
            raise EvidenceError(f"invalid phase output hash: {path}")
    if payload["security_coverage"] != list(SECURITY_COVERAGE):
        raise EvidenceError(f"security coverage is incomplete: {path}")
    if payload["network_used"] is not False or payload["external_write_used"] is not False:
        raise EvidenceError(f"report includes an out-of-scope side effect: {path}")


def aggregate(reports: list[Path], output: Path, output_root: Path, expected_commit: str) -> int:
    output = validated_output_path(output, output_root)
    if not HEX_40.fullmatch(expected_commit):
        raise EvidenceError("--expected-commit must be a 40-character lowercase Git identifier")
    if len(reports) != len(PLATFORMS):
        raise EvidenceError("exactly three native reports are required")
    normalized_paths = {os.path.normcase(os.path.abspath(path)) for path in reports}
    if len(normalized_paths) != len(reports):
        raise EvidenceError("native report paths must be unique")

    by_platform: dict[str, dict[str, Any]] = {}
    digests: dict[str, str] = {}
    for path in reports:
        payload, digest = read_report(path)
        validate_report(payload, path)
        platform_name = payload["platform"]
        if platform_name in by_platform:
            raise EvidenceError(f"duplicate native platform report: {platform_name}")
        by_platform[platform_name] = payload
        digests[platform_name] = digest
    if set(by_platform) != set(PLATFORMS):
        raise EvidenceError("Linux, macOS, and Windows reports are all required")
    if {payload["git_commit"] for payload in by_platform.values()} != {expected_commit}:
        raise EvidenceError("native reports do not match the expected Git commit")
    trees = {payload["git_tree"] for payload in by_platform.values()}
    if len(trees) != 1:
        raise EvidenceError("native reports do not bind to one Git tree")
    actual_tree = git(["rev-parse", f"{expected_commit}^{{tree}}"], environment=clean_environment())
    if trees != {actual_tree}:
        raise EvidenceError("native reports do not bind to the expected commit's Git tree")

    value = {
        "schema_version": 1,
        "evidence_kind": "agentsmith-first-verified-loop-native-aggregate",
        "status": "passed",
        "git_commit": expected_commit,
        "git_tree": next(iter(trees)),
        "platforms": list(PLATFORMS),
        "phase_labels": [label for label, _ in PHASES],
        "security_coverage": list(SECURITY_COVERAGE),
        "report_sha256": {name: digests[name] for name in PLATFORMS},
        "recorded_at": now_utc(),
        "native_evidence_complete": True,
        "network_used": False,
        "external_write_used": False,
    }
    atomic_json(output, value)
    print(output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    record_parser = subparsers.add_parser("record", help="run and record the native fixture gate")
    record_parser.add_argument("--output", type=Path, required=True)
    record_parser.add_argument("--output-root", type=Path, required=True)
    record_parser.add_argument("--expected-commit")
    aggregate_parser = subparsers.add_parser("aggregate", help="bind three native reports")
    aggregate_parser.add_argument("--report", action="append", type=Path, required=True)
    aggregate_parser.add_argument("--expected-commit", required=True)
    aggregate_parser.add_argument("--output", type=Path, required=True)
    aggregate_parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "record":
            return record(args.output, args.output_root, args.expected_commit)
        return aggregate(
            [absolute_lexical(path) for path in args.report],
            args.output,
            args.output_root,
            args.expected_commit,
        )
    except EvidenceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
