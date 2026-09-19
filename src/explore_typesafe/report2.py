"""Pages for the extended study, rendered from results/evaluation2.json."""

from __future__ import annotations

import json

from .common import RESULTS_DIR, load_scenario
from .report import pct, table
from .s4_search import QUERIES
from .s5_features import QUESTIONS as S5_QUESTIONS


def _fmt(x) -> str:
    return "–" if x is None else pct(x)


def _q_rows(jev: dict, haiku: dict | None, split: str) -> list[list]:
    rows = []
    for fam, d in jev.items():
        if split not in d:
            continue
        j = d[split]
        metric = lambda x: (f"{pct(x['accuracy'])}" if "accuracy" in x else f"{pct(x['exact'])} (MAE {x['mae']:.2f})")
        row = [f"`{fam}`", d["type"], j["n"], metric(j)]
        if haiku is not None:
            row.append(metric(haiku[fam][split]))
        rows.append(row)
    return rows


def page_scale(e: dict) -> str:
    q, t, p1, g3 = e["questions"], e["tuning"], e["s1_policy"], e["s3_gate"]
    tune_rows = [[f"`{run.removesuffix('_gen')}`", f"`{qid}`", f"{v['threshold']:.2f}", pct(v["dev_at_0.5"]), pct(v["dev_tuned"]),
                  pct(v["test_at_0.5"]), f"**{pct(v['test_tuned'])}**"]
                 for run, d in t.items() for qid, v in d.items()]
    gen_rows = []
    for run in ("s1_ward_gen", "s2_discharge_gen", "s3_inbox_gen"):
        for fam, d in q[run].items():
            m = lambda x: pct(x["accuracy"]) if "accuracy" in x else f"{pct(x['exact'])} (MAE {x['mae']:.2f})"
            gen_rows.append([run.removesuffix("_gen"), f"`{fam}`", d["type"], m(d["dev"]), m(d["test"])])
    return f"""# Scaling up: generated cases

The original scenarios have 20 hand-authored cases each, so one case moves a percentage by five points. Each scenario now also has **80 generated cases** built from labelled parts, drawn from the 900 new patients in the [1,000-patient cohort](data.md), and split **40 dev / 40 test**. Thresholds are tuned on dev and reported on test.

| Scenario | How a generated case is built | Where the label comes from |
| --- | --- | --- |
| Ward | A note from three snippet types: a *driver* (sets concern and pattern), a *mental-state* snippet (new, baseline, negated or none) and an *infection* snippet (active, treated, negated or none). Vital signs are drawn to match the driver; "soft" drivers such as a stroke keep NEWS2 low. | Composition rules over the snippet labels |
| Discharge | Code picks an action per FHIR medication (continue, blanket-continue, change, withhold, stop, omit), adds new drugs (sometimes deliberately conflicting), and writes the plan with brand names, abbreviations and blanket statements. | **Computed**: a drug-class, allergy-class and interaction table applied to the final regimen |
| Inbox | A labelled intent (32 kinds), plus an optional add-on, a tone (capitals, understated, "URGENT!!!") and, in 8% of messages, a prompt-injection prefix that must not change the answer. | The intent's labels |

Discharge labels are the most independent: no model judged them. The ward and inbox snippets were still written by Claude, so [issue #1](https://github.com/si618/explore-typesafe-ai/issues/1) (independent labels) still applies.

## Results by split

{table(['Scenario', 'Question', 'Primitive', 'dev', 'test'], gen_rows)}

Dev and test agree closely, which suggests the hand-authored results were not a fluke of 20 cases. The pattern holds:
- **Strong:** extraction (`med_status` 98–99%), infection, new confusion and allergy checks.
- **Weak:** interaction (about 70%), Score answers that need judgment (discharge justification 60%), and safeguarding (72% on test).

## Ward policy at scale

| Split | n | NEWS2 only: band exact | NEWS2 only: under-triaged | NEWS2 + Jev: band exact | NEWS2 + Jev: under-triaged |
| --- | --- | --- | --- | --- | --- |
| dev | {p1['dev']['n']} | {pct(p1['dev']['news2_only_exact'])} | {p1['dev']['news2_only_under']} | {pct(p1['dev']['combined_exact'])} | {p1['dev']['combined_under']} |
| test | {p1['test']['n']} | {pct(p1['test']['news2_only_exact'])} | {p1['test']['news2_only_under']} | {pct(p1['test']['combined_exact'])} | {p1['test']['combined_under']} |

The main result from the hand-authored set holds on unseen cases: NEWS2 alone under-triages about half of these patients, whose key signal is in the note, and adding Jev's reading cuts that sharply.

## Threshold tuning (dev → test)

Each Noul's decision threshold was chosen to maximise dev accuracy, then applied unchanged to test.

{table(['Scenario', 'Noul', 'Tuned threshold', 'dev @0.5', 'dev tuned', 'test @0.5', 'test tuned'], tune_rows)}

Tuning transfers. The Nouls that over-fired at 0.5 (safeguarding, red flag, interaction) all improve on test with a higher threshold (0.75–0.85). That is exactly the "calibrate thresholds on your own data" step the TypeSafe docs recommend. The inbox gate did not need tuning: at the default route-confidence gate of 0.6, auto-dispatched messages were {_fmt(g3['test_default']['auto_accuracy'])} correct on test ({g3['test_default']['auto']} of 40 auto-dispatched).
"""


