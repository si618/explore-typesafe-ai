"""Prepare and score an independent, blinded label sample.

The packet deliberately contains no Jev answers or reference labels.  A labeler
can answer it offline and write ``labels.json`` using the schema documented in
``data/independent_labels/README.md``; this module then computes agreement.
"""

from __future__ import annotations

import json
from datetime import date
from importlib import import_module
from pathlib import Path

from .common import RESULTS_DIR, YES, load_scenario
from .run import SCENARIOS

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "independent_labels"
SAMPLE_SIZE = 15


def _run(name: str) -> dict:
    return json.loads((RESULTS_DIR / f"{name}.json").read_text())


def _question_ids(name: str, result: dict) -> list[str]:
    return list(result["cases"][0]["answers"])


def _select_cases(name: str) -> list[str]:
    """Select 15 cases, prioritising ambiguity and Jev/reference disagreement."""
    scenario = load_scenario(name)
    results = _run(name)
    mod = import_module(f"explore_typesafe.{name}")
    cases = {c["patient"]: c for c in scenario["cases"]}
    ranked: list[tuple[int, str]] = []
    for result in results["cases"]:
        case = cases[result["patient"]]
        reasons = 0
        if case["reference"].get("ambiguous"):
            reasons += 2
        answers = result["answers"]
        for qid, answer in answers.items():
            if qid.startswith("med_"):
                continue
            value = answer.get("choice", round(answer.get("score", answer.get("noul", 0))))
            derived = mod.reference(case) if hasattr(mod, "reference") else case["reference"]
            truth = derived.get(qid, case["reference"].get(qid))
            if isinstance(truth, list):
                mismatch = value not in truth
            else:
                mismatch = value != truth
            reasons += mismatch
        ranked.append((reasons, result["patient"]))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    return [patient for _, patient in ranked[:SAMPLE_SIZE]]


def build_packet() -> list[dict]:
    """Build a case-stratified packet without answers or references."""
    packet = []
    for name in SCENARIOS:
        scenario = load_scenario(name)
        cases = {c["patient"]: c for c in scenario["cases"]}
        results = {r["patient"]: r for r in _run(name)["cases"]}
        for patient in _select_cases(name):
            result = results[patient]
            for qid, question in result["questions"].items():
                packet.append({
                    "id": f"{name}/{patient}/{qid}",
                    "scenario": name,
                    "patient": patient,
                    "setting": scenario["setting"],
                    "state": result["state"],
                    "question": question,
                    "answer_format": {
                        "noul": "true or false",
                        "choice": "one option key from criteria",
                        "score": "integer level index into criteria (0-based)",
                    }[question["type"]],
                })
    return packet


def _truth(name: str, patient: str, qid: str):
    scenario = load_scenario(name)
    case = next(c for c in scenario["cases"] if c["patient"] == patient)
    if name == "s2_discharge" and qid.startswith("med_"):
        return import_module(f"explore_typesafe.{name}").reference_statuses(case)[int(qid[4:])]
    return case["reference"][qid]


def _match(truth, other):
    """A list reference accepts any of its answers (as in evaluate.py); otherwise use its first."""
    if isinstance(truth, list):
        return other if other in truth else truth[0]
    return truth


def _jev(answer: dict):
    if "noul" in answer:
        return answer["noul"] >= YES
    if "score" in answer:
        return round(answer["score"])
    return answer["choice"]


def compare(labels: dict) -> list[dict]:
    rows = []
    results = {name: {r["patient"]: r for r in _run(name)["cases"]} for name in SCENARIOS}
    for item in build_packet():
        if item["id"] not in labels:
            continue
        name, patient, qid = item["id"].split("/")
        rows.append({"id": item["id"], "type": item["question"]["type"], "reference": _truth(name, patient, qid),
                     "independent": labels[item["id"]], "jev": _jev(results[name][patient]["answers"][qid])})
    return rows


def agreement(rows: list[dict]) -> dict:
    """Compute unweighted κ for Nouls/Choices and weighted κ for Scores."""
    from sklearn.metrics import cohen_kappa_score

    def kappa(a, b, kind):
        kwargs = {"weights": "quadratic"} if kind == "score" else {}
        return cohen_kappa_score(a, b, **kwargs)

    out = {"n": len(rows), "by_type": {}}
    for kind in ("noul", "choice", "score"):
        subset = [r for r in rows if r["type"] == kind]
        if not subset:
            continue
        ind, jev = [r["independent"] for r in subset], [r["jev"] for r in subset]
        out["by_type"][kind] = {
            "n": len(subset),
            "reference_vs_independent": kappa([_match(r["reference"], r["independent"]) for r in subset], ind, kind),
            "jev_vs_independent": kappa(jev, ind, kind),
            "jev_vs_reference": kappa(jev, [_match(r["reference"], r["jev"]) for r in subset], kind),
            "reference_independent_disagreements": sum(_match(r["reference"], r["independent"]) != r["independent"]
                                                       for r in subset),
        }
    return out


def disagreements(rows: list[dict]) -> list[dict]:
    """Every judgment where the independent label differs from the reference, with Jev's answer; both kept."""
    return [r for r in rows if _match(r["reference"], r["independent"]) != r["independent"]]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    packet = build_packet()
    (OUT / "packet.json").write_text(json.dumps(packet, indent=2) + "\n")
    labels_path = OUT / "labels.json"
    labels = json.loads(labels_path.read_text()) if labels_path.exists() else {}
    rows = compare(labels)
    (OUT / "agreement.json").write_text(json.dumps(agreement(rows), indent=2) + "\n")
    (OUT / "disagreements.json").write_text(json.dumps(disagreements(rows), indent=1) + "\n")
    print(f"wrote {len(packet)} blinded items and agreement.json")


if __name__ == "__main__":
    main()
