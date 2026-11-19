"""Mean-variance selection objective (cand.py C2_mv, Ledoit-Wolf covariance) on the N = 50/100/150
universes of build.py, certified with the MILP of mip.py.

Objective (minimise, exactly k = 6 selected, equal weights 1/6), as cand.py `pick` with risk = gamma:
  G(T) = sum_{i in T} lin_i + sum_{i<j in T} Q_ij
  lin_i = -S_i / k + gamma * Sigma_ii / k^2,   Q_ij = 2 gamma Sigma_ij / k^2
  = -(mean score of the 6) + gamma * (annualised variance of the equal-weight portfolio)
S: rank (0..1) of the mean 63/126/252-day return (the score of build.py / bt.py);
Sigma: Ledoit-Wolf (2004, constant-correlation target) shrinkage of the last 126 daily log
returns' covariance, x 252. gamma = 4 and 12 are the "weak" and "medium" settings of cand.md.

Unlike the proxy objective there is no correlation cap term; the pair term is the covariance
itself and is dense (every pair, both signs).

Ising form for RQAOA (x = (1 - z) / 2, z = -1 selected, cardinality by a penalty lambda * sum x):
  E(z) = const + sum_i h_i z_i + sum_{i<j} J_ij z_i z_j,
  J_ij = Q_ij / 4,  h_i = -(lin_i + lambda) / 2 - sum_{j != i} Q_ij / 4   (h0 = h at lambda = 0)

argv: build    writes mv_problem_<N>_g<gamma>.json and mv_result.json (MILP optimum, comparison
               with the proxy objective's optimum on the same universe)
      variant  PADO variant (additive fit + degree-3 sparsification, as build.py) of each problem:
               mv_variant_<N>_g<gamma>.json; its MILP k=6 optimum scored on the full objective
"""

import json
import os
import sys

import numpy as np
from scipy.stats import rankdata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cand import lw_const_corr  # noqa: E402
from mip import energy, solve  # noqa: E402

K = 6
GAMMAS = (4, 12)


def universes(px):
    allsyms = px["syms"]; base = px["base50"]; added = [s for s in allsyms if s not in base]
    return {50: base, 100: base + added[0::2], 150: allsyms}


def build_one(P, syms, gamma):
    n = len(syms)
    S = (rankdata(sum(P[-1] / P[-1 - d] - 1.0 for d in (63, 126, 252)) / 3.0, method="average") - 1.0) / (n - 1)
    lr = np.diff(np.log(P[-127:]), axis=0)
    cov, delta = lw_const_corr(lr)
    cov = cov * 252.0
    lin = -S / K + gamma * np.diag(cov) / K ** 2
    Q = 2.0 * gamma * cov / K ** 2
    np.fill_diagonal(Q, 0.0)
    h0 = -lin / 2.0 - Q.sum(1) / 4.0
    iu = np.triu_indices(n, 1)
    J = [(int(i), int(j), float(Q[i, j] / 4.0)) for i, j in zip(*iu)]
    return {"syms": syms, "k": K, "gamma": gamma, "score": S.tolist(), "lin": lin.tolist(), "Q": Q.tolist(),
            "cov": cov.tolist(), "lw_delta": float(delta), "h0": h0.tolist(), "J": J}


def port_stats(T, cov, rho):
    w = np.zeros(len(cov)); w[T] = 1.0 / len(T)
    return {"vol": float(np.sqrt(w @ cov @ w)),
            "avg_corr": float(np.mean([rho[i, j] for a, i in enumerate(T) for j in T[a + 1:]]))}


def cmd_build():
    px = json.load(open(os.path.join(HERE, "prices.json")))
    allsyms = px["syms"]; P_all = np.array(px["prices"]).T
    out = {}
    for N, syms in universes(px).items():
        P = P_all[:, [allsyms.index(s) for s in syms]]
        rho = np.corrcoef(np.diff(np.log(P[-127:]), axis=0).T)
        proxy = json.load(open(os.path.join(HERE, f"problem_{N}.json")))
        assert proxy["syms"] == syms
        mp = json.load(open(os.path.join(HERE, "mip_result.json")))[f"N{N}_original"]
        proxyT = sorted(syms.index(u) for u in mp["pick"])
        for g in GAMMAS:
            pb = build_one(P, syms, g)
            pb.update(data_sha256=px["sha256"], dates=[px["dates"][0], px["dates"][-1]])
            json.dump(pb, open(os.path.join(HERE, f"mv_problem_{N}_g{g}.json"), "w"))
            lin, Q, cov = np.array(pb["lin"]), np.array(pb["Q"]), np.array(pb["cov"])
            s = solve(lin, Q, K)
            T = s.pop("T")
            r = {**s, "N": N, "gamma": g, "pick": [syms[i] for i in T], "lw_delta": pb["lw_delta"],
                 "mean_score": float(np.mean(np.array(pb["score"])[T])), **port_stats(T, cov, rho),
                 "proxy_pick": mp["pick"], "proxy_pick_G_mv": energy(proxyT, lin, Q),
                 "proxy_mean_score": float(np.mean(np.array(pb["score"])[proxyT])),
                 **{f"proxy_{k}": v for k, v in port_stats(proxyT, cov, rho).items()},
                 "overlap_with_proxy": len(set(T) & set(proxyT))}
            out[f"N{N}_g{g}"] = r
            print(f"N={N:3d} gamma={g:2d}  MILP {r['G']:+.6f} (bound {r['dual_bound']:+.6f}, {r['nodes']} nodes, "
                  f"{r['seconds']:.1f}s) certified={r['certified']}  vol {r['vol']:.3f} (proxy {r['proxy_vol']:.3f})  "
                  f"score {r['mean_score']:.3f} (proxy {r['proxy_mean_score']:.3f})  overlap {r['overlap_with_proxy']}/6  "
                  f"{r['pick']}", flush=True)
    json.dump(out, open(os.path.join(HERE, "mv_result.json"), "w"), indent=1)


