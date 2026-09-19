"""Evaluation of the expanded study: generated S1–S3 cases (dev/test), the S2 v2
decomposition, S4 search, S5 features, and the Claude Haiku baseline.

Thresholds are tuned on `dev` only and reported on `test`. The original 20
hand-authored cases per scenario are reported separately as `hand`.
"""

from __future__ import annotations

import json
import statistics
from importlib import import_module

import numpy as np

from .common import RESULTS_DIR, YES, load_scenario
from .evaluate import PRICE_PER_MTOK, _pct

GRID = [round(x, 2) for x in np.arange(0.1, 0.91, 0.05)]


def _load(run: str):
    res = json.loads((RESULTS_DIR / f"{run}.json").read_text())
    scen = res.get("scenario_file", run)
    module = scen.removesuffix("_gen")
    mod = import_module(f"explore_typesafe.{module}")
    cases = {c["patient"]: c for c in load_scenario(scen)["cases"]}
    return mod, cases, res


def _truth(module: str, case: dict, qid: str):
    ref = case["reference"]
    if module == "s2_discharge" and qid.startswith("med_"):
        from .s2_discharge import reference_statuses
        return reference_statuses(case)[int(qid[4:])]
    return ref.get(qid)


def _match(truth, value) -> bool:
    return value in truth if isinstance(truth, list) else value == truth


def _haiku_value(qtype: str, a: dict | None):
    """Normalise a Haiku answer into Jev's answer shape (None if missing/invalid)."""
    if not isinstance(a, dict):
        return None
    try:
        if qtype == "noul":
            return {"type": "noul", "noul": float(a["p_yes"])}
        if qtype == "choice":
            return {"type": "choice", "choice": a["choice"], "confidence": float(a.get("confidence", 1))}
        return {"type": "score", "score": float(a["level"]), "confidence": float(a.get("confidence", 1))}
    except (KeyError, TypeError, ValueError):
        return None


def question_table(run: str, answers_by_patient: dict | None = None, splits=("hand", "dev", "test")) -> dict:
    """Per question id family: accuracy (Noul at 0.5), Choice accuracy, Score exact/MAE, by split."""
    mod, cases, res = _load(run)
    module = res.get("scenario_file", run).removesuffix("_gen")
    rows: dict[tuple, list] = {}
    for r in res["cases"]:
        case = cases[r["patient"]]
        split = r.get("split") or "hand"
        answers = answers_by_patient[r["patient"]] if answers_by_patient is not None else r["answers"]
        for qid, q in r["questions"].items():
            truth = _truth(module, case, qid)
            if truth is None:
                continue
            a = answers.get(qid)
            if answers_by_patient is not None:
                a = _haiku_value(q["type"], a)
            fam = "med_status" if qid.startswith("med_") else qid
            rows.setdefault((fam, q["type"], split), []).append((a, truth, qid in case["reference"].get("ambiguous", [])))
    out = {}
    for (fam, qtype, split), items in rows.items():
        n = len(items)
        if qtype == "noul":
            ok = [a is not None and (a["noul"] >= YES) == t for a, t, _ in items]
            brier = statistics.mean((a["noul"] - t) ** 2 for a, t, _ in items if a is not None) if any(a for a, _, _ in items) else None
            out.setdefault(fam, {"type": "Noul"})[split] = {"n": n, "accuracy": sum(ok) / n, "brier": brier}
        elif qtype == "choice":
            ok = [a is not None and _match(t, a["choice"]) for a, t, _ in items]
            out.setdefault(fam, {"type": "Choice"})[split] = {"n": n, "accuracy": sum(ok) / n}
        else:
            ok = [a is not None and round(a["score"]) == t for a, t, _ in items]
            mae = statistics.mean(abs(a["score"] - t) for a, t, _ in items if a is not None)
            out.setdefault(fam, {"type": "Score"})[split] = {"n": n, "exact": sum(ok) / n, "mae": mae}
    return out


def tune_nouls(run: str) -> dict:
    """Per-Noul threshold maximising dev accuracy, then dev/test accuracy at 0.5 and at the tuned threshold."""
    mod, cases, res = _load(run)
    module = res.get("scenario_file", run).removesuffix("_gen")
    fams: dict[str, dict[str, list]] = {}
    for r in res["cases"]:
        for qid, q in r["questions"].items():
            if q["type"] != "noul":
                continue
            t = _truth(module, cases[r["patient"]], qid)
            if t is None:
                continue
            fams.setdefault(qid, {}).setdefault(r["split"], []).append((r["answers"][qid]["noul"], t))
    out = {}
    for qid, by in fams.items():
        acc = lambda xs, th: sum((p >= th) == t for p, t in xs) / len(xs)
        best = max(GRID, key=lambda th: (acc(by["dev"], th), -abs(th - 0.5)))
        out[qid] = {"threshold": best, "dev_at_0.5": acc(by["dev"], 0.5), "dev_tuned": acc(by["dev"], best),
                    "test_at_0.5": acc(by["test"], 0.5), "test_tuned": acc(by["test"], best), "n_test": len(by["test"])}
    return out


