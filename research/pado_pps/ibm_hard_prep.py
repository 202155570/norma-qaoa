"""Harder instances for the IBM run (README 8.3): coupling-strengthened N=20 variants.

The variant QUBO of small.instance(seed, d) is sum d_i x_i + sum_kept R_ij x_i x_j + lambda sum x_i.
Here the kept residual couplings R are multiplied by KAPPA (a stronger diversification penalty;
this is no longer the MaiQ objective) and lambda is re-tuned so p=1 QAOA selects 6 on average.
At KAPPA=1 greedy descent from the empty set finds the ground state on 19/20 instances; at 4 it
misses on 18/20.

Selection: seeds 0..NSEED-1; keep instances where greedy from the empty set misses the ground
state; rank by the share of random starts whose single-flip descent reaches it (lower = harder);
take the NPICK hardest. Seeds where p=1 picks fewer than 6 even at lambda=0 are skipped.
Per pick: PPS chain at w=5 and exact chain (state vector), p=1..PMAX, scored exactly; exact
ground-state probability and top-0.1% / top-1% energy shares of the noiseless circuit.
Where the chains differ by > 0.01 in exact energy, an extra circuit with the exact angles (key _exact).

argv: (none)   writes ibm/spec_hard.json
"""

import json
import os

import numpy as np

import ppsl
import small

HERE = os.path.dirname(os.path.abspath(__file__))
N, D, KAPPA, NSEED, NPICK, PMAX, W = 20, 3, 4.0, 30, 3, 4, 5
IDX = np.arange(1 << N)
ZALL = (1 - 2 * ((IDX[:, None] >> np.arange(N)) & 1)).astype(np.int8)   # Z of basis state k, qubit i


def hard_instance(seed):
    pb = small.instance(seed, D)                        # for syms and the unscaled terms
    J = pb["J"]
    lin_half = np.array(pb["h0"], float)                 # h0 = -d/2 - sum_incident R/4 ; J = R/4
    for i, j, v in J:
        lin_half[i] += v; lin_half[j] += v               # -> -d/2
    h0 = lin_half.copy()
    for i, j, v in J:
        h0[i] -= KAPPA * v; h0[j] -= KAPPA * v
    out = {"syms": pb["syms"], "h0": h0, "J": [(i, j, KAPPA * v) for i, j, v in J], "max_degree": pb["max_degree"]}
    return ppsl.tune_lambda(out)


def spectrum(h, J):
    E = ZALL @ np.asarray(h, float)
    for i, j, v in J:
        E = E + v * ZALL[:, i] * ZALL[:, j]
    return E


def descend(z, h, J):
    z = z.astype(float).copy()
    nb = [[] for _ in range(N)]
    for i, j, v in J:
        nb[i].append((j, v)); nb[j].append((i, v))
    while True:
        f = h + np.array([sum(v * z[j] for j, v in nb[i]) for i in range(N)])
        dE = -2 * z * f
        i = int(np.argmin(dE))
        if dE[i] >= -1e-12:
            return z
        z[i] = -z[i]


def e_of(z, h, J):
    return float(z @ h + sum(v * z[i] * z[j] for i, j, v in J))


