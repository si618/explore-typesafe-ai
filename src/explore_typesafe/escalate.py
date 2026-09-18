"""Build the System Two review packet: every uncertain judgment, without Jev's answer
or the reference label, in the same typed answer space as the original question.

The reviewer (a Claude model) writes `results/system_two_review.json`:
{"<scenario>/<patient>/<question_id>": {"answer": <option key | level index | true/false>, "rationale": "..."}}
"""

from __future__ import annotations

import json
from importlib import import_module

from .common import RESULTS_DIR, load_scenario
from .run import SCENARIOS

# Which question each uncertainty reason maps to.
S3_REASON_QUESTIONS = {
    "low route confidence": ["route"],
    "uncertain red flag": ["red_flag"],
    "route and urgency disagree": ["route", "urgency"],
    "red flag but non-emergency route": ["route", "red_flag"],
    "safeguarding concern: human review required": ["safeguarding"],
}


def _flagged_questions(name: str, answers: dict, reasons: list[str]) -> list[str]:
    if name == "s3_inbox":
        # An escalated message always gets a reviewed route: that is the decision that acts.
        return sorted({"route", *(q for r in reasons for q in S3_REASON_QUESTIONS[r])}) if reasons else []
    out = []
    for r in reasons:
        if r.startswith("uncertain "):
            out.append(r.removeprefix("uncertain "))
        elif r == "low concern confidence":
            out.append("concern")
        elif r.startswith("low confidence on"):
            out += [k for k, a in answers.items() if k.startswith("med_") and a["confidence"] < 0.5]
    return out


def build() -> list[dict]:
    items = []
    for name in SCENARIOS:
        mod = import_module(f"explore_typesafe.{name}")
        cases = {c["patient"]: c for c in load_scenario(name)["cases"]}
        results = json.loads((RESULTS_DIR / f"{name}.json").read_text())
        for r in results["cases"]:
            reasons = mod.uncertain(cases[r["patient"]], r["answers"])
            for qid in _flagged_questions(name, r["answers"], reasons):
                q = r["questions"][qid]
                items.append({
                    "id": f"{name}/{r['patient']}/{qid}",
                    "setting": load_scenario(name)["setting"],
                    "state": r["state"],
                    "question": q,
                    "answer_format": {
                        "noul": "true or false",
                        "choice": "one option key from criteria",
                        "score": "integer level index into criteria (0-based)",
                    }[q["type"]],
                })
    return items


if __name__ == "__main__":
    items = build()
    (RESULTS_DIR / "system_two_packet.json").write_text(json.dumps(items, indent=1) + "\n")
    print(len(items), "items;", {s: sum(i["id"].startswith(s) for i in items) for s in SCENARIOS})
