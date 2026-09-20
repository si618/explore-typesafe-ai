"""Worked API examples for the report: one real request and response per scenario.

Every example is rendered from a stored case in results/, so the payload shown is
what the runner actually sent and the answers are what Jev actually returned. Long
free text and fanned-out questions are abridged for the page; each block says what
was cut and links to the untrimmed JSON.
"""

from __future__ import annotations

import json
import pprint

from .common import RESULTS_DIR

REPO = "https://github.com/si618/explore-typesafe-ai/blob/main"
SDK_CALL = """async with AsyncTypeSafeClient(model="{model}") as client:
    response = await client.system_one(state, questions)

body = response.raw_http_response.json()"""


def _literal(obj) -> str:
    """Render a payload as a Python literal.

    A JSON dump is already valid Python for these payloads (strings and numbers), and
    reads better than pprint; fall back only if a bool or None ever appears.
    """
    def plain(o) -> bool:
        if isinstance(o, dict):
            return all(plain(v) for v in o.values())
        if isinstance(o, list):
            return all(plain(v) for v in o)
        return isinstance(o, (str, int, float)) and not isinstance(o, bool)

    if plain(obj):
        return json.dumps(obj, indent=2, ensure_ascii=False)
    return pprint.pformat(obj, width=100, sort_dicts=False)


def _abridge(obj, path: str, cuts: list[str], text_chars: int, max_items: int):
    """Shorten long strings and long lists, recording what was cut."""
    if isinstance(obj, str):
        if len(obj) > text_chars:
            cuts.append(f"`{path}` truncated from {len(obj):,} characters")
            return obj[:text_chars].rstrip() + " …"
        return obj
    if isinstance(obj, dict):
        return {k: _abridge(v, f"{path}.{k}" if path else k, cuts, text_chars, max_items) for k, v in obj.items()}
    if isinstance(obj, list):
        kept = obj[:max_items]
        if len(obj) > max_items:
            cuts.append(f"`{path}` shows {max_items} of {len(obj)} entries")
        return [_abridge(v, f"{path}[{i}]", cuts, text_chars, max_items) for i, v in enumerate(kept)]
    return obj


def _pick(d: dict, keep: list[str] | None, label: str, cuts: list[str]) -> dict:
    if not keep:
        return d
    shown = {k: d[k] for k in keep if k in d}
    if len(shown) < len(d):
        cuts.append(f"{len(shown)} of {len(d)} {label} shown")
    return shown


def api_example(run: str, patient: str | None = None, *, module: str, intro: str,
                keep: list[str] | None = None, text_chars: int = 400, max_items: int = 3,
                heading: str = "## Example request and response") -> str:
    """Render one recorded case from results/{run}.json as an SDK call plus response body."""
    result = json.loads((RESULTS_DIR / f"{run}.json").read_text())
    case = next(c for c in result["cases"] if patient is None or c["patient"] == patient)
    cuts: list[str] = []
    state = _abridge(case["state"], "", cuts, text_chars, max_items)
    questions = _pick(case["questions"], keep, "questions and their answers", cuts)
    answers = _pick(case["answers"], keep, "answers", [])
    request = f'state = {_literal(state)}\n\nquestions = {_literal(questions)}\n\n' + SDK_CALL.format(model=case["model"])
    response = _literal({"answers": answers, "model": case["model"], "usage": case["usage"]})
    trimmed = (" Abridged for this page: " + "; ".join(cuts) + ".") if cuts else ""
    return f"""{heading}

{intro} `state` and `questions` are built by [`{module}.py`]({REPO}/src/explore_typesafe/{module}.py);
`system_one` answers every question in one request.

```python
from typesafe_sdk import AsyncTypeSafeClient

{request}
```

The response body, exactly as recorded:

```json
{response}
```

Request `{case['request_id']}` took **{case['latency_ms']:.0f} ms** for {len(case['questions'])} questions
({case['usage']['input_tokens']:,} input / {case['usage']['output_tokens']:,} output tokens).{trimmed}
Every case of this run, untrimmed, is in [`results/{run}.json`]({REPO}/results/{run}.json).
"""
