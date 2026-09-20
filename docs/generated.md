# Generated cases (dev/test)

Twenty hand-written cases per scenario are enough to show behaviour but too few to measure it. For each of scenarios 1–3, **80 more cases** were generated from the 1,000-patient cohort, with **[reference labels](vocabulary.md#reference-label) known by construction** rather than judged:

- **Ward:** notes are assembled from labelled snippets (a driver that sets concern and pattern, a mental-state snippet, an infection snippet), and vital signs are drawn to match.
- **Discharge:** the plan is built in code from per-medication actions, new drugs, reasons and phrasing variants. Allergy, duplicate and [interaction](vocabulary.md#interaction) labels are computed from the final regimen using class and interaction tables.
- **Inbox:** messages combine a labelled intent with optional benign add-ons, tone variants and a prompt-injection prefix that must not change the labels.

Cases are split 50/50 into **dev** (used for threshold tuning) and **test** (used only for reporting). The labels and splits were committed before any model saw these cases. The generator is [`generate.py`](https://github.com/si618/explore-typesafe-ai/blob/main/src/explore_typesafe/generate.py).

## Per-question results

[Noul](vocabulary.md#noul) accuracy is at the default 0.5 threshold. The last column is test accuracy at the threshold that maximised **dev** accuracy.

| Scenario | Question | [Primitive](vocabulary.md#primitive) | Dev | Test | Test, dev-tuned threshold |
| --- | --- | --- | --- | --- | --- |
| 1. Ward | `new_confusion` | Noul | 95% | 95% | 98% @ 0.80 |
| 1. Ward | `infection` | Noul | 98% | 100% | 100% @ 0.55 |
| 1. Ward | `concern` | [Score](vocabulary.md#score) | 90% · [MAE](vocabulary.md#mae) 0.14 | 78% · MAE 0.25 | – |
| 1. Ward | `pattern` | [Choice](vocabulary.md#choice) | 95% | 92% | – |
| 2. Discharge | `med_status` | Choice | 99% | 98% | – |
| 2. Discharge | `allergy_conflict` | Noul | 100% | 100% | 100% @ 0.50 |
| 2. Discharge | `duplicate_therapy` | Noul | 88% | 85% | 90% @ 0.70 |
| 2. Discharge | `interaction` | Noul | 70% | 68% | 80% @ 0.75 |
| 2. Discharge | `justification` | Score | 60% · MAE 0.55 | 60% · MAE 0.47 | – |
| 3. Inbox | `route` | Choice | 85% | 85% | – |
| 3. Inbox | `urgency` | Score | 80% · MAE 0.24 | 80% · MAE 0.22 | – |
| 3. Inbox | `red_flag` | Noul | 85% | 82% | 95% @ 0.75 |
| 3. Inbox | `medication_issue` | Noul | 100% | 95% | 95% @ 0.50 |
| 3. Inbox | `safeguarding` | Noul | 78% | 72% | 95% @ 0.85 |

The tuned thresholds are informative in their own right. `safeguarding` wants 0.85 and `red_flag` 0.75: [Jev](vocabulary.md#jev) leans towards yes on these, and a higher bar fixes most of the over-calling ([safeguarding](vocabulary.md#safeguarding) goes from 72% to 95% on test). `interaction` still tops out at 80%: no threshold rescues a multi-hop question.

## Scenario policies

**Ward:** [under-triage](vocabulary.md#under-triage) against the reference band, [NEWS2](vocabulary.md#news2) alone vs NEWS2 + Jev.

| Split | Cases | NEWS2 only: under-triaged | NEWS2 + Jev: under-triaged | NEWS2 + Jev: [over-triaged](vocabulary.md#over-triage) | NEWS2 + Jev: band exact |
| --- | --- | --- | --- | --- | --- |
| dev | 40 | 23 | 3 | 1 | 90% |
| test | 40 | 22 | 8 | 1 | 78% |

The hand-case result holds: NEWS2 alone under-triages about half the patients, because the generated notes (like real ones) carry the decisive signal in text. On test, NEWS2 + Jev still under-triages 8 of 40. Every one is a concern Score one level low, with no confusion misses. Five are *routine* instead of *ward review*, and two are *urgent* instead of *emergency*.

**Inbox:** the [confidence gate](vocabulary.md#confidence-gate) (route [confidence](vocabulary.md#confidence) ≥ 0.6, red flag outside 0.2–0.8, route and urgency agree, no safeguarding flag) auto-dispatched 24/40 dev and 16/40 test messages, all routed correctly (100%). The rest go to review. Overall route accuracy is 85% on test.

## Discharge: decomposing the weak checks

In v1, a single Noul asks "is there a duplicate?" or "is there an interaction?" over the whole regimen. That is several hops at once, which the [Jev jaggedness notes](https://docs.typesafe.ai/model-jaggedness/jev-1.13) flag as unreliable. v2 asks each hop as its own narrow question in the same request, and code aggregates:

- one Choice per medication for its **therapeutic class**; duplicates are counted in code;
- new-drug candidates are found by exact formulary lookup in code, then one Noul per candidate asks whether it is **prescribed after discharge**;
- one Noul per *(new drug, other drug)* pair for **interactions**, and one per *(drug, drug allergy)* pair for **allergy class**.

A v2 request carries up to 71 questions, and [p50](vocabulary.md#p50) latency is still 337 ms.

| Version | Hand (20) | Generated dev (40) | Generated test (40) |
| --- | --- | --- | --- |
| v1 | 55% · 0 missed / 8 false holds | 95% · 0 missed / 2 false holds | 85% · 0 missed / 4 false holds |
| v2 | 75% · 2 missed / 2 false holds | 70% · 12 missed / 0 false holds | 75% · 9 missed / 0 false holds |
| v2.1 | 70% · 0 missed / 6 false holds | 100% · 0 missed / 0 false holds | 95% · 0 missed / 1 false holds |

v2 fixed the false holds but introduced **missed holds**. Its "new drug" Noul asked two things at once (is it prescribed, *and* was it absent before admission?). Code already guarantees the second, and asking again made Jev answer no for plainly new drugs, which switched off the downstream checks. **v2.1** asks only what code can't know ("does the text tell the patient to take X after discharge?").

!!! warning "v2.1 is not a clean held-out result"
    v2.1 is one revision made after seeing v2's results on every split, including test. It was committed before it ran, but no split is untouched by the design, so treat its numbers as optimistic. The remaining weakness shows on every split: the pairwise interaction Nouls still over-call.

??? note "Per-flag accuracy by version"

    | Version | Flag | Hand | Generated dev | Generated test |
    | --- | --- | --- | --- | --- |
    | v1 | `allergy_conflict` | 100% (0 FP, 0 FN) | 100% (0 FP, 0 FN) | 100% (0 FP, 0 FN) |
    | v1 | `duplicate_therapy` | 70% (6 FP, 0 FN) | 88% (4 FP, 1 FN) | 85% (6 FP, 0 FN) |
    | v1 | `interaction` | 75% (5 FP, 0 FN) | 70% (12 FP, 0 FN) | 68% (13 FP, 0 FN) |
    | v2 | `allergy_conflict` | 90% (0 FP, 2 FN) | 90% (1 FP, 3 FN) | 85% (0 FP, 6 FN) |
    | v2 | `duplicate_therapy` | 90% (2 FP, 0 FN) | 88% (0 FP, 5 FN) | 90% (0 FP, 4 FN) |
    | v2 | `interaction` | 100% (0 FP, 0 FN) | 68% (1 FP, 12 FN) | 88% (1 FP, 4 FN) |
    | v2.1 | `allergy_conflict` | 100% (0 FP, 0 FN) | 98% (1 FP, 0 FN) | 100% (0 FP, 0 FN) |
    | v2.1 | `duplicate_therapy` | 75% (5 FP, 0 FN) | 100% (0 FP, 0 FN) | 95% (1 FP, 1 FN) |
    | v2.1 | `interaction` | 75% (5 FP, 0 FN) | 78% (9 FP, 0 FN) | 72% (11 FP, 0 FN) |
