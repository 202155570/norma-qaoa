"""Walk-forward backtest of selection objectives, 148 ETFs, 10 years, monthly, k = 6.

At each month-end t (once 253 days of history exist) every objective is rebuilt from data up
to and including t only, its best 6 are bought equal-weight at the close of t and held (weights
drift) to the next month-end. 10 bp per side on traded weight.

Objectives (classical optimum by steepest-swap local search, greedy start + 30 random restarts):
  maiq     original: -WS s_i on the diagonal, WC max(rho,0) + WCAP [rho > 0.70] on pairs
  pado     variant:  additive fit c + a_i + a_j moved to the diagonal (exact on |S| = 6),
                     residual kept on a degree-3 sparse graph (cap pairs first, then |R|)
  cluster  pado + at most one ETF per correlation cluster (average linkage on 1 - rho, cut 0.30)
  score    the 6 highest scores
  random   6 uniformly at random each month (200 independent paths)
  equal    all 148 equal weight
Reference: SPY. Excess returns over BIL (T-bill ETF, in the universe).
Sharpe CIs: stationary block bootstrap of paired daily excess returns, mean block 21 days,
2000 resamples, seed 11.

argv: run            writes bt_daily.npz and bt_result.json
      selftest       local search vs exhaustive optimum on problem_50.json
"""

import json
import math
import os
import sys
import time

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import rankdata

HERE = os.path.dirname(os.path.abspath(__file__))
WS, WC, WCAP, RHO_CAP, K, DEG = 1.0, 0.5, 2.0, 0.70, 6, 3
COST = 0.001


def local_search(lin, Q, rng, clusters=None, restarts=30):
    n = len(lin)

    def feasible_random():
        if clusters is None:
            return list(rng.choice(n, K, replace=False))
        T, used = [], set()
        for u in rng.permutation(n):
            if clusters[u] not in used:
                T.append(int(u)); used.add(clusters[u])
                if len(T) == K:
                    return T

    def greedy():
        T = []
        while len(T) < K:
            g = lin + (Q[:, T].sum(1) if T else 0.0)
            g[T] = np.inf
            if clusters is not None and T:
                g[np.isin(clusters, clusters[T])] = np.inf
            T.append(int(np.argmin(g)))
        return T

    def energy(T):
        return float(lin[T].sum() + Q[np.ix_(T, T)][np.triu_indices(K, 1)].sum())

    best = (np.inf, None)
    for start in [greedy()] + [feasible_random() for _ in range(restarts)]:
        T = list(start)
        while True:
            QT = Q[:, T]
            tot = QT.sum(1)
            cand = lin[:, None] + tot[:, None] - QT                    # cost of u replacing T[a]
            cur = np.array([lin[T[a]] + tot[T[a]] - QT[T[a], a] for a in range(K)])
            delta = cand - cur[None, :]
            delta[T, :] = np.inf
            if clusters is not None:
                for a in range(K):
                    rest = [T[b] for b in range(K) if b != a]
                    delta[np.isin(clusters, clusters[rest]), a] = np.inf
            u, a = np.unravel_index(np.argmin(delta), delta.shape)
            if delta[u, a] >= -1e-12:
                break
            T[a] = int(u)
        e = energy(T)
        if e < best[0]:
            best = (e, sorted(T))
    return best


