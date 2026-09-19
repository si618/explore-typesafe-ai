# Independent labels

`packet.json` is a stratified sample of 15 cases per scenario, favouring cases
marked ambiguous and cases where Jev and the reference disagree. It contains the
state and typed question only: no Jev answers and no reference labels.

`labels.json` maps each packet `id` to an answer matching `answer_format`
(`true`/`false`, a choice key, or a 0-based score level). `provenance.json`
records who or what produced it and how it was isolated; `codex_run/` holds the
prompt, sandbox script, Codex config and the full event log of the run.

```bash
uv run python -m explore_typesafe.independent_labels
```

writes `agreement.json` (κ per question type: reference, independent and Jev,
pairwise) and `disagreements.json` (every judgment where the independent label
and the reference differ, with Jev's answer). Where the reference accepts several
answers, any of them counts as agreement, as in `evaluate.py`.

Disagreements are published alongside the pre-registered labels, not merged
into them. They have not been adjudicated: the only labellers so far are models,
and a Claude adjudicator would reintroduce the circularity this check is for.

The labeller is a different model family from the Claude models that authored
the scenarios and reference labels, but this is not a clinician review and must
not be described as clinical validation.
