# Models, timing & tokens

## Models

| Role | Model | Tokens | Notes |
| --- | --- | --- | --- |
| System One judgments (all 60 scenario requests) | `jev-1.13.0` (pinned; `jev-latest` resolved to the same build on the run date) | 90,167 in / 15,677 out | TypeSafe API, Python SDK `typesafe-sdk` 0.7.0 |
| Orchestration: read docs, generate & map FHIR, author scenarios and reference labels, write pipeline and report | `claude-opus-5` | ≈260k (session context counter; approximate) | Claude Code main session |
| System Two: blinded review of 65 escalated judgments | `claude-sonnet-5` | 139,819 | Claude Code subagent; 10 tool calls, 8.2 min wall-clock across two batches (58 + 7 items) |

## Jev timing and usage

Latency is client-side wall-clock time for one `POST /v1/systemone`, measured with `time.perf_counter()` around the SDK call. Requests were sent sequentially from a single client over the public internet, so the figures include network round-trip. Cost uses the published price of $0.042 per million **input** tokens; output tokens are free.

| Scenario | Model | Requests | Questions | Q/request | mean ms | p50 ms | p95 ms | max ms | Input tok | Output tok | Cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| s1 ward | jev-1.13.0 | 20 | 80 | 4 | 372 | 334 | 588 | 797 | 21,924 | 3,113 | $0.0009 |
| s2 discharge | jev-1.13.0 | 20 | 223 | 8–15 | 330 | 324 | 388 | 427 | 51,446 | 9,808 | $0.0022 |
| s3 inbox | jev-1.13.0 | 20 | 100 | 5 | 340 | 333 | 402 | 563 | 16,797 | 2,756 | $0.0007 |
| **all** |  | 60 | 403 |  | 347 | 330 | 467 | 797 | 90,167 | 15,677 | $0.0038 |

Latency is flat in the number of questions: questions over one state are evaluated in parallel.

| Questions in request | Requests | Median latency (ms) |
| --- | --- | --- |
| 4 | 20 | 334 |
| 5 | 20 | 333 |
| 8 | 2 | 383 |
| 9 | 2 | 362 |
| 10 | 4 | 314 |
| 11 | 5 | 307 |
| 12 | 1 | 299 |
| 13 | 3 | 325 |
| 14 | 2 | 364 |
| 15 | 1 | 300 |

For scale, the whole evaluation of 403 typed judgments cost **$0.0038** in Jev tokens.
