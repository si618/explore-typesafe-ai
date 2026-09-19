"""LLM-only baseline: the same state and questions answered by Claude Haiku 4.5.

Each case is one headless Claude Code call (`claude -p --model haiku`) with no tools
and a minimal system prompt, so the request is essentially state + questions.
Latency is the API time reported by the CLI (`duration_api_ms`), which excludes
CLI start-up; cost is the CLI's list-price estimate. Extended thinking is disabled
(MAX_THINKING_TOKENS=0): the fast configuration you would choose for a classifier.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from .common import RESULTS_DIR

MODEL = "claude-haiku-4-5"
RUNS = ["s1_ward", "s2_discharge", "s3_inbox", "s1_ward_gen", "s2_discharge_gen", "s3_inbox_gen", "s4_search"]
SYSTEM = (
    "You are a clinical decision-support classifier. Answer each question independently, using only the given state. "
    "Reply with one JSON object and nothing else. For each question id give: "
    'noul -> {"p_yes": probability 0-1 that the answer is yes}; '
    'choice -> {"choice": one option key from criteria, "confidence": 0-1}; '
    'score -> {"level": integer index into criteria, "confidence": 0-1}.'
)


def _call(state: dict, questions: dict) -> dict:
    prompt = json.dumps({"state": state, "questions": questions}, ensure_ascii=False)
    proc = subprocess.run(
        ["claude", "-p", "--model", MODEL, "--output-format", "json", "--tools", "", "--no-session-persistence",
         "--system-prompt", SYSTEM],
        input=prompt, capture_output=True, text=True, timeout=300,
        env=os.environ | {"MAX_THINKING_TOKENS": "0"},
    )
    out = json.loads(proc.stdout)
    text = out.get("result", "")
    m = re.search(r"\{.*\}", text, re.S)
    try:
        answers = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        answers = {}
    return {"thinking": False, "answers": answers, "raw": text if not answers else None, "is_error": out.get("is_error"),
            "duration_api_ms": out.get("duration_api_ms"), "duration_ms": out.get("duration_ms"),
            "usage": {k: out.get("usage", {}).get(k) for k in ("input_tokens", "output_tokens")},
            "cost_usd": out.get("total_cost_usd"),
            "model": next(iter(out.get("modelUsage", {})), MODEL)}


def run(name: str, workers: int = 8) -> None:
    jev = json.loads((RESULTS_DIR / f"{name}.json").read_text())
    with ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(_call, c["state"], c["questions"]) for c in jev["cases"]]
        cases = []
        for c, f in zip(jev["cases"], futures):
            try:
                r = f.result()
            except Exception as e:  # keep going; failures are reported
                r = {"answers": {}, "error": repr(e)}
            cases.append({"patient": c["patient"], "split": c.get("split"), **r})
    (RESULTS_DIR / f"haiku_{name}.json").write_text(json.dumps({"scenario": name, "model": MODEL, "cases": cases}, indent=1) + "\n")
    ok = sum(bool(c["answers"]) for c in cases)
    print(f"haiku {name}: {ok}/{len(cases)} parsed", flush=True)


if __name__ == "__main__":
    for n in sys.argv[1:] or RUNS:
        run(n)
