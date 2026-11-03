"""Original MaiQ objective and its PADO variant for N = 50, 100, 150 (k = 6).

Original (FAIQ Co-Sign definitions): score s_i = rank score of the mean 3/6/12-month return,
rho = Pearson correlation of the last 126 daily log returns,
  G(x) = sum_i -WS s_i x_i + sum_{i<j} Q_ij x_i x_j,  Q_ij = WC max(rho,0) + WCAP [rho > 0.70],
  subject to sum x = k.

Variant, step 1 (exact on sum x = k): fit Q_ij ~ c + a_i + a_j over all pairs. On any k-subset
  sum_{i<j in S} (c + a_i + a_j) = c C(k,2) + (k-1) sum_{i in S} a_i,
so moving the fit into the linear term leaves G unchanged up to a constant. This removes the
part of the correlation that every ETF shares (the market) and the part each ETF carries to
every partner, leaving the residual R_ij = Q_ij - c - a_i - a_j.
Variant, step 2 (the approximation): keep residual pairs by |R| (cap pairs first) while both
ends have degree < 3; drop the rest.
Variant, step 3: drop sum x = k and add lambda sum x (chosen later by lam.py); samples are
repaired to k afterwards.

Universes: N=50 is the original 50; N=100 adds every other one of the 100 added ETFs;
N=150 adds all.

argv: <prices.json>   writes problem_<N>.json
"""

import itertools
import json
import os
import sys

import numpy as np
from scipy.stats import rankdata

WS, WC, WCAP, RHO_CAP, K, DEG = 1.0, 0.5, 2.0, 0.70, 6, 3
HERE = os.path.dirname(os.path.abspath(__file__))
PX = json.load(open(sys.argv[1]))
ALL = PX["syms"]; P_ALL = np.array(PX["prices"]).T                       # T x 150
base = PX["base50"]; added = [s for s in ALL if s not in base]
UNIV = {50: base, 100: base + added[0::2], 150: ALL}


def build(syms):
    n = len(syms)
    P = P_ALL[:, [ALL.index(s) for s in syms]]
    ret = [P[-1] / P[-1 - d] - 1.0 for d in (63, 126, 252)]
    S = (rankdata(sum(ret) / 3.0, method="average") - 1.0) / (n - 1)
    rho = np.corrcoef(np.diff(np.log(P[-127:]), axis=0).T)
    Q = WC * np.maximum(rho, 0.0) + WCAP * (rho > RHO_CAP)
    np.fill_diagonal(Q, 0.0)
    lin = -WS * S
    iu = np.triu_indices(n, 1)
    # additive fit Q_ij ~ c + a_i + a_j (least squares over the pairs)
    A = np.zeros((len(iu[0]), n + 1)); A[:, 0] = 1.0
    A[np.arange(len(iu[0])), 1 + iu[0]] = 1.0; A[np.arange(len(iu[0])), 1 + iu[1]] = 1.0
    coef = np.linalg.lstsq(A, Q[iu], rcond=None)[0]
    c, a = float(coef[0]), coef[1:]
    R = Q - c - a[:, None] - a[None, :]
    np.fill_diagonal(R, 0.0)
    d = lin + (K - 1) * a
    # check the exactness of step 1 on random k-subsets
    rng = np.random.default_rng(0)
    for _ in range(200):
        s = rng.choice(n, K, replace=False)
        g0 = lin[s].sum() + sum(Q[i, j] for i, j in itertools.combinations(s, 2))
        g1 = d[s].sum() + sum(R[i, j] for i, j in itertools.combinations(s, 2)) + c * K * (K - 1) / 2
        assert abs(g0 - g1) < 1e-9, (g0, g1)
    # degree-capped sparsification
    pairs = sorted(zip(*iu), key=lambda e: (not rho[e] > RHO_CAP, -abs(R[e])))
    deg = np.zeros(n, int); kept = []
    for i, j in pairs:
        if deg[i] < DEG and deg[j] < DEG:
            kept.append((int(i), int(j), float(R[i, j]))); deg[i] += 1; deg[j] += 1
    caps = [(int(i), int(j)) for i, j in zip(*iu) if rho[i, j] > RHO_CAP]
    kept_set = {(i, j) for i, j, _ in kept}
    # Ising of the variant at lambda = 0:  x = (1 - z)/2
    h0 = -d / 2.0
    for i, j, v in kept:
        h0[i] -= v / 4.0; h0[j] -= v / 4.0
    J = [(i, j, v / 4.0) for i, j, v in kept]
    rabs = np.abs(R[iu])
    return {"syms": syms, "k": K, "score": S.tolist(), "lin": lin.tolist(), "Q": Q.tolist(),
            "fit_c": c, "fit_a": a.tolist(), "d": d.tolist(), "R_kept": kept,
            "h0": h0.tolist(), "J": J, "max_degree": int(deg.max()),
            "stats": {"pairs": len(rabs), "Q_nonzero": int((Q[iu] != 0).sum()), "kept": len(kept),
                      "cap_pairs": len(caps), "cap_pairs_kept": sum(e in kept_set for e in caps),
                      "Q_var_explained_by_fit": float(1 - ((R[iu]) ** 2).sum() / ((Q[iu] - Q[iu].mean()) ** 2).sum()),
                      "R_abs_kept_share": float(sum(abs(v) for *_, v in kept) / rabs.sum())},
            "data_sha256": PX["sha256"], "dates": [PX["dates"][0], PX["dates"][-1]]}


if __name__ == "__main__":
    for n, syms in UNIV.items():
        pb = build(syms)
        json.dump(pb, open(os.path.join(HERE, f"problem_{n}.json"), "w"))
        print(n, pb["max_degree"], json.dumps(pb["stats"]), flush=True)
