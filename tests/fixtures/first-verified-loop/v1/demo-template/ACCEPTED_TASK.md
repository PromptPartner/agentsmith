# Accepted task

## Outcome

Report a project as ready only when every required launch check passes.

## Non-goals

- Do not add dependencies.
- Do not change the fixture format or command-line interface.
- Do not weaken or remove a check.

## Affected scope

`readiness.py` and its test only.

## Acceptance checks

- The partial-check test passes for the intended reason.
- `python readiness.py checks.json` prints `NOT READY` and exits with status 1.
- The configured verification phases pass after the bounded fix.
