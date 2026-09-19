# Vocabulary

Short definitions of the terms used in this report. The TypeSafe terms follow the [TypeSafe docs](https://docs.typesafe.ai).

## TypeSafe and Jev

**System One / System Two**
:   After Kahneman's *Thinking, Fast and Slow*. A **System One** model makes fast, focused judgments and returns typed answers, not text. **System Two** here means a slower, deliberate reasoning step: a large language model (Claude Sonnet 5) or a human, called only when System One is unsure.

**Jev**
:   TypeSafe's flagship System One model. This report pins `jev-1.13.0`. It is priced per input token; output tokens are free.

**State**
:   The content Jev evaluates: a string, JSON object or array. Here it is a small JSON object that code builds from FHIR data and free text. Questions refer to parts of it by path, for example `` `nursing_note` ``.

**Question / primitive**
:   One typed judgment about the state. All questions in a request see the same state and are answered independently and in parallel. There are three primitives:

| Primitive | Asks | Returns | Example here |
| --- | --- | --- | --- |
| **Choice** | Which one of these options? | `choice`, a probability per option, `confidence` | Who should handle this patient message? |
| **Score** | Where on this ordered scale? | `score` (a probability-weighted level, can be fractional), probabilities per level, `confidence` | How worried should the ward team be (levels 0–3)? |
| **Noul** | Is this statement true? | `noul`: the probability of yes (0–1) | Does the note describe new confusion? |

**Criteria**
:   The answer space: Choice options, Score levels, or optional true/false definitions for a Noul. Clear criteria matter more than clever instructions.

**Confidence**
:   A 0–1 summary of how concentrated a Choice or Score probability distribution is. It describes the model's certainty, not correctness. Nouls have no separate confidence: a value near 0.5 is itself the uncertainty signal.

**Fan-out**
:   Asking many questions over one state in a single request, for example one Choice per medication. Latency barely changes as questions are added.

**Confidence gate / escalation**
:   Rules in code that act on an answer only when it is confident, and otherwise send it to System Two. Examples: route confidence < 0.6, or a Noul between 0.2 and 0.8.

**Jaggedness**
:   TypeSafe's term for Jev's known weak spots: literal reading, arithmetic, dates, multi-hop reasoning ("indirection"), large irrelevant state, and generation.

## Task categories

Decision shapes from the TypeSafe [use-case map](https://docs.typesafe.ai/concepts/use-case-map), as used in the scenarios:

| Category | Meaning | Where it appears |
| --- | --- | --- |
| **Classification** | One known category should win | Type of deterioration (ward) |
| **Detection** | Probability that one property is present | New confusion, infection, red flag, safeguarding |
| **Scoring** | Place something on an ordered rubric | Nurse concern, message urgency, quality of explanations |
| **Routing** | A category selects the next code path | Inbox queue |
| **Ranking** | Order items by a semantic signal | Ward huddle priority list |
| **Verification** | Check an artefact for specific failure modes | Allergy conflict, duplicate therapy, interaction |
| **Structured data extraction** | Recover known fields from unstructured text | Status of each medication at discharge |

## Evaluation terms

**Reference label**
:   The expected answer for each case, written by Claude Opus 5 and committed before Jev ran. This is not a clinician gold standard.

**Ambiguous**
:   A reference label that could reasonably go either way. Accuracy is reported with and without these.

**Brier score**
:   Mean squared error between a probability and the 0/1 truth; lower is better, and 0 is perfect. It measures calibration as well as correctness.

**MAE**
:   Mean absolute error between a fractional Score and the reference level.

**Under-triage / over-triage**
:   Assigning a less urgent (under) or more urgent (over) band than the reference.

**p50 / p95 latency**
:   The median and 95th-percentile request time.

## Clinical and data terms

**NEWS2**
:   The UK Royal College of Physicians' *National Early Warning Score 2*. It adds points for respiratory rate, oxygen saturation, supplemental oxygen, blood pressure, heart rate, level of consciousness and temperature. A total of 0 means routine observations; 1–4 is ward-level; 5–6, or any single parameter scoring 3, needs an urgent review; 7 or more is an emergency response. It is computed in code here.

**ACVPU**
:   The consciousness scale in NEWS2: **A**lert, new **C**onfusion, responds to **V**oice, to **P**ain, **U**nresponsive. Anything other than Alert scores 3. Jev's new-confusion Noul can upgrade a charted *A* to *C*.

**SpO₂ scale 1 / 2**
:   NEWS2 oxygen-saturation scoring. Scale 2 is for patients with a lower target (88–92%), such as some COPD patients at risk of CO₂ retention.

**Escalation band**
:   This report's four response levels: routine → ward review → urgent review → emergency.

**Sepsis screen**
:   A structured check for infection causing organ dysfunction. It is prompted here when infection is suspected and NEWS2 is 5 or more.

**Delirium**
:   An acute, fluctuating change in attention and awareness. It is distinct from dementia, which is long-standing, but it often occurs on top of it.

**Medication reconciliation**
:   Comparing the medications a patient took before admission with the discharge plan, so every drug is deliberately continued, changed, withheld or stopped.

**Duplicate therapy / interaction**
:   Two drugs with the same ingredient or class taken together (for example two statins, or two paracetamol-containing products), or a combination known to be harmful (for example clarithromycin with simvastatin).

**Safeguarding**
:   Protecting a patient, or someone they care for, from harm, neglect or self-harm.

**Melaena**
:   Black, tarry stool from upper gastrointestinal bleeding. Black stool on iron tablets is expected and harmless.

**STEMI / NSTEMI / PCI**
:   Heart attack with or without ST-segment elevation on the ECG, and percutaneous coronary intervention (a stent).

**GTN**
:   Glyceryl trinitrate (nitroglycerin) spray for angina.

**FHIR R4 / R5**
:   HL7 *Fast Healthcare Interoperability Resources*, the standard for exchanging health records as typed JSON resources. R4 (4.0.1) is the most widely deployed; R5 (5.0.0) is the latest release.

**FHIR resources used here**
:   `Patient`, `Condition` (diagnoses), `AllergyIntolerance`, `MedicationRequest`, `Observation` (vitals and labs), `Encounter`, `DocumentReference` (notes), and `Communication` (patient messages).

**US Core**
:   The US implementation guide that constrains FHIR R4. Synthea's R4 exports conform to it.

**Synthea**
:   An open-source generator of realistic but entirely synthetic patient histories.
