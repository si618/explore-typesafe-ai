"""Express the authored scenario inputs as validated FHIR R5 resources.

- s1: vital signs -> Observation (LOINC); nursing note -> DocumentReference (LOINC 34746-8 Nurse note)
- s2: discharge medication section -> DocumentReference (LOINC 18842-5 Discharge summary)
- s3: patient portal message -> Communication (patient -> hospital)
"""

from __future__ import annotations

import base64
import json
import uuid

from fhir.resources.bundle import Bundle

from .common import load_scenario, patient
from .fhir import ROOT

OUT = ROOT / "data" / "fhir-r5-scenarios"
WHEN = "2026-09-18T19:30:00+09:30"
VITALS = {  # key: (LOINC, display, UCUM unit)
    "rr": ("9279-1", "Respiratory rate", "/min"),
    "spo2": ("59408-5", "Oxygen saturation in Arterial blood by Pulse oximetry", "%"),
    "sbp": ("8480-6", "Systolic blood pressure", "mm[Hg]"),
    "hr": ("8867-4", "Heart rate", "/min"),
    "temp": ("8310-5", "Body temperature", "Cel"),
}


def _id(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "/".join(parts)))


def _doc(pid: str, key: str, loinc: tuple[str, str], text: str) -> dict:
    return {
        "resourceType": "DocumentReference", "id": _id(pid, key), "status": "current",
        "type": {"coding": [{"system": "http://loinc.org", "code": loinc[0], "display": loinc[1]}]},
        "subject": {"reference": f"Patient/{pid}"}, "date": WHEN,
        "content": [{"attachment": {"contentType": "text/plain", "data": base64.b64encode(text.encode()).decode()}}],
    }


def s1(case: dict, pid: str) -> list[dict]:
    obs = case["obs"]
    out = [{
        "resourceType": "Observation", "id": _id(pid, k), "status": "final",
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs"}]}],
        "code": {"coding": [{"system": "http://loinc.org", "code": code, "display": disp}]},
        "subject": {"reference": f"Patient/{pid}"}, "effectiveDateTime": WHEN,
        "valueQuantity": {"value": obs[k], "unit": unit, "system": "http://unitsofmeasure.org", "code": unit},
    } for k, (code, disp, unit) in VITALS.items()]
    out.append({
        "resourceType": "Observation", "id": _id(pid, "acvpu"), "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "67775-7", "display": "Level of responsiveness"}]},
        "subject": {"reference": f"Patient/{pid}"}, "effectiveDateTime": WHEN,
        "valueCodeableConcept": {"text": {"A": "Alert", "V": "Responds to voice"}.get(obs["acvpu"], obs["acvpu"])},
        "note": [{"text": f"Supplemental oxygen: {'yes' if obs['on_o2'] else 'no'}; SpO2 scale {obs['spo2_scale']}"}],
    })
    out.append(_doc(pid, "nursing_note", ("34746-8", "Nurse Note"), case["note"]))
    return out


def s2(case: dict, pid: str) -> list[dict]:
    return [_doc(pid, "discharge_meds", ("18842-5", "Discharge summary"), case["discharge_text"])]


def s3(case: dict, pid: str) -> list[dict]:
    return [{
        "resourceType": "Communication", "id": _id(pid, "message"), "status": "completed",
        "subject": {"reference": f"Patient/{pid}"}, "sender": {"reference": f"Patient/{pid}"},
        "sent": WHEN, "payload": [{"contentCodeableConcept": {"text": case["message"]}}],
    }]


def build() -> None:
    for name, fn in (("s1_ward", s1), ("s2_discharge", s2), ("s3_inbox", s3)):
        (OUT / name).mkdir(parents=True, exist_ok=True)
        for case in load_scenario(name)["cases"]:
            pid = patient(case["patient"])["id"]
            bundle = {"resourceType": "Bundle", "type": "collection",
                      "entry": [{"fullUrl": f"urn:uuid:{r['id']}", "resource": r} for r in fn(case, pid)]}
            Bundle.model_validate(bundle)
            (OUT / name / f"{pid}.json").write_text(json.dumps(bundle, indent=1) + "\n")
    print("scenario bundles validated as FHIR R5")


if __name__ == "__main__":
    build()
