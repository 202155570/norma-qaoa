"""Summarise the PPS-training map (README 6.9).

small.jsonl: capture per (d, w, p), median and min over instances. Exact reference at depth p is
the best exact-scored energy of the chains run on that instance (the exact chain and every PPS
chain), so an exact chain stuck in a local optimum does not inflate capture above 1.
large.jsonl: w-convergence (w_gap_over_extra_gain <= 0.10) and, where the light cone fits,
capture against the exact-trained light-cone chain.

argv: [small.jsonl] [large.jsonl]   ->  prints tables, writes map.json
"""

import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CRIT, WCONV = 0.90, 0.10


def load(path):
    return [json.loads(l) for l in open(path)] if os.path.exists(path) else []


def small_map(rows):
    best = defaultdict(lambda: np.inf)          # (d, inst, p) -> best exact-scored energy
    for r in rows:
        k = (r["d"], r["inst"], r["p"])
        best[k] = min(best[k], r["E_exact_trained"], r["E_pps_trained_scored"])
    cells = defaultdict(list)
    for r in rows:
        if r["p"] == 1:
            continue
        ref = best[(r["d"], r["inst"], r["p"])]
        extra = r["E1"] - ref
        if extra <= 1e-9:
            continue
        cells[(r["d"], r["w"], r["p"])].append({
            "inst": r["inst"], "capture": (r["E1"] - r["E_pps_trained_scored"]) / extra,
            "capture_raw": r["capture"], "compile_s": r["compile_s"], "train_s": r["pps_train_s"]})
    out = []
    for (d, w, p), v in sorted(cells.items()):
        c = [x["capture"] for x in v]
        out.append({"d": d, "w": w, "p": p, "n_inst": len(v), "capture_median": float(np.median(c)),
                    "capture_min": float(min(c)), "pass_median": bool(np.median(c) >= CRIT),
                    "pass_all": bool(min(c) >= CRIT), "compile_s_max": max(x["compile_s"] for x in v),
                    "train_s_max": max(x["train_s"] for x in v), "per_inst": v})
    return out


def large_map(rows):
    out = []
    for r in rows:
        if "infeasible" in r:
            out.append({k: r[k] for k in ("N", "d", "w_train", "p", "w", "stage", "infeasible", "peak_rss_gb")})
            continue
        e = {k: r.get(k) for k in ("N", "d", "max_degree", "edges", "p", "w_train", "w_gap_over_extra_gain",
                                   "compile_train_s", "compile_check_s", "train_s", "peak_rss_gb", "peak_gpu_gb",
                                   "max_ball", "check_infeasible")}
        g = r["w_gap_over_extra_gain"]
        e["w_converged"] = None if g is None else bool(g <= WCONV)
        if "E_exact_trained" in r and r["p"] > 1:
            ref = min(r["E_exact_trained"], r["E_exact_of_pps_angles"])
            extra = r["E1_ref"] - ref
            e["capture_lc"] = (r["E1_ref"] - r["E_exact_of_pps_angles"]) / extra if extra > 1e-9 else None
        out.append(e)
    return out


def fmt(v, f="{:.3f}"):
    return "-" if v is None else (f.format(v) if isinstance(v, float) else str(v))


if __name__ == "__main__":
    sp = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "small.jsonl")
    lp = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "large.jsonl")
    sm, lm = small_map(load(sp)), large_map(load(lp))
    print("small (N=20): d w p | n  capture median / min  | compile max s  train max s")
    for c in sm:
        print(f"  {c['d']} {c['w']} {c['p']} | {c['n_inst']}  {c['capture_median']:.3f} / {c['capture_min']:.3f}"
              f"{'' if c['pass_all'] else ' *'}  | {c['compile_s_max']:.0f}  {c['train_s_max']:.0f}")
    print("large: N d w p | w-gap/extra  conv  capture_lc | compile train/check s  peak RAM/GPU GB")
    for e in lm:
        if "infeasible" in e:
            print(f"  {e['N']} {e['d']} {e['w_train']} {e['p']} | INFEASIBLE w={e['w']} {e['stage']}: {e['infeasible']}")
            continue
        print(f"  {e['N']} {e['d']} {e['w_train']} {e['p']} | {fmt(e['w_gap_over_extra_gain'], '{:.2e}')}  {fmt(e['w_converged'])}"
              f"  {fmt(e.get('capture_lc'))} | {fmt(e['compile_train_s'], '{:.0f}')}/{fmt(e['compile_check_s'], '{:.0f}')}"
              f"  {fmt(e['peak_rss_gb'])}/{fmt(e.get('peak_gpu_gb'))}"
              + (f"  check: {e['check_infeasible']}" if e.get("check_infeasible") else ""))
    json.dump({"criterion": CRIT, "w_conv": WCONV, "small": sm, "large": lm},
              open(os.path.join(HERE, "map.json"), "w"), indent=1)