def perf(run: str) -> dict:
    res = json.loads((RESULTS_DIR / f"{run}.json").read_text())
    lat = [c["latency_ms"] for c in res["cases"]]
    tin = sum(c["usage"]["input_tokens"] for c in res["cases"])
    return {"model": sorted({c["model"] for c in res["cases"]}), "requests": len(lat),
            "questions": sum(len(c["questions"]) for c in res["cases"]), "concurrency": res.get("concurrency", 1),
            "wall_seconds": res.get("wall_seconds"), "p50_ms": round(_pct(lat, 0.5)), "p95_ms": round(_pct(lat, 0.95)),
            "input_tokens": tin, "output_tokens": sum(c["usage"]["output_tokens"] for c in res["cases"]),
            "cost_usd": tin / 1e6 * PRICE_PER_MTOK}


# ---- scenario policies on generated sets ---------------------------------------------

def s1_policy(run="s1_ward_gen") -> dict:
    mod, cases, res = _load(run)
    out = {}
    for split in ("dev", "test"):
        rows = [(mod.decide(cases[r["patient"]], r["answers"]), mod.reference(cases[r["patient"]]))
                for r in res["cases"] if r["split"] == split]
        n = len(rows)
        out[split] = {"n": n,
                      "news2_only_exact": sum(d["baseline_band"] == f["band"] for d, f in rows) / n,
                      "news2_only_under": sum(d["baseline_band"] < f["band"] for d, f in rows),
                      "combined_exact": sum(d["band"] == f["band"] for d, f in rows) / n,
                      "combined_under": sum(d["band"] < f["band"] for d, f in rows),
                      "combined_over": sum(d["band"] > f["band"] for d, f in rows)}
    return out


def s2_policy() -> dict:
    """v1 (single verification Nouls) vs v2 (decomposed) on hand and generated test cases."""
    from . import s2_discharge as s2
    out = {}
    for label, v1run, v2run, split in (("hand", "s2_discharge", "s2_discharge_v2", None),
                                       ("gen_test", "s2_discharge_gen", "s2_discharge_gen_v2", "test"),
                                       ("gen_dev", "s2_discharge_gen", "s2_discharge_gen_v2", "dev")):
        _, cases, r1 = _load(v1run)
        _, _, r2 = _load(v2run)
        a2 = {c["patient"]: c["answers"] for c in r2["cases"]}
        rows = []
        for r in r1["cases"]:
            if split and r["split"] != split:
                continue
            case = cases[r["patient"]]
            rows.append((s2.decide(case, r["answers"]), s2.decide_v2(case, a2[r["patient"]]), s2.reference(case)))
        n = len(rows)
        flag = {}
        for f in s2.VERIFY:
            for v, idx in (("v1", 0), ("v2", 1)):
                tp = sum(x[idx]["flags"][f] and x[2]["flags"][f] for x in rows)
                fp = sum(x[idx]["flags"][f] and not x[2]["flags"][f] for x in rows)
                fn = sum(not x[idx]["flags"][f] and x[2]["flags"][f] for x in rows)
                flag.setdefault(f, {})[v] = {"accuracy": sum(x[idx]["flags"][f] == x[2]["flags"][f] for x in rows) / n,
                                             "tp": tp, "fp": fp, "fn": fn}
        out[label] = {"n": n, "flags": flag,
                      "action_v1": sum(x[0]["action"] == x[2]["action"] for x in rows) / n,
                      "action_v2": sum(x[1]["action"] == x[2]["action"] for x in rows) / n,
                      "missed_holds_v1": sum(x[2]["action"] == 2 and x[0]["action"] < 2 for x in rows),
                      "missed_holds_v2": sum(x[2]["action"] == 2 and x[1]["action"] < 2 for x in rows),
                      "false_holds_v1": sum(x[2]["action"] < 2 and x[0]["action"] == 2 for x in rows),
                      "false_holds_v2": sum(x[2]["action"] < 2 and x[1]["action"] == 2 for x in rows)}
    return out


