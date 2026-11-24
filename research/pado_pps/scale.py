"""Does the quantum sample gain grow faster with N than the classical descent's success falls? Exploratory,
not pre-registered.

Instances: hybrid.make_sub on random N-item subsets of the N = 150 universe, k = N / 4, pair term all pairs,
families corr_c / rand, strength x4 / x16, seeds 0..4 (20 per N), N = 16, 20, 24, 28.
Quantum: Dicke start, complete-graph XY mixer exp(-i beta sum_{i<j} (XX + YY) / 2), no penalty, depth p = 1..3,
exact in the weight-k subspace (dimension C(N, k), 1.18 M at N = 28): the mixer is the Johnson-graph adjacency
A, applied as the degree-k polynomial that interpolates exp(-i beta lambda_t) on its k + 1 eigenvalues
(hybrid._johnson_mix), A psi by a neighbour table on the GPU. Angles minimise <G> (autograd + L-BFGS; p = 1 from a
grid, p > 1 from the previous depth). Reported: P(opt) (one shot), amplification P(opt) * C(N, k), and the share
of S shots whose swap descent (hybrid.descend) reaches the optimum.
Classical: share q of R uniform random k-subsets whose swap descent reaches the optimum.
argv: <out.jsonl> <N,N,...> [per] [S] [R]   (env SC_ONLY=<fam>:<s> runs one family x strength)
"""

import itertools
import json
import math
import os
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hard  # noqa: E402
import hybrid as HY  # noqa: E402

DEV = torch.device(os.environ.get("PF_DEVICE", "cpu"))
REL = 1e-9


def subspace(n, k, lin, Q):
    C = np.array(list(itertools.combinations(range(n), k)), dtype=np.int64)
    D = len(C)
    G = lin[C].sum(1)
    for a in range(k):
        for b in range(a + 1, k):
            G += Q[C[:, a], C[:, b]]
    masks = (np.int64(1) << C).sum(1)
    lut = np.full(1 << n, -1, dtype=np.int32); lut[masks] = np.arange(D, dtype=np.int32)
    nbr = np.empty((D, k * (n - k)), dtype=np.int32); cnt = np.zeros(D, dtype=np.int64)
    for i in range(n):
        bi = (masks >> i) & 1
        for j in range(n):
            if i == j:
                continue
            rows = np.flatnonzero((bi == 1) & (((masks >> j) & 1) == 0))
            nbr[rows, cnt[rows]] = lut[masks[rows] ^ (1 << i) ^ (1 << j)]; cnt[rows] += 1
    assert (cnt == k * (n - k)).all() and (nbr >= 0).all()
    del lut
    return C, G, nbr


class XYFull:
    def __init__(self, n, k, G, nbr):
        self.n, self.k = n, k
        self.G = torch.tensor(G, device=DEV)
        self.nbr = torch.tensor(nbr, dtype=torch.long, device=DEV)
        self.D = len(G)
        lam = np.array([(k - t) * (n - k - t) - t for t in range(k + 1)], float)
        self.lam = torch.tensor(lam, device=DEV)
        self.c, self.r = (lam.max() + lam.min()) / 2, (lam.max() - lam.min()) / 2
        mu = (lam - self.c) / self.r
        self.Vinv = torch.linalg.inv(torch.tensor(np.vander(mu, k + 1, increasing=True), dtype=torch.complex128, device=DEV))
        self.sc = float(np.std(G))

    def A(self, psi):
        out = torch.zeros_like(psi)
        for c0 in range(0, self.nbr.shape[1], 16):
            out = out + psi[self.nbr[:, c0:c0 + 16]].sum(1)
        return out

    def mix(self, beta, psi):
        a = self.Vinv @ torch.exp(-1j * beta * self.lam.to(torch.complex128))
        K = psi; out = a[0] * K
        for m in range(1, self.k + 1):
            K = (self.A(K) - self.c * K) / self.r
            out = out + a[m] * K
        return out

    def state(self, x):
        p = len(x) // 2
        psi = torch.full((self.D,), self.D ** -0.5, dtype=torch.complex128, device=DEV)
        for l in range(p):
            g = x[2 * l] / self.sc; b = x[2 * l + 1]
            psi = psi * torch.exp(-1j * g * self.G)
            psi = self.mix(b, psi)
        return psi

    def energy(self, x):
        psi = self.state(x)
        return (psi.abs() ** 2 * self.G).sum()

    def fg(self, x):
        xt = torch.tensor(np.asarray(x, float), device=DEV, requires_grad=True)
        e = self.energy(xt); e.backward()
        return float(e.detach()), xt.grad.cpu().numpy().copy()


