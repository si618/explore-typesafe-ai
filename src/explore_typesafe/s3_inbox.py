"""Scenario 3: post-discharge patient message inbox.

A Choice routes the message, a Score grades urgency, and three Nouls detect red
flags, medication problems and safeguarding concerns. Code auto-dispatches only
when the answers are confident and agree with each other; everything else is
escalated to a System Two reviewer (a Claude model).
"""

from __future__ import annotations

from .common import YES, choice, noul, patient, score

ROUTES = {
    "emergency_services": "Possible life-threatening emergency now: advise calling emergency services and alert the on-call doctor",
    "on_call_clinician": "New or worsening symptoms that could become serious today: a doctor or senior nurse calls back within 2 hours",
    "nurse_callback": "A clinical question or mild symptom that a nurse can handle within 1 working day",
    "pharmacist": "A question about medication supply, doses, side effects or interactions that a pharmacist can resolve",
    "admin": "Appointments, letters, feedback or other non-clinical requests",
}
QUESTIONS = {
    "route": choice("Who should handle `message` first?", ROUTES),
    "urgency": score(
        "How soon does `message` need a response from a clinician?",
        [
            "Can wait up to 3 working days: an administrative or routine question with no symptoms",
            "Within 1 working day: mild symptoms or a medication question with no immediate risk",
            "Within 2 hours: new or worsening symptoms that could become serious today",
            "Immediately: symptoms or statements suggesting a life-threatening emergency or immediate risk to life",
        ],
    ),
    "red_flag": noul(
        "Does `message` describe a situation that may be a life-threatening emergency needing immediate care, such as "
        "signs of a heart attack, stroke, anaphylaxis, major bleeding, sepsis, or intent to self-harm?"
    ),
    "medication_issue": noul(
        "Does `message` report a problem with the patient's medication, such as a side effect, missed or incorrect "
        "doses, stopping a medicine, running out, or confusion about instructions?"
    ),
    "safeguarding": noul(
        "Does `message` indicate that the patient, or someone they care for, may be unsafe at home or at risk of "
        "harm from themselves or others?"
    ),
}
ROUTE_URGENCY = {"emergency_services": 3, "on_call_clinician": 2, "nurse_callback": 1, "pharmacist": 1, "admin": 0}


def state(case: dict) -> dict:
    p = patient(case["patient"])
    return {
        "patient": {"age": p["age"], "sex": p["sex"], "active_conditions": p["active_conditions"],
                    "active_medications": p["active_medications"]},
        "discharge_reason": case["discharge_reason"],
        "message": case["message"],
    }


def questions(case: dict) -> dict:
    return QUESTIONS


def decide(case: dict, answers: dict) -> dict:
    route = answers["route"]
    urgency = answers["urgency"]["score"]
    red = answers["red_flag"]["noul"]
    reasons = []
    if route["confidence"] < 0.6:
        reasons.append("low route confidence")
    if 0.2 < red < 0.8:
        reasons.append("uncertain red flag")
    if abs(ROUTE_URGENCY[route["choice"]] - urgency) > 1:
        reasons.append("route and urgency disagree")
    if red >= YES and route["choice"] != "emergency_services":
        reasons.append("red flag but non-emergency route")
    if answers["safeguarding"]["noul"] >= YES:
        reasons.append("safeguarding concern: human review required")
    return {"route": route["choice"], "urgency": round(urgency), "escalate": bool(reasons), "reasons": reasons}


def uncertain(case: dict, answers: dict) -> list[str]:
    return decide(case, answers)["reasons"]
