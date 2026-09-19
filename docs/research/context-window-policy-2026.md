# Research: context load and handoff policy

> Decision note verified 2026-09-17. Keep this source material under `docs/research/` (R9);
> obsolete material moves to `_archive/`, never deletion.

## Question

Should AgentSmith tell every operator to hand off when roughly 25–30% of a model's context window
has been used, and should the optional hook enforce that percentage by default?

## Sources consulted

| Source | Finding used |
|---|---|
| [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/) (TACL 2024) | Retrieval varies with information position; the middle can perform worse than the beginning or end. |
| [NoLiMa](https://arxiv.org/abs/2502.05167) (2025) | Long-context performance declines materially on tasks that cannot rely on literal matching, with different curves by model. |
| [Context Length Alone Hurts LLM Performance Despite Perfect Retrieval](https://aclanthology.org/2025.findings-emnlp.1264/) (EMNLP 2025) | Longer irrelevant context can reduce performance even when the needed information is retrieved correctly. |
| [Claude Code hooks guide](https://code.claude.com/docs/en/hooks-guide) | A Stop hook can return top-level `decision: "block"` and `reason`; context percentage reaches the status line, not the Stop event. |
| Local status-line, hook, documentation, and tests | Normal installs used the Python runtime hook, while threshold and freshness behavior existed only in the legacy Bash hook. |

## Findings

1. Long-context degradation is real, but it is not one curve. Model, task difficulty, distractors,
   information position, and conversation history all matter.
2. A model accepting a token is not proof that it uses that token reliably. Maximum context and
   reliable context are different product properties.
3. None of the reviewed independent research establishes 25–30% occupancy as a universal boundary.
   The former AgentSmith rule converted a local observation into a general performance claim.
4. The usage gauge remains useful: it reports load and helps an operator recognize long sessions.
   It must not be described as a quality score.
5. Phase boundaries, repetition, missed constraints, and upcoming risk are often better handoff
   signals than window occupancy alone.

## Decision

- Keep the neutral `ctx:NN%` usage gauge.
- Keep explicit `handoff` / `wrap up` as the reliable cross-runtime cue.
- Disable percentage automation when `HANDOFF_PCT_THRESHOLD` is absent.
- Let an operator explicitly set an integer from 1–100 after calibrating it on their own work.
- Treat that setting as a once-per-session, best-effort workflow heuristic. It is not a claimed
  model-quality boundary.
- Preserve the five-minute signal freshness check and fail open on missing, stale, malformed, or
  unsafe input.

This changes existing behavior deliberately: installations that relied on the former implicit 30%
value receive no percentage cue after updating until they set an explicit threshold. The gauge and
keyword handoff continue unchanged.

## Calibration protocol

Use this only when a team wants an automatic cue:

1. Select representative repository tasks with deterministic checks and a judgment rubric.
2. Run each task in fresh sessions at several realistic context loads, such as 10%, 25%, 50%, and
   75%. Vary whether important information appears near the beginning, middle, or end.
3. Repeat per model and runtime; one successful run is not a baseline.
4. Compare correctness, missed constraints, unnecessary retries, tool errors, cost, and time—not
   just whether the final answer looks plausible.
5. Choose a cue before the measured degradation point, leaving enough room to safe-state and write
   the handoff. If no stable degradation point appears, leave percentage automation disabled.
6. Re-run the calibration after a material model/runtime change or when real sessions contradict
   the stored threshold.

## Non-claims

- This decision does not claim that long context is harmless.
- It does not claim that compaction preserves all relevant information.
- It does not choose one threshold for Claude, Codex, or any named model family.
- It does not automate session rollover; the hook only asks the current agent to preserve state.
