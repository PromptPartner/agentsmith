# Feedback 0007: Unicode hook command escaping

> A harness post-incident. Never delete this record; archive it under `_archive/` if obsolete.

- **Date:** 2026-08-26
- **Status:** applied
- **Cost:** Hook definitions installed below a Unicode path pointed at a non-existent literal
  `\\uXXXX` pathname, so the client could not invoke the managed runtime.

## 1. Evidence / symptom

The effective-state doctor fixture installed AgentSmith under a path containing `ü`. Doctor found
both managed commands but classified them as stale: their JSON values contained literal
`\\u00fc`, while the installed runtime path contained the real character.

## 2. Failure mechanism

`install_hooks()` used `json.dumps()` as a command-line quoting function. JSON quoting happens to
survive common ASCII paths, but it escapes non-ASCII code points and is not the native shell's
argument grammar.

## 3. Bounded edit

Construct hook commands with `shlex.join()` on POSIX and `subprocess.list2cmdline()` on Windows,
then let the surrounding JSON serializer encode the completed command exactly once.

## 4. Named surface

`agentsmith.py` hook command construction; the Unicode native-install fixture in
`scripts/test-agent-conformance.py`; `scripts/test-doctor.py`.

## 5. Non-regression validation

Install into a Unicode/space path, assert doctor resolves the current runtime, and execute the
installed hook command through the host shell. The command must return the expected hook payload.
