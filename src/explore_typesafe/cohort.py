"""Deterministic assignment of cohort patients to scenarios."""

from __future__ import annotations

import json

from .fhir import ROOT

SCENARIO_SIZE = 20


def load_cohort() -> list[dict]:
    return json.loads((ROOT / "data" / "cohort.json").read_text())


def assign() -> dict[str, list[dict]]:
    """Ward = oldest multimorbid; discharge = most medications; inbox = the rest with a problem list."""
    pool = sorted(load_cohort(), key=lambda p: p["id"])
    ward = sorted(
        (p for p in pool if p["age"] >= 55),
        key=lambda p: (-len(p["active_conditions"]), p["id"]),
    )[:SCENARIO_SIZE]
    taken = {p["id"] for p in ward}
    discharge = sorted(
        (p for p in pool if p["id"] not in taken),
        key=lambda p: (-(len(p["active_medications"]) + 3 * bool(p["allergies"])), p["id"]),
    )[:SCENARIO_SIZE]
    taken |= {p["id"] for p in discharge}
    inbox = [p for p in pool if p["id"] not in taken and p["active_conditions"]][:SCENARIO_SIZE]
    return {"s1_ward": ward, "s2_discharge": discharge, "s3_inbox": inbox}


if __name__ == "__main__":
    for name, patients in assign().items():
        print(f"\n##### {name}")
        for i, p in enumerate(patients):
            print(f"[{i}] {p['id'][:8]} {p['name']}, {p['age']}{p['sex'][0].upper()}")
            print("   cond:", "; ".join(p["active_conditions"]))
            print("   meds:", "; ".join(p["active_medications"]))
            if p["allergies"]:
                print("   allergy:", "; ".join(p["allergies"]))
