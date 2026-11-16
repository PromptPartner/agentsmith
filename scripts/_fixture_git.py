"""Keep test fixtures' Git commands in their own repositories (standard library only).

Hooks, `git rebase --exec` and wrappers export GIT_DIR, GIT_WORK_TREE and similar variables. A test
fixture that inherits them runs `git -C <temporary> init` or `commit` against that repository
instead of its own: one such run re-initialized a shared repository as bare. Every scripts/test-*
file calls isolate() before anything else; fixtures may also use clean_git_env() and run_git().
"""
from __future__ import annotations

import os
import subprocess
from typing import Any, Mapping

# `git rev-parse --local-env-vars`, plus the ref namespace. `git -c` overrides
# (GIT_CONFIG_KEY_n / GIT_CONFIG_VALUE_n) are dropped by prefix.
REPOSITORY_ENV = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
    "GIT_OBJECT_DIRECTORY", "GIT_DIR", "GIT_WORK_TREE", "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE",
    "GIT_INDEX_FILE", "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE", "GIT_PREFIX",
    "GIT_SHALLOW_FILE", "GIT_COMMON_DIR", "GIT_NAMESPACE",
)
_PREFIXES = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")


def _inherited(name: str) -> bool:
    upper = name.upper()
    return upper in REPOSITORY_ENV or upper.startswith(_PREFIXES)


def clean_git_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """A copy of `base` (default: os.environ) without inherited Git repository variables."""
    return {key: value for key, value in (os.environ if base is None else base).items() if not _inherited(key)}


def isolate() -> None:
    """Remove inherited Git repository variables from this process, so every child inherits a clean one."""
    for name in [name for name in os.environ if _inherited(name)]:
        del os.environ[name]


def run_git(args: list[str], *, env: Mapping[str, str] | None = None, **kwargs: Any) -> subprocess.CompletedProcess:
    """`git <args>` with a clean environment; other keyword arguments go to subprocess.run."""
    return subprocess.run(["git", *args], env=clean_git_env(env), **kwargs)
