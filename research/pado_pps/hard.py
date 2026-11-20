"""Where does the exact MILP (mip.solve, HiGHS) stop being fast? Exploratory scan over the structure
of the pair term, on the real data of mv.py (prices.json, N = 50/100/150 universes).

Objective (minimise, exactly k selected):  G(T) = sum_{i in T} lin_i + sum_{i<j in T} Q_ij
  lin_i = -S_i / k        S: rank (0..1) of the mean 63/126/252-day return (as mv.py)
  Q = c * mask * B, three families of B from the Ledoit-Wolf covariance / correlation rho of the
  last 126 daily log returns:
    cov     B = Sigma                         (mean-variance pair term: almost all positive, PSD)
    corr_c  B = rho - median(rho)             (penalise pairs more correlated than typical, reward
                                               less correlated pairs: half the pairs negative,
                                               not PSD, frustrated, but structured by real data)
    rand    B = |rho - median(rho)| * random sign   (spin-glass control: same magnitudes, no structure)
  density (mask): deg3 = greedy by |B| keeping a pair while both ends have degree < 3 (as build.py),
                  or the top fraction 0.1 / 0.3 / 1.0 of all pairs by |B|
  strength s: c is set so that (k - 1) * rms(kept Q) = s * std(lin), i.e. s = 1 means one item's pair
              term with the other k - 1 selected items is about as large as the spread of scores.

Per problem:
  milp   mip.solve (sparse problems with the neighbour RLT inequality), time limit TL;
         status, certified, incumbent, dual bound, gap, nodes, seconds
  swap   best-improvement swap search with k fixed (as compare.swap_search) from the score-greedy
         start + 100 random starts; best, time, and per-start hit rate against the best known value
         (min of MILP incumbent and swap best)
Exploratory, not pre-registered.

argv: map  <out.jsonl> <N> <k> <TL> <workers>        all family x density x strength at one (N, k)
      cfg  <out.jsonl> <TL> <workers> N:k:fam:dens:s ...   explicit list (scaling runs)
Configurations already in <out.jsonl> are skipped (resume). Env HARD_RESTARTS: swap random starts (default 100).
"""

import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
from scipy.stats import rankdata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cand import lw_const_corr  # noqa: E402
from mip import energy, solve  # noqa: E402
from mv import universes  # noqa: E402

FAMILIES = ("cov", "corr_c", "rand")
DENSITIES = ("deg3", "0.1", "0.3", "1.0")
STRENGTHS = (0.25, 1.0, 4.0, 16.0)
REL = 1e-9
_BASE = {}


def base(N):
    if N not in _BASE:
        px = json.load(open(os.path.join(HERE, "prices.json")))
        allsyms = px["syms"]; P_all = np.array(px["prices"]).T
        syms = universes(px)[N]
        P = P_all[:, [allsyms.index(s) for s in syms]]
        S = (rankdata(sum(P[-1] / P[-1 - d] - 1.0 for d in (63, 126, 252)) / 3.0, method="average") - 1.0) / (N - 1)
        cov, _ = lw_const_corr(np.diff(np.log(P[-127:]), axis=0)); cov = cov * 252.0
        sd = np.sqrt(np.diag(cov))
        _BASE[N] = (S, cov, cov / np.outer(sd, sd))
    return _BASE[N]


def make(N, k, fam, dens, s):
    S, cov, rho = base(N)
    lin = -S / k
    iu = np.triu_indices(N, 1)
    med = float(np.median(rho[iu]))
    if fam == "cov":
        B = cov.copy()
    elif fam == "corr_c":
        B = rho - med
    elif fam == "rand":
        sg = np.random.default_rng([N, 7]).choice([-1.0, 1.0], size=(N, N))
        sg = np.triu(sg, 1); sg = sg + sg.T
        B = np.abs(rho - med) * sg
    else:
        raise KeyError(fam)
    np.fill_diagonal(B, 0.0)
    order = np.argsort(-np.abs(B[iu]), kind="stable")
    mask = np.zeros(len(order), bool)
    if dens == "deg3":
        deg = np.zeros(N, int)
        for e in order:
            i, j = iu[0][e], iu[1][e]
            if deg[i] < 3 and deg[j] < 3:
                mask[e] = True; deg[i] += 1; deg[j] += 1
    else:
        mask[order[: int(round(float(dens) * len(order)))]] = True
    q = np.where(mask, B[iu], 0.0)
    c = s * lin.std() / ((k - 1) * np.sqrt(np.mean(q[mask] ** 2)))
    Q = np.zeros((N, N)); Q[iu] = c * q; Q = Q + Q.T
    return lin, Q


