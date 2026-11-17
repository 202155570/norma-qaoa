"""Pre-registered comparison of literature-based changes to the MaiQ selection objective.
Everything about the candidates and the verdict is fixed in cand_prereg.md (written first).

Setup as bt.py: 148 ETFs, monthly, k = 6, 10 bp per side, optimum by bt.local_search.
Selection period: first 72 rebalances. Confirmation period: last 36, used once.

argv: selftest   shrinkage sanity check; base reproduces the MaiQ holdings of bt.py (first 72 months)
      train      first 72 rebalances only (prices after the split are never read)
      final      all 108, writes cand_result.json and cand_holdings.json
Run with python -I.
"""

import hashlib
import json
import math
import os
import sys
import time

import numpy as np
from scipy.stats import rankdata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)            # -I drops the script directory; bt.py is our own module
from bt import COST, K, RHO_CAP, WC, WCAP, WS, block_boot_idx, local_search, mdd, sharpe  # noqa: E402

SPLIT = 72
GAMMAS = (4, 12, 36)
# name: (signal, risk, trend filter, inverse-vol weights)
SPEC = {"base": ("orig", "orig", False, False),
        "C1_signal": ("m12_1", "orig", False, False),
        **{f"C2_mv{g}": ("orig", g, False, False) for g in GAMMAS},
        "C3_trend": ("orig", "orig", True, False),
        "C4_invvol": ("orig", "orig", False, True),
        **{f"all_mv{g}": ("m12_1", g, True, True) for g in GAMMAS},
        "score_only": None, "equal": None}
SINGLE = ["C1_signal"] + [f"C2_mv{g}" for g in GAMMAS] + ["C3_trend", "C4_invvol"]


def lw_const_corr(X):
    """Ledoit-Wolf (2004) shrinkage of the sample covariance towards the constant-correlation
    target. X: T x n returns. Returns (covariance, shrinkage intensity)."""
    T, n = X.shape
    x = X - X.mean(0)
    S = x.T @ x / T
    var = np.diag(S).copy(); sd = np.sqrt(var)
    rbar = ((S / np.outer(sd, sd)).sum() - n) / (n * (n - 1))
    F = rbar * np.outer(sd, sd); np.fill_diagonal(F, var)
    phi_m = (x ** 2).T @ (x ** 2) / T - S ** 2
    theta = (x ** 3).T @ x / T - var[:, None] * S
    np.fill_diagonal(theta, 0.0)
    rho = np.trace(phi_m) + rbar * ((sd[None, :] / sd[:, None]) * theta).sum()
    gamma = ((S - F) ** 2).sum()
    delta = max(0.0, min(1.0, (phi_m.sum() - rho) / gamma / T))
    return delta * F + (1.0 - delta) * S, delta


def hold_w(Pf, w0, w_prev_end):
    turnover = np.abs(w0 - w_prev_end).sum()
    growth = Pf / Pf[0]
    V = growth @ w0
    r = V[1:] / V[:-1] - 1.0
    r[0] -= COST * turnover
    return r, turnover, w0 * growth[-1] / V[-1]


def month_inputs(H, bil):
    n = H.shape[1]
    rank01 = lambda v: (rankdata(v, method="average") - 1.0) / (n - 1)
    lr = np.diff(np.log(H[-127:]), axis=0)
    rho = np.corrcoef(lr.T)
    Q0 = WC * np.maximum(rho, 0.0) + WCAP * (rho > RHO_CAP)
    np.fill_diagonal(Q0, 0.0)
    cov, delta = lw_const_corr(lr)
    r252 = H[-1] / H[-253] - 1.0
    return {"S": {"orig": rank01(sum(H[-1] / H[-1 - d] - 1.0 for d in (63, 126, 252)) / 3.0),
                  "m12_1": rank01(H[-22] / H[-253] - 1.0)},
            "Q0": Q0, "cov": cov * 252.0, "delta": delta, "vol": lr.std(0, ddof=1),
            "elig": np.where(r252 > r252[bil])[0]}


