"""Scenario 1: ward deterioration huddle.

Code computes NEWS2 from charted observations (arithmetic stays in code). Jev reads
the nursing note for the things NEWS2 cannot see: new confusion that was not
charted, suspected infection, how worried the nurse is, and the type of problem.
"""

from __future__ import annotations

from .common import YES, choice, noul, patient, score

BANDS = ["routine", "ward_review", "urgent_review", "emergency"]

QUESTIONS = {
    "new_confusion": noul(
        "Does `nursing_note` describe a new change in the patient's mental state or level of consciousness "
        "compared with their usual baseline, such as new confusion, disorientation, agitation, hallucinations, "
        "drowsiness or reduced responsiveness?",
        true="A change from the patient's usual mental state is described, even if they have dementia or a learning disability at baseline.",
        false="Mental state is normal, or unchanged from a known baseline such as long-standing dementia that is as usual.",
    ),
    "infection": noul(
        "Does `nursing_note` describe signs of a current infection, an infection being treated, or a suspicion of infection?",
        true="For example fever, rigors, purulent sputum, urinary symptoms, spreading redness, or an infection under treatment.",
        false="No infection signs are described, or infection is explicitly ruled out.",
    ),
    "concern": score(
        "How worried should the ward team be about this patient right now, based on `nursing_note`?",
        [
            "Stable or improving, no new problems; routine care",
            "A minor issue to keep monitoring, with no clinical review needed today",
            "A worrying change that needs a doctor to assess within the hour, such as a behaviour change, an event that has since resolved, or family saying the patient is not themselves",
            "Acute deterioration happening now that needs immediate senior review or the rapid response team",
        ],
    ),
    "pattern": choice(
        "What is the main type of clinical deterioration described in `nursing_note`?",
        {
            "sepsis_infection": "Infection causing systemic illness: fever or rigors with fast heart rate, low blood pressure, new confusion or low urine output",
            "respiratory": "Worsening breathing, rising oxygen requirement or low oxygen saturation",
            "cardiac": "Chest pain, arrhythmia, or collapse from a heart cause",
            "neurological": "Stroke, head injury, seizure, delirium, or reduced consciousness from a brain cause",
            "bleeding": "Blood loss, such as black stools, vomiting blood, or bleeding with falling blood pressure",
            "metabolic_renal": "Blood sugar, electrolyte, calcium, fluid balance or kidney problems",
            "drug_or_substance": "Medication toxicity, over-sedation, or alcohol or drug withdrawal",
            "other": "A concerning change that fits none of the other options",
            "no_acute_change": "No deterioration: stable, improving, or at baseline",
        },
    ),
}


def state(case: dict) -> dict:
    p = patient(case["patient"])
    return {
        "patient": {"age": p["age"], "sex": p["sex"], "active_conditions": p["active_conditions"]},
        "admission_reason": case["admission"],
        "nursing_note": case["note"],
    }


def questions(case: dict) -> dict:
    return QUESTIONS


# --- deterministic policy -------------------------------------------------------

def _band(value: float, bands: list[tuple[float, float, int]]) -> int:
    return next(pts for lo, hi, pts in bands if lo <= value <= hi)


def news2(obs: dict, acvpu: str | None = None) -> tuple[int, bool]:
    """Royal College of Physicians NEWS2. Returns (total, any single parameter scored 3)."""
    inf = float("inf")
    parts = [
        _band(obs["rr"], [(0, 8, 3), (9, 11, 1), (12, 20, 0), (21, 24, 2), (25, inf, 3)]),
        _band(obs["sbp"], [(0, 90, 3), (91, 100, 2), (101, 110, 1), (111, 219, 0), (220, inf, 3)]),
        _band(obs["hr"], [(0, 40, 3), (41, 50, 1), (51, 90, 0), (91, 110, 1), (111, 130, 2), (131, inf, 3)]),
        _band(obs["temp"], [(0, 35.0, 3), (35.05, 36.0, 1), (36.05, 38.0, 0), (38.05, 39.0, 1), (39.05, inf, 2)]),
        2 if obs["on_o2"] else 0,
        0 if (acvpu or obs["acvpu"]) == "A" else 3,
    ]
    s = obs["spo2"]
    if obs["spo2_scale"] == 2:  # hypercapnic target 88-92%
        if obs["on_o2"] and s >= 93:
            parts.append(_band(s, [(93, 94, 1), (95, 96, 2), (97, 100, 3)]))
        else:
            parts.append(_band(s, [(0, 83, 3), (84, 85, 2), (86, 87, 1), (88, 100, 0)]))
    else:
        parts.append(_band(s, [(0, 91, 3), (92, 93, 2), (94, 95, 1), (96, 100, 0)]))
    return sum(parts), 3 in parts


def news2_band(total: int, red: bool) -> int:
    if total >= 7:
        return 3
    if total >= 5 or red:
        return 2
    return 1 if total >= 1 else 0


def decide(case: dict, answers: dict) -> dict:
    obs = case["obs"]
    charted, charted_red = news2(obs)
    confused = answers["new_confusion"]["noul"] >= YES
    acvpu = "C" if confused and obs["acvpu"] == "A" else obs["acvpu"]
    augmented, red = news2(obs, acvpu)
    concern = answers["concern"]["score"]
    band = max(news2_band(augmented, red), round(concern))
    return {
        "news2_charted": charted,
        "news2_augmented": augmented,
        "baseline_band": news2_band(charted, charted_red),
        "band": band,
        "sepsis_screen": answers["infection"]["noul"] >= YES and augmented >= 5,
        "priority": band * 100 + augmented + 2 * concern,
    }


def reference(case: dict) -> dict:
    ref = case["reference"]
    obs = case["obs"]
    acvpu = "C" if ref["new_confusion"] and obs["acvpu"] == "A" else obs["acvpu"]
    total, red = news2(obs, acvpu)
    return {"news2": total, "band": max(news2_band(total, red), ref["concern"])}


def uncertain(case: dict, answers: dict) -> list[str]:
    reasons = [f"uncertain {k}" for k in ("new_confusion", "infection") if 0.2 < answers[k]["noul"] < 0.8]
    if answers["concern"]["confidence"] < 0.5:
        reasons.append("low concern confidence")
    return reasons
