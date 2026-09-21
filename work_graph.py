"""Deterministic local work-graph coordination over the finite-run controller."""

from __future__ import annotations

import hashlib
import contextlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = 1
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
OID = re.compile(r"[0-9a-f]{40,64}\Z")


class GraphError(RuntimeError):
    pass


def git(repo: Path, *arguments: str, check: bool = True) -> str:
    result = subprocess.run(["git", *arguments], cwd=repo, text=True, capture_output=True, check=False)
    if check and result.returncode:
        raise GraphError(result.stderr.strip() or result.stdout.strip() or "Git command failed")
    return result.stdout.strip()


def repository(target: str | Path) -> Path:
    path = Path(target).resolve()
    if not path.is_dir():
        raise GraphError("target must be an existing Git repository directory")
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path,
                            text=True, capture_output=True, check=False)
    if result.returncode:
        raise GraphError("target is not inside a Git repository")
    return Path(result.stdout.strip()).resolve()


def common_directory(repo: Path) -> Path:
    value = Path(git(repo, "rev-parse", "--git-common-dir"))
    return (value if value.is_absolute() else repo / value).resolve()


def safe_file(repo: Path, relative: str, *, label: str) -> Path:
    if (not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative
            or relative.startswith("/")):
        raise GraphError(f"{label} must be a repository-relative POSIX file path")
    parts = relative.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise GraphError(f"{label} must be a repository-relative POSIX file path")
    path = repo
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise GraphError(f"{label} traverses a symlink")
    if not path.is_file():
        raise GraphError(f"{label} is not a regular file")
    return path


def committed_bytes(repo: Path, commit: str, relative: str, *, label: str) -> bytes:
    path = safe_file(repo, relative, label=label)
    result = subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=repo,
                            capture_output=True, check=False)
    if result.returncode:
        raise GraphError(f"{label} must be committed at the graph contract commit")
    if path.read_bytes() != result.stdout:
        raise GraphError(f"{label} differs from committed contract bytes")
    return result.stdout


