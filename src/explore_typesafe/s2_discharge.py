"""Scenario 2: discharge medication reconciliation.

One Choice per pre-admission medication (fanned out in a single request) extracts
what the discharge text does with it; three Nouls verify the regimen for allergy,
duplication and interaction problems; a Score grades how well changes are explained.
Code turns those into a pharmacist action.
"""

from __future__ import annotations

from .common import YES, choice, noul, patient, score

ACTIONS = ["release", "pharmacist_review", "hold"]
STATUS = {
    "continued": "Continued at the same dose, either named explicitly or covered by a blanket statement such as 'continue all other medications'",
    "dose_changed": "Still taken, but the dose, frequency or directions change, for example increased, reduced, or changed to as-needed",
    "withheld": "Paused temporarily, with a plan to restart later",
    "stopped": "Stopped, discontinued, completed, or replaced by a different drug",
    "not_mentioned": "Not named and not covered by any blanket statement, so its status at discharge is unknown",
}
VERIFY = {
    "allergy_conflict": noul(
        "Does `discharge_medication_text` prescribe a medication that belongs to the same drug class as one of the "
        "patient's drug allergies listed in `patient.allergies`? Brand names and combination products count.",
        true="A prescribed or continued medication contains a drug from an allergy's drug class.",
        false="No prescribed medication belongs to an allergy's drug class. Food, environmental and animal allergies do not count.",
    ),
    "duplicate_therapy": noul(
        "After discharge, will the patient be taking two or more medications with the same active ingredient or from "
        "the same therapeutic class for the same purpose, based on `pre_admission_medications` and `discharge_medication_text`?",
        true="Two or more concurrent medications share an active ingredient (including inside brand-name or combination products) or a therapeutic class.",
        false="Each active ingredient and therapeutic class appears once. Duplicates that the discharge text stops do not count.",
    ),
    "interaction": noul(
        "Does a medication newly started in `discharge_medication_text` have a well-known, clinically important "
        "interaction with another medication the patient will be taking after discharge?",
        true="A new medication has a recognised interaction that prescribing guidance says to avoid or to manage actively.",
        false="New medications have no clinically important interaction with the rest of the regimen, or no medication is newly started.",
    ),
}
JUSTIFICATION = score(
    "How well does `discharge_medication_text` explain the medication changes it makes?",
    [
        "Changes are made with no reasons given, or a blanket 'continue all' is used when the regimen clearly needed review",
        "New or changed medications are listed, but most have no reason or follow-up plan",
        "Most changes have a reason, but some reasons, durations or follow-up plans are missing",
        "Every change has a clear reason, with durations or follow-up plans where needed",
    ],
)


def state(case: dict) -> dict:
    p = patient(case["patient"])
    return {
        "patient": {"age": p["age"], "sex": p["sex"], "allergies": p["allergies"], "active_conditions": p["active_conditions"]},
        "admission_reason": case["admission"],
        "pre_admission_medications": p["active_medications"],
        "discharge_medication_text": case["discharge_text"],
    }


def questions(case: dict) -> dict:
    meds = patient(case["patient"])["active_medications"]
    qs = {
        f"med_{i}": choice(
            f"According to `discharge_medication_text`, what happens at discharge to the pre-admission medication "
            f"`pre_admission_medications[{i}]` ({m})?",
            STATUS,
        )
        for i, m in enumerate(meds)
    }
    return {**qs, **VERIFY, "justification": JUSTIFICATION}


def reference_statuses(case: dict) -> list[str]:
    """Map the reference's substring keys onto the FHIR medication list, one-to-one."""
    meds = patient(case["patient"])["active_medications"]
    out = []
    for m in meds:
        keys = [k for k in case["reference"]["med_status"] if k in m.lower()]
        # "simvastatin 10" beats "simvastatin" when both could match
        keys = [k for k in keys if not any(k != o and k in o for o in keys)]
        assert len(keys) == 1, (case["patient"], m, keys)
        out.append(case["reference"]["med_status"][keys[0]])
    assert len(set(out)) and len(out) == len(meds)
    return out


def _action(statuses: list[str], flags: dict[str, bool], justification: float) -> int:
    if any(flags.values()):
        return 2  # hold: pharmacist must intervene before the patient leaves
    if "not_mentioned" in statuses or justification < 1.5:
        return 1  # review: unreconciled medication or unexplained changes
    return 0


def decide(case: dict, answers: dict) -> dict:
    n = len(patient(case["patient"])["active_medications"])
    meds = [answers[f"med_{i}"] for i in range(n)]
    statuses = [m["choice"] for m in meds]
    # A low-confidence extraction is treated as unreconciled.
    statuses = [s if m["confidence"] >= 0.5 else "not_mentioned" for s, m in zip(statuses, meds)]
    flags = {k: answers[k]["noul"] >= YES for k in VERIFY}
    return {"statuses": [m["choice"] for m in meds], "flags": flags,
            "action": _action(statuses, flags, answers["justification"]["score"])}


def reference(case: dict) -> dict:
    ref = case["reference"]
    statuses = reference_statuses(case)
    flags = {k: ref[k] for k in VERIFY}
    return {"statuses": statuses, "flags": flags, "action": _action(statuses, flags, ref["justification"])}


def uncertain(case: dict, answers: dict) -> list[str]:
    reasons = [f"uncertain {k}" for k in VERIFY if 0.2 < answers[k]["noul"] < 0.8]
    n = len(patient(case["patient"])["active_medications"])
    low = [i for i in range(n) if answers[f"med_{i}"]["confidence"] < 0.5]
    if low:
        reasons.append(f"low confidence on {len(low)} medication status(es)")
    return reasons
