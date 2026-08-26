#!/usr/bin/env python3
"""Validate the portable-agent contract and, optionally, the production runtime.

The fixture checks are intentionally independent of the implementation.  During the
migration the default mode reports unmet production checks as GAPs but exits cleanly;
``--strict`` turns every GAP into a failure and is the release/CI certification gate.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "compatibility"
CONTRACT_PATH = FIXTURES / "contract.json"
REGISTRY_PATH = ROOT / "config" / "agents.json"
CORE_PATH = ROOT / "agentsmith.py"


class Results:
    def __init__(self, strict: bool) -> None:
        self.strict = strict
        self.passed = 0
        self.gaps: list[str] = []
        self.failures: list[str] = []

    def ok(self, label: str) -> None:
        self.passed += 1
        print(f"  PASS  {label}")

    def check(self, condition: bool, label: str, detail: str = "") -> None:
        if condition:
            self.ok(label)
            return
        message = f"{label}{': ' + detail if detail else ''}"
        if self.strict:
            self.failures.append(message)
            print(f"  FAIL  {message}")
        else:
            self.gaps.append(message)
            print(f"  GAP   {message}")

    def fixture(self, condition: bool, label: str, detail: str = "") -> None:
        if condition:
            self.ok(label)
            return
        message = f"{label}{': ' + detail if detail else ''}"
        self.failures.append(message)
        print(f"  FAIL  {message}")


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def as_agent_list(registry: Any) -> list[dict[str, Any]]:
    if isinstance(registry, list):
        return registry
    if not isinstance(registry, dict):
        return []
    agents = registry.get("agents", [])
    if isinstance(agents, list):
        return agents
    if isinstance(agents, dict):
        return [dict(value, id=key) for key, value in agents.items() if isinstance(value, dict)]
    return []


def field(record: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in record:
            return record[name]
    return None


def has_capability_declaration(value: Any, statuses: set[str], management: set[str]) -> bool:
    if not isinstance(value, dict):
        return False
    return (
        value.get("client_support") in statuses
        and value.get("agentsmith_management") in management
        and isinstance(value.get("notes"), str)
        and bool(value["notes"].strip())
    )


def parse_frontmatter(text: str) -> str:
    """Return only the frontmatter; full YAML parsing is unnecessary for these invariants."""
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---\n", 4)
    return "" if end < 0 else text[4:end]


def validate_fixtures(results: Results, contract: dict[str, Any]) -> None:
    print("fixture contract")
    agents = contract.get("agents", [])
    ids = [agent.get("id") for agent in agents]
    results.fixture(contract.get("schema_version") == 1, "contract schema is pinned")
    results.fixture(contract.get("canonical_project_instructions") == "AGENTS.md", "AGENTS.md is canonical")
    results.fixture(len(ids) == 16 and len(set(ids)) == 16, "exactly 16 unique certification targets")
    results.fixture(
        {agent["id"] for agent in agents if agent.get("tier") == "native"} == {"claude", "codex"},
        "only Claude and Codex are native",
    )
    results.fixture(
        {agent["id"] for agent in agents if agent.get("adapter") == "configured"}
        == {"gemini-cli", "aider", "continue", "goose"},
        "configured-adapter target set is explicit",
    )
    results.fixture(
        set(contract.get("excluded_backends", [])) == {"lm-studio", "tabby"},
        "model backends are excluded as harness targets",
    )
    selection = contract.get("selection_cases", [])
    results.fixture(any(case.get("error") == "mixed-selection" for case in selection), "mixed selector rejection is covered")
    results.fixture(
        {scenario for scenario in contract.get("conformance_scenarios", [])}
        >= {
            "native-windows-without-bash",
            "nested-rule-precedence",
            "skill-identity-independent-of-install-path",
            "foreign-config-preservation",
            "uninstall-ownership",
        },
        "high-risk conformance scenarios are enumerated",
    )

    nested = load_json(FIXTURES / "nested" / "cases.json")
    for case in nested["cases"]:
        chain = [FIXTURES / "nested" / item for item in case["instruction_chain"]]
        sentinels = []
        for path in chain:
            match = re.search(r"^CONFORMANCE_SENTINEL=(.+)$", path.read_text(encoding="utf-8"), re.MULTILINE)
            sentinels.append(match.group(1) if match else None)
        results.fixture(
            bool(sentinels) and sentinels[-1] == case["effective_sentinel"],
            f"nearest nested rule wins for {case['working_path']}",
        )

    skill_paths = sorted((FIXTURES / "skill-paths").glob("**/SKILL.md"))
    skill_text = [path.read_text(encoding="utf-8") for path in skill_paths]
    skill_names = []
    for text in skill_text:
        frontmatter = parse_frontmatter(text)
        match = re.search(r"^name:\s*(\S+)\s*$", frontmatter, re.MULTILINE)
        skill_names.append(match.group(1) if match else None)
    results.fixture(len(skill_paths) == 2 and len(set(skill_names)) == 1, "skill identity is metadata-derived across install paths")
    results.fixture(all("compatibility:" in parse_frontmatter(text) for text in skill_text), "fixture skills declare compatibility")
    results.fixture(skill_paths[0].read_bytes() == skill_paths[1].read_bytes(), "Claude skill adapter does not fork portable guidance")

    managed = load_json(FIXTURES / "managed-config" / "case.json")
    results.fixture(len(managed.get("invariants", [])) == 4, "managed-config lifecycle invariants are fixture-backed")


def validate_registry(results: Results, contract: dict[str, Any]) -> list[dict[str, Any]]:
    print("production registry")
    if not REGISTRY_PATH.is_file():
        results.check(False, "machine-readable registry exists", str(REGISTRY_PATH.relative_to(ROOT)))
        return []
    try:
        registry = load_json(REGISTRY_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        results.check(False, "machine-readable registry parses", str(exc))
        return []
    results.ok("machine-readable registry parses")
    agents = as_agent_list(registry)
    expected = {agent["id"]: agent for agent in contract["agents"]}
    actual = {agent.get("id"): agent for agent in agents}
    results.check(set(actual) == set(expected), "registry contains the exact 16 targets")
    results.check(
        all(field(actual.get(agent_id, {}), "target_tier", "tier") == spec["tier"] for agent_id, spec in expected.items()),
        "registry tiers match the certification contract",
    )
    def adapter_kind(agent: dict[str, Any]) -> str | None:
        explicit = agent.get("adapter")
        if explicit:
            return explicit
        if field(agent, "target_tier", "tier") == "native":
            return "native"
        instructions = agent.get("instructions", {})
        return "configured" if isinstance(instructions, dict) and instructions.get("discovery") == "configured" else "direct"

    results.check(
        all(adapter_kind(actual.get(agent_id, {})) == spec["adapter"] for agent_id, spec in expected.items()),
        "registry adapter kinds match the certification contract",
    )

    statuses = set(contract["capability_statuses"])
    evidence = set(contract["evidence_levels"])
    management = set(contract["management_statuses"])
    complete_records = True
    separated_capabilities = True
    instruction_paths = True
    for agent_id, agent in actual.items():
        required_aliases = {"name": ("name", "display_name"), "target_tier": ("target_tier", "tier")}
        complete_records &= all(
            field(agent, *required_aliases.get(key, (key,))) is not None
            for key in contract["required_registry_fields"]
        )
        instructions = field(agent, "instructions", "instruction_discovery")
        if not isinstance(instructions, dict):
            instruction_paths = False
        else:
            instruction_paths &= all(field(instructions, key) is not None for key in contract["required_instruction_fields"])
        skills_tools = agent.get("skills_tools", {})
        native_runtime = agent.get("native_runtime", {})
        for capability in (field(skills_tools, "agent_skills", "skills"), field(skills_tools, "mcp"), field(native_runtime, "hooks")):
            separated_capabilities &= has_capability_declaration(capability, statuses, management)
        local_models = agent.get("local_models", {})
        separated_capabilities &= (
            isinstance(local_models, dict)
            and local_models.get("client_support") in statuses
            and isinstance(local_models.get("providers"), list)
            and isinstance(local_models.get("notes"), str)
        )
        proofs = agent.get("evidence", [])
        separated_capabilities &= isinstance(proofs, list) and bool(proofs) and all(
            isinstance(proof, dict) and proof.get("type") in evidence for proof in proofs
        )
        os_support = field(agent, "operating_systems", "os")
        complete_records &= isinstance(os_support, dict) and isinstance(os_support.get("targets"), list) and isinstance(os_support.get("constraints"), list)
        if agent_id in {"claude", "codex"} and isinstance(instructions, dict):
            source = field(instructions, "canonical", "source", "file")
            instruction_paths &= source in (None, "AGENTS.md")
    results.check(complete_records, "every agent declares paths, OS, local-model, and evidence fields")
    results.check(instruction_paths, "instruction discovery declares project/global paths and nesting")
    dimensions = registry.get("dimensions", []) if isinstance(registry, dict) else []
    results.check(set(dimensions) == {"instructions", "skills_tools", "native_runtime"}, "registry reports the three compatibility layers independently")
    results.check(separated_capabilities, "skills, MCP, hooks, and local models declare support without overclaiming evidence")

    groups = registry.get("groups", {}) if isinstance(registry, dict) else {}
    results.check(isinstance(groups, dict) and set(groups) >= {"native", "standard", "local", "all"}, "all selector groups are declared")
    if isinstance(groups, dict):
        results.check(set(groups.get("native", [])) == {"claude", "codex"}, "native group is exact")
        results.check(set(groups.get("all", [])) == set(expected), "all group expands to every certified target")
        results.check(bool(groups.get("standard")) and set(groups.get("standard", [])) <= set(expected), "standard group is a non-empty certified subset")
        results.check(bool(groups.get("local")) and set(groups.get("local", [])) <= set(expected), "local group is a non-empty certified subset")
    return agents


def run_core(*arguments: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CORE_PATH), *arguments],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )


def output_has_all(output: str, words: Iterable[str]) -> bool:
    folded = output.casefold()
    return all(word.casefold() in folded for word in words)


def validate_runtime(results: Results, contract: dict[str, Any], agents: list[dict[str, Any]]) -> None:
    print("production runtime")
    if not CORE_PATH.is_file():
        results.check(False, "Python 3.11+ stdlib core exists", CORE_PATH.name)
        return
    source = CORE_PATH.read_text(encoding="utf-8")
    results.ok("Python core exists")
    version_guard = bool(re.search(r"3[.,_]11|\(\s*3\s*,\s*11\s*\)|version_info\s*[<(]=?\s*\(?3\s*,\s*11", source))
    results.check(version_guard, "Python core has an actionable 3.11+ runtime guard")

    try:
        compile(source, str(CORE_PATH), "exec")
        results.ok("Python core compiles")
    except SyntaxError as exc:
        results.check(False, "Python core compiles", str(exc))

    imported_roots = set(re.findall(r"^(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", source, re.MULTILINE))
    third_party = imported_roots - set(sys.stdlib_module_names) - {"__future__"}
    results.check(not third_party, "Python core imports only the standard library", ", ".join(sorted(third_party)))

    for launcher_name, tokens, max_lines in (
        ("setup.sh", ("agentsmith.py", "python3", "python"), 100),
        ("setup.ps1", ("agentsmith.py", "python", "py"), 120),
    ):
        path = ROOT / launcher_name
        if not path.is_file():
            results.check(False, f"{launcher_name} launcher exists")
            continue
        launcher = path.read_text(encoding="utf-8-sig")
        results.check(len(launcher.splitlines()) <= max_lines, f"{launcher_name} is a thin launcher")
        results.check(output_has_all(launcher, tokens), f"{launcher_name} discovers Python and delegates identical arguments")

    help_run = run_core("--help")
    results.check(help_run.returncode == 0, "agentsmith --help succeeds", help_run.stdout[-300:])
    results.check(output_has_all(help_run.stdout, ("--agent", "--platform")), "help documents new selector and legacy alias")

    list_run = run_core("agents", "list")
    expected_ids = [agent["id"] for agent in contract["agents"]]
    results.check(list_run.returncode == 0, "agentsmith agents list succeeds", list_run.stdout[-300:])
    results.check(output_has_all(list_run.stdout, expected_ids), "agents list exposes all 16 targets")

    compatibility = run_core("compatibility")
    results.check(compatibility.returncode == 0, "agentsmith compatibility succeeds", compatibility.stdout[-300:])
    results.check(
        output_has_all(compatibility.stdout, ("instructions", "skills", "mcp", "hooks", "tokens")),
        "compatibility separates capabilities and reports static-context size",
    )

    doctor = run_core("doctor", "--agent", "aider")
    results.check(
        output_has_all(doctor.stdout, ("instructions", "skills", "mcp", "hooks")),
        "doctor reports each capability independently",
        doctor.stdout[-300:],
    )

    mixed = run_core("--agent", "claude", "--platform", "codex", "--dry-run")
    results.check(mixed.returncode != 0 and output_has_all(mixed.stdout, ("agent", "platform")), "mixed --agent/--platform selection is rejected")

    legacy_console_env = os.environ.copy()
    legacy_console_env["PYTHONIOENCODING"] = "cp1252"
    legacy_console = subprocess.run(
        [sys.executable, str(CORE_PATH), "--agent", "native", "--profile", "general-admin", "--dry-run"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=legacy_console_env,
        check=False,
    )
    results.check(
        legacy_console.returncode == 0,
        "runtime status output works with an untouched Windows CP-1252 console",
        legacy_console.stderr.decode("cp1252", errors="replace")[-300:],
    )

    for label, selector in (
        ("repeatable selector", ("--agent", "claude", "--agent", "codex")),
        ("comma selector", ("--agent", "claude,codex")),
        ("native group", ("--agent", "native")),
        ("standard group", ("--agent", "standard")),
        ("local group", ("--agent", "local")),
        ("legacy both alias", ("--platform", "both")),
    ):
        selected = run_core(*selector, "--dry-run", "--profile", "general-admin")
        results.check(selected.returncode == 0, f"{label} resolves", selected.stdout[-300:])

    for helper in ("verify", "handoff", "new-feedback", "new-research"):
        helper_help = run_core(helper, "--help")
        results.check(helper_help.returncode == 0, f"cross-platform {helper} helper is exposed by Python CLI", helper_help.stdout[-300:])

    with tempfile.TemporaryDirectory(prefix="agentsmith profiles ") as profile_temporary:
        profile_root = Path(profile_temporary)
        profile_failures: list[str] = []
        for profile_path in sorted((ROOT / "profiles").glob("*.md")):
            destination = profile_root / profile_path.stem
            destination.mkdir()
            assembled = run_core(
                "--agent", "codex", "--profile", profile_path.stem, "--assemble-only", "--target", str(destination)
            )
            instructions = destination / "AGENTS.md"
            if assembled.returncode or not instructions.exists() or re.search(r"\{\{[A-Z_]+\}\}", instructions.read_text(encoding="utf-8")):
                profile_failures.append(profile_path.stem)
        results.check(not profile_failures, "every profile assembles without unresolved template tokens", ", ".join(profile_failures))

    with tempfile.TemporaryDirectory(prefix="agentsmith org policy ") as org_temporary:
        org_root = Path(org_temporary)
        org_dir = org_root / "policy"
        org_dir.mkdir()
        settings_path = org_dir / "managed-settings.json"
        settings_path.write_text('{"permissions":{"foreign":"keep","disableAutoMode":"custom"},"other":7}\n', encoding="utf-8")
        org_env = os.environ.copy()
        org_env.update({"HOME": str(org_root / "home"), "HARNESS_ORG_DIR": str(org_dir)})
        org_install = run_core("--agent", "claude", "--org-policy", "--profile", "security-audit", env=org_env)
        installed_settings = load_json(settings_path) if org_install.returncode == 0 else {}
        results.check(
            org_install.returncode == 0
            and installed_settings.get("permissions", {}).get("disableBypassPermissionsMode") == "disable"
            and installed_settings.get("permissions", {}).get("foreign") == "keep",
            "organization policy hardens managed keys and preserves foreign settings",
        )
        org_uninstall = run_core("--agent", "claude", "--org-policy", "--uninstall", env=org_env)
        restored_settings = load_json(settings_path) if settings_path.exists() else {}
        results.check(
            org_uninstall.returncode == 0
            and restored_settings == {"permissions": {"foreign": "keep", "disableAutoMode": "custom"}, "other": 7}
            and not (org_dir / "CLAUDE.md").exists(),
            "organization-policy uninstall restores prior managed values",
        )

    # This is a real end-to-end project assembly, isolated from the operator's home.
    with tempfile.TemporaryDirectory(prefix="agentsmith conformance ") as temporary:
        sandbox = Path(temporary)
        project = sandbox / "prøjéct with spaces"
        project.mkdir()
        env = os.environ.copy()
        env.update({"HOME": str(sandbox / "home"), "USERPROFILE": str(sandbox / "home"), "CODEX_HOME": str(sandbox / "codex home")})
        install = run_core(
            "--agent",
            "all",
            "--profile",
            "general-admin",
            "--operator-name",
            "Ada Lovelace",
            "--tracker",
            "Linear",
            "--assemble-only",
            "--target",
            str(project),
            env=env,
        )
        canonical = project / "AGENTS.md"
        claude_copy = project / "CLAUDE.md"
        results.check(install.returncode == 0, "all-agent assembly succeeds in a Unicode path", install.stdout[-500:])
        results.check(canonical.is_file() and not canonical.is_symlink(), "all-agent assembly writes a real canonical AGENTS.md")
        results.check(
            claude_copy.is_file() and canonical.is_file() and claude_copy.read_bytes() == canonical.read_bytes(),
            "Claude receives an equivalent generated copy",
        )
        project_cli = project / ".agentsmith" / "agentsmith"
        windows_cli = project / ".agentsmith" / "agentsmith.cmd"
        active_cli = ["cmd", "/c", str(windows_cli)] if os.name == "nt" else [str(project_cli)]
        shim_run = subprocess.run(
            [*active_cli, "--version"], cwd=project, text=True, capture_output=True, check=False
        ) if (windows_cli.exists() if os.name == "nt" else project_cli.exists()) else None
        results.check(
            bool(shim_run and shim_run.returncode == 0 and "agentsmith" in shim_run.stdout.casefold()),
            "installed current-OS project shim resolves the Python CLI",
        )
        installed_list = subprocess.run(
            [*active_cli, "agents", "list"], cwd=project, text=True, capture_output=True, check=False
        ) if (windows_cli.exists() if os.name == "nt" else project_cli.exists()) else None
        results.check(
            bool(installed_list and installed_list.returncode == 0 and output_has_all(installed_list.stdout, expected_ids)),
            "installed project shim carries the compatibility registry",
        )
        windows_shim = windows_cli.read_text(encoding="utf-8-sig") if windows_cli.exists() else ""
        results.check(
            output_has_all(windows_shim, ("agentsmith.py", "python", "py -3")),
            "installed Windows project shim discovers Python without Bash",
        )
        if canonical.is_file():
            canonical_text = canonical.read_text(encoding="utf-8")
            results.check("@RTK.md" not in canonical_text, "canonical instructions contain no proprietary import")
            results.check("**Ada Lovelace** is the lead" in canonical_text, "operator identity reaches canonical instructions")
            results.check(
                "writes are NOT authorized" in canonical_text and "The team's record is **Linear**" in canonical_text,
                "tracker naming defaults to ask-first consent",
            )

        before = sorted((path.relative_to(project), path.read_bytes()) for path in project.rglob("*") if path.is_file())
        rerun = run_core(
            "--agent",
            "all",
            "--profile",
            "general-admin",
            "--assemble-only",
            "--target",
            str(project),
            env=env,
        )
        after = sorted((path.relative_to(project), path.read_bytes()) for path in project.rglob("*") if path.is_file())
        results.check(rerun.returncode == 0 and before == after, "all-agent assembly is idempotent")

        allowed_project = sandbox / "explicit tracker consent"
        allowed_project.mkdir()
        allowed = run_core(
            "--agent", "codex", "--profile", "general-admin", "--tracker", "Linear",
            "--tracker-writes", "allowed", "--target", str(allowed_project), env=env,
        )
        allowed_text = (allowed_project / "AGENTS.md").read_text(encoding="utf-8") if allowed.returncode == 0 else ""
        results.check("writes are authorized" in allowed_text, "explicit tracker-write opt-in is rendered")

        refused = run_core(
            "--agent", "native", "--global", "--target", str(project), "--dry-run", env=env,
        )
        results.check(refused.returncode != 0 and "target" in refused.stdout.casefold(), "global target redirect is refused before writes")

        dry_project = sandbox / "dry run"
        dry_project.mkdir()
        dry = run_core("--agent", "all", "--profile", "general-admin", "--dry-run", "--target", str(dry_project), env=env)
        results.check(dry.returncode == 0 and not any(dry_project.iterdir()), "all-agent dry-run performs no project writes")

        design_project = sandbox / "generated design system"
        design_project.mkdir()
        design = run_core(
            "--agent", "codex", "--profile", "software-dev", "--design-system", "generate",
            "--target", str(design_project), env=env,
        )
        results.check(
            design.returncode == 0 and (design_project / "DESIGN.md").is_file(),
            "design-system generate retains the legacy scaffold behavior",
            design.stdout[-300:],
        )
        invalid_design_project = sandbox / "invalid design system"
        invalid_design_project.mkdir()
        invalid_design = run_core(
            "--agent", "codex", "--profile", "software-dev", "--design-system", "catalog:../escape",
            "--target", str(invalid_design_project), env=env,
        )
        results.check(
            invalid_design.returncode != 0 and not any(invalid_design_project.iterdir()),
            "invalid design-system sources are rejected before project writes",
        )

        update_root = sandbox / "self update scope"
        seed = update_root / "seed"
        remote = update_root / "remote.git"
        checkout = update_root / "checkout"
        update_project = update_root / "project"
        seed.mkdir(parents=True)
        update_project.mkdir()
        for directory in ("core", "profiles", "config"):
            shutil.copytree(ROOT / directory, seed / directory)
        shutil.copy2(CORE_PATH, seed / "agentsmith.py")
        git_steps = [
            ["git", "-C", str(seed), "init", "-q", "-b", "main"],
            ["git", "-C", str(seed), "config", "user.name", "Conformance Test"],
            ["git", "-C", str(seed), "config", "user.email", "user@example.com"],
            ["git", "-C", str(seed), "add", "."],
            ["git", "-C", str(seed), "commit", "-qm", "initial"],
            ["git", "clone", "-q", "--bare", str(seed), str(remote)],
            ["git", "clone", "-q", str(remote), str(checkout)],
        ]
        git_ready = all(subprocess.run(step, capture_output=True, check=False).returncode == 0 for step in git_steps)
        update_env = env.copy()
        update_env.update({"HOME": str(update_root / "home"), "CODEX_HOME": str(update_root / "codex-home")})
        initial_update_install = subprocess.run(
            [sys.executable, str(checkout / "agentsmith.py"), "--agent", "codex", "--profile", "general-admin",
             "--assemble-only", "--operator-name", "Scope Test", "--target", str(update_project)],
            text=True, capture_output=True, env=update_env, check=False,
        ) if git_ready else None
        global_sentinels = [Path(update_env["HOME"]) / ".claude" / "CLAUDE.md", Path(update_env["CODEX_HOME"]) / "AGENTS.md"]
        for sentinel in global_sentinels:
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text("foreign global content\n", encoding="utf-8")
        if git_ready:
            identity_source = seed / "core" / "00-identity.md"
            identity_source.write_text(identity_source.read_text(encoding="utf-8") + "\nSELF_UPDATE_SCOPE_PROBE\n", encoding="utf-8")
            git_ready = all(
                subprocess.run(step, capture_output=True, check=False).returncode == 0
                for step in (
                    ["git", "-C", str(seed), "add", "core/00-identity.md"],
                    ["git", "-C", str(seed), "commit", "-qm", "probe"],
                    ["git", "-C", str(seed), "push", "-q", str(remote), "main"],
                )
            )
        update_run = subprocess.run(
            [sys.executable, str(checkout / "agentsmith.py"), "--self-update", "--from", str(remote),
             "--target", str(update_project)],
            text=True, capture_output=True, env=update_env, check=False,
        ) if git_ready and initial_update_install and initial_update_install.returncode == 0 else None
        updated_text = (update_project / "AGENTS.md").read_text(encoding="utf-8") if (update_project / "AGENTS.md").exists() else ""
        results.check(
            bool(update_run and update_run.returncode == 0)
            and "SELF_UPDATE_SCOPE_PROBE" in updated_text
            and "**Scope Test** is the lead" in updated_text
            and all(path.read_text(encoding="utf-8") == "foreign global content\n" for path in global_sentinels),
            "explicit-target self-update reassembles only that project and preserves its identity",
            (update_run.stdout + update_run.stderr)[-500:] if update_run else "Git fixture setup failed",
        )

        adapter_project = sandbox / "adapters CRLF"
        (adapter_project / ".gemini").mkdir(parents=True)
        (adapter_project / ".continue" / "rules").mkdir(parents=True)
        (adapter_project / ".gemini" / "settings.json").write_bytes(
            b'{\r\n  "foreign": {"keep": true},\r\n  "context": {"fileName": ["GEMINI.md"]}\r\n}\r\n'
        )
        (adapter_project / ".aider.conf.yml").write_bytes(b'model: foreign-model\r\nread:\r\n  - NOTES.md\r\n')
        (adapter_project / ".continue" / "rules" / "agentsmith.md").write_bytes(b'# foreign Continue rule\r\n')
        (adapter_project / ".goosehints").write_bytes(b'foreign Goose hint\r\n')
        configured_selector = "gemini-cli,aider,continue,goose"
        adapter_install = run_core(
            "--agent", configured_selector, "--profile", "general-admin", "--target", str(adapter_project), env=env
        )
        gemini_path = adapter_project / ".gemini" / "settings.json"
        aider_path = adapter_project / ".aider.conf.yml"
        continue_path = adapter_project / ".continue" / "rules" / "agentsmith.md"
        goose_path = adapter_project / ".goosehints"
        gemini_data = load_json(gemini_path) if gemini_path.is_file() else {}
        adapter_text = "\n".join(
            path.read_text(encoding="utf-8") for path in (aider_path, continue_path, goose_path) if path.is_file()
        )
        results.check(adapter_install.returncode == 0, "configured adapters accept CRLF foreign config", adapter_install.stdout[-300:])
        results.check(
            gemini_data.get("foreign") == {"keep": True}
            and gemini_data.get("context", {}).get("fileName") == ["GEMINI.md", "AGENTS.md"]
            and "foreign-model" in adapter_text
            and "NOTES.md" in adapter_text
            and "foreign Continue rule" in adapter_text
            and "foreign Goose hint" in adapter_text,
            "configured adapters preserve foreign content and point to canonical AGENTS.md",
        )
        adapter_before = sorted((path.relative_to(adapter_project), path.read_bytes()) for path in adapter_project.rglob("*") if path.is_file())
        adapter_rerun = run_core(
            "--agent", configured_selector, "--profile", "general-admin", "--target", str(adapter_project), env=env
        )
        adapter_after = sorted((path.relative_to(adapter_project), path.read_bytes()) for path in adapter_project.rglob("*") if path.is_file())
        results.check(adapter_rerun.returncode == 0 and adapter_before == adapter_after, "configured-adapter re-run is byte-idempotent")

        adapter_uninstall = run_core("--agent", configured_selector, "--uninstall", "--target", str(adapter_project), env=env)
        gemini_after = load_json(gemini_path) if gemini_path.is_file() else {}
        residual_text = "\n".join(
            path.read_text(encoding="utf-8") for path in (aider_path, continue_path, goose_path) if path.is_file()
        )
        results.check(adapter_uninstall.returncode == 0, "configured-adapter uninstall succeeds", adapter_uninstall.stdout[-300:])
        results.check(
            gemini_after.get("foreign") == {"keep": True}
            and gemini_after.get("context", {}).get("fileName") == ["GEMINI.md"]
            and "foreign-model" in residual_text
            and "NOTES.md" in residual_text
            and "foreign Continue rule" in residual_text
            and "foreign Goose hint" in residual_text
            and "AGENTS.md" not in residual_text
            and "AGENTSMITH MANAGED" not in residual_text
            and not (adapter_project / "AGENTS.md").exists(),
            "uninstall removes only configured-adapter managed content",
        )

        hooks_project = sandbox / "native hooks"
        hooks_project.mkdir()
        subprocess.run(["git", "-C", str(hooks_project), "init", "-q"], check=False)
        hooks = run_core(
            "--agent",
            "native",
            "--profile",
            "general-admin",
            "--target",
            str(hooks_project),
            "--with-handoff-hooks",
            "--with-hooks",
            env=env,
        )
        configured_commands: list[str] = []
        for path in (sandbox / "home", sandbox / "codex home", hooks_project):
            if not path.exists():
                continue
            for config_path in (*path.rglob("*.json"), *path.rglob("*.toml")):
                for line in config_path.read_text(encoding="utf-8-sig").splitlines():
                    if "command" in line.casefold():
                        configured_commands.append(line)
        bash_hook = any(re.search(r"(?:\bbash\b|\.sh\b)", command, re.IGNORECASE) for command in configured_commands)
        results.check(hooks.returncode == 0, "native hook install succeeds through Python core", hooks.stdout[-300:])
        results.check(bool(configured_commands) and not bash_hook, "native hook configuration invokes Python without Bash or .sh helpers")
        git_hook = hooks_project / ".git" / "hooks" / "pre-commit"
        git_hook_text = git_hook.read_text(encoding="utf-8") if git_hook.exists() else ""
        results.check(
            output_has_all(git_hook_text, ("agentsmith.py", "hook git-pre-commit"))
            and "bash" not in git_hook_text.casefold(),
            "Git hook uses Git's launcher only to delegate to Python",
        )

    skill_files = sorted((ROOT / "skills").glob("*/SKILL.md"))
    skills_have_metadata = bool(skill_files)
    skills_are_path_neutral = bool(skill_files)
    for path in skill_files:
        text = path.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(text)
        skills_have_metadata &= "compatibility:" in frontmatter
        skills_are_path_neutral &= not bool(
            re.search(r"(?:identify|infer).{0,100}(?:runtime|platform).{0,100}(?:\.claude/skills|\.agents/skills)", text, re.IGNORECASE | re.DOTALL)
        )
    results.check(skills_have_metadata, "every bundled skill has compatibility metadata")
    results.check(skills_are_path_neutral, "bundled skills do not infer runtime identity from installation path")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail on unimplemented production conformance checks")
    parser.add_argument("--fixtures-only", action="store_true", help="validate only the implementation-neutral fixtures")
    arguments = parser.parse_args()
    results = Results(strict=arguments.strict)
    try:
        contract = load_json(CONTRACT_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: cannot load {CONTRACT_PATH}: {exc}")
        return 1

    validate_fixtures(results, contract)
    if not arguments.fixtures_only:
        agents = validate_registry(results, contract)
        validate_runtime(results, contract, agents)

    print()
    print(f"agent-conformance: {results.passed} passed, {len(results.gaps)} gaps, {len(results.failures)} failed")
    if results.gaps:
        print("Run with --strict to make reported implementation gaps release-blocking.")
    return 1 if results.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
