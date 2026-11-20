"""RQAOA on the hard problems of hard.py (dense, strong, mixed-sign pair terms) whose k-optimum the MILP
certified (hard.jsonl at 300 s, hard_long.jsonl at 1 h). Exploratory, not pre-registered.

Problems: the 6 certified only in the 1-hour rerun and the 6 slowest certified within 300 s.
Ising form (x = (1 - z)/2, z = -1 selected, cardinality by a penalty lambda * sum x), as mv.py:
  J_ij = Q_ij / 4,  h_i = -(lin_i + lambda) / 2 - sum_{j != i} Q_ij / 4
lambda: the ground state of the penalised problem selects k when f(k) + lambda k < f(m) + lambda m for
every m != k, f(m) = min_{|T|=m} G(T). f(k) is the certified MILP optimum; f(m) for m != k (1 .. 2k + 10)
is the best of 300 swap-search starts (an upper bound, not certified: certifying them takes MILP hours on
these problems). lambda is the midpoint of the resulting interval. If the true f(m) is lower for some m,
the true ground state may select m instead of k; a run that ends with another count is reported as such.

penalty quad (argv): P (sum x - k)^2 instead, the usual QUBO cardinality encoding, needed when f(m) is not
convex around k (mixed-sign pair terms: no lambda selects k). In x: lin' = lin + P (1 - 2k), Q' = Q + 2P.
P = 2 * max_m (f(k) - f(m)) / (m - k)^2 with f(m) from swap search for m = 1 .. 2k + 10 (300 starts) and
every 5th m up to N - 1 (30 starts), f(N) exact; same caveat (upper bounds on f(m), so P may be too small).

Scoring: hit = RQAOA ends with exactly k selected and G(T) equals the certified optimum (1e-9 relative).
Also reported: the Ising energy of the RQAOA state against that of the optimum (a lower one would show
that lambda let another count win).

Methods (same recursion of rqaoa.rqaoa, last NC = 10 variables enumerated):
  p1      RQAOA p = 1, closed-form correlations (exact for any coupling density)
  seqfix  the coefficients instead of correlations (compare.Coef): the classical counterpart
  ppsr    RQAOA p = 1 with padopauli (PPSReuse, weight cut w; GPU with PADO_PRESET=gpu)
argv: run <out.jsonl> <engine> <workers> <linear|quad> [w] [keys,...]
"""

import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hard  # noqa: E402

LONG = ["N150_k6_corr_c_1.0_s16", "N100_k15_rand_1.0_s4", "N100_k15_rand_1.0_s16", "N150_k15_rand_1.0_s4",
        "N150_k15_cov_1.0_s16", "N100_k15_corr_c_1.0_s16"]
REL = 1e-9


def problems():
    scan = {json.loads(l)["key"]: json.loads(l) for l in open(os.path.join(HERE, "hard.jsonl"))}
    long_ = {json.loads(l)["key"]: json.loads(l) for l in open(os.path.join(HERE, "hard_long.jsonl"))}
    slow = sorted((r for r in scan.values() if r["milp_certified"]), key=lambda r: -r["milp_seconds"])[:6]
    out = []
    for key in LONG:
        r = long_[key]; assert r["milp_certified"], key
        out.append(r)
    out += slow
    return out


def swap_f(lin, Q, m, rng, starts=300):
    return min(e for e, _ in hard.swap_search(lin, Q, m, rng, starts))


