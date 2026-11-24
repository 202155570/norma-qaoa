"""Does training the angles on CVaR instead of the mean change the scaling result (hard.md result 10)?

Same 80 instances, same circuit (Dicke start, complete-graph XY mixer, p = 1..3, exact in the weight-k subspace)
as scale.py; only the training objective changes. CVaR_alpha = mean of G over the lowest-G alpha share of the
output distribution (the states are sorted by G once, so it is differentiable in the angles). alpha = 0.1, 0.01.
Starts: the CVaR p = 1 grid's best 3 plus the mean-trained angles stored in the scale_*.jsonl record (p > 1: the
CVaR angles of depth p - 1 extended, plus the stored mean-trained angles of depth p), so CVaR training never
starts worse than the mean-trained point. Reported per depth: P(opt), amplification, share of S shots whose swap
descent reaches the optimum (same S, same descent as scale.py). q (classical) is taken from the stored record.

Decision rule, fixed before the run. On the 40 problems with N = 24, 28, at p = 3, for either alpha, CVaR changes
the conclusion if (a) the median over problems of amp(CVaR) / amp(mean) is >= 2, or (b) the mean of
hybrid hit share(CVaR) - hybrid hit share(mean) is >= +5 %p with a bootstrap 95% CI above 0.
Otherwise the quantum side is closed as proposed on the deck's next-steps slide.
argv: <out.jsonl> [alpha,alpha,...]   (env PF_DEVICE=cuda)
"""

import glob
import json
import os
import sys
import time

import numpy as np
import torch
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hybrid as HY  # noqa: E402
import scale as SC  # noqa: E402

DEV = SC.DEV


class CVaR:
    def __init__(self, eng, alpha):
        self.eng, self.alpha = eng, alpha
        self.order = torch.argsort(eng.G)
        self.Gs = eng.G[self.order]

    def value(self, x):
        ps = (self.eng.state(x).abs() ** 2)[self.order]
        excl = torch.cumsum(ps, 0) - ps
        w = torch.minimum(ps, torch.clamp(self.alpha - excl, min=0.0))
        return (w * self.Gs).sum() / self.alpha

    def fg(self, x):
        xt = torch.tensor(np.asarray(x, float), device=DEV, requires_grad=True)
        v = self.value(xt); v.backward()
        return float(v.detach()), xt.grad.cpu().numpy().copy()


def train(obj, p, warm, stored):
    starts = [np.asarray(stored, float)]
    if p == 1:
        grid = [(g, b) for g in np.linspace(-3, 3, 13) for b in np.linspace(-0.3, 0.3, 13)]
        with torch.no_grad():
            vs = [float(obj.value(torch.tensor(x, device=DEV))) for x in grid]
        starts += [np.array(grid[i]) for i in np.argsort(vs)[:3]]
    else:
        starts += [np.r_[warm, 0.1, 0.02], np.r_[warm, -0.1, -0.02]]
    best = None
    for x0 in starts:
        r = minimize(obj.fg, x0, jac=True, method="L-BFGS-B", options={"maxiter": 200})
        if best is None or r.fun < best.fun:
            best = r
    return best


def run(rec, alpha):
    n, k, fam, s, seed, S = rec["n"], rec["k"], rec["fam"], rec["s"], rec["seed"], rec["S"]
    idx = np.array(rec["idx"])
    lin, Q = HY.make_sub(idx, k, fam, s, seed)
    t0 = time.time()
    C, G, nbr = SC.subspace(n, k, lin, Q)
    o = int(np.argmin(G)); Gopt = float(G[o]); tol = SC.REL * abs(Gopt); D = len(G)
    assert abs(Gopt - rec["G_opt"]) <= 1e-9 * abs(Gopt)
    eng = SC.XYFull(n, k, G, nbr); obj = CVaR(eng, alpha)
    rng = np.random.default_rng([seed, n, int(s), len(fam), 19, int(round(1 / alpha))])
    res = {}; warm = None
    for p in (1, 2, 3):
        t1 = time.time()
        r = train(obj, p, warm, rec["res"][f"p{p}"]["angles"]); warm = r.x
        with torch.no_grad():
            pr = (eng.state(torch.tensor(r.x, device=DEV)).abs() ** 2).cpu().numpy()
        pr = pr / pr.sum()
        shots = rng.choice(D, S, p=pr)
        hy = np.mean([HY.descend(list(C[sh]), lin, Q)[0] <= Gopt + tol for sh in shots])
        res[f"p{p}"] = {"cvar": float(r.fun), "mean_E": float((pr * G).sum()), "P_opt": float(pr[o]),
                        "amp": float(pr[o] * D), "raw_hit_share": float(np.mean(G[shots] <= Gopt + tol)),
                        "hybrid_hit_share": float(hy), "angles": list(map(float, r.x)), "seconds": time.time() - t1}
    del eng, obj
    if DEV.type == "cuda":
        torch.cuda.empty_cache()
    return {k_: rec[k_] for k_ in ("n", "k", "fam", "s", "seed", "D", "G_opt", "q_random_descent", "S")} | {
        "alpha": alpha, "res": res, "mean_res": {p: {m: v[m] for m in ("P_opt", "amp", "hybrid_hit_share")}
                                                 for p, v in rec["res"].items()}, "seconds": time.time() - t0}


def main(out, alphas):
    recs = [json.loads(l) for f in sorted(glob.glob(os.path.join(HERE, "scale_*.jsonl"))) for l in open(f)]
    recs.sort(key=lambda r: (r["n"], r["fam"], r["s"], r["seed"]))
    path = os.path.join(HERE, out)
    done = set()
    if os.path.exists(path):
        done = {(r["alpha"], r["n"], r["fam"], r["s"], r["seed"]) for r in map(json.loads, open(path))}
    fo = open(path, "a")
    for alpha in alphas:
        for rec in recs:
            key = (alpha, rec["n"], rec["fam"], rec["s"], rec["seed"])
            if key in done:
                continue
            r = run(rec, alpha)
            fo.write(json.dumps(r) + "\n"); fo.flush()
            print(f"a={alpha:g} N={r['n']} {r['fam']:6s} s{r['s']:<4g} seed {r['seed']}  " + "  ".join(
                f"{p}: amp {v['amp']:.0f} (mean {r['mean_res'][p]['amp']:.0f}) hyb {v['hybrid_hit_share']:.2f} "
                f"({r['mean_res'][p]['hybrid_hit_share']:.2f})" for p, v in r["res"].items()) +
                f"  {r['seconds']:.0f}s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], [float(a) for a in (sys.argv[2] if len(sys.argv) > 2 else "0.1,0.01").split(",")])
