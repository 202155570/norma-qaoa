"""Exploratory comparison of the selection objectives with classical portfolio models.
Same data and rules as bt.py / cand.py: prices10.json (148 ETFs), month-end rebalance (108 times,
2017-11 -> 2026-11), weights set from data up to the rebalance day only, held with drift to the next
month-end, 10 bp per side on traded weight, Sharpe of excess returns over BIL.
NOT pre-registered: the confirmation and validation windows of cand_prereg.md / oos_prereg.md were
already spent; this is a description, not a test.

Inputs each month (as cand.month_inputs): S = rank of the mean 63/126/252-day return; Sigma =
Ledoit-Wolf (constant correlation) covariance of the last 126 daily log returns, x 252; mu = mean of
the last 252 daily simple returns x 252 (only for max-Sharpe).

Ours (6 ETFs, equal weight; the portfolios RQAOA / MILP / local search reach when they find the optimum):
  proxy6      the proxy objective (bt.py "maiq")
  mv6_g4/12   mean-variance with k = 6 (cand.py C2_mv4 / C2_mv12)
Classical, long-only, continuous weights over all 148 ETFs:
  minvar      min w' Sigma w
  mv_g4/12    max S'w - gamma w' Sigma w (the continuous counterpart of mv6)
  maxsharpe   max (mu - rf)'w / sqrt(w' Sigma w)   (rf = BIL's mean over the same window)
  erc         equal risk contribution (Spinu's convex form)
  hrp         hierarchical risk parity (Lopez de Prado 2016: single linkage on sqrt((1 - rho)/2),
              quasi-diagonal order, recursive bisection with inverse-variance cluster weights)
  invvol      weights proportional to 1 / volatility
  equal       1/146 each;  spy  SPY
The classical models invest in the 146 non-cash ETFs: BIL and SHV (T-bill ETFs, volatility 0.3%) are
left out, otherwise minvar and hrp put nearly everything in T-bills and their excess return over
BIL is noise around zero. The 6-ETF objectives keep the full 148 (as bt.py); how often they hold
BIL or SHV is reported.
argv: run   writes models_result.json and prints the table
"""

import json
import math
import os
import sys
import time

import numpy as np
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.optimize import minimize
from scipy.spatial.distance import squareform

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bt import block_boot_idx, mdd, sharpe  # noqa: E402
from cand import K, SPEC, hold_w, month_inputs, pick, weights  # noqa: E402

OURS = {"proxy6": "base", "mv6_g4": "C2_mv4", "mv6_g12": "C2_mv12"}
CASH = ("BIL", "SHV")
CLASSICAL = ["minvar", "mv_g4", "mv_g12", "maxsharpe", "erc", "hrp", "invvol", "equal"]


def qp_simplex(f, n, w0=None):
    """min f(w) over the simplex (w >= 0, sum w = 1); f returns (value, gradient)."""
    w0 = np.full(n, 1.0 / n) if w0 is None else w0
    r = minimize(f, w0, jac=True, method="SLSQP", bounds=[(0.0, 1.0)] * n,
                 constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1.0, "jac": lambda w: np.ones(n)}],
                 options={"maxiter": 500, "ftol": 1e-12})
    w = np.clip(r.x, 0.0, None)
    return w / w.sum()


def erc(C):
    """Spinu (2013): min 1/2 y'Cy - (1/n) sum log y, y > 0; w = y / sum y has equal risk contributions."""
    n = len(C); b = np.full(n, 1.0 / n)
    f = lambda y: (0.5 * y @ C @ y - b @ np.log(y), C @ y - b / y)
    r = minimize(f, np.full(n, 1.0 / np.sqrt(np.diag(C)).sum()), jac=True, method="L-BFGS-B",
                 bounds=[(1e-12, None)] * n, options={"maxiter": 2000, "gtol": 1e-12})
    return r.x / r.x.sum()


