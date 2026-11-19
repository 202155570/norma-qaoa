"""Recursive QAOA (RQAOA, Bravyi, Kliesch, Koenig, Tang, PRL 125, 260505 (2020)) on the Ising
problems of this study, with fields (the field-term generalisation: <Z_i> may fix a variable).

Ising: E(z) = c + sum_i h_i z_i + sum_{i<j} J_ij z_i z_j, z in {+1,-1} (z=-1: ETF selected).
One RQAOA step on the current problem (n > NC variables):
  1. train depth-p QAOA angles (|+>^n, p x [RZ(2 g h_i), RZZ(2 g J_ij), RX(2 b)]) on <E>
  2. compute M_i = <Z_i> and M_ij = <Z_i Z_j> on every edge
  3. take the largest |M|:  field -> z_i = sign(M_i);  edge -> z_j = sign(M_ij) z_i
     and substitute it into the problem (one variable fewer; new edges may appear)
When n <= NC the rest is solved by enumeration, then the substitutions are undone.
Expectation engines:
  sv   exact torch state vector (n <= ~22)                       - reference
  pps  padopauli at max_weight W, one compiled program per step   - large n
  ppsr pps, compiled program reused across steps (PPSReuse)       - large n, p >= 2 on cpu
QAOA training per step: p=1 from the grid of ppsl.grid_p1 (+ the previous step's angles), then
INTERP + L-BFGS-B up to p, as in ppsl.chain.

argv: check <seed>                N=20 coupling-strengthened instance: M from pps(w) vs sv at
                                   random and trained angles, p=1,2
      n20 <p> <engine> <w> <out>  RQAOA on the N=20 kappa=4 instances (seeds 0..29)
      p1check                     closed-form depth-1 engine (P1) vs SV on dense instances
      mv <out> [tags]             RQAOA p=1 (P1) on the mean-variance problems of mv.py (tags: N<N>_g<gamma>)
      big <p> <w> <out> [tags]    RQAOA (pps) on problem_{50,100,150}.json at kappa=1 and kappa=4, lambda set
                                   so that the Ising ground state selects 6 (see cmd_big); tags: comma list
                                   of N<N>_k<kappa> to run only those
env: PF_DEVICE (cpu/cuda), PADO_PRESET (cpu/gpu), RQAOA_NC (default 10), RQAOA_ENGINE (big: pps/ppsr),
     RQAOA_MV_FAST=1 (mv: lambda interval from counts <= 12 only, reference = MILP k-optimum),
     RQAOA_MV_ENGINE (mv: p1 default, or ppsr = padopauli on the dense couplings) with RQAOA_MV_W (default 3)
"""

import itertools
import json
import os
import sys
import time

import numpy as np
import torch
from scipy.optimize import minimize

import ppsl

HERE = os.path.dirname(os.path.abspath(__file__))
DEV = torch.device(os.environ.get("PF_DEVICE", "cpu"))
PRESET = os.environ.get("PADO_PRESET", "cpu")
NC = int(os.environ.get("RQAOA_NC", "10"))      # enumerate when this many variables remain
KAPPA = 4


# ---------------------------------------------------------------- expectation engines
class SV:
    def __init__(self, n, h, E, p):
        self.n, self.p, self.E = n, p, E
        idx = torch.arange(1 << n, device=DEV)
        self.Z = 1.0 - 2.0 * ((idx[:, None] >> torch.arange(n, device=DEV)[None, :]) & 1).double()
        diag = self.Z @ torch.tensor(h, dtype=torch.float64, device=DEV)
        for (i, j), v in E:
            diag = diag + v * self.Z[:, i] * self.Z[:, j]
        self.diag = diag
        self.ZZ = torch.stack([self.Z[:, i] * self.Z[:, j] for (i, j), _ in E], 1) if E else None

    def obs(self, x):                           # x: torch (2p,) -> (n + m,)
        n, p = self.n, self.p
        psi = torch.full((1 << n,), (1 << n) ** -0.5, dtype=torch.complex128, device=DEV)
        for l in range(p):
            psi = psi * torch.exp(-1j * x[l] * self.diag)
            c, s = torch.cos(x[p + l]), -1j * torch.sin(x[p + l])
            t = psi.reshape((2,) * n)
            for q in range(n):
                t = c * t + s * torch.flip(t, dims=[n - 1 - q])
            psi = t.reshape(-1)
        pr = psi.abs() ** 2
        out = [pr @ self.Z]
        if self.ZZ is not None:
            out.append(pr @ self.ZZ)
        return torch.cat(out).cpu()

    def obs_batch(self, X):
        return torch.stack([self.obs(x.to(DEV)) for x in X])


