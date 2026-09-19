# Prompt & approach

## The prompt

This report was produced by Claude Code (Claude Opus 5) from the following prompt. The only edit is a typo fix ("such as gh cli actions").

> Create a github repository to demonstrate the /typesafe-ai skill and Jev model used in conjunction with claude codes own models. Name the repo explore-typesafe-ai, read https://docs.typesafe.ai/ then construct and store realistic synthetic clinical data for 100 patients using latest FHIR models for structure. Use publicly available data if possible, otherwise use a tool like Synthea to build them.
>
> Then create 3 clinically relevant scenarios that could occur in a hospital setting to evaluate each of the available primitives against suitable decision task categories. Then run the scenarios against the model, store the result.
>
> Create a report for rendering in a static Zeniscal website, using github actions to publish via the repos github page at https://si618.github.io/explore-typesafe-ai. Your audience are technically astute, keep content concise; the main goal is demonstrate the capabilities of System One / Jev models in a clinical scenario. The report should include this prompt and your reasoning for choosing the different scenarios, but leave out infrastructure tasks such as gh cli actions.

Follow-up instructions given during the session:

- include token usage and models in report
- include timing metrics for jev model runs
- zensical should support dark and light modes defaulting to system
- add vocabulary section to briefly explain primitives, task categories, news2, etc.
- dark and light modes are a bit bland and harsh, soften them
- update themes to use tokyo dark and tokyo light

## How the prompt was read

| Prompt element | Interpretation |
| --- | --- |
| "/typesafe-ai skill" | The skill steered the design: read the live docs first, keep arithmetic and policy in code, ask narrow typed questions, fan out independent questions in one request, and gate on confidence. |
| "in conjunction with Claude Code's own models" | Claude Opus 5 wrote the pipeline, authored the scenario text and wrote the reference labels. A separate, blinded Claude Sonnet 5 agent acts as the **System Two** reviewer for judgments that Jev flags as uncertain. |
| "latest FHIR models" | Synthea's current exporter emits FHIR **R4** (US Core). The clinical snapshot used here is mapped to FHIR **R5** (5.0.0, the latest published release) and validated with `fhir.resources` 8.x. |
| "publicly available data if possible" | Public clinical datasets such as MIMIC need credentialed access and data-use agreements, so they can't be redistributed in a public repo. Synthea's output is openly licensed and reproducible from a seed. |
| "each of the available primitives against suitable decision task categories" | Every scenario uses all three primitives (Choice, Score and Noul). Each question is mapped to one of the task categories in the TypeSafe docs (classification, detection, scoring, routing, ranking, verification, structured data extraction). |
| "Zeniscal" | [Zensical](https://zensical.org), the static site generator from the Material for MkDocs team. |

## Why these three scenarios

The docs describe Jev as a fast, calibrated judge of meaning. It is not a calculator, a date engine or a generator. So I looked for hospital decisions where:

1. structured data exists but **the decisive signal is in free text** written by clinicians or patients;
2. a deterministic rule already exists, so Jev can be shown to **complement it** rather than replace it;
3. the cost of error is asymmetric, so **confidence-gated escalation** matters;
4. together, the scenarios cover the three primitives across as many task categories as possible.

| Scenario | Why it was chosen | Decision categories | Primitives |
| --- | --- | --- | --- |
| [1. Ward deterioration huddle](s1-ward.md) | NEWS2 (the UK National Early Warning Score) is computed from charted vital signs, but nurses often write "not himself" or "muddled" and still chart *Alert*. Undocumented new confusion and nurse worry are known causes of missed deterioration. | Detection, Scoring, Ranking, Classification | Noul ×2, Score, Choice |
| [2. Discharge medication reconciliation](s2-discharge.md) | Medication errors at transitions of care are common and harmful. The pre-admission list is structured (FHIR), but the discharge plan is prose, full of blanket statements ("continue all other meds"), brand names and abbreviations. | Structured data extraction, Verification, Scoring | Choice (fan-out, one per medication), Noul ×3, Score |
| [3. Post-discharge message inbox](s3-inbox.md) | A 24/7 inbox must be triaged before a human reads it. Some messages are emergencies phrased casually, some are routine requests written in capitals, and one contains a prompt-injection attempt. | Routing, Classification, Scoring, Detection | Choice, Score, Noul ×3 |

The scenarios deliberately include hard cases: dementia with **unchanged** baseline confusion versus dementia with **new** delirium; negated findings ("No chest pain. No confusion…"); brand-name hops (Augmentin is a penicillin, Norco contains paracetamol); black stool on iron (expected) versus black stool on clopidogrel (a GI bleed); and an embedded `SYSTEM NOTE:` instruction.
