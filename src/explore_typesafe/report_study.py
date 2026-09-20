"""Report pages for the expanded study (results/evaluation2.json): generated cases,
S2 decomposition, S4 note search, S5 features, and the Claude Haiku baseline."""

from __future__ import annotations

import json

from .common import RESULTS_DIR
from .report_example import api_example

RUNS_LABEL = {"s1_ward_gen": "1. Ward", "s2_discharge_gen": "2. Discharge", "s3_inbox_gen": "3. Inbox"}


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(" --- " for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _metric(q: dict, split: str) -> str:
    m = q.get(split)
    if not m:
        return "–"
    if q["type"] == "Noul":
        return f"{pct(m['accuracy'])}"
    if q["type"] == "Score":
        return f"{pct(m['exact'])} · MAE {m['mae']:.2f}"
    return pct(m["accuracy"])


def _max_questions(run: str) -> int:
    return max(len(c["questions"]) for c in json.loads((RESULTS_DIR / f"{run}.json").read_text())["cases"])


def page_generated(e: dict) -> str:
    rows = []
    for run, qs in e["questions"].items():
        for qid, q in qs.items():
            t = e["tuning"][run].get(qid)
            tuned = f"{pct(t['test_tuned'])} @ {t['threshold']:.2f}" if t else "–"
            rows.append([RUNS_LABEL[run], f"`{qid}`", q["type"], _metric(q, "dev"), _metric(q, "test"), tuned])
    s1 = e["s1_policy"]
    s2 = e["s2_policy"]
    s3 = e["s3_gate"]
    s2_rows = [[v, *(f"{pct(s2[sp][v]['action'])} · {s2[sp][v]['missed_holds']} missed / {s2[sp][v]['false_holds']} false holds"
                     for sp in ("hand", "gen_dev", "gen_test"))] for v in ("v1", "v2", "v2.1")]
    flag_rows = [[v, f"`{f}`", *(f"{pct(s2[sp][v]['flags'][f]['accuracy'])} ({s2[sp][v]['flags'][f]['fp']} FP, {s2[sp][v]['flags'][f]['fn']} FN)"
                                 for sp in ("hand", "gen_dev", "gen_test"))]
                 for v in ("v1", "v2", "v2.1") for f in ("allergy_conflict", "duplicate_therapy", "interaction")]
    p = e["perf"]
    return f"""# Generated cases (dev/test)

Twenty hand-written cases per scenario are enough to show behaviour but too few to measure it. For each of scenarios 1–3, **80 more cases** were generated from the 1,000-patient cohort, with **reference labels known by construction** rather than judged:

- **Ward:** notes are assembled from labelled snippets (a driver that sets concern and pattern, a mental-state snippet, an infection snippet), and vital signs are drawn to match.
- **Discharge:** the plan is built in code from per-medication actions, new drugs, reasons and phrasing variants. Allergy, duplicate and interaction labels are computed from the final regimen using class and interaction tables.
- **Inbox:** messages combine a labelled intent with optional benign add-ons, tone variants and a prompt-injection prefix that must not change the labels.

Cases are split 50/50 into **dev** (used for threshold tuning) and **test** (used only for reporting). The labels and splits were committed before any model saw these cases. The generator is [`generate.py`](https://github.com/si618/explore-typesafe-ai/blob/main/src/explore_typesafe/generate.py).

## Per-question results

Noul accuracy is at the default 0.5 threshold. The last column is test accuracy at the threshold that maximised **dev** accuracy.

{table(['Scenario', 'Question', 'Primitive', 'Dev', 'Test', 'Test, dev-tuned threshold'], rows)}

The tuned thresholds are informative in their own right. `safeguarding` wants 0.85 and `red_flag` 0.75: Jev leans towards yes on these, and a higher bar fixes most of the over-calling (safeguarding goes from {pct(e['tuning']['s3_inbox_gen']['safeguarding']['test_at_0.5'])} to {pct(e['tuning']['s3_inbox_gen']['safeguarding']['test_tuned'])} on test). `interaction` still tops out at {pct(e['tuning']['s2_discharge_gen']['interaction']['test_tuned'])}: no threshold rescues a multi-hop question.

## Scenario policies

**Ward:** under-triage against the reference band, NEWS2 alone vs NEWS2 + Jev.

{table(['Split', 'Cases', 'NEWS2 only: under-triaged', 'NEWS2 + Jev: under-triaged', 'NEWS2 + Jev: over-triaged', 'NEWS2 + Jev: band exact'],
       [[sp, s1[sp]['n'], s1[sp]['news2_only_under'], s1[sp]['combined_under'], s1[sp]['combined_over'], pct(s1[sp]['combined_exact'])] for sp in ('dev', 'test')])}

The hand-case result holds: NEWS2 alone under-triages about half the patients, because the generated notes (like real ones) carry the decisive signal in text. On test, NEWS2 + Jev still under-triages {s1['test']['combined_under']} of {s1['test']['n']}. Every one is a concern Score one level low, with no confusion misses. Five are *routine* instead of *ward review*, and two are *urgent* instead of *emergency*.

**Inbox:** the confidence gate (route confidence ≥ {s3['default_gate']}, red flag outside 0.2–0.8, route and urgency agree, no safeguarding flag) auto-dispatched {s3['dev_default']['auto']}/40 dev and {s3['test_default']['auto']}/40 test messages, all routed correctly ({pct(s3['test_default']['auto_accuracy'])}). The rest go to review. Overall route accuracy is {pct(s3['route_accuracy']['test'])} on test.

## Discharge: decomposing the weak checks

In v1, a single Noul asks "is there a duplicate?" or "is there an interaction?" over the whole regimen. That is several hops at once, which the [Jev jaggedness notes](https://docs.typesafe.ai/model-jaggedness/jev-1.13) flag as unreliable. v2 asks each hop as its own narrow question in the same request, and code aggregates:

- one Choice per medication for its **therapeutic class**; duplicates are counted in code;
- new-drug candidates are found by exact formulary lookup in code, then one Noul per candidate asks whether it is **prescribed after discharge**;
- one Noul per *(new drug, other drug)* pair for **interactions**, and one per *(drug, drug allergy)* pair for **allergy class**.

A v2 request carries up to {_max_questions('s2_discharge_gen_v2')} questions, and p50 latency is still {p['s2_discharge_gen_v2']['p50_ms']} ms.

{table(['Version', 'Hand (20)', 'Generated dev (40)', 'Generated test (40)'], s2_rows)}

v2 fixed the false holds but introduced **missed holds**. Its "new drug" Noul asked two things at once (is it prescribed, *and* was it absent before admission?). Code already guarantees the second, and asking again made Jev answer no for plainly new drugs, which switched off the downstream checks. **v2.1** asks only what code can't know ("does the text tell the patient to take X after discharge?").

!!! warning "v2.1 is not a clean held-out result"
    v2.1 is one revision made after seeing v2's results on every split, including test. It was committed before it ran, but no split is untouched by the design, so treat its numbers as optimistic. The remaining weakness shows on every split: the pairwise interaction Nouls still over-call.

??? note "Per-flag accuracy by version"

{chr(10).join('    ' + l for l in table(['Version', 'Flag', 'Hand', 'Generated dev', 'Generated test'], flag_rows).splitlines())}
"""


def page_s4(e: dict) -> str:
    s4, notes, sens = e["s4"], e["s4_notes"], e["s4_sensitivity"]
    h = e["haiku"].get("s4_search", {}).get("haiku")
    return f"""# 4. Semantic search over notes

**Setting:** a clinician asks a plain-language question ("has this patient ever had a heart attack?") and the system searches the patient's 10 most recent clinical notes (Synthea text, FHIR R5 `DocumentReference`).

**Why this scenario:** retrieval is one of the task categories in the TypeSafe docs, and the notes use clinical vocabulary ("myocardial infarction") that the lay question doesn't. A keyword search for the lay words is the naive baseline.

**Cases:** 12 queries × 25 patients (about half positive), **{s4['cases']} searches over {s4['notes_judged']:,} notes**.

**Ground truth (objective, by regex):** a note is relevant if a Synthea `(disorder)` phrase in it matches the clinical term. No model wrote these labels.

| Question per search | Primitive | Task category |
| --- | --- | --- |
| Does `notes[i]` show the answer is yes? (one per note) | Noul ×10 | Search / Retrieval |
| Which note is the best evidence? | Choice (10 notes + none) | Ranking |
| Taking all notes together, is the answer yes? | Noul | Detection |

{api_example('s4_search', module='s4_search', keep=['note_0', 'best', 'any'], text_chars=240, max_items=2,
             intro='One search: the query, the ten notes, and a Noul per note plus the two whole-patient questions.')}
## Results

| Method | Note precision | Note recall | Note F1 |
| --- | --- | --- | --- |
| Lay keyword search | {pct(s4['lay_keyword_note_level']['precision'])} | {pct(s4['lay_keyword_note_level']['recall'])} | {s4['lay_keyword_note_level']['f1']:.2f} |
| Jev, all 10 notes in one request | {pct(s4['note_level']['precision'])} | {pct(s4['note_level']['recall'])} | {s4['note_level']['f1']:.2f} |
| Jev, one note per request | {pct(notes['note_level']['precision'])} | {pct(notes['note_level']['recall'])} | {notes['note_level']['f1']:.2f} |""" + (f"""
| Claude Haiku 4.5, all 10 notes in one request | {pct(h['note_level']['precision'])} | {pct(h['note_level']['recall'])} | {h['note_level']['f1']:.2f} |""" if h else "") + f"""

| Patient-level answer | Accuracy | Precision | Recall |
| --- | --- | --- | --- |
| "Any" Noul over all notes | {pct(s4['patient_any_noul']['accuracy'])} | {pct(s4['patient_any_noul']['precision'])} | {pct(s4['patient_any_noul']['recall'])} |
| Max of per-note Nouls (all-in-one request) | {pct(s4['patient_from_notes']['accuracy'])} | {pct(s4['patient_from_notes']['precision'])} | {pct(s4['patient_from_notes']['recall'])} |
| Max of per-note Nouls (one note per request) | {pct(notes['patient_from_notes']['accuracy'])} | {pct(notes['patient_from_notes']['precision'])} | {pct(notes['patient_from_notes']['recall'])} |

The best-evidence Choice picked a relevant note (or correctly said *none*) in **{pct(s4['best_note_choice_accuracy'])}** of searches. Jev bridges lay and clinical vocabulary almost perfectly: recall is about 100% against the keyword baseline's {pct(s4['lay_keyword_note_level']['recall'])}.

## The "false positives" are mostly label gaps

Note-level precision looks modest, and isolating each note in its own request made it *worse* ({pct(s4['note_level']['precision'])} → {pct(notes['note_level']['precision'])}). The hypothesis being tested was that one note's evidence leaks into judgments of the others. Inspecting the per-note false positives doesn't support it: **{sens['per_note']['false_positives_with_strong_evidence']} of {sens['per_note']['strict_false_positives']}** show the condition through its treatment or an explicit statement. The regex can't see those, because it only reads `(disorder)` phrases. Examples include metformin or insulin for diabetes, an ACE inhibitor or thiazide for high blood pressure, donepezil for dementia, and "a documented history of opioid addiction".

Re-scoring with those notes counted as relevant (a **post-hoc** sensitivity analysis; the patterns are in [`evaluate2.py`](https://github.com/si618/explore-typesafe-ai/blob/main/src/explore_typesafe/evaluate2.py)):

| Variant | Strict labels: P / R | Strong-evidence labels: P / R |
| --- | --- | --- |
| All 10 notes in one request | {pct(sens['all_in_one']['strict']['precision'])} / {pct(sens['all_in_one']['strict']['recall'])} | {pct(sens['all_in_one']['strong_evidence']['precision'])} / {pct(sens['all_in_one']['strong_evidence']['recall'])} |
| One note per request | {pct(sens['per_note']['strict']['precision'])} / {pct(sens['per_note']['strict']['recall'])} | {pct(sens['per_note']['strong_evidence']['precision'])} / {pct(sens['per_note']['strong_evidence']['recall'])} |

Both variants are about 98.5% precise. They differ in **recall of indirect evidence**: judged alone, a note that only lists metformin is recognised as showing diabetes ({sens['per_note']['label_gap_jev_yes']} of {sens['per_note']['label_gap_notes']} such notes). With ten notes in the state, more of those are missed. Isolation costs {notes['perf']['wall_seconds'] / s4['perf']['wall_seconds']:.0f}× the wall time and {notes['perf']['input_tokens'] / s4['perf']['input_tokens']:.2f}× the tokens (${notes['perf']['cost_usd']:.3f} vs ${s4['perf']['cost_usd']:.3f}), and it only matters if "treated for X" should count as "has X".
"""


def page_s5(e: dict) -> str:
    s5 = e["s5"]
    m = s5["models"]
    uni = sorted(s5["univariate_auroc"].items(), key=lambda kv: -kv[1])
    return f"""# 5. Jev judgments as ML features

**Setting:** predict which patients will have an **emergency or inpatient encounter in the next 12 months**, for all {s5['n']:,} patients in the cohort, as of an index date of 2025-09-19.

**Why this scenario:** the TypeSafe docs describe using typed judgments as **features for classical ML**. This tests that pattern where the outcome comes from Synthea's simulated encounters, so no model wrote the labels ({s5['positives']} positives, {pct(s5['positives'] / s5['n'])}).

| Feature set | Features | Cross-validated AUROC (mean ± sd) |
| --- | --- | --- |
| Structured: age, sex, chronic disorder count, medication count, prior-year acute use | {m['structured']['features']} | {m['structured']['auroc_mean']:.3f} ± {m['structured']['auroc_sd']:.3f} |
| Jev: 10 typed judgments over the most recent note before the index date | {m['jev']['features']} | {m['jev']['auroc_mean']:.3f} ± {m['jev']['auroc_sd']:.3f} |
| Structured + Jev | {m['structured+jev']['features']} | {m['structured+jev']['auroc_mean']:.3f} ± {m['structured+jev']['auroc_sd']:.3f} |

Logistic regression, 5-fold stratified cross-validation repeated 5 times.

## Reading this honestly

- **Jev features from one note match the structured baseline** (AUROC {m['jev']['auroc_mean']:.2f} vs {m['structured']['auroc_mean']:.2f}), and together they add only **{m['structured+jev']['auroc_mean'] - m['structured']['auroc_mean']:+.3f}**. That is a small gain.
- **The ceiling is Synthea, not the features.** Synthea's acute encounters are driven by stochastic disease modules, so every feature set sits near 0.64. This synthetic outcome can't show whether Jev features would help on real utilisation data. It can show the mechanics: {s5['perf']['requests']:,} notes × 10 questions in {s5['perf']['wall_seconds']:.0f} s for ${s5['perf']['cost_usd']:.3f}.
- **The strongest single features** are the Score for overall clinical burden (AUROC {s5['univariate_auroc']['burden']:.2f}) and the cardiovascular Noul ({s5['univariate_auroc']['cardiovascular']:.2f}).

??? note "Univariate AUROC of every Jev feature"

{chr(10).join('    ' + l for l in table(['Feature', 'AUROC'], [[f'`{k}`', f'{v:.3f}'] for k, v in uni]).splitlines())}

{api_example('s5_features', '7d27b12f', module='s5_features', text_chars=500,
             keep=['burden', 'diabetes_complications', 'mental_health'],
             intro='One patient\'s most recent note before the index date, turned into ten numeric features.')}
"""


def page_haiku(e: dict) -> str:
    h = e["haiku"]
    rows = []
    for run in ("s1_ward", "s2_discharge", "s3_inbox", "s1_ward_gen", "s2_discharge_gen", "s3_inbox_gen"):
        if run not in h:
            continue
        split = "hand" if not run.endswith("_gen") else "test"
        for qid, q in h[run]["jev"].items():
            hq = h[run]["haiku"].get(qid, {})
            rows.append([f"{RUNS_LABEL.get(run, RUNS_LABEL.get(run + '_gen'))} ({split})", f"`{qid}`", q["type"],
                         _metric(q, split), _metric(hq, split) if hq else "–"])
    perf_rows = []
    for run, v in h.items():
        hp, jp = v.get("haiku_perf"), v.get("jev_perf")
        if not hp or not jp:
            continue
        perf_rows.append([run.replace("_", " "), hp["requests"], f"{jp['p50_ms']} / {hp['p50_ms']}", f"{jp['p95_ms']} / {hp['p95_ms']}",
                          f"${jp['cost_usd']:.4f} / ${hp['cost_usd']:.4f}", f"{hp['cost_usd'] / jp['cost_usd']:.0f}×"])
    s4h = h.get("s4_search", {})
    return f"""# Jev vs an LLM baseline

To put Jev's accuracy in context, the same states and questions were answered by **Claude Haiku 4.5**, which you might otherwise use for a classification step. Each request was a headless Claude Code call with no tools, a minimal system prompt and extended thinking disabled. Haiku returned the same typed answer space as JSON (a probability for Nouls, an option and confidence for Choices, a level and confidence for Scores).

## Accuracy

Hand cases, and the **test** split of the generated cases:

{table(['Scenario', 'Question', 'Primitive', 'Jev', 'Haiku 4.5'], rows)}""" + (f"""

Note search (note-level F1): Jev {s4h['jev']['note_level']['f1']:.2f}, Haiku {s4h['haiku']['note_level']['f1']:.2f}.""" if s4h else "") + f"""

The two models are **close on most questions**, and neither dominates:

- **Haiku is stronger** on routing and on the questions where Jev over-calls (inbox route, safeguarding, discharge interactions).
- **Jev is stronger** on high-volume extraction over the generated plans (per-medication status {_metric(h['s2_discharge_gen']['jev']['med_status'], 'test')} vs {_metric(h['s2_discharge_gen']['haiku']['med_status'], 'test')}), on the infection and allergy checks, on grading justifications, and on note search.

## Latency and cost

{table(['Run', 'Requests', 'p50 ms (Jev / Haiku)', 'p95 ms (Jev / Haiku)', 'Cost (Jev / Haiku)', 'Haiku cost multiple'], perf_rows)}

Haiku latency is the API time reported by the CLI (`duration_api_ms`), which excludes CLI start-up. Its cost is the CLI's list-price estimate, including prompt-cache writes. Haiku token counts aren't compared: the runner recorded only uncached input tokens (as few as 3 for a request carrying ten notes), so they understate Haiku's real input.

**The trade-off:** Jev answers in a fifth to an eighth of the time, at 1/40th to 1/60th of the cost, with lower accuracy on some judgments and higher on others. That suits the architecture used throughout this report: Jev for every judgment, and a reasoning model only for the uncertain slice.
"""