def train(eng, p, warm, rng):
    from scipy.optimize import minimize
    if p == 1:
        grid = [(g, b) for g in np.linspace(-3, 3, 13) for b in np.linspace(-0.3, 0.3, 13)]
        with torch.no_grad():
            es = [float(eng.energy(torch.tensor(x, device=DEV))) for x in grid]
        starts = [np.array(grid[i]) for i in np.argsort(es)[:3]]
    else:
        starts = [np.r_[warm, 0.1, 0.02], np.r_[warm, -0.1, -0.02]]
    best = None
    for x0 in starts:
        r = minimize(eng.fg, x0, jac=True, method="L-BFGS-B", options={"maxiter": 200})
        if best is None or r.fun < best.fun:
            best = r
    return best


def run(inst, S, R):
    n, k, fam, s, seed = inst["n"], inst["k"], inst["fam"], inst["s"], inst["seed"]
    rng0 = np.random.default_rng([seed, 31, n])
    idx = np.sort(rng0.choice(150, n, replace=False))
    lin, Q = HY.make_sub(idx, k, fam, s, seed)
    t0 = time.time()
    C, G, nbr = subspace(n, k, lin, Q)
    o = int(np.argmin(G)); Gopt = float(G[o]); tol = REL * abs(Gopt)
    D = len(G)
    rng = np.random.default_rng([seed, n, int(s), len(fam), 9])
    # classical: random starts + descent
    qhits = 0
    for _ in range(R):
        T = list(rng.choice(n, k, replace=False))
        qhits += HY.descend(T, lin, Q)[0] <= Gopt + tol
    q = qhits / R
    t_cl = time.time() - t0
    eng = XYFull(n, k, G, nbr)
    res = {}; warm = None
    for p in (1, 2, 3):
        t1 = time.time()
        r = train(eng, p, warm, rng); warm = r.x
        with torch.no_grad():
            pr = (eng.state(torch.tensor(r.x, device=DEV)).abs() ** 2).cpu().numpy()
        pr = pr / pr.sum()
        shots = rng.choice(D, S, p=pr)
        raw = np.mean([G[sh] <= Gopt + tol for sh in shots])
        hy = np.mean([HY.descend(list(C[sh]), lin, Q)[0] <= Gopt + tol for sh in shots])
        res[f"p{p}"] = {"E": float(r.fun), "E_rel": (float(r.fun) - float(G.mean())) / (Gopt - float(G.mean())),
                        "P_opt": float(pr[o]), "amp": float(pr[o] * D), "raw_hit_share": float(raw),
                        "hybrid_hit_share": float(hy), "angles": list(map(float, r.x)), "seconds": time.time() - t1}
    del eng; torch.cuda.empty_cache() if DEV.type == "cuda" else None
    return {**inst, "idx": idx.tolist(), "D": D, "G_opt": Gopt, "q_random_descent": q, "R": R, "S": S,
            "classical_seconds": t_cl, "res": res, "seconds": time.time() - t0}


def main(out, Ns, per, S, R):
    path = os.path.join(HERE, out)
    done = set()
    if os.path.exists(path):
        done = {(r["n"], r["fam"], r["s"], r["seed"]) for r in map(json.loads, open(path))}
    fo = open(path, "a")
    only = os.environ.get("SC_ONLY")                      # e.g. "corr_c:4" to split the runs
    for n in Ns:
        for fam in ("corr_c", "rand"):
            for s in (4.0, 16.0):
                if only and only != f"{fam}:{s:g}":
                    continue
                for seed in range(per):
                    inst = {"n": n, "k": n // 4, "fam": fam, "s": s, "seed": seed}
                    if (n, fam, s, seed) in done:
                        continue
                    r = run(inst, S, R)
                    fo.write(json.dumps(r) + "\n"); fo.flush()
                    print(f"N={n} k={n // 4} {fam:6s} s{s:<4g} seed {seed}  D={r['D']}  q={r['q_random_descent']:.3f}  " + "  ".join(
                        f"p{p}: P(opt) {v['P_opt']:.2e} amp {v['amp']:.0f} hyb {v['hybrid_hit_share']:.2f}" for p, v in
                        ((k_[1], r['res'][k_]) for k_ in r['res'])) + f"  {r['seconds']:.0f}s", flush=True)


if __name__ == "__main__":
    Ns = [int(x) for x in sys.argv[2].split(",")]
    main(sys.argv[1], Ns, int(sys.argv[3]) if len(sys.argv) > 3 else 5, int(sys.argv[4]) if len(sys.argv) > 4 else 200,
         int(sys.argv[5]) if len(sys.argv) > 5 else 1000)
