"""Shared helpers: scenario loading, patient lookup, question constructors."""

from __future__ import annotations

import json
from functools import cache

from .cohort import load_cohort
from .fhir import ROOT

SCENARIO_DIR = ROOT / "data" / "scenarios"
RESULTS_DIR = ROOT / "results"
YES = 0.5  # Noul decision threshold used throughout; see report for sensitivity.


def load_scenario(name: str) -> dict:
    return json.loads((SCENARIO_DIR / f"{name}.json").read_text())


@cache
def _patients() -> dict[str, dict]:
    return {p["id"]: p for p in load_cohort()}


def patient(prefix: str) -> dict:
    matches = [p for pid, p in _patients().items() if pid.startswith(prefix)]
    assert len(matches) == 1, prefix
    return matches[0]


def noul(instructions, true: str | None = None, false: str | None = None) -> dict:
    q = {"type": "noul", "instructions": instructions}
    if true or false:
        q["criteria"] = {"true": true, "false": false}
    return q


def choice(instructions, options: dict) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": options}


def score(instructions, levels: list) -> dict:
    return {"type": "score", "instructions": instructions, "criteria": levels}
