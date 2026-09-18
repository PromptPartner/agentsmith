#!/usr/bin/env python3
"""Regenerate the sanitized First Verified Loop public proof from a clean source copy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
FIXED_GIT_DATE = "2026-09-18T09:00:00+00:00"


class ProofError(RuntimeError):
    pass


def run(
    arguments: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    expected: set[int] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        arguments,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    allowed = expected if expected is not None else {0}
    if result.returncode not in allowed:
        command = shlex.join(arguments) if os.name != "nt" else subprocess.list2cmdline(arguments)
        raise ProofError(
            f"command failed ({result.returncode}, expected {sorted(allowed)}): {command}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def isolated_environment(home: Path, codex_home: Path | None = None) -> dict[str, str]:
    selected_codex_home = codex_home or home / ".codex"
    selected_codex_home.mkdir(parents=True, exist_ok=True)
    claude_home = home / ".claude"
    claude_home.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith(("GIT_", "PYTHON")):
            environment.pop(key)
    environment.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "CODEX_HOME": str(selected_codex_home),
            "CLAUDE_CONFIG_DIR": str(claude_home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_DATA_HOME": str(home / ".local/share"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return environment


def copy_clean_source(destination: Path, environment: dict[str, str]) -> None:
    def ignored(directory: str, names: list[str]) -> set[str]:
        relative = Path(directory).resolve().relative_to(ROOT.resolve())
        blocked = {".git", "__pycache__", ".pytest_cache", ".DS_Store"}
        if relative == Path(".harness"):
            blocked.update({"handoffs", "evidence", "receipts"})
        if relative == Path("docs/demos"):
            blocked.add("first-verified-loop")
            blocked.update(name for name in names if name.startswith("agentsmith-fvl07-output-"))
        return set(names) & blocked

    shutil.copytree(ROOT, destination, symlinks=True, ignore=ignored)
    git_env = environment.copy()
    git_env.update(
        {
            "GIT_AUTHOR_DATE": FIXED_GIT_DATE,
            "GIT_COMMITTER_DATE": FIXED_GIT_DATE,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    run(["git", "init", "-q"], cwd=destination, env=git_env)
    run(["git", "checkout", "-qb", "proof/source"], cwd=destination, env=git_env)
    run(["git", "config", "user.name", "AgentSmith Proof Fixture"], cwd=destination, env=git_env)
    run(["git", "config", "user.email", "proof@example.com"], cwd=destination, env=git_env)
    run(["git", "add", "-A"], cwd=destination, env=git_env)
    run(["git", "commit", "-qm", "clean proof source"], cwd=destination, env=git_env)
    status = run(["git", "status", "--porcelain=v1"], cwd=destination, env=git_env)
    if status.stdout:
        raise ProofError("temporary proof source is not clean")


def file_snapshot(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


def normalize_text(text: str, replacements: dict[str, str]) -> str:
    for actual, replacement in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(actual, replacement)
        text = text.replace(actual.replace("\\", "/"), replacement)
        text = text.replace(actual.replace("/", "\\"), replacement)
    text = re.sub(r"(\$(?:SOURCE|DEMO|WORKSPACE|HOME))[/\\\\]+", r"\1/", text)
    text = re.sub(r'''["'](\$(?:SOURCE|DEMO|WORKSPACE|HOME))["']''', r"\1", text)
    text = re.sub(r"\b[0-9a-f]{40}\b", "<git-commit>", text)
    text = re.sub(r"\b\d{8}-\d{4}\b", "<handoff-time>", text)
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b", "<recorded-at>", text)
    text = re.sub(r"\bin \d+(?:\.\d+)?s\b", "in <elapsed>s", text)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def normalized_output_hash(path: Path, replacements: dict[str, str]) -> str:
    normalized = normalize_text(path.read_text(encoding="utf-8", errors="replace"), replacements)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_value(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"started_at", "finished_at", "recorded_at", "timestamp"}:
                normalized[key] = "<recorded-at>"
            elif key == "duration_seconds":
                normalized[key] = "<elapsed-seconds>"
            elif key in {"hostname", "platform"}:
                normalized[key] = f"<{key}>"
            else:
                normalized[key] = normalize_value(item, replacements)
        return normalized
    if isinstance(value, list):
        return [normalize_value(item, replacements) for item in value]
    if isinstance(value, str):
        return normalize_text(value, replacements)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    path.write_bytes(content.encode("utf-8"))


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((value.rstrip() + "\n").encode("utf-8"))


def command_artifact(label: str, result: subprocess.CompletedProcess[str], replacements: dict[str, str]) -> str:
    return normalize_text(
        f"$ {label}\n"
        f"exit: {result.returncode}\n"
        "--- stdout ---\n"
        f"{result.stdout.rstrip() or '<empty>'}\n"
        "--- stderr ---\n"
        f"{result.stderr.rstrip() or '<empty>'}\n",
        replacements,
    )


def git_fixture(project: Path, branch: str, environment: dict[str, str]) -> str:
    env = environment.copy()
    env.update(
        {
            "GIT_AUTHOR_DATE": FIXED_GIT_DATE,
            "GIT_COMMITTER_DATE": FIXED_GIT_DATE,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    run(["git", "init", "-q"], cwd=project, env=env)
    run(["git", "checkout", "-qb", branch], cwd=project, env=env)
    run(["git", "config", "user.name", "AgentSmith Proof Fixture"], cwd=project, env=env)
    run(["git", "config", "user.email", "proof@example.com"], cwd=project, env=env)
    run(["git", "add", "-A"], cwd=project, env=env)
    run(["git", "commit", "-qm", "intentional red baseline"], cwd=project, env=env)
    return run(["git", "rev-parse", "HEAD"], cwd=project, env=env).stdout.strip()


def build_loop_artifacts(source: Path, workspace: Path, output: Path) -> dict[str, str]:
    core = source / "agentsmith.py"
    demo = workspace / "demo"
    loop_home = workspace / "loop-home"
    environment = isolated_environment(loop_home)
    replacements = {
        str(source): "$SOURCE",
        str(source.resolve()): "$SOURCE",
        str(demo): "$DEMO",
        str(demo.resolve()): "$DEMO",
        str(workspace): "$WORKSPACE",
        str(workspace.resolve()): "$WORKSPACE",
        str(loop_home): "$HOME",
        str(loop_home.resolve()): "$HOME",
    }
    initialized = run(
        [sys.executable, str(core), "demo", "first-loop", "--target", str(demo)],
        cwd=source,
        env=environment,
    )
    baseline_commit = git_fixture(demo, "proof/first-loop", environment)

    status_result = run(
        [sys.executable, str(core), "status", "--target", str(demo), "--json"],
        cwd=source,
        env=environment,
    )
    status = normalize_value(json.loads(status_result.stdout), replacements)
    write_json(output / "artifacts/status.json", status)

    red = run(
        [sys.executable, str(core), "verify", "--target", str(demo)],
        cwd=source,
        env=environment,
        expected={1},
    )
    write_text(output / "artifacts/red.txt", command_artifact("agentsmith verify --target $DEMO", red, replacements))

    readiness = demo / "readiness.py"
    baseline = readiness.read_text(encoding="utf-8")
    if "return any(checks.values())" not in baseline:
        raise ProofError("demo baseline no longer contains the named bounded defect")
    readiness.write_text(baseline.replace("return any(checks.values())", "return all(checks.values())"), encoding="utf-8")

    green = run(
        [
            sys.executable,
            str(core),
            "verify",
            "--target",
            str(demo),
            "--record",
            ".harness/evidence/public-proof",
            "--tree-class",
            "disposable-fixture",
        ],
        cwd=source,
        env=environment,
    )
    write_text(
        output / "artifacts/green.txt",
        command_artifact(
            "agentsmith verify --target $DEMO --record .harness/evidence/public-proof "
            "--tree-class disposable-fixture",
            green,
            replacements,
        ),
    )
    receipt_path = demo / ".harness/evidence/public-proof/receipt.json"
    receipt = normalize_value(json.loads(receipt_path.read_text(encoding="utf-8")), replacements)
    for phase in receipt["phases"]:
        for stream, relative_path in phase["output_paths"].items():
            phase["output_hashes"][stream] = normalized_output_hash(
                receipt_path.parent / relative_path,
                replacements,
            )
    write_json(output / "artifacts/receipt.json", receipt)

    real_path = run(
        [sys.executable, "readiness.py", "checks.json"],
        cwd=demo,
        env=environment,
        expected={1},
    )
    write_text(
        output / "artifacts/real-path.txt",
        command_artifact("python3 readiness.py checks.json", real_path, replacements),
    )

    handed_off = run(
        [sys.executable, str(core), "handoff", "first-verified-loop", "--target", str(demo)],
        cwd=source,
        env=environment,
    )
    note = max((demo / ".harness/handoffs").glob("handoff-*.md"))
    dirty_count = len(
        run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=demo,
            env=environment,
        ).stdout.splitlines()
    )
    recovery = f"agentsmith status --target {shlex.quote(str(demo))}" if os.name != "nt" else (
        "agentsmith status --target " + subprocess.list2cmdline([str(demo)])
    )
    note.write_text(
        textwrap.dedent(
            f"""\
            # Handoff — first-verified-loop — 20260918-1200

            **Branch:** proof/first-loop   **HEAD:** {baseline_commit}   **Uncommitted files:** {dirty_count}

            ## Recovery checkpoint

            - **Exact objective:** Correct the failed readiness check and retain its evidence.
            - **Repository / worktree:** {demo}
            - **Protected-state hashes:** baseline commit {baseline_commit}
            - **Branch / commit:** proof/first-loop / {baseline_commit}
            - **External identifiers:** none
            - **Completed verification:** receipt .harness/evidence/public-proof/receipt.json passed all three phases
            - **Active external operation:** none
            - **Next read-only recovery command:** `{recovery}`
            - **Remaining authorized writes:** none
            - **Stop conditions:** stop before any Git or file mutation
            - **Skipped validation:** native operating-system matrix remains CI evidence

            ## What shipped this session

            The failed partial readiness check now reaches the visible command as NOT READY.

            ## What is still pending

            Independent review of the public demonstration.

            ## Deviations from the plan / decisions made (don't re-litigate)

            None.

            ## Exact next step

            Run the saved read-only status command.

            ## Gotchas a fresh session would otherwise re-derive

            The receipt and dirty readiness.py are intentional evidence from the bounded fix.

            ---
            ## Kickoff prompt for a fresh chat
            ```
            Resume the bounded readiness proof from this handoff. Inspect the receipt, then run only
            the saved read-only status command. Do not change Git or repository state.
            ```
            """
        ),
        encoding="utf-8",
    )
    resumed = run(
        [sys.executable, str(core), "resume", str(note), "--target", str(demo), "--json"],
        cwd=source,
        env=environment,
    )
    resume_payload = normalize_value(json.loads(resumed.stdout), replacements)
    write_json(output / "artifacts/resume.json", resume_payload)
    write_text(output / "artifacts/handoff.md", normalize_text(note.read_text(encoding="utf-8"), replacements))

    compatibility_result = run(
        [sys.executable, str(core), "compatibility", "--json"],
        cwd=source,
        env=environment,
    )
    compatibility = normalize_value(json.loads(compatibility_result.stdout), replacements)
    write_json(output / "artifacts/compatibility.json", compatibility)
    return {
        "demo_initialize": normalize_text(initialized.stdout + initialized.stderr, replacements),
        "handoff_command": normalize_text(handed_off.stdout + handed_off.stderr, replacements),
    }


def lifecycle_fixture(source: Path, workspace: Path, output: Path, *, existing: bool) -> None:
    core = source / "agentsmith.py"
    label = "existing" if existing else "clean"
    fixture_root = workspace / f"install-{label}"
    project = fixture_root / "project"
    home = fixture_root / "home"
    codex_home = home / ".codex"
    project.mkdir(parents=True)
    codex_home.mkdir(parents=True)
    foreign_project = "# Foreign project context\n\nKeep this exact project sentence.\n"
    foreign_client = '[foreign]\nvalue = "keep-this-client-setting"\n'
    if existing:
        (project / "AGENTS.md").write_text(foreign_project, encoding="utf-8")
        (codex_home / "config.toml").write_text(foreign_client, encoding="utf-8")

    env = isolated_environment(home, codex_home)
    arguments = [
        sys.executable,
        str(core),
        "install",
        "--agent",
        "codex",
        "--profile",
        "software-dev",
        "--safety",
        "cautious",
        "--operator-name",
        "Proof Operator",
        "--operator-role",
        "Evaluator",
        "--target",
        str(project),
    ]
    first = run(arguments, cwd=source, env=env)
    first_snapshot = {"project": file_snapshot(project), "client": file_snapshot(codex_home)}
    second = run(arguments, cwd=source, env=env)
    second_snapshot = {"project": file_snapshot(project), "client": file_snapshot(codex_home)}
    status = run([sys.executable, str(core), "status", "--target", str(project), "--json"], cwd=source, env=env)
    uninstall = run([*arguments, "--uninstall"], cwd=source, env=env)

    agents_path = project / "AGENTS.md"
    config_path = codex_home / "config.toml"
    agents_text = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    owned_project_instructions_removed = "BEGIN AGENTSMITH" not in agents_text
    foreign_project_exact = (not existing) or agents_text == foreign_project
    config_without_managed_safety = re.sub(
        r"\A# BEGIN AGENTSMITH MANAGED\n.*?# END AGENTSMITH MANAGED\n",
        "",
        config_text,
        count=1,
        flags=re.DOTALL,
    )
    foreign_client_prefix_exact = (not existing) or config_without_managed_safety == foreign_client
    value = {
        "schema_version": 1,
        "fixture": label,
        "source_tree_clean": True,
        "install_exit": first.returncode,
        "rerun_exit": second.returncode,
        "status_exit": status.returncode,
        "uninstall_exit": uninstall.returncode,
        "idempotent": first_snapshot == second_snapshot,
        "managed_project_instructions_removed": owned_project_instructions_removed,
        "runtime_scaffolding_retained": (project / ".agentsmith/agentsmith.py").is_file(),
        "client_safety_configuration_retained": "BEGIN AGENTSMITH" in config_text,
        "foreign_project_content_preserved": foreign_project_exact,
        "foreign_client_config_preserved": foreign_client_prefix_exact,
        "foreign_project_sha256": hashlib.sha256(foreign_project.encode()).hexdigest() if existing else None,
        "foreign_client_prefix_sha256": hashlib.sha256(foreign_client.encode()).hexdigest() if existing else None,
    }
    write_json(output / f"artifacts/install-{label}.json", value)


def write_documentation(output: Path, run_metadata: dict[str, str]) -> None:
    write_text(
        output / "README.md",
        """# First Verified Loop — public proof