def _controller() -> Any:
    root = Path(__file__).resolve().parent
    source = root / "autonomous-run.py"
    if not source.is_file():
        source = root / "scripts" / "autonomous-run.py"
    if not source.is_file():
        raise GraphError("finite autonomous-run controller is unavailable")
    spec = importlib.util.spec_from_file_location("agentsmith_finite_run_for_graph", source)
    if spec is None or spec.loader is None:
        raise GraphError("finite autonomous-run controller cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _object(value: Any, keys: set[str], *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise GraphError(f"{label} must have exactly {', '.join(sorted(keys))}")
    return value


def _json_object(payload: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GraphError(f"{label} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise GraphError(f"{label} must be a JSON object")
    return value


def _identifier(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise GraphError(f"{label} must be 1-64 ASCII letters, digits, '-' or '_'")
    return value


def _topological_order(nodes: dict[str, dict[str, Any]], declared: list[str]) -> None:
    position = {run_id: index for index, run_id in enumerate(declared)}
    for run_id, node in nodes.items():
        for dependency in node["depends_on"]:
            if dependency not in nodes:
                raise GraphError(f"node {run_id} has unknown dependency {dependency}")
            if position[dependency] >= position[run_id]:
                # Distinguish a true cycle from an order that merely violates dependency order.
                visiting: set[str] = set()
                visited: set[str] = set()

                def visit(candidate: str) -> None:
                    if candidate in visiting:
                        raise GraphError(f"dependency cycle includes {candidate}")
                    if candidate in visited:
                        return
                    visiting.add(candidate)
                    for prerequisite in nodes[candidate]["depends_on"]:
                        if prerequisite in nodes:
                            visit(prerequisite)
                    visiting.remove(candidate)
                    visited.add(candidate)

                for candidate in nodes:
                    visit(candidate)
                raise GraphError(f"integration_order must place {dependency} before {run_id}")


def load_contract(target: str | Path, graph_path: str) -> dict[str, Any]:
    repo = repository(target)
    if git(repo, "status", "--porcelain"):
        raise GraphError("graph validation requires a clean committed repository")
    commit = git(repo, "rev-parse", "HEAD^{commit}")
    graph_bytes = committed_bytes(repo, commit, graph_path, label="graph")
    graph = _object(
        _json_object(graph_bytes, label="graph"),
        {"schema_version", "graph_id", "max_parallel", "integration_order", "nodes"},
        label="graph",
    )
    if type(graph["schema_version"]) is not int or graph["schema_version"] != SCHEMA_VERSION:
        raise GraphError("unsupported graph schema_version")
    graph_id = _identifier(graph["graph_id"], label="graph_id")
    parallel = graph["max_parallel"]
    if type(parallel) is not int or not 1 <= parallel <= 2:
        raise GraphError("max_parallel must be 1 or 2 in work-graph v1")
    raw_nodes = graph["nodes"]
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise GraphError("nodes must be a non-empty array")
    nodes: dict[str, dict[str, Any]] = {}
    for index, raw_node in enumerate(raw_nodes):
        node = _object(raw_node, {"run_id", "manifest_path", "manifest_sha256", "depends_on"},
                       label=f"nodes[{index}]")
        run_id = _identifier(node["run_id"], label=f"nodes[{index}].run_id")
        if run_id in nodes:
            raise GraphError(f"duplicate run_id {run_id}")
        digest = node["manifest_sha256"]
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise GraphError(f"node {run_id} has invalid manifest_sha256")
        dependencies = node["depends_on"]
        if (not isinstance(dependencies, list) or len(dependencies) != len(set(map(str, dependencies)))
                or not all(isinstance(item, str) and IDENTIFIER.fullmatch(item) for item in dependencies)):
            raise GraphError(f"node {run_id} has invalid depends_on")
        nodes[run_id] = node
    order = graph["integration_order"]
    if (not isinstance(order, list) or not all(isinstance(item, str) for item in order)
            or set(order) != set(nodes) or len(order) != len(nodes)):
        raise GraphError("integration_order must list every run_id exactly once")
    _topological_order(nodes, order)
    controller = _controller()
    manifests: dict[str, dict[str, Any]] = {}
    scopes: dict[str, dict[str, list[str]]] = {}
    for run_id in order:
        node = nodes[run_id]
        relative = node["manifest_path"]
        payload = committed_bytes(repo, commit, relative, label=f"manifest for {run_id}")
        if hashlib.sha256(payload).hexdigest() != node["manifest_sha256"]:
            raise GraphError(f"manifest hash mismatch for {run_id}")
        manifest = _json_object(payload, label=f"manifest for {run_id}")
        if manifest.get("run_id") != run_id:
            raise GraphError(f"manifest run_id mismatch for {run_id}")
        base_ref = manifest.get("base_ref")
        if base_ref != "HEAD" and base_ref != commit:
            raise GraphError(f"manifest base_ref for {run_id} must pin the contract commit")
        if git(repo, "rev-parse", "--verify", f"{base_ref}^{{commit}}", check=False) != commit:
            raise GraphError(f"manifest base_ref for {run_id} must resolve to the contract commit")
        try:
            controller.validate_manifest(manifest, repo)
            scopes[run_id] = controller.normalized_scope(manifest["scope"])
        except (controller.RunError, ValueError, TypeError, KeyError) as exc:
            raise GraphError(f"invalid manifest for {run_id}: {exc}") from exc
        for pattern in scopes[run_id]["allowed_paths"]:
            prefix = controller.fixed_prefix(pattern)
            if prefix == "." or prefix == ".git" or prefix.startswith(".git/"):
                raise GraphError(f"unsafe scope for {run_id}: allowed_paths must reserve a narrow non-Git path")
        limits = manifest["limits"]
        for field in ("max_attempts", "wall_minutes", "codex_goal_tokens"):
            value = limits.get(field)
            if type(value) is not int or value <= 0:
                raise GraphError(f"invalid budget for {run_id}: limits.{field} must be positive")
        cost = limits.get("claude_max_usd")
        if type(cost) not in (int, float) or not math.isfinite(cost) or cost <= 0:
            raise GraphError(f"invalid budget for {run_id}: limits.claude_max_usd must be positive")
        manifests[run_id] = manifest
    return {
        "repo": repo, "contract_commit": commit, "graph_path": graph_path,
        "graph_sha256": hashlib.sha256(graph_bytes).hexdigest(), "graph_id": graph_id,
        "graph": graph, "nodes": nodes, "order": order, "manifests": manifests,
        "scopes": scopes, "controller": controller,
    }


def _child_state(contract: dict[str, Any], run_id: str) -> dict[str, Any] | None:
    path = common_directory(contract["repo"]) / "agentsmith-runs" / run_id / "state.json"
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise GraphError(f"child state for {run_id} is not a regular file")
    state = _json_object(path.read_bytes(), label=f"child state for {run_id}")
    if state.get("run_id") != run_id or state.get("manifest_sha256") != contract["nodes"][run_id]["manifest_sha256"]:
        raise GraphError(f"child state lineage mismatch for {run_id}")
    if state.get("repo") != str(contract["repo"]):
        raise GraphError(f"child state repository mismatch for {run_id}")
    return state


def _accepted_commit(contract: dict[str, Any], run_id: str, state: dict[str, Any]) -> str:
    commit = state.get("accepted_commit")
    base = state.get("base_head")
    branch = state.get("branch")
    if (not isinstance(commit, str) or not OID.fullmatch(commit)
            or not isinstance(base, str) or not OID.fullmatch(base)
            or branch != f"agentsmith/{run_id}"):
        raise GraphError(f"accepted child {run_id} has incomplete lineage")
    repo = contract["repo"]
    if git(repo, "rev-parse", f"refs/heads/{branch}", check=False) != commit:
        raise GraphError(f"accepted child {run_id} branch moved or is missing")
    result = subprocess.run(["git", "merge-base", "--is-ancestor", base, commit],
                            cwd=repo, capture_output=True, check=False)
    if result.returncode:
        raise GraphError(f"accepted child {run_id} no longer descends from its base")
    receipt = state.get("last_checker_receipt")
    if not isinstance(receipt, dict) or receipt.get("status") != "accepted" or receipt.get("commit") != commit:
        raise GraphError(f"accepted child {run_id} has no matching checker receipt")
    return commit


def checker_receipt_sha256(receipt: dict[str, Any]) -> str:
    payload = json.dumps(receipt, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def predecessor_ids(contract: dict[str, Any], run_id: str) -> list[str]:
    found: set[str] = set()

    def visit(candidate: str) -> None:
        for dependency in contract["nodes"][candidate]["depends_on"]:
            if dependency not in found:
                found.add(dependency)
                visit(dependency)

    visit(run_id)
    return [candidate for candidate in contract["order"] if candidate in found]


def expected_sources(contract: dict[str, Any], run_id: str) -> list[dict[str, str]]:
    sources = []
    for predecessor in predecessor_ids(contract, run_id):
        state = _child_state(contract, predecessor)
        if state is None or state.get("status") != "accepted":
            raise GraphError(f"predecessor {predecessor} has no accepted child state")
        commit = _accepted_commit(contract, predecessor, state)
        sources.append({
            "run_id": predecessor,
            "accepted_commit": commit,
            "receipt_sha256": checker_receipt_sha256(state["last_checker_receipt"]),
        })
    return sources


def _checkpoint_commit(contract: dict[str, Any], run_id: str) -> str | None:
    path = common_directory(contract["repo"]) / "agentsmith-graphs" / contract["graph_id"] / "state.json"
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise GraphError("graph state is not a regular file")
    controller = _controller()
    try:
        state = controller.load_json(path)
    except controller.RunError as exc:
        raise GraphError(f"graph state is unreadable: {exc}") from exc
    if (state.get("schema_version") != SCHEMA_VERSION
            or state.get("graph_id") != contract["graph_id"]
            or state.get("graph_sha256") != contract["graph_sha256"]
            or state.get("contract_commit") != contract["contract_commit"]):
        raise GraphError("graph state contract drift")
    checkpoints = state.get("checkpoints", [])
    if not isinstance(checkpoints, list):
        raise GraphError("graph checkpoints are malformed")
    matches = [item for item in checkpoints if isinstance(item, dict) and item.get("run_id") == run_id]
    if not matches:
        return None
    if len(matches) != 1:
        raise GraphError(f"duplicate dependency checkpoints for {run_id}")
    receipt = matches[0]
    commit = receipt.get("checkpoint_oid")
    if (not isinstance(commit, str) or not OID.fullmatch(commit)
            or receipt.get("base_oid") != contract["contract_commit"]
            or not isinstance(receipt.get("sources"), list)):
        raise GraphError(f"dependency checkpoint for {run_id} is malformed")
    if git(contract["repo"], "cat-file", "-t", commit, check=False) != "commit":
        raise GraphError(f"dependency checkpoint for {run_id} is missing")
    if git(contract["repo"], "rev-parse", f"{commit}^{{tree}}") != receipt.get("checkpoint_tree"):
        raise GraphError(f"dependency checkpoint for {run_id} changed tree")
    if receipt["sources"] != expected_sources(contract, run_id):
        raise GraphError(f"dependency checkpoint for {run_id} source lineage mismatch")
    branch = f"refs/heads/agentsmith-graph/{contract['graph_id']}/checkpoint/{run_id}"
    if git(contract["repo"], "rev-parse", branch, check=False) != commit:
        raise GraphError(f"dependency checkpoint for {run_id} branch moved or is missing")
    for source in receipt["sources"]:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", source["accepted_commit"], commit],
            cwd=contract["repo"], capture_output=True, check=False,
        )
        if result.returncode:
            raise GraphError(f"dependency checkpoint for {run_id} omits {source['run_id']}")
    return commit


def status(contract: dict[str, Any]) -> dict[str, Any]:
    controller = contract["controller"]
    nodes: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    reserved: list[str] = []
    running_count = 0
    for run_id in contract["order"]:
        state = _child_state(contract, run_id)
        if state is None:
            continue
        child_status = state.get("status")
        if child_status in {"prepared", "making", "checking", "retrying", "resuming"}:
            pid = state.get("controller_pid")
            if controller.process_is_live(pid):
                reserved.append(run_id)
                running_count += 1
    for run_id in contract["order"]:
        node = contract["nodes"][run_id]
        state = _child_state(contract, run_id)
        checkpoint = _checkpoint_commit(contract, run_id) if node["depends_on"] else contract["contract_commit"]
        result: dict[str, Any] = {"run_id": run_id, "effective_base_oid": checkpoint}
        if state is not None:
            child_status = state.get("status")
            if checkpoint is None or state.get("base_head") != checkpoint:
                raise GraphError(f"child base lineage mismatch for {run_id}")
            if child_status == "accepted":
                result.update(status="completed", reason="accepted child commit and checker receipt")
                result["accepted_commit"] = _accepted_commit(contract, run_id, state)
            elif child_status == "escalated":
                result.update(status="failed", reason=str(state.get("reason") or "child run escalated"))
            elif child_status == "interrupted":
                result.update(status="interrupted", reason=str(state.get("reason") or "child run interrupted"))
            elif child_status in {"prepared", "making", "checking", "retrying", "resuming"}:
                live = controller.process_is_live(state.get("controller_pid"))
                result.update(status="running" if live else "interrupted",
                              reason="child controller active" if live else "child controller is not live")
            else:
                result.update(status="blocked", reason="unknown child state")
        else:
            dependencies = node["depends_on"]
            failed = [item for item in dependencies if by_id[item]["status"] in {"failed", "blocked", "interrupted"}]
            pending = [item for item in dependencies if by_id[item]["status"] != "completed"]
            if failed:
                result.update(status="blocked", reason="dependency failed or interrupted: " + ", ".join(failed))
            elif pending:
                result.update(status="waiting", reason="waiting for dependencies: " + ", ".join(pending))
            elif dependencies and checkpoint is None:
                result.update(status="waiting", reason="dependency checkpoint not assembled")
            elif running_count >= contract["graph"]["max_parallel"]:
                result.update(status="waiting", reason="parallel capacity reached")
            else:
                conflicting = None
                for other in reserved:
                    collision = controller.scope_collision(contract["scopes"][run_id], contract["scopes"][other])
                    if collision:
                        conflicting = f"{collision[0]} conflict with {other}: {collision[1]}"
                        break
                if conflicting:
                    result.update(status="conflicting", reason=conflicting)
                else:
                    result.update(status="ready", reason="dependencies and scope permit dispatch")
                    reserved.append(run_id)
                    running_count += 1
        node_actions = {
            "ready": ("start", "dispatch this node"),
            "waiting": ("status", "wait for prerequisites or capacity"),
            "conflicting": ("status", "wait for conflicting work"),
            "running": ("status", "inspect active child"),
            "completed": ("status", "retain accepted evidence"),
            "failed": ("status", "inspect child escalation"),
            "blocked": ("status", "inspect failed prerequisite"),
            "interrupted": ("resume", "reconcile interrupted child"),
        }
        command, reason = node_actions[result["status"]]
        result["next_action"] = {"command": command, "reason": reason}
        by_id[run_id] = result
        nodes.append(result)
    ready_set = [item["run_id"] for item in nodes if item["status"] == "ready"]
    if all(item["status"] == "completed" for item in nodes):
        graph_status, action = "completed", "integrate"
    elif any(item["status"] == "failed" for item in nodes):
        graph_status, action = "failed", "status"
    elif any(item["status"] in {"blocked", "interrupted"} for item in nodes):
        graph_status, action = "blocked", "status"
    elif any(item["status"] == "running" for item in nodes):
        graph_status, action = "running", "status"
    else:
        graph_status, action = "prepared", "start" if ready_set else "status"
    if _graph_directory(contract).exists():
        saved = _load_graph_state(contract)
        if saved["status"] == "stopped":
            graph_status, action, ready_set = "stopped", "resume", []
    if graph_status == "completed" and (_graph_directory(contract) / "integration-candidate.json").is_file():
        action = "status"
        action_reason = "local candidate exists; inspect proof and obtain separate delivery approval"
    else:
        action_reason = "local graph state permits this action"
    return {
        "schema_version": SCHEMA_VERSION, "graph_id": contract["graph_id"],
        "contract_commit": contract["contract_commit"], "graph_sha256": contract["graph_sha256"],
        "status": graph_status, "nodes": nodes, "ready_set": ready_set,
        "next_action": {"command": action, "reason": action_reason},
    }


def validation_report(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION, "graph_id": contract["graph_id"],
        "contract_commit": contract["contract_commit"], "graph_sha256": contract["graph_sha256"],
        "node_count": len(contract["nodes"]), "max_parallel": contract["graph"]["max_parallel"],
        "integration_order": contract["order"], "valid": True,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _graph_directory(contract: dict[str, Any]) -> Path:
    root = common_directory(contract["repo"]) / "agentsmith-graphs"
    directory = root / contract["graph_id"]
    if root.is_symlink() or directory.is_symlink():
        raise GraphError("graph state path cannot traverse a symlink")
    return directory


def _stop_path(contract: dict[str, Any]) -> Path:
    # The finite-run metadata guard treats this controller-owned stop signal like
    # child STOP files: a stop is safety-reducing and may arrive during a maker turn.
    root = common_directory(contract["repo"]) / "agentsmith-runs"
    stop_dir = root / "graph-stop" / contract["graph_id"]
    if any(path.is_symlink() for path in (root, root / "graph-stop", stop_dir)):
        raise GraphError("graph stop path cannot traverse a symlink")
    return stop_dir / "STOP"


def _load_graph_state(contract: dict[str, Any]) -> dict[str, Any]:
    path = _graph_directory(contract) / "state.json"
    controller = _controller()
    try:
        state = controller.load_json(path)
    except controller.RunError as exc:
        raise GraphError("graph has no readable durable state") from exc
    if not isinstance(state, dict) or any(state.get(key) != value for key, value in (
        ("schema_version", SCHEMA_VERSION), ("graph_id", contract["graph_id"]),
        ("graph_path", contract["graph_path"]), ("graph_sha256", contract["graph_sha256"]),
        ("contract_commit", contract["contract_commit"]),
    )):
        raise GraphError("durable graph state does not match the committed graph contract")
    if (state.get("status") not in {"prepared", "running", "completed", "failed", "stopped", "blocked"}
            or not isinstance(state.get("dispatches"), list)
            or not isinstance(state.get("checkpoints"), list)
            or not isinstance(state.get("stop_requested"), bool)):
        raise GraphError("durable graph state has invalid lifecycle fields")
    return state


@contextlib.contextmanager
def _graph_lock(contract: dict[str, Any]):
    directory = _graph_directory(contract)
    path = directory / "LOCK"
    controller = _controller()
    token = os.urandom(16).hex()
    with controller.coordination_lock(controller.state_root(contract["repo"])):
        if path.exists():
            try:
                owner = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise GraphError("graph lifecycle lock is unreadable; refusing recovery") from exc
            if (not isinstance(owner, dict) or set(owner) != {"graph_id", "pid", "token"}
                    or owner["graph_id"] != contract["graph_id"]
                    or not isinstance(owner["pid"], int)
                    or not isinstance(owner["token"], str)
                    or not re.fullmatch(r"[0-9a-f]{32}", owner["token"])):
                raise GraphError("graph lifecycle lock owner is ambiguous; refusing recovery")
            if controller.process_is_live(owner["pid"]):
                raise GraphError(f"graph controller is already live at process {owner['pid']}")
            path.unlink()
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"graph_id": contract["graph_id"], "pid": os.getpid(), "token": token}, handle)
            handle.flush()
            os.fsync(handle.fileno())
    try:
        yield
    finally:
        with controller.coordination_lock(controller.state_root(contract["repo"])):
            try:
                owner = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                owner = None
            if isinstance(owner, dict) and owner.get("token") == token:
                path.unlink()


def _save_graph_state(directory: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    try:
        _controller().write_json(directory / "state.json", state)
    except OSError as exc:
        raise GraphError(f"could not persist graph state: {exc}") from exc


def _graph_event(directory: Path, graph_id: str, kind: str, *, run_id: str | None = None,
                 commit: str | None = None, reason: str) -> None:
    path = directory / "events.jsonl"
    sequence = len(path.read_text(encoding="utf-8").splitlines()) + 1 if path.exists() else 1
    record = {
        "schema_version": SCHEMA_VERSION, "graph_id": graph_id, "sequence": sequence,
        "at": _now(), "event": kind, "run_id": run_id, "commit_oid": commit, "reason": reason,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _controller_source() -> Path:
    root = Path(__file__).resolve().parent
    installed = root / "autonomous-run.py"
    source = root / "scripts" / "autonomous-run.py"
    candidate = installed if installed.is_file() else source
    if not candidate.is_file():
        raise GraphError("finite autonomous-run controller is unavailable")
    return candidate


def _create_checkpoint_unlocked(contract: dict[str, Any], state: dict[str, Any], run_id: str,
                                directory: Path) -> str:
    sources = expected_sources(contract, run_id)
    if not sources:
        raise GraphError(f"node {run_id} has no predecessors to compose")
    repo = contract["repo"]
    branch = f"agentsmith-graph/{contract['graph_id']}/checkpoint/{run_id}"
    worktree = repo.parent / f"{repo.name}-{contract['graph_id']}-checkpoint-{run_id}"
    if worktree.exists() or worktree.is_symlink() or git(repo, "show-ref", "--verify", f"refs/heads/{branch}", check=False):
        raise GraphError(f"checkpoint artifacts already exist for {run_id}; refusing overwrite")
    created = subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(worktree), contract["contract_commit"]],
        cwd=repo, text=True, capture_output=True, check=False,
    )
    if created.returncode:
        raise GraphError(created.stderr.strip() or f"checkpoint worktree creation failed for {run_id}")
    hooks = directory / "empty-hooks"
    hooks.mkdir(exist_ok=True)
    for source in sources:
        merged = subprocess.run(
            ["git", "-c", f"core.hooksPath={hooks}", "-c", "commit.gpgsign=false",
             "merge", "--no-ff", "--no-edit", source["accepted_commit"]],
            cwd=worktree, text=True, capture_output=True, check=False,
        )
        if merged.returncode:
            raise GraphError(
                f"checkpoint {run_id} conflicts while merging {source['run_id']}; "
                f"worktree retained at {worktree}: {merged.stderr.strip()}"
            )
    commit = git(worktree, "rev-parse", "HEAD")
    receipt = {
        "run_id": run_id, "base_oid": contract["contract_commit"], "checkpoint_oid": commit,
        "checkpoint_tree": git(worktree, "rev-parse", "HEAD^{tree}"),
        "sources": sources, "created_at": _now(),
    }
    state["checkpoints"].append(receipt)
    _save_graph_state(directory, state)
    _graph_event(directory, contract["graph_id"], "checkpoint_created", run_id=run_id,
                 commit=commit, reason="accepted predecessor commits composed in integration order")
    if _checkpoint_commit(contract, run_id) != commit:
        raise GraphError(f"checkpoint {run_id} did not survive lineage validation")
    return commit


def _create_checkpoint(contract: dict[str, Any], state: dict[str, Any], run_id: str,
                       directory: Path) -> str:
    controller = _controller()
    try:
        with controller.git_phase(contract["repo"], "writer", timeout_seconds=60):
            return _create_checkpoint_unlocked(contract, state, run_id, directory)
    except controller.RunError as exc:
        raise GraphError(f"checkpoint {run_id} could not acquire Git writer phase: {exc}") from exc


def start_graph(contract: dict[str, Any]) -> dict[str, Any]:
    """Run a new graph locally while children retain budgets and maker/checker ownership."""
    directory = _graph_directory(contract)
    try:
        directory.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise GraphError("graph already has local state; use status or resume") from exc
    with _graph_lock(contract):
        state: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION, "graph_id": contract["graph_id"],
            "graph_path": contract["graph_path"], "graph_sha256": contract["graph_sha256"],
            "contract_commit": contract["contract_commit"], "status": "prepared",
            "created_at": _now(), "updated_at": _now(), "dispatches": [], "checkpoints": [],
            "candidate_path": None, "stop_requested": False,
        }
        _save_graph_state(directory, state)
        _graph_event(directory, contract["graph_id"], "graph_prepared", reason="pinned committed graph")
        return _run_graph(contract, state, directory)


def child_failure_reason(child: dict[str, Any] | None, returncode: int, stderr: str) -> str:
    """Keep a useful child crash signature without copying process output into graph evidence."""
    known = child.get("reason") if child else None
    if isinstance(known, str) and known.strip():
        return known[:500]
    status = child.get("status") if child else None
    if status not in {"making", "checking", "retrying", "accepted", "escalated", "interrupted"}:
        status = "unknown"
    exception = "unknown"
    for line in reversed(stderr.splitlines()):
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_.]{0,63})(?::|$)", line)
        if match:
            exception = match.group(1)
            break
    location = "unknown"
    frames = re.findall(r'File "([^"\r\n]+)", line ([0-9]{1,6}), in [A-Za-z_][A-Za-z0-9_]*', stderr)
    for path, line in reversed(frames):
        if re.split(r"[\\/]", path)[-1] == "autonomous-run.py":
            location = f"autonomous-run.py:{line}"
            break
    return f"child process exit={returncode} in {status}; exception={exception}; location={location}"


