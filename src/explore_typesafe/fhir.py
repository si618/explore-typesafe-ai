"""Synthea FHIR R4 bundles -> validated FHIR R5 clinical snapshots.

Synthea exports FHIR R4 (US Core). The scenarios only need a clinical snapshot of
each patient (demographics, active problems, allergies, active medications, the
latest labs/vitals and recent encounters), so we map those resources to FHIR R5
and validate them against the R5 models in `fhir.resources`. Billing resources
(Claim, ExplanationOfBenefit) and history are left in the raw R4 bundles.
"""

from __future__ import annotations

import gzip
import json
import re
from datetime import date
from pathlib import Path

from fhir.resources.bundle import Bundle

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "synthea-r4"
R5_DIR = ROOT / "data" / "fhir-r5"

# LOINC codes kept as "latest value" observations.
LOINC = {
    "8867-4": "heart_rate",
    "9279-1": "respiratory_rate",
    "8310-5": "temperature",
    "2708-6": "spo2",
    "59408-5": "spo2",
    "85354-9": "blood_pressure",
    "39156-5": "bmi",
    "4548-4": "hba1c",
    "2160-0": "creatinine",
    "33914-3": "egfr",
    "6298-4": "potassium",
    "718-7": "haemoglobin",
    "2093-3": "total_cholesterol",
}
AS_OF = date(2026, 9, 19)  # snapshot date used for ages


def _concept(cc: dict | None) -> dict | None:
    if not cc:
        return None
    return {k: v for k, v in cc.items() if k in ("coding", "text")}


def _patient(r: dict) -> dict:
    return {
        "resourceType": "Patient",
        "id": r["id"],
        "identifier": [i for i in r.get("identifier", []) if i.get("system") == "https://github.com/synthetichealth/synthea"],
        "name": [{k: v for k, v in n.items() if k in ("use", "family", "given", "prefix")} for n in r.get("name", [])[:1]],
        "gender": r["gender"],
        "birthDate": r["birthDate"],
        "address": [{k: v for k, v in a.items() if k in ("city", "state", "postalCode", "country")} for a in r.get("address", [])[:1]],
    }


def _condition(r: dict, subject: dict) -> dict:
    out = {
        "resourceType": "Condition",
        "id": r["id"],
        "clinicalStatus": r["clinicalStatus"],
        "verificationStatus": r.get("verificationStatus"),
        "category": r.get("category"),
        "code": _concept(r["code"]),
        "subject": subject,
        "onsetDateTime": r.get("onsetDateTime"),
        "recordedDate": r.get("recordedDate"),
        "abatementDateTime": r.get("abatementDateTime"),
    }
    return {k: v for k, v in out.items() if v is not None}


def _allergy(r: dict, subject: dict) -> dict:
    out = {
        "resourceType": "AllergyIntolerance",
        "id": r["id"],
        "clinicalStatus": r.get("clinicalStatus"),
        "verificationStatus": r.get("verificationStatus"),
        "category": r.get("category"),
        "criticality": r.get("criticality"),
        "code": _concept(r["code"]),
        "patient": subject,
        "recordedDate": r.get("recordedDate"),
    }
    # R5: `type` became a CodeableConcept.
    if r.get("type"):
        out["type"] = {"coding": [{"system": "http://hl7.org/fhir/allergy-intolerance-type", "code": r["type"]}]}
    # R5: reaction.manifestation became CodeableReference(Observation).
    reactions = []
    for rx in r.get("reaction", []):
        reactions.append(
            {k: v for k, v in {
                "manifestation": [{"concept": _concept(m)} for m in rx.get("manifestation", [])],
                "severity": rx.get("severity"),
            }.items() if v}
        )
    if reactions:
        out["reaction"] = reactions
    return {k: v for k, v in out.items() if v is not None}


def _dosage(d: dict) -> dict:
    d = dict(d)
    # R5: asNeeded[x] became `asNeeded` (boolean) + `asNeededFor`.
    if "asNeededBoolean" in d:
        d["asNeeded"] = d.pop("asNeededBoolean")
    if "asNeededCodeableConcept" in d:
        d["asNeeded"] = True
        d["asNeededFor"] = [d.pop("asNeededCodeableConcept")]
    return d


def _medication_request(r: dict, subject: dict) -> dict | None:
    if "medicationCodeableConcept" not in r:
        return None
    out = {
        "resourceType": "MedicationRequest",
        "id": r["id"],
        "status": r["status"],
        "intent": r["intent"],
        "category": r.get("category"),
        # R5: medication[x] became `medication` (CodeableReference).
        "medication": {"concept": _concept(r["medicationCodeableConcept"])},
        "subject": subject,
        "authoredOn": r.get("authoredOn"),
        "dosageInstruction": [_dosage(d) for d in r.get("dosageInstruction", [])] or None,
    }
    # R5: reasonCode/reasonReference merged into `reason` (CodeableReference).
    reasons = [{"concept": {"text": rr["display"]}} for rr in r.get("reasonReference", []) if rr.get("display")]
    if reasons:
        out["reason"] = reasons
    return {k: v for k, v in out.items() if v is not None}


def _observation(r: dict, subject: dict) -> dict:
    out = {
        "resourceType": "Observation",
        "id": r["id"],
        "status": r["status"],
        "category": r.get("category"),
        "code": _concept(r["code"]),
        "subject": subject,
        "effectiveDateTime": r.get("effectiveDateTime"),
        "valueQuantity": r.get("valueQuantity"),
        "valueCodeableConcept": r.get("valueCodeableConcept"),
        "component": [
            {k: v for k, v in c.items() if k in ("code", "valueQuantity")} for c in r.get("component", [])
        ] or None,
    }
    return {k: v for k, v in out.items() if v is not None}


