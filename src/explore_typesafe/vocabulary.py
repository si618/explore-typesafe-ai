"""Link the first mention of each glossary term on a page to vocabulary.md.

Every rendered page gets at most one link per term, on the term's first
occurrence in prose. Code, fenced blocks, existing links, headings, admonition
titles and quoted source text are left alone, so `noul` in a request payload
and NEWS2 in the quoted prompt both stay plain text.
"""

from __future__ import annotations

import re

VOCAB = "vocabulary.md"

# (anchor, pattern), matched in this order so a longer phrase claims its text
# before a term nested in it: "confidence gate" before "confidence", "reference
# label" before "score", NSTEMI before STEMI. An anchor listed twice is a
# fallback: the second pattern is only tried if the first found nothing.
TERMS: list[tuple[str, str]] = [
    ("system-one", r"System One"),
    ("system-two", r"System Two"),
    ("confidence-gate", r"(?i:confidence gates?)"),
    ("escalation-band", r"(?i:escalation bands?)"),
    ("reference-label", r"(?i:reference labels?)"),
    ("brier-score", r"Brier(?: scores?)?"),
    ("under-triage", r"(?i:under-triag\w+)"),
    ("over-triage", r"(?i:over-triag\w+)"),
    ("medication-reconciliation", r"(?i:(?:medication|med) reconciliation)"),
    ("duplicate-therapy", r"(?i:duplicate therapy)"),
    ("sepsis-screen", r"(?i:sepsis screens?)"),
    ("task-categories", r"(?i:task categor(?:y|ies))"),
    ("fan-out", r"(?i:fan-outs?)"),
    ("jaggedness", r"(?i:jagged(?:ness)?)"),
    ("jev", r"Jev"),
    ("noul", r"Nouls?"),
    ("choice", r"Choice"),
    ("score", r"Score"),
    ("primitive", r"(?i:primitives?)"),
    ("confidence", r"(?i:confidence)"),
    ("ambiguous", r"(?i:ambiguous)"),
    ("mae", r"MAE"),
    ("p50", r"p50"),
    ("p95", r"p95"),
    ("news2", r"NEWS2"),
    ("acvpu", r"ACVPU"),
    ("delirium", r"(?i:delirium)"),
    ("medication-reconciliation", r"(?i:reconciliation)"),  # fallback for the bare word
    ("interaction", r"(?i:interactions?)"),
    ("safeguarding", r"(?i:safeguarding)"),
    ("melaena", r"(?i:melaena)"),
    ("nstemi", r"NSTEMI"),
    ("stemi", r"STEMI"),
    ("pci", r"PCI"),
    ("gtn", r"GTN"),
    ("fhir", r"FHIR"),
    ("us-core", r"US Core"),
    ("synthea", r"Synthea"),
]

# Spans a link must not land in or straddle.
SKIP = re.compile(
    r"^[ \t]*(```|~~~).*?^[ \t]*\1[ \t]*$"   # fenced blocks, mermaid included
    r"|(`+)[^`]*?\2"                           # inline code
    r"|\[[^\]]*\]\([^)]*\)"                    # existing links
    r"|https?://\S+"                           # bare URLs
    r"|^#{1,6} [^\n]*"                         # headings
    r"|^[ \t]*(?:!!!|\?\?\?\+?) [^\n]*"        # admonition titles
    r"|^[ \t]*>[^\n]*"                         # block-quoted source text, e.g. the prompt
    r'|"[^"\n]*"',                             # anything quoted verbatim
    re.MULTILINE | re.DOTALL,
)


def _term_re(pattern: str) -> re.Pattern[str]:
    # A slash or backslash either side means the term is part of an identifier
    # (s2\_discharge/.../interaction) or a run of alternatives (Score/Noul/Choice).
    core = rf"(?<![\w\-/\\])(?:{pattern})(?![\w\-/\\])"
    return re.compile(rf"\*\*{core}\*\*|{core}")


TERM_RES = [(anchor, _term_re(pattern)) for anchor, pattern in TERMS]


def link_vocabulary(text: str) -> str:
    """Link each term's first free occurrence in `text` to its glossary entry."""
    taken = [m.span() for m in SKIP.finditer(text)]
    links: list[tuple[int, int, str]] = []
    linked = set(re.findall(rf"{VOCAB}#([\w-]+)", text))  # already linked by hand
    for anchor, term in TERM_RES:
        if anchor in linked:
            continue
        for m in term.finditer(text):
            start, end = m.span()
            if any(start < b and a < end for a, b in taken):
                continue
            links.append((start, end, anchor))
            taken.append((start, end))
            linked.add(anchor)
            break
    for start, end, anchor in sorted(links, reverse=True):
        text = f"{text[:start]}[{text[start:end]}]({VOCAB}#{anchor}){text[end:]}"
    return text
