"""Scenario 4: semantic search over a patient's clinical notes.

A clinician asks a plain-language question ("has this patient ever had a heart
attack?"). Each patient's 10 most recent notes (FHIR R5 DocumentReference, Synthea
text) are searched. Ground truth is objective: a note is relevant when it contains
the clinical term for the query (e.g. "myocardial infarction"), found by regex.
Relevance is matched only inside "... (disorder)" phrases, so screening procedures
("depression screening") don't count. Jev only sees the lay query, so it must
bridge lay and clinical vocabulary; a lay keyword search is the naive baseline.
"""

from __future__ import annotations

import base64
import json
import random
import re

from .common import SCENARIO_DIR, choice, noul
from .fhir import R5_DIR

QUERIES = {  # lay query -> clinical ground-truth pattern, lay keyword baseline pattern
    "Has the patient ever had a heart attack?": (r"myocardial infarction", r"heart attack"),
    "Does the patient have diabetes?": (r"diabetes mellitus", r"diabetes"),
    "Does the patient have kidney disease?": (r"kidney disease|disorder of kidney", r"kidney disease"),
    "Does the patient have high blood pressure?": (r"hypertension", r"high blood pressure"),
    "Has the patient had seizures?": (r"seizure|epilep", r"seizure"),
    "Does the patient have dementia?": (r"alzheimer|dementia", r"dementia"),
    "Does the patient have a chronic lung condition such as asthma or COPD?": (r"asthma|emphysema|chronic obstructive", r"asthma|copd"),
    "Has the patient had cancer?": (r"malignant|carcinoma", r"cancer"),
    "Has the patient had a stroke?": (r"stroke|cerebrovascular", r"stroke"),
    "Does the patient have depression?": (r"depressive", r"depression"),
    "Has the patient had problems with drugs or alcohol?": (r"drug abuse|alcoholism|overdose|substance", r"drugs|alcohol"),
    "Has the patient had a blood clot in the leg or lungs?": (r"embolism|thrombosis", r"blood clot"),
}
PER_QUERY = 25  # ~half positive, half negative patients per query
SEED = 404


def disorders(text: str) -> str:
    """Only the diagnosis phrases of a note (Synthea tags them "(disorder)")."""
    return " | ".join(re.findall(r"([^,.;:\n()]{0,80})\(disorder\)", text))


def notes_of(bundle: dict) -> list[dict]:
    docs = [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "DocumentReference"]
    docs.sort(key=lambda d: d.get("date", ""))
    return [{"date": d["date"][:10], "text": base64.b64decode(d["content"][0]["attachment"]["data"]).decode()}
            for d in docs]


def build_cases() -> list[dict]:
    rng = random.Random(SEED)
    files = sorted(R5_DIR.glob("*.json"))
    rng.shuffle(files)
    pos: dict[str, list] = {q: [] for q in QUERIES}
    neg: dict[str, list] = {q: [] for q in QUERIES}
    for f in files:
        notes = notes_of(json.loads(f.read_text()))
        if len(notes) < 5:
            continue
        for q, (pat, lay) in QUERIES.items():
            rel = [bool(re.search(pat, disorders(n["text"]), re.I)) for n in notes]
            case = {"patient": f.stem[:8], "query": q, "note_dates": [n["date"] for n in notes],
                    "reference": {"relevant": rel, "any": any(rel),
                                  "lay_keyword_hits": [bool(re.search(lay, n["text"], re.I)) for n in notes]}}
            (pos if any(rel) else neg)[q].append(case)
    cases = []
    for q in QUERIES:
        k = min(len(pos[q]), (PER_QUERY + 1) // 2)
        cases += pos[q][:k] + neg[q][: PER_QUERY - k]
    return cases


def _notes(case: dict) -> list[dict]:
    f = next(R5_DIR.glob(f"{case['patient']}*.json"))
    return notes_of(json.loads(f.read_text()))


def state(case: dict) -> dict:
    return {"query": case["query"], "notes": [{"id": f"note_{i}", **n} for i, n in enumerate(_notes(case))]}


def questions(case: dict) -> dict:
    n = len(case["note_dates"])
    qs = {f"note_{i}": noul(f"Does `notes[{i}].text` contain information showing that the answer to `query` is yes?")
          for i in range(n)}
    qs["best"] = choice("Which note is the best evidence for answering `query` with yes?",
                        {f"note_{i}": f"`notes[{i}]`" for i in range(n)} | {"none": "No note shows the answer is yes"})
    qs["any"] = noul("Taking all of `notes` together, is the answer to `query` yes?")
    return qs


def uncertain(case: dict, answers: dict) -> list[str]:
    return ["uncertain patient-level answer"] if 0.2 < answers["any"]["noul"] < 0.8 else []


def main() -> None:
    cases = build_cases()
    out = {"scenario": "s4_search", "title": "Semantic search over clinical notes", "seed": SEED,
           "setting": "A clinician asks a plain-language question about a patient's history; the system searches the patient's 10 most recent notes.",
           "cases": cases}
    (SCENARIO_DIR / "s4_search.json").write_text(json.dumps(out, indent=1) + "\n")
    print(len(cases), "cases,", sum(c["reference"]["any"] for c in cases), "positive")


if __name__ == "__main__":
    main()
