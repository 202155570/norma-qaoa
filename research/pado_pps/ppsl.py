"""Train QAOA angles on the PADO surrogate and score them exactly.

Problem: the PADO variant of the MaiQ objective (see build.py) on any ETF subset, coupling
degree cap d, lambda set so that p=1 QAOA (exact optimum) selects 6 ETFs on average.
Circuit: |+>^n, p x [exp(-i g C) exp(-i b sum X)].

Two training chains per instance, each p=1 from a grid then INTERP + L-BFGS for p=2..pmax:
  exact  - exact energies and gradients (torch state vector, n <= 22)
  pps    - padopauli surrogate at max_weight w, gradients by autograd
Both chains' angles are scored with the exact energy. Score of the PPS chain at depth p:
  extra-gain capture = (E1* - E(pps angles)) / (E1* - E(exact angles)),
  E1* = exact-trained p=1 energy. Criterion (operator, 2026-11-03): >= 0.90.
"""

import itertools
import math
import os
import time

import numpy as np
import torch
from scipy.optimize import minimize
from scipy.stats import rankdata

from lc import LightCone

WS, WC, WCAP, RHO_CAP, K = 1.0, 0.5, 2.0, 0.70, 6
# Execution targets. PADO_PRESET: padopauli compile preset (cpu / gpu / hybrid).
# PF_DEVICE: torch device for the exact state vector (cpu / cuda). Defaults reproduce the
# measurements in this directory; the GPU settings are untested here (no GPU on the dev machine).
PADO_PRESET = os.environ.get("PADO_PRESET", "cpu")
DEVICE = torch.device(os.environ.get("PF_DEVICE", "cpu"))


def make_problem(P, syms, deg):
    """P: T x n prices of the subset. Returns the variant's Ising h0 (lambda = 0) and J."""
    n = P.shape[1]
    ret = [P[-1] / P[-1 - d_] - 1.0 for d_ in (63, 126, 252)]
    S = (rankdata(sum(ret) / 3.0, method="average") - 1.0) / (n - 1)
    rho = np.corrcoef(np.diff(np.log(P[-127:]), axis=0).T)
    Q = WC * np.maximum(rho, 0.0) + WCAP * (rho > RHO_CAP)
    np.fill_diagonal(Q, 0.0)
    lin = -WS * S
    iu = np.triu_indices(n, 1)
    A = np.zeros((len(iu[0]), n + 1)); A[:, 0] = 1.0
    A[np.arange(len(iu[0])), 1 + iu[0]] = 1.0; A[np.arange(len(iu[0])), 1 + iu[1]] = 1.0
    coef = np.linalg.lstsq(A, Q[iu], rcond=None)[0]
    a = coef[1:]
    R = Q - coef[0] - a[:, None] - a[None, :]
    d = lin + (K - 1) * a
    dg = np.zeros(n, int); kept = []
    for i, j in sorted(zip(*iu), key=lambda e: (not rho[e] > RHO_CAP, -abs(R[e]))):
        if dg[i] < deg and dg[j] < deg:
            kept.append((int(i), int(j), float(R[i, j]))); dg[i] += 1; dg[j] += 1
    h0 = -d / 2.0
    for i, j, v in kept:
        h0[i] -= v / 4.0; h0[j] -= v / 4.0
    return {"syms": syms, "h0": h0, "J": [(i, j, v / 4.0) for i, j, v in kept], "max_degree": int(dg.max())}


def grid_p1(f):
    grid = [np.array([g, b]) for g in np.linspace(-2.0, 2.0, 21) for b in np.linspace(-0.75, 0.75, 13)]
    vals = [f(x) for x in grid]
    return [grid[a] for a in np.argsort(vals)[:3]]


def tune_lambda(pb, from_brentq=True):
    from scipy.optimize import brentq
    n = len(pb["h0"])

    def p1(lam):
        m = LightCone(n, pb["h0"] - lam / 2, pb["J"], 1)
        r = min((minimize(m.energy, s, method="L-BFGS-B") for s in grid_p1(m.energy)), key=lambda r: r.fun)
        return r, m.weight(r.x)
    f = lambda lam: p1(lam)[1] - K
    lo, hi = 0.0, 0.5
    while f(hi) > 0:
        lo, hi = hi, hi * 2
    lam = brentq(f, lo, hi, xtol=1e-4)
    pb["lambda"] = lam; pb["h"] = pb["h0"] - lam / 2
    return pb


