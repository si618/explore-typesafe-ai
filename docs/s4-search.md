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

## Example request and response

One search: the query, the ten notes, and a Noul per note plus the two whole-patient questions. `state` and `questions` are built by [`s4_search.py`](https://github.com/si618/explore-typesafe-ai/blob/main/src/explore_typesafe/s4_search.py);
`system_one` answers every question in one request.

```python
from typesafe_sdk import AsyncTypeSafeClient

state = {
  "query": "Has the patient ever had a heart attack?",
  "notes": [
    {
      "id": "note_0",
      "date": "2023-01-01",
      "text": "\n2023-01-01\n\n# Chief Complaint\nNo complaints.\n\n# History of Present Illness\nShara355 Roseanne877 is a 77 year-old nonhispanic white female. Patient has a history of part-time employment (finding), medication review due (situation), full-tim …"
    },
    {
      "id": "note_1",
      "date": "2023-04-27",
      "text": "\n2023-04-27\n\n# Chief Complaint\nNo complaints.\n\n# History of Present Illness\nShara355 Roseanne877 is a 77 year-old nonhispanic white female. Patient has a history of part-time employment (finding), fracture of forearm (disorder), medication …"
    }
  ]
}

questions = {
  "note_0": {
    "type": "noul",
    "instructions": "Does `notes[0].text` contain information showing that the answer to `query` is yes?"
  },
  "best": {
    "type": "choice",
    "instructions": "Which note is the best evidence for answering `query` with yes?",
    "criteria": {
      "note_0": "`notes[0]`",
      "note_1": "`notes[1]`",
      "note_2": "`notes[2]`",
      "note_3": "`notes[3]`",
      "note_4": "`notes[4]`",
      "note_5": "`notes[5]`",
      "note_6": "`notes[6]`",
      "note_7": "`notes[7]`",
      "note_8": "`notes[8]`",
      "note_9": "`notes[9]`",
      "none": "No note shows the answer is yes"
    }
  },
  "any": {
    "type": "noul",
    "instructions": "Taking all of `notes` together, is the answer to `query` yes?"
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
    "note_0": {
      "type": "noul",
      "noul": 0.02
    },
    "best": {
      "type": "choice",
      "choice": "note_6",
      "confidence": 0.64,
      "probabilities": {
        "note_1": 0.0,
        "note_3": 0.0,
        "note_2": 0.0,
        "none": 0.0,
        "note_7": 0.31,
        "note_4": 0.0,
        "note_5": 0.0,
        "note_9": 0.0,
        "note_0": 0.0,
        "note_6": 0.68,
        "note_8": 0.01
      }
    },
    "any": {
      "type": "noul",
      "noul": 0.98
    }
  },
  "model": "jev-1.13.0",
  "usage": {
    "input_tokens": 5475,
    "output_tokens": 313
  }
}
```

Request `req_01a0b717158c73fab8227773f5f52149` took **655 ms** for 12 questions
(5,475 input / 313 output tokens). Abridged for this page: `notes` shows 2 of 10 entries; `notes[0].text` truncated from 1,260 characters; `notes[1].text` truncated from 962 characters; 3 of 12 questions and their answers shown.
Every case of this run, untrimmed, is in [`results/s4_search.json`](https://github.com/si618/explore-typesafe-ai/blob/main/results/s4_search.json).

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
