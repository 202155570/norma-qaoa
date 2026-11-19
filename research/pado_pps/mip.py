"""Certify the classical optimum of the selection objectives with an exact MILP (HiGHS via scipy).

Objective (minimise, exactly k selected):  G(T) = sum_{i in T} lin_i + sum_{i<j in T} Q_ij
Linearisation: binary x_i, continuous y_ij standing for x_i x_j on every pair with Q_ij != 0.
  Q_ij > 0: y_ij >= x_i + x_j - 1, y_ij >= 0
  Q_ij < 0: y_ij <= x_i, y_ij <= x_j
  dense Q (all pairs present): RLT equalities sum_{j != i} y_ij = (k - 1) x_i (multiply sum x = k
  by x_i); valid for any 0/1 point and much tighter in the LP relaxation.
  cluster constraint (bt.py "cluster"): at most one per cluster.
The MILP is solved to mip_rel_gap = 0. Its x is rounded and G recomputed with numpy; that value
must equal the MILP objective, and the reported dual bound must not exceed it.

argv: problems   problem_{50,100,150}.json: original (lin, Q) and PADO variant (d, R_kept),
                 vs the picks in rank_*.json (exhaustive for N=50, local search + sampling for 100/150)
      bt         every one of the 108 backtest rebalances (bt.py objectives, same data and code),
                 maiq / pado / cluster, vs the local-search picks in bt_holdings.json
      redo       rebuild the backtest return path of each objective with the certified MILP picks
                 (bt.py hold/sharpe, same costs) and compare with the local-search path: the path
                 from bt_holdings.json must reproduce bt_result.json's Sharpe exactly first
Writes mip_result.json (problems) or mip_bt.json (bt; redo adds "redo" to it).
"""

import json
import os
import sys
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

HERE = os.path.dirname(os.path.abspath(__file__))
TOL = 1e-9


def energy(T, lin, Q):
    T = list(T)
    return float(lin[T].sum() + Q[np.ix_(T, T)][np.triu_indices(len(T), 1)].sum())


def solve(lin, Q, k, clusters=None, time_limit=3600.0):
    n = len(lin)
    iu, ju = np.triu_indices(n, 1)
    keep = Q[iu, ju] != 0.0
    I, J = iu[keep], ju[keep]; q = Q[I, J]; m = len(q)
    dense = m == n * (n - 1) // 2 and k is not None
    c = np.r_[lin, q]
    rows, cols, vals, lo, hi = [], [], [], [], []
    r = 0

    def add(entries, l, h):
        nonlocal r
        for col, v in entries:
            rows.append(r); cols.append(col); vals.append(v)
        lo.append(l); hi.append(h); r += 1

    if k is not None:                                   # k None: unconstrained (Ising ground state)
        add([(i, 1.0) for i in range(n)], k, k)
    for e, (i, j, v) in enumerate(zip(I, J, q)):
        y = n + e
        if v > 0:
            add([(y, 1.0), (i, -1.0), (j, -1.0)], -1.0, np.inf)
        else:
            add([(y, 1.0), (i, -1.0)], -np.inf, 0.0)
            add([(y, 1.0), (j, -1.0)], -np.inf, 0.0)
    if dense:
        inc = [[] for _ in range(n)]
        for e, (i, j) in enumerate(zip(I, J)):
            inc[i].append(n + e); inc[j].append(n + e)
        for i in range(n):
            add([(y, 1.0) for y in inc[i]] + [(i, -(k - 1.0))], 0.0, 0.0)
    if clusters is not None:
        for cl in np.unique(clusters):
            add([(int(u), 1.0) for u in np.flatnonzero(clusters == cl)], -np.inf, 1.0)
    A = coo_matrix((vals, (rows, cols)), shape=(r, n + m)).tocsr()
    t0 = time.time()
    res = milp(c, constraints=LinearConstraint(A, lo, hi), integrality=np.r_[np.ones(n), np.zeros(m)],
               bounds=Bounds(np.zeros(n + m), np.r_[np.ones(n), np.ones(m)]),
               options={"mip_rel_gap": 0.0, "time_limit": time_limit, "presolve": True})
    sec = time.time() - t0
    if res.x is None:
        return {"status": int(res.status), "message": res.message, "seconds": sec}
    T = sorted(np.flatnonzero(res.x[:n] > 0.5).tolist())
    G = energy(T, lin, Q)
    ok = (res.status == 0 and (k is None or len(T) == k) and abs(G - res.fun) < 1e-6
          and res.mip_dual_bound <= G + 1e-6 and (clusters is None or len(set(clusters[T])) == len(T)))
    return {"status": int(res.status), "certified": bool(ok), "T": T, "G": G, "milp_obj": float(res.fun),
            "dual_bound": float(res.mip_dual_bound), "gap": float(res.mip_gap), "nodes": int(res.mip_node_count),
            "pairs": m, "dense_rlt": dense, "seconds": sec}