def run_one(args):
    ref, eng_kind, w, pen = args
    import torch
    torch.set_num_threads(int(os.environ.get("HR_THREADS", "1")))
    import rqaoa as R
    N, k = ref["N"], ref["k"]
    lin, Q = hard.make(N, k, ref["family"], ref["density"], ref["strength"])
    T_opt = ref["milp_T"]; G_opt = ref["milp_G"]
    assert abs(hard.energy(T_opt, lin, Q) - G_opt) < 1e-9
    t0 = time.time()
    rng = np.random.default_rng([N, k, 99])
    f = {0: 0.0, k: G_opt}
    for m in range(1, min(N - 1, 2 * k + 10) + 1):
        if m != k:
            f[m] = swap_f(lin, Q, m, rng)
    if pen == "quad":
        for m in range(2 * k + 15, N, 5):
            f[m] = swap_f(lin, Q, m, rng, 30)
        f[N] = float(lin.sum() + Q.sum() / 2.0)
    lo = max((f[k] - f[m]) / (m - k) for m in f if m > k)
    hi = min((f[m] - f[k]) / (k - m) for m in f if m < k)
    lam_s = time.time() - t0
    row = {"key": ref["key"], "N": N, "k": k, "family": ref["family"], "density": ref["density"],
           "strength": ref["strength"], "engine": eng_kind, "w": w, "penalty": pen, "G_opt": G_opt,
           "milp_seconds": ref["milp_seconds"], "lambda_interval": [lo, hi], "lambda_seconds": lam_s}
    iu = np.triu_indices(N, 1)
    if pen == "linear":
        if not lo < hi:
            row.update(status="no_lambda")
            return row
        lam = 0.5 * (lo + hi); lin_p, Q_p = lin + lam, Q
    else:
        P = 2.0 * max(max((f[k] - f[m]) / (m - k) ** 2 for m in f if m != k), 1e-6)
        lam = P; lin_p = lin + P * (1 - 2 * k); Q_p = Q + 2.0 * P; np.fill_diagonal(Q_p, 0.0)
    h = -lin_p / 2.0 - Q_p.sum(1) / 4.0
    J = [(int(i), int(j), float(Q_p[i, j] / 4.0)) for i, j in zip(*iu) if Q_p[i, j] != 0.0]
    if eng_kind == "seqfix":
        from compare import Coef
        make = lambda n_, h_, E_, q: Coef(n_, h_, E_, q)
    else:
        make = R.engine_factory(eng_kind, w)
    t1 = time.time()
    z, steps = R.rqaoa(h, J, 1, make)
    T = sorted(int(i) for i in np.flatnonzero(z < 0))
    G = hard.energy(T, lin, Q) if T else 0.0
    z_opt = np.ones(N); z_opt[T_opt] = -1.0
    E_r, E_o = R.energy_z(z, h, J), R.energy_z(z_opt, h, J)
    row.update(status="ok", lam=lam, selected=len(T), G=G, rel_gap=(G - G_opt) / abs(G_opt),
               hit=bool(len(T) == k and G <= G_opt + REL * abs(G_opt)), overlap=len(set(T) & set(T_opt)),
               E_ising=E_r, E_ising_opt=E_o, ising_lower_than_opt=bool(E_r < E_o - REL * abs(E_o)),
               n_field=sum(s["pick"][0] == "field" for s in steps), n_edge=sum(s["pick"][0] == "edge" for s in steps),
               seconds=time.time() - t1, T=T)
    return row


def main(out, eng_kind, workers, pen, w, only):
    path = os.path.join(HERE, out)
    done = {(json.loads(l)["key"], json.loads(l)["engine"]) for l in open(path)} if os.path.exists(path) else set()
    todo = [(r, eng_kind, w, pen) for r in problems() if (r["key"], eng_kind) not in done and (not only or r["key"] in only)]
    print(f"{len(todo)} to run, engine {eng_kind}", flush=True)
    with Pool(workers, maxtasksperchild=1) as pool, open(path, "a") as fo:
        for r in pool.imap_unordered(run_one, todo):
            fo.write(json.dumps(r) + "\n"); fo.flush()
            if r["status"] != "ok":
                print(f"{r['key']:26s} {r['status']} {r['lambda_interval']}", flush=True)
                continue
            print(f"{r['key']:26s} {eng_kind:6s} hit {r['hit']!s:5} sel {r['selected']}/{r['k']} gap {r['rel_gap']:+.2e} "
                  f"overlap {r['overlap']}/{r['k']} ising_lower {r['ising_lower_than_opt']} field/edge {r['n_field']}/{r['n_edge']} "
                  f"{r['seconds']:.0f}s (lambda {r['lambda_seconds']:.0f}s)", flush=True)


if __name__ == "__main__":
    assert sys.argv[1] == "run"
    out, eng_kind, workers = sys.argv[2], sys.argv[3], int(sys.argv[4])
    pen = sys.argv[5]; assert pen in ("linear", "quad")
    w = int(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] != "-" else None
    only = sys.argv[7].split(",") if len(sys.argv) > 7 else None
    main(out, eng_kind, workers, pen, w, only)