class PPS:
    def __init__(self, n, h, E, p, w):
        from padopauli import Circuit
        qc = Circuit(n_qubits=n); lay, kind, coef = [], [], []
        for i in range(n):
            qc.h(i)
        for l in range(p):
            for i in range(n):
                qc.rz(i, param_idx=len(coef)); lay.append(l); kind.append(0); coef.append(2.0 * h[i])
            for (i, j), v in E:
                qc.rzz(i, j, param_idx=len(coef)); lay.append(l); kind.append(0); coef.append(2.0 * v)
            for i in range(n):
                qc.rx(i, param_idx=len(coef)); lay.append(l); kind.append(1); coef.append(2.0)
        obs = [("Z", [i], 1.0) for i in range(n)] + [("ZZ", [i, j], 1.0) for (i, j), _ in E]
        t0 = time.time()
        qc.compile(observables=obs, preset=PRESET, dtype="float64", max_weight=w, verbosity=0)
        self.compile_s = time.time() - t0
        self.qc, self.p = qc, p
        self.sel = torch.tensor(lay) + p * torch.tensor(kind)
        self.coef = torch.tensor(coef, dtype=torch.float64)

    def obs(self, x):
        return self.qc.expvals(self.coef * x[self.sel]).reshape(-1).cpu()      # gpu preset returns cuda tensors

    def obs_batch(self, X):
        return self.qc.expvals(self.coef[None, :] * X[:, self.sel]).cpu()


