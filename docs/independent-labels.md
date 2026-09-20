# Independent reference labels

[Issue #1](https://github.com/si618/explore-typesafe-ai/issues/1) identified a circularity risk: Claude authored the hand cases and
labels, and a Claude reviewer judged [Jev](vocabulary.md#jev)'s uncertain answers. This page checks the
reference against a blind sample of **15 cases per scenario** (302 typed
judgments), labelled by a different model family. The sample favours cases marked
[ambiguous](vocabulary.md#ambiguous) and cases where Jev and the reference disagree, so it is harder than the
full set.

!!! danger "Correction"
    The first version of this page ([PR #2](https://github.com/si618/explore-typesafe-ai/pull/2)) reported κ = 1.00 on every
    question type. Those labels were not independent: a script had copied the reference
    labels into `labels.json`. They were replaced by the isolated run described below
    ([PR #4](https://github.com/si618/explore-typesafe-ai/pull/4)).

## Agreement

| Question type | Judgments | Reference vs independent κ | Jev vs independent κ | Jev vs reference κ | Reference ≠ independent |
| --- | --- | --- | --- | --- | --- |
| [Noul](vocabulary.md#noul) | 120 | 0.73 | 0.77 | 0.61 | 14 |
| [Choice](vocabulary.md#choice) | 137 | 0.94 | 0.89 | 0.88 | 5 |
| [Score](vocabulary.md#score) | 45 | 0.80 | 0.86 | 0.80 | 15 |

κ is unweighted for Nouls and Choices, and quadratic weighted κ for Scores. Where
the reference accepts several answers, any of them counts as agreement, as in the
main evaluation. Jev's Nouls use the 0.5 threshold and its Scores are rounded.

**The independent labels and the reference differ on 34 of 302 judgments.
In 24 of them Jev gave the independent label's answer, and in 9 the
reference's.** So some of what this report counts as Jev errors on these cases may be
reference errors. On Nouls and Scores, Jev agrees with the independent labeller more
than the reference does. Treat that as a lead, not a rate: the sample was chosen partly
for Jev/reference disagreement, which makes this pattern more likely than it would be
across all cases.

| Scenario | Question | Disagreements | Jev = independent | Jev = reference |
| --- | --- | --- | --- | --- |
| 2. Discharge | `justification` | 11 | 7 | 3 |
| 2. Discharge | `duplicate_therapy` | 7 | 5 | 2 |
| 2. Discharge | `med_status` | 4 | 2 | 2 |
| 1. Ward | `infection` | 2 | 2 | 0 |
| 1. Ward | `concern` | 2 | 1 | 1 |
| 2. Discharge | `interaction` | 2 | 2 | 0 |
| 3. Inbox | `safeguarding` | 2 | 2 | 0 |
| 3. Inbox | `urgency` | 2 | 2 | 0 |
| 1. Ward | `new_confusion` | 1 | 0 | 1 |
| 3. Inbox | `route` | 1 | 1 | 0 |

Most disagreements are in discharge [reconciliation](vocabulary.md#medication-reconciliation): how well medication changes are
justified (a Score where adjacent levels are close calls) and whether a regimen
contains [duplicate therapy](vocabulary.md#duplicate-therapy). These are the questions where a pharmacist's view
matters most.

??? note "All 34 disagreements"
    | Judgment | Reference | Independent | Jev |
    | --- | --- | --- | --- |
    | `s1_ward/2030b2b1/infection` | `True` | `False` | `False` |
    | `s1_ward/2030b2b1/concern` | `3` | `2` | `3` |
    | `s1_ward/ff269b67/infection` | `False` | `True` | `True` |
    | `s1_ward/8853bb83/concern` | `1` | `0` | `0` |
    | `s1_ward/67d3388a/new_confusion` | `False` | `True` | `False` |
    | `s2_discharge/011fd88e/duplicate_therapy` | `False` | `True` | `True` |
    | `s2_discharge/011fd88e/interaction` | `False` | `True` | `True` |
    | `s2_discharge/011fd88e/justification` | `2` | `1` | `1` |
    | `s2_discharge/c9fb242a/med_4` | `continued` | `dose_changed` | `continued` |
    | `s2_discharge/c9fb242a/justification` | `1` | `2` | `2` |
    | `s2_discharge/e2aaac15/justification` | `3` | `2` | `2` |
    | `s2_discharge/0d650f96/duplicate_therapy` | `False` | `True` | `False` |
    | `s2_discharge/397d83f9/med_1` | `continued` | `dose_changed` | `dose_changed` |
    | `s2_discharge/397d83f9/duplicate_therapy` | `False` | `True` | `False` |
    | `s2_discharge/397d83f9/interaction` | `False` | `True` | `True` |
    | `s2_discharge/397d83f9/justification` | `3` | `2` | `2` |
    | `s2_discharge/7608e330/justification` | `2` | `3` | `3` |
    | `s2_discharge/18625cef/med_2` | `continued` | `dose_changed` | `continued` |
    | `s2_discharge/18625cef/justification` | `0` | `1` | `1` |
    | `s2_discharge/3699ce0c/justification` | `1` | `3` | `2` |
    | `s2_discharge/4036a737/justification` | `3` | `2` | `3` |
    | `s2_discharge/5f37c925/duplicate_therapy` | `False` | `True` | `True` |
    | `s2_discharge/6ab723fc/justification` | `2` | `1` | `1` |
    | `s2_discharge/9dd09d0d/duplicate_therapy` | `False` | `True` | `True` |
    | `s2_discharge/bb6aff77/med_5` | `continued` | `dose_changed` | `dose_changed` |
    | `s2_discharge/bb6aff77/duplicate_therapy` | `False` | `True` | `True` |
    | `s2_discharge/bb6aff77/justification` | `3` | `2` | `3` |
    | `s2_discharge/e650d645/duplicate_therapy` | `False` | `True` | `True` |
    | `s2_discharge/e650d645/justification` | `1` | `2` | `1` |
    | `s3_inbox/1f0fae32/safeguarding` | `False` | `True` | `True` |
    | `s3_inbox/1b09bfb3/route` | `['nurse_callback', 'pharmacist']` | `on_call_clinician` | `on_call_clinician` |
    | `s3_inbox/1b09bfb3/urgency` | `1` | `2` | `2` |
    | `s3_inbox/1b09bfb3/safeguarding` | `False` | `True` | `True` |
    | `s3_inbox/5e96d8dc/urgency` | `0` | `1` | `1` |

The disagreements have **not been adjudicated**, and the pre-registered labels are
unchanged. A Claude adjudicator would bring back the circularity this check is for,
so that step is left for a clinician or pharmacist, tracked in
[issue #5](https://github.com/si618/explore-typesafe-ai/issues/5).

## How the labels were produced

- **Labeller:** Codex CLI 0.155.1, model gpt-5.6-luna (reasoning effort medium), 2026-09-19. Not a clinician or pharmacist.
- **Isolation:** each chunk of 5 cases ran in a bubblewrap sandbox whose only project
  content was that chunk, with a fresh Codex home (no session history), web search,
  browser, apps and computer use off, and Codex's own read-only sandbox.
- **Audit:** the full Codex event log is committed. It contains only the answer
  messages: no tool calls, file reads or web access.

The packet, labels, prompt, sandbox script, event logs and scorer live in
[`data/independent_labels/`](https://github.com/si618/explore-typesafe-ai/tree/main/data/independent_labels).
This is a model-family check, not clinical validation.
