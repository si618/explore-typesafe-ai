"""Score stored Jev results against the pre-registered reference labels."""

from __future__ import annotations

import json
import statistics
from importlib import import_module

from .common import RESULTS_DIR, YES, load_scenario

PRICE_PER_MTOK = 0.042  # jev-1.13.0, input tokens only (docs.typesafe.ai/models)


def _load(name: str):
    mod = import_module(f"explore_typesafe.{name}")
    cases = {c["patient"]: c for c in load_scenario(name)["cases"]}
    results = json.loads((RESULTS_DIR / f"{name}.json").read_text())
    return mod, cases, results


def _pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def perf(results: dict) -> dict:
    lat = [c["latency_ms"] for c in results["cases"]]
    tok_in = [c["usage"]["input_tokens"] for c in results["cases"]]
    tok_out = [c["usage"]["output_tokens"] for c in results["cases"]]
    nq = [len(c["questions"]) for c in results["cases"]]
    return {
        "model": sorted({c["model"] for c in results["cases"]}),
        "requests": len(lat),
        "questions": sum(nq),
        "questions_per_request": f"{min(nq)}–{max(nq)}" if min(nq) != max(nq) else str(nq[0]),
        "latency_mean_ms": round(statistics.mean(lat)),
        "latency_p50_ms": round(_pct(lat, 0.5)),
        "latency_p95_ms": round(_pct(lat, 0.95)),
        "latency_max_ms": round(max(lat)),
        "input_tokens": sum(tok_in),
        "output_tokens": sum(tok_out),
        "cost_usd": sum(tok_in) / 1e6 * PRICE_PER_MTOK,
    }


def _noul_row(name, pairs):
    """pairs: (probability, truth, ambiguous)"""
    clear = [(p, t) for p, t, a in pairs if not a]
    acc = lambda ps: sum((p >= YES) == t for p, t in ps) / len(ps)
    brier = statistics.mean((p - t) ** 2 for p, t in clear)
    return {"question": name, "type": "Noul", "n": len(pairs), "accuracy": acc([(p, t) for p, t, _ in pairs]),
            "accuracy_unambiguous": acc(clear), "brier_unambiguous": brier}


def eval_s1() -> dict:
    mod, cases, results = _load("s1_ward")
    rows, per_case = [], []
    for r in results["cases"]:
        case, a = cases[r["patient"]], r["answers"]
        ref, dec, refd = case["reference"], mod.decide(case, a), mod.reference(case)
        per_case.append({
            "patient": r["patient"], "admission": case["admission"],
            "new_confusion": a["new_confusion"]["noul"], "ref_new_confusion": ref["new_confusion"],
            "infection": a["infection"]["noul"], "ref_infection": ref["infection"],
            "concern": a["concern"]["score"], "concern_conf": a["concern"]["confidence"], "ref_concern": ref["concern"],
            "pattern": a["pattern"]["choice"], "pattern_conf": a["pattern"]["confidence"], "ref_pattern": ref["pattern"],
            "news2_charted": dec["news2_charted"], "news2_augmented": dec["news2_augmented"], "ref_news2": refd["news2"],
            "baseline_band": dec["baseline_band"], "band": dec["band"], "ref_band": refd["band"],
            "priority": dec["priority"], "uncertain": mod.uncertain(case, a),
            "ambiguous": ref.get("ambiguous", []),
        })
    for q in ("new_confusion", "infection"):
        rows.append(_noul_row(q, [(c[q], c[f"ref_{q}"], q in c["ambiguous"]) for c in per_case]))
    rows.append({"question": "concern", "type": "Score", "n": len(per_case),
                 "exact": sum(round(c["concern"]) == c["ref_concern"] for c in per_case) / len(per_case),
                 "mae": statistics.mean(abs(c["concern"] - c["ref_concern"]) for c in per_case)})
    rows.append({"question": "pattern", "type": "Choice", "n": len(per_case),
                 "accuracy": sum(c["pattern"] in c["ref_pattern"] for c in per_case) / len(per_case),
                 "accuracy_primary": sum(c["pattern"] == c["ref_pattern"][0] for c in per_case) / len(per_case)})
    n = len(per_case)
    policy = {
        "news2_only_exact": sum(c["baseline_band"] == c["ref_band"] for c in per_case) / n,
        "news2_only_under": sum(c["baseline_band"] < c["ref_band"] for c in per_case),
        "combined_exact": sum(c["band"] == c["ref_band"] for c in per_case) / n,
        "combined_under": sum(c["band"] < c["ref_band"] for c in per_case),
        "combined_over": sum(c["band"] > c["ref_band"] for c in per_case),
        "news2_only_over": sum(c["baseline_band"] > c["ref_band"] for c in per_case),
    }
    ranked = sorted(per_case, key=lambda c: -c["priority"])
    ref_top = {c["patient"] for c in per_case if c["ref_band"] == 3}
    policy["emergency_cases"] = len(ref_top)
    policy["emergency_in_top_k"] = len(ref_top & {c["patient"] for c in ranked[: len(ref_top)]})
    base_ranked = sorted(per_case, key=lambda c: -c["news2_charted"])
    policy["emergency_in_top_k_news2_only"] = len(ref_top & {c["patient"] for c in base_ranked[: len(ref_top)]})
    return {"perf": perf(results), "questions": rows, "policy": policy, "cases": ranked}


