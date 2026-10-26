#!/usr/bin/env python3
"""Immutable native-client launch primitives shared by autonomous runs and evaluations."""

from __future__ import annotations

from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Iterator


ALLOWED_ENVIRONMENT_KEYS = (
    "PATH", "HOME", "USERPROFILE", "USER", "USERNAME", "LOGNAME",
    "APPDATA", "LOCALAPPDATA", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT",
    "TMPDIR", "TEMP", "TMP", "LANG", "SHELL", "TERM", "COLORTERM", "NO_COLOR",
    "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "SSL_CERT_FILE", "SSL_CERT_DIR",
    "CODEX_HOME", "CLAUDE_CONFIG_DIR",
)


def native_command_prefix(agent: str, executable: str | None = None) -> list[str]:
    """Return an argv prefix for a configured native client without a shell hop."""
    if agent not in {"claude", "codex"}:
        raise ValueError(f"unsupported native client: {agent}")
    configured = executable or os.environ.get(
        "AGENTSMITH_CLAUDE_BIN" if agent == "claude" else "AGENTSMITH_CODEX_BIN",
        agent,
    )
    if Path(configured).suffix.casefold() == ".py":
        return [sys.executable, configured]
    return [configured]


def minimal_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Allow only client-discovery, locale, temporary-directory, and certificate context."""
    parent = source if source is not None else os.environ
    allowed = set(ALLOWED_ENVIRONMENT_KEYS)
    env = {
        key: value
        for key, value in parent.items()
        if key.upper() in allowed or key.upper().startswith("LC_")
    }
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "/usr/bin/false" if os.name != "nt" else ""
    env.pop("SSH_AUTH_SOCK", None)
    return env


@contextmanager
def native_environment(
    agent: str, source: dict[str, str] | None = None
) -> Iterator[dict[str, str]]:
    """Yield an allowlisted environment with Codex configuration isolated from OAuth."""
    env = minimal_environment(source)
    if agent != "codex":
        yield env
        return

    home_value = env.get("CODEX_HOME") or env.get("HOME") or env.get("USERPROFILE")
    if not home_value:
        raise RuntimeError("Codex native launch requires a resolvable home directory")
    source_home = Path(home_value) if env.get("CODEX_HOME") else Path(home_value) / ".codex"
    source_home = source_home.expanduser().resolve()
    auth_path = source_home / "auth.json"
    try:
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Codex native launch requires readable ChatGPT subscription authentication") from exc
    if auth.get("auth_mode") != "chatgpt":
        raise RuntimeError("Codex native launch requires ChatGPT subscription authentication")

    with tempfile.TemporaryDirectory(
        prefix="agentsmith-codex-home-", dir=source_home.parent
    ) as temporary:
        isolated_home = Path(temporary)
        try:
            isolated_home.chmod(0o700)
        except OSError:
            pass
        isolated_auth = isolated_home / "auth.json"
        try:
            os.link(auth_path, isolated_auth, follow_symlinks=True)
        except OSError as exc:
            raise RuntimeError(
                "Codex native launch cannot safely bridge ChatGPT authentication on this filesystem"
            ) from exc
        (isolated_home / "config.toml").write_text(
            "check_for_update_on_startup = false\n\n[analytics]\nenabled = false\n",
            encoding="utf-8",
        )
        env["CODEX_HOME"] = str(isolated_home)
        yield env


def usage_metrics(stdout: str) -> tuple[float, int]:
    """Return the run's total (cost in USD, tokens) from a native client's JSON output.

    Codex reports usage once per turn, so a run costs the sum of its turns. Claude's final
    `result` message already totals the session, so when one is present it is the only source:
    adding the per-message usage that precedes it would count every token twice.
    """
    values: list[Any] = []
    try:
        values.append(json.loads(stdout))
    except json.JSONDecodeError:
        for line in stdout.splitlines():
            try:
                values.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    events = [item for value in values for item in (value if isinstance(value, list) else [value])]
    results = [event for event in events if isinstance(event, dict) and event.get("type") == "result"]
    token_keys = ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens")

    def amount(value: Any) -> float:
        # A negative or non-finite figure would refund the run-wide budget, so it counts as zero.
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return 0.0
        return max(0.0, float(value))

    def measure(value: Any) -> tuple[float, int]:
        # The outermost usage block counts once; nested breakdowns inside it are not added again.
        if isinstance(value, dict):
            cost = amount(value.get("total_cost_usd"))
            tokens = sum(int(amount(value.get(key))) for key in token_keys)
            if tokens:
                return cost, tokens
            for child in value.values():
                child_cost, child_tokens = measure(child)
                cost += child_cost
                tokens += child_tokens
            return cost, tokens
        if isinstance(value, list):
            measured = [measure(child) for child in value]
            return sum(item[0] for item in measured), sum(item[1] for item in measured)
        return 0.0, 0

    measured = [measure(event) for event in (results or events)]
    return sum(item[0] for item in measured), sum(item[1] for item in measured)


def nested_object(value: Any, required: Iterable[str]) -> dict[str, Any] | None:
    keys = set(required)
    if isinstance(value, dict):
        if keys.issubset(value):
            return value
        for key in ("structured_output", "result", "output", "message", "content", "item"):
            if key in value:
                found = nested_object(value[key], keys)
                if found:
                    return found
        for child in value.values():
            found = nested_object(child, keys)
            if found:
                return found
    elif isinstance(value, list):
        for child in reversed(value):
            found = nested_object(child, keys)
            if found:
                return found
    elif isinstance(value, str):
        try:
            return nested_object(json.loads(value), keys)
        except json.JSONDecodeError:
            return None
    return None


def parse_structured_output(receipt_path: Path | None, stdout: str, required: Iterable[str]) -> dict[str, Any]:
    candidates: list[Any] = []
    if receipt_path and receipt_path.exists():
        try:
            candidates.append(json.loads(receipt_path.read_text(encoding="utf-8")))
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
    for candidate in reversed(candidates):
        found = nested_object(candidate, required)
        if found:
            return found
    raise ValueError("native client emitted no schema-shaped structured output")


def claude_sandbox_settings(cwd: Path, extra_write_dirs: Iterable[Path] = (), *, read_only: bool = False,
                            protected_write_paths: Iterable[Path] = ()) -> dict[str, Any]:
    writes = [] if read_only else [str(path) for path in extra_write_dirs]
    reads = [str(cwd), *[str(path) for path in extra_write_dirs]]
    protected = [str(path.resolve()) for path in protected_write_paths]
    return {
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "autoAllowBashIfSandboxed": True,
            "allowUnsandboxedCommands": False,
            "filesystem": {
                "allowWrite": writes,
                "denyWrite": [*([str(cwd)] if read_only else []), *protected],
                "denyRead": [str(Path.home())],
                "allowRead": reads,
            },
            "network": {"allowedDomains": [], "deniedDomains": ["*"]},
        },
        "permissions": {
            "deny": ["WebFetch", "WebSearch", "mcp__*"]
            + (["Edit", "Write", "NotebookEdit"] if read_only else [])
            + [f"Edit(/{path})" for path in protected]
            + [f"Edit(/{path}/**)" for path in protected]
        },
        "enableAllProjectMcpServers": False,
        "disableAllHooks": True,
    }


def codex_permissions(cwd: Path, extra_write_dirs: Iterable[Path] = (), *, read_only: bool = False,
                      protected_write_paths: Iterable[Path] = ()) -> dict[str, Any]:
    temporary_access = 'read' if read_only else 'write'
    filesystem = {':root': 'read', ':tmpdir': temporary_access, ':slash_tmp': temporary_access}
    if not read_only:
        for path in (cwd, *extra_write_dirs):
            filesystem[str(path.resolve())] = 'write'
    for path in protected_write_paths:
        filesystem[str(path.resolve())] = 'read'
    return {'filesystem': filesystem, 'network': {'enabled': False}}


def toml_inline(value: Any) -> str:
    if isinstance(value, dict):
        return '{' + ','.join(json.dumps(key) + '=' + toml_inline(item) for key, item in value.items()) + '}'
    if isinstance(value, bool):
        return str(value).lower()
    return json.dumps(value)


def build_native_command(
    agent: str,
    prompt: str,
    cwd: Path,
    schema_path: Path,
    receipt_path: Path,
    *,
    settings_path: Path | None = None,
    extra_write_dirs: Iterable[Path] = (),
    read_only: bool = False,
    model: str = "",
    effort: str = "",
    claude_max_usd: float = 0.0,
    protected_write_paths: Iterable[Path] = (),
) -> list[str]:
    if agent == "codex":
        protected = list(protected_write_paths)
        command = [*native_command_prefix(agent), "exec", "--json"]
        if protected:
            permissions = codex_permissions(cwd, extra_write_dirs, read_only=read_only,
                                           protected_write_paths=protected)
            command += ['--strict-config', '-c', 'default_permissions="agentsmith"',
                        '-c', 'permissions=' + toml_inline({'agentsmith': permissions})]
        else:
            command += ['--sandbox', 'read-only' if read_only else 'workspace-write']
        for directory in (() if read_only else extra_write_dirs):
            command += ["--add-dir", str(directory)]
        command += [
            "--disable", "hooks", "--disable", "plugins", "--disable", "remote_plugin",
            "--disable", "apps", "--disable", "skill_mcp_dependency_install",
            "-c", "mcp_servers={}",
            "-c", "approval_policy=never",
            "--output-schema", str(schema_path), "-o", str(receipt_path),
        ]
        if not protected:
            command += ['-c', 'sandbox_workspace_write.network_access=false']
        if model:
            command += ["--model", model]
        if effort:
            command += ["-c", f'model_reasoning_effort="{effort}"']
        return [*command, prompt]
    if agent != "claude":
        raise ValueError(f"unsupported native client: {agent}")
    if settings_path is None:
        raise ValueError("Claude launches require an isolated settings path")
    command = [
        *native_command_prefix(agent), "-p", "--output-format", "json", "--permission-mode", "dontAsk",
        "--setting-sources", "", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
        "--settings", str(settings_path), "--json-schema", schema_path.read_text(encoding="utf-8"),
    ]
    if model:
        command += ["--model", model]
    if effort:
        command += ["--effort", effort]
    if claude_max_usd > 0:
        command += ["--max-budget-usd", str(claude_max_usd)]
    return [*command, prompt]


def client_version(executable: str | Iterable[str]) -> str:
    command = [executable] if isinstance(executable, str) else list(executable)
    result = subprocess.run(
        [*command, "--version"], text=True, capture_output=True, check=False, timeout=10,
        env=minimal_environment(),
    )
    return (result.stdout or result.stderr).strip().splitlines()[0] if result.returncode == 0 and (result.stdout or result.stderr).strip() else "unknown"