def _run_graph(contract: dict[str, Any], state: dict[str, Any], directory: Path,
               resume_ids: list[str] | None = None) -> dict[str, Any]:
    repo = contract["repo"]
    state["status"] = "running"
    _save_graph_state(directory, state)
    active: dict[str, subprocess.Popen[str]] = {}
    if resume_ids:
        _graph_event(directory, contract["graph_id"], "graph_resumed",
                     reason="pinned contracts and retained child limits reconciled")
        for run_id in resume_ids:
            active[run_id] = subprocess.Popen(
                [sys.executable, str(_controller_source()), "resume", run_id],
                cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
    dispatched = {item["run_id"] for item in state["dispatches"]}
    pending_events: list[tuple[str, str, str | None, str]] = []
    stop_sent: set[str] = set()
    while True:
        stopping = _stop_path(contract).exists()
        if stopping:
            for run_id in active:
                if run_id in stop_sent or _child_state(contract, run_id) is None:
                    continue
                subprocess.run([sys.executable, str(_controller_source()), "stop", run_id],
                               cwd=repo, text=True, capture_output=True, check=False)
                stop_sent.add(run_id)
            if not active:
                state["stop_requested"] = True
                state["status"] = "stopped"
                _save_graph_state(directory, state)
                _graph_event(directory, contract["graph_id"], "graph_stopped",
                             reason="operator stop retained all child and graph artifacts")
                return status(contract)
        report = status(contract)
        by_id = {item["run_id"]: item for item in report["nodes"]}
        try:
            if not active and not stopping:
                for run_id in contract["order"]:
                    node = contract["nodes"][run_id]
                    if (node["depends_on"] and _checkpoint_commit(contract, run_id) is None
                            and all(by_id[dependency]["status"] == "completed" for dependency in node["depends_on"])):
                        _create_checkpoint(contract, state, run_id, directory)
        except GraphError:
            state["status"] = "blocked"
            _save_graph_state(directory, state)
            raise
        report = status(contract)
        if not active and not stopping:
            launches: list[tuple[str, Path, str]] = []
            for run_id in report["ready_set"]:
                if run_id in dispatched or len(launches) >= contract["graph"]["max_parallel"]:
                    continue
                node = contract["nodes"][run_id]
                base = (_checkpoint_commit(contract, run_id) if node["depends_on"]
                        else contract["contract_commit"])
                if base is None:
                    raise GraphError(f"node {run_id} has no verified effective base")
                launches.append((run_id, repo / node["manifest_path"], base))
                state["dispatches"].append({
                    "run_id": run_id, "effective_base_oid": base,
                    "checkpoint_oid": base if node["depends_on"] else None,
                    "child_state_path": f"agentsmith-runs/{run_id}/state.json", "started_at": _now(),
                })
            if launches:
                _save_graph_state(directory, state)
                for run_id, manifest, base in launches:
                    _graph_event(directory, contract["graph_id"], "run_dispatched", run_id=run_id,
                                 commit=base, reason="deterministic ready set and pinned base")
                for run_id, manifest, base in launches:
                    active[run_id] = subprocess.Popen(
                        [sys.executable, str(_controller_source()), "start", str(manifest),
                         "--graph", contract["graph_path"], "--effective-base", base],
                        cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    )
                    dispatched.add(run_id)
        for run_id, process in list(active.items()):
            if process.poll() is None:
                continue
            stdout, stderr = process.communicate()
            del active[run_id]
            child = _child_state(contract, run_id)
            if stopping and child is not None and child.get("status") == "interrupted":
                continue
            if process.returncode == 0 and child is not None and child.get("status") == "accepted":
                pending_events.append(("run_completed", run_id, child.get("accepted_commit"),
                                       "child checker accepted"))
            else:
                reason = child_failure_reason(child, process.returncode, stderr)
                pending_events.append(("run_failed", run_id, None,
                                       reason[:500] or "child process exited without accepted evidence"))
        if not active and pending_events:
            for kind, run_id, commit, reason in pending_events:
                _graph_event(directory, contract["graph_id"], kind, run_id=run_id,
                             commit=commit, reason=reason)
            pending_events.clear()
        report = status(contract)
        if all(item["status"] == "completed" for item in report["nodes"]):
            state["status"] = "completed"
            _save_graph_state(directory, state)
            _graph_event(directory, contract["graph_id"], "graph_completed",
                         reason="every child accepted; local integration remains pending")
            return report
        if not active and not report["ready_set"]:
            if stopping:
                continue
            by_id = {item["run_id"]: item for item in report["nodes"]}
            if any(node["depends_on"] and by_id[run_id]["status"] == "waiting"
                   and all(by_id[dependency]["status"] == "completed"
                           for dependency in node["depends_on"])
                   and _checkpoint_commit(contract, run_id) is None
                   for run_id, node in contract["nodes"].items()):
                continue
            state["status"] = "failed" if report["status"] == "failed" else "blocked"
            _save_graph_state(directory, state)
            return report
        time.sleep(0.05)


def stop_graph(contract: dict[str, Any]) -> dict[str, Any]:
    state = _load_graph_state(contract)
    if state["status"] == "completed":
        raise GraphError("completed graph cannot be stopped")
    path = _stop_path(contract)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"requested_at={_now()}\n")
            handle.flush()
            os.fsync(handle.fileno())
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        current = _load_graph_state(contract)
        if current["status"] == "stopped":
            return status(contract)
        time.sleep(0.05)
    raise GraphError("graph stop was requested but controller did not confirm within ten seconds")