class P1:
    """Exact depth-1 expectations for any coupling graph (dense included), closed form.
    State e^{-i b sum X} e^{-i g H}|+>^n with H = sum h_i Z_i + sum J_ij Z_i Z_j (the circuit above):
      <Z_u>     = sin 2b sin(2g h_u) prod_{w != u} cos(2g J_uw)
      <Z_u Z_v> = (sin 4b / 2) sin(2g J_uv) [cos(2g h_u) prod_{w != u,v} cos(2g J_uw)
                                           + cos(2g h_v) prod_{w != u,v} cos(2g J_vw)]
                + (sin^2 2b / 2) [cos(2g (h_u - h_v)) prod_{w != u,v} cos(2g (J_uw - J_vw))
                                 - cos(2g (h_u + h_v)) prod_{w != u,v} cos(2g (J_uw + J_vw))]
    (Heisenberg picture; checked against SV in cmd_p1check). Cost O(|E| n) per evaluation."""

    def __init__(self, n, h, E, p):
        assert p == 1, "closed form is depth 1 only"
        self.n, self.p = n, 1
        self.h = torch.tensor(np.asarray(h, float), dtype=torch.float64)
        Jm = np.zeros((n, n))
        for (i, j), v in E:
            Jm[i, j] = Jm[j, i] = v
        self.J = torch.tensor(Jm)
        self.U = torch.tensor([i for (i, _), _ in E], dtype=torch.long)
        self.V = torch.tensor([j for (_, j), _ in E], dtype=torch.long)
        m = len(E)
        mask = torch.zeros((m, n), dtype=torch.bool)
        if m:
            mask[torch.arange(m), self.U] = True; mask[torch.arange(m), self.V] = True
        self.mask = mask
        self.JU, self.JV = self.J[self.U], self.J[self.V]                 # (m, n)
        self.Juv = self.J[self.U, self.V]

    def obs(self, x):
        g, b = x[0], x[1]
        one = torch.ones((), dtype=torch.float64)
        CJ = torch.cos(2 * g * self.J)
        Mz = torch.sin(2 * b) * torch.sin(2 * g * self.h) * CJ.prod(1)
        if len(self.U) == 0:
            return Mz
        hu, hv = self.h[self.U], self.h[self.V]
        Pu = torch.where(self.mask, one, torch.cos(2 * g * self.JU)).prod(1)
        Pv = torch.where(self.mask, one, torch.cos(2 * g * self.JV)).prod(1)
        Dm = torch.where(self.mask, one, torch.cos(2 * g * (self.JU - self.JV))).prod(1)
        Dp = torch.where(self.mask, one, torch.cos(2 * g * (self.JU + self.JV))).prod(1)
        zz = (0.5 * torch.sin(4 * b) * torch.sin(2 * g * self.Juv) * (torch.cos(2 * g * hu) * Pu + torch.cos(2 * g * hv) * Pv)
              + 0.5 * torch.sin(2 * b) ** 2 * (torch.cos(2 * g * (hu - hv)) * Dm - torch.cos(2 * g * (hu + hv)) * Dp))
        return torch.cat([Mz, zz])

    def obs_batch(self, X, chunk=8):
        """Same formulas, vectorised over a batch of angle pairs (no autograd needed for the grid)."""
        outs = []
        one = torch.ones((), dtype=torch.float64)
        hu, hv = self.h[self.U], self.h[self.V]
        for X0 in torch.split(X, chunk):
            g = X0[:, 0][:, None, None]; b = X0[:, 1][:, None]
            Mz = torch.sin(2 * b) * torch.sin(2 * g[:, :, 0] * self.h[None]) * torch.cos(2 * g * self.J[None]).prod(2)
            if len(self.U) == 0:
                outs.append(Mz); continue
            Pu = torch.where(self.mask, one, torch.cos(2 * g * self.JU[None])).prod(2)
            Pv = torch.where(self.mask, one, torch.cos(2 * g * self.JV[None])).prod(2)
            Dm = torch.where(self.mask, one, torch.cos(2 * g * (self.JU - self.JV)[None])).prod(2)
            Dp = torch.where(self.mask, one, torch.cos(2 * g * (self.JU + self.JV)[None])).prod(2)
            g2 = g[:, :, 0]
            zz = (0.5 * torch.sin(4 * b) * torch.sin(2 * g2 * self.Juv[None]) * (torch.cos(2 * g2 * hu[None]) * Pu + torch.cos(2 * g2 * hv[None]) * Pv)
                  + 0.5 * torch.sin(2 * b) ** 2 * (torch.cos(2 * g2 * (hu - hv)[None]) * Dm - torch.cos(2 * g2 * (hu + hv)[None]) * Dp))
            outs.append(torch.cat([Mz, zz], 1))
        return torch.cat(outs)


class PPSReuse:
    """pps with one compiled program reused across RQAOA steps. The compiled program depends only on
    the circuit structure and the observables (angles x coefficients are passed at evaluation), so a
    step whose active variables and edges are a subset of the compiled ones reuses it: a removed
    variable gets zero field and zero couplings (its qubit decouples; Pauli paths through it carry a
    sin(0) factor and never lose their support on it, so the other expectations are those of the
    reduced circuit), a coupling changed by a substitution is just a new coefficient. Recompiled (on
    the current variables only) when a tie creates an edge the program does not have."""
    labelled = True

    def __init__(self, w):
        self.w, self.prog = w, {}

    def __call__(self, n, h, E, q, act):
        eo = [(act[i], act[j]) for (i, j), _ in E]
        c = self.prog.get(q)
        fresh = c is None or not (set(eo) <= c["eset"] and set(act) <= c["aset"])
        if fresh:
            c = {"pps": PPS(n, h, E, q, self.w), "act": list(act), "edges": eo, "aset": set(act), "eset": set(eo)}
            c["qpos"] = {u: a for a, u in enumerate(c["act"])}
            c["epos"] = {e: a for a, e in enumerate(c["edges"])}
            self.prog[q] = c
        return _ReuseView(c, act, h, E, eo, q, c["pps"].compile_s if fresh else 0.0)