DEG = 3


def variant(lin, Q, k=K, deg=DEG):
    """PADO variant of build.py applied to a (lin, Q) pair: step 1 (exact on sum x = k) moves the
    least-squares additive fit Q_ij ~ c + a_i + a_j into the linear term, d = lin + (k - 1) a;
    step 2 keeps residual pairs by |R| while both ends have degree < deg (no cap term here)."""
    n = len(lin); iu = np.triu_indices(n, 1)
    A = np.zeros((len(iu[0]), n + 1)); A[:, 0] = 1.0
    A[np.arange(len(iu[0])), 1 + iu[0]] = 1.0; A[np.arange(len(iu[0])), 1 + iu[1]] = 1.0
    coef = np.linalg.lstsq(A, Q[iu], rcond=None)[0]
    c, a = float(coef[0]), coef[1:]
    R = Q - c - a[:, None] - a[None, :]; np.fill_diagonal(R, 0.0)
    d = lin + (k - 1) * a
    degc = np.zeros(n, int); kept = []
    for i, j in sorted(zip(*iu), key=lambda e: -abs(R[e])):
        if degc[i] < deg and degc[j] < deg:
            kept.append((int(i), int(j), float(R[i, j]))); degc[i] += 1; degc[j] += 1
    Rk = np.zeros((n, n))
    for i, j, v in kept:
        Rk[i, j] = Rk[j, i] = v
    h0 = -d / 2.0 - Rk.sum(1) / 4.0
    J = [(i, j, v / 4.0) for i, j, v in kept]
    var_expl = float(1 - (R[iu] ** 2).sum() / ((Q[iu] - Q[iu].mean()) ** 2).sum())
    kept_share = float(sum(abs(v) for *_, v in kept) / np.abs(R[iu]).sum())
    return {"d": d.tolist(), "R_kept": kept, "h0": h0.tolist(), "J": J, "fit_c": c,
            "Q_var_explained_by_fit": var_expl, "R_abs_kept_share": kept_share}


def cmd_variant():
    """mv_variant_<N>_g<gamma>.json, and how good the variant's k=6 optimum is on the full objective."""
    out = json.load(open(os.path.join(HERE, "mv_result.json")))
    for N in (50, 100, 150):
        for g in GAMMAS:
            pb = json.load(open(os.path.join(HERE, f"mv_problem_{N}_g{g}.json")))
            lin, Q, syms = np.array(pb["lin"]), np.array(pb["Q"]), pb["syms"]
            v = variant(lin, Q)
            v.update(syms=syms, k=K, gamma=g, N=N)
            json.dump(v, open(os.path.join(HERE, f"mv_variant_{N}_g{g}.json"), "w"))
            d = np.array(v["d"]); Rk = np.zeros((N, N))
            for i, j, x in v["R_kept"]:
                Rk[i, j] = Rk[j, i] = x
            s = solve(d, Rk, K); T = s["T"]
            full = out[f"N{N}_g{g}"]; Topt = [syms.index(u) for u in full["pick"]]
            # rank of the variant's pick on the full objective among all k-subsets is not enumerable;
            # report its gap to the certified full optimum and the overlap
            Gv = energy(T, lin, Q)
            r = {"variant_pick": [syms[i] for i in T], "variant_certified": s["certified"], "variant_pick_G_full": Gv,
                 "full_opt_G": full["G"], "rel_gap_full": (Gv - full["G"]) / abs(full["G"]),
                 "overlap_with_full_opt": len(set(T) & set(Topt)), "Q_var_explained_by_fit": v["Q_var_explained_by_fit"],
                 "R_abs_kept_share": v["R_abs_kept_share"]}
            full["variant"] = r
            print(f"N={N:3d} gamma={g:2d}  fit explains {r['Q_var_explained_by_fit']:.1%} of pair variance, kept |R| share "
                  f"{r['R_abs_kept_share']:.1%}  variant optimum == full optimum: {r['overlap_with_full_opt'] == K}  "
                  f"(overlap {r['overlap_with_full_opt']}/6, full-objective gap {r['rel_gap_full']:.1e})", flush=True)
    json.dump(out, open(os.path.join(HERE, "mv_result.json"), "w"), indent=1)


if __name__ == "__main__":
    {"build": cmd_build, "variant": cmd_variant}[sys.argv[1]]()
