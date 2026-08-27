#!/usr/bin/env python3
"""Render AgentSmith's dependency-free Claude Code status line."""

from __future__ import annotations

import getpass
import json
import math
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
from typing import Any


SESSION_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def percentage(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and 0 <= number <= 100 else None


def clean_segment(value: Any) -> str:
    return CONTROL_CHARACTERS.sub("?", str(value))


def write_signal(session_id: str, used: float) -> None:
    directory = Path(tempfile.gettempdir())
    temporary: Path | None = None
    try:
        descriptor, raw_path = tempfile.mkstemp(prefix=".agentsmith-status-", dir=directory)
        temporary = Path(raw_path)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"{used:g}")
        temporary.replace(directory / f"claude-ctx-{session_id}.pct")
        temporary = None
    except OSError:
        pass
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    cwd = nested(payload, "workspace", "current_dir") or payload.get("cwd") or os.getcwd()
    model = nested(payload, "model", "display_name") or nested(payload, "model", "id") or ""
    used = percentage(nested(payload, "context_window", "used_percentage"))
    session_id = payload.get("session_id")
    if isinstance(session_id, str) and SESSION_ID.fullmatch(session_id) and used is not None:
        write_signal(session_id, used)

    try:
        user = getpass.getuser()
    except (OSError, KeyError):
        user = "user"
    try:
        host = socket.gethostname().split(".", 1)[0]
    except OSError:
        host = "host"
    parts = [f"{clean_segment(user)}@{clean_segment(host)}:{clean_segment(cwd)}"]
    if model:
        parts.append(clean_segment(model))
    if used is not None:
        parts.append(f"ctx:{used:.0f}%")
    print("  ".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