def resume_graph(contract: dict[str, Any]) -> dict[str, Any]:
    directory = _graph_directory(contract)
    _load_graph_state(contract)
    with _graph_lock(contract):
        state = _load_graph_state(contract)
        if state["status"] not in {"stopped", "running", "blocked"}:
            raise GraphError(f"graph in {state['status']} state cannot resume")
        report = status(contract)
        by_id = {item["run_id"]: item for item in report["nodes"]}
        dispatched: set[str] = set()
        resume_ids: list[str] = []
        controller = _controller()
        for item in state["dispatches"]:
            if not isinstance(item, dict) or not isinstance(item.get("run_id"), str):
                raise GraphError("graph dispatch lineage is malformed")
            run_id = item["run_id"]
            if run_id in dispatched or run_id not in contract["nodes"]:
                raise GraphError("graph dispatch lineage has a duplicate or foreign run")
            dispatched.add(run_id)
            if item.get("effective_base_oid") != by_id[run_id]["effective_base_oid"]:
                raise GraphError(f"effective base drift for dispatched node {run_id}")
            child = _child_state(contract, run_id)
            if child is None:
                raise GraphError(f"dispatched node {run_id} has no child state; manual reconciliation required")
            child_status = child.get("status")
            if child_status in {"accepted", "escalated"}:
                continue
            if controller.process_is_live(child.get("controller_pid")):
                raise GraphError(f"child controller {run_id} is still live; refusing duplicate resume")
            worktree_value = child.get("worktree")
            if not isinstance(worktree_value, str):
                raise GraphError(f"child {run_id} has no recorded worktree")
            worktree = Path(worktree_value)
            if (worktree.is_symlink() or not worktree.is_dir()
                    or common_directory(worktree) != common_directory(contract["repo"])
                    or git(worktree, "symbolic-ref", "-q", "HEAD") != f"refs/heads/agentsmith/{run_id}"
                    or git(worktree, "status", "--porcelain", "--untracked-files=all")):
                raise GraphError(f"cannot resume dirty or moved child worktree {run_id}")
            manifest = controller.load_json(contract["repo"] / contract["nodes"][run_id]["manifest_path"])
            if controller.remaining_seconds(child, manifest) <= 0:
                raise GraphError(f"child {run_id} original wall-clock deadline is exhausted")
            resume_ids.append(run_id)
        stop = _stop_path(contract)
        if state["status"] == "stopped" and not stop.is_file():
            raise GraphError("stopped graph has no durable stop request")
        stop.unlink(missing_ok=True)
        state["stop_requested"] = False
        return _run_graph(contract, state, directory, resume_ids)


