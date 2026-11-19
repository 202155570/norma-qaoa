"""Standard QAOA vs multi-angle QAOA (ma-QAOA) on the coupling-strengthened N=20 instances
(ibm/spec_hard.json, README 8.3). Noiseless only.

Standard: per layer one gamma (all RZ and RZZ) and one beta (all RX) -> 2p parameters.
ma-QAOA:  per layer one gamma per field term (n), one per coupling (m), one beta per qubit (n)
          -> p (2n + m) parameters (70 per layer here).
Angles enter exactly as in ppsl / ibm_run: RZ(2 g h_i), RZZ(2 g J_ij), RX(2 b).

Training (L-BFGS-B): ma-QAOA starts from the exact-trained standard angles copied to every term
(so it can only improve on standard at the same p) and from NPERT perturbed copies of them; the
best start by the training objective is kept. Two trainers:
  exact - torch state vector, exact gradient
  pps   - padopauli at w=W (same compiled circuit as standard QAOA, one slot per gate),
          best start chosen by the PPS energy, then scored exactly
Metrics from the exact output distribution: energy, P(ground state), share in the lowest 0.1%
of the spectrum (E_q001 of the spec).

env: PF_DEVICE (cpu/cuda), PADO_PRESET (cpu/gpu)
argv: <pmax> <out.jsonl>      train and append rows
      check <out.jsonl>       p=1 ma rows: round every RZZ angle to the nearest multiple of pi (the circuit
                              then has no entangling gate) and compare P(ground state) before and after
"""

import json
import os
import sys
import time

import numpy as np
import torch
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
DEV = torch.device(os.environ.get("PF_DEVICE", "cpu"))
PRESET = os.environ.get("PADO_PRESET", "cpu")
W, NPERT, SIGMA, MAXIT = 5, 4, 0.05, 1000


class MaSV:
    """state vector with one angle per term; x = per layer [g_h (n), g_e (m), b (n)]"""

    def __init__(self, n, h, J):
        self.n, self.m = n, len(J)
        idx = torch.arange(1 << n, device=DEV)
        Z = 1.0 - 2.0 * ((idx[:, None] >> torch.arange(n, device=DEV)[None, :]) & 1).double()
        self.Zh = Z * torch.tensor(h, dtype=torch.float64, device=DEV)
        self.ZJ = torch.stack([v * Z[:, i] * Z[:, j] for i, j, v in J], 1)
        self.diag = self.Zh.sum(1) + self.ZJ.sum(1)

    def psi(self, x):
        n, m = self.n, self.m; L = 2 * n + m; p = len(x) // L
        psi = torch.full((1 << n,), (1 << n) ** -0.5, dtype=torch.complex128, device=DEV)
        for l in range(p):
            gh, ge, b = x[l * L:l * L + n], x[l * L + n:l * L + n + m], x[l * L + n + m:(l + 1) * L]
            psi = psi * torch.exp(-1j * (self.Zh @ gh + self.ZJ @ ge))
            t = psi.reshape((2,) * n)
            for q in range(n):
                t = torch.cos(b[q]) * t - 1j * torch.sin(b[q]) * torch.flip(t, dims=[n - 1 - q])
            psi = t.reshape(-1)
        return psi

    def fg(self, x):
        xt = torch.tensor(np.asarray(x, float), device=DEV, requires_grad=True)
        e = (self.psi(xt).abs() ** 2 @ self.diag); e.backward()
        return float(e.detach()), xt.grad.cpu().numpy().copy()

    def probs(self, x):
        with torch.no_grad():
            return (self.psi(torch.tensor(np.asarray(x, float), device=DEV)).abs() ** 2).cpu().numpy()


class MaPPS:
    """padopauli, one slot per gate (the circuit ppsl.PPS compiles), driven by per-term angles"""

    def __init__(self, n, h, J, p, w):
        from padopauli import Circuit
        qc = Circuit(n_qubits=n); scale = []
        for i in range(n):
            qc.h(i)
        for l in range(p):
            for i in range(n):
                qc.rz(i, param_idx=len(scale)); scale.append(2.0 * h[i])
            for i, j, v in J:
                qc.rzz(i, j, param_idx=len(scale)); scale.append(2.0 * v)
            for i in range(n):
                qc.rx(i, param_idx=len(scale)); scale.append(2.0)
        obs = [("Z", [i], float(h[i])) for i in range(n)] + [("ZZ", [i, j], float(v)) for i, j, v in J]
        t0 = time.time()
        qc.compile(observables=[obs], preset=PRESET, dtype="float64", max_weight=w, verbosity=0)
        self.compile_s = time.time() - t0
        self.qc, self.scale = qc, torch.tensor(scale, dtype=torch.float64)

    def fg(self, x):
        xt = torch.tensor(np.asarray(x, float), requires_grad=True)
        e = self.qc.expvals(self.scale * xt)[0]; e.backward()
        return float(e.detach()), xt.grad.numpy().copy()


