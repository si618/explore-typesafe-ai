# 5. Jev judgments as ML features

**Setting:** predict which patients will have an **emergency or inpatient encounter in the next 12 months**, for all 1,000 patients in the cohort, as of an index date of 2025-09-19.

**Why this scenario:** the TypeSafe docs describe using typed judgments as **features for classical ML**. This tests that pattern where the outcome comes from [Synthea](vocabulary.md#synthea)'s simulated encounters, so no model wrote the labels (179 positives, 18%).

| Feature set | Features | Cross-validated AUROC (mean ± sd) |
| --- | --- | --- |
| Structured: age, sex, chronic disorder count, medication count, prior-year acute use | 5 | 0.641 ± 0.010 |
| [Jev](vocabulary.md#jev): 10 typed judgments over the most recent note before the index date | 17 | 0.637 ± 0.006 |
| Structured + Jev | 22 | 0.649 ± 0.006 |

Logistic regression, 5-fold stratified cross-validation repeated 5 times.

## Reading this honestly

- **Jev features from one note match the structured baseline** (AUROC 0.64 vs 0.64), and together they add only **+0.008**. That is a small gain.
- **The ceiling is Synthea, not the features.** Synthea's acute encounters are driven by stochastic disease modules, so every feature set sits near 0.64. This synthetic outcome can't show whether Jev features would help on real utilisation data. It can show the mechanics: 1,000 notes × 10 questions in 41 s for $0.048.
- **The strongest single features** are the [Score](vocabulary.md#score) for overall clinical burden (AUROC 0.64) and the cardiovascular [Noul](vocabulary.md#noul) (0.59).

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

## Example request and response

One patient's most recent note before the index date, turned into ten numeric features. `state` and `questions` are built by [`s5_features.py`](https://github.com/si618/explore-typesafe-ai/blob/main/src/explore_typesafe/s5_features.py);
`system_one` answers every question in one request.

```python
from typesafe_sdk import AsyncTypeSafeClient

state = {
  "note": "\n2025-09-04\n\n# Chief Complaint\n- Frequent Urination\n- Thirst\n- Tingling in Hands and Feet\n\n\n# History of Present Illness\nGarland107 is a 83 year-old nonhispanic white male. Patient has a history of gingival disease (disorder), overdose (disorder), severe anxiety (panic) (finding), chronic kidney disease stage 3 (disorder), medication review due (situation), unemployed (finding), victim of intimate partner abuse (finding), viral sinusitis (disorder), chronic kidney disease stage 4 (disorder), par …"
}

questions = {
  "burden": {
    "type": "score",
    "instructions": "How much chronic disease does `note` describe?",
    "criteria": [
      "No chronic disease; only minor or acute problems",
      "One chronic condition, such as hypertension or asthma",
      "Several chronic conditions, such as diabetes with kidney or heart disease",
      "Advanced disease: heart failure, advanced kidney disease, cancer, dementia, or multiple organ involvement"
    ]
  },
  "diabetes_complications": {
    "type": "noul",
    "instructions": "Does `note` describe diabetes with complications affecting the kidneys, nerves or eyes?"
  },
  "mental_health": {
    "type": "noul",
    "instructions": "Does `note` describe a mental health condition such as depression or anxiety?"
  }
}

async with AsyncTypeSafeClient(model="jev-1.13.0") as client:
    response = await client.system_one(state, questions)

body = response.raw_http_response.json()
```

The response body, exactly as recorded:

```json
{
  "answers": {
    "burden": {
      "type": "score",
      "score": 3.0,
      "confidence": 1.0,
      "legend": {
        "0": "No chronic disease; only minor or acute problems",
        "1": "One chronic condition, such as hypertension or asthma",
        "2": "Several chronic conditions, such as diabetes with kidney or heart disease",
        "3": "Advanced disease: heart failure, advanced kidney disease, cancer, dementia, or multiple organ involvement"
      },
      "probabilities": {
        "0": 0.0,
        "1": 0.0,
        "2": 0.0,
        "3": 1.0
      }
    },
    "diabetes_complications": {
      "type": "noul",
      "noul": 0.73
    },
    "mental_health": {
      "type": "noul",
      "noul": 0.97
    }
  },
  "model": "jev-1.13.0",
  "usage": {
    "input_tokens": 1360,
    "output_tokens": 252
  }
}
```

Request `req_01a0b71789c67ad9ba08819af09bcfef` took **373 ms** for 10 questions
(1,360 input / 252 output tokens). Abridged for this page: `note` truncated from 2,144 characters; 3 of 10 questions and their answers shown.
Every case of this run, untrimmed, is in [`results/s5_features.json`](https://github.com/si618/explore-typesafe-ai/blob/main/results/s5_features.json).