class _ReuseView:
    def __init__(self, c, act, h, E, eo, p, compile_s):
        nq, ne = len(c["act"]), len(c["edges"])
        hc, Jc = np.zeros(nq), np.zeros(ne)
        for a, u in enumerate(act):
            hc[c["qpos"][u]] = h[a]
        for e, (_, v) in zip(eo, E):
            Jc[c["epos"][e]] = v
        self.pps, self.p, self.compile_s = c["pps"], p, compile_s
        self.coef = torch.tensor(np.tile(np.r_[2.0 * hc, 2.0 * Jc, 2.0 * np.ones(nq)], p), dtype=torch.float64)
        self.idx = torch.tensor([c["qpos"][u] for u in act] + [nq + c["epos"][e] for e in eo])

    def obs(self, x):
        return self.pps.qc.expvals(self.coef * x[self.pps.sel]).reshape(-1).cpu()[self.idx]

    def obs_batch(self, X):
        return self.pps.qc.expvals(self.coef[None, :] * X[:, self.pps.sel]).cpu()[:, self.idx]


# ---------------------------------------------------------------- QAOA training on one problem
def train(eng, h, E, x_prev=None):
    w = torch.tensor(np.r_[h, [v for _, v in E]], dtype=torch.float64)

    def fg(x):
        xt = torch.tensor(np.asarray(x, float), requires_grad=True)
        e = eng.obs(xt) @ w; e.backward()
        return float(e.detach()), xt.grad.numpy().copy()
    return fg, w


def qaoa(make_engine, h, E, p, prev):
    """Train depth 1..p; returns (angles at depth p, engine at depth p, energy, compile seconds)."""
    x, comp = None, 0.0
    for q in range(1, p + 1):
        eng = make_engine(q); comp += getattr(eng, "compile_s", 0.0)
        fg, w = train(eng, h, E)
        if q == 1:
            G = np.array([[g, b] for g in np.linspace(-2.0, 2.0, 21) for b in np.linspace(-0.75, 0.75, 13)])
            with torch.no_grad():
                e = (eng.obs_batch(torch.tensor(G)) @ w).numpy()
            starts = [G[a] for a in np.argsort(e)[:3]]
        else:
            starts = [ppsl.interp(x)]
        if prev is not None and len(prev) == 2 * q:
            starts.append(np.asarray(prev))
        r = min((minimize(fg, s, jac=True, method="L-BFGS-B", options={"maxiter": 200}) for s in starts),
                key=lambda r: r.fun)
        x = r.x
    return x, eng, float(r.fun), comp


# ---------------------------------------------------------------- RQAOA
def energy_z(z, h, J, c=0.0):
    return float(c + np.dot(h, z) + sum(v * z[i] * z[j] for i, j, v in J))