def objectives(P, rng):
    """P: price history up to and including the rebalance day (T x n)."""
    n = P.shape[1]
    ret = [P[-1] / P[-1 - d] - 1.0 for d in (63, 126, 252)]
    S = (rankdata(sum(ret) / 3.0, method="average") - 1.0) / (n - 1)
    rho = np.corrcoef(np.diff(np.log(P[-127:]), axis=0).T)
    Q = WC * np.maximum(rho, 0.0) + WCAP * (rho > RHO_CAP)
    np.fill_diagonal(Q, 0.0)
    lin = -WS * S
    iu = np.triu_indices(n, 1)
    A = np.zeros((len(iu[0]), n + 1)); A[:, 0] = 1.0
    A[np.arange(len(iu[0])), 1 + iu[0]] = 1.0; A[np.arange(len(iu[0])), 1 + iu[1]] = 1.0
    coef = np.linalg.lstsq(A, Q[iu], rcond=None)[0]
    a = coef[1:]
    R = Q - coef[0] - a[:, None] - a[None, :]
    d = lin + (K - 1) * a
    Rs = np.zeros_like(R); deg = np.zeros(n, int)
    for i, j in sorted(zip(*iu), key=lambda e: (not rho[e] > RHO_CAP, -abs(R[e]))):
        if deg[i] < DEG and deg[j] < DEG:
            Rs[i, j] = Rs[j, i] = R[i, j]; deg[i] += 1; deg[j] += 1
    D = np.clip(1.0 - rho, 0.0, None); np.fill_diagonal(D, 0.0)
    cl = fcluster(linkage(squareform(D, checks=False), "average"), t=1.0 - RHO_CAP, criterion="distance")
    picks = {"maiq": local_search(lin, Q, rng)[1],
             "pado": local_search(d, Rs, rng)[1],
             "cluster": local_search(d, Rs, rng, clusters=cl)[1],
             "score": sorted(np.argsort(-S)[:K].tolist())}
    avg_rho = {m: float(np.mean([rho[i, j] for x, i in enumerate(T) for j in T[x + 1:]])) for m, T in picks.items()}
    return picks, avg_rho, int(cl.max())


def hold(Pf, T, w_prev_end):
    """Equal weight in T at row 0 of Pf, drift to the last row. Returns daily returns (len-1),
    the traded turnover at row 0, and the drifted end weights."""
    n = Pf.shape[1]
    w0 = np.zeros(n); w0[T] = 1.0 / len(T)
    turnover = np.abs(w0 - w_prev_end).sum()
    growth = Pf / Pf[0]
    V = growth @ w0
    r = V[1:] / V[:-1] - 1.0
    r[0] -= COST * turnover
    w_end = w0 * growth[-1] / V[-1]
    return r, turnover, w_end


def sharpe(x):
    return float(x.mean() / x.std(ddof=1) * math.sqrt(252))


def mdd(r):
    v = np.cumprod(1 + r)
    return float((v / np.maximum.accumulate(v) - 1).min())


def block_boot_idx(T, rng, mean_block=21):
    idx = np.empty(T, int); i = 0
    while i < T:
        s = rng.integers(T); L = rng.geometric(1 / mean_block)
        take = min(L, T - i)
        idx[i:i + take] = (s + np.arange(take)) % T; i += take
    return idx


