#!/usr/bin/env python3
"""Agentsmith's cross-platform installer and runtime.

Python 3.11+ and the standard library are the compatibility boundary.  The two
setup launchers do nothing except find a suitable interpreter and execute this
file, so macOS, Linux, and native Windows exercise the same implementation.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import tomllib
from typing import Any, Iterable
import urllib.error
import urllib.request


VERSION = "0.2.0"
OFFICIAL_REMOTE = "https://github.com/PromptPartner/agentsmith.git"
ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "config" / "agents.json"
BEGIN = "<!-- BEGIN AGENTSMITH — universal agent harness (managed by agentsmith — edit core/profiles, not here) -->"
END = "<!-- END AGENTSMITH -->"
LEGACY_BEGIN = "<!-- BEGIN AGENTSMITH — universal agent harness (managed by setup.sh — edit core/profiles, not here) -->"
OLDER_BEGIN = "<!-- BEGIN UNIVERSAL CLAUDE HARNESS (managed by setup.sh — edit core/profiles, not here) -->"
OLDER_END = "<!-- END UNIVERSAL CLAUDE HARNESS -->"
TEXT_BEGIN = "# BEGIN AGENTSMITH MANAGED"
TEXT_END = "# END AGENTSMITH MANAGED"
TRACKER_ASK = (
    "**writes are NOT authorized** — draft the entry and surface it for the operator to post; "
    "never create or comment on items yourself. Offer once; if they say yes, that's durable for this session."
)
TRACKER_ALLOWED = (
    "**writes are authorized** (the operator opted in at setup) — file it directly, and make agent work "
    "visible there (a note when work starts and when it lands)."
)
AGENT_IDS = (
    "claude", "codex", "github-copilot", "cursor", "gemini-cli", "windsurf-devin", "cline", "roo-code", "aider",
    "continue", "openhands", "goose", "opencode", "jetbrains-junie", "zed", "jules",
)
GROUPS = {
    "native": ("claude", "codex"),
    "standard": AGENT_IDS[2:],
    "local": ("aider", "cline", "openhands", "goose", "opencode"),
    "all": AGENT_IDS,
}
CODE_PROFILES = {"software-dev", "devops-setup"}
RUNTIME_FILES = (
    ".agentsmith/agentsmith.py",
    ".agentsmith/agentsmith",
    ".agentsmith/agentsmith.cmd",
    ".agentsmith/config/agents.json",
    ".agentsmith/evaluate.py",
    ".agentsmith/native_launcher.py",
)
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


class CliError(RuntimeError):
    pass


def say(message: str) -> None:
    print(f"» {message}")


def ok(message: str) -> None:
    # Native Windows may start Python with a legacy CP-1252 console. Keep the
    # installer usable before the operator has configured UTF-8 output.
    print(f"  [ok] {message}")


def warn(message: str) -> None:
    print(f"  ! {message}", file=sys.stderr)


def require_python() -> None:
    if sys.version_info < (3, 11):
        raise CliError(
            f"Agentsmith requires Python 3.11 or newer; found {sys.version.split()[0]}. "
            "Install Python 3.11+ and rerun the same command."
        )


def load_registry() -> dict[str, Any]:
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(f"Cannot load agent registry {REGISTRY_PATH}: {exc}") from exc
    return data


def csv(values: Iterable[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or ():
        result.extend(part.strip() for part in value.split(",") if part.strip())
    return result


def resolve_agents(agent_values: Iterable[str] | None, platform: str | None) -> list[str]:
    if agent_values and platform:
        raise CliError("--agent and --platform cannot be combined; --platform is the backward-compatible alias")
    requested = csv(agent_values)
    if platform:
        requested = {"both": ["claude", "codex"]}.get(platform, [platform])
    if not requested:
        requested = ["claude"]  # migration-compatible default
    expanded: list[str] = []
    for value in requested:
        choices = GROUPS.get(value, (value,))
        for choice in choices:
            if choice not in AGENT_IDS:
                raise CliError(f"Unknown agent or group '{value}'. Run 'agentsmith agents list'.")
            if choice not in expanded:
                expanded.append(choice)
    return expanded


def home_dir() -> Path:
    # PowerShell passes HOME through on every OS; Path.home() can ignore that on Windows.
    return Path(os.environ.get("HOME") or os.environ.get("USERPROFILE") or str(Path.home())).expanduser()


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or home_dir() / ".codex").expanduser()


def backup(path: Path) -> Path | None:
    if not path.exists() or not path.is_file():
        return None
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.name}.bak.{stamp}")
    counter = 0
    while candidate.exists():
        counter += 1
        candidate = path.with_name(f"{path.name}.bak.{stamp}.{counter}")
    shutil.copy2(path, candidate)
    return candidate


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    newline = "\r\n" if path.exists() and "\r\n" in path.read_text(encoding="utf-8", errors="replace") else "\n"
    content = content.replace("\r\n", "\n").replace("\n", newline)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temp = Path(handle.name)
    try:
        replace_with_retry(temp, path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def replace_with_retry(source: Path, destination: Path) -> None:
    delays = (0.05, 0.1, 0.2)
    for attempt in range(len(delays) + 1):
        try:
            source.replace(destination)
            return
        except PermissionError:
            if attempt == len(delays):
                raise
            time.sleep(delays[attempt])


def atomic_write_bytes(path: Path, content: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        temp = Path(handle.name)
    if mode is not None:
        temp.chmod(mode)
    try:
        replace_with_retry(temp, path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def managed_markers(text: str) -> tuple[str, str] | None:
    for begin, end in ((BEGIN, END), (LEGACY_BEGIN, END), (OLDER_BEGIN, OLDER_END)):
        if begin in text:
            return begin, end
    return None


def reconcile_markdown(path: Path, block: str, *, force: bool, dry_run: bool) -> None:
    if dry_run:
        say(f"DRY RUN — would reconcile {path}")
        return
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    markers = managed_markers(old)
    if markers:
        begin, end = markers
        pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
        rendered = pattern.sub(block.rstrip(), old, count=1)
        rendered = rendered.rstrip() + "\n"
        if rendered == old:
            ok(f"managed instructions already current in {path}")
            return
        backup(path)
        atomic_write(path, rendered)
        ok(f"updated managed instructions in {path}")
    elif old and not force:
        bak = backup(path)
        atomic_write(path, old.rstrip() + "\n\n" + block.rstrip() + "\n")
        ok(f"appended managed instructions to {path} (backup: {bak.name if bak else 'none'})")
    else:
        if old:
            backup(path)
        atomic_write(path, block.rstrip() + "\n")
        ok(f"wrote {path}")


def remove_managed_markdown(path: Path, *, dry_run: bool) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    markers = managed_markers(text)
    if not markers:
        return
    if dry_run:
        say(f"DRY RUN — would remove managed instructions from {path}")
        return
    backup(path)
    begin, end = markers
    remaining = re.sub(re.escape(begin) + r".*?" + re.escape(end), "", text, count=1, flags=re.S).strip()
    if remaining:
        atomic_write(path, remaining + "\n")
    else:
        path.unlink()
    ok(f"removed managed instructions from {path}")


def recover_identity(paths: Iterable[Path]) -> dict[str, str]:
    values: dict[str, str] = {}
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"\*\*(.+?)\*\* is the lead\. Role: \*\*(.+?)\*\*\.", text)
        if match:
            values.setdefault("operator_name", match.group(1))
            values.setdefault("operator_role", match.group(2))
            tail = text[match.end():]
            bio = next((line.strip() for line in tail.splitlines() if line.strip()), "")
            if bio and not bio.startswith("When you explain"):
                values.setdefault("operator_bio", bio)
        tracker = re.search(r"The team's record is \*\*(.+?)\*\*", text)
        if not tracker:
            tracker = re.search(r"File it in \*\*(.+?)\*\*", text)
        if tracker:
            values.setdefault("tracker", tracker.group(1))
            values.setdefault("tracker_writes", "allowed" if "writes are authorized" in text else "ask")
        if values:
            break
    return values


def detect_profile(target: Path) -> str:
    names = {p.name for p in target.iterdir()} if target.exists() else set()
    if names & {"go.mod", "package.json", "tsconfig.json", "Cargo.toml", "pyproject.toml", "requirements.txt", "pom.xml", "Gemfile", "composer.json"}:
        return "software-dev"
    if names & {"Dockerfile", "ansible.cfg", "Vagrantfile"} or any(target.glob("*.tf")):
        return "devops-setup"
    if any(target.glob("*.ipynb")) or any(target.glob("*.csv")) or (target / "notebooks").is_dir():
        return "data-crunching"
    if (target / "docs").is_dir() or names & {"mkdocs.yml", "_config.yml"}:
        return "document-creation"
    if any(target.glob(ext) for ext in ("*.py", "*.js", "*.ts", "*.go", "*.rs")):
        return "software-dev"
    return "general-admin"


def build_instructions(args: argparse.Namespace, profiles: list[str], include_core: bool, recovery: dict[str, str]) -> str:
    operator_name = args.operator_name or recovery.get("operator_name") or "the project lead"
    operator_role = args.operator_role or recovery.get("operator_role") or "owner / decision-maker"
    operator_bio = args.operator_bio or recovery.get("operator_bio") or (
        "They decide direction and accept the risk; you are the technical co-pilot — proactive, "
        "evidence-driven, and honest about trade-offs."
    )
    tracker = args.tracker or recovery.get("tracker") or "your project's tracker (or a KNOWN-ISSUES.md at the repo root)"
    tracker_writes = args.tracker_writes or recovery.get("tracker_writes") or "ask"
    parts = [BEGIN, f"<!-- Generated. Profiles: {','.join(profiles) or 'none'}. core={str(include_core).lower()}. Edit core/ or profiles/, then re-run setup. -->", ""]
    if include_core:
        for source in sorted((ROOT / "core").glob("*.md")):
            parts.extend((source.read_text(encoding="utf-8").rstrip(), "", ""))
    if profiles:
        parts.extend(("---", "", f"# Work-Type Profile(s): {','.join(profiles)}", ""))
        for profile in profiles:
            source = ROOT / "profiles" / f"{profile}.md"
            if not source.exists():
                available = ", ".join(p.stem for p in sorted((ROOT / "profiles").glob("*.md")))
                raise CliError(f"No such profile '{profile}'. Available: {available}")
            parts.extend((source.read_text(encoding="utf-8").rstrip(), "", ""))
    parts.append(END)
    replacements = {
        "OPERATOR_NAME": operator_name,
        "OPERATOR_ROLE": operator_role,
        "OPERATOR_BIO": operator_bio,
        "TRACKER": tracker,
        "TRACKER_POLICY": TRACKER_ALLOWED if tracker_writes == "allowed" else TRACKER_ASK,
    }
    rendered = "\n".join(parts)
    for key, value in replacements.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return re.sub(r"\{\{([A-Z_]+)\}\}", r"[TODO: set \1]", rendered)


def merge_json(path: Path, mutation: Any, *, dry_run: bool) -> None:
    if dry_run:
        say(f"DRY RUN — would reconcile {path}")
        return
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    try:
        data = json.loads(original) if original.strip() else {}
    except json.JSONDecodeError as exc:
        raise CliError(f"Refusing to modify invalid JSON {path}: {exc}") from exc
    mutation(data)
    rendered = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if original == rendered:
        ok(f"managed JSON already current in {path}")
        return
    if original:
        backup(path)
    atomic_write(path, rendered)
    json.loads(path.read_text(encoding="utf-8"))
    ok(f"reconciled {path}")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def available_statusline_path(base: Path, prior_files: dict[str, Any]) -> Path:
    prior = next((Path(raw) for raw in prior_files if Path(raw).suffix == base.suffix), None)
    if prior is not None:
        return prior
    if not base.exists():
        return base
    counter = 1
    while True:
        candidate = base.with_name(f"{base.stem}-{counter}{base.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def statusline_owner(target: Path, global_mode: bool) -> str:
    return "global" if global_mode else f"project:{target.resolve()}"


def claude_statusline_installation(prior: dict[str, Any] | None) -> tuple[dict[str, str], list[tuple[Path, str]]]:
    source = ROOT / "config" / "statusline.py"
    prior_files = prior.get("files", {}) if isinstance(prior, dict) else {}
    if not isinstance(prior_files, dict):
        prior_files = {}
    destination = available_statusline_path(
        home_dir() / ".claude" / "agentsmith-statusline.py", prior_files
    )
    files = [(destination, source.read_text(encoding="utf-8"))]
    if os.name == "nt":
        wrapper = available_statusline_path(
            home_dir() / ".claude" / "agentsmith-statusline.ps1", prior_files
        )
        python_literal = str(Path(sys.executable).resolve()).replace("'", "''")
        script_literal = str(destination).replace("'", "''")
        files.append(
            (
                wrapper,
                # Preserve Claude's JSON bytes; Windows PowerShell pipelines re-encode native stdin.
                f"& '{python_literal}' '{script_literal}'\n"
                "exit $LASTEXITCODE\n",
            )
        )
        command = f'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{wrapper.as_posix()}"'
    else:
        command = native_command(str(Path(sys.executable).resolve()), str(destination))
    return {"type": "command", "command": command}, files


def install_default_statuslines(
    agents: list[str], target: Path, global_mode: bool, *, dry_run: bool
) -> None:
    """Activate defaults only where a client has no active built-in or explicit choice."""
    if "claude" not in agents:
        return
    settings_path = home_dir() / ".claude" / "settings.json"
    original = settings_path.read_text(encoding="utf-8") if settings_path.exists() else ""
    try:
        data = json.loads(original) if original.strip() else {}
    except json.JSONDecodeError as exc:
        raise CliError(f"Refusing to modify invalid JSON {settings_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CliError(f"Refusing to replace non-object Claude settings in {settings_path}")

    state = load_state(home_dir())
    ownership = state.get("native_statuslines", {})
    if not isinstance(ownership, dict):
        ownership = {}
    prior = ownership.get("claude")
    prior_value = prior.get("value") if isinstance(prior, dict) else None
    current_is_owned = isinstance(prior, dict) and data.get("statusLine") == prior_value
    if "statusLine" in data and not current_is_owned:
        if "claude" in ownership and not dry_run:
            ownership.pop("claude", None)
            record_state(home_dir(), "native_statuslines", ownership, dry_run=False)
        return

    value, assets = claude_statusline_installation(prior if isinstance(prior, dict) else None)
    if dry_run:
        say(f"DRY RUN — would activate the default Claude status line in {settings_path}")
        return

    prior_files = prior.get("files", {}) if isinstance(prior, dict) else {}
    if not isinstance(prior_files, dict):
        prior_files = {}
    installed_files: dict[str, str] = {}
    for path, content in assets:
        rendered = content.replace("\r\n", "\n")
        if path.exists() and path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n") != rendered:
            expected_hash = prior_files.get(str(path))
            if expected_hash and file_sha256(path) != expected_hash:
                warn(f"modified AgentSmith status-line helper preserved: {path}")
                installed_files[str(path)] = expected_hash
                continue
            backup(path)
        if not path.exists() or path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n") != rendered:
            atomic_write(path, rendered)
        installed_files[str(path)] = file_sha256(path)

    def activate(current: dict[str, Any]) -> None:
        current["statusLine"] = value

    merge_json(settings_path, activate, dry_run=False)
    owners = prior.get("owners", []) if isinstance(prior, dict) else []
    if not isinstance(owners, list):
        owners = []
    owner = statusline_owner(target, global_mode)
    owners = list(dict.fromkeys([*owners, owner]))
    ownership["claude"] = {"value": value, "files": installed_files, "owners": owners}
    record_state(home_dir(), "native_statuslines", ownership, dry_run=False)
    if data.get("disableAllHooks") is True:
        warn("Claude's explicit disableAllHooks=true also disables its configured status line")


def remove_default_statuslines(
    agents: list[str], target: Path, global_mode: bool, *, dry_run: bool
) -> None:
    if "claude" not in agents:
        return
    state = load_state(home_dir())
    ownership = state.get("native_statuslines", {})
    if not isinstance(ownership, dict) or not isinstance(ownership.get("claude"), dict):
        return
    prior = ownership["claude"]
    settings_path = home_dir() / ".claude" / "settings.json"
    data: dict[str, Any] = {}
    if settings_path.exists():
        try:
            loaded = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CliError(f"Refusing to modify invalid JSON {settings_path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise CliError(f"Refusing to replace non-object Claude settings in {settings_path}")
        data = loaded
    owned_value_active = data.get("statusLine") == prior.get("value")
    if "statusLine" in data and not owned_value_active:
        if not dry_run:
            ownership.pop("claude", None)
            record_state(home_dir(), "native_statuslines", ownership, dry_run=False)
        return

    owners = prior.get("owners", [])
    if not isinstance(owners, list):
        owners = []
    owner = statusline_owner(target, global_mode)
    if owners and owner not in owners:
        return
    remaining_owners = [value for value in owners if value != owner]
    if remaining_owners:
        if not dry_run:
            prior["owners"] = remaining_owners
            ownership["claude"] = prior
            record_state(home_dir(), "native_statuslines", ownership, dry_run=False)
        return
    if owned_value_active:
        if dry_run:
            say(f"DRY RUN — would remove AgentSmith's default Claude status line from {settings_path}")
        else:
            data.pop("statusLine", None)
            backup(settings_path)
            if data:
                atomic_write(settings_path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            else:
                settings_path.unlink()

    files = prior.get("files", {})
    if isinstance(files, dict) and (owned_value_active or "statusLine" not in data):
        for raw_path, expected_hash in files.items():
            path = Path(raw_path)
            if not path.is_file():
                continue
            if not isinstance(expected_hash, str) or file_sha256(path) != expected_hash:
                warn(f"modified AgentSmith status-line helper preserved: {path}")
                continue
            if dry_run:
                say(f"DRY RUN — would remove AgentSmith's status-line helper {path}")
            else:
                path.unlink()
    if not dry_run:
        ownership.pop("claude", None)
        record_state(home_dir(), "native_statuslines", ownership, dry_run=False)


def state_path(target: Path) -> Path:
    return target / ".agentsmith" / "state.json"


def load_state(target: Path) -> dict[str, Any]:
    path = state_path(target)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        warn(f"invalid ownership state ignored: {path}")
        return {}


def load_update_state(target: Path) -> dict[str, Any]:
    path = state_path(target)
    if not path.exists():
        return {}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(f"Cannot use malformed update state {path}: {exc}") from exc
    if not isinstance(state, dict):
        raise CliError(f"Cannot use non-object update state {path}")
    return state


def record_state(target: Path, key: str, value: Any, *, dry_run: bool) -> None:
    if dry_run:
        return
    state = load_state(target)
    state[key] = value
    path = state_path(target)
    rendered = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != rendered:
        atomic_write(path, rendered)


def source_release_identity() -> dict[str, str | None]:
    """Describe this runtime without mistaking an installed project for the source checkout."""
    identity: dict[str, str | None] = {"release": None, "commit": None}
    if not shutil.which("git"):
        return identity
    probe = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--show-toplevel", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    lines = probe.stdout.splitlines()
    if probe.returncode or len(lines) != 2:
        return identity
    try:
        source_root = Path(lines[0]).resolve()
    except OSError:
        return identity
    if source_root != ROOT.resolve():
        return identity
    unstaged = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet"], check=False)
    staged = subprocess.run(["git", "-C", str(ROOT), "diff", "--cached", "--quiet"], check=False)
    if unstaged.returncode or staged.returncode:
        return identity
    identity["commit"] = lines[1]
    tag = subprocess.run(
        ["git", "-C", str(ROOT), "describe", "--tags", "--exact-match", "--match", "v[0-9]*"],
        text=True,
        capture_output=True,
        check=False,
    )
    candidate = tag.stdout.strip()
    if tag.returncode == 0 and candidate == f"v{VERSION}":
        identity["release"] = candidate
    return identity


def record_installation_manifest(
    target: Path,
    agents: list[str],
    profiles: list[str],
    args: argparse.Namespace,
    recovery: dict[str, str],
) -> None:
    if args.dry_run:
        return
    manifest_root = home_dir() if args.global_mode else target
    state = load_state(manifest_root)
    prior_installation = state.get("installation", {})
    source = source_release_identity()
    if not source.get("commit") and isinstance(prior_installation, dict):
        prior_source = prior_installation.get("source")
        if isinstance(prior_source, dict):
            source = {
                "release": prior_source.get("release") if isinstance(prior_source.get("release"), str) else None,
                "commit": prior_source.get("commit") if isinstance(prior_source.get("commit"), str) else None,
            }
    requested_mcp = csv(args.with_mcp)
    available_mcp = json.loads((ROOT / "config" / "mcp.example.json").read_text(encoding="utf-8"))["mcpServers"]
    prior_capabilities = prior_installation.get("capabilities", {}) if isinstance(prior_installation, dict) else {}
    if not isinstance(prior_capabilities, dict):
        prior_capabilities = {}
    prior_mcp = prior_capabilities.get("mcp", [])
    if not isinstance(prior_mcp, list):
        prior_mcp = []
    mcp_names = list(dict.fromkeys(
        name for name in [*prior_mcp, *requested_mcp]
        if isinstance(name, str) and name in available_mcp
    ))
    safety = {
        agent_id: args.safety
        for agent_id in agents
        if agent_id in {"claude", "codex"}
    }
    state["schema_version"] = 1
    managed_files: list[dict[str, str]] = []
    managed_root = home_dir() if args.global_mode else target
    for relative_root in (Path(".agents") / "skills", Path(".claude") / "skills"):
        skill_root = managed_root / relative_root
        if not skill_root.is_dir():
            continue
        for path in sorted(skill_root.rglob("*")):
            if path.is_file():
                managed_files.append({
                    "root": "home" if args.global_mode else "target",
                    "path": path.relative_to(managed_root).as_posix(),
                    "sha256": file_sha256(path),
                })
    state["installation"] = {
        "installed_version": VERSION,
        "source": source,
        "scope": "global" if args.global_mode else "project",
        "agents": agents,
        "profiles": profiles,
        "include_core": not args.profile_only,
        "safety": safety,
        "operator": {
            "name": args.operator_name or recovery.get("operator_name") or "the project lead",
            "role": args.operator_role or recovery.get("operator_role") or "owner / decision-maker",
            "bio": args.operator_bio or recovery.get("operator_bio") or (
                "They decide direction and accept the risk; you are the technical co-pilot — proactive, "
                "evidence-driven, and honest about trade-offs."
            ),
        },
        "tracker": {
            "name": args.tracker or recovery.get("tracker") or "your project's tracker (or a KNOWN-ISSUES.md at the repo root)",
            "writes": args.tracker_writes or recovery.get("tracker_writes") or "ask",
        },
        "capabilities": {
            "handoff_hooks": bool(args.with_handoff_hooks or prior_capabilities.get("handoff_hooks")),
            "hooks": bool(args.with_hooks or prior_capabilities.get("hooks")),
            "mcp": mcp_names,
            "skills": bool(args.with_skills or prior_capabilities.get("skills")),
            "ui_design_hook": bool(args.with_ui_design_hook or prior_capabilities.get("ui_design_hook")),
        },
        "managed_files": managed_files,
    }
    path = state_path(manifest_root)
    rendered = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != rendered:
        atomic_write(path, rendered)


def reconcile_text_block(path: Path, block: str, *, dry_run: bool) -> None:
    if dry_run:
        say(f"DRY RUN — would reconcile {path}")
        return
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    pattern = re.compile(rf"(?ms)^\s*{re.escape(TEXT_BEGIN)}\n.*?^{re.escape(TEXT_END)}\s*\n?")
    foreign = pattern.sub("", old).rstrip()
    rendered = (foreign + "\n\n" if foreign else "") + block.rstrip() + "\n"
    if old == rendered:
        ok(f"managed config already current in {path}")
        return
    if old:
        backup(path)
    atomic_write(path, rendered)
    ok(f"reconciled {path}")


def mcp_source(names: Iterable[str]) -> dict[str, Any]:
    source = json.loads((ROOT / "config" / "mcp.example.json").read_text(encoding="utf-8"))["mcpServers"]
    selected: dict[str, Any] = {}
    for name in names:
        if name not in source:
            warn(f"unknown MCP server '{name}' skipped")
            continue
        selected[name] = {k: v for k, v in source[name].items() if k != "_use"}
    return selected


def toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, bool):
        return str(value).lower()
    raise TypeError(type(value).__name__)


def reconcile_codex_toml(path: Path, safety: str | None, mcp: dict[str, Any], *, dry_run: bool) -> None:
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    managed_pattern = re.compile(rf"(?ms)^\s*{re.escape(TEXT_BEGIN)}\n.*?^{re.escape(TEXT_END)}\s*\n?")
    old_match = managed_pattern.search(old)
    old_block = old_match.group(0) if old_match else ""
    foreign = managed_pattern.sub("", old).lstrip("\n")
    available = json.loads((ROOT / "config" / "mcp.example.json").read_text(encoding="utf-8"))["mcpServers"]
    prior_names = set(re.findall(r"(?m)^\[mcp_servers\.([A-Za-z0-9_-]+)\]\s*$", old_block))
    manual_names = set(re.findall(r"(?m)^\[mcp_servers\.([A-Za-z0-9_-]+)(?:\.[^]]+)?\]\s*$", foreign))
    selected = dict(mcp)
    for name in prior_names:
        if name in available and name not in selected:
            selected[name] = {key: value for key, value in available[name].items() if key != "_use"}
    for name in sorted(manual_names & set(selected)):
        warn(f"manual MCP server '{name}' wins; managed duplicate skipped")
        selected.pop(name)
    lines = [TEXT_BEGIN]
    if safety:
        lines.extend(
            ['approval_policy = "on-request"', 'sandbox_mode = "workspace-write"']
            if safety == "cautious" else ['approval_policy = "never"', 'sandbox_mode = "danger-full-access"']
        )
    for name, entry in sorted(selected.items()):
        lines.extend(("", f"[mcp_servers.{name}]"))
        for key, value in entry.items():
            if key != "env":
                lines.append(f"{key} = {toml_value(value)}")
        if entry.get("env"):
            lines.extend(("", f"[mcp_servers.{name}.env]"))
            for key, value in entry["env"].items():
                lines.append(f"{key} = {toml_value(value)}")
    lines.append(TEXT_END)
    block = "\n".join(lines) + "\n"
    first_table = re.search(r"(?m)^\s*\[", foreign)
    if first_table:
        prefix, tables = foreign[:first_table.start()], foreign[first_table.start():]
        rendered = prefix.rstrip("\n") + ("\n" if prefix.strip() else "") + block + tables.lstrip("\n")
    else:
        rendered = foreign.rstrip("\n") + ("\n" if foreign.strip() else "") + block
    if old == rendered:
        ok(f"managed Codex TOML already current in {path}")
        return
    if dry_run:
        say(f"DRY RUN — would reconcile {path}")
        return
    import tomllib
    try:
        tomllib.loads(rendered)
    except Exception as exc:
        raise CliError(f"Refusing to write invalid generated TOML {path}: {exc}") from exc
    if old:
        backup(path)
    atomic_write(path, rendered)
    ok(f"reconciled {path}")
    if not dry_run:
        with path.open("rb") as handle:
            tomllib.load(handle)


def install_skills(target: Path, agents: list[str], *, force: bool, dry_run: bool) -> None:
    canonical = target / ".agents" / "skills"
    destinations = [canonical]
    if "claude" in agents:
        destinations.append(target / ".claude" / "skills")
    for destination in destinations:
        if dry_run:
            say(f"DRY RUN — would install canonical skills into {destination}")
            continue
        destination.mkdir(parents=True, exist_ok=True)
        for source in sorted((ROOT / "skills").iterdir()):
            if not source.is_dir() or not (source / "SKILL.md").exists():
                continue
            dest = destination / source.name
            if dest.exists() and not force:
                continue
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(source, dest)
        ok(f"skills installed into {destination}")


def install_adapters(target: Path, agents: list[str], *, dry_run: bool) -> None:
    if "gemini-cli" in agents:
        gemini_path = target / ".gemini" / "settings.json"
        existing_gemini: dict[str, Any] = {}
        if gemini_path.exists():
            try:
                existing_gemini = json.loads(gemini_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        existing_names = existing_gemini.get("context", {}).get("fileName", [])
        if isinstance(existing_names, str):
            existing_names = [existing_names]
        def gemini(data: dict[str, Any]) -> None:
            context = data.setdefault("context", {})
            current = context.get("fileName", [])
            if isinstance(current, str):
                current = [current]
            context["fileName"] = list(dict.fromkeys([*current, "AGENTS.md"]))
        merge_json(gemini_path, gemini, dry_run=dry_run)
        prior_owned = load_state(target).get("gemini_context_added", False)
        record_state(target, "gemini_context_added", prior_owned or "AGENTS.md" not in existing_names, dry_run=dry_run)
    if "aider" in agents:
        path = target / ".aider.conf.yml"
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if re.search(r"(?m)^\s*-\s*AGENTS\.md\s*(?:#.*)?$", existing):
            pass
        elif re.search(r"(?m)^read\s*:\s*$", existing):
            rendered = re.sub(r"(?m)^(read\s*:\s*)$", r"\1\n  - AGENTS.md # agentsmith-managed", existing, count=1)
            if not dry_run:
                backup(path); atomic_write(path, rendered)
        else:
            reconcile_text_block(path, f"{TEXT_BEGIN}\nread:\n  - AGENTS.md\n{TEXT_END}", dry_run=dry_run)
    if "continue" in agents:
        block = textwrap.dedent(f"""\
            {TEXT_BEGIN}
            ---
            name: Agentsmith canonical project instructions
            alwaysApply: true
            ---
            Read and follow the repository-root `AGENTS.md`. It is the canonical managed instruction file;
            nearer user instructions retain precedence. Do not maintain a second copy of its contents here.
            {TEXT_END}
            """)
        reconcile_text_block(target / ".continue" / "rules" / "agentsmith.md", block, dry_run=dry_run)
    if "goose" in agents:
        reconcile_text_block(
            target / ".goosehints",
            f"{TEXT_BEGIN}\nRead and follow the repository-root AGENTS.md as this project's canonical instructions.\n{TEXT_END}",
            dry_run=dry_run,
        )


def copy_runtime(target: Path, *, dry_run: bool) -> Path:
    destination = target / ".agentsmith" / "agentsmith.py"
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "agentsmith.py", destination)
        registry_destination = destination.parent / "config" / "agents.json"
        registry_destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REGISTRY_PATH, registry_destination)
        for helper_name in ("native_launcher.py", "evaluate.py"):
            helper_source = ROOT / helper_name
            if helper_source.exists():
                shutil.copy2(helper_source, destination.parent / helper_name)
        posix_launcher = destination.parent / "agentsmith"
        windows_launcher = destination.parent / "agentsmith.cmd"
        atomic_write(posix_launcher, textwrap.dedent("""\
            #!/bin/sh
            set -eu
            DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
            if command -v python3 >/dev/null 2>&1; then exec python3 "$DIR/agentsmith.py" "$@"; fi
            if command -v python >/dev/null 2>&1; then exec python "$DIR/agentsmith.py" "$@"; fi
            echo "Agentsmith requires Python 3.11+ (tried python3 and python)." >&2
            exit 127
            """))
        posix_launcher.chmod(posix_launcher.stat().st_mode | 0o111)
        atomic_write(windows_launcher, textwrap.dedent("""\
            @echo off
            where python3 >nul 2>nul && goto python3
            where python >nul 2>nul && goto python
            where py >nul 2>nul && goto py
            echo Agentsmith requires Python 3.11+ ^(tried python3, python, and py -3^). 1>&2
            exit /b 127
            :python3
            python3 "%~dp0agentsmith.py" %*
            exit /b %errorlevel%
            :python
            python "%~dp0agentsmith.py" %*
            exit /b %errorlevel%
            :py
            py -3 "%~dp0agentsmith.py" %*
            exit /b %errorlevel%
            """))
    return destination


def install_native_config(target: Path, agents: list[str], args: argparse.Namespace) -> None:
    selected_mcp = mcp_source(csv(args.with_mcp))
    prior_safety = getattr(args, "prior_managed_safety", {})
    for agent_id in agents:
        if prior_safety.get(agent_id) == "trusted" and args.safety == "cautious":
            destination = (
                home_dir() / ".claude" / "settings.json"
                if agent_id == "claude"
                else codex_home() / "config.toml"
            )
            if args.dry_run:
                say(
                    f"DRY RUN — would migrate AgentSmith-managed {agent_id} safety "
                    f"from trusted to cautious in {destination}"
                )
            else:
                warn(
                    f"WARNING: migrating AgentSmith-managed {agent_id} safety from trusted to "
                    f"cautious; the existing config will be backed up: {destination}"
                )
    if "claude" in agents and not args.assemble_only:
        def claude_settings(data: dict[str, Any]) -> None:
            permissions = data.setdefault("permissions", {})
            if not isinstance(permissions, dict):
                raise CliError("Refusing to replace non-object Claude permissions configuration")
            permissions["defaultMode"] = "acceptEdits" if args.safety == "cautious" else "bypassPermissions"
        merge_json(home_dir() / ".claude" / "settings.json", claude_settings, dry_run=args.dry_run)
    if "codex" in agents and not args.assemble_only:
        reconcile_codex_toml(codex_home() / "config.toml", args.safety, {}, dry_run=args.dry_run)
    if not args.assemble_only:
        install_default_statuslines(agents, target, args.global_mode, dry_run=args.dry_run)
    if not args.assemble_only and not args.dry_run:
        state = load_state(home_dir())
        native_safety = state.get("native_safety", {})
        if not isinstance(native_safety, dict):
            native_safety = {}
        for agent_id in agents:
            native_safety[agent_id] = args.safety
        record_state(home_dir(), "native_safety", native_safety, dry_run=False)
    if selected_mcp and not args.global_mode:
        if "claude" in agents:
            mcp_path = target / ".mcp.json"
            existing_servers: dict[str, Any] = {}
            if mcp_path.exists():
                try:
                    existing_servers = json.loads(mcp_path.read_text(encoding="utf-8")).get("mcpServers", {})
                except json.JSONDecodeError:
                    pass
            def claude_mcp(data: dict[str, Any]) -> None:
                servers = data.setdefault("mcpServers", {})
                for name, value in selected_mcp.items():
                    servers.setdefault(name, value)
            merge_json(mcp_path, claude_mcp, dry_run=args.dry_run)
            prior_state = load_state(target).get("claude_mcp_added", [])
            added = sorted(set(prior_state) | {name for name in selected_mcp if name not in existing_servers})
            record_state(target, "claude_mcp_added", added, dry_run=args.dry_run)
        if "codex" in agents:
            reconcile_codex_toml(target / ".codex" / "config.toml", None, selected_mcp, dry_run=args.dry_run)


def install_claude_plugin_packs(agents: list[str], requested: str | None, *, dry_run: bool) -> None:
    packs = csv([requested] if requested else [])
    if not packs:
        return
    if "claude" not in agents:
        warn("--with-plugins is Claude-only and was ignored because Claude is not selected")
        return
    known = {
        "dev-workflow": (
            [("marketplace", "shinpr/claude-code-workflows")],
            ["dev-workflows@claude-code-workflows", "dev-workflows-frontend@claude-code-workflows", "feature-dev@claude-plugins-official", "frontend-design@claude-plugins-official", "qodo-skills@claude-plugins-official"],
        ),
        "stack-lsp": (
            [("marketplace", "gopherguides/gopher-ai"), ("marketplace", "Piebald-AI/claude-code-lsps")],
            ["go-dev@gopher-ai", "tailwind@gopher-ai", "gopls@claude-code-lsps", "typescript-lsp@claude-plugins-official", "gopls-lsp@claude-plugins-official"],
        ),
        "security": (
            [("marketplace", "briiirussell/cybersecurity-skills")],
            ["claude-security@claude-plugins-official", "cybersecurity-skills@cybersecurity-skills"],
        ),
    }
    unknown = sorted(set(packs) - set(known))
    if unknown:
        raise CliError(f"Unknown Claude plugin pack(s): {', '.join(unknown)}")
    if dry_run:
        say(f"DRY RUN — would install Claude plugin pack(s): {', '.join(packs)}")
        return
    if not shutil.which("claude"):
        warn("Claude CLI is not on PATH; plugin packs were not installed")
        return
    for pack in packs:
        marketplaces, plugins = known[pack]
        for _, repository in marketplaces:
            result = subprocess.run(["claude", "plugin", "marketplace", "add", repository])
            if result.returncode:
                warn(f"Claude marketplace add reported an issue: {repository}")
        for plugin in plugins:
            result = subprocess.run(["claude", "plugin", "install", plugin])
            if result.returncode:
                warn(f"Claude plugin install reported an issue: {plugin}")


def self_update(args: argparse.Namespace) -> int:
    warn("install --self-update is deprecated and updates only a clean Git checkout; use 'agentsmith update' for installed scopes")
    if not shutil.which("git"):
        raise CliError("Self-update needs git on PATH")
    if subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet"]).returncode or subprocess.run(
        ["git", "-C", str(ROOT), "diff", "--cached", "--quiet"]
    ).returncode:
        raise CliError("Self-update refused: the harness checkout is dirty; commit or stash first")
    branch = subprocess.run(
        ["git", "-C", str(ROOT), "symbolic-ref", "--short", "HEAD"], capture_output=True, text=True
    )
    if branch.returncode:
        raise CliError("Self-update refused: the harness checkout is on a detached HEAD")
    remote = args.update_from or os.environ.get("HARNESS_REMOTE")
    if not remote and (ROOT / ".harness" / "remote").exists():
        remote = (ROOT / ".harness" / "remote").read_text(encoding="utf-8").strip()
    if not remote:
        result = subprocess.run(["git", "-C", str(ROOT), "remote", "get-url", "origin"], capture_output=True, text=True)
        if result.returncode:
            raise CliError("Self-update needs --from, HARNESS_REMOTE, .harness/remote, or an origin remote")
        remote = result.stdout.strip()
    if args.dry_run:
        say(f"DRY RUN — would fast-forward {branch.stdout.strip()} from {remote} and reassemble managed targets")
        return 0
    before = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    fetched = subprocess.run(["git", "-C", str(ROOT), "fetch", remote, branch.stdout.strip()], env=git_env)
    if fetched.returncode:
        raise CliError("Self-update fetch failed; the checkout was not changed")
    merged = subprocess.run(["git", "-C", str(ROOT), "merge", "--ff-only", "FETCH_HEAD"], env=git_env)
    if merged.returncode:
        raise CliError("Self-update refused a non-fast-forward update; resolve the branch manually")
    after = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    if before == after:
        ok(f"harness checkout already current ({after[:9]})")
        return 0
    ok(f"harness checkout fast-forwarded ({before[:9]} -> {after[:9]})")
    if not args.no_reassemble:
        reassemble_managed_targets(args)
    return 0


def stable_release_tags(remote: str, *, timeout_seconds: int = 10) -> list[tuple[tuple[int, int, int], str]]:
    """Return stable semantic-version tags advertised by a Git remote."""
    if not shutil.which("git"):
        raise CliError("Update checks need git on PATH")
    git_env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/usr/bin/false" if os.name != "nt" else "",
    }
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "--refs", "--", remote],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
            env=git_env,
        )
    except subprocess.TimeoutExpired as exc:
        raise CliError(f"Update check timed out after {timeout_seconds} seconds; no installation changes were made") from exc
    except OSError as exc:
        raise CliError(f"Update check could not start git: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "remote unavailable"
        raise CliError(f"Update check failed ({detail}); no installation changes were made")
    releases: list[tuple[tuple[int, int, int], str]] = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        match = re.fullmatch(r"refs/tags/(v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*))", fields[1])
        if match:
            releases.append(((int(match.group(2)), int(match.group(3)), int(match.group(4))), match.group(1)))
    return sorted(set(releases))


def cmd_update_check(args: argparse.Namespace) -> int:
    remote = args.update_from or OFFICIAL_REMOTE
    releases = stable_release_tags(remote)
    if not releases:
        raise CliError(f"No stable semantic-version tags were found at {remote}")
    latest_version, tag = releases[-1]
    current_match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", VERSION)
    if not current_match:
        raise CliError(f"Installed version {VERSION!r} is not a stable semantic version")
    current_version = tuple(int(current_match.group(index)) for index in range(1, 4))
    payload = {
        "current_version": VERSION,
        "latest_version": ".".join(str(part) for part in latest_version),
        "tag": tag,
        "update_available": latest_version > current_version,
        "remote": remote,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif payload["update_available"]:
        say(f"Agentsmith {payload['latest_version']} is available ({tag}); run 'agentsmith update plan' to inspect it")
    else:
        ok(f"Agentsmith {VERSION} is the latest stable release")
    return 0


def resolve_stable_release(remote: str, requested_tag: str | None) -> dict[str, str]:
    releases = stable_release_tags(remote)
    if not releases:
        raise CliError(f"No stable semantic-version tags were found at {remote}")
    release_by_tag = {tag: version for version, tag in releases}
    tag = requested_tag or releases[-1][1]
    if tag not in release_by_tag:
        raise CliError(f"Release {tag!r} is not an advertised stable semantic-version tag at {remote}")
    version_tuple = release_by_tag[tag]
    version = ".".join(str(part) for part in version_tuple)
    git_env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/usr/bin/false" if os.name != "nt" else "",
    }
    with tempfile.TemporaryDirectory(prefix="agentsmith-release-") as temporary:
        checkout = Path(temporary) / "checkout"
        try:
            cloned = subprocess.run(
                ["git", "clone", "--quiet", "--no-checkout", "--single-branch", "--branch", tag, "--", remote, str(checkout)],
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
                env=git_env,
            )
        except subprocess.TimeoutExpired as exc:
            raise CliError("Release checkout timed out; no installation changes were made") from exc
        if cloned.returncode:
            detail = cloned.stderr.strip().splitlines()[-1] if cloned.stderr.strip() else "clone failed"
            raise CliError(f"Could not stage release {tag} ({detail}); no installation changes were made")
        commit_result = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", f"refs/tags/{tag}^{{commit}}"],
            text=True,
            capture_output=True,
            check=False,
            env=git_env,
        )
        commit = commit_result.stdout.strip()
        if commit_result.returncode or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
            raise CliError(f"Release tag {tag} does not resolve to a valid Git commit")
        tree = subprocess.run(
            ["git", "-C", str(checkout), "ls-tree", "-r", commit],
            text=True,
            capture_output=True,
            check=False,
            env=git_env,
        )
        unsafe_entry = next(
            (line for line in tree.stdout.splitlines() if line.startswith(("120000 ", "160000 "))),
            None,
        )
        if tree.returncode or unsafe_entry:
            raise CliError(f"Release {tag} contains an unsupported symbolic link or submodule")
        checked_out = subprocess.run(
            ["git", "-C", str(checkout), "checkout", "--quiet", "--detach", commit],
            text=True,
            capture_output=True,
            check=False,
            env=git_env,
        )
        if checked_out.returncode:
            raise CliError(f"Release commit {commit[:12]} could not be checked out")
        for candidate in checkout.rglob("*"):
            if candidate.is_symlink():
                raise CliError(f"Release {tag} contains a symbolic link, which staged updates do not accept: {candidate.relative_to(checkout)}")
        runtime = checkout / "agentsmith.py"
        try:
            runtime_text = runtime.read_text(encoding="utf-8")
        except OSError as exc:
            raise CliError(f"Release {tag} has no readable agentsmith.py runtime") from exc
        declared = re.search(r'^VERSION = "([^"]+)"$', runtime_text, re.MULTILINE)
        if not declared or declared.group(1) != version:
            actual = declared.group(1) if declared else "missing"
            raise CliError(f"Release {tag} declares version {actual!r}, expected {version!r}")
    return {"tag": tag, "version": version, "commit": commit}


def checkout_planned_release(remote: str, release: dict[str, str], destination: Path) -> Path:
    resolved = resolve_stable_release(remote, release["tag"])
    if resolved != release:
        raise CliError("The selected release tag moved or changed after planning; create a new plan")
    git_env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/usr/bin/false" if os.name != "nt" else "",
    }
    result = subprocess.run(
        [
            "git", "clone", "--quiet", "--no-checkout", "--single-branch", "--branch", release["tag"],
            "--", remote, str(destination),
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
        env=git_env,
    )
    if result.returncode:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "clone failed"
        raise CliError(f"Could not restage release {release['tag']} ({detail})")
    checked_out = subprocess.run(
        ["git", "-C", str(destination), "checkout", "--quiet", "--detach", release["commit"]],
        text=True,
        capture_output=True,
        check=False,
        env=git_env,
    )
    if checked_out.returncode:
        raise CliError(f"Could not check out planned commit {release['commit'][:12]}")
    return destination


def validate_installation_manifest(state: dict[str, Any]) -> dict[str, Any]:
    allowed_state = {
        "schema_version", "installation", "gemini_context_added", "native_statuslines",
        "native_safety", "claude_mcp_added", "skills_installed", "update_policy",
    }
    unknown_state = sorted(set(state) - allowed_state)
    if unknown_state:
        raise CliError(f"Installation state has unknown field(s): {', '.join(unknown_state)}")
    if state.get("schema_version") != 1:
        raise CliError("Installation state has no supported schema; rerun install with explicit choices before planning an update")
    installation = state.get("installation")
    if not isinstance(installation, dict):
        raise CliError("Installation state has no manifest; rerun install with explicit choices before planning an update")
    allowed_installation = {
        "installed_version", "source", "scope", "agents", "profiles", "include_core",
        "safety", "operator", "tracker", "capabilities", "managed_files",
    }
    unknown_installation = sorted(set(installation) - allowed_installation)
    if unknown_installation:
        raise CliError(f"Installation manifest has unknown field(s): {', '.join(unknown_installation)}")
    required = allowed_installation
    missing = sorted(required - set(installation))
    if missing:
        raise CliError(f"Installation manifest is missing field(s): {', '.join(missing)}")
    return installation


def reconstruct_pre_manifest_installation(target: Path, scope: str, state: dict[str, Any]) -> dict[str, Any]:
    instruction_candidates = (
        [home_dir() / ".claude" / "CLAUDE.md", codex_home() / "AGENTS.md"]
        if scope == "global"
        else [target / "AGENTS.md", target / "CLAUDE.md"]
    )
    managed_instructions = [
        path for path in instruction_candidates
        if path.is_file() and managed_markers(path.read_text(encoding="utf-8", errors="replace"))
    ]
    if not managed_instructions:
        raise CliError("Pre-manifest install has no managed instruction markers; rerun install with explicit choices")
    metadata_values: set[tuple[tuple[str, ...], bool]] = set()
    for path in managed_instructions:
        text = path.read_text(encoding="utf-8", errors="replace")
        metadata = re.search(r"Generated\. Profiles: ([^.]+)\. core=(true|false)\.", text)
        if not metadata:
            raise CliError(f"Cannot infer profiles and core choice from {path}; rerun install explicitly")
        profiles = () if metadata.group(1) == "none" else tuple(metadata.group(1).split(","))
        metadata_values.add((profiles, metadata.group(2) == "true"))
    if len(metadata_values) != 1:
        raise CliError("Managed instruction copies disagree about profiles or core choice; rerun install explicitly")
    profiles, include_core = next(iter(metadata_values))
    home_state = load_state(home_dir().resolve())
    native_safety = home_state.get("native_safety", {})
    native_safety = native_safety if isinstance(native_safety, dict) else {}
    agents: list[str] = []
    if scope == "global":
        if (home_dir() / ".claude" / "CLAUDE.md") in managed_instructions:
            agents.append("claude")
        if (codex_home() / "AGENTS.md") in managed_instructions:
            agents.append("codex")
    else:
        claude_copy = target / "CLAUDE.md"
        if claude_copy in managed_instructions:
            agents.append("claude")
        native_candidates = {key for key in native_safety if key in {"claude", "codex"}}
        if native_candidates == {"codex"}:
            agents.append("codex")
        elif native_candidates - set(agents):
            raise CliError("Pre-manifest native agent ownership is ambiguous; rerun install with explicit --agent choices")
        adapters = {
            "gemini-cli": target / ".gemini" / "settings.json",
            "aider": target / ".aider.conf.yml",
            "continue": target / ".continue" / "rules" / "agentsmith.md",
            "goose": target / ".goosehints",
        }
        for agent_id, path in adapters.items():
            if path.is_file():
                agents.append(agent_id)
    agents = list(dict.fromkeys(agents))
    if not agents:
        raise CliError("Pre-manifest agent selection cannot be inferred; rerun install with explicit --agent choices")
    safety: dict[str, str] = {}
    for agent_id in agents:
        if agent_id not in {"claude", "codex"}:
            continue
        value = native_safety.get(agent_id)
        if value not in {"cautious", "trusted"}:
            raise CliError(f"Pre-manifest safety for {agent_id} cannot be inferred; rerun install with explicit --safety")
        safety[agent_id] = value
    recovery = recover_identity(managed_instructions)
    runtime = target / ".agentsmith" / "agentsmith.py" if scope == "project" else Path(__file__).resolve()
    installed_version = VERSION
    if runtime.is_file():
        declared = re.search(r'^VERSION = "([^"]+)"$', runtime.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
        if declared:
            installed_version = declared.group(1)
    config_texts = []
    for path in (home_dir() / ".claude" / "settings.json", codex_home() / "config.toml"):
        if path.is_file():
            config_texts.append(path.read_text(encoding="utf-8", errors="replace"))
    combined_config = "\n".join(config_texts)
    mcp_names = sorted(set(re.findall(r"(?m)^\[mcp_servers\.([A-Za-z0-9_-]+)\]\s*$", combined_config)))
    skill_root = home_dir() if scope == "global" else target
    skills = (skill_root / ".agents" / "skills").is_dir()
    return {
        "installed_version": installed_version,
        "source": {"release": None, "commit": None},
        "scope": scope,
        "agents": agents,
        "profiles": list(profiles),
        "include_core": include_core,
        "safety": safety,
        "operator": {
            "name": recovery.get("operator_name", "the project lead"),
            "role": recovery.get("operator_role", "owner / decision-maker"),
            "bio": recovery.get("operator_bio", (
                "They decide direction and accept the risk; you are the technical co-pilot — proactive, "
                "evidence-driven, and honest about trade-offs."
            )),
        },
        "tracker": {
            "name": recovery.get("tracker", "your project's tracker (or a KNOWN-ISSUES.md at the repo root)"),
            "writes": recovery.get("tracker_writes", "ask"),
        },
        "capabilities": {
            "handoff_hooks": "handoff-on-keyword" in combined_config,
            "hooks": False,
            "mcp": mcp_names,
            "skills": skills,
            "ui_design_hook": "ui-design-reminder" in combined_config,
        },
        "managed_files": [],
    }


def fingerprint_entry(root_name: str, root: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    return {
        "root": root_name,
        "path": relative,
        "sha256": file_sha256(path) if path.is_file() else None,
        "mode": path.stat().st_mode & 0o777 if path.is_file() else None,
    }


def safe_update_path(root: Path, relative: str | Path) -> Path:
    """Return a contained updater path after rejecting every symbolic-link component."""
    root = root.resolve()
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts or not relative_path.parts:
        raise CliError(f"Update path escapes its declared root: {relative}")
    candidate = root.joinpath(relative_path)
    current = root
    for part in relative_path.parts:
        current = current / part
        if current.is_symlink():
            raise CliError(f"Update refused to follow symbolic link {current}")
    try:
        candidate.resolve(strict=False).relative_to(root)
    except (OSError, ValueError) as exc:
        raise CliError(f"Update path escapes its declared root: {candidate}") from exc
    return candidate


def installation_fingerprints(target: Path, installation: dict[str, Any]) -> tuple[dict[str, str], list[dict[str, Any]]]:
    roots = {
        "target": target,
        "home": home_dir().resolve(),
        "codex_home": codex_home().resolve(),
    }
    candidates: set[tuple[str, Path]] = set()

    def add(root_name: str, relative: str) -> None:
        root = roots[root_name]
        path = safe_update_path(root, relative)
        if path.is_dir():
            for child in path.rglob("*"):
                checked = safe_update_path(root, child.relative_to(root))
                if checked.is_file():
                    candidates.add((root_name, checked))
        else:
            candidates.add((root_name, path))

    if installation["scope"] == "project":
        for relative in (
            "AGENTS.md", "CLAUDE.md", *RUNTIME_FILES, ".agentsmith/autonomous-run.py", ".agentsmith/state.json",
            ".harness/templates", ".harness/verify.conf",
        ):
            add("target", relative)
        adapters = {
            "gemini-cli": ".gemini/settings.json",
            "aider": ".aider.conf.yml",
            "continue": ".continue/rules/agentsmith.md",
            "goose": ".goosehints",
        }
        for agent_id in installation["agents"]:
            if agent_id in adapters:
                add("target", adapters[agent_id])
        if installation["capabilities"].get("skills"):
            add("target", ".agents/skills")
            if "claude" in installation["agents"]:
                add("target", ".claude/skills")
    else:
        if "claude" in installation["agents"]:
            add("home", ".claude/CLAUDE.md")
        if "codex" in installation["agents"]:
            add("codex_home", "AGENTS.md")
        if installation["capabilities"].get("skills"):
            add("home", ".agents/skills")
            if "claude" in installation["agents"]:
                add("home", ".claude/skills")
        if installation["capabilities"].get("handoff_hooks") or installation["capabilities"].get("ui_design_hook"):
            for relative in RUNTIME_FILES:
                add("home", relative)
    add("home", ".agentsmith/state.json")
    home_state = load_update_state(roots["home"])
    native_statuslines = home_state.get("native_statuslines", {})
    claude_statusline = native_statuslines.get("claude", {}) if isinstance(native_statuslines, dict) else {}
    statusline_files = claude_statusline.get("files", {}) if isinstance(claude_statusline, dict) else {}
    if isinstance(statusline_files, dict):
        for raw_path in statusline_files:
            if not isinstance(raw_path, str):
                continue
            try:
                relative = Path(raw_path).relative_to(roots["home"]).as_posix()
            except ValueError:
                continue
            if re.fullmatch(r"\.claude/agentsmith-statusline(?:-\d+)?\.(?:py|ps1)", relative):
                add("home", relative)
    if "claude" in installation["agents"]:
        add("home", ".claude/settings.json")
    if "codex" in installation["agents"]:
        add("codex_home", "config.toml")
        add("codex_home", "hooks.json")
    entries = [fingerprint_entry(root_name, roots[root_name], path) for root_name, path in candidates]
    entries.sort(key=lambda item: (item["root"], item["path"]))
    return {name: str(path) for name, path in roots.items()}, entries


def update_integrity_key(*, create: bool) -> bytes:
    key_path = safe_update_path(home_dir().resolve(), ".agentsmith/update-integrity.key")
    if key_path.exists():
        if not key_path.is_file():
            raise CliError(f"Update integrity key is not a regular file: {key_path}")
        try:
            key = key_path.read_bytes()
        except OSError as exc:
            raise CliError(f"Cannot read update integrity key {key_path}: {exc}") from exc
        if len(key) != 32:
            raise CliError(f"Update integrity key has an invalid length: {key_path}")
        return key
    if not create:
        raise CliError(f"Update integrity key is missing: {key_path}; create a new plan on this machine")
    key = secrets.token_bytes(32)
    atomic_write_bytes(key_path, key, 0o600)
    try:
        key_path.chmod(0o600)
    except OSError as exc:
        raise CliError(f"Cannot secure update integrity key {key_path}: {exc}") from exc
    return key


def plan_integrity(payload: dict[str, Any], key: bytes) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "hmac-sha256:" + hmac.new(key, canonical, hashlib.sha256).hexdigest()


def cmd_update_plan(args: argparse.Namespace) -> int:
    if args.global_mode == bool(args.target):
        raise CliError("Update planning requires exactly one of --global or --target PATH")
    target = home_dir().resolve() if args.global_mode else Path(args.target).expanduser().resolve()
    safe_update_path(target, ".agentsmith/state.json")
    state = load_update_state(target)
    expected_scope = "global" if args.global_mode else "project"
    migration_warnings: list[str] = []
    if state.get("schema_version") == 1 and isinstance(state.get("installation"), dict):
        installation = validate_installation_manifest(state)
    else:
        installation = reconstruct_pre_manifest_installation(target, expected_scope, state)
        migration_warnings.append(
            "Pre-manifest installation choices were reconstructed from managed markers and ownership state; "
            "apply will persist schema version 1."
        )
    if installation["scope"] != expected_scope:
        raise CliError(f"Installation manifest scope is {installation['scope']!r}, not {expected_scope!r}")
    remote = args.update_from or OFFICIAL_REMOTE
    release = resolve_stable_release(remote, args.version)
    roots, fingerprints = installation_fingerprints(target, installation)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": expected_scope,
        "target": str(target),
        "roots": roots,
        "remote": remote,
        "release": release,
        "installation": installation,
        "fingerprints": fingerprints,
        "proposed_changes": [],
        "preserved_foreign_content": [
            "Content outside AgentSmith-managed markers and owned configuration remains in place.",
            "Modified helpers, research, source material, and unowned configuration are not deletion targets.",
        ],
        "migration_warnings": migration_warnings,
        "verification": [
            "repeat the staged release installer with the recorded manifest choices",
            "require the exact create/replace paths, hashes, and modes recorded in proposed_changes",
            "run agentsmith doctor --strict for the selected install",
            "compare post-update state and write a rollback receipt",
        ],
    }
    with tempfile.TemporaryDirectory(prefix="agentsmith-plan-") as temporary:
        _, proposed = stage_planned_update(payload, Path(temporary), execute_candidate=False)
        payload["proposed_changes"] = proposed_change_manifest(payload, proposed)
    payload["integrity"] = plan_integrity(payload, update_integrity_key(create=True))
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.save:
        destination = Path(args.save).expanduser().resolve()
        atomic_write(destination, rendered)
        ok(f"saved read-only installation plan for {release['tag']} to {destination}")
    else:
        print(rendered, end="")
    return 0


def load_update_document(path: Path, kind: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(f"Cannot read {kind} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CliError(f"{kind.capitalize()} must be a JSON object")
    integrity = payload.get("integrity")
    unsigned = {key: value for key, value in payload.items() if key != "integrity"}
    expected_integrity = plan_integrity(unsigned, update_integrity_key(create=False))
    if not isinstance(integrity, str) or not hmac.compare_digest(integrity, expected_integrity):
        raise CliError(f"{kind.capitalize()} integrity check failed; do not apply an edited or partial file")
    return payload


def validated_plan(path: Path) -> dict[str, Any]:
    plan = load_update_document(path, "plan")
    allowed = {
        "schema_version", "created_at", "scope", "target", "roots", "remote", "release",
        "installation", "fingerprints", "proposed_changes", "preserved_foreign_content",
        "migration_warnings", "verification", "integrity",
    }
    unknown = sorted(set(plan) - allowed)
    missing = sorted(allowed - set(plan))
    if unknown or missing:
        detail = f"unknown: {', '.join(unknown)}" if unknown else f"missing: {', '.join(missing)}"
        raise CliError(f"Plan fields are not supported ({detail})")
    if plan["schema_version"] != 1 or plan["scope"] not in {"project", "global"}:
        raise CliError("Plan schema or scope is not supported")
    if not isinstance(plan["target"], str) or not isinstance(plan["remote"], str) or not plan["remote"]:
        raise CliError("Plan target and remote must be non-empty strings")
    expected_target = home_dir().resolve() if plan["scope"] == "global" else Path(plan["target"]).resolve()
    expected_roots = {
        "target": str(expected_target),
        "home": str(home_dir().resolve()),
        "codex_home": str(codex_home().resolve()),
    }
    if plan["roots"] != expected_roots or Path(plan["target"]).resolve() != expected_target:
        raise CliError("Plan roots do not match the current target, HOME, and CODEX_HOME")
    release = plan["release"]
    if not isinstance(release, dict) or set(release) != {"tag", "version", "commit"}:
        raise CliError("Plan release identity is malformed")
    if not re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", release.get("tag", "")):
        raise CliError("Plan release tag is not a stable semantic version")
    if release["tag"] != f"v{release.get('version')}" or not re.fullmatch(r"[0-9a-f]{40,64}", release.get("commit", "")):
        raise CliError("Plan release version or commit is malformed")
    installation = validate_installation_manifest({"schema_version": 1, "installation": plan["installation"]})
    if installation["scope"] != plan["scope"]:
        raise CliError("Plan scope and installation manifest disagree")
    if not isinstance(plan["fingerprints"], list):
        raise CliError("Plan fingerprints must be a list")
    for item in plan["fingerprints"]:
        if not isinstance(item, dict) or set(item) != {"root", "path", "sha256", "mode"}:
            raise CliError("Plan contains a malformed fingerprint")
        if item["root"] not in expected_roots or not isinstance(item["path"], str):
            raise CliError("Plan fingerprint has an unknown root or path")
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise CliError("Plan fingerprint path escapes its declared root")
        safe_update_path(Path(expected_roots[item["root"]]), relative)
        if item["sha256"] is not None and not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise CliError("Plan fingerprint hash is malformed")
        if item["mode"] is not None and (not isinstance(item["mode"], int) or not 0 <= item["mode"] <= 0o777):
            raise CliError("Plan fingerprint mode is malformed")
    if not isinstance(plan["proposed_changes"], list):
        raise CliError("Plan proposed changes must be a list")
    proposed_paths: set[tuple[str, str]] = set()
    for item in plan["proposed_changes"]:
        if not isinstance(item, dict) or set(item) != {
            "root", "path", "operation", "before_sha256", "before_mode", "after_sha256", "after_mode"
        }:
            raise CliError("Plan contains a malformed proposed change")
        if item["root"] not in expected_roots or item["operation"] not in {"create", "replace"}:
            raise CliError("Plan proposed change has an unknown root or operation")
        if not isinstance(item["path"], str) or not allowed_update_path(item["root"], item["path"], installation):
            raise CliError("Plan proposed change is outside managed update surfaces")
        safe_update_path(Path(expected_roots[item["root"]]), item["path"])
        for name in ("before_sha256", "after_sha256"):
            if item[name] is not None and not re.fullmatch(r"[0-9a-f]{64}", item[name]):
                raise CliError("Plan proposed change hash is malformed")
        for name in ("before_mode", "after_mode"):
            if item[name] is not None and (not isinstance(item[name], int) or not 0 <= item[name] <= 0o777):
                raise CliError("Plan proposed change mode is malformed")
        if item["after_sha256"] is None or item["after_mode"] is None:
            raise CliError("Plan proposed change has no staged result")
        if item["operation"] == "create" and (item["before_sha256"] is not None or item["before_mode"] is not None):
            raise CliError("Plan create operation has an existing-file baseline")
        if item["operation"] == "replace" and (item["before_sha256"] is None or item["before_mode"] is None):
            raise CliError("Plan replace operation has no existing-file baseline")
        identity = (item["root"], item["path"])
        if identity in proposed_paths:
            raise CliError("Plan contains a duplicate proposed change")
        proposed_paths.add(identity)
    return plan


def recheck_plan_fingerprints(plan: dict[str, Any]) -> None:
    for item in plan["fingerprints"]:
        path = safe_update_path(Path(plan["roots"][item["root"]]), item["path"])
        actual = file_sha256(path) if path.is_file() else None
        actual_mode = path.stat().st_mode & 0o777 if path.is_file() else None
        if actual != item["sha256"] or actual_mode != item["mode"]:
            raise CliError(f"Update refused: {item['root']}:{item['path']} changed after planning")


def copy_plan_inputs_to_shadow(plan: dict[str, Any], shadow_roots: dict[str, Path]) -> None:
    for item in plan["fingerprints"]:
        if item["sha256"] is None:
            continue
        source = safe_update_path(Path(plan["roots"][item["root"]]), item["path"])
        destination = safe_update_path(shadow_roots[item["root"]], item["path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def prepare_owned_skills(plan: dict[str, Any], shadow_roots: dict[str, Path]) -> set[tuple[str, str]]:
    inventory = plan["installation"].get("managed_files", [])
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for item in inventory:
        if not isinstance(item, dict) or set(item) != {"root", "path", "sha256"}:
            raise CliError("Installation managed-file inventory is malformed")
        parts = Path(item["path"]).parts
        if len(parts) < 4 or (parts[0], parts[1]) not in {(".agents", "skills"), (".claude", "skills")}:
            continue
        prefix = Path(*parts[:3]).as_posix()
        grouped.setdefault((item["root"], prefix), []).append(item)
    preserved: set[tuple[str, str]] = set()
    for (root_name, prefix), items in grouped.items():
        source_root = Path(plan["roots"][root_name])
        actual_root = safe_update_path(source_root, prefix)
        recorded = {item["path"]: item["sha256"] for item in items}
        current: dict[str, str] = {}
        if actual_root.is_dir():
            for path in actual_root.rglob("*"):
                relative = path.relative_to(source_root)
                checked = safe_update_path(source_root, relative)
                if checked.is_file():
                    current[relative.as_posix()] = file_sha256(checked)
        shadow_skill = safe_update_path(shadow_roots[root_name], prefix)
        if current == recorded:
            if shadow_skill.exists():
                shutil.rmtree(shadow_skill)
        else:
            preserved.add((root_name, prefix))
    return preserved


def retain_customized_skill_baselines(
    plan: dict[str, Any], shadow_roots: dict[str, Path], preserved: set[tuple[str, str]]
) -> None:
    if not preserved:
        return
    state_root = shadow_roots["home"] if plan["scope"] == "global" else shadow_roots["target"]
    state = load_state(state_root)
    installation = state.get("installation")
    if not isinstance(installation, dict):
        raise CliError("Staged installer did not write an installation manifest")
    new_inventory = installation.get("managed_files", [])
    kept_new = [
        item for item in new_inventory
        if not any(item.get("root") == root_name and item.get("path", "").startswith(prefix + "/") for root_name, prefix in preserved)
    ]
    prior = plan["installation"].get("managed_files", [])
    kept_prior = [
        item for item in prior
        if any(item.get("root") == root_name and item.get("path", "").startswith(prefix + "/") for root_name, prefix in preserved)
    ]
    installation["managed_files"] = [*kept_new, *kept_prior]
    atomic_write(state_path(state_root), json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def install_arguments_from_manifest(plan: dict[str, Any], shadow_target: Path) -> list[str]:
    installation = plan["installation"]
    arguments = ["install", "--agent", ",".join(installation["agents"])]
    if plan["scope"] == "global":
        arguments.append("--global")
    else:
        arguments += ["--target", str(shadow_target)]
    for profile in installation["profiles"]:
        arguments += ["--profile", profile]
    if not installation["include_core"]:
        arguments.append("--profile-only")
    safety_values = set(installation["safety"].values())
    if len(safety_values) > 1:
        raise CliError("Update cannot reproduce mixed native safety settings; reinstall each scope explicitly")
    if safety_values:
        arguments += ["--safety", next(iter(safety_values))]
    operator = installation["operator"]
    arguments += ["--operator-name", operator["name"], "--operator-role", operator["role"], "--operator-bio", operator["bio"]]
    tracker = installation["tracker"]
    arguments += ["--tracker", tracker["name"], "--tracker-writes", tracker["writes"]]
    capabilities = installation["capabilities"]
    if capabilities.get("skills"):
        arguments.append("--with-skills")
    for name in capabilities.get("mcp", []):
        arguments += ["--with-mcp", name]
    if capabilities.get("handoff_hooks"):
        arguments.append("--with-handoff-hooks")
    if capabilities.get("ui_design_hook"):
        arguments.append("--with-ui-design-hook")
    if capabilities.get("hooks"):
        arguments.append("--with-hooks")
    return arguments


def shadow_files(root: Path) -> dict[str, tuple[bytes, int]]:
    result: dict[str, tuple[bytes, int]] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        checked = safe_update_path(root, relative)
        if (
            checked.is_file()
            and ".git" not in relative.parts
            and not re.search(r"\.bak\.\d{8}-\d{6}(?:\.\d+)?$", checked.name)
        ):
            result[relative.as_posix()] = (checked.read_bytes(), checked.stat().st_mode & 0o777)
    return result


def translate_shadow_paths(
    content: bytes, shadow_roots: dict[str, Path], actual_roots: dict[str, str]
) -> bytes:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content
    replacements: set[tuple[str, str]] = set()
    for root_name, shadow_root in shadow_roots.items():
        actual = actual_roots[root_name]
        for old, new in ((str(shadow_root), actual), (shadow_root.as_posix(), Path(actual).as_posix())):
            replacements.add((old, new))
            replacements.add((json.dumps(old, ensure_ascii=False)[1:-1], json.dumps(new, ensure_ascii=False)[1:-1]))
    for old, new in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        text = text.replace(old, new)
    return text.encode("utf-8")


def allowed_update_path(root_name: str, relative: str, installation: dict[str, Any]) -> bool:
    path = Path(relative)
    if ".." in path.parts or path.is_absolute():
        return False
    if root_name == "target":
        exact = {
            "AGENTS.md", "CLAUDE.md", ".harness/verify.conf", ".aider.conf.yml", ".goosehints",
            ".gemini/settings.json", ".continue/rules/agentsmith.md",
            *RUNTIME_FILES, ".agentsmith/autonomous-run.py", ".agentsmith/state.json",
        }
        prefixes = (".harness/templates/", ".agents/skills/", ".claude/skills/")
        return relative in exact or relative.startswith(prefixes)
    if root_name == "home":
        return (
            relative in {".agentsmith/state.json", *RUNTIME_FILES}
            or relative in {".claude/CLAUDE.md", ".claude/settings.json"}
            or bool(re.fullmatch(r"\.claude/agentsmith-statusline(?:-\d+)?\.(?:py|ps1)", relative))
            or relative.startswith((".agents/skills/", ".claude/skills/"))
        )
    if root_name == "codex_home":
        return relative in {"AGENTS.md", "config.toml", "hooks.json"}
    return False


def trusted_stage_install(
    checkout: Path,
    release_version: str,
    arguments: list[str],
    shadow_env: dict[str, str],
) -> None:
    """Run today's trusted installer logic against data files from a candidate release."""
    global ROOT, REGISTRY_PATH, VERSION
    prior_root, prior_registry, prior_version = ROOT, REGISTRY_PATH, VERSION
    prior_environment = {name: os.environ.get(name) for name in shadow_env}
    output, errors = io.StringIO(), io.StringIO()
    try:
        ROOT = checkout
        REGISTRY_PATH = checkout / "config" / "agents.json"
        VERSION = release_version
        os.environ.update(shadow_env)
        parsed = parser().parse_args(arguments)
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = cmd_install(parsed)
        if result:
            raise CliError(f"Trusted staged installer returned {result}")
    except Exception as exc:
        detail = (output.getvalue() + errors.getvalue()).strip()[-1000:]
        suffix = f"\n{detail}" if detail else ""
        raise CliError(f"Trusted planning install failed before real files changed: {exc}{suffix}") from exc
    finally:
        ROOT, REGISTRY_PATH, VERSION = prior_root, prior_registry, prior_version
        for name, value in prior_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def stage_planned_update(
    plan: dict[str, Any], temporary_root: Path, *, execute_candidate: bool
) -> tuple[Path, list[tuple[str, str, bytes, int]]]:
    checkout = checkout_planned_release(plan["remote"], plan["release"], temporary_root / "release")
    shadow_roots = {
        "target": temporary_root / "target",
        "home": temporary_root / "home",
        "codex_home": temporary_root / "codex-home",
    }
    for root in shadow_roots.values():
        root.mkdir(parents=True, exist_ok=True)
    copy_plan_inputs_to_shadow(plan, shadow_roots)
    preserved_skills = prepare_owned_skills(plan, shadow_roots)
    shadow_env = {
        "HOME": str(shadow_roots["home"]),
        "USERPROFILE": str(shadow_roots["home"]),
        "CODEX_HOME": str(shadow_roots["codex_home"]),
        "GIT_TERMINAL_PROMPT": "0",
    }
    install_arguments = install_arguments_from_manifest(plan, shadow_roots["target"])
    if execute_candidate:
        candidate_env = {
            name: os.environ[name]
            for name in (
                "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "TMPDIR",
                "LANG", "LC_ALL", "PYTHONIOENCODING",
            )
            if name in os.environ
        }
        install = subprocess.run(
            [sys.executable, str(checkout / "agentsmith.py"), *install_arguments],
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
            env={**candidate_env, **shadow_env},
        )
        if install.returncode:
            detail = (install.stdout + install.stderr).strip()[-1000:]
            raise CliError(f"Staged release install failed before real files changed:\n{detail}")
    else:
        trusted_stage_install(checkout, plan["release"]["version"], install_arguments, shadow_env)
    retain_customized_skill_baselines(plan, shadow_roots, preserved_skills)
    proposed: list[tuple[str, str, bytes, int]] = []
    for root_name, shadow_root in shadow_roots.items():
        for relative, (content, mode) in shadow_files(shadow_root).items():
            if not allowed_update_path(root_name, relative, plan["installation"]):
                raise CliError(f"Release attempted an update outside the managed surface: {root_name}:{relative}")
            content = translate_shadow_paths(content, shadow_roots, plan["roots"])
            actual = safe_update_path(Path(plan["roots"][root_name]), relative)
            if actual.exists() and not actual.is_file():
                raise CliError(f"Update refused to replace non-file path {actual}")
            current = actual.read_bytes() if actual.is_file() else None
            current_mode = actual.stat().st_mode & 0o777 if actual.is_file() else None
            if current != content or current_mode != mode:
                proposed.append((root_name, relative, content, mode))
    proposed.sort(key=lambda item: (item[0], item[1]))
    return checkout, proposed


