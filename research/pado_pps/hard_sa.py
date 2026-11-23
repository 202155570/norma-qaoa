"""Simulated annealing on the 12 hard problems of hard_rqaoa.py (MILP-certified k-optima). Exploratory.

Two versions, both with R independent replicas run in parallel (numpy), geometric temperature schedule
from T0 to T1 (T0 = median |Delta| of random moves at a random start, T1 = T0 / 1000):
  swap  moves keep exactly k selected (swap one selected item for one unselected); the classical
        counterpart of a constraint-preserving mixer
  flip  single-bit flips on the QUBO with the quadratic cardinality penalty P (sum x - k)^2, P as in
        hard_rqaoa.py (read from hard_rqaoa.jsonl); what an annealer that takes a QUBO faces.
        Reported: share of replicas ending with exactly k, best G among those.
Per problem and version: best G, hit (= certified optimum, 1e-9 relative), share of replicas at the optimum,
seconds. argv: <out.jsonl> [sweeps] [replicas]
"""

import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hard  # noqa: E402
import hard_rqaoa as H  # noqa: E402

REL = 1e-9


def sa_swap(lin, Q, k, sweeps, R, rng):
    n = len(lin)
    X = np.zeros((R, n), bool)
    for r in range(R):
        X[r, rng.choice(n, k, replace=False)] = True
    S = X.astype(float) @ Q                                      # S[r, i] = sum_{j in T} Q_ij
    def delta(a, b):                                             # swap out a (in T), in b (not in T)
        ar = np.arange(R)
        return (lin[b] + S[ar, b] - Q[a, b]) - (lin[a] + S[ar, a])
    # pick random in/out indices via ranks of random keys (vectorised)
    def pick():
        key = rng.random((R, n))
        a = np.argmax(np.where(X, key, -1.0), 1); b = np.argmax(np.where(~X, key, -1.0), 1)
        return a, b
    a, b = pick(); T0 = float(np.median(np.abs(delta(a, b)))) or 1.0
    steps = sweeps * n
    temps = T0 * (1e-3) ** (np.arange(steps) / max(steps - 1, 1))
    ar = np.arange(R)
    for t in range(steps):
        a, b = pick()
        d = delta(a, b)
        acc = (d <= 0) | (rng.random(R) < np.exp(-np.maximum(d, 0) / temps[t]))
        if acc.any():
            r = ar[acc]
            X[r, a[acc]] = False; X[r, b[acc]] = True
            S[r] += Q[b[acc]] - Q[a[acc]]
    G = np.array([hard.energy(sorted(np.flatnonzero(x).tolist()), lin, Q) for x in X])
    return G, X


def sa_flip(lin, Q, k, P, sweeps, R, rng):
    n = len(lin)
    linp = lin + P * (1 - 2 * k); Qp = Q + 2.0 * P; np.fill_diagonal(Qp, 0.0)
    X = rng.random((R, n)) < k / n
    S = X.astype(float) @ Qp
    ar = np.arange(R)
    i = rng.integers(0, n, R)
    d = np.where(X[ar, i], -1.0, 1.0) * (linp[i] + S[ar, i])
    T0 = float(np.median(np.abs(d))) or 1.0
    steps = sweeps * n
    temps = T0 * (1e-3) ** (np.arange(steps) / max(steps - 1, 1))
    for t in range(steps):
        i = rng.integers(0, n, R)
        sgn = np.where(X[ar, i], -1.0, 1.0)
        d = sgn * (linp[i] + S[ar, i])
        acc = (d <= 0) | (rng.random(R) < np.exp(-np.maximum(d, 0) / temps[t]))
        if acc.any():
            r = ar[acc]
            X[r, i[acc]] = ~X[r, i[acc]]
            S[r] += sgn[acc][:, None] * Qp[i[acc]]
    cnt = X.sum(1)
    G = np.array([hard.energy(sorted(np.flatnonzero(x).tolist()), lin, Q) if c == k else np.inf for x, c in zip(X, cnt)])
    return G, cnt


def main(out, sweeps, R):
    Pq = {}
    for l in open(os.path.join(HERE, "hard_rqaoa.jsonl")):
        r = json.loads(l)
        if r["penalty"] == "quad":
            Pq[r["key"]] = r["lam"]
    fo = open(os.path.join(HERE, out), "a")
    for ref in H.problems():
        N, k = ref["N"], ref["k"]
        lin, Q = hard.make(N, k, ref["family"], ref["density"], ref["strength"])
        Gopt = ref["milp_G"]; tol = REL * abs(Gopt)
        for ver in ("swap", "flip"):
            rng = np.random.default_rng([N, k, int(ref["strength"] * 100), len(ref["family"]), 5])
            t0 = time.time()
            if ver == "swap":
                G, _ = sa_swap(lin, Q, k, sweeps, R, rng); feas = 1.0
            else:
                G, cnt = sa_flip(lin, Q, k, Pq[ref["key"]], sweeps, R, rng); feas = float(np.mean(cnt == k))
            sec = time.time() - t0
            best = float(G.min())
            row = {"key": ref["key"], "N": N, "k": k, "version": ver, "sweeps": sweeps, "replicas": R,
                   "G_opt": Gopt, "best_G": best if np.isfinite(best) else None,
                   "hit": bool(best <= Gopt + tol), "hit_share": float(np.mean(G <= Gopt + tol)),
                   "feasible_share": feas, "rel_gap": (best - Gopt) / abs(Gopt) if np.isfinite(best) else None,
                   "seconds": sec, "P": Pq[ref["key"]] if ver == "flip" else None}
            fo.write(json.dumps(row) + "\n"); fo.flush()
            print(f"{ref['key']:26s} {ver:4s} hit {row['hit']!s:5} share {row['hit_share']:.2f} feasible {feas:.2f} "
                  f"gap {row['rel_gap'] if row['rel_gap'] is not None else float('nan'):+.2e} {sec:.1f}s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 200, int(sys.argv[3]) if len(sys.argv) > 3 else 100)