def s3_gate(run="s3_inbox_gen") -> dict:
    """Default gate (route confidence < 0.6 etc.) vs a route-confidence gate tuned on dev to reach 95% auto accuracy."""
    mod, cases, res = _load(run)
    def evaluate(split, conf_gate):
        auto = esc = auto_ok = 0
        for r in res["cases"]:
            if r["split"] != split:
                continue
            a, ref = r["answers"], cases[r["patient"]]["reference"]
            reasons = mod.decide(cases[r["patient"]], a)["reasons"]
            reasons = [x for x in reasons if x != "low route confidence"]
            if a["route"]["confidence"] < conf_gate:
                reasons.append("low route confidence")
            if reasons:
                esc += 1
            else:
                auto += 1
                auto_ok += a["route"]["choice"] in ref["route"]
        return {"auto": auto, "escalated": esc, "auto_accuracy": auto_ok / auto if auto else None}
    candidates = [g for g in GRID if (evaluate("dev", g)["auto_accuracy"] or 0) >= 0.95]
    tuned = min(candidates) if candidates else 0.9
    return {"default_gate": 0.6, "tuned_gate": tuned,
            "dev_default": evaluate("dev", 0.6), "test_default": evaluate("test", 0.6),
            "dev_tuned": evaluate("dev", tuned), "test_tuned": evaluate("test", tuned),
            "route_accuracy": {s: sum(r["answers"]["route"]["choice"] in cases[r["patient"]]["reference"]["route"]
                                      for r in res["cases"] if r["split"] == s) / sum(r["split"] == s for r in res["cases"])
                               for s in ("dev", "test")}}


# ---- S4 search --------------------------------------------------------------------------

def _prf(pairs):
    tp = sum(p and t for p, t in pairs); fp = sum(p and not t for p, t in pairs); fn = sum(t and not p for p, t in pairs)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": prec, "recall": rec, "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0}


def s4(answers_source: str = "jev") -> dict:
    res = json.loads((RESULTS_DIR / "s4_search.json").read_text())
    cases = load_scenario("s4_search")["cases"]
    haiku = None
    if answers_source == "haiku":
        haiku = json.loads((RESULTS_DIR / "haiku_s4_search.json").read_text())["cases"]
    note_pairs, lay_pairs, pat_pairs, agg_pairs, top1 = [], [], [], [], []
    for i, (r, c) in enumerate(zip(res["cases"], cases)):
        ans = r["answers"] if haiku is None else {q: _haiku_value(r["questions"][q]["type"], haiku[i]["answers"].get(q))
                                                  for q in r["questions"]}
        rel = c["reference"]["relevant"]
        probs = [(ans.get(f"note_{j}") or {"noul": 0.0})["noul"] for j in range(len(rel))]
        note_pairs += [(p >= YES, t) for p, t in zip(probs, rel)]
        lay_pairs += list(zip(c["reference"]["lay_keyword_hits"], rel))
        pat_pairs.append(((ans.get("any") or {"noul": 0.0})["noul"] >= YES, c["reference"]["any"]))
        agg_pairs.append((max(probs) >= YES, c["reference"]["any"]))
        best = (ans.get("best") or {"choice": None})["choice"]
        top1.append(best in {f"note_{j}" for j, t in enumerate(rel) if t} if c["reference"]["any"] else best == "none")
    acc = lambda ps: sum(p == t for p, t in ps) / len(ps)
    out = {"note_level": _prf(note_pairs), "lay_keyword_note_level": _prf(lay_pairs),
           "patient_any_noul": {"accuracy": acc(pat_pairs), **_prf(pat_pairs)},
           "patient_from_notes": {"accuracy": acc(agg_pairs), **_prf(agg_pairs)},
           "best_note_choice_accuracy": sum(top1) / len(top1),
           "notes_judged": len(note_pairs), "cases": len(pat_pairs)}
    if answers_source == "jev":
        out["perf"] = perf("s4_search")
    return out


# ---- S5 features -------------------------------------------------------------------------

