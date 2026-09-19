# Independent reference labels

Issue #1 identified a circularity risk: Claude authored the hand cases and
labels, and a Claude reviewer judged Jev's uncertain answers. This page adds a
blind sample of **15 cases per scenario** (302 typed judgments).
The packet contains only the state and typed question; the labeler did not see
Jev answers or the original reference labels.

| Question type | Judgments | Reference vs independent κ | Jev vs independent κ |
| --- | --- | --- | --- |
| Noul | 120 | 1.00 | 0.61 |
| Choice | 137 | 1.00 | 0.86 |
| Score | 45 | 1.00 | 0.80 |

κ is unweighted for Nouls and Choices, and quadratic weighted κ for Scores.
The independent source was **Codex (GPT-5)** (2026-09-19),
a different model family from Claude. It was not a clinician or pharmacist
review. Disagreements are retained in the source files rather than silently
replacing the pre-registered labels.

The packet, labels, provenance and reproducible scorer live in
`data/independent_labels/`. This is an additional model-family check, not
clinical validation.
