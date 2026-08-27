#!/usr/bin/env python3
"""Immutable native-client launch primitives shared by autonomous runs and evaluations."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Iterable, Iterator


ALLOWED_ENVIRONMENT_KEYS = (
    "PATH", "HOME", "USERPROFILE", "USER", "USERNAME", "LOGNAME",
    "APPDATA", "LOCALAPPDATA", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT",
    "TMPDIR", "TEMP", "TMP", "LANG", "SHELL", "TERM", "COLORTERM", "NO_COLOR",
    "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "SSL_CERT_FILE", "SSL_CERT_DIR",
    "CODEX_HOME", "CLAUDE_CONFIG_DIR",
)


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
    values: list[Any] = []
    try:
        values.append(json.loads(stdout))
    except json.JSONDecodeError:
        for line in stdout.splitlines():
            try:
                values.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    costs: list[float] = []
    token_blocks: list[int] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            cost = value.get("total_cost_usd")
            if isinstance(cost, (int, float)):
                costs.append(float(cost))
            tokens = sum(
                int(value.get(key, 0))
                for key in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens")
                if isinstance(value.get(key, 0), (int, float))
            )
            if tokens:
                token_blocks.append(tokens)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for value in values:
        walk(value)
    return max(costs, default=0.0), max(token_blocks, default=0)


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


def claude_sandbox_settings(cwd: Path, extra_write_dirs: Iterable[Path] = (), *, read_only: bool = False) -> dict[str, Any]:
    writes = [] if read_only else [str(path) for path in extra_write_dirs]
    reads = [str(cwd), *[str(path) for path in extra_write_dirs]]
    return {
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "autoAllowBashIfSandboxed": True,
            "allowUnsandboxedCommands": False,
            "filesystem": {
                "allowWrite": writes,
                "denyRead": [str(Path.home())],
                "allowRead": reads,
            },
            "network": {"allowedDomains": [], "deniedDomains": ["*"]},
        },
        "permissions": {
            "deny": ["WebFetch", "WebSearch", "mcp__*"]
            + (["Edit", "Write", "NotebookEdit"] if read_only else [])
        },
        "enableAllProjectMcpServers": False,
    }


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
) -> list[str]:
    if agent == "codex":
        executable = os.environ.get("AGENTSMITH_CODEX_BIN", "codex")
        command = [executable, "exec", "--json", "--sandbox", "workspace-write"]
        for directory in extra_write_dirs:
            command += ["--add-dir", str(directory)]
        command += [
            "--disable", "hooks", "--disable", "plugins", "--disable", "remote_plugin",
            "--disable", "apps", "--disable", "skill_mcp_dependency_install",
            "-c", "mcp_servers={}",
            "-c", "sandbox_workspace_write.network_access=false", "-c", "approval_policy=never",
            "--output-schema", str(schema_path), "-o", str(receipt_path),
        ]
        if model:
            command += ["--model", model]
        if effort:
            command += ["-c", f'model_reasoning_effort="{effort}"']
        return [*command, prompt]
    if agent != "claude":
        raise ValueError(f"unsupported native client: {agent}")
    if settings_path is None:
        raise ValueError("Claude launches require an isolated settings path")
    executable = os.environ.get("AGENTSMITH_CLAUDE_BIN", "claude")
    command = [
        executable, "-p", "--output-format", "json", "--permission-mode", "dontAsk",
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


def client_version(executable: str) -> str:
    result = subprocess.run(
        [executable, "--version"], text=True, capture_output=True, check=False, timeout=10,
        env=minimal_environment(),
    )
    return (result.stdout or result.stderr).strip().splitlines()[0] if result.returncode == 0 and (result.stdout or result.stderr).strip() else "unknown"
