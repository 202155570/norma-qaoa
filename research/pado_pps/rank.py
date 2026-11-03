"""C2: is the variant's best k=6 portfolio also good under the original MaiQ objective?

Original G(S) = sum_{i in S} lin_i + sum_{i<j in S} Q_ij.
Variant  V(S) = sum_{i in S} d_i + sum_{kept i<j in S} R_ij   (lambda is constant on |S| = k).

N=50:  exhaustive over all C(50,6) subsets: variant optimum, its original rank and percentile,
       and the original optimum for reference.          writes rank_50.json
N>=100: variant optimum and original best by swap local search (200 random restarts each);
       original percentile of the variant optimum among 1,000,000 uniform random subsets
       (seed recorded).                                   writes rank_<N>.json

argv: <N>
"""

import itertools
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
n = int(sys.argv[1])
pb = json.load(open(os.path.join(HERE, f"problem_{n}.json")))
K = pb["k"]; syms = pb["syms"]
lin = np.array(pb["lin"]); Q = np.array(pb["Q"])
d = np.array(pb["d"]); R = np.zeros((n, n))
for i, j, v in pb["R_kept"]:
    R[i, j] = R[j, i] = v


def batch_energy(c, a, M):
    e = a[c].sum(1)
    for x, y in itertools.combinations(range(K), 2):
        e = e + M[c[:, x], c[:, y]]
    return e


def local_search(a, M, rng, restarts=200):
    best = (math.inf, None)
    for _ in range(restarts):
        s = list(rng.choice(n, K, replace=False))
        f = lambda s: a[s].sum() + sum(M[x, y] for x, y in itertools.combinations(s, 2))
        cur = f(s); improved = True
        while improved:
            improved = False
            for pos in range(K):
                out = [q for q in range(n) if q not in s]
                for q in out:
                    t = s.copy(); t[pos] = q; e = f(t)
                    if e < cur - 1e-12:
                        s, cur, improved = t, e, True
                        break
                if improved:
                    break
        if cur < best[0]:
            best = (cur, sorted(int(v) for v in s))
    return best


t0 = time.time()
if n == 50:
    G_all, V_all, C_all = [], [], []
    for first in range(n - K + 1):
        rest = np.array(list(itertools.combinations(range(first + 1, n), K - 1)), dtype=np.int64)
        c = np.concatenate([np.full((len(rest), 1), first), rest], axis=1)
        G_all.append(batch_energy(c, lin, Q)); V_all.append(batch_energy(c, d, R)); C_all.append(c)
    G = np.concatenate(G_all); V = np.concatenate(V_all); C = np.concatenate(C_all)
    av, ag = int(np.argmin(V)), int(np.argmin(G))
    rank = int((G < G[av]).sum()) + 1
    out = {"N": n, "method": "exhaustive", "count": int(len(G)),
           "variant_opt": [syms[i] for i in C[av]], "variant_opt_G": float(G[av]),
           "original_opt": [syms[i] for i in C[ag]], "original_opt_G": float(G[ag]),
           "rank": rank, "percentile": rank / len(G),
           "corr_G_V": float(np.corrcoef(G, V)[0, 1]),
           "variant_opt_rank_in_V_of_original_opt": int((V < V[ag]).sum()) + 1}
else:
    rng = np.random.default_rng(2026)
    ev, sv = local_search(d, R, rng)
    eg, sg = local_search(lin, Q, rng)
    sv_a = np.array([sv])
    gv = float(batch_energy(sv_a, lin, Q)[0])
    samp = np.concatenate([np.argpartition(rng.random((100_000, n)), K, axis=1)[:, :K] for _ in range(10)])
    Gs = batch_energy(samp, lin, Q)
    out = {"N": n, "method": "local search (200 restarts) + 1e6 uniform samples, seed 2026",
           "variant_opt": [syms[i] for i in sv], "variant_opt_G": gv,
           "original_best_found": [syms[i] for i in sg], "original_best_found_G": float(eg),
           "percentile": float((Gs < gv).mean()), "samples": int(len(Gs)),
           "sample_corr_G_V": float(np.corrcoef(Gs[:200_000], batch_energy(samp[:200_000], d, R))[0, 1])}
out["seconds"] = round(time.time() - t0, 1)
json.dump(out, open(os.path.join(HERE, f"rank_{n}.json"), "w"), indent=1)
print(json.dumps(out, ensure_ascii=False))