This bundle is a reproducible, sanitized record of one bounded AgentSmith task. It follows the same
value from an intentional failing test through the corrected logic, all configured checks, the
visible command, a verification receipt, a durable handoff, and read-only resume.

Start with the [runbook](RUNBOOK.md), then inspect the [flow](FLOW.md),
[claim map](CLAIM-MAP.md), [security review](SECURITY-REVIEW.md),
[release-readiness boundary](RELEASE-READINESS.md), and [current limitations](LIMITATIONS.md).

## Evidence chain

1. [Read-only status and coverage](artifacts/status.json)
2. [Named red test](artifacts/red.txt)
3. [Green three-phase verification](artifacts/green.txt)
4. [Real command-path output](artifacts/real-path.txt)
5. [Verification receipt](artifacts/receipt.json)
6. [Handoff](artifacts/handoff.md) and [zero-drift resume](artifacts/resume.json)
7. [Clean installation lifecycle](artifacts/install-clean.json)
8. [Existing-config preservation lifecycle](artifacts/install-existing.json)
9. [Compatibility evidence snapshot](artifacts/compatibility.json)

All commands ran from a temporary clean Git copy of the current source. The checked-in artifacts are
normalized only as documented in [sanitization.json](sanitization.json); raw temporary paths and
timestamps are not public proof. Regenerate the bundle with:

```bash
python3 scripts/generate-first-loop-proof.py --output /tmp/agentsmith-first-loop-proof
```
""",
    )
    write_text(
        output / "RUNBOOK.md",
        """# Reproduction runbook

## Automated clean-room replay

From the AgentSmith repository root, choose a new output directory:

```bash
python3 scripts/generate-first-loop-proof.py --output /tmp/agentsmith-first-loop-proof
```

The generator copies the current source into a temporary directory, initializes and commits that
copy locally, asserts it is clean, and runs every recorded command from that copy. It creates no
remote, performs no network call, and deletes the raw workspace when finished.

Compare the regenerated directory with `docs/demos/first-verified-loop/`. The FVL-07 contract does
this byte-for-byte after normalizing the fields listed in `sanitization.json`.

## Manual command journey

The automated replay executes this sequence against a new `$DEMO` directory:

```text
agentsmith demo first-loop --target $DEMO
git init && git checkout -b proof/first-loop && git add -A && git commit
agentsmith status --target $DEMO --json
agentsmith verify --target $DEMO                         # named red test
# change only readiness.py: any(checks.values()) → all(checks.values())
agentsmith verify --target $DEMO --record .harness/evidence/public-proof \\
  --tree-class disposable-fixture
python3 readiness.py checks.json                         # NOT READY, exit 1
agentsmith handoff first-verified-loop --target $DEMO
agentsmith resume HANDOFF --target $DEMO --json
```

