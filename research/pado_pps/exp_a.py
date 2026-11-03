"""Experiment A: QAOA on the PADO variant proposes, the original MaiQ objective repairs to k = 6.

Shots are drawn from the product of the exact single-qubit marginals q_i = P(x_i = 1) of the
p = 2 variant QAOA (light cone, exact). Correlations between qubits are ignored: this is the
approximation. Each shot is repaired to exactly 6 with the ORIGINAL objective G:
remove the asset whose removal lowers G most while |T| > 6, add the one that lowers G most while
|T| < 6 (candidates: the whole universe). The best repaired shot is the pick.

Baselines use the same marginal values and the same repair; only which ETF gets which q
changes:
  score order - q sorted descending, assigned to ETFs sorted by score descending
  random      - q randomly permuted over ETFs (a fresh permutation per run)
Reference (not a baseline): greedy from the empty set (what the repair does with no shot info).

Criterion (operator, 2026-11-03), per N: median over runs of the QAOA pick's original
percentile <= 1%, and the QAOA median best G lower than both baselines' median best G.

argv: <N,...> <shots> <runs>     writes exp_a_<N>.json
"""

import itertools
import json
import os
import sys
import time

import numpy as np

from lc import LightCone

HERE = os.path.dirname(os.path.abspath(__file__))


def energy(T, lin, Q):
    T = list(T)
    return float(lin[T].sum() + Q[np.ix_(T, T)][np.triu_indices(len(T), 1)].sum())


def repair(T, lin, Q, k):
    T = list(T)
    while len(T) > k:
        a = np.array(T)
        # removing t changes G by -(lin_t + sum_{s in T, s != t} Q_ts)
        contrib = lin[a] + Q[np.ix_(a, a)].sum(1)
        T.pop(int(np.argmax(contrib)))
    while len(T) < k:
        gain = lin + (Q[T].sum(0) if T else 0.0)
        gain[T] = np.inf
        T.append(int(np.argmin(gain)))
    return tuple(sorted(T))


def best_of_shots(q, lin, Q, k, shots, rng, cache):
    X = rng.random((shots, len(q))) < q
    best = (np.inf, None)
    for row in X:
        T = repair(np.flatnonzero(row), lin, Q, k)
        e = cache.get(T)
        if e is None:
            e = cache[T] = energy(T, lin, Q)
        if e < best[0]:
            best = (e, T)
    return best


if __name__ == "__main__":
    ns = [int(v) for v in sys.argv[1].split(",")]
    shots, runs = int(sys.argv[2]), int(sys.argv[3])
    for n in ns:
        t0 = time.time()
        pb = json.load(open(os.path.join(HERE, f"problem_{n}.json")))
        k, syms = pb["k"], pb["syms"]
        lin, Q = np.array(pb["lin"]), np.array(pb["Q"])
        S = np.array(pb["score"])
        z = LightCone(n, np.array(pb["h"]), pb["J"], 2).expvals(np.array(pb["angles"]["2"]))[:n]
        q = (1.0 - z) / 2.0
        # reference distribution of the original objective for percentiles
        if n == 50:
            G = []
            for first in range(n - k + 1):
                rest = np.array(list(itertools.combinations(range(first + 1, n), k - 1)), dtype=np.int64)
                c = np.concatenate([np.full((len(rest), 1), first), rest], axis=1)
                e = lin[c].sum(1)
                for a, b in itertools.combinations(range(k), 2):
                    e = e + Q[c[:, a], c[:, b]]
                G.append(e)
            ref = np.sort(np.concatenate(G)); ref_kind = "exhaustive"
        else:
            rs = np.random.default_rng(99)
            c = np.concatenate([np.argpartition(rs.random((100_000, n)), k, axis=1)[:, :k] for _ in range(10)])
            e = lin[c].sum(1)
            for a, b in itertools.combinations(range(k), 2):
                e = e + Q[c[:, a], c[:, b]]
            ref = np.sort(e); ref_kind = "1e6 uniform samples, seed 99"
        pct = lambda g: float(np.searchsorted(ref, g, side="left") / len(ref))
        order_q = np.argsort(-q); order_s = np.argsort(-S)
        q_score = np.empty(n); q_score[order_s] = q[order_q]
        rng = np.random.default_rng(7)
        cache = {}
        res = {"qaoa": [], "score_order": [], "random": []}
        for r in range(runs):
            res["qaoa"].append(best_of_shots(q, lin, Q, k, shots, rng, cache))
            res["score_order"].append(best_of_shots(q_score, lin, Q, k, shots, rng, cache))
            res["random"].append(best_of_shots(rng.permutation(q), lin, Q, k, shots, rng, cache))
        greedy = repair([], lin, Q, k)
        summ = {}
        for m, v in res.items():
            g = np.array([e for e, _ in v])
            picks = {}
            for e, T in v:
                picks[",".join(syms[i] for i in T)] = e
            summ[m] = {"median_best_G": float(np.median(g)), "min_best_G": float(g.min()), "max_best_G": float(g.max()),
                       "median_percentile": pct(float(np.median(g))), "worst_percentile": pct(float(g.max())),
                       "distinct_picks": len(picks),
                       "most_common_pick": max(picks, key=lambda s: sum(1 for e, T in v if ",".join(syms[i] for i in T) == s))}
        win_score = sum(a[0] < b[0] for a, b in zip(res["qaoa"], res["score_order"]))
        win_rand = sum(a[0] < b[0] for a, b in zip(res["qaoa"], res["random"]))
        out = {"N": n, "shots": shots, "runs": runs, "percentile_reference": ref_kind,
               "q_sum": float(q.sum()), "q_top10": [[syms[i], round(float(q[i]), 4)] for i in order_q[:10]],
               "summary": summ,
               "qaoa_beats_score_order_runs": int(win_score), "qaoa_beats_random_runs": int(win_rand),
               "greedy_from_empty": {"pick": [syms[i] for i in greedy], "G": energy(greedy, lin, Q),
                                     "percentile": pct(energy(greedy, lin, Q))},
               "original_best_G_known": float(ref[0]) if n == 50 else json.load(open(os.path.join(HERE, f"rank_{n}.json")))["original_best_found_G"]}
        out["pass"] = (summ["qaoa"]["median_percentile"] <= 0.01
                       and summ["qaoa"]["median_best_G"] < summ["score_order"]["median_best_G"]
                       and summ["qaoa"]["median_best_G"] < summ["random"]["median_best_G"])
        out["seconds"] = round(time.time() - t0, 1)
        json.dump(out, open(os.path.join(HERE, f"exp_a_{n}_s{shots}.json"), "w"), indent=1, ensure_ascii=False)
        print(json.dumps({k_: out[k_] for k_ in ("N", "q_sum", "summary", "qaoa_beats_score_order_runs",
                                                 "qaoa_beats_random_runs", "greedy_from_empty", "original_best_G_known",
                                                 "pass", "seconds")}, ensure_ascii=False), flush=True)
