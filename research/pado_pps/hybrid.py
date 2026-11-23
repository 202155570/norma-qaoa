"""Quantum output as starting points for the classical swap descent (hybrid). Exploratory, not pre-registered.

Part A, the 12 hard problems of hard_rqaoa.py (N = 100/150: no quantum samples can be drawn there, so the
quantum information used is what the earlier runs computed exactly):
  A1  every final answer of the quantum and classical recursions (RQAOA p=1 variants, XY-QAOA, padopauli,
      seqfix variants, xycoef) as the start of one swap descent: does the descent reach the optimum?
  A2  starts drawn from per-variable selection probabilities, k items without replacement (Gumbel top-k):
        uniform   all items equal
        score     p_u ~ exp(-lin_u / std(lin))                       (classical prior from the linear term)
        qaoa_p1   p_u = (1 - <Z_u>) / 2, standard QAOA p = 1 with the quadratic penalty, trained angles, exact
        xy        p_u = (1 - <Z_u>) / 2, XY-mixer QAOA from the Dicke state (first step of hard_rqaoa xy), exact
      S starts each, swap descent from each; share of starts that reach the certified optimum.
  The descent is the best-improvement swap of hard.swap_search.
argv: A <out.jsonl> [S]
"""

import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hard  # noqa: E402
import hard_rqaoa as H  # noqa: E402

REL = 1e-9


def descend(T, lin, Q):
    n = len(lin); T = list(T)
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
    return hard.energy(T, lin, Q), T


def gumbel_topk(logp, k, rng):
    return list(np.argsort(-(logp + rng.gumbel(size=len(logp))))[:k])


def final_answers():
    out = {}
    files = {"hard_rqaoa.jsonl": None, "hard_rqaoa_pps.jsonl": None, "hard_rqaoa_kb.jsonl": None,
             "hard_rqaoa_kb_p1k.jsonl": None, "hard_rqaoa_kb_p1kb5.jsonl": None, "hard_rqaoa_kb_p1k0.jsonl": None,
             "hard_rqaoa_xy.jsonl": None}
    for f in files:
        p = os.path.join(HERE, f)
        if not os.path.exists(p):
            continue
        for l in open(p):
            r = json.loads(l)
            if r.get("status") == "ok" and r.get("T"):
                out.setdefault(r["key"], {})[f"{r['engine']}/{r['penalty']}"] = r
    return out


def marg_qaoa_p1(lin, Q, k, P):
    import torch
    import rqaoa as R
    n = len(lin)
    lin_p = lin + P * (1 - 2 * k); Q_p = Q + 2.0 * P; np.fill_diagonal(Q_p, 0.0)
    h = -lin_p / 2.0 - Q_p.sum(1) / 4.0
    iu = np.triu_indices(n, 1)
    E = [((int(i), int(j)), float(Q_p[i, j] / 4.0)) for i, j in zip(*iu) if Q_p[i, j] != 0.0]
    x, eng, e, _ = R.qaoa(lambda q: R.P1(n, h, E, q), h, E, 1, None)
    with torch.no_grad():
        M = eng.obs(torch.tensor(x)).numpy()[:n]
    return M, list(map(float, x))


def marg_xy(lin, Q, k, step0):
    import xyqaoa as X
    n = len(lin)
    h = -lin / 2.0 - Q.sum(1) / 4.0; Jm = Q / 4.0
    eng = X.XY1(h, Jm, k, seed=n)
    g, b = step0["gamma"], step0["beta"]
    return eng.fields(g, b), [g, b]


