"""Solver comparison on the Ising problems RQAOA was run on (same h, J, same lambda, known ground state).

Problems (41):
  n20   the 29 coupling x4 N=20 instances of ibm_hard_prep.hard_instance (GS by enumeration)
  proxy the PADO variant of problem_{50,100,150}.json at kappa 1 and 4, lambda_gs6 of rqaoa_big.jsonl
  mv    the mean-variance problems of mv.py, lambda of rqaoa_mv.jsonl
Every method minimises the same E(z) = sum h_i z_i + sum J_ij z_i z_j (z = -1 selected); a hit is
E within 1e-9 (relative) of the ground state energy.

Classical methods:
  greedy     steepest single-flip descent from the empty selection (z = +1)
  descent    single-flip steepest descent from 200 random starts (best of them; hit rate per start)
  swap       the cardinality form (x = (1 - z)/2, exactly k_gs selected): best-improvement swap
             search from the score-greedy start and 30 random starts (as bt.local_search)
  sa         simulated annealing, 20 independent runs of 1000 sweeps, geometric temperature from
             T0 = mean |local field| down to T0 / 1000 (best of 20; hit rate per run)
  seqfix     the recursion of rqaoa.py with the QAOA correlations replaced by the coefficients
             (M_i = -h_i, M_ij = -J_ij): the small-angle limit of p = 1 RQAOA, a purely classical rule
             (same elimination, same enumeration of the last NC = 10 variables)
RQAOA rows are read from rqaoa_n20.jsonl (sv), rqaoa_big.jsonl / rqaoa_big_p2.jsonl (padopauli) and
rqaoa_mv.jsonl (closed form).

argv: run    writes compare.jsonl and prints the summary
"""

import json
import os
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rqaoa as R  # noqa: E402

REL = 1e-9


# ---------------------------------------------------------------- problems
def problems():
    import ibm_hard_prep as H
    out = []
    n20 = {r["seed"]: r for r in map(json.loads, open(os.path.join(HERE, "rqaoa_n20.jsonl")))
           if r["engine"] == "sv" and r["p"] == 1}
    for seed in sorted(n20):
        pb = H.hard_instance(seed)
        out.append({"tag": f"n20_s{seed}", "family": "n20", "h": np.array(pb["h"], float), "J": pb["J"],
                    "E_gs": n20[seed]["E_gs"], "k_gs": n20[seed]["selected_gs"]})
    big = {r["tag"]: r for r in map(json.loads, open(os.path.join(HERE, "rqaoa_big.jsonl")))}
    for N in (50, 100, 150):
        pb = json.load(open(os.path.join(HERE, f"problem_{N}.json")))
        J1 = [(int(i), int(j), float(v)) for i, j, v in pb["J"]]
        for kappa in (1, R.KAPPA):
            if kappa == 1:
                h0, J = np.array(pb["h0"], float), J1
            else:
                lin_half = np.array(pb["h0"], float)
                for i, j, v in J1:
                    lin_half[i] += v; lin_half[j] += v
                h0 = lin_half.copy()
                for i, j, v in J1:
                    h0[i] -= kappa * v; h0[j] -= kappa * v
                J = [(i, j, kappa * v) for i, j, v in J1]
            r = big[f"N{N}_k{kappa}"]
            out.append({"tag": f"proxy_N{N}_k{kappa}", "family": "proxy", "h": h0 - r["lambda_gs6"] / 2, "J": J,
                        "E_gs": r["E_gs"], "k_gs": r["selected_gs"]})
    for r in map(json.loads, open(os.path.join(HERE, "rqaoa_mv.jsonl"))):
        pb = json.load(open(os.path.join(HERE, f"mv_problem_{r['N']}_g{r['gamma']}.json")))
        out.append({"tag": f"mv_N{r['N']}_g{r['gamma']}", "family": "mv", "h": np.array(pb["h0"]) - r["lambda_gs6"] / 2,
                    "J": [(int(i), int(j), float(v)) for i, j, v in pb["J"]], "E_gs": r["E_gs"],
                    "k_gs": r["selected_gs"]})
    for p in out:
        n = len(p["h"]); Jm = np.zeros((n, n))
        for i, j, v in p["J"]:
            Jm[i, j] += v; Jm[j, i] += v
        p["Jm"] = Jm
    return out


def energies(Z, h, Jm):
    """Z: (R, n) of +-1."""
    return Z @ h + 0.5 * np.einsum("ri,ij,rj->r", Z, Jm, Z)


# ---------------------------------------------------------------- classical solvers
def descent(Z, h, Jm):
    """Steepest single-flip descent of each row of Z until no flip lowers E."""
    Z = Z.copy(); F = h[None] + Z @ Jm
    rows = np.arange(len(Z))
    while True:
        dE = -2.0 * Z * F                                    # energy change of flipping each spin
        k = np.argmin(dE, 1); best = dE[rows, k]
        act = best < -1e-12
        if not act.any():
            return Z
        r, i = rows[act], k[act]
        F[r] -= 2.0 * Z[r, i][:, None] * Jm[i]
        Z[r, i] *= -1.0


