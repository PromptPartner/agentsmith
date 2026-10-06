"""Advisory, read-only audit of native agent configuration (standard library only).

Selected check categories inspired by ECC / AgentShield; implementation is original.
No configured command is executed and no server or transcript is accessed.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
import re
import shlex
from typing import Any
from urllib.parse import urlsplit, unquote

MAX_BYTES = 1024 * 1024
PROJECT_FILES = (
    '.claude/settings.json', '.claude/settings.local.json', '.claude/hooks.json',
    '.codex/config.toml', '.codex/hooks.json', '.mcp.json', '.claude/mcp.json',
    '.codex/mcp.json', 'AGENTS.md', 'CLAUDE.md', 'GEMINI.md',
    '.claude/CLAUDE.md', '.codex/AGENTS.md', '.github/copilot-instructions.md',
)
USER_FILES = (
    '.claude/settings.json', '.claude/settings.local.json', '.claude/hooks.json',
    '.claude/mcp.json', '.claude.json', '.codex/config.toml', '.codex/hooks.json',
    '.codex/AGENTS.md', '.claude/CLAUDE.md',
)
SEVERITIES = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}


def _safe(value: str) -> str:
    from agentsmith import redact_secret_text
    value = redact_secret_text(value)[0]
    # URL userinfo and bearer literals are credential shapes outside the shared detector.
    value = re.sub(r'(?i)([a-z][a-z0-9+.-]*://)[^/\s]+:[^/\s]+@', r'\1[REDACTED]@', value)
    value = re.sub(r'(?i)\bBearer\s+[^\s\"\',;]+', 'Bearer [REDACTED]', value)
    return ''.join(c for c in value if c in '\n\t' or (ord(c) >= 32 and not 127 <= ord(c) <= 159))


def _environment_reference(value: str) -> bool:
    return bool(re.fullmatch(r'\$\{[A-Za-z_][A-Za-z0-9_]*\}|\$[A-Za-z_][A-Za-z0-9_]*|\[REDACTED\]', value))


def _transport_credential(key: str, value: str) -> bool:
    if key.casefold() in {'authorization', 'proxy-authorization'}:
        match = re.fullmatch(r'(?i)Bearer\s+(.+)', value.strip())
        if match and not _environment_reference(match.group(1)):
            return True
    if re.match(r'(?i)^[a-z][a-z0-9+.-]*://', value):
        password = urlsplit(value).password
        if password and not _environment_reference(unquote(password)):
            return True
    return False


def _walk(value: Any, location: str = '$'):
    yield location, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, f'{location}.{key}')
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f'{location}[{index}]')


def _shell_commands(command: str, depth: int = 0) -> list[list[str]]:
    """Identify simple command positions; quoted diagnostic text stays an argument.

    This is a bounded static recognizer, not a shell execution model.
    """
    if depth > 4:
        raise ValueError('shell wrapper nesting exceeds inspection limit')
    lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|')
    lexer.whitespace_split = True
    groups: list[list[str]] = [[]]
    for token in lexer:
        if token and all(character in ';&|' for character in token):
            groups.append([])
        else:
            groups[-1].append(token)
    commands = []
    for tokens in groups:
        while tokens and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', tokens[0]):
            tokens = tokens[1:]
        if not tokens:
            continue
        if Path(tokens[0]).name == 'env':
            tokens = tokens[1:]
            while tokens and (tokens[0].startswith('-') or re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', tokens[0])):
                tokens = tokens[1:]
            if not tokens:
                continue
        executable = Path(tokens[0]).name.casefold()
        if executable in {'sh', 'bash', 'zsh', 'dash', 'ksh', 'powershell', 'pwsh', 'cmd', 'cmd.exe'}:
            for i, flag in enumerate(tokens[1:], 1):
                if (flag.casefold() in {'-command', '/c'} or re.fullmatch(r'-[a-z]*c[a-z]*', flag)) and i + 1 < len(tokens):
                    commands.extend(_shell_commands(tokens[i + 1], depth + 1))
                    break
            else:
                commands.append(tokens)
        else:
            commands.append(tokens)
    return commands


def _download_execute(command: str) -> bool:
    downloaded = False
    for tokens in _shell_commands(command):
        executable = Path(tokens[0]).name.casefold()
        if executable in {'curl', 'wget', 'invoke-webrequest', 'iwr'}:
            downloaded = True
        elif downloaded and (executable in {'bash', 'sh', 'zsh', 'dash', 'ksh', 'iex', 'invoke-expression'} or re.fullmatch(r'python[0-9.]*', executable)):
            return True
    return False


def _unpinned(command: str, depth: int = 0) -> bool:
    for tokens in _shell_commands(command, depth):
        launcher = Path(tokens[0]).name
        if launcher not in {'npx', 'npx.cmd', 'uvx'}:
            continue
        tail = tokens[1:]
        packages = []
        explicit = False
        cursor = 0
        while cursor < len(tail):
            arg = tail[cursor]
            if arg in {'--package', '-p', '--from'}:
                if cursor + 1 >= len(tail):
                    return True
                packages.append(tail[cursor + 1])
                explicit = True
                cursor += 2
                continue
            if arg.startswith(('--package=', '--from=')):
                packages.append(arg.split('=', 1)[1])
                explicit = True
                cursor += 1
                continue
            # Options with dependencies/values cannot safely be guessed.
            if arg in {'--with', '--with-editable', '--with-requirements'}:
                return True
            if not arg.startswith('-'):
                if not explicit:
                    packages.append(arg)
                break
            cursor += 1
        if not packages:
            return True
        # Exact numeric versions only; tags and ranges remain mutable.
        if any(not re.search(r'(?:@|==)\d+\.\d+(?:\.\d+)?(?:[-+][A-Za-z0-9.-]+)?$', package) for package in packages):
            return True
    return False


def _read_bounded(base: Path, name: str) -> bytes:
    """Pin each directory descriptor and refuse links/races on POSIX."""
    if os.open in os.supports_dir_fd and hasattr(os, 'O_NOFOLLOW'):
        descriptor = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            parts = Path(name).parts
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            file_descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0), dir_fd=descriptor)
            with os.fdopen(file_descriptor, 'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError('configuration is not a regular file')
                return stream.read(MAX_BYTES + 1)
        finally:
            os.close(descriptor)
    # A platform without descriptor-relative no-follow cannot promise safe reads.
    raise NotImplementedError('Safe descriptor-relative reads are unsupported on this platform')


def _schema_check(data: Any) -> None:
    if not isinstance(data, dict):
        raise ValueError('configuration must be an object/table')
    for location, value in _walk(data):
        key = location.rsplit('.', 1)[-1]
        if key in {'hooks', 'mcpServers', 'mcp_servers', 'permissions'} and not isinstance(value, (dict, list) if key == 'hooks' and '[' in location else dict):
            raise ValueError(f'{location} must be an object/table')
        if key == 'command' and (not isinstance(value, (str, list)) or (isinstance(value, list) and not all(isinstance(x, str) for x in value))):
            raise ValueError(f'{location} command must be text or argv')
        if key == 'args' and (not isinstance(value, list) or not all(isinstance(x, str) for x in value)):
            raise ValueError(f'{location} args must be a list of strings')
        if key in {'defaultMode', 'permissionMode', 'defaultPermissionMode', 'approval_policy', 'sandbox_mode'} and not isinstance(value, str):
            raise ValueError(f'{location} permission setting must be text')
        if key in {'allow', 'deny', 'ask'} and '.permissions.' in location and (not isinstance(value, list) or not all(isinstance(x, str) for x in value)):
            raise ValueError(f'{location} permission rules must be a list of strings')
        if key == 'hooks' and isinstance(value, list):
            if not all(isinstance(x, dict) for x in value):
                raise ValueError(f'{location} hook handlers must be objects')
            for handler in value:
                if not isinstance(handler.get('type'), str):
                    raise ValueError(f'{location} hook handler needs a type')
                if handler['type'] == 'command' and 'command' not in handler:
                    raise ValueError(f'{location} command hook needs a command')
        if key == 'hooks' and isinstance(value, dict):
            for handlers in value.values():
                if not isinstance(handlers, list) or not all(isinstance(x, dict) for x in handlers):
                    raise ValueError(f'{location} event handlers must be lists')
                if not all(isinstance(h.get('hooks'), list) for h in handlers):
                    raise ValueError(f'{location} event handler needs a hooks list')


def audit_config(root: Path | str, *, include_user: bool = False,
                 user_home: Path | str | None = None) -> dict[str, Any]:
    """Return a versioned report. Missing known files are recorded, not errors."""
    from agentsmith import redact_secret_text
    root = Path(root).resolve()
    report: dict[str, Any] = {'schema_version': 1, 'complete': True,
        'scope': 'project-and-user' if include_user else 'project',
        'inspected': [], 'unsupported': [], 'unreadable': [], 'absent': [],
        'findings': [], 'advisory': True,
        'limitations': ['Static selected configuration checks only; no containment claim.',
                        'No commands executed, MCP servers contacted, transcripts scanned, or files changed.']}
    if not root.is_dir():
        report['unreadable'].append({'path': '.', 'reason': 'Project root does not exist or is not a directory', 'error_type': 'InvalidRoot'})
        report['complete'] = False
        return report
    candidates = [(root, name, name) for name in PROJECT_FILES]
    if include_user:
        home = Path(user_home) if user_home is not None else Path.home()
        candidates.extend((home.resolve(), name, f'~/{name}') for name in USER_FILES if not (name.startswith('.codex/') and os.environ.get('CODEX_HOME') and user_home is None))
        if os.environ.get('CODEX_HOME') and user_home is None:
            codex_home = Path(os.environ['CODEX_HOME']).expanduser().resolve()
            candidates.extend((codex_home, name, f'$CODEX_HOME/{name}') for name in ('config.toml', 'hooks.json', 'AGENTS.md'))
    def finding(rule, severity, path, location, message, remediation):
        record = {'rule_id': rule, 'severity': severity, 'path': _safe(path),
                  'location': _safe(location), 'message': _safe(message),
                  'remediation': remediation}
        if record not in report['findings']:
            report['findings'].append(record)
    for base, name, display in candidates:
        path = base / name
        record = {'path': _safe(display)}
        try:
            # Opening discovery verifies directory readability even if all files appear absent.
            with os.scandir(base):
                pass
            if any((base / Path(*Path(name).parts[:i])).is_symlink() for i in range(1, len(Path(name).parts) + 1)):
                raise ValueError('symbolic links are not inspected')
            if not path.exists():
                report['absent'].append(record)
                continue
            raw = _read_bounded(base, name)
            if len(raw) > MAX_BYTES:
                raise ValueError('configuration exceeds 1 MiB inspection limit')
            text = raw.decode('utf-8')
            data = None
            if path.suffix == '.json':
                def no_duplicates(pairs):
                    result = {}
                    for key, value in pairs:
                        if key in result:
                            raise ValueError('duplicate JSON key')
                        result[key] = value
                    return result
                data = json.loads(text, object_pairs_hook=no_duplicates)
            elif path.suffix == '.toml':
                try:
                    import tomllib
                except ImportError:
                    report['unsupported'].append({**record, 'reason': 'TOML requires Python 3.11 or newer'})
                    report['complete'] = False
                    continue
                data = tomllib.loads(text)
            if data is not None:
                _schema_check(data)
            report['inspected'].append({**record, 'format': path.suffix.lstrip('.')})
            if data is not None:
                for location, value in _walk(data):
                    if isinstance(value, list) and location.endswith('.hooks'):
                        for handler in value:
                            if handler.get('type') != 'command':
                                report['unsupported'].append({**record, 'location': _safe(location), 'reason': 'Non-command hook type is outside the initial static execution checks'})
                                report['complete'] = False
            for number, line in enumerate(text.splitlines(), 1):
                # Environment references carry no live credential.
                sanitized = re.sub(r'\$\{[^}\n]+\}|\$[A-Za-z_][A-Za-z0-9_]*', '[ENV]', line)
                _, categories = redact_secret_text(sanitized)
                if categories:
                    finding('credential-exposed', 'high', display, f'line:{number}',
                            'Potential credential: ' + ', '.join(categories),
                            'Move credentials to an untracked environment or secret manager; rotate exposed live values.')
            if data is None:
                continue
            for location, value in _walk(data):
                key = location.rsplit('.', 1)[-1]
                if isinstance(value, str) and (_transport_credential(key, value) or (re.search(r'(?:password|secret|token|api[_-]?key)$', key, re.I) and len(value) >= 8 and not _environment_reference(value))):
                    finding('credential-exposed', 'high', display, location, 'Potential credential in configuration field.', 'Move credentials to an untracked environment or secret manager; rotate exposed live values.')
                if key in {'defaultMode', 'permissionMode', 'defaultPermissionMode'} and value == 'bypassPermissions':
                    finding('permission-bypass', 'high', display, location, 'Permission checks are bypassed (may be intentional trusted mode).', 'Review trusted-mode intent and use a narrower permission mode where appropriate.')
                if (key == 'sandbox_mode' and value == 'danger-full-access') or (key in {'dangerouslySkipPermissions', 'dangerously_skip_permissions'} and value is True):
                    finding('trusted-mode', 'high', display, location, 'Intentional trusted mode: containment or permission checks are disabled.', 'Confirm trusted-mode intent; use workspace isolation or a narrower sandbox when required.')
                if key == 'approval_policy' and value == 'never':
                    finding('permission-bypass', 'medium', display, location, 'Approval prompts are disabled; sandbox settings still apply.', 'Review the approval policy together with sandbox_mode.')
                if '.allow[' in location and isinstance(value, str) and re.fullmatch(r'\*|(?:Bash|Shell|Exec)(?:\(\*\)|\(:\*\))?', value, re.I):
                    finding('shell-permission-broad', 'high', display, location, 'Shell permission allows arbitrary commands.', 'Replace broad shell grants with the reviewed commands actually needed.')
                if isinstance(value, dict) and 'command' in value and ('.hooks' in location or 'mcpServers' in location or 'mcp_servers' in location or name.endswith('hooks.json')):
                    cmd = value['command']
                    if isinstance(cmd, list):
                        cmd = shlex.join(cmd)
                    args = value.get('args', [])
                    command = cmd + (' ' + shlex.join(args) if args else '')
                    if _download_execute(command):
                        finding('download-execute', 'high', display, location, 'Launcher matches a static download-and-execute command pattern.', 'Fetch and inspect separately; use a reviewed local executable or verify an immutable digest.')
                    if _unpinned(command):
                        finding('package-unpinned', 'medium', display, location, 'Package launcher matches a static unpinned-package pattern.', 'Pin the reviewed package to an exact version and review its provenance.')
        except NotImplementedError:
            report['unsupported'].append({**record, 'reason': 'Safe descriptor-relative no-follow reads unavailable on this platform'})
            report['complete'] = False
        except (OSError, ValueError, TypeError, UnicodeError, RecursionError) as exc:
            # Do not print exception text: parse errors can contain source values.
            report['unreadable'].append({**record, 'reason': 'Unsafe, malformed, oversized, or unreadable configuration', 'error_type': type(exc).__name__})
            report['complete'] = False
    return report


def exit_code(report: dict[str, Any], fail_on: str | None = None) -> int:
    if not report['complete']:
        return 2
    if fail_on and any(SEVERITIES[f['severity']] >= SEVERITIES[fail_on] for f in report['findings']):
        return 1
    return 0


def render_text(report: dict[str, Any]) -> str:
    lines = [f"Configuration audit: {'complete' if report['complete'] else 'INCOMPLETE'} ({report['scope']}; advisory)",
             f"Inspected {len(report['inspected'])}; unsupported {len(report['unsupported'])}; unreadable {len(report['unreadable'])}; findings {len(report['findings'])}."]
    for f in report['findings']:
        lines.extend([f"[{f['severity']}] {f['rule_id']} {f['path']}:{f['location']}: {f['message']}", f"  Remediation: {f['remediation']}"])
    for status in ('unsupported', 'unreadable'):
        for item in report[status]:
            lines.append(f"{status}: {item['path']}: {item['reason']}")
    lines.extend(report['limitations'])
    return '\n'.join(lines) + '\n'