def page_decomposition(e: dict) -> str:
    p = e["s2_policy"]
    rows = []
    for label, name in (("hand", "Hand-authored (20)"), ("gen_dev", "Generated dev (40)"), ("gen_test", "Generated test (40)")):
        for v in ("v1", "v2", "v2.1"):
            x = p[label][v]
            f = x["flags"]
            rows.append([name if v == "v1" else "", v, pct(x["action"]), x["missed_holds"], x["false_holds"],
                         *(f"{pct(f[k]['accuracy'])} ({f[k]['fp']}/{f[k]['fn']})" for k in ("allergy_conflict", "duplicate_therapy", "interaction"))])
    perf = e["perf"]
    return f"""# Discharge: decomposing the weak checks

In the original run, the single `duplicate_therapy` and `interaction` Nouls were the weakest questions. Answering them takes several hops: enumerate the regimen, classify each drug, then compare the pairs. The [Jev jaggedness notes](https://docs.typesafe.ai/model-jaggedness/jev-1.13) predict exactly this failure. This page tests their advice to reduce the hops and move aggregation into code.

| Variant | What Jev is asked (one request per discharge) | What code does |
| --- | --- | --- |
| **v1** | Three whole-regimen Nouls: allergy conflict? duplicate? interaction? | Hold if any Noul ≥ 0.5 |
| **v2** | Per drug: therapeutic class (Choice). Per new-drug candidate: "is it newly started (not in the pre-admission list)?" (Noul). Per pair: *new drug × other drug* interaction (Noul) and *drug × drug allergy* conflict (Noul). | Finds candidate drug names with a formulary lookup, builds the regimen, detects duplicate classes, ORs the pair Nouls |
| **v2.1** | As v2, but the candidate question becomes "does the text tell the patient to take X after discharge?" | Same |

v2 averages about {perf['s2_discharge_gen_v2']['questions'] // perf['s2_discharge_gen_v2']['requests']} questions per request (up to 71), still in **one request** at p50 {perf['s2_discharge_gen_v2']['p50_ms']} ms.

## Results

Flag cells show accuracy (false positives / false negatives).

{table(['Case set', 'Variant', 'Action correct', 'Missed holds', 'False holds', 'Allergy', 'Duplicate', 'Interaction'], rows)}

## What happened

1. **v2 removed the false positives** but broke recall: 9 holds were missed on test. The error was mine, not the model's. The "is it newly started (not in the pre-admission list)?" question compounded two checks, and code had already done the second. Jev answered *no* for plainly new drugs: "New: aspirin 75 mg daily" scored 0.06, while the pairwise allergy question for the same drug scored 0.98.
2. **v2.1 asked only what code cannot know.** On generated cases it gets the best result of any variant (100% of dev and 95% of test discharge actions correct, with no missed holds). This single revision was made after looking at generated cases from both splits, so treat the v2.1 test figures as optimistic.
3. **v2.1 regresses on the hand-authored set,** for a new reason: brand names. "Continue Norco" matches the formulary, and Norco isn't in the FHIR list under that name (it appears as hydrocodone/acetaminophen). So it becomes a "new" candidate and gets double-counted as a duplicate. That hop now lives in code (name matching) and needs its own fix, such as an RxNorm ingredient lookup.
4. **Pairwise interaction Nouls still over-fire.** Asking "is there an important interaction between X and Y?" for every pair invites false positives. That points to a curated interaction table (code) or a higher, dev-tuned threshold.

**Takeaway:** decomposition does what the docs promise for the judgment it isolates. But every hop you move into code becomes code you must get right, and the generated set's code-computed labels are what make that measurable.
"""