def pick(inp, spec, rng):
    """Returns (picked indices, number of slots filled with BIL)."""
    sig, risk, trend, _ = spec
    S = inp["S"][sig]; n = len(S)
    if risk == "orig":
        lin, Q = -WS * S, inp["Q0"]
    else:
        lin = -S / K + risk * np.diag(inp["cov"]) / K ** 2
        Q = 2.0 * risk * inp["cov"] / K ** 2
        Q = Q - np.diag(np.diag(Q))
    idx = inp["elig"] if trend else np.arange(n)
    if len(idx) <= K:
        return sorted(idx.tolist()), K - len(idx)
    T = local_search(lin[idx], Q[np.ix_(idx, idx)], rng)[1]
    return sorted(idx[T].tolist()), 0


def weights(n, T, fill, vol, inv, bil):
    w = np.zeros(n)
    w[bil] += fill / K
    if T:
        v = 1.0 / vol[T] if inv else np.ones(len(T))
        w[T] += (len(T) / K) * v / v.sum()
    return w


def run(P, dates, syms, n_periods):
    n = P.shape[1]
    bil, spy = syms.index("BIL"), syms.index("SPY")
    month = [d[:7] for d in dates]
    reb = [t for t in range(len(dates) - 1) if month[t] != month[t + 1] and t >= 253]
    reb.append(len(dates) - 1)
    reb = reb[: n_periods + 1]
    names = list(SPEC)
    R = {m: [] for m in names}; turn = {m: [] for m in names}; wend = {m: np.zeros(n) for m in names}
    fills = {m: 0 for m in names}; bil_w = {m: [] for m in names}; holdings = []; deltas = []; n_elig = []
    NR = 200; rrng = np.random.default_rng(7)
    Rr = [[] for _ in range(NR)]; wr = [np.zeros(n) for _ in range(NR)]
    for x, (a, b) in enumerate(zip(reb[:-1], reb[1:])):
        inp = month_inputs(P[: a + 1], bil); Pf = P[a: b + 1]
        deltas.append(inp["delta"]); n_elig.append(len(inp["elig"]))
        row = {"date": dates[a]}
        for i, m in enumerate(names):
            if m == "equal":
                w = np.full(n, 1.0 / n)
            elif m == "score_only":
                T = sorted(np.argsort(-inp["S"]["orig"])[:K].tolist()); row[m] = [syms[j] for j in T]
                w = weights(n, T, 0, inp["vol"], False, bil)
            else:
                T, fill = pick(inp, SPEC[m], np.random.default_rng([5, x, i]))
                fills[m] += fill; row[m] = [syms[j] for j in T]
                w = weights(n, T, fill, inp["vol"], SPEC[m][3], bil)
            bil_w[m].append(float(w[bil]))
            r, tv, wend[m] = hold_w(Pf, w, wend[m]); R[m].append(r); turn[m].append(tv)
        for y in range(NR):
            T = sorted(rrng.choice(n, K, replace=False).tolist())
            r, _, wr[y] = hold_w(Pf, weights(n, T, 0, inp["vol"], False, bil), wr[y]); Rr[y].append(r)
        holdings.append(row)
    R = {m: np.concatenate(v) for m, v in R.items()}
    days = slice(reb[0] + 1, reb[-1] + 1)
    rf = P[days, bil] / P[reb[0]: reb[-1], bil] - 1.0
    R["spy"] = P[days, spy] / P[reb[0]: reb[-1], spy] - 1.0
    return {"R": R, "Rr": np.array([np.concatenate(v) for v in Rr]), "rf": rf, "reb": reb, "turn": turn,
            "fills": fills, "bil_w": bil_w, "holdings": holdings, "deltas": deltas, "n_elig": n_elig}


def table(out, lo, hi, p_lo, p_hi):
    """Metrics on the day slice [lo, hi) (rebalance periods [p_lo, p_hi))."""
    rf = out["rf"][lo:hi]; yrs = (hi - lo) / 252
    rand = np.array([sharpe(v[lo:hi] - rf) for v in out["Rr"]])
    t = {}
    for m, r in out["R"].items():
        r = r[lo:hi]
        t[m] = {"ann_return": float(np.prod(1 + r) ** (1 / yrs) - 1), "ann_vol": float(r.std(ddof=1) * math.sqrt(252)),
                "sharpe": sharpe(r - rf), "max_drawdown": mdd(r), "sharpe_pct_vs_random": float((rand < sharpe(r - rf)).mean())}
        if m in out["turn"]:
            t[m]["turnover_per_year"] = float(sum(out["turn"][m][p_lo:p_hi]) / yrs)
            t[m]["mean_bil_weight"] = float(np.mean(out["bil_w"][m][p_lo:p_hi]))
    return t, {"sharpe_median": float(np.median(rand)), "sharpe_p5": float(np.percentile(rand, 5)),
               "sharpe_p95": float(np.percentile(rand, 95))}