def rqaoa(h0, J0, p, make_engine, log=None):
    """h0: (n,), J0: [(i, j, v)]. make_engine(n, h, E, q). Returns z (n,) and the step log."""
    n0 = len(h0)
    h = {i: float(h0[i]) for i in range(n0)}
    J = {}
    for i, j, v in J0:
        key = (min(i, j), max(i, j)); J[key] = J.get(key, 0.0) + float(v)
    subs, steps, prev = [], [], None
    while len(h) > NC:
        act = sorted(h); pos = {u: a for a, u in enumerate(act)}
        hv = np.array([h[u] for u in act])
        E = [((pos[i], pos[j]), v) for (i, j), v in sorted(J.items())]
        t0 = time.time()
        if getattr(make_engine, "labelled", False):
            mk = lambda q: make_engine(len(act), hv, E, q, act)
        else:
            mk = lambda q: make_engine(len(act), hv, E, q)
        x, eng, e_q, comp = qaoa(mk, hv, E, p, prev)
        prev = x
        with torch.no_grad():
            M = eng.obs(torch.tensor(x)).numpy()
        a = int(np.argmax(np.abs(M)))
        sgn = 1.0 if M[a] >= 0 else -1.0
        if a < len(act):                                      # fix z_u = sgn
            u = act[a]
            for (i, j) in [k for k in J if u in k]:
                o = j if i == u else i
                h[o] += sgn * J.pop((i, j))
            h.pop(u); subs.append(("fix", u, sgn))
            what = ("field", [u], float(M[a]))
        else:                                                 # z_v = sgn z_u
            (pi, pj), _ = E[a - len(act)]
            u, v = act[pi], act[pj]
            for (i, j) in [k for k in J if v in k]:
                o = j if i == v else i
                val = J.pop((i, j))
                if o != u:
                    key = (min(o, u), max(o, u)); J[key] = J.get(key, 0.0) + sgn * val
                    if abs(J[key]) < 1e-14:
                        J.pop(key)
            h[u] += sgn * h.pop(v); subs.append(("tie", v, u, sgn))
            what = ("edge", [u, v], float(M[a]))
        row = {"n": len(act), "edges": len(E), "max_degree": int(max(np.bincount(np.array([k for e, _ in E for k in e]),
                                                                              minlength=len(act)))) if E else 0,
               "E_qaoa": e_q, "pick": what, "angles": list(map(float, x)), "compile_s": comp, "s": time.time() - t0}
        steps.append(row)
        if log:
            log(row)
    # enumerate the rest
    act = sorted(h); pos = {u: a for a, u in enumerate(act)}
    hv = np.array([h[u] for u in act]); Jr = [(pos[i], pos[j], v) for (i, j), v in J.items()]
    zs = 1 - 2 * ((np.arange(1 << len(act))[:, None] >> np.arange(len(act))) & 1)
    e = zs @ hv + sum(v * zs[:, i] * zs[:, j] for i, j, v in Jr)
    zbest = zs[int(np.argmin(e))]
    z = np.zeros(n0)
    for u in act:
        z[u] = zbest[pos[u]]
    for s in reversed(subs):
        if s[0] == "fix":
            z[s[1]] = s[2]
        else:
            z[s[1]] = s[3] * z[s[2]]
    return z, steps


# ---------------------------------------------------------------- ground truth and instances
def brute_gs(h, J):
    n = len(h)
    zs = 1 - 2 * ((np.arange(1 << n)[:, None] >> np.arange(n)) & 1).astype(np.int8)
    e = zs @ np.asarray(h) + sum(v * zs[:, i].astype(float) * zs[:, j] for i, j, v in J)
    order = np.argsort(e)
    return float(e[order[0]]), zs[order[0]].astype(float), float(e[order[1]]), e


def milp_gs(h, J):
    """Ising ground state by MILP: z = 1 - 2x."""
    from mip import solve
    n = len(h)
    lin = -2.0 * np.asarray(h, float); Q = np.zeros((n, n))
    for i, j, v in J:
        lin[i] -= 2.0 * v; lin[j] -= 2.0 * v
        Q[i, j] += 4.0 * v; Q[j, i] += 4.0 * v
    const = float(np.sum(h) + sum(v for _, _, v in J))
    s = solve(lin, Q, None)
    z = np.ones(n); z[s["T"]] = -1.0
    return const + s["G"], z, s


def kappa_problem(pb, kappa):
    """Scale the kept residual couplings by kappa and re-tune lambda (ibm_hard_prep.hard_instance)."""
    lin_half = np.array(pb["h0"], float)
    for i, j, v in pb["J"]:
        lin_half[i] += v; lin_half[j] += v
    h0 = lin_half.copy()
    for i, j, v in pb["J"]:
        h0[i] -= kappa * v; h0[j] -= kappa * v
    out = {"syms": pb["syms"], "h0": h0, "J": [(int(i), int(j), kappa * v) for i, j, v in pb["J"]]}
    return ppsl.tune_lambda(out)


def engine_factory(kind, w):
    if kind == "sv":
        return lambda n, h, E, q: SV(n, h, E, q)
    if kind == "ppsr":
        return PPSReuse(w)
    if kind == "p1":
        return lambda n, h, E, q: P1(n, h, E, q)
    return lambda n, h, E, q: PPS(n, h, E, q, w)