def cleanup_graph(contract: dict[str, Any], *, preview: bool) -> dict[str, Any]:
    """Inventory or remove only verified disposable graph worktrees, never source evidence."""
    state = _load_graph_state(contract)
    artifacts: list[dict[str, str]] = []
    repo = contract["repo"]
    for run_id in contract["order"]:
        child = _child_state(contract, run_id)
        if child is None:
            continue
        worktree = child.get("worktree")
        branch = child.get("branch")
        if isinstance(worktree, str):
            artifacts.append({"kind": "child_worktree", "path": worktree,
                              "owner": run_id, "disposition": "retain",
                              "reason": "child controller owns source and checker evidence"})
        if isinstance(branch, str):
            artifacts.append({"kind": "child_branch", "path": f"refs/heads/{branch}",
                              "owner": run_id, "disposition": "retain",
                              "reason": "accepted source branch is not disposable graph data"})
    for checkpoint in state["checkpoints"]:
        if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("run_id"), str):
            raise GraphError("checkpoint inventory is malformed; refusing cleanup preview")
        run_id = checkpoint["run_id"]
        if run_id not in contract["nodes"]:
            raise GraphError("checkpoint inventory names a foreign node")
        worktree = repo.parent / f"{repo.name}-{contract['graph_id']}-checkpoint-{run_id}"
        branch = f"refs/heads/agentsmith-graph/{contract['graph_id']}/checkpoint/{run_id}"
        verified = _checkpoint_commit(contract, run_id) == checkpoint.get("checkpoint_oid")
        disposition = ("eligible_after_explicit_cleanup" if worktree.exists() and verified
                       else "already_removed" if not worktree.exists() else "retain_ambiguous")
        reason = "verified graph-owned checkpoint" if verified else "checkpoint ownership is ambiguous"
        artifacts.extend([
            {"kind": "checkpoint_worktree", "path": str(worktree), "owner": contract["graph_id"],
             "disposition": disposition, "reason": reason},
            {"kind": "checkpoint_branch", "path": branch, "owner": contract["graph_id"],
             "disposition": "retain", "reason": "pinned dependency lineage must remain verifiable"},
        ])
    artifacts.append({"kind": "graph_state", "path": str(_graph_directory(contract)),
                      "owner": contract["graph_id"], "disposition": "retain",
                      "reason": "durable orchestration and audit evidence"})
    report = status(contract)
    if not preview:
        if report["status"] != "completed":
            raise GraphError("cleanup applies only after every child has accepted evidence")
        with _graph_lock(contract):
            removable: list[Path] = []
            common = common_directory(repo)
            checkpoint_ids = {
                str(repo.parent / f"{repo.name}-{contract['graph_id']}-checkpoint-{item['run_id']}"): item["run_id"]
                for item in state["checkpoints"]
            }
            for artifact in artifacts:
                if artifact["kind"] != "checkpoint_worktree" or artifact["disposition"] == "already_removed":
                    continue
                worktree = Path(artifact["path"])
                run_id = checkpoint_ids.get(str(worktree))
                if run_id is None:
                    raise GraphError(f"checkpoint worktree has no exact recorded owner: {worktree}")
                expected_ref = f"refs/heads/agentsmith-graph/{contract['graph_id']}/checkpoint/{run_id}"
                expected_oid = _checkpoint_commit(contract, run_id)
                marker = worktree / ".git"
                if (worktree.is_symlink() or not worktree.is_dir() or not marker.is_file()
                        or marker.is_symlink()):
                    raise GraphError(f"checkpoint worktree ownership is ambiguous: {worktree}")
                marker_text = marker.read_text(encoding="utf-8", errors="replace").strip()
                if not marker_text.startswith("gitdir: "):
                    raise GraphError(f"checkpoint worktree has no linked Git marker: {worktree}")
                admin = Path(marker_text[8:]).resolve()
                if (not admin.is_relative_to(common / "worktrees")
                        or Path(git(worktree, "rev-parse", "--show-toplevel")).resolve() != worktree.resolve()
                        or git(worktree, "symbolic-ref", "-q", "HEAD") != expected_ref
                        or git(worktree, "rev-parse", "HEAD") != expected_oid):
                    raise GraphError(f"checkpoint worktree does not match pinned branch and commit: {worktree}")
                if git(worktree, "status", "--porcelain", "--untracked-files=all", "--ignored=matching"):
                    raise GraphError(f"checkpoint worktree contains changes or untracked data: {worktree}")
                removable.append(worktree)
            for worktree in removable:
                removed = subprocess.run(["git", "worktree", "remove", str(worktree)], cwd=repo,
                                         text=True, capture_output=True, check=False)
                if removed.returncode:
                    raise GraphError(removed.stderr.strip() or f"could not remove checkpoint {worktree}")
            _graph_event(_graph_directory(contract), contract["graph_id"], "cleanup_completed",
                         reason=f"removed {len(removable)} clean graph-owned checkpoint worktree(s); refs retained")
        for artifact in artifacts:
            if artifact["kind"] == "checkpoint_worktree" and artifact["disposition"] == "eligible_after_explicit_cleanup":
                artifact["disposition"] = "removed"
    report["artifacts"] = artifacts
    return report


