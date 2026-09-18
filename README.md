# explore-typesafe-ai

Evaluating [TypeSafe](https://docs.typesafe.ai)'s System One model **Jev** on three hospital decisions over 100 synthetic FHIR patients. Claude models write the pipeline, author the scenarios and review escalations as System Two.

**Report:** https://si618.github.io/explore-typesafe-ai

| Scenario | Primitives |
| --- | --- |
| Ward deterioration huddle: NEWS2 in code, plus Jev reading the nursing note | Noul, Score, Choice |
| Discharge medication reconciliation: per-medication extraction plus regimen verification | Choice (fan-out), Noul, Score |
| Post-discharge patient inbox: routing with a confidence gate | Choice, Score, Noul |

## Layout

```
data/synthea-r4/          raw Synthea bundles (FHIR R4, gzipped)
data/fhir-r5/             per-patient clinical snapshots, FHIR R5 (validated)
data/fhir-r5-scenarios/   scenario inputs as FHIR R5 Observation / DocumentReference / Communication
data/scenarios/           case definitions + reference labels (committed before any Jev run)
results/                  raw Jev answers, timing, usage; System Two packet and review; evaluation
src/explore_typesafe/     pipeline (see below)
report/                   static narrative for the site
docs/                     generated Zensical site source
```

## Reproduce

```bash
uv sync
uv run python -m explore_typesafe.fhir            # R4 -> R5 snapshots + cohort.json
uv run python -m explore_typesafe.scenario_fhir   # scenario inputs as R5 bundles
export TYPESAFE_API_KEY=...
uv run python -m explore_typesafe.run             # 60 requests to jev-1.13.0
uv run python -m explore_typesafe.escalate        # System Two review packet
# review packet -> results/system_two_review.json (done by a blinded Claude agent)
uv run python -m explore_typesafe.evaluate
uv run python -m explore_typesafe.report          # renders docs/
uv run zensical serve
```

Synthetic data only. This is not clinically validated.