# ---------------------------------------------------------------- commands
def cmd_check(seed):
    import ibm_hard_prep as H
    pb = H.hard_instance(seed); n = len(pb["h"])
    E = [((i, j), v) for i, j, v in pb["J"]]
    rng = np.random.default_rng(0)
    for p in (1, 2):
        sv = SV(n, pb["h"], E, p)
        x_tr, _, e_tr, _ = qaoa(lambda q: SV(n, pb["h"], E, q), np.array(pb["h"]), E, p, None)
        for w in (4, 5, 6, 8):
            ps = PPS(n, pb["h"], E, p, w)
            for tag, x in [("random", rng.uniform(-1, 1, 2 * p)), ("trained", x_tr)]:
                xt = torch.tensor(x)
                with torch.no_grad():
                    a, b = sv.obs(xt).numpy(), ps.obs(xt).numpy()
                print(f"s{seed} p={p} w={w} {tag:7s} max|M_pps - M_sv| {np.abs(a - b).max():.2e}  "
                      f"argmax same {int(np.argmax(np.abs(a))) == int(np.argmax(np.abs(b)))}  compile {ps.compile_s:.1f}s", flush=True)


def cmd_p1check():
    """P1 (closed form) vs SV on dense instances: random fields and couplings, and the leading
    14 ETFs of the mean-variance problem (N=50, gamma=4) at its GS-6 lambda scale."""
    rng = np.random.default_rng(3)
    cases = []
    n = 12
    hr = rng.normal(0, 1, n); Er = [((i, j), float(rng.normal(0, 0.5))) for i in range(n) for j in range(i + 1, n)]
    cases.append(("random dense n=12", n, hr, Er))
    pb = json.load(open(os.path.join(HERE, "mv_problem_50_g4.json")))
    n = 14; Q = np.array(pb["Q"])[:n, :n]; lin = np.array(pb["lin"])[:n]
    hm = -(lin + 0.3) / 2 - Q.sum(1) / 4
    Em = [((i, j), float(Q[i, j] / 4)) for i in range(n) for j in range(i + 1, n)]
    cases.append(("mean-variance 14 ETFs", n, hm, Em))
    for name, n, h, E in cases:
        sv, p1 = SV(n, h, E, 1), P1(n, h, E, 1)
        worst = 0.0
        for _ in range(5):
            x = torch.tensor(rng.uniform(-2, 2, 2))
            with torch.no_grad():
                worst = max(worst, float((sv.obs(x) - p1.obs(x)).abs().max()))
        xt = torch.tensor(rng.uniform(-1, 1, 2), requires_grad=True)
        w = torch.tensor(np.r_[h, [v for _, v in E]])
        (p1.obs(xt) @ w).backward(); g1 = xt.grad.clone()
        xs = xt.detach().clone().requires_grad_(True)
        (sv.obs(xs) @ w).backward(); g2 = xs.grad.clone()
        print(f"{name}: max|M_P1 - M_SV| {worst:.2e}  max|grad diff| {float((g1 - g2).abs().max()):.2e}", flush=True)


def run_one(tag, h, J, E_gs, z_gs, p, eng, w, out, extra):
    t0 = time.time(); nsteps = []
    z, steps = rqaoa(np.asarray(h, float), J, p, engine_factory(eng, w), log=lambda r: nsteps.append(r))
    Ez = energy_z(z, h, J)
    row = {"tag": tag, "n": len(h), "p": p, "nc": NC, "engine": eng, "w": w if eng != "sv" else None,
           "E_rqaoa": Ez, "E_gs": E_gs, "hit_gs": bool(abs(Ez - E_gs) < 1e-9),
           "rel_gap": float((Ez - E_gs) / abs(E_gs)), "selected": int((z < 0).sum()),
           "selected_gs": int((np.asarray(z_gs) < 0).sum()),
           "n_field": sum(s["pick"][0] == "field" for s in steps), "n_edge": sum(s["pick"][0] == "edge" for s in steps),
           "max_degree_seen": max(s["max_degree"] for s in steps), "compile_s": sum(s["compile_s"] for s in steps),
           "seconds": time.time() - t0, "z": z.tolist(), "steps": steps, **extra}
    open(out, "a").write(json.dumps(row) + "\n")
    print(f"{tag:14s} n={row['n']:3d} p={p} {eng}{'' if eng == 'sv' else w}  E {Ez:+.4f}  GS {E_gs:+.4f}  "
          f"hit {row['hit_gs']}  gap {row['rel_gap']:.2e}  sel {row['selected']}/{row['selected_gs']}  "
          f"field/edge {row['n_field']}/{row['n_edge']}  maxdeg {row['max_degree_seen']}  {row['seconds']:.0f}s", flush=True)
    return row