def integrate_graph(contract: dict[str, Any]) -> dict[str, Any]:
    """Compose accepted commits locally and verify the combined candidate."""
    directory = _graph_directory(contract)
    _load_graph_state(contract)
    with _graph_lock(contract):
        state = _load_graph_state(contract)
        if state["status"] != "completed" or status(contract)["status"] != "completed":
            raise GraphError("integration requires every child to have accepted evidence")
        if (directory / "integration-candidate.json").exists():
            raise GraphError("a verified local candidate already exists; inspect it before retry")
        repo = contract["repo"]
        sources: list[dict[str, Any]] = []
        for run_id in contract["order"]:
            child = _child_state(contract, run_id)
            if child is None or child.get("status") != "accepted":
                raise GraphError(f"child {run_id} has no accepted state")
            commit = _accepted_commit(contract, run_id, child)
            worktree_value = child.get("worktree")
            if not isinstance(worktree_value, str):
                raise GraphError(f"child {run_id} has no recorded worktree")
            worktree = Path(worktree_value)
            if (worktree.is_symlink() or not worktree.is_dir()
                    or common_directory(worktree) != common_directory(repo)
                    or git(worktree, "symbolic-ref", "-q", "HEAD") != f"refs/heads/agentsmith/{run_id}"
                    or git(worktree, "rev-parse", "HEAD") != commit
                    or git(worktree, "status", "--porcelain", "--untracked-files=all", "--ignored=matching")):
                raise GraphError(f"accepted source {run_id} worktree is missing, dirty, or moved")
            if contract["nodes"][run_id]["depends_on"]:
                _checkpoint_commit(contract, run_id)
            sources.append({"run_id": run_id, "accepted_commit": commit,
                            "receipt_sha256": checker_receipt_sha256(child["last_checker_receipt"]),
                            "already_included": False})
        attempt = 1
        while attempt <= 100:
            suffix = f"{attempt:03d}"
            branch = f"agentsmith-graph/{contract['graph_id']}/candidate/{suffix}"
            worktree = repo.parent / f"{repo.name}-{contract['graph_id']}-candidate-{suffix}"
            if (not worktree.exists() and not worktree.is_symlink()
                    and not git(repo, "show-ref", "--verify", f"refs/heads/{branch}", check=False)):
                break
            attempt += 1
        else:
            raise GraphError("candidate attempt namespace is exhausted")
        controller = _controller()
        try:
            with controller.git_phase(repo, "writer", timeout_seconds=60):
                created = subprocess.run(["git", "worktree", "add", "-b", branch, str(worktree),
                                          contract["contract_commit"]], cwd=repo, text=True,
                                         capture_output=True, check=False)
                if created.returncode:
                    raise GraphError(created.stderr.strip() or "candidate worktree creation failed")
                state["candidate_path"] = str(worktree)
                _save_graph_state(directory, state)
                hooks = directory / "empty-hooks"
                hooks.mkdir(exist_ok=True)
                for source in sources:
                    source_commit = source["accepted_commit"]
                    if git(repo, "rev-parse", f"refs/heads/agentsmith/{source['run_id']}") != source_commit:
                        raise GraphError(f"source branch moved before integrating {source['run_id']}")
                    included = subprocess.run(["git", "merge-base", "--is-ancestor", source_commit,
                                               "HEAD"], cwd=worktree, capture_output=True, check=False)
                    if included.returncode == 0:
                        source["already_included"] = True
                        continue
                    merged = subprocess.run(
                        ["git", "-c", f"core.hooksPath={hooks}", "-c", "commit.gpgsign=false",
                         "merge", "--no-ff", "--no-edit", source_commit],
                        cwd=worktree, text=True, capture_output=True, check=False,
                    )
                    if merged.returncode:
                        raise GraphError(f"candidate merge conflicts at {source['run_id']}; "
                                         f"retained at {worktree}: {merged.stderr.strip()}")
                candidate_commit = git(worktree, "rev-parse", "HEAD")
                candidate_tree = git(worktree, "rev-parse", "HEAD^{tree}")
        except (GraphError, controller.RunError) as exc:
            _graph_event(directory, contract["graph_id"], "candidate_failed",
                         reason=str(exc)[:500])
            raise GraphError(str(exc)) from exc
        if git(worktree, "status", "--porcelain", "--untracked-files=all"):
            raise GraphError(f"composed candidate is dirty at {worktree}")
        proof_dir = directory / f"verification-{suffix}"
        command = [sys.executable, str(Path(__file__).resolve().parent / "agentsmith.py"),
                   "verify", "--target", str(worktree), "--record", str(proof_dir),
                   "--tree-class", "linked-worktree"]
        verified = subprocess.run(command, cwd=worktree, text=True, capture_output=True, check=False)
        proof = proof_dir / "receipt.json"
        if verified.returncode or not proof.is_file():
            _graph_event(directory, contract["graph_id"], "candidate_failed",
                         reason=f"full verification failed for {branch}: " +
                                (verified.stderr.strip() or verified.stdout.strip())[-300:])
            raise GraphError(f"candidate {branch} failed full verification; worktree and proof retained")
        try:
            proof_record = json.loads(proof.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GraphError("candidate verification receipt is unreadable") from exc
        if proof_record.get("status") != "passed":
            raise GraphError("candidate verification receipt did not pass")
        candidate = {
            "schema_version": SCHEMA_VERSION, "graph_id": contract["graph_id"],
            "graph_sha256": contract["graph_sha256"], "contract_commit": contract["contract_commit"],
            "base_oid": contract["contract_commit"], "candidate_branch": branch,
            "candidate_commit": candidate_commit, "candidate_tree": candidate_tree,
            "sources": sources,
            "verification": {"command": "agentsmith verify (full configured phases)",
                             "exit_code": 0, "receipt_sha256": hashlib.sha256(proof.read_bytes()).hexdigest()},
            "created_at": _now(), "external_write_used": False, "human_approval_required": True,
        }
        if git(worktree, "rev-parse", "HEAD") != candidate_commit:
            raise GraphError("candidate moved during verification")
        path = directory / "integration-candidate.json"
        descriptor, temp_name = tempfile.mkstemp(prefix=".candidate.", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(candidate, indent=2, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            Path(temp_name).unlink(missing_ok=True)
        _graph_event(directory, contract["graph_id"], "candidate_created", commit=candidate_commit,
                     reason="accepted sources composed and full configured verification passed locally")
        return candidate
