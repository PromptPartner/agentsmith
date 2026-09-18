#!/usr/bin/env python3
"""Exercise the user-visible command and validate its expected negative result."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


root = Path(__file__).resolve().parent
result = subprocess.run(
    [sys.executable, str(root / "readiness.py"), str(root / "checks.json")],
    text=True,
    encoding="utf-8",
    errors="replace",
    capture_output=True,
    check=False,
)
if result.returncode != 1 or result.stdout != "NOT READY\n" or result.stderr:
    print(
        f"expected NOT READY with exit 1; got exit {result.returncode}, "
        f"stdout={result.stdout!r}, stderr={result.stderr!r}",
        file=sys.stderr,
    )
    raise SystemExit(1)
print("real command path correctly reported NOT READY")