def _encounter(r: dict, subject: dict) -> dict:
    out = {
        "resourceType": "Encounter",
        "id": r["id"],
        "status": "completed" if r["status"] == "finished" else r["status"],  # R5 renamed finished -> completed
        # R5: `class` is now a list of CodeableConcept.
        "class": [{"coding": [r["class"]]}],
        "type": [_concept(t) for t in r.get("type", [])],
        "subject": subject,
        "actualPeriod": r.get("period"),  # R5: period -> actualPeriod
    }
    reasons = [_concept(c) for c in r.get("reasonCode", [])]
    if reasons:
        out["reason"] = [{"value": [{"concept": c} for c in reasons]}]
    return out


def to_r5_snapshot(r4_bundle: dict, recent_encounters: int = 5) -> dict:
    resources = [e["resource"] for e in r4_bundle["entry"]]
    by_type: dict[str, list[dict]] = {}
    for r in resources:
        by_type.setdefault(r["resourceType"], []).append(r)

    patient = by_type["Patient"][0]
    subject = {"reference": f"urn:uuid:{patient['id']}"}
    out: list[dict] = [_patient(patient)]

    for c in by_type.get("Condition", []):
        if c["clinicalStatus"]["coding"][0]["code"] == "active":
            out.append(_condition(c, subject))
    for a in by_type.get("AllergyIntolerance", []):
        out.append(_allergy(a, subject))

    seen_meds: set[str] = set()
    for m in sorted(by_type.get("MedicationRequest", []), key=lambda m: m.get("authoredOn", ""), reverse=True):
        if m["status"] != "active":
            continue
        mr = _medication_request(m, subject)
        if mr and mr["medication"]["concept"]["text"].lower() not in seen_meds:
            seen_meds.add(mr["medication"]["concept"]["text"].lower())
            out.append(mr)

    latest: dict[str, dict] = {}
    for o in by_type.get("Observation", []):
        codes = [c["code"] for c in o["code"].get("coding", [])]
        key = next((LOINC[c] for c in codes if c in LOINC), None)
        if key and o.get("effectiveDateTime", "") > latest.get(key, {}).get("effectiveDateTime", ""):
            latest[key] = o
    out.extend(_observation(o, subject) for o in latest.values())

    encounters = sorted(by_type.get("Encounter", []), key=lambda e: e["period"]["start"], reverse=True)
    out.extend(_encounter(e, subject) for e in encounters[:recent_encounters])

    bundle = {
        "resourceType": "Bundle",
        "id": f"snapshot-{patient['id']}",
        "type": "collection",
        "timestamp": f"{AS_OF.isoformat()}T00:00:00Z",
        "entry": [{"fullUrl": f"urn:uuid:{r['id']}", "resource": r} for r in out],
    }
    Bundle.model_validate(bundle)  # raises if anything is not valid R5
    return bundle


def summarise(bundle: dict) -> dict:
    """Compact, human-readable view of an R5 snapshot, used to build Jev state."""
    res = [e["resource"] for e in bundle["entry"]]
    p = next(r for r in res if r["resourceType"] == "Patient")
    born = date.fromisoformat(p["birthDate"])
    age = AS_OF.year - born.year - ((AS_OF.month, AS_OF.day) < (born.month, born.day))
    name = p["name"][0]
    obs = {}
    for o in (r for r in res if r["resourceType"] == "Observation"):
        key = next(LOINC[c["code"]] for c in o["code"]["coding"] if c["code"] in LOINC)
        if "valueQuantity" in o:
            obs[key] = f"{round(o['valueQuantity']['value'], 1)} {o['valueQuantity'].get('unit', '')}".strip()
        elif "component" in o:
            parts = {c["code"]["coding"][0]["code"]: round(c["valueQuantity"]["value"]) for c in o["component"]}
            obs[key] = f"{parts.get('8480-6')}/{parts.get('8462-4')} mmHg"  # systolic/diastolic
    return {
        "id": p["id"],
        # Synthea appends digits to names ("Trinidad33"); strip them for readability.
        "name": re.sub(r"\d+", "", " ".join([*name.get("given", []), name.get("family", "")])),
        "age": age,
        "sex": p["gender"],
        "active_conditions": sorted({
            r["code"]["text"].replace(" (disorder)", "")
            for r in res
            if r["resourceType"] == "Condition" and "(disorder)" in r["code"]["text"]
        }),
        "allergies": sorted({r["code"]["text"] for r in res if r["resourceType"] == "AllergyIntolerance"}),
        "active_medications": [r["medication"]["concept"]["text"] for r in res if r["resourceType"] == "MedicationRequest"],
        "latest_results": obs,
    }


def load_snapshots() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in sorted(R5_DIR.glob("*.json"))}


def build_all() -> None:
    R5_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(RAW_DIR.glob("*.json.gz")):
        bundle = to_r5_snapshot(json.load(gzip.open(path)))
        pid = bundle["entry"][0]["resource"]["id"]
        (R5_DIR / f"{pid}.json").write_text(json.dumps(bundle, indent=1))
    summaries = [summarise(b) for b in load_snapshots().values()]
    (ROOT / "data" / "cohort.json").write_text(json.dumps(summaries, indent=1))
    print(f"wrote {len(summaries)} validated R5 snapshots")


if __name__ == "__main__":
    build_all()
