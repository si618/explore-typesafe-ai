# Independent labels

`packet.json` is a stratified sample of 15 cases per scenario. It contains the
state and typed question only: it intentionally omits Jev answers and the
pre-registered reference labels.

The labeler writes `labels.json` as an object keyed by packet `id`, with values
matching `answer_format` (`true`/`false`, a choice key, or an integer score).
The provenance below records the label source and date; it must be updated when
the packet is labelled. Run:

```bash
uv run python -m explore_typesafe.independent_labels
```

The current sample was independently reviewed by Codex (GPT-5), 2026-09-19,
using only `packet.json`. This is a different model family from the Claude
models that authored the scenarios and original labels, but it is not a
clinician review and must not be described as clinical validation.
