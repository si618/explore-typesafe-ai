# 4. Semantic search over notes

**Setting:** a clinician asks a plain-language question ("has this patient ever had a heart attack?") and the system searches the patient's 10 most recent clinical notes (Synthea text, FHIR R5 `DocumentReference`).

**Why this scenario:** retrieval is one of the task categories in the TypeSafe docs, and the notes use clinical vocabulary ("myocardial infarction") that the lay question doesn't. A keyword search for the lay words is the naive baseline.

**Cases:** 12 queries × 25 patients (about half positive), **300 searches over 2,922 notes**.

**Ground truth (objective, by regex):** a note is relevant if a Synthea `(disorder)` phrase in it matches the clinical term. No model wrote these labels.

| Question per search | Primitive | Task category |
| --- | --- | --- |
| Does `notes[i]` show the answer is yes? (one per note) | Noul ×10 | Search / Retrieval |
| Which note is the best evidence? | Choice (10 notes + none) | Ranking |
| Taking all notes together, is the answer yes? | Noul | Detection |

## Results

| Method | Note precision | Note recall | Note F1 |
| --- | --- | --- | --- |
| Lay keyword search | 64% | 25% | 0.35 |
| Jev, all 10 notes in one request | 76% | 100% | 0.86 |
| Jev, one note per request | 67% | 100% | 0.80 |
| Claude Haiku 4.5, all 10 notes in one request | 70% | 100% | 0.83 |

| Patient-level answer | Accuracy | Precision | Recall |
| --- | --- | --- | --- |
| "Any" Noul over all notes | 96% | 89% | 100% |
| Max of per-note Nouls (all-in-one request) | 97% | 92% | 100% |
| Max of per-note Nouls (one note per request) | 97% | 92% | 100% |

The best-evidence Choice picked a relevant note (or correctly said *none*) in **93%** of searches. Jev bridges lay and clinical vocabulary almost perfectly: recall is about 100% against the keyword baseline's 25%.

## The "false positives" are mostly label gaps

Note-level precision looks modest, and isolating each note in its own request made it *worse* (76% → 67%). The hypothesis being tested was that one note's evidence leaks into judgments of the others. Inspecting the per-note false positives doesn't support it: **209 of 218** show the condition through its treatment or an explicit statement. The regex can't see those, because it only reads `(disorder)` phrases. Examples include metformin or insulin for diabetes, an ACE inhibitor or thiazide for high blood pressure, donepezil for dementia, and "a documented history of opioid addiction".

Re-scoring with those notes counted as relevant (a **post-hoc** sensitivity analysis; the patterns are in [`evaluate2.py`](https://github.com/si618/explore-typesafe-ai/blob/main/src/explore_typesafe/evaluate2.py)):

| Variant | Strict labels: P / R | Strong-evidence labels: P / R |
| --- | --- | --- |
| All 10 notes in one request | 76% / 100% | 98% / 83% |
| One note per request | 67% / 100% | 99% / 95% |

Both variants are about 98.5% precise. They differ in **recall of indirect evidence**: judged alone, a note that only lists metformin is recognised as showing diabetes (209 of 243 such notes). With ten notes in the state, more of those are missed. Isolation costs 9× the wall time and 1.46× the tokens ($0.082 vs $0.056), and it only matters if "treated for X" should count as "has X".
