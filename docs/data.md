# Synthetic cohort

**100 synthetic patients** were generated with [Synthea](https://github.com/synthetichealth/synthea) (`master-branch-latest`, released 2026-08-18). No real patient data was used.

```bash
java -jar synthea-with-dependencies.jar -s 618 -cs 618 -p 100 -a 25-90 \
  --exporter.years_of_history 5 --generate.only_alive_patients true Massachusetts
```

| | |
| --- | --- |
| Age | median 60, range 25–89 |
| Sex | 51 female, 49 male |
| Active disorders | mean 4.6 per patient |
| Active medications | mean 4.2 per patient |
| Recorded allergies | 18 patients |
| Most common active disorders | Anemia (42), Essential hypertension (37), Ischemic heart disease (37), Chronic sinusitis (28), Loss of teeth (25), Hyperlipidemia (24) |

## Storage and FHIR versions

| Path | Content | FHIR |
| --- | --- | --- |
| [`data/synthea-r4/`](https://github.com/si618/explore-typesafe-ai/blob/main/data/synthea-r4) | Complete Synthea bundles, gzipped (18 MB, ~200 MB raw, including claims) | R4 4.0.1 + US Core, as exported |
| [`data/fhir-r5/`](https://github.com/si618/explore-typesafe-ai/blob/main/data/fhir-r5) | Clinical snapshot per patient: Condition 1,294, Observation 798, Encounter 500, MedicationRequest 422, Patient 100, AllergyIntolerance 78 | **R5 5.0.0**, validated |
| [`data/fhir-r5-scenarios/`](https://github.com/si618/explore-typesafe-ai/blob/main/data/fhir-r5-scenarios) | Scenario inputs: vital signs (`Observation`), nursing notes and discharge text (`DocumentReference`), patient messages (`Communication`) | **R5 5.0.0**, validated |
| [`data/scenarios/`](https://github.com/si618/explore-typesafe-ai/blob/main/data/scenarios) | Case definitions and **reference labels**, committed before the first Jev run | – |

The R4 → R5 mapping (`src/explore_typesafe/fhir.py`) handles the breaking changes these resources hit: `MedicationRequest.medication[x]` → `medication` (CodeableReference), `reasonReference` → `reason`, `Dosage.asNeededBoolean` → `asNeeded`, `AllergyIntolerance.type` code → CodeableConcept, `reaction.manifestation` → CodeableReference, `Encounter.class` → list, `period` → `actualPeriod`, and status `finished` → `completed`. Every bundle is validated against the R5 models in `fhir.resources` 8.3.

Jev never sees raw FHIR. Code builds a small, named JSON `state` for each question set, with only the fields that decision needs. The [jaggedness notes](https://docs.typesafe.ai/model-jaggedness/jev-1.13) warn that irrelevant state costs accuracy.