if __name__ == "__main__":
    if sys.argv[1] == "selftest":
        pb = json.load(open(os.path.join(HERE, "problem_50.json")))
        e, T = local_search(np.array(pb["lin"]), np.array(pb["Q"]), np.random.default_rng(0))
        r = json.load(open(os.path.join(HERE, "rank_50.json")))
        print(f"local search {e:+.6f} {[pb['syms'][i] for i in T]}   exhaustive {r['original_opt_G']:+.6f} {r['original_opt']}")
        assert abs(e - r["original_opt_G"]) < 1e-9
        print("selftest PASS"); sys.exit()

    px = json.load(open(os.path.join(HERE, "prices10.json")))
    syms, dates = px["syms"], px["dates"]
    P = np.array(px["prices"]).T
    n = P.shape[1]
    bil, spy = syms.index("BIL"), syms.index("SPY")
    month = [d[:7] for d in dates]
    reb = [t for t in range(len(dates) - 1) if month[t] != month[t + 1] and t >= 253]
    reb.append(len(dates) - 1)
    rng = np.random.default_rng(5)
    methods = ["maiq", "pado", "cluster", "score", "equal"]
    R = {m: [] for m in methods}; turn = {m: [] for m in methods}; wend = {m: np.zeros(n) for m in methods}
    NR = 200
    Rr = [[] for _ in range(NR)]; wr = [np.zeros(n) for _ in range(NR)]
    rho_log = {m: [] for m in ["maiq", "pado", "cluster", "score"]}; hold_log = []; ncl = []
    t0 = time.time()
    for a, b in zip(reb[:-1], reb[1:]):
        picks, avg_rho, nc = objectives(P[: a + 1], rng)
        picks["equal"] = list(range(n))
        Pf = P[a: b + 1]
        for m in methods:
            r, tv, wend[m] = hold(Pf, picks[m], wend[m]); R[m].append(r); turn[m].append(tv)
        for x in range(NR):
            r, _, wr[x] = hold(Pf, sorted(rng.choice(n, K, replace=False).tolist()), wr[x]); Rr[x].append(r)
        for m in rho_log:
            rho_log[m].append(avg_rho[m])
        ncl.append(nc)
        hold_log.append({"date": dates[a], **{m: [syms[i] for i in picks[m]] for m in ["maiq", "pado", "cluster", "score"]}})
    R = {m: np.concatenate(v) for m, v in R.items()}
    Rr = np.array([np.concatenate(v) for v in Rr])
    days = slice(reb[0] + 1, reb[-1] + 1)
    rf = P[days, bil] / P[reb[0]: reb[-1], bil] - 1.0
    spy_r = P[days, spy] / P[reb[0]: reb[-1], spy] - 1.0
    R["spy"] = spy_r
    ex = {m: v - rf for m, v in R.items()}
    exr = Rr - rf[None, :]
    yrs = len(rf) / 252
    rand_sh = np.array([sharpe(x) for x in exr])
    res = {"period": [dates[reb[0]], dates[reb[-1]]], "rebalances": len(reb) - 1, "n_etfs": n,
           "data_sha256": px["sha256"], "clusters_median": float(np.median(ncl)), "methods": {}}
    for m, r in R.items():
        res["methods"][m] = {"ann_return": float(np.prod(1 + r) ** (1 / yrs) - 1), "ann_vol": float(r.std(ddof=1) * math.sqrt(252)),
                             "sharpe": sharpe(ex[m]), "max_drawdown": mdd(r),
                             "turnover_per_year": float(sum(turn[m]) / yrs) if m in turn else None,
                             "avg_pair_rho": float(np.mean(rho_log[m])) if m in rho_log else None,
                             "sharpe_pct_vs_random": float((rand_sh < sharpe(ex[m])).mean())}
    res["random"] = {"sharpe_median": float(np.median(rand_sh)), "sharpe_p5": float(np.percentile(rand_sh, 5)),
                     "sharpe_p95": float(np.percentile(rand_sh, 95)), "paths": NR}
    brng = np.random.default_rng(11); B = 2000
    pairs = [("pado", "maiq"), ("cluster", "maiq"), ("cluster", "pado"), ("maiq", "score"), ("pado", "score"),
             ("cluster", "score"), ("maiq", "equal"), ("cluster", "equal"), ("maiq", "spy"), ("cluster", "spy")]
    diffs = {p: [] for p in pairs}
    for _ in range(B):
        idx = block_boot_idx(len(rf), brng)
        sh = {m: sharpe(ex[m][idx]) for m in ex}
        for p in pairs:
            diffs[p].append(sh[p[0]] - sh[p[1]])
    res["sharpe_diff"] = {f"{a}-{b}": {"point": res["methods"][a]["sharpe"] - res["methods"][b]["sharpe"],
                                       "ci95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))],
                                       "p_le_0": float(np.mean(np.array(v) <= 0))}
                          for (a, b), v in diffs.items()}
    res["seconds"] = round(time.time() - t0, 1)
    res["last_holdings"] = hold_log[-1]
    json.dump(res, open(os.path.join(HERE, "bt_result.json"), "w"), indent=1)
    json.dump(hold_log, open(os.path.join(HERE, "bt_holdings.json"), "w"))
    np.savez(os.path.join(HERE, "bt_daily.npz"), **R, rf=rf)
    print(json.dumps({k: res[k] for k in ("period", "rebalances", "n_etfs", "clusters_median", "random", "seconds")}))
    for m, v in res["methods"].items():
        print(f"{m:>8}  수익 {v['ann_return']:+.2%}  변동성 {v['ann_vol']:.2%}  샤프 {v['sharpe']:.3f}  MDD {v['max_drawdown']:.2%}"
              f"  회전 {v['turnover_per_year'] if v['turnover_per_year'] is None else round(v['turnover_per_year'], 2)}"
              f"  평균ρ {v['avg_pair_rho'] if v['avg_pair_rho'] is None else round(v['avg_pair_rho'], 3)}"
              f"  무작위 대비 백분위 {v['sharpe_pct_vs_random']:.2f}")
    for k_, v in res["sharpe_diff"].items():
        print(f"  샤프 차이 {k_:>16}: {v['point']:+.3f}  95% CI [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]")
