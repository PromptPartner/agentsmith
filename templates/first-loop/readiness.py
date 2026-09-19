#!/usr/bin/env python3
"""Small dependency-free launch-readiness checker with one intentional defect."""

from __future__ import annotations

import json
from pathlib import Path
import sys


def is_ready(checks: dict[str, bool]) -> bool:
    # Intentional baseline defect for the guided exercise: one passing check is not enough.
    return any(checks.values())


def main(argv: list[str] | None = None) -> int:
    arguments = list(argv if argv is not None else sys.argv[1:])
    if len(arguments) != 1:
        print("usage: readiness.py CHECKS.json", file=sys.stderr)
        return 2
    checks = json.loads(Path(arguments[0]).read_text(encoding="utf-8"))
    ready = is_ready(checks)
    print("READY" if ready else "NOT READY")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
