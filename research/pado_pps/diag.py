"""Diagnosis of the MaiQ selection objective on the walk-forward setup of bt.py
(148 ETFs, 10 years, monthly, k = 6, 10 bp per side). Nothing here selects a new objective.

A. Score: does it predict the next holding period?
   rank IC (Spearman) of the score and of its three return horizons with the next-period
   return, score quintile portfolios (equal weight, no cost), top-6 minus universe mean.
   Asset-class equal-weight portfolios (no cost) for reference.
B. Correlation: does the trailing 126-day correlation predict the next period's?
   Spearman over pairs, and how often a pair above the 0.70 cap stays above it.
C. Term ablation, each solved by bt.local_search and held like bt.py:
     full        -WS s + WC max(rho,0) + WCAP [rho > 0.70]     (the MaiQ objective)
     no_cap      -WS s + WC max(rho,0)
     no_corr     -WS s + WCAP [rho > 0.70]
     no_score     WC max(rho,0) + WCAP [rho > 0.70]
     score_only  the 6 highest scores
   The cap term alone is not run: almost every 6-set has zero cost, so its optimum is arbitrary.

Split: first 72 rebalances / last 36, reported side by side (stability, not a hold-out).
The last holding period is a 1-day stub (2026-10-30 -> 11-02): it stays in the return paths,
as in bt.py, and is left out of the per-month statistics of A and B.
argv: run     writes diag_result.json     (python -I diag.py run)
"""

import json
import math
import os
import sys
import time

import numpy as np
from scipy.stats import rankdata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)            # -I drops the script directory; bt.py is our own module
from bt import K, RHO_CAP, WC, WCAP, WS, block_boot_idx, hold, local_search, mdd, sharpe  # noqa: E402

SPLIT = 72
REIT = {"VNQ", "IYR", "VNQI", "REM", "SCHH"}
VARIANTS = ["full", "no_cap", "no_corr", "no_score", "score_only"]
CLASSES = ["equity", "bond", "commodity", "reit", "currency"]


def class_of(syms):
    t = json.load(open(os.path.join(HERE, "tickers.json")))
    broad = {"bond": "bond", "real": "commodity", "real_commod": "commodity", "currency": "currency"}
    m = {s: "equity" for s in t["spare"]}
    for part in (t["groups"], t["added"]):
        for g, lst in part.items():
            for s in lst:
                m[s] = "reit" if s in REIT else broad.get(g, "equity")
    return [m[s] for s in syms]


