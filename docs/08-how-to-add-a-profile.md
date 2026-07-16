# How to add or edit a profile

Profiles are where the harness flexes to new kinds of work. Adding one is cheap and is exactly
the System-Evolution Mindset in action (`core/60`): when you hit work that none of the eight
profiles fits well, write a ninth instead of fighting the wrong one.

## Add a profile

1. Copy an existing profile that's closest in spirit:
   `cp profiles/general-admin.md profiles/<your-name>.md`
2. Keep the **section structure** (it's what makes profiles consistent and scannable):
   - `## Profile: <Title>` + **Use this profile when**
   - **What "done" and "verified" mean here** (sharpen Rule 2/5 for this work)
   - **The load-bearing rules** for this work (the 2–4 things that, if skipped, ship it broken)
   - **Quality gates** (a concrete, checkable list)
   - **Failure modes to guard against**
   - **Recommended skills & tools** (map the ecosystem; stay tight — Rule 10)
   - **Addendum to the STOP table** (3–4 work-specific rationalizations + their reality)
3. Reference core rules by number (R1–R10) instead of restating them — the core is always loaded
   alongside the profile.
4. Keep it **work-type-neutral about tools** (use placeholders), so it travels across projects.
5. Assemble with it: `./setup.sh --profile <your-name>` and read the composed `CLAUDE.md` to
   confirm it reads as one coherent rulebook.

## Edit the core (rarely, carefully)

The `core/` files are the static context loaded every turn — the leanest, most load-bearing
layer. Change them only when a lesson is genuinely universal (applies to *all* work, not one
profile). A profile-specific lesson belongs in the profile. Every core line should trace to a
real incident; if you can't name the failure it prevents, it doesn't belong (Rule 10).

## Keep the static/dynamic boundary honest

Before adding text anywhere in `core/` or a profile, ask: **does this need to be loaded every
turn, or could it be a skill / a `docs/` page / a template pulled in on demand?** Prefer dynamic
context. The assembled `CLAUDE.md` should stay lean — that's not tidiness, it's what keeps the
agent sharp (`docs/01-harness-philosophy.md`).
