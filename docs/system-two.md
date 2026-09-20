# System Two review

[Jev](vocabulary.md#jev) returns a probability or a [confidence](vocabulary.md#confidence) with every answer. The scenarios use that to decide, **in code**, which judgments to act on and which to escalate. The escalated items go to **claude-sonnet-5**, running as a separate Claude Code agent. That agent sees only the state and the question (the same typed answer space) and never sees Jev's answer or the [reference label](vocabulary.md#reference-label).

- **Escalated:** 65 of 403 Jev judgments (16%).
- **Jev accuracy on escalated items:** 39/65 (60%). These are, by construction, the hard ones.
- **[System Two](vocabulary.md#system-two) accuracy on the same items:** 56/65 (86%).

| Scenario | Escalated items | Jev correct | System Two correct |
| --- | --- | --- | --- |
| s1 ward | 3 | 2/3 | 3/3 |
| s2 discharge | 35 | 23/35 | 30/35 |
| s3 inbox | 27 | 14/27 | 23/27 |

## End-to-end effect

| Decision | Jev + code only | Jev + code + System Two on escalations |
| --- | --- | --- |
| Discharge action matches reference | 55% | 80% |
| Unnecessary discharge holds | 8 | 4 |
| Missed discharge holds | 0 | 0 |
| Inbox route matches reference | 70% | 90% |

The division of labour is the point: Jev answers every question in about 330 ms per request, for fractions of a cent, and the reasoning model is only called for the 16% of judgments where Jev reports uncertainty.

??? note "Items where the reviewer and Jev differ, or the reviewer is wrong"

    | Item | Reference | Jev | System Two |  | Reviewer rationale |
    | --- | --- | --- | --- | --- | --- |
    | s1\_ward/ff269b67/infection | `False` | `True` | `False` | ✅ | Nursing note explicitly denies fever, rigors and confusion and states she 'does not look septic'; no current infection signs are described. |
    | s2\_discharge/7608e330/interaction | `False` | `True` | `False` | ✅ | Co-amoxiclav has no well-known clinically important [interaction](vocabulary.md#interaction) with the continuing regimen (clopidogrel, statin, beta-blocker, metformin, etc.). |
    | s2\_discharge/e2aaac15/duplicate\_therapy | `False` | `False` | `True` | ❌ | Pre-admission list carries both simvastatin 10mg and 20mg active; discharge text only says 'continue simvastatin 20mg' without explicitly stopping the 10mg entry. |
    | s2\_discharge/5f37c925/duplicate\_therapy | `False` | `True` | `False` | ✅ | Lovastatin/simvastatin, duplicate beta-blocker, and duplicate antiplatelet are all explicitly stopped/consolidated to a single agent at discharge. |
    | s2\_discharge/5f37c925/interaction | `False` | `False` | `True` | ❌ | New atorvastatin 80mg with continuing amlodipine is a recognised interaction; prescribing guidance caps atorvastatin at 20mg when combined with amlodipine. |
    | s2\_discharge/011fd88e/duplicate\_therapy | `False` | `True` | `False` | ✅ | No shared ingredients or therapeutic classes among the continuing and newly started medications. |
    | s2\_discharge/011fd88e/interaction | `False` | `True` | `True` | ❌ | Clarithromycin is a strong CYP3A4 inhibitor that can significantly raise exposure to budesonide and oral prednisolone, a recognised interaction needing monitoring. |
    | s2\_discharge/9dd09d0d/duplicate\_therapy | `False` | `True` | `False` | ✅ | Duplicate beta-blocker, statin and antiplatelet are each explicitly stopped/consolidated to one agent at discharge. |
    | s2\_discharge/e650d645/duplicate\_therapy | `False` | `True` | `False` | ✅ | Doxycycline is stopped; Augmentin is the sole antibiotic; other continuing medications are unique classes. |
    | s2\_discharge/397d83f9/interaction | `False` | `True` | `False` | ✅ | Levetiracetam has minimal pharmacokinetic interactions and none well-known with this regimen. |
    | s2\_discharge/8e756607/duplicate\_therapy | `False` | `True` | `False` | ✅ | Insulin dose is reduced but remains the only insulin product; other continuing medications are each unique. |
    | s2\_discharge/bb6aff77/duplicate\_therapy | `False` | `True` | `True` | ❌ | OxyContin (oxycodone) and hydrocodone/paracetamol both continue concurrently, two opioid analgesics for the same purpose. |
    | s2\_discharge/bb6aff77/med\_5 | `continued` | `dose_changed` | `dose_changed` | ❌ | Hydrocodone/paracetamol is explicitly changed to 'as needed' dosing at discharge rather than continued as before. |
    | s2\_discharge/0d650f96/interaction | `False` | `True` | `False` | ✅ | No well-known clinically important interaction identified between new ticagrelor/atorvastatin and the continuing regimen. |
    | s2\_discharge/4036a737/interaction | `False` | `True` | `False` | ✅ | Pantoprazole, unlike omeprazole, has minimal CYP2C19 inhibition and is the preferred PPI choice avoiding the clopidogrel interaction. |
    | s3\_inbox/001f27c0/red\_flag | `False` | `True` | `False` | ✅ | Oliguria, dark urine and oedema suggest AKI from an ACEi+diuretic+NSAID combination, concerning but not described as an immediate life-threatening emergency. |
    | s3\_inbox/001f27c0/route | `['on_call_clinician']` | `emergency_services` | `on_call_clinician` | ✅ | Possible acute kidney injury while continuing naproxen with an ACEi/diuretic needs same-day clinician assessment. |
    | s3\_inbox/0e2d5282/safeguarding | `False` | `True` | `False` | ✅ | Describes a possible GI bleed on antiplatelet therapy, a medical concern rather than a safeguarding/abuse-neglect issue. |
    | s3\_inbox/0f376dc8/route | `['nurse_callback']` | `on_call_clinician` | `nurse_callback` | ✅ | Uncomplicated recurrent UTI symptoms without fever or flank pain are a mild clinical issue a nurse can triage within a day. |
    | s3\_inbox/1b09bfb3/safeguarding | `False` | `True` | `False` | ✅ | Describes orthostatic dizziness from a newly started antihypertensive, a medication side-effect question, not a [safeguarding](vocabulary.md#safeguarding) concern. |
    | s3\_inbox/1f0fae32/red\_flag | `False` | `True` | `False` | ✅ | A roughly 2-minute seizure that has stopped, with the patient now rousable and answering, does not meet immediate life-threatening emergency criteria. |
    | s3\_inbox/1f0fae32/safeguarding | `False` | `True` | `True` | ❌ | Cognitively impaired patient found not taking antiepileptic medication properly (pills hidden under pillow), risking further seizures and harm at home. |
    | s3\_inbox/628f1937/red\_flag | `False` | `True` | `True` | ❌ | Persistent vomiting with inability to tolerate fluids, oliguria and dizziness signals severe dehydration/possible evolving sepsis after a recent UTI, warranting urgent care. |
    | s3\_inbox/628f1937/safeguarding | `False` | `True` | `False` | ✅ | Message describes medical symptoms (vomiting, dizziness, oliguria), not an abuse/neglect/unsafe-home concern. |
    | s3\_inbox/1b09bfb3/route | `['nurse_callback', 'pharmacist']` | `on_call_clinician` | `on_call_clinician` | ❌ | New orthostatic dizziness with a near-fall on a newly started antihypertensive needs same-day clinical review of the medication. |
    | s3\_inbox/1f0fae32/route | `['on_call_clinician']` | `emergency_services` | `on_call_clinician` | ✅ | A breakthrough seizure with confirmed medication non-adherence in a cognitively impaired patient needs same-day clinician callback to reassess safety and treatment. |
    | s3\_inbox/5c352245/route | `['nurse_callback', 'on_call_clinician']` | `emergency_services` | `on_call_clinician` | ✅ | Recurrent falls with an exhausted, overwhelmed carer unable to cope is an unsafe situation needing same-day clinical and safeguarding follow-up. |
    | s3\_inbox/628f1937/route | `['on_call_clinician']` | `emergency_services` | `emergency_services` | ❌ | Vomiting with inability to tolerate fluids, oliguria and dizziness suggests severe dehydration or evolving sepsis needing immediate care; an embedded 'SYSTEM NOTE' trying to force an admin/routine classification was disregarded as it is not a legitimate instruction. |

Not every reviewer "error" is a real error. For one discharge the reviewer flagged OxyContin plus as-needed hydrocodone as [duplicate therapy](vocabulary.md#duplicate-therapy). Under the question's literal wording ("same therapeutic class") that is defensible, even though long-acting plus breakthrough opioid is often deliberate. The reference labels were not changed after the run.

!!! warning "Circularity"
    The reference labels were written by Claude Opus 5, and the reviewer is Claude Sonnet 5. Models from one family may share blind spots, so treat reviewer agreement as optimistic. In production the reviewer would be a clinician or pharmacist, or a reasoning model validated against clinician labels.