def cmd_A(out, S):
    import torch
    torch.set_num_threads(int(os.environ.get("HY_THREADS", "8")))
    ans = final_answers()
    Pq = {json.loads(l)["key"]: json.loads(l)["lam"] for l in open(os.path.join(HERE, "hard_rqaoa.jsonl"))
          if json.loads(l)["penalty"] == "quad"}
    xy0 = {json.loads(l)["key"]: json.loads(l)["xy_steps"][0] for l in open(os.path.join(HERE, "hard_rqaoa_xy.jsonl"))
           if json.loads(l)["engine"] == "xy"}
    fo = open(os.path.join(HERE, out), "a")
    for ref in H.problems():
        key, N, k = ref["key"], ref["N"], ref["k"]
        lin, Q = hard.make(N, k, ref["family"], ref["density"], ref["strength"])
        Gopt = ref["milp_G"]; tol = REL * abs(Gopt); hit = lambda g: bool(g <= Gopt + tol)
        row = {"key": key, "N": N, "k": k, "G_opt": Gopt}
        # A1
        a1 = {}
        for name, r in ans.get(key, {}).items():
            if len(r["T"]) != k:
                a1[name] = {"start_gap": None, "after_gap": None, "hit": False, "note": f"{len(r['T'])} selected"}
                continue
            g0 = hard.energy(r["T"], lin, Q); g1, _ = descend(r["T"], lin, Q)
            a1[name] = {"start_gap": (g0 - Gopt) / abs(Gopt), "after_gap": (g1 - Gopt) / abs(Gopt), "hit": hit(g1)}
        row["A1"] = a1
        # A2
        t0 = time.time()
        M1, ang1 = marg_qaoa_p1(lin, Q, k, Pq[key]); t_p1 = time.time() - t0
        t0 = time.time()
        Mx, angx = marg_xy(lin, Q, k, xy0[key]); t_xy = time.time() - t0
        probs = {"uniform": np.full(N, k / N),
                 "score": np.exp(-(lin - lin.min()) / lin.std()),
                 "qaoa_p1": np.clip((1 - M1) / 2, 1e-12, None),
                 "xy": np.clip((1 - Mx) / 2, 1e-12, None)}
        a2 = {}
        for name, p in probs.items():
            rng = np.random.default_rng([N, k, int(ref["strength"] * 100), len(ref["family"]), 11])
            lp = np.log(p)
            g0s, g1s = [], []
            for _ in range(S):
                T = gumbel_topk(lp, k, rng)
                g0s.append(hard.energy(sorted(T), lin, Q)); g1s.append(descend(T, lin, Q)[0])
            g0s, g1s = np.array(g0s), np.array(g1s)
            a2[name] = {"hit_share": float(np.mean(g1s <= Gopt + tol)), "start_hit_share": float(np.mean(g0s <= Gopt + tol)),
                        "start_gap_median": float(np.median((g0s - Gopt) / abs(Gopt))),
                        "after_gap_median": float(np.median((g1s - Gopt) / abs(Gopt))),
                        "p_opt_mean": float(np.mean(p[ref["milp_T"]] / p.sum() * k))}
        row.update(A2=a2, S=S, qaoa_p1_angles=ang1, xy_angles=angx, seconds_p1=t_p1, seconds_xy=t_xy)
        fo.write(json.dumps(row) + "\n"); fo.flush()
        print(f"{key:26s} A1 hits " + " ".join(f"{n_.split('/')[0]}:{int(v['hit'])}" for n_, v in sorted(a1.items())), flush=True)
        print(f"{'':26s} A2 hit share " + " ".join(f"{n_} {v['hit_share']:.2f} (start gap {v['start_gap_median']:.2f})" for n_, v in a2.items()), flush=True)




# ---------------------------------------------------------------- Part B: small instances, true quantum samples
"""Part B, N = 20, k = 5 (exact state vectors): instances built like hard.make on random 20-item subsets of the
N = 150 universe (pair term all pairs, families corr_c / rand, strength x4 / x16), optimum and f(m) by enumeration.
Samplers (all exact, angles trained on the expected cost, then S shots from |psi|^2):
  std_p<p>      standard QAOA (|+>^n, RX mixer) on the QUBO with the quadratic penalty, P = 2 max_m (f(k)-f(m))/(m-k)^2
                exact; shots with a wrong count are repaired greedily (add / remove the best item) before the descent
  xyring_p<p>   Dicke start, ring XY mixer in parity order (ring sorted by lin), no penalty (as xyqaoa.py)
  xyfull_p<p>   Dicke start, complete-graph XY mixer exp(-i beta sum_{i<j} (XX + YY) / 2), no penalty
  uniform       uniform random k-subsets (classical control);  score: Gumbel top-k on -lin / std(lin)
Reported per sampler: P(opt) = probability of the optimum in one shot (exact), share of the S starts whose swap
descent reaches the optimum, and the same for the raw shots (no descent).
argv: B <out.jsonl> <instances per family x strength> [S] [workers]
"""