def page_s4(e: dict) -> str:
    s = e["s4"]
    h = e["haiku"].get("s4_search")
    hk = h["haiku"] if h else None
    rows = [["Lay keyword search (baseline)", "–", pct(s["lay_keyword_note_level"]["precision"]), pct(s["lay_keyword_note_level"]["recall"]), f"{s['lay_keyword_note_level']['f1']:.2f}"],
            ["Jev: Noul per note", "10 Nouls/request", pct(s["note_level"]["precision"]), pct(s["note_level"]["recall"]), f"{s['note_level']['f1']:.2f}"]]
    if hk:
        rows.append(["Claude Haiku 4.5: same questions", "LLM", pct(hk["note_level"]["precision"]), pct(hk["note_level"]["recall"]), f"{hk['note_level']['f1']:.2f}"])
    pat = [["Jev: one Noul over all notes", pct(s["patient_any_noul"]["accuracy"]), pct(s["patient_any_noul"]["recall"])],
           ["Jev: max of per-note Nouls (code)", pct(s["patient_from_notes"]["accuracy"]), pct(s["patient_from_notes"]["recall"])],
           ["Jev: best-evidence Choice correct", pct(s["best_note_choice_accuracy"]), "–"]]
    if hk:
        pat += [["Haiku: one answer over all notes", pct(hk["patient_any_noul"]["accuracy"]), pct(hk["patient_any_noul"]["recall"])],
                ["Haiku: best-evidence choice correct", pct(hk["best_note_choice_accuracy"]), "–"]]
    q = "\n".join(f"| {k} | `{v[0]}` | `{v[1]}` |" for k, v in QUERIES.items())
    pf = s["perf"]
    return f"""# 4. Searching a patient's notes

A clinician asks a plain-language question about a patient's history, and the system searches that patient's **10 most recent notes** (Synthea's own clinical-note text, stored as FHIR R5 `DocumentReference`).

**Categories:** search, retrieval, ranking. **Primitives:** Noul per note (fanned out), Choice for the best evidence note, and a Noul for the patient-level answer.

**Ground truth is objective.** A note is relevant when its diagnosis phrases (`… (disorder)`) contain the clinical term for the query. Jev only sees the *lay* query, so it has to bridge "heart attack" to "myocardial infarction". A lay keyword search is the naive baseline.

??? note "Queries, ground-truth patterns and keyword baseline"

    | Lay query | Clinical pattern (truth) | Keyword baseline |
    | --- | --- | --- |
{chr(10).join('    ' + l for l in q.splitlines())}

{s['cases']} patient-query cases (about half positive), {s['notes_judged']:,} note judgments.

## Note-level retrieval

{table(['Method', '', 'Precision', 'Recall', 'F1'], rows)}

## Patient-level answer

{table(['Method', 'Accuracy', 'Recall'], pat)}

Jev finds almost every relevant note: recall {pct(s['note_level']['recall'])}, against {pct(s['lay_keyword_note_level']['recall'])} for keywords. Its precision is lower because it also accepts notes that imply the condition, for example a note that lists insulin or "diabetic retinopathy" for a diabetes query. Whether that counts as an error depends on whether you want *evidence* or an *exact diagnosis mention*. Aggregating the per-note Nouls in code slightly beats asking one question over all 10 notes at once, which matches the docs' advice to keep the state small and let code combine the results.

**Scale:** {pf['requests']} requests, {pf['questions']:,} questions, {pf['input_tokens']:,} input tokens (about 4.4k per request), {pf['wall_seconds']} s wall-clock at concurrency {pf['concurrency']}, p50 {pf['p50_ms']} ms, **${pf['cost_usd']:.3f}**.
"""