def sa(h, Jm, rng, runs=20, sweeps=1000):
    n = len(h)
    Z = rng.choice([-1.0, 1.0], size=(runs, n)); F = h[None] + Z @ Jm
    T0 = float(np.mean(np.abs(F))); Ts = T0 * (1e-3) ** (np.arange(sweeps) / (sweeps - 1))
    rows = np.arange(runs)
    for T in Ts:
        for i in rng.permutation(n):
            dE = -2.0 * Z[:, i] * F[:, i]
            acc = (dE <= 0) | (rng.random(runs) < np.exp(-np.clip(dE, 0, None) / T))
            if acc.any():
                r = rows[acc]
                F[r] -= 2.0 * Z[r, i][:, None] * Jm[i][None]
                Z[r, i] *= -1.0
    return descent(Z, h, Jm)


def swap_search(h, Jm, k, rng, restarts=30):
    """Cardinality form: x = (1 - z)/2, E = const + sum lin_i x_i + sum_{i<j} Q_ij x_i x_j."""
    n = len(h)
    lin = -2.0 * h - 2.0 * Jm.sum(1); Q = 4.0 * Jm

    def G(T):
        return lin[T].sum() + 0.5 * Q[np.ix_(T, T)].sum()

    def greedy():
        T = []
        while len(T) < k:
            g = lin + (Q[:, T].sum(1) if T else 0.0); g[T] = np.inf
            T.append(int(np.argmin(g)))
        return T

    best = (np.inf, None)
    for start in [greedy()] + [list(rng.choice(n, k, replace=False)) for _ in range(restarts)]:
        T = list(start)
        while True:
            inT = np.zeros(n, bool); inT[T] = True
            s = Q[:, T].sum(1)                                # sum_{t in T} Q_xt
            out_gain = lin[T] + s[T]                          # contribution removed with a in T
            in_cost = lin + s                                 # contribution added with b (before removing a)
            D = in_cost[None, :] - Q[np.array(T)][:, :] - out_gain[:, None]     # (a, b): b in, a out
            D[:, inT] = np.inf
            a, b = np.unravel_index(np.argmin(D), D.shape)
            if D[a, b] >= -1e-12:
                break
            T[a] = int(b)
        e = G(T)
        if e < best[0]:
            best = (e, sorted(T))
    z = np.ones(n); z[best[1]] = -1.0
    return z


class Coef:
    """Engine for rqaoa.rqaoa returning the coefficients as 'correlations' (seqfix)."""

    def __init__(self, n, h, E, p):
        self.M = torch.tensor(np.r_[-np.asarray(h, float), [-v for _, v in E]], dtype=torch.float64)

    def obs(self, x):
        return self.M + 0.0 * x.sum()

    def obs_batch(self, X):
        return self.M[None].repeat(len(X), 1)


# ---------------------------------------------------------------- run
def cmd_run():
    rng = np.random.default_rng(2026)
    out = open(os.path.join(HERE, "compare.jsonl"), "w")
    rows = []
    for p in problems():
        h, Jm, J, Eg = p["h"], p["Jm"], p["J"], p["E_gs"]
        n = len(h)
        hit = lambda e: bool(e <= Eg + REL * max(1.0, abs(Eg)))
        k_gs = None
        res = {}
        t0 = time.time(); z = descent(np.ones((1, n)), h, Jm)[0]
        res["greedy"] = (float(energies(z[None], h, Jm)[0]), time.time() - t0, None)
        t0 = time.time(); Z = descent(rng.choice([-1.0, 1.0], size=(200, n)), h, Jm); e = energies(Z, h, Jm)
        res["descent"] = (float(e.min()), time.time() - t0, float(np.mean([hit(x) for x in e])))
        t0 = time.time(); Z = sa(h, Jm, rng); e = energies(Z, h, Jm)
        res["sa"] = (float(e.min()), time.time() - t0, float(np.mean([hit(x) for x in e])))
        # k of the ground state: from the problem's reference (sel count of the GS of each family)
        k_gs = p.get("k_gs")
        if k_gs is None:
            # the ground state's selection count: recover it from any hit found above, else from MILP
            cands = [Z[np.argmin(e)]]
            zbest = cands[0]
            if hit(float(energies(zbest[None], h, Jm)[0])):
                k_gs = int((zbest < 0).sum())
            else:
                _, zg, _ = R.milp_gs(h, J)
                k_gs = int((zg < 0).sum())
        t0 = time.time(); z = swap_search(h, Jm, k_gs, rng)
        res["swap"] = (float(energies(z[None], h, Jm)[0]), time.time() - t0, None)
        t0 = time.time()
        z, _ = R.rqaoa(h, J, 1, lambda n_, h_, E_, q: Coef(n_, h_, E_, q))
        res["seqfix"] = (float(energies(z[None], h, Jm)[0]), time.time() - t0, None)
        for m, (e, s, rate) in res.items():
            row = {"tag": p["tag"], "family": p["family"], "n": n, "k_gs": k_gs, "method": m, "E": e, "E_gs": Eg,
                   "hit": hit(e), "rel_gap": (e - Eg) / abs(Eg), "seconds": s, "hit_rate": rate}
            out.write(json.dumps(row) + "\n"); rows.append(row)
        out.flush()
        print(f"{p['tag']:16s} n={n:3d} k={k_gs}  " + "  ".join(
            f"{m} {'HIT' if hit(e) else f'{(e - Eg) / abs(Eg):.1e}'}{'' if rate is None else f'({rate:.2f})'} {s:.1f}s"
            for m, (e, s, rate) in res.items()), flush=True)


if __name__ == "__main__":
    {"run": cmd_run}[sys.argv[1]]()