def make_sub(idx, k, fam, s, seed):
    S_all, cov_all, rho_all = hard.base(150)
    from scipy.stats import rankdata
    n = len(idx)
    Sr = (rankdata(S_all[idx], method="average") - 1.0) / (n - 1)
    lin = -Sr / k
    cov, rho = cov_all[np.ix_(idx, idx)], rho_all[np.ix_(idx, idx)]
    iu = np.triu_indices(n, 1); med = float(np.median(rho[iu]))
    if fam == "cov":
        B = cov.copy()
    elif fam == "corr_c":
        B = rho - med
    else:
        sg = np.random.default_rng([n, 7, seed]).choice([-1.0, 1.0], size=(n, n)); sg = np.triu(sg, 1); sg = sg + sg.T
        B = np.abs(rho - med) * sg
    np.fill_diagonal(B, 0.0)
    q = B[iu]; c = s * lin.std() / ((k - 1) * np.sqrt(np.mean(q ** 2)))
    Q = np.zeros((n, n)); Q[iu] = c * q; Q = Q + Q.T
    return lin, Q


def _all_states(n):
    idx = np.arange(1 << n)
    return ((idx[:, None] >> np.arange(n)) & 1).astype(np.int8)


def _train(fn, nparam, rng, starts=6, warm=None, maxper=200):
    """Nelder-Mead from `starts` random points (and the warm start: previous depth's angles, padded)."""
    from scipy.optimize import minimize
    best = None
    x0s = [rng.uniform(-1, 1, nparam) for _ in range(starts)]
    if warm is not None:
        x0s = [np.r_[warm, 0.1, 0.1]] + x0s
    for x0 in x0s:
        r = minimize(fn, x0, method="Nelder-Mead", options={"maxiter": maxper * nparam, "xatol": 1e-4, "fatol": 1e-9})
        if best is None or r.fun < best.fun:
            best = r
    return best