def swap_search(lin, Q, k, rng, restarts=100):
    n = len(lin)

    def greedy():
        T = []
        while len(T) < k:
            g = lin + (Q[:, T].sum(1) if T else 0.0); g[T] = np.inf
            T.append(int(np.argmin(g)))
        return T

    out = []
    for start in [greedy()] + [list(rng.choice(n, k, replace=False)) for _ in range(restarts)]:
        T = list(start)
        while True:
            inT = np.zeros(n, bool); inT[T] = True
            s = Q[:, T].sum(1)
            D = (lin + s)[None, :] - Q[np.array(T)] - (lin[T] + s[T])[:, None]
            D[:, inT] = np.inf
            a, b = np.unravel_index(np.argmin(D), D.shape)
            if D[a, b] >= -1e-12:
                break
            T[a] = int(b)
        T = sorted(int(x) for x in T)
        out.append((energy(T, lin, Q), T))
    return out


def key(N, k, fam, dens, s):
    return f"N{N}_k{k}_{fam}_{dens}_s{s:g}"


def run_one(args):
    N, k, fam, dens, s, TL = args
    lin, Q = make(N, k, fam, dens, s)
    iu = np.triu_indices(N, 1); qv = Q[iu]; nz = qv != 0
    t0 = time.time()
    sw = swap_search(lin, Q, k, np.random.default_rng([N, k, len(fam), int(s * 100)]), int(os.environ.get("HARD_RESTARTS", "100")))
    t_sw = time.time() - t0
    e_sw = np.array([e for e, _ in sw]); T_sw = sw[int(np.argmin(e_sw))][1]
    m = solve(lin, Q, k, time_limit=TL, rlt_sparse=True)
    G_m = m.get("G", np.inf)
    best = min(G_m, float(e_sw.min()))
    tol = REL * max(1.0, abs(best))
    row = {"key": key(N, k, fam, dens, s), "N": N, "k": k, "family": fam, "density": dens, "strength": s,
           "time_limit": TL, "pairs": int(nz.sum()), "neg_pair_share": float((qv[nz] < 0).mean()),
           "Q_min_eig": float(np.linalg.eigvalsh(Q)[0]),
           "milp_status": m["status"], "milp_certified": m.get("certified", False), "milp_G": G_m if np.isfinite(G_m) else None,
           "milp_dual_bound": m.get("dual_bound"), "milp_gap": m.get("gap"), "milp_nodes": m.get("nodes"),
           "milp_seconds": m["seconds"], "milp_T": m.get("T"),
           "swap_best": float(e_sw.min()), "swap_T": T_sw, "swap_seconds": t_sw, "swap_starts": len(sw),
           "swap_hit_rate": float(np.mean(e_sw <= best + tol)), "swap_found_best": bool(e_sw.min() <= best + tol),
           "milp_found_best": bool(G_m <= best + tol), "best_known": best}
    return row


def main(out, cfgs, workers):
    path = os.path.join(HERE, out)
    done = set()
    if os.path.exists(path):
        done = {json.loads(l)["key"] for l in open(path)}
    todo = [c for c in cfgs if key(*c[:5]) not in done]
    print(f"{len(todo)} to run ({len(cfgs) - len(todo)} done)", flush=True)
    for N in sorted({c[0] for c in todo}):
        base(N)
    with Pool(workers, maxtasksperchild=1) as pool, open(path, "a") as f:
        for r in pool.imap_unordered(run_one, todo):
            f.write(json.dumps(r) + "\n"); f.flush()
            st = "CERT" if r["milp_certified"] else f"gap {r['milp_gap'] if r['milp_gap'] is not None else float('nan'):.1e}"
            print(f"{r['key']:28s} pairs {r['pairs']:6d} neg {r['neg_pair_share']:.2f}  MILP {st} {r['milp_seconds']:7.1f}s "
                  f"nodes {r['milp_nodes']}  swap best={r['swap_found_best']} hit {r['swap_hit_rate']:.2f} "
                  f"{r['swap_seconds']:.1f}s", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "map":
        out, N, k, TL, w = sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6])
        main(out, [(N, k, f, d, s, TL) for f in FAMILIES for d in DENSITIES for s in STRENGTHS], w)
    elif cmd == "cfg":
        out, TL, w = sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
        cfgs = []
        for a in sys.argv[5:]:
            N, k, f, d, s = a.split(":")
            cfgs.append((int(N), int(k), f, d, float(s), TL))
        main(out, cfgs, w)
