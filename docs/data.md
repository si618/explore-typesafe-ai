# Synthetic cohort

**1,000 synthetic patients** were generated with [Synthea](https://github.com/synthetichealth/synthea) (`master-branch-latest`, released 2026-08-18): the original 100 (seed 618), used by the hand-written scenario cases, plus 900 more (seed 619) for the generated cases, note search and feature scenarios. No real patient data was used.

```bash
java -jar synthea-with-dependencies.jar -s 618 -cs 618 -p 100 -a 25-90 \
  --exporter.years_of_history 5 --generate.only_alive_patients true Massachusetts
# +900: seed 619, -p 900, otherwise the same flags
```

| | |
| --- | --- |
| Age | median 59, range 25–89 |
| Sex | 509 female, 491 male |
| Active disorders | mean 4.3 per patient |
| Active medications | mean 3.9 per patient |
| Recorded allergies | 154 patients |
| Most common active disorders | Anemia (449), Essential hypertension (355), Ischemic heart disease (337), Chronic sinusitis (265), Metabolic syndrome X (209), Loss of teeth (205) |

## Storage and FHIR versions

| Path | Content | FHIR |
| --- | --- | --- |
| [`data/synthea-r4/`](https://github.com/si618/explore-typesafe-ai/blob/main/data/synthea-r4) | Complete Synthea bundles for the original 100, gzipped, including claims | R4 4.0.1 + US Core, as exported |
| [Release `cohort-1000`](https://github.com/si618/explore-typesafe-ai/releases/tag/cohort-1000) | Complete Synthea bundles for the other 900 (too large to commit) | R4 4.0.1 + US Core, as exported |
| [`data/fhir-r5/`](https://github.com/si618/explore-typesafe-ai/blob/main/data/fhir-r5) | Clinical snapshot per patient, including the 10 most recent clinical notes: Condition 12,445, DocumentReference 9,843, Observation 7,978, Encounter 4,993, MedicationRequest 3,884, Patient 1,000, AllergyIntolerance 679 | **R5 5.0.0**, validated |
| [`data/fhir-r5-scenarios/`](https://github.com/si618/explore-typesafe-ai/blob/main/data/fhir-r5-scenarios) | Hand-written scenario inputs: vital signs (`Observation`), nursing notes and discharge text (`DocumentReference`), patient messages (`Communication`) | **R5 5.0.0**, validated |
| [`data/scenarios/`](https://github.com/si618/explore-typesafe-ai/blob/main/data/scenarios) | Case definitions and **reference labels**, each set committed before its first model run | – |

The R4 → R5 mapping (`src/explore_typesafe/fhir.py`) handles the breaking changes these resources hit: `MedicationRequest.medication[x]` → `medication` (CodeableReference), `reasonReference` → `reason`, `Dosage.asNeededBoolean` → `asNeeded`, `AllergyIntolerance.type` code → CodeableConcept, `reaction.manifestation` → CodeableReference, `Encounter.class` → list, `period` → `actualPeriod`, `DocumentReference.context.period` → `period`, and status `finished` → `completed`. Every bundle is validated against the R5 models in `fhir.resources` 8.3.

Jev never sees raw FHIR. Code builds a small, named JSON `state` for each question set, with only the fields that decision needs. The [jaggedness notes](https://docs.typesafe.ai/model-jaggedness/jev-1.13) warn that irrelevant state costs accuracy.
