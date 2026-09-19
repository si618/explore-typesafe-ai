"""Scenario 5: Jev judgments as features for a classical prediction model.

Task: predict whether a patient has an emergency or inpatient encounter in the 12
months after an index date (2025-09-19), for all 1,000 patients.
- Outcome: Synthea's simulated encounters (class EMER or IMP), so labels are not
  written by any model.
- Structured baseline: age, sex, active chronic disorders, active medications,
  and emergency/inpatient use in the prior 12 months, all computed as of the index date.
- Jev features: typed judgments over the patient's most recent clinical note
  before the index date.
Models are logistic regressions evaluated with repeated stratified 5-fold
cross-validation (AUROC).
"""

from __future__ import annotations

import base64
import gzip
import json
from datetime import date

from .common import SCENARIO_DIR, choice, noul, score
from .fhir import RAW_DIR, RAW_EXTRA_DIR

INDEX = "2025-09-19"
END = "2026-09-19"
PRIOR = "2024-09-19"
ACUTE = {"EMER", "IMP"}

QUESTIONS = {
    "burden": score("How much chronic disease does `note` describe?", [
        "No chronic disease; only minor or acute problems",
        "One chronic condition, such as hypertension or asthma",
        "Several chronic conditions, such as diabetes with kidney or heart disease",
        "Advanced disease: heart failure, advanced kidney disease, cancer, dementia, or multiple organ involvement",
    ]),
    "cardiovascular": noul("Does `note` describe cardiovascular disease such as heart attack, coronary disease, heart failure or stroke?"),
    "respiratory": noul("Does `note` describe a chronic lung disease such as COPD, emphysema or asthma?"),
    "diabetes_complications": noul("Does `note` describe diabetes with complications affecting the kidneys, nerves or eyes?"),
    "mental_health": noul("Does `note` describe a mental health condition such as depression or anxiety?"),
    "substance": noul("Does `note` describe alcohol or drug misuse, overdose, or current smoking?"),
    "social_risk": noul("Does `note` describe social risk factors such as isolation, unemployment, housing problems, or limited social support?"),
    "polypharmacy": score("How complex is the medication list in `note`?", [
        "No regular medications",
        "One or two simple regular medications",
        "Several regular medications for different conditions",
        "Many medications including high-risk ones such as insulin, anticoagulants or opioids",
    ]),
    "recent_acute": noul("Does `note` describe a recent acute illness, injury, emergency visit or hospital admission?"),
    "dominant": choice("Which clinical area is the main concern in `note`?", {
        "cardiometabolic": "Heart, blood pressure, diabetes or cholesterol",
        "respiratory": "Lungs or breathing",
        "renal": "Kidneys",
        "neuro_cognitive": "Dementia, seizures, stroke or brain injury",
        "mental_substance": "Mental health or substance use",
        "musculoskeletal_injury": "Bones, joints or injuries",
        "cancer": "Cancer",
        "routine": "Routine care only, no significant problem",
    }),
}


def _age(birth: str, on: str) -> int:
    b, d = date.fromisoformat(birth), date.fromisoformat(on)
    return d.year - b.year - ((d.month, d.day) < (b.month, b.day))


def extract(path) -> dict:
    res = [e["resource"] for e in json.load(gzip.open(path))["entry"]]
    p = next(r for r in res if r["resourceType"] == "Patient")
    enc = [r for r in res if r["resourceType"] == "Encounter"]
    acute = [e["period"]["start"][:10] for e in enc if e["class"]["code"] in ACUTE]
    conds = [r for r in res if r["resourceType"] == "Condition" and "(disorder)" in r["code"]["text"]
             and r.get("onsetDateTime", "9999")[:10] <= INDEX and r.get("abatementDateTime", "9999")[:10] > INDEX]
    meds = {r["medicationCodeableConcept"]["text"] for r in res if r["resourceType"] == "MedicationRequest"
            and "medicationCodeableConcept" in r and r.get("authoredOn", "9999")[:10] <= INDEX
            and (r["status"] == "active" or r.get("dispenseRequest", {}).get("validityPeriod", {}).get("end", "0000")[:10] > INDEX)}
    notes = sorted((r for r in res if r["resourceType"] == "DocumentReference" and r["date"][:10] <= INDEX),
                   key=lambda r: r["date"])
    return {
        "patient": p["id"][:8],
        "structured": {
            "age": _age(p["birthDate"], INDEX),
            "female": p["gender"] == "female",
            "chronic_disorders": len({c["code"]["text"] for c in conds}),
            "medications": len(meds),
            "prior_acute_12m": sum(PRIOR < d <= INDEX for d in acute),
        },
        "note_date": notes[-1]["date"][:10],
        "note": base64.b64decode(notes[-1]["content"][0]["attachment"]["data"]).decode(),
        "reference": {"acute_12m": any(INDEX < d <= END for d in acute)},
    }


def build_cases() -> list[dict]:
    paths = sorted([*RAW_DIR.glob("*.json.gz"), *RAW_EXTRA_DIR.glob("*.json.gz")])
    return [extract(p) for p in paths]


def state(case: dict) -> dict:
    return {"note": case["note"]}


def questions(case: dict) -> dict:
    return QUESTIONS


def uncertain(case: dict, answers: dict) -> list[str]:
    return []


def main() -> None:
    cases = build_cases()
    out = {"scenario": "s5_features", "title": "Jev features for a utilisation prediction model", "index_date": INDEX,
           "setting": "Predict an emergency or inpatient encounter in the 12 months after the index date for every patient in the cohort.",
           "cases": cases}
    (SCENARIO_DIR / "s5_features.json").write_text(json.dumps(out, indent=1) + "\n")
    print(len(cases), "patients,", sum(c["reference"]["acute_12m"] for c in cases), "with the outcome")


if __name__ == "__main__":
    main()
