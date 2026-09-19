"""Run scenario cases against Jev and store the raw results.

One request per case: all of a case's questions share one state and are answered
in parallel by the model. Latency is client-side wall-clock per request; the
`concurrency` used is recorded with the results because in-flight requests share
the client's network link.

Usage: python -m explore_typesafe.run [RUN ...]   (default: every run in RUNS)
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from importlib import import_module

from typesafe_sdk import AsyncTypeSafeClient

from .common import RESULTS_DIR, load_scenario

MODEL = "jev-1.13.0"  # pinned rather than jev-latest so results are reproducible
# run name -> (scenario file, module, variant, concurrency)
RUNS = {
    "s1_ward": ("s1_ward", "s1_ward", "", 1),
    "s2_discharge": ("s2_discharge", "s2_discharge", "", 1),
    "s3_inbox": ("s3_inbox", "s3_inbox", "", 1),
    "s1_ward_gen": ("s1_ward_gen", "s1_ward", "", 1),
    "s2_discharge_gen": ("s2_discharge_gen", "s2_discharge", "", 1),
    "s3_inbox_gen": ("s3_inbox_gen", "s3_inbox", "", 1),
    "s2_discharge_v2": ("s2_discharge", "s2_discharge", "_v2", 1),
    "s2_discharge_gen_v2": ("s2_discharge_gen", "s2_discharge", "_v2", 1),
    "s2_discharge_v21": ("s2_discharge", "s2_discharge", "_v21", 1),
    "s2_discharge_gen_v21": ("s2_discharge_gen", "s2_discharge", "_v21", 1),
    "s4_search": ("s4_search", "s4_search", "", 8),
    "s4_search_notes": ("s4_search_notes", "s4_search", "_note", 8),
    "s5_features": ("s5_features", "s5_features", "", 8),
}
SCENARIOS = ["s1_ward", "s2_discharge", "s3_inbox"]  # the original hand-authored runs


async def _one(client, mod, variant, case, sem) -> dict:
    state = getattr(mod, f"state{variant}")(case)
    questions = getattr(mod, f"questions{variant}")(case)
    async with sem:
        t0 = time.perf_counter()
        response = await client.system_one(state, questions)
        latency_ms = (time.perf_counter() - t0) * 1000
    body = response.raw_http_response.json()
    return {"patient": case["patient"], "split": case.get("split"), "state": state, "questions": questions,
            "answers": body["answers"], "model": body["model"], "usage": body["usage"],
            "latency_ms": round(latency_ms, 1), "request_id": response.request_id}


async def run(name: str, client: AsyncTypeSafeClient) -> dict:
    scenario_file, module, variant, concurrency = RUNS[name]
    mod = import_module(f"explore_typesafe.{module}")
    cases = load_scenario(scenario_file)["cases"]
    sem = asyncio.Semaphore(concurrency)
    t0 = time.perf_counter()
    results = await asyncio.gather(*(_one(client, mod, variant, c, sem) for c in cases))
    wall = time.perf_counter() - t0
    print(f"{name}: {len(results)} requests, {sum(len(r['questions']) for r in results)} questions, "
          f"{wall:.1f} s wall, concurrency {concurrency}", flush=True)
    return {"scenario": name, "scenario_file": scenario_file, "variant": variant, "concurrency": concurrency,
            "wall_seconds": round(wall, 1), "run_at": datetime.now(UTC).isoformat(timespec="seconds"), "cases": results}


async def main(names: list[str]) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    async with AsyncTypeSafeClient(model=MODEL) as client:
        for name in names or list(RUNS):
            result = await run(name, client)
            (RESULTS_DIR / f"{name}.json").write_text(json.dumps(result, indent=1) + "\n")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