The lifecycle replay separately installs into a clean fixture and a fixture carrying foreign
project and Codex configuration, repeats each install byte-idempotently, reads status, uninstalls,
and verifies that owned markers are gone while foreign bytes remain.
""",
    )
    write_text(
        output / "FLOW.md",
        """# Architecture and evidence flow

![First Verified Loop flow from clean source through resume and lifecycle evidence](flow.svg)

The receipt proves deterministic configured checks. The real command exercises the user-visible
path. The handoff/resume pair proves continuity without changing Git or file state. Lifecycle
fixtures prove managed ownership and preservation boundaries, not behavior of every client version.
""",
    )
    write_text(
        output / "flow.svg",
        """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="430" viewBox="0 0 1200 430" role="img" aria-labelledby="title desc">
  <title id="title">First Verified Loop evidence flow</title>
  <desc id="desc">A clean source copy produces status, a named red test, a bounded fix, green verification, real-path evidence, a receipt, handoff, read-only resume, and installation lifecycle evidence.</desc>
  <defs>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#315a7d"/></marker>
    <style>.box{fill:#f4f8fb;stroke:#315a7d;stroke-width:2;rx:8}.label{font:600 14px sans-serif;fill:#183247;text-anchor:middle}.sub{font:12px sans-serif;fill:#46657c;text-anchor:middle}.edge{stroke:#315a7d;stroke-width:2;fill:none;marker-end:url(#arrow)}</style>
  </defs>
  <rect class="box" x="20" y="55" width="125" height="64"/><text class="label" x="82" y="82">Clean source</text><text class="sub" x="82" y="102">local commit</text>
  <rect class="box" x="170" y="55" width="125" height="64"/><text class="label" x="232" y="82">Status</text><text class="sub" x="232" y="102">coverage</text>
  <rect class="box" x="320" y="55" width="125" height="64"/><text class="label" x="382" y="82">Named red test</text><text class="sub" x="382" y="102">expected failure</text>
  <rect class="box" x="470" y="55" width="125" height="64"/><text class="label" x="532" y="82">Bounded fix</text><text class="sub" x="532" y="102">any → all</text>
  <rect class="box" x="620" y="55" width="125" height="64"/><text class="label" x="682" y="82">Green verify</text><text class="sub" x="682" y="102">three phases</text>
  <rect class="box" x="770" y="55" width="125" height="64"/><text class="label" x="832" y="82">Real path</text><text class="sub" x="832" y="102">NOT READY</text>
  <rect class="box" x="920" y="55" width="110" height="64"/><text class="label" x="975" y="82">Receipt</text><text class="sub" x="975" y="102">hashes + exits</text>
  <rect class="box" x="1055" y="55" width="125" height="64"/><text class="label" x="1117" y="82">Handoff</text><text class="sub" x="1117" y="102">durable state</text>
  <path class="edge" d="M145 87 H165"/><path class="edge" d="M295 87 H315"/><path class="edge" d="M445 87 H465"/><path class="edge" d="M595 87 H615"/><path class="edge" d="M745 87 H765"/><path class="edge" d="M895 87 H915"/><path class="edge" d="M1030 87 H1050"/>
  <rect class="box" x="990" y="180" width="190" height="70"/><text class="label" x="1085" y="208">Read-only resume</text><text class="sub" x="1085" y="230">ready + zero drift</text><path class="edge" d="M1117 119 V175"/>
  <rect class="box" x="185" y="300" width="230" height="72"/><text class="label" x="300" y="328">Clean install lifecycle</text><text class="sub" x="300" y="350">install · rerun · status · uninstall</text>
  <rect class="box" x="485" y="300" width="250" height="72"/><text class="label" x="610" y="328">Existing-config lifecycle</text><text class="sub" x="610" y="350">foreign bytes preserved</text>
  <rect class="box" x="805" y="300" width="190" height="72"/><text class="label" x="900" y="328">Claim map</text><text class="sub" x="900" y="350">proof + boundary</text>
  <path class="edge" d="M82 119 V270 H300 V295"/><path class="edge" d="M82 119 V270 H610 V295"/><path class="edge" d="M415 336 H480"/><path class="edge" d="M735 336 H800"/><path class="edge" d="M1085 250 V270 H900 V295"/>
</svg>""",
    )
    write_text(
        output / "CLAIM-MAP.md",
        """# Claim map

| Statement | Evidence | Support level | Boundary |
|---|---|---|---|
| One bounded task can retain an inspectable red → green → real-path → receipt → handoff chain. | `artifacts/red.txt` through `artifacts/resume.json` | Reproduced fixture evidence | Proves this dependency-free task, not universal correctness. |
| Status exposes configured verification coverage before work starts. | `artifacts/status.json` | Reproduced fixture evidence | Does not prove every repository detector is complete. |
| A recorded verification receipt binds three passing phases to the disposable fixture. | `artifacts/receipt.json` | Reproduced fixture evidence | Does not replace runtime, visual, or human evaluation evidence. |
| Project installation is repeatable and its managed instruction block can be uninstalled. | `artifacts/install-clean.json` | Reproduced fixture evidence | Runtime/template scaffolding and selected native-client safety remain until separately changed. |
| Foreign project and Codex settings survive install, rerun, and uninstall in the named fixture. | `artifacts/install-existing.json` | Reproduced fixture evidence | Proves the recorded fixture only. |
| Compatibility is reported by capability and evidence level. | `artifacts/compatibility.json` and [`../../22-compatibility-contract.md`](../../22-compatibility-contract.md) | Registry and fixture evidence | Certification targets are not all native or observed. |

No customer outcome, productivity gain, beginner validation, endorsement, or universal agent-client
compatibility claim is supported by this demonstration.
""",
    )
    write_text(
        output / "LIMITATIONS.md",
        """# Current limitations

- This demonstration proves one small Python fixture. It does not prove that every agent-generated
  change is correct or that every repository can be configured automatically.
- The lifecycle records are fixture evidence. They do not prove real-client discovery or behavior.
- Project uninstall removes managed project instructions but retains the selected native-client
  safety configuration. Reconfigure client safety explicitly if that local policy should change.
- Claude Code and Codex are the deepest native integrations. Other registry targets retain their
  explicit certification state; the bundle does not upgrade it.
- No beginner observation or customer result is included. “Beginner-proven,” productivity, return
  on investment, avoided-defect, and endorsement claims remain unsupported.
- The raw clean-room workspace is intentionally temporary. Public artifacts normalize volatile
  paths, timestamps, host/platform fields, commit IDs, and elapsed times; see `sanitization.json`.
- POSIX can pin each handoff path component with no-follow directory descriptors. Windows lacks the
  same primitive and uses fail-closed path prechecks plus final-handle validation.
- Network absence is established by the generator's bounded local command graph, isolated client
  homes, and disabled update checks; the replay does not run inside an operating-system network
  sandbox.
- Native operating-system release evidence still requires a separately authorized clean commit,
  push, and hosted workflow run. This bundle performs no remote write.
""",
    )
    write_text(
        output / "SECURITY-REVIEW.md",
        """# FVL-08 security review

No security blocker was found in the First Verified Loop boundary. The review names each required
threat explicitly and ties it to executable evidence rather than treating a green aggregate as a
security claim.

| Threat | Reviewed boundary and evidence |
|---|---|
| `command-injection` | Discovery never executes repository hints; only reviewed detector commands can enter a plan, and resume accepts one literal status-command grammar. |
| `path-traversal` | Absolute, parent-traversal, cross-target, home, broad-root, and outside-project targets fail before writes. |
| `symlink-escape` | Verification config, backup, demo target, and handoff fixtures reject redirected components; POSIX resume pins directory descriptors with no-follow semantics. |
| `plan-tampering` | Apply recomputes discovery and binds the schema-valid plan to its target, inputs, labels, and commands before changing configuration. |
| `secret-redaction` | Discovery, plan diffs, errors, resume output, verification sidecars, and public artifacts are covered by redaction and leak-gate fixtures. |
| `foreign-file-preservation` | CRLF, comments, custom phases, project instructions, client settings, and occupied targets are preserved at the documented ownership boundary. |
| `git-state-safety` | Demo creation performs no Git action; resume observes with optional locks disabled and leaves branch, HEAD, refs, stash, index, and dirty state unchanged. |

The independent review reran the focused FVL-02, FVL-04, FVL-05, and FVL-07 suites and found no
blocker. Residuals remain explicit: proof generation is not enclosed by an operating-system network
sandbox, and Windows uses fail-closed prechecks plus final-handle validation rather than POSIX
directory-descriptor pinning. Native report authenticity relies on same-run hosted-job artifact
trust. Output roots are explicit and symlink-checked, but an attacker who can mutate the runner's
private temporary directory during the narrow check/write interval is already inside that trust
boundary.
""",
    )
    write_text(
        output / "RELEASE-READINESS.md",
        """# FVL-08 release-readiness boundary

The local product promise is covered by the status, profile, discovery/apply, red-to-green demo,
real command, receipt, resume, documentation, lifecycle, claim-map, and security artifacts in this
bundle. The repository gate contains 25 verification phases, and the implementation remains
standard-library only, so no new runtime dependency audit applies.

Release closure is fail-closed. The wave is **not complete until** the native Linux, macOS, and
Windows jobs each produce a passing machine-readable report for the same clean Git commit and tree,
and `scripts/first-loop-release-evidence.py aggregate` accepts exactly those three reports. Workflow
logs alone are not the receipt. The aggregate artifact plus a final repository receipt and handoff,
both written after the last change, close FVL-08.

No commit, push, workflow trigger, publish, merge, or deployment is implied by this document.
""",
    )
    write_json(
        output / "sanitization.json",
        {
            "schema_version": 1,
            "purpose": "Remove machine-specific data while retaining command outcomes and evidence structure.",
            "normalized": [
                "temporary clean-source, demo, lifecycle, workspace, and home paths",
                "40-character local Git commit identifiers",
                "handoff filename timestamps",
                "receipt timestamps",
                "receipt hostname and platform fields",
                "receipt phase durations",
                "receipt output hashes after path, elapsed-time, and line-ending sanitization",
                "test elapsed times",
                "line endings",
            ],
            "not_normalized": [
                "exit codes",
                "test names and pass/fail outcomes",
                "verification phase labels",
                "receipt status",
                "Git dirty-state booleans",
                "installation ownership and preservation results",
                "compatibility capability and evidence values",
            ],
            "source_clean": True,
            "network_used": False,
            "external_write_used": False,
            "demo_initialization_observed": bool(run_metadata["demo_initialize"]),
            "handoff_creation_observed": bool(run_metadata["handoff_command"]),
        },
    )


def build_into(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="agentsmith-fvl07-clean-") as temporary:
        workspace = Path(temporary)
        source = workspace / "source"
        source_environment = isolated_environment(workspace / "source-home")
        copy_clean_source(source, source_environment)
        metadata = build_loop_artifacts(source, workspace, output)
        lifecycle_fixture(source, workspace, output, existing=False)
        lifecycle_fixture(source, workspace, output, existing=True)
        write_documentation(output, metadata)


def build(output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise ProofError(f"output directory must be new or empty: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="agentsmith-fvl07-output-", dir=output.parent) as staging_root:
        staged = Path(staging_root) / "proof"
        build_into(staged)
        if output.exists():
            output.rmdir()
        os.replace(staged, output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="new or empty directory for sanitized proof")
    args = parser.parse_args()
    try:
        build(Path(args.output).expanduser().resolve())
    except ProofError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(Path(args.output).expanduser().resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
