# 5. Jev judgments as ML features

**Setting:** predict which patients will have an **emergency or inpatient encounter in the next 12 months**, for all 1,000 patients in the cohort, as of an index date of 2025-09-19.

**Why this scenario:** the TypeSafe docs describe using typed judgments as **features for classical ML**. This tests that pattern where the outcome comes from Synthea's simulated encounters, so no model wrote the labels (179 positives, 18%).

| Feature set | Features | Cross-validated AUROC (mean ± sd) |
| --- | --- | --- |
| Structured: age, sex, chronic disorder count, medication count, prior-year acute use | 5 | 0.641 ± 0.010 |
| Jev: 10 typed judgments over the most recent note before the index date | 17 | 0.637 ± 0.006 |
| Structured + Jev | 22 | 0.649 ± 0.006 |

Logistic regression, 5-fold stratified cross-validation repeated 5 times.

## Reading this honestly

- **Jev features from one note match the structured baseline** (AUROC 0.64 vs 0.64), and together they add only **+0.008**. That is a small gain.
- **The ceiling is Synthea, not the features.** Synthea's acute encounters are driven by stochastic disease modules, so every feature set sits near 0.64. This synthetic outcome can't show whether Jev features would help on real utilisation data. It can show the mechanics: 1,000 notes × 10 questions in 41 s for $0.048.
- **The strongest single features** are the Score for overall clinical burden (AUROC 0.64) and the cardiovascular Noul (0.59).

??? note "Univariate AUROC of every Jev feature"

    | Feature | AUROC |
    | --- | --- |
    | `burden` | 0.636 |
    | `cardiovascular` | 0.590 |
    | `diabetes_complications` | 0.589 |
    | `polypharmacy` | 0.583 |
    | `social_risk` | 0.570 |
    | `substance` | 0.561 |
    | `respiratory` | 0.551 |
    | `dominant=neuro_cognitive` | 0.539 |
    | `dominant=cardiometabolic` | 0.538 |
    | `mental_health` | 0.531 |
    | `recent_acute` | 0.525 |
    | `dominant=renal` | 0.524 |
    | `dominant=cancer` | 0.509 |
    | `dominant=mental_substance` | 0.495 |
    | `dominant=respiratory` | 0.477 |
    | `dominant=musculoskeletal_injury` | 0.476 |
    | `dominant=routine` | 0.405 |
