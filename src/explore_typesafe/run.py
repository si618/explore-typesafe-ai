"""Run every scenario case against Jev and store the raw results.

One request per case: all of a case's questions share one state and are answered
in parallel by the model. Requests are sent sequentially so latency is measured
without client-side contention.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from importlib import import_module

from typesafe_sdk import TypeSafeClient

from .common import RESULTS_DIR, load_scenario

SCENARIOS = ["s1_ward", "s2_discharge", "s3_inbox"]
MODEL = "jev-1.13.0"  # pinned rather than jev-latest so results are reproducible


def run(name: str, client: TypeSafeClient) -> dict:
    mod = import_module(f"explore_typesafe.{name}")
    scenario = load_scenario(name)
    cases = []
    for case in scenario["cases"]:
        state, questions = mod.state(case), mod.questions(case)
        t0 = time.perf_counter()
        response = client.system_one(state, questions)
        latency_ms = (time.perf_counter() - t0) * 1000
        body = response.raw_http_response.json()
        cases.append({
            "patient": case["patient"],
            "state": state,
            "questions": questions,
            "answers": body["answers"],
            "model": body["model"],
            "usage": body["usage"],
            "latency_ms": round(latency_ms, 1),
            "request_id": response.request_id,
        })
        print(f"{name} {case['patient']} {len(questions):>2}q {latency_ms:7.0f} ms {body['usage']}", flush=True)
    return {"scenario": name, "run_at": datetime.now(UTC).isoformat(timespec="seconds"), "cases": cases}


def main(names: list[str]) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    with TypeSafeClient(model=MODEL) as client:
        for name in names or SCENARIOS:
            result = run(name, client)
            (RESULTS_DIR / f"{name}.json").write_text(json.dumps(result, indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