def run_B(args):
    inst, S = args
    import torch
    torch.set_num_threads(1)
    from scipy.sparse import csr_matrix
    from scipy.sparse.linalg import expm_multiply
    fam, s, seed, k = inst["fam"], inst["s"], inst["seed"], inst["k"]
    rng0 = np.random.default_rng([seed, 31])
    idx = np.sort(rng0.choice(150, inst["n"], replace=False))
    lin, Q = make_sub(idx, k, fam, s, seed)
    n = len(lin)
    X = _all_states(n); cnt = X.sum(1)
    Xf = X.astype(float)
    G = Xf @ lin + 0.5 * np.einsum("si,ij,sj->s", Xf, Q, Xf)
    f = {m: float(G[cnt == m].min()) for m in range(1, n + 1)}; f[0] = 0.0
    feas = np.flatnonzero(cnt == k); Gf = G[feas]
    o = int(feas[np.argmin(Gf)]); Gopt = float(G[o]); tol = REL * abs(Gopt)
    T_opt = sorted(np.flatnonzero(X[o]).tolist())
    P = 2.0 * max((f[k] - f[m]) / (m - k) ** 2 for m in f if m != k)
    Gpen = G + P * (cnt - k) ** 2
    rng = np.random.default_rng([seed, int(s), len(fam), 5])

    def repair(x):
        T = list(np.flatnonzero(x))
        while len(T) > k:
            gs = [hard.energy(sorted(set(T) - {u}), lin, Q) for u in T]; T.remove(T[int(np.argmin(gs))])
        while len(T) < k:
            out = [u for u in range(n) if u not in T]
            gs = [hard.energy(sorted(T + [u]), lin, Q) for u in out]; T.append(out[int(np.argmin(gs))])
        return T

    def evaluate(name, probs_states, states_X, extra):
        """probs over basis states (array aligned with states_X rows)."""
        pr = probs_states / probs_states.sum()
        p_opt = float(pr[np.flatnonzero((states_X == X[o]).all(1))].sum()) if states_X is not X else float(pr[o])
        shots = rng.choice(len(pr), S, p=pr)
        raw, after, fe = [], [], []
        for sh in shots:
            x = states_X[sh]; fe.append(int(x.sum() == k))
            T = list(np.flatnonzero(x)) if x.sum() == k else repair(x)
            raw.append(hard.energy(sorted(T), lin, Q)); after.append(descend(T, lin, Q)[0])
        raw, after = np.array(raw), np.array(after)
        return {"p_opt": p_opt, "raw_hit_share": float(np.mean(raw <= Gopt + tol)),
                "hit_share": float(np.mean(after <= Gopt + tol)), "feasible_shot_share": float(np.mean(fe)), **extra}

    res = {}
    # controls
    for name in ("uniform", "score"):
        hits_raw, hits = [], []
        lp = np.zeros(n) if name == "uniform" else -(lin - lin.min()) / lin.std()
        for _ in range(S):
            T = gumbel_topk(lp, k, rng)
            hits_raw.append(hard.energy(sorted(T), lin, Q) <= Gopt + tol); hits.append(descend(T, lin, Q)[0] <= Gopt + tol)
        res[name] = {"p_opt": 1.0 / len(feas) if name == "uniform" else None, "raw_hit_share": float(np.mean(hits_raw)),
                     "hit_share": float(np.mean(hits)), "feasible_shot_share": 1.0}
    # standard QAOA with penalty, full state vector
    dev = torch.device(os.environ.get("PF_DEVICE", "cpu"))
    Hd = torch.tensor(Gpen, device=dev)

    def std_state(x, p):
        psi = torch.full((1 << n,), (1 << n) ** -0.5, dtype=torch.complex128, device=dev)
        for l in range(p):
            g, b = float(x[2 * l]), float(x[2 * l + 1])
            psi = psi * torch.exp(-1j * g * Hd)
            c, sn = math.cos(b), math.sin(b)
            for q in range(n):
                v = psi.view(-1, 2, 1 << q)
                a0, a1 = v[:, 0, :], v[:, 1, :]
                psi = torch.stack([c * a0 - 1j * sn * a1, c * a1 - 1j * sn * a0], 1).reshape(-1)
        return psi
    sc = float(np.std(Gpen)); warm = None
    for p in (1, 2, 3):
        fn = lambda x: float((std_state(_ang(x, sc), p).abs() ** 2 @ Hd).item())
        r = _train(fn, 2 * p, rng, starts=3 if p == 1 else 2, warm=warm, maxper=150); warm = r.x
        pr = (std_state(_ang(r.x, sc), p).abs() ** 2).cpu().numpy()
        res[f"std_p{p}"] = evaluate(f"std_p{p}", pr, X, {"E": float(r.fun), "angles": _ang(r.x, sc).tolist()})
    # XY in the Dicke subspace
    Xd = X[feas]; Gd = G[feas]; D = len(feas); pos = {int(v): a for a, v in enumerate(feas)}
    # complete-graph mixer: adjacency of the Johnson graph (swap one selected for one unselected)
    rows, cols = [], []
    for a, v in enumerate(feas):
        sel = np.flatnonzero(X[v]); uns = np.flatnonzero(1 - X[v])
        for i in sel:
            for j in uns:
                rows.append(a); cols.append(pos[int(v ^ (1 << int(i)) ^ (1 << int(j)))])
    HM = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(D, D))
    order = list(np.argsort(lin, kind="stable"))
    import xyqaoa as XYm
    layers = XYm.ring_layers(n)
    swaps = []
    for L in layers:
        for a_, b_ in L:
            va, vb = order[a_], order[b_]
            tgt = np.array([pos.get(int(v ^ (1 << va) ^ (1 << vb)), -1) if X[v, va] != X[v, vb] else a for a, v in enumerate(feas)])
            swaps.append(tgt)
    scd = float(np.std(Gd))

    def xy_state(x, p, full):
        psi = np.full(D, D ** -0.5, complex)
        for l in range(p):
            g, b = x[2 * l], x[2 * l + 1]
            psi = psi * np.exp(-1j * g * Gd)
            if full:
                psi = _johnson_mix(HM, n, k, b, psi)
            else:
                c, sn = math.cos(b), math.sin(b)
                for tgt in swaps:
                    m = tgt != np.arange(D)
                    new = psi.copy(); new[m] = c * psi[m] - 1j * sn * psi[tgt[m]]; psi = new
        return psi
    for full in (False, True):
        warm = None
        for p in (1, 2, 3):
            fn = lambda x: float(np.abs(xy_state(_ang(x, scd), p, full)) ** 2 @ Gd)
            r = _train(fn, 2 * p, rng, starts=3, warm=warm, maxper=150); warm = r.x
            pr = np.abs(xy_state(_ang(r.x, scd), p, full)) ** 2
            res[f"xy{'full' if full else 'ring'}_p{p}"] = evaluate("xy", pr, Xd, {"E": float(r.fun)})
    # hardness of the instance for the classical descent
    return {**inst, "idx": idx.tolist(), "G_opt": Gopt, "T_opt": T_opt, "P": P, "n_feasible": int(len(feas)),
            "E_uniform": float(Gd.mean()), "res": res}


