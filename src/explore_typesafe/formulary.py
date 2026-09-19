"""Drug classes, allergy classes and interactions used to build (and, in s2 v2, look up) regimens.

These tables are exact lookups, so they live in code. They are deliberately small:
they cover the Synthea cohort's medications plus the drugs the generator adds.
"""

from __future__ import annotations

import re

CLASSES = {
    "statin": r"simvastatin|atorvastatin|rosuvastatin|pravastatin|lovastatin",
    "beta_blocker": r"metoprolol|propranolol|carvedilol|bisoprolol|atenolol|labetalol|nebivolol",
    "ace_inhibitor": r"lisinopril|enalapril|ramipril|benazepril|perindopril",
    "arb": r"losartan|valsartan|irbesartan|candesartan",
    "thiazide": r"hydrochlorothiazide|indapamide|chlorthalidone",
    "p2y12": r"clopidogrel|prasugrel|ticagrelor",
    "aspirin": r"aspirin|vazalore",
    "nsaid": r"ibuprofen|naproxen|diclofenac|celecoxib",
    "paracetamol": r"acetaminophen|paracetamol|tylenol|percocet|norco",
    "opioid": r"hydrocodone|oxycodone|tramadol|fentanyl|codeine|morphine|meperidine|buprenorphine|percocet|norco|oxycontin",
    "anticoagulant": r"warfarin|apixaban|rivaroxaban",
    "ppi": r"omeprazole|pantoprazole|esomeprazole",
    "h1_antihistamine": r"diphenhydramine|chlorpheniramine|chlorphenamine|loratadine|fexofenadine|cetirizine|terfenadine|astemizole|doxylamine",
    "benzodiazepine": r"clonazepam|diazepam|lorazepam",
    "ssri": r"sertraline|fluoxetine|citalopram",
    "cholinesterase_inhibitor": r"donepezil|galantamine|rivastigmine",
    "penicillin": r"penicillin|amoxicillin|augmentin|co-amoxiclav|flucloxacillin|tazocin|piperacillin",
    "cephalosporin": r"cefalexin|cefdinir|ceftriaxone|cefuroxime",
    "sulfonamide_antibiotic": r"sulfamethoxazole|co-trimoxazole|bactrim",
    "macrolide": r"clarithromycin|erythromycin|azithromycin",
    "ccb_dhp": r"amlodipine",
    "ccb_non_dhp": r"verapamil|diltiazem",
    "loop_diuretic": r"furosemide|bumetanide",
    "bisphosphonate": r"alendron",
}
# Allergy (FHIR display, lower-case) -> classes that conflict with it.
ALLERGY_CLASSES = {"penicillin v": {"penicillin"}, "aspirin": {"aspirin"}, "lisinopril": {"ace_inhibitor"},
                   "sulfamethoxazole / trimethoprim": {"sulfonamide_antibiotic"}, "cefdinir": {"cephalosporin"}}
# (new drug pattern, other drug pattern): well-known interactions to avoid or actively manage.
INTERACTIONS = [
    (r"clarithromycin|erythromycin", r"simvastatin|lovastatin|terfenadine|astemizole|warfarin"),
    (r"fluconazole", r"simvastatin|warfarin"),
    (r"omeprazole|esomeprazole", r"clopidogrel"),
    (r"ibuprofen|naproxen|diclofenac", r"warfarin|clopidogrel|prasugrel"),
    (r"sildenafil", r"nitroglycerin"),
    (r"spironolactone", r"lisinopril|enalapril|ramipril|losartan|valsartan|irbesartan"),
    (r"tramadol", r"sertraline|fluoxetine|citalopram"),
    (r"co-trimoxazole", r"warfarin|lisinopril|enalapril|ramipril"),
    (r"amiodarone", r"digoxin|warfarin|simvastatin"),
    (r"metronidazole", r"warfarin"),
]

EXTRA_DRUGS = (r"levetiracetam|prednisolone|melatonin|senna|lactulose|nitrofurantoin|doxycycline|levothyroxine|fluconazole|"
               r"sildenafil|spironolactone|amiodarone|metronidazole|ecotrin|insulin|humulin|metformin|digoxin|tacrolimus|"
               r"cefalexin|ceftriaxone|ondansetron|galantamine|donepezil")
FORMULARY = re.compile(r"\b(" + "|".join([*CLASSES.values(), EXTRA_DRUGS]) + r")\b", re.I)


def classes_of(text: str) -> set[str]:
    t = text.lower()
    return {c for c, pat in CLASSES.items() if re.search(pat, t)}


def drug_allergies(allergies: list[str]) -> list[str]:
    """FHIR allergy displays that are drugs (Synthea marks non-drug allergens as substance/organism/finding)."""
    return [a for a in allergies if not re.search(r"\((substance|organism|finding)\)", a)]