def problems():
    out = {}
    for N in (50, 100, 150):
        pb = json.load(open(os.path.join(HERE, f"problem_{N}.json")))
        rk = json.load(open(os.path.join(HERE, f"rank_{N}.json")))
        syms, k = pb["syms"], pb["k"]
        lin, Q = np.array(pb["lin"]), np.array(pb["Q"])
        d = np.array(pb["d"]); R = np.zeros((N, N))
        for i, j, v in pb["R_kept"]:
            R[int(i), int(j)] = R[int(j), int(i)] = v
        # rank_*.json: original optimum (exhaustive at N=50, best found otherwise) and the variant
        # optimum; its variant_opt_G is that pick scored on the ORIGINAL objective, so the reference
        # value is recomputed here on the objective being solved
        for name, (a, M, refT) in {"original": (lin, Q, rk.get("original_opt", rk.get("original_best_found"))),
                                    "variant": (d, R, rk["variant_opt"])}.items():
            s = solve(a, M, k)
            s["pick"] = [syms[i] for i in s.pop("T")]
            ref = energy([syms.index(u) for u in refT], a, M)
            s["reference_G"], s["reference_pick"], s["reference_method"] = ref, refT, rk["method"]
            s["reference_is_optimal"] = bool(abs(ref - s["G"]) < TOL and s["certified"])
            out[f"N{N}_{name}"] = s
            print(f"N={N:3d} {name:8s} MILP {s['G']:+.6f} (bound {s['dual_bound']:+.6f}, {s['nodes']} nodes, {s['seconds']:.1f}s) "
                  f"certified={s['certified']}  ref {ref:+.6f} same={s['reference_is_optimal']}  {s['pick']}", flush=True)
    json.dump(out, open(os.path.join(HERE, "mip_result.json"), "w"), indent=1)


def backtest():
    sys.path.insert(0, HERE)
    import bt
    rec = []

    def record(lin, Q, rng, clusters=None, restarts=30):           # capture the matrices bt.py builds
        rec.append((lin.copy(), Q.copy(), None if clusters is None else clusters.copy()))
        return 0.0, list(range(bt.K))
    bt.local_search = record
    px = json.load(open(os.path.join(HERE, "prices10.json")))
    syms, dates = px["syms"], px["dates"]
    P = np.array(px["prices"]).T
    month = [x[:7] for x in dates]
    reb = [t for t in range(len(dates) - 1) if month[t] != month[t + 1] and t >= 253] + [len(dates) - 1]
    hold = json.load(open(os.path.join(HERE, "bt_holdings.json")))
    assert len(hold) == len(reb) - 1
    rows = []; t0 = time.time()
    for x, a in enumerate(reb[:-1]):
        assert hold[x]["date"] == dates[a]
        rec.clear(); bt.objectives(P[: a + 1], np.random.default_rng(0))
        for (lin, Q, cl), name in zip(rec, ["maiq", "pado", "cluster"]):
            s = solve(lin, Q, bt.K, clusters=cl)
            ls_T = [syms.index(u) for u in hold[x][name]]
            ls_G = energy(ls_T, lin, Q)
            s.update(date=dates[a], method=name, pick=[syms[i] for i in s.pop("T")], local_search_G=ls_G,
                     local_search_optimal=bool(ls_G <= s["G"] + TOL and s["certified"]))
            rows.append(s)
        r3 = rows[-3:]
        print(f"{dates[a]}  " + "  ".join(f"{r['method']} {r['G']:+.4f} ls {r['local_search_G'] - r['G']:+.1e} "
                                          f"{'OK' if r['local_search_optimal'] else 'MISS'} {r['seconds']:.1f}s" for r in r3)
              + f"  [{time.time() - t0:.0f}s]", flush=True)
    summ = {}
    for name in ["maiq", "pado", "cluster"]:
        rs = [r for r in rows if r["method"] == name]
        summ[name] = {"months": len(rs), "certified": sum(r["certified"] for r in rs),
                      "local_search_optimal": sum(r["local_search_optimal"] for r in rs),
                      "max_ls_excess": max(r["local_search_G"] - r["G"] for r in rs),
                      "seconds_median": float(np.median([r["seconds"] for r in rs])),
                      "seconds_max": max(r["seconds"] for r in rs)}
    print(json.dumps(summ, indent=1))
    json.dump({"summary": summ, "data_sha256": px["sha256"], "rows": rows},
              open(os.path.join(HERE, "mip_bt.json"), "w"), indent=1)


def redo():
    sys.path.insert(0, HERE)
    import bt
    px = json.load(open(os.path.join(HERE, "prices10.json")))
    syms, dates = px["syms"], px["dates"]
    P = np.array(px["prices"]).T; n = P.shape[1]
    month = [x[:7] for x in dates]
    reb = [t for t in range(len(dates) - 1) if month[t] != month[t + 1] and t >= 253] + [len(dates) - 1]
    hold = json.load(open(os.path.join(HERE, "bt_holdings.json")))
    res_bt = json.load(open(os.path.join(HERE, "bt_result.json")))
    mb = json.load(open(os.path.join(HERE, "mip_bt.json")))
    mpick = {(r["date"], r["method"]): r["pick"] for r in mb["rows"]}
    bil = syms.index("BIL")
    rf = P[reb[0] + 1: reb[-1] + 1, bil] / P[reb[0]: reb[-1], bil] - 1.0
    out = {}
    for name in ["maiq", "pado", "cluster"]:
        sh = {}
        for src in ["local_search", "milp"]:
            w = np.zeros(n); rs = []
            for x, (a, b) in enumerate(zip(reb[:-1], reb[1:])):
                names = hold[x][name] if src == "local_search" else mpick[(dates[a], name)]
                r, _, w = bt.hold(P[a: b + 1], sorted(syms.index(u) for u in names), w); rs.append(r)
            sh[src] = float(bt.sharpe(np.concatenate(rs) - rf))
        assert abs(sh["local_search"] - res_bt["methods"][name]["sharpe"]) < 1e-12, (name, sh, res_bt["methods"][name]["sharpe"])
        diff = sum(sorted(hold[x][name]) != sorted(mpick[(dates[a], name)]) for x, a in enumerate(reb[:-1]))
        out[name] = {"sharpe_local_search": sh["local_search"], "sharpe_milp": sh["milp"], "months_different": diff}
        print(name, out[name])
    mb["redo"] = out
    json.dump(mb, open(os.path.join(HERE, "mip_bt.json"), "w"), indent=1)


if __name__ == "__main__":
    {"problems": problems, "bt": backtest, "redo": redo}[sys.argv[1]]()