def page_s5(e: dict) -> str:
    s = e["s5"]
    m = s["models"]
    uni = sorted(s["univariate_auroc"].items(), key=lambda kv: -abs(kv[1] - 0.5))[:8]
    pf = s["perf"]
    return f"""# 5. Jev judgments as model features

Can Jev turn free text into useful *features* for a classical model? Here the task is predicting whether a patient has an **emergency or inpatient encounter in the 12 months after an index date** (2025-09-19), for all **{s['n']:,} patients** ({s['positives']} had one).

- **Outcome:** Synthea's simulated encounters. No model wrote these labels.
- **Structured baseline (5 features):** age, sex, active chronic disorders, active medications, and emergency/inpatient visits in the prior 12 months, all computed in code as of the index date.
- **Jev features (17):** from the patient's most recent note before the index date. Two Scores (chronic disease burden, medication complexity), seven Nouls (cardiovascular, respiratory, diabetes complications, mental health, substance use, social risk, recent acute illness) and one Choice (main clinical area, used as 8 probabilities).
- **Model:** standardised logistic regression, stratified 5-fold cross-validation repeated 5 times.

| Features | AUROC (mean ± sd) |
| --- | --- |
| Structured only | {m['structured']['auroc_mean']:.3f} ± {m['structured']['auroc_sd']:.3f} |
| Jev only | {m['jev']['auroc_mean']:.3f} ± {m['jev']['auroc_sd']:.3f} |
| Structured + Jev | **{m['structured+jev']['auroc_mean']:.3f}** ± {m['structured+jev']['auroc_sd']:.3f} |

Jev's text features alone match the hand-built structured features, and the combination adds a small, consistent gain. The absolute AUROCs are modest because Synthea's acute events are largely random given a patient's history, so there is limited signal to find. The point is the method: {pf['questions']:,} typed judgments over 1,000 notes, with no prompt engineering beyond the question text, produced features a standard model can use.

Strongest single Jev features (univariate AUROC): {", ".join(f"`{k}` {v:.2f}" for k, v in uni)}.

**Scale:** {pf['requests']:,} requests, {pf['questions']:,} questions, {pf['wall_seconds']} s wall-clock at concurrency {pf['concurrency']}, p50 {pf['p50_ms']} ms, **${pf['cost_usd']:.3f}** for the whole cohort.
"""