def hrp(C):
    sd = np.sqrt(np.diag(C)); rho = C / np.outer(sd, sd)
    D = np.sqrt(np.clip((1.0 - rho) / 2.0, 0.0, None)); np.fill_diagonal(D, 0.0)
    order = leaves_list(linkage(squareform(D, checks=False), "single"))
    w = np.ones(len(C)); clusters = [list(order)]
    while clusters:
        nxt = []
        for c in clusters:
            if len(c) < 2:
                continue
            a, b = c[: len(c) // 2], c[len(c) // 2:]
            var = []
            for s in (a, b):
                iv = 1.0 / np.diag(C)[s]; iv /= iv.sum()
                var.append(iv @ C[np.ix_(s, s)] @ iv)
            alpha = 1.0 - var[0] / (var[0] + var[1])
            w[a] *= alpha; w[b] *= 1.0 - alpha
            nxt += [a, b]
        clusters = nxt
    return w / w.sum()


def classical_weights(m, inp, mu, rf, prev):
    C = inp["cov"]; S = inp["S"]["orig"]; n = len(S)
    if m == "minvar":
        return qp_simplex(lambda w: (w @ C @ w, 2 * C @ w), n, prev.get(m))
    if m.startswith("mv_g"):
        g = float(m[4:])
        return qp_simplex(lambda w: (-S @ w + g * w @ C @ w, -S + 2 * g * C @ w), n, prev.get(m))
    if m == "maxsharpe":
        ex = mu - rf
        if (ex <= 0).all():                                   # no asset above the risk-free rate: hold BIL-like minvar
            return qp_simplex(lambda w: (w @ C @ w, 2 * C @ w), n, prev.get(m))

        def f(w):
            v = w @ C @ w; s = np.sqrt(v); e = ex @ w
            return -e / s, -(ex / s - e * (C @ w) / s ** 3)
        return qp_simplex(f, n, prev.get(m))
    if m == "erc":
        return erc(C)
    if m == "hrp":
        return hrp(C)
    if m == "invvol":
        v = 1.0 / inp["vol"]; return v / v.sum()
    if m == "equal":
        return np.full(n, 1.0 / n)
    raise KeyError(m)


def cmd_run():
    px = json.load(open(os.path.join(HERE, "prices10.json")))
    syms, dates = px["syms"], px["dates"]
    P = np.array(px["prices"]).T; n = P.shape[1]
    bil, spy = syms.index("BIL"), syms.index("SPY")
    month = [d[:7] for d in dates]
    reb = [t for t in range(len(dates) - 1) if month[t] != month[t + 1] and t >= 253] + [len(dates) - 1]
    names = list(OURS) + CLASSICAL
    R = {m: [] for m in names}; turn = {m: [] for m in names}; wend = {m: np.zeros(n) for m in names}
    eff_n = {m: [] for m in names}; prev = {}; cash_w = {m: [] for m in names}
    cash = [syms.index(c) for c in CASH]; risky = np.array([i for i in range(n) if i not in cash])
    t0 = time.time()
    for x, (a, b) in enumerate(zip(reb[:-1], reb[1:])):
        H = P[: a + 1]; inp = month_inputs(H, bil); Pf = P[a: b + 1]
        r1 = H[-252:] / H[-253:-1] - 1.0
        mu = r1.mean(0) * 252; rf = float(r1[:, bil].mean() * 252)
        for m in names:
            if m in OURS:
                i = list(SPEC).index(OURS[m])
                T, fill = pick(inp, SPEC[OURS[m]], np.random.default_rng([5, x, i]))
                w = weights(n, T, fill, inp["vol"], False, bil)
            else:
                sub = {"cov": inp["cov"][np.ix_(risky, risky)], "S": {"orig": inp["S"]["orig"][risky]}, "vol": inp["vol"][risky]}
                ws = classical_weights(m, sub, mu[risky], rf, prev); prev[m] = ws
                w = np.zeros(n); w[risky] = ws
            cash_w[m].append(float(w[cash].sum()))
            eff_n[m].append(float(1.0 / (w ** 2).sum()))
            r, tv, wend[m] = hold_w(Pf, w, wend[m]); R[m].append(r); turn[m].append(tv)
        if x % 12 == 0:
            print(f"{dates[a]}  [{time.time() - t0:.0f}s]", flush=True)
    R = {m: np.concatenate(v) for m, v in R.items()}
    days = slice(reb[0] + 1, reb[-1] + 1)
    rfd = P[days, bil] / P[reb[0]: reb[-1], bil] - 1.0
    R["spy"] = P[days, spy] / P[reb[0]: reb[-1], spy] - 1.0
    yrs = len(rfd) / 252
    res = {"period": [dates[reb[0]], dates[reb[-1]]], "rebalances": len(reb) - 1, "n_etfs": n,
           "data_sha256": px["sha256"], "preregistered": False, "methods": {}}
    for m, r in R.items():
        res["methods"][m] = {"ann_return": float(np.prod(1 + r) ** (1 / yrs) - 1), "ann_vol": float(r.std(ddof=1) * math.sqrt(252)),
                             "sharpe": sharpe(r - rfd), "max_drawdown": mdd(r),
                             "turnover_per_year": float(sum(turn[m]) / yrs) if m in turn else None,
                             "effective_n_median": float(np.median(eff_n[m])) if m in eff_n else None,
                             "mean_cash_weight": float(np.mean(cash_w[m])) if m in cash_w else None}
    # Sharpe differences vs proxy6 and mv6_g4 (stationary block bootstrap, as bt.py)
    ex = {m: r - rfd for m, r in R.items()}
    rng = np.random.default_rng(11); B = 2000
    pairs = [(c, o) for o in ("proxy6", "mv6_g4") for c in CLASSICAL + ["spy"] + [q for q in OURS if q != o]]
    d = {p: [] for p in pairs}
    for _ in range(B):
        idx = block_boot_idx(len(rfd), rng)
        sh = {m: sharpe(ex[m][idx]) for m in ex}
        for p in pairs:
            d[p].append(sh[p[0]] - sh[p[1]])
    res["sharpe_diff"] = {f"{a}-{b}": {"point": sharpe(ex[a]) - sharpe(ex[b]),
                                      "ci95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]}
                         for (a, b), v in d.items()}
    json.dump(res, open(os.path.join(HERE, "models_result.json"), "w"), indent=1)
    print(f"\n{res['period'][0]} -> {res['period'][1]}, {res['rebalances']} rebalances, {n} ETFs")
    print(f"{'model':10s} {'return':>7s} {'vol':>6s} {'Sharpe':>7s} {'MDD':>7s} {'turn/yr':>8s} {'eff N':>6s} {'cash':>5s}")
    for m, v in res["methods"].items():
        print(f"{m:10s} {v['ann_return']:7.1%} {v['ann_vol']:6.1%} {v['sharpe']:7.3f} {v['max_drawdown']:7.1%} "
              f"{'' if v['turnover_per_year'] is None else format(v['turnover_per_year'], '8.2f'):>8s} "
              f"{'' if v['effective_n_median'] is None else format(v['effective_n_median'], '6.1f'):>6s} "
              f"{'' if v['mean_cash_weight'] is None else format(v['mean_cash_weight'], '5.1%'):>5s}")
    for k, v in res["sharpe_diff"].items():
        print(f"  {k:20s} {v['point']:+.3f} [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]")


if __name__ == "__main__":
    {"run": cmd_run}[sys.argv[1]]()
