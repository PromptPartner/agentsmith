# Contributing to AgentSmith

Thank you for helping improve AgentSmith. Contributions can include bug reports, profile improvements,
documentation, tests, and code.

## Before you start

- Search the [existing issues](https://github.com/PromptPartner/agentsmith/issues) before opening a new one.
- Use the issue form that best matches the change. For a substantial behavior change, open a feature
  request before investing in an implementation.
- Never include credentials, private repository content, personal data, or an undisclosed vulnerability
  in an issue, pull request, fixture, or commit. Report vulnerabilities as described in
  [SECURITY.md](SECURITY.md).
- Keep each pull request focused on one concern. Preserve research and source material unless its owner
  has explicitly approved deletion.

## Development workflow

1. Fork the repository and create a branch from `master`.
2. Read `AGENTS.md` and the documentation for the area you are changing.
3. For changed behavior, add a check that fails for the expected reason before implementing the fix.
4. Make the smallest complete change, including affected documentation.
5. Run the full verification command:

   ```text
   agentsmith verify
   ```

6. Exercise the changed path once in a disposable project. Do not test installers against a project that
   contains work you cannot restore.
7. Open a pull request using the repository template and include the evidence you observed.

If the `agentsmith` command is not available yet, use the repository's documented development entry point
for the same verification phases.

## Profile changes

Profiles define what good work and sufficient proof mean for a work type. A profile contribution should:

- describe a distinct work type or a necessary modifier;
- state when to use it and when another profile is a better fit;
- define observable completion and verification gates;
- avoid project-specific rules in the universal core; and
- include or update checks that keep generated instructions and profile metadata aligned.

Use the profile proposal issue form before adding a new profile. Prefer sharpening an existing profile when
the work shares the same completion standard.

## Pull request expectations

A reviewable pull request has a clear reason, a focused diff, and evidence. Include:

- the problem and intended outcome;
- the approach and material trade-offs;
- the failing-before and passing-after evidence for behavior changes;
- the full verification result and a real-path check; and
- any compatibility, security, documentation, or follow-up impact.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md). Contributions are accepted
under the repository's [MIT License](LICENSE).