def broadcast(xs, n, m):
    """standard angles [g_1..g_p, b_1..b_p] -> ma layout"""
    p = len(xs) // 2
    return np.concatenate([np.r_[np.full(n, xs[l]), np.full(m, xs[l]), np.full(n, xs[p + l])] for l in range(p)])


def train(fg, starts):
    return min((minimize(fg, s, jac=True, method="L-BFGS-B", options={"maxiter": MAXIT}) for s in starts),
               key=lambda r: r.fun)


def metrics(sv, x, s):
    pr = sv.probs(x); E = sv.diag.cpu().numpy()
    return {"E": float(pr @ E), "P_gs": float(pr[s["gs_index"]]), "share_q001": float(pr[E <= s["E_q001"] + 1e-12].sum()),
            "approx_ratio": float((pr @ E - s["E_max"]) / (s["E_gs"] - s["E_max"]))}


def check(path):
    spec = {s["key"]: s for s in json.load(open(os.path.join(HERE, "ibm", "spec_hard.json")))}
    for r in map(json.loads, open(path)):
        if r["method"] == "standard" or r["p"] != 1:
            continue
        s = spec[f"hard_s{r['seed']}_p1"]; n, h, J = s["n"], s["h"], s["J"]; m = len(J)
        x = np.array(r["angles"]); v = np.array([j[2] for j in J])
        th = 2 * x[n:n + m] * v                                  # RZZ(th)
        k = np.round(th / np.pi); dev = np.abs(th - np.pi * k)
        xr = x.copy(); xr[n:n + m] = np.pi * k / (2 * v)
        print(f"s{r['seed']} {r['method']:10s} |RZZ - k*pi| median {np.median(dev):.3f} max {dev.max():.3f}  "
              f"P_gs {r['P_gs']:.4f} -> rounded {MaSV(n, h, J).probs(xr)[s['gs_index']]:.4f}", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "check":
        check(sys.argv[2]); sys.exit()
    pmax, out = int(sys.argv[1]), sys.argv[2]
    spec = {s["key"]: s for s in json.load(open(os.path.join(HERE, "ibm", "spec_hard.json")))}
    seeds = sorted({s["seed"] for s in spec.values()})
    rng = np.random.default_rng(5)
    for seed in seeds:
        s1 = spec[f"hard_s{seed}_p1"]; n, h, J = s1["n"], s1["h"], s1["J"]; m = len(J)
        sv = MaSV(n, h, J)
        for p in range(1, pmax + 1):
            s = spec[f"hard_s{seed}_p{p}"]
            std = broadcast(s["angles_exact"], n, m)
            e_std = sv.fg(std)[0]
            assert abs(e_std - s["E_exact_trained"]) < 1e-8, (e_std, s["E_exact_trained"])   # same circuit
            starts = [std] + [std + SIGMA * rng.standard_normal(len(std)) for _ in range(NPERT)]
            rows = [dict(method="standard", n_params=2 * p, angles=list(map(float, std)), **metrics(sv, std, s))]
            t0 = time.time(); r = train(sv.fg, starts)
            rows.append(dict(method="ma_exact", n_params=len(std), train_s=time.time() - t0, nit=int(r.nit),
                             angles=r.x.tolist(), **metrics(sv, r.x, s)))
            t0 = time.time(); pps = MaPPS(n, h, J, p, W); r = train(pps.fg, starts)
            rows.append(dict(method=f"ma_pps_w{W}", n_params=len(std), train_s=time.time() - t0, compile_s=pps.compile_s,
                             E_pps_own=float(r.fun), nit=int(r.nit), angles=r.x.tolist(), **metrics(sv, r.x, s)))
            E1 = spec[f"hard_s{seed}_p1"]["E_exact_trained"]
            ref = min(x["E"] for x in rows)
            for x in rows:
                x.update(seed=seed, p=p, E_gs=s["E_gs"], E1_standard=E1,
                         capture_vs_best=(E1 - x["E"]) / (E1 - ref) if E1 - ref > 1e-9 else None)
                open(out, "a").write(json.dumps(x) + "\n")
                print(f"s{seed} p={p} {x['method']:10s} params {x['n_params']:4d}  E {x['E']:+.4f} (GS {s['E_gs']:+.4f})  "
                      f"AR {x['approx_ratio']:.4f}  P_gs {x['P_gs']:.4f}  top0.1% {x['share_q001']:.3f}"
                      + (f"  pps-own {x['E_pps_own']:+.4f}" if "E_pps_own" in x else "")
                      + (f"  [{x['train_s']:.0f}s, {x['nit']} it]" if "train_s" in x else ""), flush=True)