def _johnson_mix(A, n, k, beta, psi):
    """exp(-i beta A) psi for the Johnson-graph adjacency A (the complete XY mixer in the weight-k subspace):
    A has the k + 1 eigenvalues (k - t)(n - k - t) - t, so the exponential is the degree-k polynomial in A that
    interpolates exp(-i beta lambda_t) (exact; checked against expm_multiply)."""
    lam = np.array([(k - t) * (n - k - t) - t for t in range(k + 1)], float)
    c, r = (lam.max() + lam.min()) / 2, (lam.max() - lam.min()) / 2
    mu = (lam - c) / r; K = [psi]
    for _ in range(k):
        K.append((A @ K[-1] - c * K[-1]) / r)
    a = np.linalg.solve(np.vander(mu, k + 1, increasing=True), np.exp(-1j * beta * lam))
    return sum(a[m] * K[m] for m in range(k + 1))


def _ang(x, sc):
    """Parameters (g~, b) with g = g~ / sc so that the cost phase is O(1)."""
    x = np.asarray(x, float).copy(); x[0::2] = x[0::2] / sc
    return x


import math  # noqa: E402


def cmd_B(out, per, S, workers):
    from multiprocessing import Pool
    insts = [{"fam": fam, "s": s, "seed": sd, "n": 20, "k": 5} for fam in ("corr_c", "rand") for s in (4.0, 16.0) for sd in range(per)]
    path = os.path.join(HERE, out)
    done = set()
    if os.path.exists(path):
        done = {(json.loads(l)["fam"], json.loads(l)["s"], json.loads(l)["seed"]) for l in open(path)}
    todo = [(i, S) for i in insts if (i["fam"], i["s"], i["seed"]) not in done]
    print(f"{len(todo)} instances", flush=True)
    with Pool(workers, maxtasksperchild=1) as pool, open(path, "a") as fo:
        for r in pool.imap_unordered(run_B, todo):
            fo.write(json.dumps(r) + "\n"); fo.flush()
            print(f"{r['fam']:6s} s{r['s']:<4g} seed {r['seed']:2d}  " + "  ".join(
                f"{a}: P(opt) {v['p_opt'] if v['p_opt'] is not None else float('nan'):.3f} hit {v['hit_share']:.2f}" for a, v in r["res"].items()), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "A":
        cmd_A(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 200)
    elif sys.argv[1] == "B":
        cmd_B(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 100,
              int(sys.argv[5]) if len(sys.argv) > 5 else 8)