def page_baseline(e: dict) -> str:
    h = e["haiku"]
    blocks = []
    tot = {"jev_cost": 0.0, "h_cost": 0.0}
    perf_rows = []
    for run, title in (("s1_ward", "Ward"), ("s2_discharge", "Discharge"), ("s3_inbox", "Inbox")):
        hand, gen = h.get(run), h.get(f"{run}_gen")
        if not hand or not gen:
            continue
        rows = []
        for fam, d in gen["jev"].items():
            m = lambda x: pct(x["accuracy"]) if "accuracy" in x else pct(x["exact"])
            rows.append([f"`{fam}`", d["type"], m(hand["jev"][fam]["hand"]), m(hand["haiku"][fam]["hand"]),
                         m(d["test"]), m(gen["haiku"][fam]["test"])])
        blocks.append(f"### {title}\n\n" + table(["Question", "Primitive", "Jev (hand)", "Haiku (hand)", "Jev (test)", "Haiku (test)"], rows))
        for r in (hand, gen):
            tot["jev_cost"] += r["jev_perf"]["cost_usd"]
            tot["h_cost"] += r["haiku_perf"]["cost_usd"]
        perf_rows.append([title, f"{gen['jev_perf']['p50_ms']} / {gen['jev_perf']['p95_ms']}",
                          f"{gen['haiku_perf']['p50_ms']} / {gen['haiku_perf']['p95_ms']}",
                          f"${(hand['jev_perf']['cost_usd'] + gen['jev_perf']['cost_usd']) / 100 * 1000:.3f}",
                          f"${(hand['haiku_perf']['cost_usd'] + gen['haiku_perf']['cost_usd']) / 100 * 1000:.2f}",
                          f"{gen['haiku_perf']['parsed']}/{gen['haiku_perf']['requests']}"])
    s4 = h.get("s4_search")
    if s4:
        perf_rows.append(["Note search", f"{s4['jev_perf']['p50_ms']} / {s4['jev_perf']['p95_ms']}",
                          f"{s4['haiku_perf']['p50_ms']} / {s4['haiku_perf']['p95_ms']}",
                          f"${s4['jev_perf']['cost_usd'] / s4['jev_perf']['requests'] * 1000:.3f}",
                          f"${s4['haiku_perf']['cost_usd'] / s4['haiku_perf']['requests'] * 1000:.2f}",
                          f"{s4['haiku_perf']['parsed']}/{s4['haiku_perf']['requests']}"])
    return f"""# LLM-only baseline: Jev vs Claude Haiku

The obvious question is "why not just ask an LLM?" So every S1–S3 case, and every note-search case, was also sent to **Claude Haiku 4.5**. Haiku got the same state and the same questions (same instructions and criteria) and was asked to return JSON with a probability or confidence for each answer. Each case is one headless Claude Code call (`claude -p --model claude-haiku-4-5`, no tools, minimal system prompt, extended thinking off, which is the fast configuration you'd choose for a classifier). Latency is the API time reported by the CLI.

## Accuracy

Hand = the 20 original cases; test = the 40 generated test cases.

{chr(10).join(blocks)}

**Neither model wins outright.**
- **Jev is better** at extraction and literal checks: medication status, infection, allergy, and the justification Score.
- **Haiku is better** where the judgment needs broader world knowledge or reading intent: inbox routing, safeguarding, and (on the 20 hand-authored discharges) duplicates and interactions.

Many of Haiku's advantages are exactly the Nouls that improved most with a dev-tuned threshold on the [scaling page](scale.md). So part of the gap is calibration rather than understanding.

## Speed, cost, reliability

| Scenario | Jev p50 / p95 ms | Haiku p50 / p95 ms | Jev cost per 1,000 cases | Haiku cost per 1,000 cases | Haiku JSON parsed |
| --- | --- | --- | --- | --- | --- |
{chr(10).join('| ' + ' | '.join(r) + ' |' for r in perf_rows)}

Jev is roughly **5–8× faster** and **30–60× cheaper** per case. Its outputs are typed by construction, while Haiku's JSON had to be parsed and validated. At the scale of scenario 5 (10,000 judgments for $0.05) that difference decides the architecture: use Jev for every item, and a reasoning model only for the minority Jev is unsure about, as on the [System Two](system-two.md) page.
"""


def extra_pages() -> dict[str, str]:
    e = json.loads((RESULTS_DIR / "evaluation2.json").read_text())
    return {"scale.md": page_scale(e), "s2-decomposition.md": page_decomposition(e), "s4-search.md": page_s4(e),
            "s5-features.md": page_s5(e), "llm-baseline.md": page_baseline(e)}