def diff_ci(out, lo, hi, pairs, seed=11, B=2000):
    rf = out["rf"][lo:hi]; ex = {m: r[lo:hi] - rf for m, r in out["R"].items()}
    rng = np.random.default_rng(seed); d = {p: [] for p in pairs}
    for _ in range(B):
        idx = block_boot_idx(hi - lo, rng)
        sh = {m: sharpe(ex[m][idx]) for m in {q for p in pairs for q in p}}
        for p in pairs:
            d[p].append(sh[p[0]] - sh[p[1]])
    return {f"{a}-{b}": {"point": sharpe(ex[a]) - sharpe(ex[b]),
                         "ci95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]} for (a, b), v in d.items()}


def select(train):
    g = max(GAMMAS, key=lambda g: train[f"C2_mv{g}"]["sharpe"])
    cands = SINGLE + [f"all_mv{g}"]
    best = max(cands, key=lambda m: train[m]["sharpe"])
    return g, cands, best, bool(train[best]["sharpe"] > train["base"]["sharpe"])


def show(title, t, rand, names):
    print(title, " random-6 sharpe", json.dumps({k: round(v, 3) for k, v in rand.items()}))
    for m in names:
        v = t[m]
        print(f"  {m:>10}: ret {v['ann_return']:+.2%}  vol {v['ann_vol']:.2%}  sharpe {v['sharpe']:.3f}  mdd {v['max_drawdown']:.1%}"
              f"  turn {round(v.get('turnover_per_year', float('nan')), 1)}  BIL {v.get('mean_bil_weight', float('nan')):.2f}"
              f"  pct {v['sharpe_pct_vs_random']:.2f}")


if __name__ == "__main__":
    mode = sys.argv[1]
    px = json.load(open(os.path.join(HERE, "prices10.json")))
    syms, dates = px["syms"], px["dates"]
    P = np.array(px["prices"]).T

    if mode == "selftest":
        rng = np.random.default_rng(0); n, T = 148, 126
        sd = rng.uniform(0.002, 0.03, n); B = rng.normal(0, 1, (n, 3)) * 0.4
        C = B @ B.T + np.diag(rng.uniform(0.3, 1.0, n)); C /= np.sqrt(np.outer(np.diag(C), np.diag(C)))
        true = C * np.outer(sd, sd); L = np.linalg.cholesky(true)
        e_s, e_l, dl = [], [], []
        for _ in range(20):
            X = rng.normal(0, 1, (T, n)) @ L.T
            est, d = lw_const_corr(X); x = X - X.mean(0)
            e_s.append(np.linalg.norm(x.T @ x / T - true)); e_l.append(np.linalg.norm(est - true)); dl.append(d)
        print(f"shrinkage: Frobenius error sample {np.mean(e_s):.3e}  shrunk {np.mean(e_l):.3e}  delta {np.mean(dl):.3f}")
        assert np.mean(e_l) < np.mean(e_s) and 0.0 < np.mean(dl) < 1.0
        est, d = lw_const_corr(X)
        assert np.allclose(est, est.T) and np.linalg.eigvalsh(est).min() > 0
        split_row = [t for t in range(len(dates) - 1) if dates[t][:7] != dates[t + 1][:7] and t >= 253][SPLIT]
        out = run(P[: split_row + 1], dates[: split_row + 1], syms, SPLIT)
        oh = json.load(open(os.path.join(HERE, "bt_holdings.json")))[:SPLIT]
        same = sum(h["base"] == o["maiq"] for h, o in zip(out["holdings"], oh))
        same_s = sum(h["score_only"] == o["score"] for h, o in zip(out["holdings"], oh))
        print(f"base = bt.py maiq holdings in {same}/{SPLIT} months; score_only = bt.py score in {same_s}/{SPLIT}")
        assert same == SPLIT and same_s == SPLIT
        print("selftest PASS"); sys.exit()

    t0 = time.time()
    names = ["base"] + SINGLE + [f"all_mv{g}" for g in GAMMAS] + ["score_only", "equal", "spy"]
    if mode == "train":
        split_row = [t for t in range(len(dates) - 1) if dates[t][:7] != dates[t + 1][:7] and t >= 253][SPLIT]
        out = run(P[: split_row + 1], dates[: split_row + 1], syms, SPLIT)      # nothing after the split is passed in
        tr, rand = table(out, 0, len(out["rf"]), 0, SPLIT)
        g, cands, best, better = select(tr)
        show(f"TRAIN {dates[out['reb'][0]]} -> {dates[out['reb'][-1]]}", tr, rand, names)
        print("  BIL-filled slots", {m: v for m, v in out["fills"].items() if v}, " eligible min/median",
              min(out["n_elig"]), float(np.median(out["n_elig"])), " shrinkage mean", round(float(np.mean(out["deltas"])), 3))
        print(f"  gamma* = {g}; candidates {cands}; selected {best}; beats base on train: {better}")
        for k, v in diff_ci(out, 0, len(out["rf"]), [(m, "base") for m in cands]).items():
            print(f"  train diff {k:>16}: {v['point']:+.3f}  CI [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]")
        print("seconds", round(time.time() - t0, 1)); sys.exit()

    assert mode == "final"
    out = run(P, dates, syms, 10 ** 6)
    reb = out["reb"]; cut = reb[SPLIT] - reb[0]; N = len(out["rf"])
    tr, rand_tr = table(out, 0, cut, 0, SPLIT)
    te, rand_te = table(out, cut, N, SPLIT, len(reb) - 1)
    g, cands, best, better = select(tr)
    pairs = [(m, "base") for m in cands] + [(best, "equal"), ("base", "equal")]
    d_tr = diff_ci(out, 0, cut, pairs); d_te = diff_ci(out, cut, N, pairs)
    D = d_te[f"{best}-base"]
    verdict = ("no candidate" if not better else "confirmed" if D["point"] > 0 and D["ci95"][0] > 0
               else "same direction, not confirmed" if D["point"] > 0 else "rejected")
    res = {"prereg_sha256": hashlib.sha256(open(os.path.join(HERE, "cand_prereg.md"), "rb").read()).hexdigest(),
           "data_sha256": px["sha256"], "versions": {"python": sys.version.split()[0], "numpy": np.__version__},
           "train_period": [dates[reb[0]], dates[reb[SPLIT]]], "test_period": [dates[reb[SPLIT]], dates[reb[-1]]],
           "gamma_star": g, "candidates": cands, "selected": best, "selected_beats_base_on_train": better,
           "verdict": verdict, "train": tr, "test": te, "random_train": rand_tr, "random_test": rand_te,
           "sharpe_diff_train": d_tr, "sharpe_diff_test": d_te,
           "bil_filled_slots": out["fills"], "eligible_min": min(out["n_elig"]), "eligible_median": float(np.median(out["n_elig"])),
           "shrinkage_mean": float(np.mean(out["deltas"])), "seconds": round(time.time() - t0, 1)}
    json.dump(res, open(os.path.join(HERE, "cand_result.json"), "w"), indent=1)
    json.dump(out["holdings"], open(os.path.join(HERE, "cand_holdings.json"), "w"))
    show(f"TRAIN {res['train_period']}", tr, rand_tr, names)
    show(f"TEST  {res['test_period']}", te, rand_te, names)
    print(f"gamma* = {g}; selected {best}; beats base on train: {better}")
    for k in d_te:
        print(f"  diff {k:>16}: train {d_tr[k]['point']:+.3f} [{d_tr[k]['ci95'][0]:+.3f}, {d_tr[k]['ci95'][1]:+.3f}]"
              f"   test {d_te[k]['point']:+.3f} [{d_te[k]['ci95'][0]:+.3f}, {d_te[k]['ci95'][1]:+.3f}]")
    print("VERDICT:", verdict, " seconds", res["seconds"])