def cmd_n20(p, eng, w, out):
    import ibm_hard_prep as H
    for seed in range(30):
        try:
            pb = H.hard_instance(seed)
        except ValueError:
            print(f"s{seed} skipped (lambda)"); continue
        E_gs, z_gs, E_2, _ = brute_gs(pb["h"], pb["J"])
        run_one(f"n20k4_s{seed}", pb["h"], pb["J"], E_gs, z_gs, p, eng, w, out, {"seed": seed, "E_2nd": E_2})


def lambda_gs(h0, J, k=6, iters=40):
    """lambda (h = h0 - lambda/2) whose Ising ground state selects k ETFs. The selected count of the
    ground state does not increase with lambda; bisect on it with the MILP ground state."""
    def count(lam):
        e, z, s = milp_gs(np.asarray(h0) - lam / 2, J)
        assert s["certified"], s
        return int((z < 0).sum()), e, z
    lo, hi = 0.0, 1.0
    while count(hi)[0] > k:
        lo, hi = hi, 2 * hi
    if count(lo)[0] < k:
        raise ValueError("fewer than k selected at lambda = 0")
    for _ in range(iters):
        mid = (lo + hi) / 2
        c = count(mid)[0]
        if c == k:
            return mid
        lo, hi = (mid, hi) if c > k else (lo, mid)
    c_lo, c_hi = count(lo)[0], count(hi)[0]
    return lo if abs(c_lo - k) <= abs(c_hi - k) else hi


def cmd_big(p, w, out, only=None):
    """problem_{50,100,150}.json at kappa = 1 and 4. The lambda stored there (p=1 QAOA selects 6 on
    average) makes every field negative, so the Ising ground state is the empty set; here lambda is
    instead set so that the ground state itself selects 6."""
    for N in (50, 100, 150):
        pb = json.load(open(os.path.join(HERE, f"problem_{N}.json")))
        J1 = [(int(i), int(j), float(v)) for i, j, v in pb["J"]]
        for kappa in (1, KAPPA):
            if only and f"N{N}_k{kappa}" not in only:
                continue
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
            lam = lambda_gs(h0, J)
            h = h0 - lam / 2
            E_gs, z_gs, s = milp_gs(h, J)
            assert s["certified"], s
            run_one(f"N{N}_k{kappa}", h, J, E_gs, z_gs, p, os.environ.get("RQAOA_ENGINE", "pps"), w, out,
                    {"N": N, "kappa": kappa, "lambda_gs6": lam, "lambda_study": pb["lambda"], "milp_s": s["seconds"]})



def lambda_k6(lin, Q, k=6, kmax0=12, f=None, picks=None, exclude_large=True):
    """Exact lambda interval in which the Ising ground state (penalty lambda * sum x) selects k, from
    cardinality-constrained optima: GS energy = min_m f(m) + lambda m with f(m) = min_{|T|=m} G(T)
    (f(0) = 0). f(m) by the RLT MILP of mip.solve for m <= kmax0; every larger m is excluded by the
    lower bound LB(m) = sum of the m smallest b_i(m), b_i(m) = lin_i + (1/2)(sum of the m-1 smallest
    Q_ij in row i), or solved exactly if the bound does not exclude it. Returns (lambda = interval midpoint, lo, hi, f, the k-optimum)."""
    from mip import solve
    n = len(lin)
    f = {0: 0.0} if f is None else f
    picks = {0: []} if picks is None else picks
    for m in range(1, kmax0 + 1):
        if m in f:
            continue
        s = solve(lin, Q, m); assert s["certified"], (m, s)
        f[m], picks[m] = s["G"], s["T"]
    # per-item bound: item i adds lin_i + (1/2) sum_{j in T} Q_ij >= lin_i + (1/2)(m-1 smallest of row i)
    Qs = np.sort(Q + np.diag(np.full(n, np.inf)), axis=1)[:, :n - 1]
    Qc = np.concatenate([np.zeros((n, 1)), np.cumsum(Qs, axis=1)], axis=1)
    LB = lambda m: np.sort(lin + 0.5 * Qc[:, m - 1])[:m].sum()
    while True:
        lo = max([(f[k] - f[m]) / (m - k) for m in f if m > k] + [-np.inf])
        hi = min([(f[m] - f[k]) / (k - m) for m in f if m < k] + [np.inf])
        if not lo < hi:
            return None, lo, hi, f, picks
        lam = 0.5 * (lo + hi)
        if not exclude_large:                                  # fast mode: interval from m <= kmax0 only
            return lam, lo, hi, f, picks
        bad = [m for m in range(kmax0 + 1, n + 1) if m not in f and LB(m) + lam * m < f[k] + lam * k + 1e-12]
        if not bad:
            return lam, lo, hi, f, picks
        for m in bad[:4]:
            s = solve(lin, Q, m); assert s["certified"], (m, s)
            f[m], picks[m] = s["G"], s["T"]


