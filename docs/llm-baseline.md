# Jev vs an LLM baseline

To put Jev's accuracy in context, the same states and questions were answered by **Claude Haiku 4.5**, which you might otherwise use for a classification step. Each request was a headless Claude Code call with no tools, a minimal system prompt and extended thinking disabled. Haiku returned the same typed answer space as JSON (a probability for Nouls, an option and confidence for Choices, a level and confidence for Scores).

## Accuracy

Hand cases, and the **test** split of the generated cases:

| Scenario | Question | Primitive | Jev | Haiku 4.5 |
| --- | --- | --- | --- | --- |
| 1. Ward (hand) | `new_confusion` | Noul | 100% | 100% |
| 1. Ward (hand) | `infection` | Noul | 90% | 85% |
| 1. Ward (hand) | `concern` | Score | 85% · MAE 0.18 | 95% · MAE 0.05 |
| 1. Ward (hand) | `pattern` | Choice | 95% | 100% |
| 2. Discharge (hand) | `med_status` | Choice | 98% | 99% |
| 2. Discharge (hand) | `allergy_conflict` | Noul | 100% | 90% |
| 2. Discharge (hand) | `duplicate_therapy` | Noul | 70% | 85% |
| 2. Discharge (hand) | `interaction` | Noul | 75% | 90% |
| 2. Discharge (hand) | `justification` | Score | 55% · MAE 0.46 | 55% · MAE 0.45 |
| 3. Inbox (hand) | `route` | Choice | 70% | 85% |
| 3. Inbox (hand) | `urgency` | Score | 70% · MAE 0.32 | 75% · MAE 0.25 |
| 3. Inbox (hand) | `red_flag` | Noul | 85% | 90% |
| 3. Inbox (hand) | `medication_issue` | Noul | 95% | 90% |
| 3. Inbox (hand) | `safeguarding` | Noul | 80% | 95% |
| 1. Ward (test) | `new_confusion` | Noul | 95% | 95% |
| 1. Ward (test) | `infection` | Noul | 100% | 85% |
| 1. Ward (test) | `concern` | Score | 78% · MAE 0.25 | 80% · MAE 0.20 |
| 1. Ward (test) | `pattern` | Choice | 92% | 85% |
| 2. Discharge (test) | `med_status` | Choice | 98% | 92% |
| 2. Discharge (test) | `allergy_conflict` | Noul | 100% | 98% |
| 2. Discharge (test) | `duplicate_therapy` | Noul | 85% | 80% |
| 2. Discharge (test) | `interaction` | Noul | 68% | 75% |
| 2. Discharge (test) | `justification` | Score | 60% · MAE 0.47 | 42% · MAE 0.65 |
| 3. Inbox (test) | `route` | Choice | 85% | 92% |
| 3. Inbox (test) | `urgency` | Score | 80% · MAE 0.22 | 82% · MAE 0.17 |
| 3. Inbox (test) | `red_flag` | Noul | 82% | 85% |
| 3. Inbox (test) | `medication_issue` | Noul | 95% | 90% |
| 3. Inbox (test) | `safeguarding` | Noul | 72% | 100% |

Note search (note-level F1): Jev 0.86, Haiku 0.83.

The two models are **close on most questions**, and neither dominates:

- **Haiku is stronger** on routing and on the questions where Jev over-calls (inbox route, safeguarding, discharge interactions).
- **Jev is stronger** on high-volume extraction over the generated plans (per-medication status 98% vs 92%), on the infection and allergy checks, on grading justifications, and on note search.

## Latency and cost

| Run | Requests | p50 ms (Jev / Haiku) | p95 ms (Jev / Haiku) | Cost (Jev / Haiku) | Haiku cost multiple |
| --- | --- | --- | --- | --- | --- |
| s1 ward | 20 | 334 / 1587 | 588 / 1952 | $0.0009 / $0.0399 | 43× |
| s2 discharge | 20 | 324 / 2692 | 388 / 3512 | $0.0022 / $0.0875 | 41× |
| s3 inbox | 20 | 333 / 1798 | 402 / 2792 | $0.0007 / $0.0398 | 56× |
| s1 ward gen | 80 | 321 / 1560 | 405 / 1732 | $0.0034 / $0.1538 | 45× |
| s2 discharge gen | 80 | 320 / 2512 | 367 / 3690 | $0.0083 / $0.3361 | 41× |
| s3 inbox gen | 80 | 318 / 1744 | 365 / 1922 | $0.0029 / $0.1565 | 53× |
| s4 search | 300 | 324 / 2216 | 436 / 2635 | $0.0560 / $3.2938 | 59× |

Haiku latency is the API time reported by the CLI (`duration_api_ms`), which excludes CLI start-up. Its cost is the CLI's list-price estimate, including prompt-cache writes. Haiku token counts aren't compared: the runner recorded only uncached input tokens (as few as 3 for a request carrying ten notes), so they understate Haiku's real input.

**The trade-off:** Jev answers in a fifth to an eighth of the time, at 1/40th to 1/60th of the cost, with lower accuracy on some judgments and higher on others. That suits the architecture used throughout this report: Jev for every judgment, and a reasoning model only for the uncertain slice.
