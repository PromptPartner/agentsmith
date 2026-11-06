"""Risk map: the tier of a commit range, from a committed path policy (standard library only).

The policy is read at the base commit, so a candidate cannot relax the policy that classifies it.
A fixed floor of always-human paths is checked here, not in the policy, so no policy can remove
it. Every changed path counts, and a rename or copy counts by its old and its new path.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable

SCHEMA_VERSION = 1
POLICY_PATH = ".harness/risk-policy.json"
# Lowest to highest. "human" is above every policy tier: the operator reviews the change in person.
TIERS = ("A", "B", "C", "human")
LENS_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
MAX_POLICY_BYTES = 256 * 1024
# `git rev-parse --local-env-vars`: settings that point Git at a repository other than --target.
REPOSITORY_ENV = frozenset({
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
    "GIT_OBJECT_DIRECTORY", "GIT_DIR", "GIT_WORK_TREE", "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE",
    "GIT_INDEX_FILE", "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE", "GIT_PREFIX",
    "GIT_SHALLOW_FILE", "GIT_COMMON_DIR"})

# The floor. Names compare ignoring case, because macOS and Windows open `claude.md` for
# `CLAUDE.md`. Agent instructions count at any depth, as the autonomous-run controller treats them.
AGENT_INSTRUCTION_FILES = frozenset({"agents.md", "agents.override.md", "claude.md",
                                     "claude.local.md", "gemini.md"})
AGENT_CONFIGURATION_FOLDERS = frozenset({".claude", ".codex", ".agents", ".cursor"})
HARNESS_FOLDERS = frozenset({".harness", ".agentsmith"})
HARNESS_FILES = frozenset({"agentsmith.py", "scripts/autonomous-run.py", "native_launcher.py",
                           "work_graph.py", "windows_verifier_sandbox.py", "risk_map.py"})


class PolicyError(ValueError):
    """The policy file at the base commit is not a valid policy."""


class RiskError(RuntimeError):
    """The commit range cannot be read."""


def _fold(path: str) -> str:
    """The spelling rules compare: case folded, and trailing dots and spaces dropped from each name,
    because macOS and Windows open `claude.md` for `CLAUDE.md` and Windows opens `AGENTS.md.` for
    `AGENTS.md`."""
    return "/".join(part.rstrip(". ") for part in path.casefold().split("/"))


def floor_reasons(path: str) -> list[str]:
    """Return the floor categories a repository-relative path falls in."""
    folded = _fold(path)
    parts = folded.split("/")
    name = parts[-1]
    reasons = []
    if name in AGENT_INSTRUCTION_FILES or any(part in AGENT_CONFIGURATION_FOLDERS for part in parts):
        reasons.append("floor:agent-instructions")
    # Folder rules cover the folder's own entry too: a submodule or symlink can sit at that path.
    if folded in (".github/workflows", ".github/actions") or folded.startswith((".github/workflows/", ".github/actions/")) \
            or name == "codeowners":
        reasons.append("floor:ci")
    if parts[0] in HARNESS_FOLDERS or folded in HARNESS_FILES or folded.startswith("scripts/verify"):
        reasons.append("floor:harness")
    if (name.startswith((".env", "id_")) or name.endswith((".pem", "_key"))
            or "secrets" in parts):
        reasons.append("floor:credentials")
    if "migrations" in parts:
        reasons.append("floor:migrations")
    return reasons


def _wildcard(pattern: list[str] | str, items: list[str] | str, star: str,
              same: Any) -> bool:
    """Greedy two-pointer wildcard match: at most len(pattern) * len(items) steps, never exponential.
    `star` matches any run of items; every other token must be `same` as exactly one item."""
    p = i = 0
    star_at, resume = -1, 0
    while i < len(items):
        if p < len(pattern) and pattern[p] == star:
            star_at, resume = p, i
            p += 1
        elif p < len(pattern) and same(pattern[p], items[i]):
            p += 1
            i += 1
        elif star_at >= 0:
            p, resume = star_at + 1, resume + 1
            i = resume
        else:
            return False
    while p < len(pattern) and pattern[p] == star:
        p += 1
    return p == len(pattern)


def _segment(pattern: str, name: str) -> bool:
    # `*` is any run of characters inside one folder name, `?` exactly one character.
    return _wildcard(pattern, name, "*", lambda token, char: token == "?" or token == char)


def _compile(pattern: str) -> list[str]:
    return pattern.casefold().split("/")


def _matches(segments: list[str], path: str) -> bool:
    # `**` is any run of whole folders, including none: `docs/**` covers `docs` itself.
    return _wildcard(segments, path.split("/"), "**", _segment)


def glob_match(pattern: str, path: str) -> bool:
    """Root-anchored glob match, ignoring case: `*` and `?` stay in one folder, `**` crosses folders."""
    return _matches(_compile(pattern), _fold(path))


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise PolicyError("duplicate key in policy")
    return dict(pairs)


def load_policy(data: bytes | None) -> dict[str, Any]:
    """Validate policy bytes. None (no policy at the base commit) gives a policy with no rules."""
    if data is None:
        return {"rules": []}
    if len(data) > MAX_POLICY_BYTES:
        raise PolicyError("policy is larger than 256 KiB")
    try:
        policy = json.loads(data.decode("utf-8"), object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PolicyError(f"policy is not valid JSON: {exc}") from None
    if not isinstance(policy, dict) or set(policy) != {"schema_version", "rules"}:
        raise PolicyError("policy must be an object with exactly schema_version and rules")
    if type(policy["schema_version"]) is not int or policy["schema_version"] != SCHEMA_VERSION \
            or not isinstance(policy["rules"], list):
        raise PolicyError(f"policy needs schema_version {SCHEMA_VERSION} and a rules array")
    rules = []
    for number, rule in enumerate(policy["rules"], start=1):
        where = f"rule {number}"
        if not isinstance(rule, dict) or not {"paths", "tier"} <= set(rule) <= {"paths", "tier", "lenses"}:
            raise PolicyError(f"{where} must have paths and tier, and optionally lenses")
        if rule["tier"] not in TIERS:
            raise PolicyError(f"{where}: tier must be one of {', '.join(TIERS)}")
        paths, lenses = rule["paths"], rule.get("lenses", [])
        if not isinstance(paths, list) or not paths or not all(
                isinstance(path, str) and path and not path.startswith("/") and "\\" not in path
                and "" not in path.split("/") for path in paths):
            raise PolicyError(f"{where}: paths must be relative globs with '/' separators")
        if not isinstance(lenses, list) or not all(isinstance(lens, str) and LENS_ID.fullmatch(lens)
                                                   for lens in lenses):
            raise PolicyError(f"{where}: lenses must be lowercase ids such as 'security'")
        rules.append({"id": f"rule:{number}", "patterns": [_compile(path) for path in paths], "tier": rule["tier"],
                      "lenses": sorted(set(lenses))})
    return {"rules": rules}


def raise_tier(recorded: str, proposed: str) -> str:
    """Return the higher tier: a reviewer can raise a recorded tier, never lower it."""
    if recorded not in TIERS or proposed not in TIERS:
        raise ValueError(f"tier must be one of {', '.join(TIERS)}")
    return max(recorded, proposed, key=TIERS.index)


def classify_path(path: str, policy: dict[str, Any], kinds: Iterable[str] = ()) -> dict[str, Any]:
    """Classify one path. `kinds` names special entries on either side of the change (symlink,
    submodule): their effect lies outside the diff, a link's target or another repository, so they
    are at least C, a change the operator reviews every time."""
    folded = _fold(path)
    # A name that is not UTF-8 cannot be matched reliably, so no rule may lower it.
    floor = (["unreadable-name"] if _unreadable(path) else []) + floor_reasons(path)
    special = [f"type:{kind}" for kind in sorted(set(kinds))]
    hits = [rule for rule in policy["rules"] if any(_matches(pattern, folded) for pattern in rule["patterns"])]
    tier = "human" if floor or not hits else "C" if special else "A"
    lenses: set[str] = set()
    for rule in hits:
        tier = raise_tier(tier, rule["tier"])
        lenses.update(rule["lenses"])
    matched = floor + special + [rule["id"] for rule in hits] + ([] if floor or hits else ["unmatched"])
    return {"path": path, "tier": tier, "lenses": sorted(lenses), "matched": matched}


def classify(paths: Iterable[str] | dict[str, list[str]], policy: dict[str, Any]) -> dict[str, Any]:
    """Pure classification of paths, or of {path: entry kinds}. An empty change is human: nothing
    was classified."""
    kinds = paths if isinstance(paths, dict) else {path: [] for path in paths}
    rows = [classify_path(path, policy, kinds[path]) for path in sorted(kinds)]
    tier = "human" if not rows else "A"
    for row in rows:
        tier = raise_tier(tier, row["tier"])
    return {"tier": tier, "lenses": sorted({lens for row in rows for lens in row["lenses"]}), "paths": rows}


def _decode(raw: bytes) -> str:
    # Bytes that are not UTF-8 become lone surrogates (U+DC80-U+DCFF), which classify_path makes
    # human and the JSON shows as \udcXX escapes.
    return raw.decode("utf-8", "surrogateescape")


def _unreadable(path: str) -> bool:
    return any("\udc80" <= char <= "\udcff" for char in path)


ENTRY_KINDS = {b"120000": "symlink", b"160000": "submodule"}


def parse_raw(raw: bytes) -> dict[str, list[str]]:
    """Parse `git diff-tree -z --raw` output into {path: special entry kinds}, naming every path,
    old and new. A rename or copy gives each path the kind of its own side."""
    fields = raw.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    paths: dict[str, set[str]] = {}
    index = 0
    while index < len(fields):
        header = fields[index].split(b" ")
        if len(header) != 5 or not header[0].startswith(b":") or not header[4]:
            raise RiskError("unexpected git diff output")
        old_mode, new_mode, status = header[0][1:], header[1], header[4][:1]
        count = 2 if status in (b"R", b"C") else 1
        named = fields[index + 1:index + 1 + count]
        if len(named) != count:
            raise RiskError("unexpected git diff output")
        sides = [(named[0], (old_mode,)), (named[1], (new_mode,))] if count == 2 else [(named[0], (old_mode, new_mode))]
        for path, modes in sides:
            paths.setdefault(_decode(path), set()).update(ENTRY_KINDS[mode] for mode in modes if mode in ENTRY_KINDS)
        index += 1 + count
    return {path: sorted(kinds) for path, kinds in sorted(paths.items())}


def _git(repo: Path, *args: str) -> bytes:
    # Hooks and `rebase --exec` export GIT_DIR and friends; they would redirect `-C repo`.
    env = {key: value for key, value in os.environ.items() if key not in REPOSITORY_ENV}
    try:
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, timeout=60, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RiskError(f"git failed: {exc}") from None
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip().splitlines()
        raise RiskError(f"git {args[0]} failed: {detail[-1] if detail else 'exit ' + str(result.returncode)}")
    return result.stdout


def _commit(repo: Path, ref: str) -> str:
    if not ref or ref.startswith("-"):
        raise RiskError(f"not a commit: {ref!r}")
    try:
        return _git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}").decode("ascii").strip()
    except RiskError:
        raise RiskError(f"not a commit: {ref!r}") from None


def _policy_at(repo: Path, base_id: str) -> tuple[dict[str, Any], str | None]:
    listing = _git(repo, "ls-tree", "-z", "--full-tree", base_id, "--", POLICY_PATH)
    blob = None
    data = None
    if listing:
        mode_type_id = listing.split(b"\t", 1)[0].split()
        # A symlink is a blob too (mode 120000); only a regular file is a policy.
        if len(mode_type_id) != 3 or not mode_type_id[0].startswith(b"100") or mode_type_id[1] != b"blob":
            raise PolicyError(f"{POLICY_PATH} at the base commit is not a regular file")
        blob = mode_type_id[2].decode("ascii")
        data = _git(repo, "cat-file", "blob", blob)
    try:
        return load_policy(data), blob
    except PolicyError as exc:
        raise PolicyError(f"{POLICY_PATH} at {base_id[:12]}: {exc}") from None


# Plumbing ignores most user diff configuration. -M and -C pair renames and copies so both paths
# are reported; --find-copies-harder also checks unmodified files as copy sources, and -l0 stops a
# configured rename limit from silently skipping that search.
DIFF_TREE = ("diff-tree", "-r", "-z", "-M", "-C", "--find-copies-harder", "-l0", "--no-commit-id", "--raw")


def classify_range(repo: Path, base: str, head: str) -> dict[str, Any]:
    """Classify base..head with the policy as committed at base."""
    base_id, head_id = _commit(repo, base), _commit(repo, head)
    policy, blob = _policy_at(repo, base_id)
    report = classify(parse_raw(_git(repo, *DIFF_TREE, base_id, head_id)), policy)
    return {"schema_version": SCHEMA_VERSION, "base": base_id, "head": head_id,
            "policy": {"path": POLICY_PATH, "blob": blob}, **report}


def classify_history(repo: Path, base: str, head: str) -> dict[str, Any]:
    """Classify every path that any commit in base..head touches, with the endpoint diff, under
    the policy at base. Pushing head publishes each of those commits, so a path added and removed
    again still counts. A merge counts its changes against each parent."""
    base_id, head_id = _commit(repo, base), _commit(repo, head)
    policy, blob = _policy_at(repo, base_id)
    paths = parse_raw(_git(repo, *DIFF_TREE, base_id, head_id))
    commits = _git(repo, "rev-list", f"{base_id}..{head_id}").decode("ascii").split()
    for commit in commits:
        for path, kinds in parse_raw(_git(repo, *DIFF_TREE, "-m", "--root", commit)).items():
            paths[path] = sorted(set(paths.get(path, [])) | set(kinds))
    report = classify(paths, policy)
    return {"schema_version": SCHEMA_VERSION, "base": base_id, "head": head_id,
            "policy": {"path": POLICY_PATH, "blob": blob}, **report}


def to_json(report: dict[str, Any]) -> str:
    """ASCII, sorted keys: byte-identical on every host and console encoding."""
    return json.dumps(report, sort_keys=True, ensure_ascii=True) + "\n"


def render_text(report: dict[str, Any]) -> str:
    lines = [f"tier: {report['tier']}", f"lenses: {', '.join(report['lenses']) or 'none'}",
             f"policy: {report['policy']['path']} at {report['base'][:12]}"
             + ("" if report["policy"]["blob"] else " (absent: every path is human)")]
    for row in report["paths"]:
        lenses = f" [{', '.join(row['lenses'])}]" if row["lenses"] else ""
        lines.append(f"  {row['tier']:<5} {row['path']}{lenses}  ({', '.join(row['matched'])})")
    if not report["paths"]:
        lines.append("  (no changed paths: human)")
    return "\n".join(lines) + "\n"