def s5() -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import RepeatedStratifiedKFold, cross_val_predict
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    from .s5_features import QUESTIONS
    res = json.loads((RESULTS_DIR / "s5_features.json").read_text())
    cases = {c["patient"]: c for c in load_scenario("s5_features")["cases"]}
    dominant = list(QUESTIONS["dominant"]["criteria"])
    S, J, y = [], [], []
    for r in res["cases"]:
        c, a = cases[r["patient"]], r["answers"]
        s = c["structured"]
        S.append([s["age"], s["female"], s["chronic_disorders"], s["medications"], s["prior_acute_12m"]])
        J.append([a["burden"]["score"], a["polypharmacy"]["score"]]
                 + [a[k]["noul"] for k in QUESTIONS if QUESTIONS[k]["type"] == "noul"]
                 + [a["dominant"]["probabilities"].get(d, 0.0) for d in dominant])
        y.append(c["reference"]["acute_12m"])
    S, J, y = np.array(S, float), np.array(J, float), np.array(y)
    sets = {"structured": S, "jev": J, "structured+jev": np.hstack([S, J])}
    out = {"n": len(y), "positives": int(y.sum()), "models": {}}
    for name, X in sets.items():
        aucs = []
        for rep in range(5):
            cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=1, random_state=rep)
            model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
            p = np.zeros(len(y))
            for tr, te in cv.split(X, y):
                model.fit(X[tr], y[tr])
                p[te] = model.predict_proba(X[te])[:, 1]
            aucs.append(roc_auc_score(y, p))
        out["models"][name] = {"auroc_mean": float(np.mean(aucs)), "auroc_sd": float(np.std(aucs)), "features": X.shape[1]}
    # Univariate signal of each Jev feature
    names = ["burden", "polypharmacy"] + [k for k in QUESTIONS if QUESTIONS[k]["type"] == "noul"] + [f"dominant={d}" for d in dominant]
    out["univariate_auroc"] = {n: float(roc_auc_score(y, J[:, i])) for i, n in enumerate(names)}
    out["perf"] = perf("s5_features")
    return out


# ---- Haiku comparison ----------------------------------------------------------------------

def haiku_compare() -> dict:
    out = {}
    for run in ("s1_ward", "s2_discharge", "s3_inbox", "s1_ward_gen", "s2_discharge_gen", "s3_inbox_gen"):
        path = RESULTS_DIR / f"haiku_{run}.json"
        if not path.exists():
            continue
        h = json.loads(path.read_text())
        by = {c["patient"]: c["answers"] for c in h["cases"]}
        lat = [c["duration_api_ms"] for c in h["cases"] if c.get("duration_api_ms")]
        out[run] = {
            "jev": question_table(run), "haiku": question_table(run, by),
            "haiku_perf": {"model": h["model"], "parsed": sum(bool(c["answers"]) for c in h["cases"]), "requests": len(h["cases"]),
                           "p50_ms": round(_pct(lat, 0.5)), "p95_ms": round(_pct(lat, 0.95)),
                           "input_tokens": sum(c["usage"]["input_tokens"] or 0 for c in h["cases"]),
                           "output_tokens": sum(c["usage"]["output_tokens"] or 0 for c in h["cases"]),
                           "cost_usd": sum(c.get("cost_usd") or 0 for c in h["cases"])},
            "jev_perf": perf(run),
        }
    if (RESULTS_DIR / "haiku_s4_search.json").exists():
        h = json.loads((RESULTS_DIR / "haiku_s4_search.json").read_text())
        lat = [c["duration_api_ms"] for c in h["cases"] if c.get("duration_api_ms")]
        out["s4_search"] = {"jev": s4("jev"), "haiku": s4("haiku"),
                            "haiku_perf": {"model": h["model"], "parsed": sum(bool(c["answers"]) for c in h["cases"]),
                                           "requests": len(h["cases"]), "p50_ms": round(_pct(lat, 0.5)),
                                           "p95_ms": round(_pct(lat, 0.95)),
                                           "input_tokens": sum(c["usage"]["input_tokens"] or 0 for c in h["cases"]),
                                           "output_tokens": sum(c["usage"]["output_tokens"] or 0 for c in h["cases"]),
                                           "cost_usd": sum(c.get("cost_usd") or 0 for c in h["cases"])},
                            "jev_perf": perf("s4_search")}
    return out


def main() -> None:
    out = {
        "questions": {r: question_table(r) for r in ("s1_ward_gen", "s2_discharge_gen", "s3_inbox_gen")},
        "tuning": {r: tune_nouls(r) for r in ("s1_ward_gen", "s2_discharge_gen", "s3_inbox_gen")},
        "s1_policy": s1_policy(), "s2_policy": s2_policy(), "s3_gate": s3_gate(),
        "s4": s4("jev"), "s5": s5(),
        "perf": {r: perf(r) for r in ("s1_ward_gen", "s2_discharge_gen", "s3_inbox_gen", "s2_discharge_v2",
                                      "s2_discharge_gen_v2", "s4_search", "s5_features")},
        "haiku": haiku_compare(),
    }
    (RESULTS_DIR / "evaluation2.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    brief = {k: v for k, v in out.items() if k not in ("haiku", "questions", "tuning")}
    print(json.dumps(brief, indent=1, default=float)[:6000])


if __name__ == "__main__":
    main()