def spearman(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    return float(np.corrcoef(rankdata(a[ok]), rankdata(b[ok]))[0, 1])


def series_stats(v, brng, block=3):
    v = np.asarray(v, float); T = len(v)
    boots = [v[block_boot_idx(T, brng, block)].mean() for _ in range(2000)]
    return {"mean": float(v.mean()), "t": float(v.mean() / (v.std(ddof=1) / math.sqrt(T))),
            "share_positive": float((v > 0).mean()),
            "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "first": float(v[:SPLIT].mean()), "last": float(v[SPLIT:].mean()), "months": T}


def ew_path(Pf, T):
    V = (Pf[:, T] / Pf[0, T]).mean(1)
    return V[1:] / V[:-1] - 1.0


def pair_mean(M, T):
    return float(np.mean([M[i, j] for x, i in enumerate(T) for j in T[x + 1:]]))


if __name__ == "__main__":
    assert sys.argv[1] == "run"
    px = json.load(open(os.path.join(HERE, "prices10.json")))
    syms, dates = px["syms"], px["dates"]
    P = np.array(px["prices"]).T
    n = P.shape[1]
    cls = np.array(class_of(syms))
    bil, spy = syms.index("BIL"), syms.index("SPY")
    month = [d[:7] for d in dates]
    reb = [t for t in range(len(dates) - 1) if month[t] != month[t + 1] and t >= 253]
    reb.append(len(dates) - 1)
    iu = np.triu_indices(n, 1)

    ic = {k: [] for k in ("score", "r63", "r126", "r252")}
    score_vol = []; top6_excess = []; q_fwd = []; Rq = [[] for _ in range(5)]
    rho_ic = []; keep = []; base = []; rho_ic63 = []; keep63 = []; base63 = []
    R = {m: [] for m in VARIANTS + ["equal"]}; turn = {m: [] for m in R}; wend = {m: np.zeros(n) for m in R}
    est_rho = {m: [] for m in VARIANTS}; real_rho = {m: [] for m in VARIANTS}; mean_s = {m: [] for m in VARIANTS}
    mix = {m: {c: 0 for c in CLASSES} for m in VARIANTS}; holdings = []
    pick_vol = {m: [] for m in VARIANTS}; univ_vol = []; Rc = {c: [] for c in CLASSES}
    NR = 200; rrng = np.random.default_rng(7)
    Rr = [[] for _ in range(NR)]; wr = [np.zeros(n) for _ in range(NR)]
    t0 = time.time()
    for x, (a, b) in enumerate(zip(reb[:-1], reb[1:])):
        H = P[: a + 1]; Pf = P[a: b + 1]
        r3 = [H[-1] / H[-1 - d] - 1.0 for d in (63, 126, 252)]
        S = (rankdata(sum(r3) / 3.0, method="average") - 1.0) / (n - 1)
        lr = np.diff(np.log(H[-127:]), axis=0)
        rho = np.corrcoef(lr.T)
        fwd = P[b] / P[a] - 1.0
        vol = lr.std(0, ddof=1) * math.sqrt(252); univ_vol.append(float(np.median(vol)))
        full_month = b - a >= 10
        # A
        top = np.argsort(-S)[:K]
        q = np.minimum((S * 5).astype(int), 4)
        if full_month:
            ic["score"].append(spearman(S, fwd))
            for name, v in zip(("r63", "r126", "r252"), r3):
                ic[name].append(spearman(v, fwd))
            score_vol.append(spearman(S, vol))
            top6_excess.append(float(fwd[top].mean() - fwd.mean()))
            q_fwd.append([float(fwd[q == g].mean()) for g in range(5)])
        for g in range(5):
            Rq[g].append(ew_path(Pf, np.where(q == g)[0]))
        for c in CLASSES:
            Rc[c].append(ew_path(Pf, np.where(cls == c)[0]))
        # B
        hi = rho[iu] > RHO_CAP
        rho_f = np.corrcoef(np.diff(np.log(Pf), axis=0).T) if full_month else np.full((n, n), np.nan)
        if full_month:
            rho_ic.append(spearman(rho[iu], rho_f[iu]))
            keep.append(float((rho_f[iu][hi] > RHO_CAP).mean())); base.append(float((rho_f[iu] > RHO_CAP).mean()))
        if a + 63 < len(dates):
            rho_g = np.corrcoef(np.diff(np.log(P[a: a + 64]), axis=0).T)
            rho_ic63.append(spearman(rho[iu], rho_g[iu]))
            keep63.append(float((rho_g[iu][hi] > RHO_CAP).mean())); base63.append(float((rho_g[iu] > RHO_CAP).mean()))
        # C
        Qc = WC * np.maximum(rho, 0.0); Qk = WCAP * (rho > RHO_CAP)
        np.fill_diagonal(Qc, 0.0); np.fill_diagonal(Qk, 0.0)
        lin = -WS * S; zero = np.zeros(n)
        prob = {"full": (lin, Qc + Qk), "no_cap": (lin, Qc), "no_corr": (lin, Qk), "no_score": (zero, Qc + Qk)}
        picks = {m: local_search(l, Q, np.random.default_rng([5, x, i]))[1] for i, (m, (l, Q)) in enumerate(prob.items())}
        picks["score_only"] = sorted(top.tolist())
        for m in VARIANTS:
            T = picks[m]
            r, tv, wend[m] = hold(Pf, T, wend[m]); R[m].append(r); turn[m].append(tv)
            est_rho[m].append(pair_mean(rho, T)); real_rho[m].append(pair_mean(rho_f, T)); mean_s[m].append(float(S[T].mean()))
            pick_vol[m].append(float(vol[T].mean()))
            for i in T:
                mix[m][cls[i]] += 1
        r, tv, wend["equal"] = hold(Pf, list(range(n)), wend["equal"]); R["equal"].append(r); turn["equal"].append(tv)
        for y in range(NR):
            r, _, wr[y] = hold(Pf, sorted(rrng.choice(n, K, replace=False).tolist()), wr[y]); Rr[y].append(r)
        holdings.append({"date": dates[a], **{m: [syms[i] for i in picks[m]] for m in VARIANTS}})

    R = {m: np.concatenate(v) for m, v in R.items()}
    Rr = np.array([np.concatenate(v) for v in Rr])
    Rq = [np.concatenate(v) for v in Rq]
    Rc = {c: np.concatenate(v) for c, v in Rc.items()}
    days = slice(reb[0] + 1, reb[-1] + 1)
    rf = P[days, bil] / P[reb[0]: reb[-1], bil] - 1.0
    R["spy"] = P[days, spy] / P[reb[0]: reb[-1], spy] - 1.0
    ex = {m: v - rf for m, v in R.items()}
    yrs = len(rf) / 252
    cut = reb[SPLIT] - reb[0]
    rand_sh = np.array([sharpe(v - rf) for v in Rr])
    brng = np.random.default_rng(11)

    res = {"period": [dates[reb[0]], dates[reb[-1]]], "split_date": dates[reb[SPLIT]], "rebalances": len(reb) - 1,
           "n_etfs": n, "data_sha256": px["sha256"],
           "versions": {"python": sys.version.split()[0], "numpy": np.__version__},
           "class_share_universe": {c: float((cls == c).mean()) for c in CLASSES},
           "universe_median_trailing_vol": float(np.mean(univ_vol)),
           "class_equal_weight": {c: {"n": int((cls == c).sum()), "ann_return": float(np.prod(1 + r) ** (1 / yrs) - 1),
                                      "ann_vol": float(r.std(ddof=1) * math.sqrt(252)), "sharpe": sharpe(r - rf)}
                                  for c, r in Rc.items()}}

    q_fwd = np.array(q_fwd)
    res["A_score"] = {
        "rank_ic": {k: series_stats(v, brng) for k, v in ic.items()},
        "score_vs_trailing_vol_spearman": float(np.mean(score_vol)),
        "top6_minus_universe_monthly": series_stats(top6_excess, brng),
        "q5_minus_q1_monthly": series_stats(q_fwd[:, 4] - q_fwd[:, 0], brng),
        "quintiles": [{"q": g + 1, "mean_monthly_return": float(q_fwd[:, g].mean()),
                       "ann_return": float(np.prod(1 + Rq[g]) ** (1 / yrs) - 1),
                       "ann_vol": float(Rq[g].std(ddof=1) * math.sqrt(252)), "sharpe": sharpe(Rq[g] - rf),
                       "max_drawdown": mdd(Rq[g])} for g in range(5)]}
    res["B_correlation"] = {
        "next_month": {"pair_rank_corr": series_stats(rho_ic, brng), "p_stay_above_cap": float(np.mean(keep)),
                       "base_rate_above_cap": float(np.mean(base))},
        "next_63_days": {"pair_rank_corr": series_stats(rho_ic63, brng), "p_stay_above_cap": float(np.mean(keep63)),
                         "base_rate_above_cap": float(np.mean(base63))}}
    res["C_ablation"] = {}
    for m, r in R.items():
        d = {"ann_return": float(np.prod(1 + r) ** (1 / yrs) - 1), "ann_vol": float(r.std(ddof=1) * math.sqrt(252)),
             "sharpe": sharpe(ex[m]), "sharpe_first": sharpe(ex[m][:cut]), "sharpe_last": sharpe(ex[m][cut:]),
             "max_drawdown": mdd(r), "sharpe_pct_vs_random": float((rand_sh < sharpe(ex[m])).mean())}
        if m in turn:
            d["turnover_per_year"] = float(sum(turn[m]) / yrs)
        if m in VARIANTS:
            tot = sum(mix[m].values())
            d.update({"est_pair_rho": float(np.mean(est_rho[m])), "realized_pair_rho": float(np.nanmean(real_rho[m])),
                      "mean_score": float(np.mean(mean_s[m])), "mean_pick_trailing_vol": float(np.mean(pick_vol[m])),
                      "class_share": {c: mix[m][c] / tot for c in CLASSES}})
        res["C_ablation"][m] = d
    res["random"] = {"sharpe_median": float(np.median(rand_sh)), "sharpe_p5": float(np.percentile(rand_sh, 5)),
                     "sharpe_p95": float(np.percentile(rand_sh, 95)), "paths": NR}
    pairs = [(m, "full") for m in VARIANTS[1:]] + [(m, "equal") for m in VARIANTS] + [("score_only", "spy")]
    diffs = {p: [] for p in pairs}
    for _ in range(2000):
        idx = block_boot_idx(len(rf), brng)
        sh = {m: sharpe(ex[m][idx]) for m in ex}
        for p in pairs:
            diffs[p].append(sh[p[0]] - sh[p[1]])
    res["sharpe_diff"] = {f"{a}-{b}": {"point": res["C_ablation"][a]["sharpe"] - res["C_ablation"][b]["sharpe"],
                                       "ci95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]}
                          for (a, b), v in diffs.items()}
    # reproduction of bt.py (computed there with Python 3.12 / numpy 2.5.3)
    old = json.load(open(os.path.join(HERE, "bt_result.json")))["methods"]
    oh = json.load(open(os.path.join(HERE, "bt_holdings.json")))
    res["reproduction"] = {
        "sharpe_now_vs_bt": {a: [res["C_ablation"][a]["sharpe"], old[b]["sharpe"]]
                             for a, b in (("full", "maiq"), ("score_only", "score"), ("equal", "equal"), ("spy", "spy"))},
        "months_same_holdings": {a: sum(h[a] == o[b] for h, o in zip(holdings, oh))
                                 for a, b in (("full", "maiq"), ("score_only", "score"))}}
    res["months_same_holdings_as_full"] = {m: sum(h[m] == h["full"] for h in holdings) for m in VARIANTS[1:]}
    res["mean_shared_picks_with_full"] = {m: float(np.mean([len(set(h[m]) & set(h["full"])) for h in holdings]))
                                          for m in VARIANTS[1:]}
    res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(os.path.join(HERE, "diag_result.json"), "w"), indent=1)
    json.dump(holdings, open(os.path.join(HERE, "diag_holdings.json"), "w"))

    print("period", res["period"], "split", res["split_date"], "seconds", res["seconds"])
    print("reproduction", json.dumps(res["reproduction"]))
    print("A rank IC")
    for k, v in res["A_score"]["rank_ic"].items():
        print(f"  {k:>6}: mean {v['mean']:+.4f}  t {v['t']:+.2f}  >0 {v['share_positive']:.2f}  CI [{v['ci95'][0]:+.4f}, {v['ci95'][1]:+.4f}]"
              f"  first {v['first']:+.4f}  last {v['last']:+.4f}")
    for k in ("top6_minus_universe_monthly", "q5_minus_q1_monthly"):
        v = res["A_score"][k]
        print(f"  {k}: mean {v['mean']:+.4%}  t {v['t']:+.2f}  CI [{v['ci95'][0]:+.4%}, {v['ci95'][1]:+.4%}]  first {v['first']:+.4%}  last {v['last']:+.4%}")
    print("  score vs trailing vol (Spearman)", round(res["A_score"]["score_vs_trailing_vol_spearman"], 3))
    for v in res["A_score"]["quintiles"]:
        print(f"  Q{v['q']}: monthly {v['mean_monthly_return']:+.3%}  ann {v['ann_return']:+.2%}  vol {v['ann_vol']:.2%}  sharpe {v['sharpe']:.3f}  mdd {v['max_drawdown']:.1%}")
    print("  class EW:", "  ".join(f"{c}(n={v['n']}) ret {v['ann_return']:+.2%} vol {v['ann_vol']:.2%} sh {v['sharpe']:.3f}"
                                    for c, v in res["class_equal_weight"].items()))
    print("B correlation")
    for k, v in res["B_correlation"].items():
        print(f"  {k}: pair rank corr {v['pair_rank_corr']['mean']:.3f}  P(stay > cap) {v['p_stay_above_cap']:.3f}  base {v['base_rate_above_cap']:.3f}")
    print("C ablation   random sharpe", json.dumps({k: round(v, 3) for k, v in res["random"].items()}))
    for m, v in res["C_ablation"].items():
        extra = (f"  est rho {v['est_pair_rho']:.3f}  real rho {v['realized_pair_rho']:.3f}  mean S {v['mean_score']:.3f}"
                 f"  pick vol {v['mean_pick_trailing_vol']:.3f}"
                 f"  mix {' '.join(f'{c[:3]} {s:.2f}' for c, s in v['class_share'].items())}") if m in VARIANTS else ""
        print(f"  {m:>10}: ret {v['ann_return']:+.2%}  vol {v['ann_vol']:.2%}  sharpe {v['sharpe']:.3f} ({v['sharpe_first']:.2f}/{v['sharpe_last']:.2f})"
              f"  mdd {v['max_drawdown']:.1%}  turn {round(v.get('turnover_per_year', float('nan')), 1)}  pct {v['sharpe_pct_vs_random']:.2f}{extra}")
    print("  universe median trailing vol", round(res["universe_median_trailing_vol"], 3),
          " same holdings as full (months)", res["months_same_holdings_as_full"],
          " shared picks with full (of 6)", {k: round(v, 2) for k, v in res["mean_shared_picks_with_full"].items()})
    for k, v in res["sharpe_diff"].items():
        print(f"  diff {k:>18}: {v['point']:+.3f}  CI [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]")