def proposed_change_manifest(
    plan: dict[str, Any], proposed: list[tuple[str, str, bytes, int]]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for root_name, relative, content, mode in proposed:
        actual = safe_update_path(Path(plan["roots"][root_name]), relative)
        existed = actual.is_file()
        before = actual.read_bytes() if existed else None
        result.append({
            "root": root_name,
            "path": relative,
            "operation": "replace" if existed else "create",
            "before_sha256": hashlib.sha256(before).hexdigest() if before is not None else None,
            "before_mode": actual.stat().st_mode & 0o777 if existed else None,
            "after_sha256": hashlib.sha256(content).hexdigest(),
            "after_mode": mode,
        })
    return result


def validate_post_update_health(plan: dict[str, Any]) -> None:
    installation = plan["installation"]
    state_root = Path(plan["roots"]["home"] if plan["scope"] == "global" else plan["roots"]["target"])
    installed = validate_installation_manifest(load_update_state(state_root))
    for field in ("scope", "agents", "profiles", "include_core", "safety", "operator", "tracker", "capabilities"):
        if installed.get(field) != installation.get(field):
            raise CliError(f"Post-update health check failed: installation manifest changed {field}")
    if installed.get("installed_version") != plan["release"]["version"]:
        raise CliError("Post-update health check failed: installed runtime version does not match the release")
    if installed.get("source") != {
        "release": plan["release"]["tag"],
        "commit": plan["release"]["commit"],
    }:
        raise CliError("Post-update health check failed: installed source identity does not match the release")

    for item in plan["proposed_changes"]:
        path = safe_update_path(Path(plan["roots"][item["root"]]), item["path"])
        actual_hash = file_sha256(path) if path.is_file() else None
        actual_mode = path.stat().st_mode & 0o777 if path.is_file() else None
        if actual_hash != item["after_sha256"] or actual_mode != item["after_mode"]:
            raise CliError(f"Post-update health check failed: {item['root']}:{item['path']} does not match the plan")

    target = Path(plan["roots"]["target"])
    instruction_paths: list[Path] = []
    if plan["scope"] == "global":
        if "claude" in installation["agents"]:
            instruction_paths.append(Path(plan["roots"]["home"]) / ".claude" / "CLAUDE.md")
        if "codex" in installation["agents"]:
            instruction_paths.append(Path(plan["roots"]["codex_home"]) / "AGENTS.md")
    else:
        instruction_paths.append(target / "AGENTS.md")
        if "claude" in installation["agents"]:
            instruction_paths.append(target / "CLAUDE.md")
    for path in instruction_paths:
        if not path.is_file() or not managed_markers(path.read_text(encoding="utf-8", errors="replace")):
            raise CliError(f"Post-update health check failed: managed instructions are missing or malformed in {path}")

    capabilities = installation["capabilities"]
    runtime_root = Path(plan["roots"]["home"]) if plan["scope"] == "global" else target
    needs_runtime = plan["scope"] == "project" or capabilities.get("handoff_hooks") or capabilities.get("ui_design_hook")
    runtime = runtime_root / ".agentsmith" / "agentsmith.py"
    if needs_runtime:
        for relative in RUNTIME_FILES:
            if not safe_update_path(runtime_root, relative).is_file():
                raise CliError(f"Post-update health check failed: managed runtime file is missing: {relative}")
        declared = re.search(
            r'^VERSION = "([^"]+)"$', runtime.read_text(encoding="utf-8", errors="replace"), re.MULTILINE
        )
        if not declared or declared.group(1) != plan["release"]["version"]:
            raise CliError("Post-update health check failed: managed runtime did not reach the planned version")

    if capabilities.get("skills"):
        skill_root = Path(plan["roots"]["home"]) if plan["scope"] == "global" else target
        required_roots = [skill_root / ".agents" / "skills"]
        if "claude" in installation["agents"]:
            required_roots.append(skill_root / ".claude" / "skills")
        if any(not root.is_dir() or not any(root.rglob("SKILL.md")) for root in required_roots):
            raise CliError("Post-update health check failed: a managed skill root is missing or empty")
        inventory = installed.get("managed_files", [])
        if not inventory or any(
            not safe_update_path(Path(plan["roots"][item["root"]]), item["path"]).is_file()
            for item in inventory
        ):
            raise CliError("Post-update health check failed: managed skill inventory is missing a file")

    requested_mcp = set(capabilities.get("mcp", []))
    if requested_mcp and plan["scope"] == "global":
        raise CliError("Post-update health check failed: global MCP ownership is not supported")
    if requested_mcp:
        rows = {row["id"]: row for row in compatibility_rows(installation["agents"])}
        for agent_id in installation["agents"]:
            if agent_id not in {"claude", "codex"}:
                continue
            mcp = inspect_mcp(agent_id, rows[agent_id], target)
            if not requested_mcp.issubset(set(mcp["managed_names"])):
                raise CliError(f"Post-update health check failed: managed MCP is incomplete for {agent_id}")

    if capabilities.get("handoff_hooks") or capabilities.get("ui_design_hook"):
        for agent_id in set(installation["agents"]) & {"claude", "codex"}:
            config = Path(plan["roots"]["home"]) / ".claude" / "settings.json" if agent_id == "claude" else Path(plan["roots"]["codex_home"]) / "hooks.json"
            commands, parse_state = hook_commands(config)
            if parse_state != "parsed":
                raise CliError(f"Post-update health check failed: hook configuration is {parse_state} for {agent_id}")
            if capabilities.get("handoff_hooks") and not any(
                str(runtime) in command and "hook handoff-on-keyword" in command for command in commands
            ):
                raise CliError(f"Post-update health check failed: handoff hook is missing for {agent_id}")
            if capabilities.get("ui_design_hook") and not any(
                str(runtime) in command and "hook ui-design-reminder" in command for command in commands
            ):
                raise CliError(f"Post-update health check failed: UI design hook is missing for {agent_id}")

    if capabilities.get("hooks"):
        hook_dir = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--git-path", "hooks"],
            text=True,
            capture_output=True,
            check=False,
        )
        if hook_dir.returncode:
            raise CliError("Post-update health check failed: managed Git hook target is not a repository")
        resolved = Path(hook_dir.stdout.strip())
        if not resolved.is_absolute():
            resolved = target / resolved
        pre_commit = resolved / "pre-commit"
        text = pre_commit.read_text(encoding="utf-8", errors="replace") if pre_commit.is_file() else ""
        if str(runtime) not in text or "hook git-pre-commit" not in text:
            raise CliError("Post-update health check failed: managed Git pre-commit hook is missing or stale")

    for agent_id, expected_safety in installation["safety"].items():
        if inspect_safety(agent_id)["state"] != expected_safety:
            raise CliError(f"Post-update health check failed: native safety does not match the manifest for {agent_id}")