def eval_s2() -> dict:
    mod, cases, results = _load("s2_discharge")
    per_case, status_pairs = [], []
    for r in results["cases"]:
        case, a = cases[r["patient"]], r["answers"]
        dec, refd = mod.decide(case, a), mod.reference(case)
        meds = r["state"]["pre_admission_medications"]
        for i, (m, got, want) in enumerate(zip(meds, dec["statuses"], refd["statuses"])):
            status_pairs.append({"patient": r["patient"], "medication": m, "got": got, "want": want,
                                 "confidence": a[f"med_{i}"]["confidence"]})
        per_case.append({
            "patient": r["patient"], "admission": case["admission"],
            **{k: a[k]["noul"] for k in mod.VERIFY}, **{f"ref_{k}": v for k, v in refd["flags"].items()},
            "justification": a["justification"]["score"], "ref_justification": case["reference"]["justification"],
            "action": dec["action"], "ref_action": refd["action"],
            "uncertain": mod.uncertain(case, a), "ambiguous": case["reference"].get("ambiguous", []),
        })
    rows = [{"question": "med_status (per medication)", "type": "Choice", "n": len(status_pairs),
             "accuracy": sum(p["got"] == p["want"] for p in status_pairs) / len(status_pairs)}]
    for q in mod.VERIFY:
        rows.append(_noul_row(q, [(c[q], c[f"ref_{q}"], q in c["ambiguous"]) for c in per_case]))
    rows.append({"question": "justification", "type": "Score", "n": len(per_case),
                 "exact": sum(round(c["justification"]) == c["ref_justification"] for c in per_case) / len(per_case),
                 "mae": statistics.mean(abs(c["justification"] - c["ref_justification"]) for c in per_case)})
    confusion: dict[str, dict[str, int]] = {}
    for p in status_pairs:
        confusion.setdefault(p["want"], {}).setdefault(p["got"], 0)
        confusion[p["want"]][p["got"]] += 1
    n = len(per_case)
    policy = {
        "action_exact": sum(c["action"] == c["ref_action"] for c in per_case) / n,
        "missed_holds": sum(c["ref_action"] == 2 and c["action"] < 2 for c in per_case),
        "false_holds": sum(c["ref_action"] < 2 and c["action"] == 2 for c in per_case),
        "ref_holds": sum(c["ref_action"] == 2 for c in per_case),
    }
    errors = [p for p in status_pairs if p["got"] != p["want"]]
    return {"perf": perf(results), "questions": rows, "policy": policy, "cases": per_case,
            "status_confusion": confusion, "status_errors": errors}


def eval_s3() -> dict:
    mod, cases, results = _load("s3_inbox")
    per_case = []
    for r in results["cases"]:
        case, a = cases[r["patient"]], r["answers"]
        ref, dec = case["reference"], mod.decide(case, a)
        per_case.append({
            "patient": r["patient"], "message": case["message"],
            "route": a["route"]["choice"], "route_conf": a["route"]["confidence"], "ref_route": ref["route"],
            "urgency": a["urgency"]["score"], "ref_urgency": ref["urgency"],
            **{k: a[k]["noul"] for k in ("red_flag", "medication_issue", "safeguarding")},
            **{f"ref_{k}": ref[k] for k in ("red_flag", "medication_issue", "safeguarding")},
            "escalate": dec["escalate"], "reasons": dec["reasons"], "ambiguous": ref.get("ambiguous", []),
        })
    n = len(per_case)
    rows = [
        {"question": "route", "type": "Choice", "n": n,
         "accuracy": sum(c["route"] in c["ref_route"] for c in per_case) / n,
         "accuracy_primary": sum(c["route"] == c["ref_route"][0] for c in per_case) / n},
        {"question": "urgency", "type": "Score", "n": n,
         "exact": sum(round(c["urgency"]) == c["ref_urgency"] for c in per_case) / n,
         "mae": statistics.mean(abs(c["urgency"] - c["ref_urgency"]) for c in per_case)},
    ]
    for q in ("red_flag", "medication_issue", "safeguarding"):
        rows.append(_noul_row(q, [(c[q], c[f"ref_{q}"], q in c["ambiguous"]) for c in per_case]))
    auto = [c for c in per_case if not c["escalate"]]
    esc = [c for c in per_case if c["escalate"]]
    policy = {
        "auto_dispatched": len(auto),
        "auto_route_accuracy": sum(c["route"] in c["ref_route"] for c in auto) / len(auto) if auto else None,
        "escalated": len(esc),
        "escalated_route_accuracy": sum(c["route"] in c["ref_route"] for c in esc) / len(esc) if esc else None,
        "emergencies": sum("emergency_services" == c["ref_route"][0] for c in per_case),
        "emergencies_auto_missed": sum(c["ref_route"][0] == "emergency_services" and c["route"] != "emergency_services"
                                       and not c["escalate"] for c in per_case),
    }
    return {"perf": perf(results), "questions": rows, "policy": policy, "cases": per_case}