def probs(h, J, x):
    """noiseless output distribution over basis states (index k: qubit i = bit i of k)"""
    diag = spectrum(h, J); p = len(x) // 2
    psi = np.full(1 << N, (1 << N) ** -0.5, dtype=complex)
    for l in range(p):
        psi = psi * np.exp(-1j * x[l] * diag)
        c, s = np.cos(x[p + l]), -1j * np.sin(x[p + l])
        t = psi.reshape((2,) * N)
        for q in range(N):
            t = c * t + s * np.flip(t, axis=N - 1 - q)
        psi = t.reshape(-1)
    return np.abs(psi) ** 2


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    cands, built, skipped = [], {}, []
    for seed in range(NSEED):
        try:
            pb = hard_instance(seed)
        except ValueError:          # p=1 selects < 6 even at lambda = 0: no lambda >= 0 gives 6
            skipped.append(seed); print(f"seed {seed}: skipped (no lambda >= 0 gives 6)", flush=True); continue
        built[seed] = pb; h = np.array(pb["h"]); J = pb["J"]
        E = spectrum(h, J); gs = int(np.argmin(E)); E0 = float(E[gs])
        miss = e_of(descend(np.ones(N), h, J), h, J) > E0 + 1e-9
        hit = np.mean([e_of(descend(rng.choice([-1.0, 1.0], N), h, J), h, J) <= E0 + 1e-9 for _ in range(200)])
        nsel = int((ZALL[gs] == -1).sum())
        print(f"seed {seed}: lambda {pb['lambda']:.3f} greedy miss {miss} descent hit {hit:.3f} GS selects {nsel}", flush=True)
        if miss:
            cands.append((hit, seed))
    picks = [s for _, s in sorted(cands)[:NPICK]]
    print("picked", picks, "skipped", skipped, flush=True)
    spec = []
    for seed in picks:
        pb = built[seed]; h = np.array(pb["h"]); J = pb["J"]
        E = spectrum(h, J); Es = np.sort(E); gs = int(np.argmin(E))
        q001, q01 = float(Es[int(1e-3 * len(Es))]), float(Es[int(1e-2 * len(Es))])
        ex = ppsl.ExactSV(N, list(h), J)
        exact = ppsl.chain(lambda p: ex, PMAX)
        pps = ppsl.chain(lambda p: ppsl.PPS(N, list(h), J, p, W), PMAX)
        E1 = ex.energy(exact[1])
        hit = np.mean([e_of(descend(rng.choice([-1.0, 1.0], N), h, J), h, J) <= Es[0] + 1e-9 for _ in range(1000)])
        for p in range(1, PMAX + 1):
            x = list(map(float, pps[p])); pr = probs(h, J, x); pe = probs(h, J, exact[p])
            Ep, Ee = ex.energy(x), ex.energy(exact[p])
            row = {"key": f"hard_s{seed}_p{p}", "n": N, "p": p, "seed": seed, "kappa": KAPPA, "lambda": pb["lambda"],
                   "syms": pb["syms"], "h": list(map(float, h)), "J": [[int(i), int(j), float(v)] for i, j, v in J],
                   "angles": x, "angles_exact": list(map(float, exact[p])),
                   "E_exact": Ep, "E_exact_source": "state vector", "E_exact_trained": Ee,
                   "capture": None if p == 1 else (E1 - Ep) / (E1 - min(Ee, Ep)),
                   "E_gs": float(Es[0]), "gs_index": gs, "gs_selects": int((ZALL[gs] == -1).sum()),
                   "E_q001": q001, "E_q01": q01, "E_max": float(Es[-1]),
                   "noiseless": {"P_gs": float(pr[gs]), "share_q001": float(pr[E <= q001].sum()),
                                 "share_q01": float(pr[E <= q01].sum())},
                   "noiseless_exact_angles": {"P_gs": float(pe[gs]), "share_q001": float(pe[E <= q001].sum())},
                   "descent_hit_rate": float(hit)}
            spec.append(row)
            print(f"{row['key']}: E pps->exact {Ep:+.4f} exact-trained {Ee:+.4f} GS {Es[0]:+.4f}  capture {row['capture']}  "
                  f"P_gs {pr[gs]:.4f} (exact angles {pe[gs]:.4f}, uniform {2.0 ** -N:.1e})  top0.1% {row['noiseless']['share_q001']:.3f}",
                  flush=True)
    # where the two chains' angles differ by more than 0.01 in exact energy, also run the
    # exact-trained angles (key suffix _exact) to separate training error from hardware noise
    extra = []
    for row in spec:
        row["angle_source"] = "pps_w5"
        if abs(row["E_exact"] - row["E_exact_trained"]) > 1e-2:
            e = dict(row, key=row["key"] + "_exact", angle_source="exact", angles=row["angles_exact"],
                     E_exact=row["E_exact_trained"], noiseless=row["noiseless_exact_angles"])
            extra.append(e)
    spec += extra
    print("exact-angle circuits", [e["key"] for e in extra], flush=True)
    os.makedirs(os.path.join(HERE, "ibm"), exist_ok=True)
    json.dump(spec, open(os.path.join(HERE, "ibm", "spec_hard.json"), "w"))