def cmd_mv(out, only=None):
    """RQAOA p=1 (closed form, exact for the dense couplings) on the mean-variance problems of mv.py,
    lambda set so that the Ising ground state selects 6; that ground state is compared with the
    MILP k=6 optimum of mv_result.json."""
    mres = json.load(open(os.path.join(HERE, "mv_result.json")))
    for N in (50, 100, 150):
        for g in (4, 12):
            if only and f"N{N}_g{g}" not in only:
                continue
            pb = json.load(open(os.path.join(HERE, f"mv_problem_{N}_g{g}.json")))
            h0, J = np.array(pb["h0"]), [(int(i), int(j), float(v)) for i, j, v in pb["J"]]
            t0 = time.time()
            f, picks = None, None
            fast = os.environ.get("RQAOA_MV_FAST") == "1"
            for kg in (6, 5, 7, 4, 8):                        # 6 if some lambda selects it, else the nearest count
                lam, lo, hi, f, picks = lambda_k6(np.array(pb["lin"]), np.array(pb["Q"]), kg, f=f, picks=picks,
                                                  exclude_large=not fast)
                if lam is not None:
                    break
            T6 = picks[kg]
            # fast mode: the reference is the MILP k-optimum; that it is also the Ising ground state is
            # proven only against m <= 12, so a lower RQAOA energy (negative gap) would show a larger-m GS
            h = h0 - lam / 2
            z_gs = np.ones(N); z_gs[T6] = -1.0
            E_gs = energy_z(z_gs, h, J)
            gs_pick = sorted(pb["syms"][i] for i in T6)
            k6 = sorted(mres[f"N{N}_g{g}"]["pick"])
            print(f"N{N}_g{g}: GS selects {kg}, lambda {lam:.4f} in ({lo:.4f}, {hi:.4f}), f(m) solved for m={sorted(f)}  "
                  f"GS == k=6 MILP optimum: {gs_pick == k6}  [{time.time() - t0:.0f}s]", flush=True)
            eng = os.environ.get("RQAOA_MV_ENGINE", "p1"); wmv = int(os.environ.get("RQAOA_MV_W", "3"))
            run_one(f"mvN{N}_g{g}", h, J, E_gs, z_gs, 1, eng, wmv, out,
                    {"N": N, "gamma": g, "k_gs": kg, "lambda_gs6": lam, "fast_lambda": fast, "lambda_interval": [lo, hi], "f_m": {str(m): v for m, v in f.items()},
                     "gs_equals_k6_optimum": gs_pick == k6, "gs_pick": gs_pick})


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "check":
        cmd_check(int(sys.argv[2]))
    elif c == "p1check":
        cmd_p1check()
    elif c == "mv":
        cmd_mv(sys.argv[2], sys.argv[3].split(",") if len(sys.argv) > 3 else None)
    elif c == "n20":
        cmd_n20(int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), sys.argv[5])
    elif c == "big":
        cmd_big(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5].split(",") if len(sys.argv) > 5 else None)