def _truth(name: str, case: dict, qid: str):
    ref = case["reference"]
    if name == "s2_discharge" and qid.startswith("med_"):
        from .s2_discharge import reference_statuses
        return reference_statuses(case)[int(qid.removeprefix("med_"))]
    return ref[qid]


def _jev(answer: dict):
    return {"noul": lambda a: a["noul"] >= YES, "choice": lambda a: a["choice"],
            "score": lambda a: round(a["score"])}[answer["type"]](answer)


def _match(truth, value) -> bool:
    return value in truth if isinstance(truth, list) else value == truth


def eval_system_two() -> dict | None:
    path = RESULTS_DIR / "system_two_review.json"
    if not path.exists():
        return None
    review = json.loads(path.read_text())
    items = []
    for item_id, rv in review["items"].items():
        name, pid, qid = item_id.split("/")
        mod, cases, results = _load(name)
        case = cases[pid]
        answer = next(r for r in results["cases"] if r["patient"] == pid)["answers"][qid]
        truth = _truth(name, case, qid)
        items.append({"id": item_id, "scenario": name, "question": qid, "truth": truth,
                      "jev": _jev(answer), "reviewer": rv["answer"], "rationale": rv["rationale"],
                      "ambiguous": qid in case["reference"].get("ambiguous", [])})
    for it in items:
        it["jev_correct"] = _match(it["truth"], it["jev"])
        it["reviewer_correct"] = _match(it["truth"], it["reviewer"])
    by = lambda f: {s: [i for i in items if i["scenario"] == s and f(i)] for s in ("s1_ward", "s2_discharge", "s3_inbox")}
    summary = {s: {"items": len(v), "jev_correct": sum(i["jev_correct"] for i in v),
                   "reviewer_correct": sum(i["reviewer_correct"] for i in v)} for s, v in by(lambda i: True).items()}

    # Final pipeline decisions with reviewed answers substituted in.
    reviewed = {i["id"]: i["reviewer"] for i in items}
    final = {}
    mod, cases, results = _load("s2_discharge")
    acts = []
    for r in results["cases"]:
        case = cases[r["patient"]]
        answers = json.loads(json.dumps(r["answers"]))
        for qid, a in answers.items():
            v = reviewed.get(f"s2_discharge/{r['patient']}/{qid}")
            if v is None:
                continue
            if a["type"] == "noul":
                a["noul"] = 1.0 if v else 0.0
            elif a["type"] == "choice":
                a["choice"], a["confidence"] = v, 1.0
        acts.append((mod.decide(case, answers)["action"], mod.reference(case)["action"]))
    final["s2_action_exact"] = sum(a == b for a, b in acts) / len(acts)
    final["s2_missed_holds"] = sum(b == 2 and a < 2 for a, b in acts)
    final["s2_false_holds"] = sum(b < 2 and a == 2 for a, b in acts)
    mod, cases, results = _load("s3_inbox")
    routes = []
    for r in results["cases"]:
        route = reviewed.get(f"s3_inbox/{r['patient']}/route", r["answers"]["route"]["choice"])
        routes.append(route in cases[r["patient"]]["reference"]["route"])
    final["s3_route_accuracy"] = sum(routes) / len(routes)
    return {"reviewer": review["reviewer"], "summary": summary, "final": final, "items": items}


def main() -> None:
    out = {"s1_ward": eval_s1(), "s2_discharge": eval_s2(), "s3_inbox": eval_s3(), "system_two": eval_system_two()}
    (RESULTS_DIR / "evaluation.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print("\n=== system_two", json.dumps(out["system_two"] and {k: v for k, v in out["system_two"].items() if k != "items"}))
    for name, ev in list(out.items())[:3]:
        print(f"\n=== {name}\n", json.dumps(ev["perf"]), "\n", json.dumps(ev["policy"]))
        for row in ev["questions"]:
            print("  ", {k: round(v, 3) if isinstance(v, float) else v for k, v in row.items()})


if __name__ == "__main__":
    main()
