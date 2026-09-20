# Models, timing & tokens

## Models

| Role | Model | Tokens | Notes |
| --- | --- | --- | --- |
| [System One](vocabulary.md#system-one) judgments (every [Jev](vocabulary.md#jev) run in this report) | `jev-1.13.0` (pinned; `jev-latest` resolved to the same build on the run date) | 6,206,761 in / 1,044,126 out | TypeSafe API, Python SDK `typesafe-sdk` 0.7.0 |
| LLM baseline: the same states and questions ([comparison](llm-baseline.md)) | `claude-haiku-4-5` | not comparable (see note) | 600 headless Claude Code calls, $4.11 list-price estimate |
| Orchestration: read docs, generate & map [FHIR](vocabulary.md#fhir), author scenarios, [reference labels](vocabulary.md#reference-label) and case generators, write pipeline and report | `claude-opus-5` | not measured (the session context was compacted, so no reliable total exists) | Claude Code main session |
| [System Two](vocabulary.md#system-two): blinded review of 65 escalated judgments | `claude-sonnet-5` | 139,819 | Claude Code subagent; 10 tool calls, 8.2 min wall-clock across two batches (58 + 7 items) |

## Jev timing and usage

Latency is client-side wall-clock time for one `POST /v1/systemone`, measured with `time.perf_counter()` around the SDK call over the public internet, so it includes network round-trip. The hand-case runs were sequential; the larger runs used up to 8 concurrent requests, and *wall s* is the elapsed time for the whole run. Cost uses the published price of $0.042 per million **input** tokens; output tokens are free.

| Run | Requests | Questions | Concurrency | [p50](vocabulary.md#p50) ms | [p95](vocabulary.md#p95) ms | Wall s | Input tok | Output tok | Cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Ward, hand | 20 | 80 | 1 | 334 | 588 | – | 21,924 | 3,113 | $0.0009 |
| 2. Discharge, hand | 20 | 223 | 1 | 324 | 388 | – | 51,446 | 9,808 | $0.0022 |
| 3. Inbox, hand | 20 | 100 | 1 | 333 | 402 | – | 16,797 | 2,756 | $0.0007 |
| 1. Ward, generated | 80 | 320 | 1 | 321 | 405 | 26.7 | 81,661 | 12,442 | $0.0034 |
| 2. Discharge, generated | 80 | 846 | 1 | 320 | 367 | 25.8 | 197,088 | 36,637 | $0.0083 |
| 3. Inbox, generated | 80 | 400 | 1 | 318 | 365 | 25.7 | 69,731 | 10,995 | $0.0029 |
| 2. Discharge v2, hand | 20 | 615 | 1 | 336 | 382 | 6.8 | 139,426 | 58,063 | $0.0059 |
| 2. Discharge v2, generated | 80 | 2,457 | 1 | 337 | 420 | 27.8 | 535,103 | 221,142 | $0.0225 |
| 2. Discharge v2.1, hand | 20 | 615 | 1 | 342 | 437 | 7.6 | 140,386 | 58,063 | $0.0059 |
| 2. Discharge v2.1, generated | 80 | 2,457 | 1 | 334 | 389 | 27.0 | 539,104 | 221,142 | $0.0226 |
| 4. Search, 10 notes/request | 300 | 3,522 | 8 | 324 | 436 | 13.5 | 1,332,484 | 91,428 | $0.0560 |
| 4. Search, 1 note/request | 2,922 | 2,922 | 8 | 315 | 387 | 118.6 | 1,943,406 | 64,284 | $0.0816 |
| 5. Features | 1,000 | 10,000 | 8 | 316 | 425 | 41.1 | 1,138,205 | 254,253 | $0.0478 |
| **all Jev runs** | 4,722 | 24,557 |  | 317 | 400 |  | 6,206,761 | 1,044,126 | **$0.26** |

**Latency is flat in the number of questions**, because questions over one state are evaluated in parallel:

| Questions in request | Requests | Median ms | p95 ms |
| --- | --- | --- | --- |
| 1 | 2,922 | 315 | 387 |
| 2–5 | 200 | 321 | 393 |
| 6–10 | 1,078 | 316 | 424 |
| 11–20 | 364 | 324 | 431 |
| 21–40 | 128 | 336 | 391 |
| 41+ | 30 | 359 | 447 |

Every Jev judgment in this report (24,557 of them, in 4,722 requests) cost **$0.26** in total.

!!! note "Haiku token counts"
    The Haiku runner recorded only the uncached input tokens the CLI reports (as few as 3 for a request carrying ten notes). The prompt itself went through the prompt cache, so those counts understate Haiku's real input, and the [comparison](llm-baseline.md) uses cost and latency instead.