def interp(x):
    p = len(x) // 2
    out = []
    for v in (x[:p], x[p:]):
        v = np.concatenate([[0.0], v, [0.0]])
        out.append([(i / p) * v[i] + ((p - i) / p) * v[i + 1] for i in range(p + 1)])
    return np.concatenate(out)


class ExactSV:
    """torch state vector, energy and gradient."""

    def __init__(self, n, h, J):
        self.n = n
        idx = torch.arange(1 << n, device=DEVICE)
        Z = 1.0 - 2.0 * ((idx[:, None] >> torch.arange(n, device=DEVICE)[None, :]) & 1).double()
        diag = Z @ torch.tensor(h, dtype=torch.float64, device=DEVICE)
        for i, j, v in J:
            diag = diag + v * Z[:, i] * Z[:, j]
        self.diag = diag

    def _E(self, x):
        n = self.n; p = len(x) // 2
        psi = torch.full((1 << n,), (1 << n) ** -0.5, dtype=torch.complex128, device=DEVICE)
        for l in range(p):
            psi = psi * torch.exp(-1j * x[l] * self.diag)
            c, s = torch.cos(x[p + l]), -1j * torch.sin(x[p + l])
            t = psi.reshape((2,) * n)
            for q in range(n):
                t = c * t + s * torch.flip(t, dims=[n - 1 - q])
            psi = t.reshape(-1)
        return (psi.abs() ** 2 @ self.diag)

    def energy(self, x):
        with torch.no_grad():
            return float(self._E(torch.tensor(np.asarray(x, float))))

    def fg(self, x):
        xt = torch.tensor(np.asarray(x, float), requires_grad=True)
        e = self._E(xt); e.backward()
        return float(e.detach()), xt.grad.numpy().copy()


class PPS:
    def __init__(self, n, h, J, p, w):
        from padopauli import Circuit
        qc = Circuit(n_qubits=n); meta = []
        for i in range(n):
            qc.h(i)
        for l in range(p):
            for i in range(n):
                qc.rz(i, param_idx=len(meta)); meta.append((l, 0, 2.0 * h[i]))
            for i, j, v in J:
                qc.rzz(i, j, param_idx=len(meta)); meta.append((l, 0, 2.0 * v))
            for i in range(n):
                qc.rx(i, param_idx=len(meta)); meta.append((l, 1, 2.0))
        obs = [("Z", [i], float(h[i])) for i in range(n)] + [("ZZ", [i, j], float(v)) for i, j, v in J]
        t0 = time.time()
        qc.compile(observables=[obs], preset=PADO_PRESET, dtype="float64", max_weight=w, verbosity=0)
        self.compile_s = time.time() - t0
        self.qc, self.p = qc, p
        self.lay = torch.tensor([m[0] for m in meta]); self.kind = torch.tensor([m[1] for m in meta])
        self.coef = torch.tensor([m[2] for m in meta], dtype=torch.float64)

    def _E(self, xt):
        p = self.p
        th = self.coef * torch.where(self.kind == 0, xt[self.lay], xt[p + self.lay])
        return self.qc.expvals(th)[0]

    def energy(self, x):
        with torch.no_grad():
            return float(self._E(torch.tensor(np.asarray(x, float))))

    def fg(self, x):
        xt = torch.tensor(np.asarray(x, float), requires_grad=True)
        e = self._E(xt); e.backward()
        return float(e.detach()), xt.grad.numpy().copy()


def step(m, x_prev):
    """One chain step: p=1 from the grid (x_prev None), else INTERP of the depth-(p-1) angles."""
    starts = grid_p1(m.energy) if x_prev is None else [interp(np.asarray(x_prev, float))]
    return min((minimize(m.fg, s, jac=True, method="L-BFGS-B", options={"maxiter": 200}) for s in starts),
               key=lambda r: r.fun)


def chain(make_model, pmax, log=None):
    """INTERP chain; make_model(p) -> object with energy/fg. Returns {p: angles}."""
    out = {}; x = None
    for p in range(1, pmax + 1):
        t0 = time.time()
        m = make_model(p)
        r = step(m, x)
        x = r.x; out[p] = x.tolist()
        if log:
            log(p, r.fun, time.time() - t0, getattr(m, "compile_s", None))
    return out