def restore_changes(changes: list[dict[str, Any]], roots: dict[str, str], backup_root: Path) -> None:
    for change in reversed(changes):
        path = safe_update_path(Path(roots[change["root"]]), change["path"])
        if change["existed"]:
            backup_path = safe_update_path(backup_root, Path(change["root"]) / change["path"])
            content = backup_path.read_bytes()
            if hashlib.sha256(content).hexdigest() != change["before_sha256"]:
                raise CliError(f"Rollback backup hash mismatch for {change['root']}:{change['path']}")
            atomic_write_bytes(path, content, change["before_mode"])
        elif path.exists():
            if path.is_dir():
                raise CliError(f"Rollback refused to remove unexpected directory {path}")
            path.unlink()


def cmd_update_apply(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan).expanduser().resolve()
    plan = validated_plan(plan_path)
    recheck_plan_fingerprints(plan)
    update_home = home_dir().resolve()
    receipt_root = safe_update_path(update_home, ".agentsmith/update-receipts")
    update_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + plan["integrity"][-12:]
    backup_root = safe_update_path(update_home, Path(".agentsmith/update-backups") / update_id)
    changes: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="agentsmith-apply-") as temporary:
        temporary_root = Path(temporary)
        checkout, proposed = stage_planned_update(plan, temporary_root, execute_candidate=True)
        actual_proposal = proposed_change_manifest(plan, proposed)
        if actual_proposal != plan["proposed_changes"]:
            raise CliError("Update refused: staged managed changes do not match the authenticated plan")
        try:
            for root_name, relative, content, mode in proposed:
                actual = safe_update_path(Path(plan["roots"][root_name]), relative)
                existed = actual.is_file()
                before_content = actual.read_bytes() if existed else b""
                before_mode = actual.stat().st_mode & 0o777 if existed else None
                if existed:
                    backup_path = safe_update_path(backup_root, Path(root_name) / relative)
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(actual, backup_path)
                atomic_write_bytes(actual, content, mode)
                changes.append({
                    "root": root_name,
                    "path": relative,
                    "existed": existed,
                    "before_sha256": hashlib.sha256(before_content).hexdigest() if existed else None,
                    "before_mode": before_mode,
                    "after_sha256": hashlib.sha256(content).hexdigest(),
                    "after_mode": mode,
                })
            validate_post_update_health(plan)
            doctor_arguments = ["doctor", "--agent", ",".join(plan["installation"]["agents"]), "--strict"]
            doctor_arguments += ["--target", plan["target"]]
            doctor = subprocess.run(
                [sys.executable, str(checkout / "agentsmith.py"), *doctor_arguments],
                text=True,
                capture_output=True,
                check=False,
                timeout=120,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
            if doctor.returncode:
                raise CliError(f"Post-update doctor failed:\n{(doctor.stdout + doctor.stderr).strip()[-1000:]}")
        except Exception:
            restore_changes(changes, plan["roots"], backup_root)
            raise
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": plan["scope"],
        "plan_integrity": plan["integrity"],
        "release": plan["release"],
        "roots": plan["roots"],
        "backup_root": str(backup_root),
        "changes": changes,
    }
    receipt["integrity"] = plan_integrity(receipt, update_integrity_key(create=False))
    receipt_path = receipt_root / f"{update_id}.json"
    try:
        receipt_root.mkdir(parents=True, exist_ok=True)
        backup_root.mkdir(parents=True, exist_ok=True)
        receipt_root.chmod(0o700)
        backup_root.chmod(0o700)
        atomic_write(receipt_path, json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    except Exception:
        restore_changes(changes, plan["roots"], backup_root)
        raise
    ok(f"applied {plan['release']['tag']} after fingerprint and health checks")
    say(f"rollback receipt: {receipt_path}")
    return 0


def cmd_update_rollback(args: argparse.Namespace) -> int:
    receipt_path = Path(args.receipt).expanduser().resolve()
    receipt = load_update_document(receipt_path, "receipt")
    allowed = {
        "schema_version", "created_at", "scope", "plan_integrity", "release", "roots",
        "backup_root", "changes", "integrity",
    }
    if set(receipt) != allowed or receipt["schema_version"] != 1:
        raise CliError("Rollback receipt has unsupported fields or schema")
    update_home = home_dir().resolve()
    expected_backup_parent = safe_update_path(update_home, ".agentsmith/update-backups")
    raw_backup_root = Path(receipt["backup_root"])
    try:
        backup_relative = raw_backup_root.relative_to(update_home)
    except ValueError as exc:
        raise CliError("Rollback receipt points outside the local update-backup directory") from exc
    backup_root = safe_update_path(update_home, backup_relative)
    if backup_root.parent != expected_backup_parent:
        raise CliError("Rollback receipt points outside the local update-backup directory")
    if receipt["scope"] not in {"project", "global"}:
        raise CliError("Rollback receipt scope is invalid")
    expected_home = str(home_dir().resolve())
    expected_codex = str(codex_home().resolve())
    if receipt["roots"].get("home") != expected_home or receipt["roots"].get("codex_home") != expected_codex:
        raise CliError("Rollback receipt does not match the current HOME and CODEX_HOME")
    if receipt["scope"] == "global" and receipt["roots"].get("target") != expected_home:
        raise CliError("Global rollback receipt target does not match HOME")
    for change in receipt["changes"]:
        if not isinstance(change, dict) or set(change) != {
            "root", "path", "existed", "before_sha256", "before_mode", "after_sha256", "after_mode"
        }:
            raise CliError("Rollback receipt contains a malformed change")
        if not isinstance(change["after_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", change["after_sha256"]):
            raise CliError("Rollback receipt contains a malformed post-update hash")
        if not isinstance(change["after_mode"], int) or not 0 <= change["after_mode"] <= 0o777:
            raise CliError("Rollback receipt contains a malformed post-update mode")
        if not isinstance(change["existed"], bool):
            raise CliError("Rollback receipt contains a malformed existence flag")
        if change["existed"] and (
            not isinstance(change["before_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", change["before_sha256"])
            or not isinstance(change["before_mode"], int)
            or not 0 <= change["before_mode"] <= 0o777
        ):
            raise CliError("Rollback receipt contains a malformed pre-update baseline")
        if not change["existed"] and (change["before_sha256"] is not None or change["before_mode"] is not None):
            raise CliError("Rollback receipt create operation has an existing-file baseline")
        if change["root"] not in receipt["roots"] or Path(change["path"]).is_absolute() or ".." in Path(change["path"]).parts:
            raise CliError("Rollback receipt contains an unsafe path")
        if not allowed_update_path(change["root"], change["path"], {}):
            raise CliError("Rollback receipt contains a path outside managed update surfaces")
        current = safe_update_path(Path(receipt["roots"][change["root"]]), change["path"])
        actual_hash = file_sha256(current) if current.is_file() else None
        actual_mode = current.stat().st_mode & 0o777 if current.is_file() else None
        if actual_hash != change["after_sha256"] or actual_mode != change["after_mode"]:
            raise CliError(f"Rollback refused: {change['root']}:{change['path']} changed after update")
    restore_changes(receipt["changes"], receipt["roots"], backup_root)
    ok(f"rolled back {len(receipt['changes'])} file(s) from {receipt_path}")
    return 0


def cmd_update_configure(args: argparse.Namespace) -> int:
    policy = {"auto_check": args.auto_check}
    root = home_dir().resolve()
    state = load_update_state(root)
    state["update_policy"] = policy
    atomic_write(state_path(root), json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    if args.auto_check == "weekly":
        ok("weekly report-only update checks enabled; installation still requires 'update apply --plan'")
    else:
        ok("automatic update checks disabled")
    return 0


def maybe_report_automatic_update() -> None:
    try:
        state = load_state(home_dir().resolve())
        policy = state.get("update_policy")
        if not isinstance(policy, dict) or policy.get("auto_check") != "weekly":
            return
        now = dt.datetime.now(dt.timezone.utc)
        raw_attempt = policy.get("last_attempt_at")
        if isinstance(raw_attempt, str):
            try:
                last_attempt = dt.datetime.fromisoformat(raw_attempt)
            except ValueError:
                last_attempt = None
            if last_attempt and last_attempt.tzinfo and now - last_attempt < dt.timedelta(days=7):
                return
        policy = {**policy, "last_attempt_at": now.isoformat()}
        record_state(home_dir().resolve(), "update_policy", policy, dry_run=False)
        releases = stable_release_tags(OFFICIAL_REMOTE, timeout_seconds=3)
        if not releases:
            return
        latest, tag = releases[-1]
        current = tuple(int(part) for part in VERSION.split(".")) if re.fullmatch(r"\d+\.\d+\.\d+", VERSION) else (0, 0, 0)
        policy["last_checked_at"] = now.isoformat()
        record_state(home_dir().resolve(), "update_policy", policy, dry_run=False)
        if latest > current:
            say(f"update available: {tag}; run 'agentsmith update plan' when you want to inspect it")
    except (CliError, OSError) as exc:
        warn(f"weekly update check skipped: {exc}")


def reassemble_managed_targets(args: argparse.Namespace) -> None:
    """Refresh managed instructions in the installation scope selected for self-update."""
    target = Path(args.target or os.getcwd()).expanduser().resolve()
    global_candidates = [home_dir() / ".claude" / "CLAUDE.md", codex_home() / "AGENTS.md"]
    project_candidates = [target / "AGENTS.md", target / "CLAUDE.md"]
    if args.global_mode:
        candidates = global_candidates
    elif args.target:
        candidates = project_candidates
    else:
        candidates = [*global_candidates, *project_candidates]
    refreshed = 0
    seen: set[Path] = set()
    for path in candidates:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        if not managed_markers(text):
            continue
        metadata = re.search(r"Generated\. Profiles: ([^.]+)\. core=(true|false)\.", text)
        if not metadata:
            warn(f"{path}: managed block has no generator metadata; rerun install with an explicit profile")
            continue
        profiles = [] if metadata.group(1) == "none" else metadata.group(1).split(",")
        missing = [profile for profile in profiles if not (ROOT / "profiles" / f"{profile}.md").exists()]
        if missing:
            warn(f"{path}: updated harness no longer contains profile(s) {', '.join(missing)}; skipped")
            continue
        block = build_instructions(args, profiles, metadata.group(2) == "true", recover_identity([path]))
        reconcile_markdown(path, block, force=False, dry_run=False)
        refreshed += 1
    if refreshed:
        ok(f"reassembled {refreshed} managed instruction target(s)")
    else:
        warn("no managed instruction targets found in the global locations or current project")


def validate_design_system_source(source: str | None) -> None:
    if not source or source in {"skip", "stub", "generate"}:
        return
    if not source.startswith("catalog:"):
        raise CliError("--design-system must be skip, stub, generate, or catalog:<slug>")
    slug = source.removeprefix("catalog:")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", slug):
        raise CliError("catalog design-system slug may contain only letters, numbers, dot, underscore, and hyphen")


def scaffold_design_system(target: Path, source: str | None, *, dry_run: bool) -> None:
    if not source or source == "skip":
        return
    validate_design_system_source(source)
    destination = target / "DESIGN.md"
    if destination.exists():
        ok("DESIGN.md already present; left unchanged")
        return
    if dry_run:
        say(f"DRY RUN — would scaffold {destination} from {source}")
        return
    if source.startswith("catalog:"):
        slug = source.removeprefix("catalog:")
        url = f"https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/{slug}/DESIGN.md"
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                payload = response.read()
            if not payload.strip():
                raise CliError(f"catalog:{slug} returned an empty DESIGN.md")
            atomic_write(destination, payload.decode("utf-8"))
            ok(f"added DESIGN.md from catalog:{slug}; review and adapt it to the project")
            return
        except (OSError, UnicodeError, urllib.error.URLError, CliError) as exc:
            warn(f"could not fetch catalog:{slug} ({exc}); using the bundled template")
    shutil.copy2(ROOT / "templates" / "design-system.md", destination)
    if source == "generate":
        ok("added DESIGN.md template; generate its contents with the project's approved design workflow")
    else:
        ok("added DESIGN.md template; fill in its TODOs")


def org_policy_install(args: argparse.Namespace, agents: list[str]) -> int:
    if agents != ["claude"]:
        raise CliError("--org-policy is Claude-only; select exactly --agent claude")
    configured = os.environ.get("HARNESS_ORG_DIR")
    if configured:
        org_dir = Path(configured).expanduser()
    elif os.name == "nt":
        org_dir = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "ClaudeCode"
    elif sys.platform == "darwin":
        org_dir = Path("/Library/Application Support/ClaudeCode")
    else:
        org_dir = Path("/etc/claude-code")
    instructions_path = org_dir / "CLAUDE.md"
    settings_path = org_dir / "managed-settings.json"
    state_file = org_dir / ".agentsmith-org-state.json"
    if args.uninstall:
        remove_managed_markdown(instructions_path, dry_run=args.dry_run)
        if state_file.exists() and settings_path.exists() and not args.dry_run:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            permissions = settings.setdefault("permissions", {})
            for key, prior in state.get("permissions", {}).items():
                if prior is None:
                    permissions.pop(key, None)
                else:
                    permissions[key] = prior
            if not permissions:
                settings.pop("permissions", None)
            backup(settings_path)
            if settings:
                atomic_write(settings_path, json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
            else:
                settings_path.unlink()
            state_file.unlink()
        return 0
    profiles = csv(args.profile)
    recovery = recover_identity([instructions_path])
    block = build_instructions(args, profiles, True, recovery)
    reconcile_markdown(instructions_path, block, force=args.force, dry_run=args.dry_run)
    prior_settings: dict[str, Any] = {}
    if settings_path.exists():
        try:
            prior_settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CliError(f"Refusing to modify invalid organization JSON {settings_path}: {exc}") from exc
    if not args.dry_run and not state_file.exists():
        previous_permissions = prior_settings.get("permissions", {})
        atomic_write(
            state_file,
            json.dumps(
                {"permissions": {key: previous_permissions.get(key) for key in ("disableBypassPermissionsMode", "disableAutoMode")}},
                indent=2,
            ) + "\n",
        )
    def harden(data: dict[str, Any]) -> None:
        permissions = data.setdefault("permissions", {})
        permissions["disableBypassPermissionsMode"] = "disable"
        permissions["disableAutoMode"] = "disable"
    merge_json(settings_path, harden, dry_run=args.dry_run)
    ok(f"Claude organization policy installed in {org_dir}")
    return 0


def append_unique_hook(data: dict[str, Any], event: str, command: str, matcher: str | None = None) -> None:
    hooks = data.setdefault("hooks", {}).setdefault(event, [])
    hooks[:] = [entry for entry in hooks if not any(command.split()[-1] in h.get("command", "") for h in entry.get("hooks", []))]
    entry: dict[str, Any] = {"hooks": [{"type": "command", "command": command}]}
    if matcher:
        entry["matcher"] = matcher
    hooks.append(entry)


def native_command(*arguments: str) -> str:
    return subprocess.list2cmdline(list(arguments)) if os.name == "nt" else shlex.join(arguments)


def install_hooks(target: Path, agents: list[str], args: argparse.Namespace) -> None:
    if not (args.with_handoff_hooks or args.with_ui_design_hook or args.with_hooks):
        return
    runtime = copy_runtime(home_dir() if args.global_mode else target, dry_run=args.dry_run)
    if args.with_handoff_hooks and "claude" in agents:
        def claude(data: dict[str, Any]) -> None:
            append_unique_hook(data, "UserPromptSubmit", native_command(sys.executable, str(runtime), "hook", "handoff-on-keyword"))
            append_unique_hook(data, "Stop", native_command(sys.executable, str(runtime), "hook", "context-budget-nudge"))
        merge_json(home_dir() / ".claude" / "settings.json", claude, dry_run=args.dry_run)
    if args.with_handoff_hooks and "codex" in agents:
        def codex(data: dict[str, Any]) -> None:
            append_unique_hook(data, "UserPromptSubmit", native_command(sys.executable, str(runtime), "hook", "handoff-on-keyword"))
        merge_json(codex_home() / "hooks.json", codex, dry_run=args.dry_run)
    if args.with_ui_design_hook:
        for agent, path in (("claude", home_dir() / ".claude" / "settings.json"), ("codex", codex_home() / "hooks.json")):
            if agent in agents:
                def ui(data: dict[str, Any]) -> None:
                    append_unique_hook(data, "PreToolUse", native_command(sys.executable, str(runtime), "hook", "ui-design-reminder"), "^(Edit|Write|apply_patch)$")
                merge_json(path, ui, dry_run=args.dry_run)
    if args.with_hooks and not args.global_mode:
        install_git_hooks(target, runtime, dry_run=args.dry_run)
    elif args.with_hooks:
        warn("--with-hooks is project-scoped and was ignored with --global")


def install_git_hooks(target: Path, runtime: Path, *, dry_run: bool) -> None:
    git_hooks = subprocess.run(["git", "-C", str(target), "rev-parse", "--git-path", "hooks"], text=True, capture_output=True)
    if git_hooks.returncode:
        warn("--with-hooks skipped: target is not a git repository")
        return
    hooks = Path(git_hooks.stdout.strip())
    if not hooks.is_absolute():
        hooks = target / hooks
    # Git supplies its own POSIX launcher on Windows; no separately installed Git Bash/WSL is
    # required. The hook delegates immediately to the exact interpreter that ran setup.
    command = (
        "#!/bin/sh\n"
        f"exec {shlex.quote(sys.executable)} {shlex.quote(str(runtime))} hook git-pre-commit\n"
    )
    if dry_run:
        say(f"DRY RUN — would install {hooks / 'pre-commit'}")
        return
    path = hooks / "pre-commit"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and " hook git-pre-commit" not in path.read_text(encoding="utf-8", errors="replace"):
        warn(f"foreign pre-commit hook preserved; add Agentsmith manually: {path}")
        return
    atomic_write(path, command)
    path.chmod(path.stat().st_mode | 0o111)
    ok(f"installed native-Python git hook {path}")


def scaffold_project(target: Path, profiles: list[str], agents: list[str], args: argparse.Namespace) -> None:
    if args.dry_run:
        say(f"DRY RUN — would scaffold cross-platform helpers under {target / '.agentsmith'}")
        return
    for path in (target / "docs/research/_archive", target / "docs/feedback/_archive", target / ".harness/handoffs", target / ".planning"):
        path.mkdir(parents=True, exist_ok=True)
    copy_runtime(target, dry_run=False)
    templates = target / ".harness" / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    for source in (ROOT / "templates").glob("*.md"):
        destination = templates / source.name
        if not destination.exists():
            shutil.copy2(source, destination)
    conf = target / ".harness" / "verify.conf"
    if not conf.exists():
        chunks = [f"# Generated for profile(s): {','.join(profiles)}", "# Commands run with the native OS shell.", ""]
        for profile in profiles:
            preset = ROOT / "config" / "verify-presets" / f"{profile}.conf"
            if preset.exists():
                chunks.append(preset.read_text(encoding="utf-8").rstrip())
        chunks.append('unwired :: echo "wire real verification phases in .harness/verify.conf" && exit 1')
        atomic_write(conf, "\n".join(chunks) + "\n")
    if "software-dev" in profiles:
        source = ROOT / "scripts" / "autonomous-run.py"
        destination = target / ".agentsmith" / "autonomous-run.py"
        if source.exists() and not destination.exists():
            shutil.copy2(source, destination)


def instruction_paths(target: Path, agents: list[str], global_mode: bool) -> tuple[list[Path], list[Path]]:
    if global_mode:
        canonical = []
        native: list[Path] = []
        if "codex" in agents:
            native.append(codex_home() / "AGENTS.md")
        if "claude" in agents:
            native.append(home_dir() / ".claude" / "CLAUDE.md")
        return canonical, native
    canonical = [target / "AGENTS.md"]
    generated = [target / "CLAUDE.md"] if "claude" in agents else []
    return canonical, generated


def remove_owned_text_block(path: Path, *, dry_run: bool) -> None:
    if not path.exists():
        return
    old = path.read_text(encoding="utf-8")
    rendered = re.sub(
        rf"(?ms)^\s*{re.escape(TEXT_BEGIN)}\n.*?^{re.escape(TEXT_END)}\s*\n?", "", old
    ).lstrip("\n")
    if rendered == old:
        return
    if dry_run:
        say(f"DRY RUN — would remove Agentsmith's managed block from {path}")
        return
    backup(path)
    if rendered.strip():
        atomic_write(path, rendered)
    else:
        path.unlink()


def remove_owned_hooks(path: Path, *, dry_run: bool) -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    hooks = data.get("hooks", {})
    for event in list(hooks):
        kept = []
        for entry in hooks[event]:
            commands = [hook.get("command", "") for hook in entry.get("hooks", [])]
            if any("agentsmith.py" in command and " hook " in command for command in commands):
                changed = True
            else:
                kept.append(entry)
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    if not hooks:
        data.pop("hooks", None)
    if not changed:
        return
    if dry_run:
        say(f"DRY RUN — would remove Agentsmith's hook definitions from {path}")
        return
    backup(path)
    if data:
        atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    else:
        path.unlink()


def remove_owned_skills(target: Path, agents: list[str], *, dry_run: bool) -> None:
    destinations = [target / ".agents" / "skills"]
    if "claude" in agents:
        destinations.append(target / ".claude" / "skills")
    for destination in destinations:
        for source in sorted((ROOT / "skills").iterdir()):
            installed = destination / source.name
            if not source.is_dir() or not installed.is_dir():
                continue
            source_files = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
            installed_files = {p.relative_to(installed): p.read_bytes() for p in installed.rglob("*") if p.is_file()}
            if source_files != installed_files:
                warn(f"modified skill preserved during uninstall: {installed}")
                continue
            if dry_run:
                say(f"DRY RUN — would remove managed skill {installed}")
            else:
                shutil.rmtree(installed)


def uninstall(args: argparse.Namespace, agents: list[str], target: Path) -> int:
    ownership = load_state(home_dir() if args.global_mode else target)
    remove_default_statuslines(agents, target, args.global_mode, dry_run=args.dry_run)
    canonical, generated = instruction_paths(target, agents, args.global_mode)
    for path in [*canonical, *generated]:
        remove_managed_markdown(path, dry_run=args.dry_run)
    if not args.global_mode:
        gemini_path = target / ".gemini" / "settings.json"
        if "gemini-cli" in agents and ownership.get("gemini_context_added", True) and gemini_path.exists():
            if args.dry_run:
                say(f"DRY RUN — would remove Agentsmith's context filename from {gemini_path}")
            else:
                data = json.loads(gemini_path.read_text(encoding="utf-8"))
                context = data.get("context", {})
                current = context.get("fileName", [])
                if isinstance(current, str):
                    current = [current]
                context["fileName"] = [value for value in current if value != "AGENTS.md"]
                if not context["fileName"]:
                    context.pop("fileName", None)
                if not context:
                    data.pop("context", None)
                backup(gemini_path)
                if data:
                    atomic_write(gemini_path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
                else:
                    gemini_path.unlink()
        for path in (target / ".continue/rules/agentsmith.md", target / ".goosehints", target / ".aider.conf.yml"):
            if path.exists():
                if args.dry_run:
                    say(f"DRY RUN — would remove Agentsmith's adapter block from {path}")
                else:
                    text = re.sub(rf"(?ms)^\s*{re.escape(TEXT_BEGIN)}\n.*?^{re.escape(TEXT_END)}\s*\n?", "", path.read_text(encoding="utf-8"))
                    text = re.sub(r"(?m)^\s*-\s*AGENTS\.md\s*# agentsmith-managed\s*$", "", text).strip()
                    if text: atomic_write(path, text + "\n")
                    else: path.unlink()
        if "codex" in agents:
            remove_owned_text_block(target / ".codex" / "config.toml", dry_run=args.dry_run)
        if "claude" in agents:
            mcp_path = target / ".mcp.json"
            owned_names = ownership.get("claude_mcp_added", [])
            if mcp_path.exists() and owned_names:
                data = json.loads(mcp_path.read_text(encoding="utf-8"))
                servers = data.get("mcpServers", {})
                for name in owned_names:
                    servers.pop(name, None)
                if not servers:
                    data.pop("mcpServers", None)
                if not args.dry_run:
                    backup(mcp_path)
                    if data: atomic_write(mcp_path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
                    else: mcp_path.unlink()
        remove_owned_hooks(home_dir() / ".claude" / "settings.json", dry_run=args.dry_run)
        remove_owned_hooks(codex_home() / "hooks.json", dry_run=args.dry_run)
    else:
        if "codex" in agents:
            remove_owned_text_block(codex_home() / "config.toml", dry_run=args.dry_run)
        if "claude" in agents:
            settings = home_dir() / ".claude" / "settings.json"
            if settings.exists():
                data = json.loads(settings.read_text(encoding="utf-8"))
                permissions = data.get("permissions", {})
                if isinstance(permissions, dict) and permissions.get("defaultMode") in {"acceptEdits", "bypassPermissions"}:
                    permissions.pop("defaultMode", None)
                    if not permissions:
                        data.pop("permissions", None)
                    if not args.dry_run:
                        backup(settings)
                        if data: atomic_write(settings, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
                        else: settings.unlink()
    if ownership.get("skills_installed"):
        remove_owned_skills(home_dir() if args.global_mode else target, agents, dry_run=args.dry_run)
    ok("uninstall removed only Agentsmith-owned instruction/config blocks; scaffolding was retained")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    agents = resolve_agents(args.agent, args.platform)
    if args.self_update:
        return self_update(args)
    if args.update_plugins:
        if "claude" not in agents:
            raise CliError("--update-plugins is Claude-only; select --agent claude or native")
        if args.dry_run:
            say("DRY RUN — would ask the Claude CLI to update installed plugins")
            return 0
        if not shutil.which("claude"):
            raise CliError("Claude CLI is not on PATH; update in-app with /plugin update")
        result = subprocess.run(["claude", "plugin", "update"])
        return result.returncode
    if args.org_policy:
        return org_policy_install(args, agents)
    target = Path(args.target or os.getcwd()).expanduser().resolve()
    validate_design_system_source(args.design_system)
    if args.global_mode and args.target:
        raise CliError("--target cannot be combined with --global; global destinations are fixed by each runtime")
    if args.global_mode and csv(args.with_mcp):
        raise CliError("--with-mcp is project-scoped; global MCP ownership is not supported")
    if args.global_mode and args.assemble_only and not args.dry_run:
        warn("--assemble-only skips runtime config but still WRITES global instruction files; use --dry-run to write nothing")
    if args.tracker_writes and args.tracker_writes not in {"ask", "allowed"}:
        raise CliError("--tracker-writes must be 'ask' or 'allowed'")
    if args.also_agents_md:
        warn("--also-agents-md is deprecated: project AGENTS.md is now always canonical")
    if args.also_gemini_md:
        warn("--also-gemini-md is deprecated: select --agent gemini-cli to point Gemini at canonical AGENTS.md")
    if args.with_rtk:
        warn("--with-rtk no longer adds proprietary instruction imports; configure output compression outside canonical AGENTS.md")
    profiles = csv(args.profile)
    if profiles == ["auto"]:
        profiles = [detect_profile(target)]
        say(f"auto-detected profile: {profiles[0]}")
    if args.uninstall:
        return uninstall(args, agents, target)
    if not profiles and not args.global_mode:
        raise CliError("Pick a profile with --profile <name[,name]> or use --global")
    canonical, generated = instruction_paths(target, agents, args.global_mode)
    ownership_safety = load_state(home_dir()).get("native_safety", {})
    if not isinstance(ownership_safety, dict):
        ownership_safety = {}
    prior_managed_safety: dict[str, str] = {
        agent_id: value
        for agent_id, value in ownership_safety.items()
        if agent_id in agents and value in {"cautious", "trusted"}
    }
    had_managed_instructions = any(
        path.exists() and managed_markers(path.read_text(encoding="utf-8", errors="replace"))
        for path in (*canonical, *generated)
    )
    if had_managed_instructions and "claude" in agents and "claude" not in prior_managed_safety:
        claude_path = home_dir() / ".claude" / "settings.json"
        try:
            claude_data = json.loads(claude_path.read_text(encoding="utf-8")) if claude_path.exists() else {}
        except json.JSONDecodeError:
            claude_data = {}
        if claude_data.get("permissions", {}).get("defaultMode") == "bypassPermissions":
            prior_managed_safety["claude"] = "trusted"
    if "codex" in agents and "codex" not in prior_managed_safety:
        codex_path = codex_home() / "config.toml"
        codex_text = codex_path.read_text(encoding="utf-8", errors="replace") if codex_path.exists() else ""
        managed = re.search(
            rf"(?ms)^{re.escape(TEXT_BEGIN)}\n(.*?)^{re.escape(TEXT_END)}",
            codex_text,
        )
        if managed and 'approval_policy = "never"' in managed.group(1) and 'sandbox_mode = "danger-full-access"' in managed.group(1):
            prior_managed_safety["codex"] = "trusted"
    args.prior_managed_safety = prior_managed_safety
    recovery = recover_identity([*canonical, *generated])
    block = build_instructions(args, profiles, not args.profile_only, recovery)
    if args.export_instructions:
        print(block)
        return 0
    for path in canonical:
        reconcile_markdown(path, block, force=args.force, dry_run=args.dry_run)
    for path in generated:
        # Claude's copy is generated from canonical source, never independently assembled.
        reconcile_markdown(path, block, force=args.force, dry_run=args.dry_run)
    if not args.global_mode:
        install_adapters(target, agents, dry_run=args.dry_run)
        scaffold_project(target, profiles, agents, args)
        scaffold_design_system(target, args.design_system, dry_run=args.dry_run)
    install_native_config(target, agents, args)
    install_claude_plugin_packs(agents, args.with_plugins, dry_run=args.dry_run)
    if args.with_skills:
        skill_root = home_dir() if args.global_mode else target
        install_skills(skill_root, agents, force=args.force, dry_run=args.dry_run)
        record_state(skill_root, "skills_installed", True, dry_run=args.dry_run)
    install_hooks(target, agents, args)
    record_installation_manifest(target, agents, profiles, args, recovery)
    ok(f"installed for {', '.join(agents)}; canonical project instructions: AGENTS.md")
    return 0


def cmd_agents_list(args: argparse.Namespace) -> int:
    registry = load_registry()
    rows = registry.get("agents", [])
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    print("ID                TIER       INSTRUCTIONS  SKILLS       MCP          HOOKS")
    for agent in rows:
        skills_tools = agent.get("skills_tools", {})
        native_runtime = agent.get("native_runtime", {})
        print(
            f"{agent['id']:<17} {agent.get('target_tier','unknown'):<10} "
            f"{agent.get('instructions',{}).get('discovery','unknown'):<13} "
            f"{skills_tools.get('agent_skills',{}).get('client_support','unknown'):<12} "
            f"{skills_tools.get('mcp',{}).get('client_support','unknown'):<12} "
            f"{native_runtime.get('hooks',{}).get('client_support','unknown')}"
        )
    return 0


def compatibility_rows(selected: list[str] | None = None) -> list[dict[str, Any]]:
    rows = load_registry().get("agents", [])
    return [row for row in rows if not selected or row["id"] in selected]


def cmd_compatibility(args: argparse.Namespace) -> int:
    selected = resolve_agents(args.agent, None) if args.agent else None
    rows = compatibility_rows(selected)
    payload = {
        "contract_version": load_registry().get("contract_version"),
        "python": ">=3.11",
        "instruction_tokens": estimate_instruction_tokens(),
        "agents": rows,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"Instruction baseline: ~{payload['instruction_tokens']} tokens (unchanged semantic core)")
        for row in rows:
            skills_tools = row.get("skills_tools", {})
            native_runtime = row.get("native_runtime", {})
            evidence = row.get("evidence", [])
            levels = ",".join(dict.fromkeys(item.get("type", "unknown") for item in evidence)) or "none"
            print(
                f"{row['id']}: instructions={row.get('instructions',{}).get('discovery','unknown')} "
                f"skills={skills_tools.get('agent_skills',{}).get('client_support','unknown')} "
                f"mcp={skills_tools.get('mcp',{}).get('client_support','unknown')} "
                f"hooks={native_runtime.get('hooks',{}).get('client_support','unknown')} "
                f"evidence={levels}"
            )
    return 0


def estimate_instruction_tokens() -> int:
    # The published baseline is one self-contained coding project (core + software-dev),
    # not the core in isolation. Keep the same chars/4 calibration as lint-leanness.sh.
    sources = [*sorted((ROOT / "core").glob("*.md")), ROOT / "profiles" / "software-dev.md"]
    if all(path.exists() for path in sources):
        return sum(len(path.read_text(encoding="utf-8")) for path in sources) // 4
    # Installed helper runtimes intentionally do not duplicate source core/profile trees.
    return 8950


def doctor_warning(code: str, message: str, recommendation: str = "") -> dict[str, str]:
    return {"code": code, "message": message, "recommendation": recommendation}


def doctor_project_root(target: Path) -> Path:
    discovered = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "--show-toplevel"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if discovered.returncode == 0 and discovered.stdout.strip():
        return Path(discovered.stdout.strip()).resolve()
    return target.resolve()


def resolve_doctor_path(value: str, base: Path | None = None) -> Path:
    rendered = value.replace("$CODEX_HOME", str(codex_home())).replace("${CODEX_HOME}", str(codex_home()))
    path = Path(rendered).expanduser()
    return path.resolve() if path.is_absolute() else ((base or Path.cwd()) / path).resolve()


def managed_block(text: str) -> str:
    markers = managed_markers(text)
    if not markers:
        return ""
    begin, end = markers
    start = text.find(begin)
    finish = text.find(end, start + len(begin))
    return "" if finish < 0 else text[start:finish + len(end)]


def instruction_source(path: Path, scope: str) -> dict[str, Any]:
    record: dict[str, Any] = {
        "scope": scope,
        "path": str(path),
        "exists": path.is_file(),
        "managed": False,
        "managed_status": "missing",
        "generated_core": None,
        "profiles": [],
        "sha256": "",
        "fingerprint_sha256": "",
        "tokens": 0,
        "core_tokens": 0,
    }
    if not path.is_file():
        return record
    payload = path.read_bytes()
    text = payload.decode("utf-8", errors="replace")
    block = managed_block(text)
    has_begin = any(begin in text for begin, _ in ((BEGIN, END), (LEGACY_BEGIN, END), (OLDER_BEGIN, OLDER_END)))
    record.update(
        {
            "managed": bool(block),
            "managed_status": "managed" if block else ("malformed" if has_begin else "unmanaged"),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "fingerprint_sha256": hashlib.sha256(payload).hexdigest(),
            "tokens": max(1, len(text) // 4),
        }
    )
    if not block:
        return record
    metadata = re.search(r"Generated\. Profiles: ([^.]+)\. core=(true|false)\.", block)
    if not metadata:
        record["managed_status"] = "malformed"
        return record
    record["profiles"] = [] if metadata.group(1) == "none" else metadata.group(1).split(",")
    record["generated_core"] = metadata.group(2) == "true"
    if record["generated_core"]:
        core = re.split(r"\n---\n\n# Work-Type Profile\(s\):", block, maxsplit=1)[0]
        record["core_tokens"] = max(1, len(core) // 4)
    return record


def instruction_chain(agent: dict[str, Any], target: Path) -> tuple[list[dict[str, Any]], Path]:
    discovery = agent.get("instructions", {})
    project_root = doctor_project_root(target)
    sources: list[dict[str, Any]] = []
    for raw in discovery.get("global_paths", []):
        sources.append(instruction_source(resolve_doctor_path(str(raw)), "global"))
    try:
        relative = target.resolve().relative_to(project_root)
        directories = [project_root]
        current = project_root
        for part in relative.parts:
            current /= part
            directories.append(current)
    except ValueError:
        directories = [target.resolve()]
        project_root = target.resolve()
    names = [str(value) for value in discovery.get("project_paths", ["AGENTS.md"])] or ["AGENTS.md"]
    for index, directory in enumerate(directories):
        candidates = [resolve_doctor_path(name, directory) for name in names]
        selected = next((candidate for candidate in candidates if candidate.is_file()), None)
        if selected:
            sources.append(instruction_source(selected, "project" if index == 0 else "nested"))
        elif index == 0:
            sources.append(instruction_source(candidates[0], "project"))
    return sources, project_root


def inspect_instructions(agent_id: str, agent: dict[str, Any], target: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    sources, project_root = instruction_chain(agent, target)
    warnings: list[dict[str, str]] = []
    existing = [source for source in sources if source["exists"]]
    malformed = [source for source in existing if source["managed_status"] == "malformed"]
    for source in malformed:
        warnings.append(
            doctor_warning(
                "malformed-instruction-metadata",
                f"Managed instruction metadata is malformed in {source['path']}",
                "Re-run install for this target after preserving any foreign content.",
            )
        )
    full_cores = [source for source in existing if source["generated_core"] is True]
    duplicate_tokens = max(0, sum(source["core_tokens"] for source in full_cores) - max(
        (source["core_tokens"] for source in full_cores), default=0
    ))
    if len(full_cores) > 1:
        warnings.append(
            doctor_warning(
                "duplicate-managed-core",
                "Global and project instruction sources both contain the full managed core.",
                "If collaborators can rely on the global layer, reinstall the project with --profile-only; keep the full project copy when self-containment is intentional.",
            )
        )
    canonical = project_root / "AGENTS.md"
    if agent_id == "claude" and canonical.is_file() and managed_block(canonical.read_text(encoding="utf-8", errors="replace")):
        generated = project_root / "CLAUDE.md"
        if not generated.is_file():
            warnings.append(
                doctor_warning(
                    "missing-generated-copy",
                    f"Claude generated copy is missing: {generated}",
                    "Re-run install with --agent claude for this project.",
                )
            )
        else:
            canonical_record = instruction_source(canonical, "project")
            generated_record = instruction_source(generated, "project")
            canonical_meta = (canonical_record["generated_core"], canonical_record["profiles"])
            generated_meta = (generated_record["generated_core"], generated_record["profiles"])
            if canonical_meta != generated_meta or managed_block(canonical.read_text(encoding="utf-8")) != managed_block(generated.read_text(encoding="utf-8")):
                warnings.append(
                    doctor_warning(
                        "conflicting-generator-metadata",
                        "Canonical AGENTS.md and Claude's generated copy disagree.",
                        "Re-run install so CLAUDE.md is regenerated from canonical AGENTS.md.",
                    )
                )
    path = next((source["path"] for source in reversed(existing)), str(project_root / "AGENTS.md"))
    state = "malformed" if malformed else ("healthy" if existing else "missing")
    return {
        "declared": str(agent.get("instructions", {}).get("discovery", "unverified")),
        "state": state,
        "path": path,
        "sources": sources,
        "combined_tokens": sum(source["tokens"] for source in existing),
        "duplicate_tokens": duplicate_tokens,
    }, warnings


def directory_snapshot(path: Path) -> dict[Path, bytes]:
    return {item.relative_to(path): item.read_bytes() for item in path.rglob("*") if item.is_file()} if path.is_dir() else {}


def inspect_skills(agent_id: str, agent: dict[str, Any], target: Path) -> dict[str, Any]:
    roots = [target / ".agents" / "skills"]
    if agent_id == "claude":
        roots.append(target / ".claude" / "skills")
    bundled = {path.name: directory_snapshot(path) for path in (ROOT / "skills").iterdir() if path.is_dir()}
    managed_names: set[str] = set()
    stale_names: set[str] = set()
    foreign_names: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for installed in root.iterdir():
            if not installed.is_dir():
                continue
            if installed.name not in bundled:
                foreign_names.add(installed.name)
            elif directory_snapshot(installed) == bundled[installed.name]:
                managed_names.add(installed.name)
            else:
                stale_names.add(installed.name)
    state = "stale" if stale_names else ("managed" if managed_names else ("foreign" if foreign_names else "missing"))
    return {
        "declared": str(agent.get("skills_tools", {}).get("agent_skills", {}).get("client_support", "unverified")),
        "state": state,
        "path": str(roots[0]),
        "paths": [str(path) for path in roots],
        "managed_names": sorted(managed_names),
        "stale_names": sorted(stale_names),
        "foreign_names": sorted(foreign_names),
    }


def inspect_mcp(agent_id: str, agent: dict[str, Any], target: Path) -> dict[str, Any]:
    declared = str(agent.get("skills_tools", {}).get("mcp", {}).get("client_support", "unverified"))
    managed_names: list[str] = []
    foreign_names: list[str] = []
    if agent_id == "claude":
        path = target / ".mcp.json"
        try:
            servers = json.loads(path.read_text(encoding="utf-8")).get("mcpServers", {}) if path.exists() else {}
        except json.JSONDecodeError:
            return {"declared": declared, "state": "malformed", "path": str(path), "managed_names": [], "foreign_names": []}
        owned = load_state(target).get("claude_mcp_added", [])
        owned = owned if isinstance(owned, list) else []
        managed_names = sorted(name for name in owned if name in servers)
        foreign_names = sorted(name for name in servers if name not in owned)
    elif agent_id == "codex":
        path = target / ".codex" / "config.toml"
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        try:
            servers = tomllib.loads(text).get("mcp_servers", {}) if text else {}
        except tomllib.TOMLDecodeError:
            return {"declared": declared, "state": "malformed", "path": str(path), "managed_names": [], "foreign_names": []}
        block = re.search(rf"(?ms)^{re.escape(TEXT_BEGIN)}\n(.*?)^{re.escape(TEXT_END)}", text)
        managed_names = sorted(set(re.findall(r"^\[mcp_servers\.([^]]+)\]", block.group(1), re.MULTILINE))) if block else []
        foreign_names = sorted(name for name in servers if name not in managed_names)
    else:
        path = target / "AGENTS.md"
        servers = {}
    state = "managed" if managed_names else ("foreign" if foreign_names else "missing")
    return {
        "declared": declared,
        "state": state,
        "path": str(path),
        "managed_names": managed_names,
        "foreign_names": foreign_names,
    }


def hook_commands(path: Path) -> tuple[list[str], str]:
    if not path.exists():
        return [], "missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], "malformed"
    commands: list[str] = []
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("command"), str):
                commands.append(value["command"])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(data.get("hooks", {}))
    return commands, "parsed"


def inspect_hooks(agent_id: str, agent: dict[str, Any], target: Path) -> dict[str, Any]:
    config = home_dir() / ".claude" / "settings.json" if agent_id == "claude" else codex_home() / "hooks.json"
    commands, parse_state = hook_commands(config) if agent_id in {"claude", "codex"} else ([], "missing")
    runtime = (target / ".agentsmith" / "agentsmith.py").resolve()
    managed_commands = [command for command in commands if "agentsmith.py" in command and " hook " in command]
    legacy_commands = [
        command for command in commands
        if any(name in command for name in ("handoff-on-keyword.sh", "context-budget-nudge.sh", "ui-design-reminder.sh"))
    ]
    stale_commands = [command for command in managed_commands if str(runtime) not in command] + legacy_commands
    git_hook = ""
    scanner_current = False
    git_root = doctor_project_root(target)
    hook_dir = subprocess.run(
        ["git", "-C", str(git_root), "rev-parse", "--git-path", "hooks"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if hook_dir.returncode == 0:
        resolved = Path(hook_dir.stdout.strip())
        if not resolved.is_absolute():
            resolved = git_root / resolved
        git_hook_path = resolved / "pre-commit"
        git_hook = str(git_hook_path)
        if git_hook_path.exists():
            hook_text = git_hook_path.read_text(encoding="utf-8", errors="replace")
            scanner_current = str(runtime) in hook_text and "hook git-pre-commit" in hook_text
            if "agentsmith" in hook_text.casefold() and not scanner_current:
                stale_commands.append(hook_text.strip())
    current_runtime = bool(managed_commands) and not stale_commands
    state = "malformed" if parse_state == "malformed" else (
        "stale" if stale_commands else ("managed" if managed_commands or scanner_current else ("foreign" if commands else "missing"))
    )
    return {
        "declared": str(agent.get("native_runtime", {}).get("hooks", {}).get("client_support", "unverified")),
        "state": state,
        "path": str(config),
        "commands": commands,
        "managed_commands": managed_commands,
        "stale_commands": stale_commands,
        "current_runtime": current_runtime,
        "scanner_path": git_hook,
        "scanner_current": scanner_current,
    }


def inspect_statusline(agent_id: str) -> dict[str, Any]:
    if agent_id == "claude":
        path = home_dir() / ".claude" / "settings.json"
        if not path.exists():
            return {"declared": "supported", "state": "missing", "active": False, "path": str(path)}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"declared": "supported", "state": "malformed", "active": False, "path": str(path)}
        if not isinstance(data, dict):
            return {"declared": "supported", "state": "malformed", "active": False, "path": str(path)}
        value = data.get("statusLine")
        ownership = load_state(home_dir()).get("native_statuslines", {})
        owned = ownership.get("claude", {}) if isinstance(ownership, dict) else {}
        if "statusLine" not in data:
            state = "missing"
        elif not value or data.get("disableAllHooks") is True:
            state = "disabled"
        elif isinstance(owned, dict) and value == owned.get("value"):
            files = owned.get("files", {})
            current = isinstance(files, dict) and bool(files) and all(
                Path(raw).is_file()
                and isinstance(expected_hash, str)
                and file_sha256(Path(raw)) == expected_hash
                for raw, expected_hash in files.items()
            )
            state = "managed" if current else "stale"
        else:
            state = "configured"
        return {
            "declared": "supported",
            "state": state,
            "active": state in {"managed", "configured"} or (
                state == "stale"
                and isinstance(owned, dict)
                and isinstance(owned.get("files"), dict)
                and bool(owned["files"])
                and all(Path(raw).is_file() for raw in owned["files"])
            ),
            "path": str(path),
        }
    if agent_id == "codex":
        path = codex_home() / "config.toml"
        if not path.exists():
            return {"declared": "supported", "state": "builtin", "active": True, "path": str(path)}
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError:
            return {"declared": "supported", "state": "malformed", "active": False, "path": str(path)}
        tui = data.get("tui", {})
        if not isinstance(tui, dict):
            state = "malformed"
        elif "status_line" not in tui:
            state = "builtin"
        elif not isinstance(tui.get("status_line"), list) or not all(
            isinstance(value, str) for value in tui["status_line"]
        ):
            state = "malformed"
        elif tui["status_line"] == []:
            state = "disabled"
        else:
            state = "configured"
        return {
            "declared": "supported",
            "state": state,
            "active": state in {"builtin", "configured"},
            "path": str(path),
        }
    return {"declared": "unsupported", "state": "unsupported", "active": False, "path": ""}


def inspect_runtime(agent: dict[str, Any], target: Path) -> dict[str, Any]:
    path = target / ".agentsmith" / "agentsmith.py"
    expected = Path(__file__).resolve()
    if not path.exists():
        state = "missing"
    elif hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(expected.read_bytes()).digest():
        state = "current"
    else:
        state = "stale"
    autonomous = target / ".agentsmith" / "autonomous-run.py"
    expected_autonomous = ROOT / "scripts" / "autonomous-run.py"
    autonomous_state = "missing"
    if autonomous.exists():
        autonomous_state = "current" if expected_autonomous.exists() and autonomous.read_bytes() == expected_autonomous.read_bytes() else "stale"
    return {
        "declared": str(agent.get("native_runtime", {}).get("lifecycle", {}).get("agentsmith_management", "unverified")),
        "state": state,
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "",
        "autonomous_path": str(autonomous),
        "autonomous_state": autonomous_state,
        "ownership_state_path": str(target / ".agentsmith" / "state.json"),
        "ownership_state_present": (target / ".agentsmith" / "state.json").is_file(),
    }


def inspect_safety(agent_id: str) -> dict[str, Any]:
    if agent_id == "claude":
        path = home_dir() / ".claude" / "settings.json"
        if not path.exists():
            return {"state": "missing", "path": str(path), "values": {}}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"state": "malformed", "path": str(path), "values": {}}
        mode = data.get("permissions", {}).get("defaultMode") if isinstance(data.get("permissions", {}), dict) else None
        state = {"acceptEdits": "cautious", "bypassPermissions": "trusted"}.get(mode, "foreign")
        return {"state": state, "path": str(path), "values": {"defaultMode": mode}}
    if agent_id == "codex":
        path = codex_home() / "config.toml"
        if not path.exists():
            return {"state": "missing", "path": str(path), "values": {}}
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError:
            return {"state": "malformed", "path": str(path), "values": {}}
        values = {"approval_policy": data.get("approval_policy"), "sandbox_mode": data.get("sandbox_mode")}
        mapping = {
            ("on-request", "workspace-write"): "cautious",
            ("never", "danger-full-access"): "trusted",
        }
        return {"state": mapping.get((values["approval_policy"], values["sandbox_mode"]), "foreign"), "path": str(path), "values": values}
    return {"state": "unsupported", "path": "", "values": {}}


def cmd_doctor(args: argparse.Namespace) -> int:
    selected = resolve_agents(args.agent, args.platform)
    target = Path(args.target or os.getcwd()).resolve()
    rows = {row["id"]: row for row in compatibility_rows(selected)}
    result: dict[str, Any] = {}
    unhealthy = False
    for agent_id in selected:
        agent = rows[agent_id]
        instructions, warnings = inspect_instructions(agent_id, agent, target)
        skills = inspect_skills(agent_id, agent, target)
        mcp = inspect_mcp(agent_id, agent, target)
        hooks = inspect_hooks(agent_id, agent, target)
        statusline = inspect_statusline(agent_id)
        runtime = inspect_runtime(agent, target)
        safety = inspect_safety(agent_id)
        capabilities = {
            "instructions": instructions,
            "skills": skills,
            "mcp": mcp,
            "hooks": hooks,
            "statusline": statusline,
            "runtime": runtime,
        }
        for name in ("skills", "mcp", "hooks", "statusline", "runtime"):
            capability = capabilities[name]
            if capability["declared"] in {"supported", "native"} and capability["state"] == "missing":
                warnings.append(
                    doctor_warning(
                        "declared-capability-missing",
                        f"{name} is declared available for {agent_id}, but no matching installed state was found.",
                        f"Re-run install with the intended {name} option if this project needs it.",
                    )
                )
        if hooks["state"] == "stale":
            warnings.append(
                doctor_warning(
                    "stale-managed-command",
                    "A managed hook or scanner command points at a stale/foreign AgentSmith runtime.",
                    "Re-run install with the relevant hook flags; foreign commands will be preserved.",
                )
            )
        expanded = any(capabilities[name]["state"] == "managed" for name in ("skills", "mcp", "hooks"))
        if safety["state"] == "trusted" and expanded:
            warnings.append(
                doctor_warning(
                    "trusted-expanded-surface",
                    "Trusted safety is combined with managed MCP, skills, or hooks.",
                    "Use cautious safety unless this expanded tool surface is deliberately trusted.",
                )
            )
        result[agent_id] = {**capabilities, "safety": safety, "warnings": warnings}
        unhealthy |= instructions["state"] in {"missing", "malformed"}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for agent_id, capabilities in result.items():
            print(agent_id)
            for name in ("instructions", "skills", "mcp", "hooks", "statusline", "runtime"):
                state = capabilities[name]
                print(f"  {name:<12} {state['state']:<9} declared={state['declared']}{' path=' + state['path'] if state['path'] else ''}")
            print(f"  {'safety':<12} {capabilities['safety']['state']:<9} path={capabilities['safety']['path']}")
            instruction_state = capabilities["instructions"]
            print(
                f"  instruction tokens combined={instruction_state['combined_tokens']} "
                f"duplicate={instruction_state['duplicate_tokens']}"
            )
            for source in instruction_state["sources"]:
                fingerprint = source["sha256"][:12] if source["sha256"] else "-"
                print(
                    f"    {source['scope']:<7} {source['managed_status']:<9} core={source['generated_core']} "
                    f"tokens={source['tokens']} sha256={fingerprint} path={source['path']}"
                )
            for warning in capabilities["warnings"]:
                suffix = f" Fix: {warning['recommendation']}" if warning["recommendation"] else ""
                print(f"  WARNING [{warning['code']}] {warning['message']}{suffix}")
    return 1 if unhealthy and args.strict else 0


def parse_verify_conf(path: Path) -> list[tuple[str, str]]:
    phases = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#") or "::" not in raw:
            continue
        label, command = raw.split("::", 1)
        if command.strip():
            phases.append((label.strip(), command.strip()))
    return phases


def cmd_verify(args: argparse.Namespace) -> int:
    root = Path(args.target or os.getcwd()).resolve()
    conf = root / ".harness" / "verify.conf"
    if not conf.exists():
        raise CliError(f"No verification config at {conf}")
    phases = [(label, cmd) for label, cmd in parse_verify_conf(conf) if not args.only or args.only in label]
    if args.list:
        for index, (label, command) in enumerate(phases, 1):
            print(f"{index}. {label} :: {command}")
        return 0
    for index, (label, command) in enumerate(phases, 1):
        print(f"[{index}/{len(phases)}] {label}\n  {command}")
        result = subprocess.run(command, cwd=root, shell=True)
        if result.returncode:
            warn(f"verification phase '{label}' failed with exit {result.returncode}")
            return result.returncode
    ok(f"all {len(phases)} verification phases passed")
    return 0


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "item"


def cmd_scaffold(kind: str, args: argparse.Namespace) -> int:
    root = Path(args.target or os.getcwd()).resolve()
    today = dt.date.today().isoformat()
    if kind == "handoff":
        directory = root / ".harness" / "handoffs"
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
        item = args.name or "UNTRACKED"
        name = f"handoff-{stamp}.md"
        def git_value(*git_args: str, fallback: str = "n/a") -> str:
            result = subprocess.run(["git", "-C", str(root), *git_args], capture_output=True, text=True)
            return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else fallback
        branch = git_value("rev-parse", "--abbrev-ref", "HEAD")
        head = git_value("rev-parse", "--short", "HEAD")
        status = git_value("status", "--porcelain", fallback="")
        dirty = len(status.splitlines()) if status else 0
        source = textwrap.dedent(f"""\
            # Handoff — {item} — {stamp}

            **Branch:** {branch}   **HEAD:** {head}   **Uncommitted files:** {dirty}
            {"> ⚠ Tree is dirty — commit or stash BEFORE handing off (core/50 step 1)." if dirty else ""}

            ## What shipped this session

            ## What is still pending

            ## Deviations from the plan / decisions made (don't re-litigate)

            ## Exact next step

            ## Gotchas a fresh session would otherwise re-derive

            ---
            ## Kickoff prompt for a fresh chat
            ```
            Resume {item} on branch {branch} (HEAD {head}). Summarize what is done, the single next step,
            key decisions already made, and this handoff note: .harness/handoffs/{name}
            ```
            """)
    elif kind == "new-feedback":
        directory = root / "docs" / "feedback"
        existing = [int(m.group(1)) for p in directory.glob("[0-9][0-9][0-9][0-9]-*.md") if (m := re.match(r"(\d{4})-", p.name))]
        number = max(existing, default=0) + 1
        name = f"{number:04d}-{slug(args.name)}.md"
        source = textwrap.dedent(f"""\
            # Feedback {number:04d}: {args.name}

            > A harness post-incident. The point is to make this class of mistake less likely next time.
            > Never delete this record; archive it under `_archive/` if it becomes obsolete.

            - **Date:** {today}
            - **Status:** open
            - **Cost:**

            ## 1. Evidence / symptom

            ## 2. Failure mechanism

            ## 3. Bounded edit

            ## 4. Named surface

            ## 5. Non-regression validation
            """)
    else:
        directory = root / "docs" / "research"
        name = f"{slug(args.name)}.md"
        source = textwrap.dedent(f"""\
            # Research: {args.name}

            > Source material and findings. Never delete this in a cleanup or history rewrite;
            > move it to `docs/research/_archive/` if it becomes obsolete.

            ## Question / scope

            ## Sources consulted

            ## Findings

            ## Open questions / what was not checked
            """)
    path = directory / name
    if path.exists():
        raise CliError(f"Refusing to overwrite existing {path}")
    if args.dry_run:
        print(path)
        return 0
    directory.mkdir(parents=True, exist_ok=True)
    atomic_write(path, source)
    print(path)
    return 0


def secret_scan_root(target: str | None) -> Path:
    candidate = Path(target or os.getcwd()).expanduser().resolve()
    result = subprocess.run(
        ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    return Path(result.stdout.strip()).resolve() if result.returncode == 0 else candidate


def secret_allow_rules(root: Path) -> list[re.Pattern[str]]:
    path = root / ".harness" / "secret-scan.allow"
    if not path.exists():
        return []
    rules: list[re.Pattern[str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise CliError(f"Cannot read secret-scan allow rules {path}: {exc}") from exc
    for number, raw in enumerate(lines, 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        try:
            rules.append(re.compile(raw))
        except re.error as exc:
            raise CliError(f"Invalid secret-scan allow regex at {path}:{number}: {exc}") from exc
    return rules


def scan_secret_records(
    records: Iterable[tuple[str, int, str]], allow_rules: list[re.Pattern[str]]
) -> list[tuple[str, int, str]]:
    findings: list[tuple[str, int, str]] = []
    for display_path, number, line in records:
        if not line.strip() or any(rule.search(line) for rule in allow_rules):
            continue
        for pattern_name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append((display_path, number, pattern_name))
                break
    return findings


def file_secret_records(path: Path, display_path: str) -> Iterable[tuple[str, int, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeError:
        return
    except OSError as exc:
        raise CliError(f"Cannot read secret-scan input {path}: {exc}") from exc
    for number, line in enumerate(text.splitlines(), 1):
        yield display_path, number, line


def tracked_secret_records(root: Path) -> Iterable[tuple[str, int, str]]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=False
    )
    if result.returncode:
        raise CliError(f"secret-scan --all needs a Git repository: {root}")
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = os.fsdecode(raw)
        path = root / relative
        if path.is_file():
            yield from file_secret_records(path, relative)


def staged_secret_records(root: Path) -> Iterable[tuple[str, int, str]]:
    result = subprocess.run(
        [
            "git", "-C", str(root), "-c", "core.quotepath=false", "diff", "--cached",
            "--no-color", "--no-ext-diff", "--unified=0", "--diff-filter=ACMR",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode:
        raise CliError(f"secret-scan needs a Git repository with a readable staged diff: {root}")
    display_path = ""
    line_number = 0
    in_hunk = False
    for raw in result.stdout.splitlines():
        if raw.startswith("+++ "):
            # Git appends a tab separator to some new-file headers. It is metadata, not part of
            # the path (core.quotepath=false keeps Unicode readable).
            display_path = raw[4:].split("\t", 1)[0]
            if display_path.startswith("b/"):
                display_path = display_path[2:]
            in_hunk = False
            continue
        if raw.startswith("@@ "):
            match = re.search(r"\+(\d+)(?:,\d+)?", raw)
            if not match:
                in_hunk = False
                continue
            line_number = int(match.group(1))
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if raw.startswith("+"):
            yield display_path, line_number, raw[1:]
            line_number += 1
        elif raw.startswith("-"):
            continue
        elif raw.startswith("\\ No newline"):
            continue
        else:
            line_number += 1


def cmd_secret_scan(args: argparse.Namespace) -> int:
    root = secret_scan_root(getattr(args, "target", None))
    paths = list(getattr(args, "paths", []) or [])
    scan_all = bool(getattr(args, "all", False))
    if scan_all and paths:
        raise CliError("secret-scan --all cannot be combined with file or stdin arguments")
    allow_rules = secret_allow_rules(root)
    if scan_all:
        records = tracked_secret_records(root)
    elif paths:
        def selected_records() -> Iterable[tuple[str, int, str]]:
            for value in paths:
                if value == "-":
                    for number, line in enumerate(sys.stdin.read().splitlines(), 1):
                        yield "<stdin>", number, line
                    continue
                path = Path(value).expanduser()
                if not path.is_absolute():
                    path = Path.cwd() / path
                yield from file_secret_records(path, value)
        records = selected_records()
    else:
        records = staged_secret_records(root)
    findings = scan_secret_records(records, allow_rules)
    if findings:
        for path, number, pattern_name in findings:
            print(f"{path}:{number}: {pattern_name}: [REDACTED]", file=sys.stderr)
        print(
            "secret-scan: BLOCKED — move the value to an environment variable or secret manager; "
            "allow only a genuine inert fixture via .harness/secret-scan.allow",
            file=sys.stderr,
        )
        return 1
    ok("secret-scan: clean")
    return 0


def cmd_hook(args: argparse.Namespace) -> int:
    payload = sys.stdin.read()
    if args.hook_name == "git-pre-commit":
        return cmd_secret_scan(argparse.Namespace(target=os.getcwd()))
    if args.hook_name == "handoff-on-keyword" and re.search(r"(?i)\b(wrap up|handoff|reset context)\b", payload):
        print(json.dumps({"additionalContext": "Before ending, create durable handoff memory with `agentsmith handoff`."}))
    elif args.hook_name == "context-budget-nudge":
        print(json.dumps({"additionalContext": "If the context is filling, write the handoff before summarizing."}))
    elif args.hook_name == "ui-design-reminder" and re.search(r"(?i)\.(css|scss|tsx|jsx|vue|svelte|html)", payload):
        print(json.dumps({"additionalContext": "Consult DESIGN.md before changing user-interface files, if it exists."}))
    return 0  # hooks fail open by design


def cmd_evaluate(args: argparse.Namespace) -> int:
    try:
        from evaluate import run_evaluation
        return int(run_evaluation(args, core_path=Path(__file__).resolve()))
    except (ValueError, RuntimeError) as exc:
        raise CliError(str(exc)) from exc


def add_common_install_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--agent", action="append", help="agent ID/group; repeatable or comma-separated")
    parser.add_argument("--platform", choices=("claude", "codex", "both"), help="deprecated alias for --agent")
    parser.add_argument("--profile", action="append")
    parser.add_argument("--target")
    parser.add_argument("--global", dest="global_mode", action="store_true")
    parser.add_argument("--profile-only", action="store_true")
    parser.add_argument("--assemble-only", action="store_true")
    parser.add_argument("--operator-name")
    parser.add_argument("--operator-role", help="operator responsibility used to calibrate decisions")
    parser.add_argument("--operator-bio", help="operator background and uneven expertise used to calibrate explanations")
    parser.add_argument("--tracker")
    parser.add_argument("--tracker-writes", choices=("ask", "allowed"))
    parser.add_argument(
        "--safety",
        choices=("cautious", "trusted"),
        default="cautious",
        help="native-client permission mode (default: cautious; trusted requires explicit opt-in)",
    )
    parser.add_argument("--with-skills", action="store_true")
    parser.add_argument("--with-mcp", action="append")
    parser.add_argument("--with-hooks", action="store_true")
    parser.add_argument("--with-handoff-hooks", action="store_true")
    parser.add_argument("--with-ui-design-hook", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--export-instructions", action="store_true")
    # Kept as accepted migration flags. Their integrations remain explicitly target-specific.
    parser.add_argument("--with-plugins")
    parser.add_argument("--with-rtk", action="store_true")
    parser.add_argument("--no-rtk", action="store_true")
    parser.add_argument("--design-system")
    parser.add_argument("--also-agents-md", action="store_true")
    parser.add_argument("--also-gemini-md", action="store_true")
    parser.add_argument("--org-policy", action="store_true")
    parser.add_argument("--update-plugins", action="store_true")
    parser.add_argument(
        "--self-update",
        action="store_true",
        help="deprecated: fast-forward only the clean harness checkout; does not provide staged install rollback",
    )
    parser.add_argument("--from", dest="update_from")
    parser.add_argument("--no-reassemble", action="store_true")
    parser.add_argument("--wizard", action="store_true")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="agentsmith",
        description="Cross-platform universal coding-agent harness",
        epilog=(
            "Run 'agentsmith install --help' for profiles, targets, safety, and capability flags. "
            "Install selection uses --agent <id|native|standard|local|all> (repeatable); "
            "legacy alias: --platform claude|codex|both."
        ),
    )
    root.add_argument("--version", action="version", version=f"agentsmith {VERSION}")
    sub = root.add_subparsers(dest="command")
    install = sub.add_parser("install", help="install or update managed rules and adapters")
    add_common_install_flags(install)
    update = sub.add_parser("update", help="check and apply staged stable-release updates")
    update_sub = update.add_subparsers(dest="update_command", required=True)
    update_check = update_sub.add_parser("check", help="report the latest stable release without changing an install")
    update_check.add_argument("--from", dest="update_from", help="explicit Git remote or local test remote")
    update_check.add_argument("--json", action="store_true")
    update_plan = update_sub.add_parser("plan", help="stage and inspect a release without changing an install")
    plan_scope = update_plan.add_mutually_exclusive_group(required=True)
    plan_scope.add_argument("--global", dest="global_mode", action="store_true")
    plan_scope.add_argument("--target")
    update_plan.add_argument("--version", help="stable release tag (default: latest stable)")
    update_plan.add_argument("--from", dest="update_from", help="explicit Git remote or local test remote")
    update_plan.add_argument("--save", help="write the plan to this local file")
    update_apply = update_sub.add_parser("apply", help="apply an inspected plan and write a rollback receipt")
    update_apply.add_argument("--plan", required=True)
    update_rollback = update_sub.add_parser("rollback", help="restore exact pre-update bytes from a receipt")
    update_rollback.add_argument("--receipt", required=True)
    update_configure = update_sub.add_parser("configure", help="opt into or disable report-only update checks")
    update_configure.add_argument("--auto-check", required=True, choices=("weekly", "off"))
    agents = sub.add_parser("agents", help="inspect the supported agent registry")
    agents_sub = agents.add_subparsers(dest="agents_command", required=True)
    listing = agents_sub.add_parser("list")
    listing.add_argument("--json", action="store_true")
    doctor = sub.add_parser("doctor", help="report each capability independently")
    doctor.add_argument("--agent", action="append")
    doctor.add_argument("--platform", choices=("claude", "codex", "both"))
    doctor.add_argument("--target")
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument("--strict", action="store_true")
    compatibility = sub.add_parser("compatibility", help="print the evidence-backed compatibility matrix")
    compatibility.add_argument("--agent", action="append")
    compatibility.add_argument("--json", action="store_true")
    verify = sub.add_parser("verify")
    verify.add_argument("--target")
    verify.add_argument("--only")
    verify.add_argument("--list", action="store_true")
    for name in ("handoff", "new-feedback", "new-research"):
        scaffold = sub.add_parser(name)
        scaffold.add_argument("name", nargs="?")
        scaffold.add_argument("--target")
        scaffold.add_argument("--dry-run", action="store_true")
    secret = sub.add_parser("secret-scan")
    secret.add_argument("--all", action="store_true", help="scan the tracked working tree")
    secret.add_argument("--target", help="Git/project root for staged, tracked-tree, and allow rules")
    secret.add_argument("paths", nargs="*", metavar="FILE", help="files to scan, or '-' for stdin")
    hook = sub.add_parser("hook")
    hook.add_argument("hook_name", choices=("handoff-on-keyword", "context-budget-nudge", "ui-design-reminder", "git-pre-commit"))
    evaluate = sub.add_parser("evaluate", help="run isolated native-client behavioral evaluations")
    evaluate.add_argument("--agent", required=True, choices=("claude", "codex", "native"),
                          help="native client to exercise; 'native' runs Claude and Codex")
    evaluate.add_argument("--scenario", action="append", help="scenario ID; repeatable (default: all nine)")
    evaluate.add_argument("--trials", type=int, default=3, help="fresh-repository trials per scenario (default: 3)")
    mode = evaluate.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="resolve the run without calling a model (default)")
    mode.add_argument("--live", action="store_true", help="call native clients; explicit positive budgets required")
    evaluate.add_argument("--claude-max-usd", type=float, default=0.0, help="run-wide Claude USD ceiling")
    evaluate.add_argument("--codex-max-tokens", type=int, default=0, help="run-wide Codex reported-token ceiling")
    evaluate.add_argument("--output", help="normalized record directory (raw logs always stay under ~/.agentsmith)")
    evaluate.add_argument("--timeout-seconds", type=int, default=600, help=argparse.SUPPRESS)
    return root


def normalize_legacy_argv(argv: list[str]) -> list[str]:
    if not argv:
        return ["install", "--wizard"]
    commands = {"install", "update", "agents", "doctor", "compatibility", "verify", "handoff", "new-feedback", "new-research", "secret-scan", "hook", "evaluate"}
    if argv[0] in commands or argv[0] in {"-h", "--help", "--version"}:
        return argv
    if "--doctor" in argv:
        return ["doctor", *[value for value in argv if value != "--doctor"]]
    return ["install", *argv]


def apply_wizard_answers(args: argparse.Namespace, input_fn: Any = input) -> None:
    chosen = input_fn("Agent ID/group [claude]: ").strip() or "claude"
    profile = input_fn("Profile [general-admin]: ").strip() or "general-admin"
    while True:
        safety = input_fn("Safety [cautious/trusted] [cautious]: ").strip() or "cautious"
        if safety in {"cautious", "trusted"}:
            break
        warn("Safety must be 'cautious' or 'trusted'; trusted is an explicit opt-in")
    args.agent = [chosen]
    args.profile = [profile]
    args.safety = safety
    args.wizard = False


def run(argv: list[str] | None = None) -> int:
    require_python()
    args = parser().parse_args(normalize_legacy_argv(list(argv if argv is not None else sys.argv[1:])))
    if args.command != "update":
        maybe_report_automatic_update()
    if args.command == "install":
        if args.wizard:
            print("Agentsmith interactive wizard is intentionally minimal in non-interactive automation.")
            print("Which assistant should receive native rules? [claude]")
            if not sys.stdin.isatty():
                return 0
            apply_wizard_answers(args)
        return cmd_install(args)
    if args.command == "update":
        if args.update_command == "check":
            return cmd_update_check(args)
        if args.update_command == "plan":
            return cmd_update_plan(args)
        if args.update_command == "apply":
            return cmd_update_apply(args)
        if args.update_command == "rollback":
            return cmd_update_rollback(args)
        if args.update_command == "configure":
            return cmd_update_configure(args)
        raise CliError(f"Unknown update command: {args.update_command}")
    if args.command == "agents":
        return cmd_agents_list(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "compatibility":
        return cmd_compatibility(args)
    if args.command == "verify":
        return cmd_verify(args)
    if args.command in {"handoff", "new-feedback", "new-research"}:
        if args.command != "handoff" and not args.name:
            raise CliError(f"{args.command} requires a topic/symptom")
        return cmd_scaffold(args.command, args)
    if args.command == "secret-scan":
        return cmd_secret_scan(args)
    if args.command == "hook":
        return cmd_hook(args)
    if args.command == "evaluate":
        return cmd_evaluate(args)
    parser().print_help()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except CliError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(2)
