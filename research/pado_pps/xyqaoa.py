"""Constraint-preserving QAOA (Dicke start, ring XY mixer, depth 1) and an RQAOA built on it. Exploratory.

State  |psi> = U_M(beta) U_C(gamma) |D^n_r>
  |D^n_r>  uniform superposition of the C(n, r) basis states with exactly r selected (z = -1)
  U_C      exp(-i gamma C),  C = sum_i h_i z_i + sum_{i<j} J_ij z_i z_j
  U_M      ring XY mixer, parity order: gates G_ab = exp(-i beta (X_a X_b + Y_a Y_b) / 2) on the ring edges
           (pos, pos + 1 mod n) in layers A (even pos), B (odd pos), C (the edge (n-1, 0) when n is odd);
           U_M = L_C L_B L_A. Every gate keeps the number selected, so no penalty term is needed.
The ring runs over the active variables in a given order (default: sorted by the field h, so that ring
neighbours have similar linear terms).

Exact expectations for any n (no state vector):
  1. Heisenberg picture through the mixer: U_M^+ O U_M is a short sum of Pauli strings with coefficients
     polynomial in cos(beta), sin(beta) (light cone of Z_u: <= 6 ring sites).
  2. For a string P with X/Y on the set B and Z on the set A:
       <D| U_C^+ P U_C |D> = C(n,r)^-1 sum_{x: |x| = r, |x xor B| = r} phi_P(x) exp(i gamma (C(x xor B) - C(x)))
     C(x xor B) - C(x) = -2 sum_{b in B} h_b z_b - 2 sum_{b in B, w not in B} J_bw z_b z_w is linear in the z_w
     outside B, so for each assignment of z_B (|B|/2 selected) the sum over the other sites is one coefficient
     of prod_w (a_w + t b_w)  (an elementary symmetric polynomial), computed by a DP in O(n r).
  Checked against the state vector in the weight-r subspace (cmd check).

Training (depth 1): energy <C>(gamma, beta) = sum_u h_u <Z_u> + sum_e J_e <Z_u Z_v>; edges are subsampled
(uniform, fixed seed, scaled) when there are more than TRAIN_EDGES; grid in gamma x dense grid in beta,
then golden-section refinement of gamma. The correlations used for the decisions (<Z_u>) are exact.

RQAOA (fix moves only; ties would turn the count into a weighted one that the XY mixer does not keep):
  fix u = argmax |<Z_u>|, z_u = sign, keep the count r; r = 0 or r = n_active fixes the rest;
  <= NC active variables: enumerate the C(n, r) assignments.
"""

import itertools
import math
import os
import time

import numpy as np
import torch

DEV = torch.device(os.environ.get("PF_DEVICE", "cpu"))
TRAIN_EDGES = int(os.environ.get("XY_TRAIN_EDGES", "1500"))
CHUNK = int(os.environ.get("XY_CHUNK", "200000"))

# ---------------------------------------------------------------- Pauli algebra
_MUL = {("X", "Y"): (1j, "Z"), ("Y", "X"): (-1j, "Z"), ("Y", "Z"): (1j, "X"), ("Z", "Y"): (-1j, "X"),
        ("Z", "X"): (1j, "Y"), ("X", "Z"): (-1j, "Y")}


def _mul1(a, b):
    if a == "I":
        return 1.0, b
    if b == "I":
        return 1.0, a
    if a == b:
        return 1.0, "I"
    return _MUL[(a, b)]


def smul(p, q):
    """Product of two Pauli strings (tuples of (site, letter), sorted): (phase, string)."""
    d = dict(p); ph = 1.0
    for s, l in q:
        f, r = _mul1(d.get(s, "I"), l); ph *= f
        if r == "I":
            d.pop(s, None)
        else:
            d[s] = r
    return ph, tuple(sorted(d.items()))


def _anti(p, q):
    d = dict(p); n = 0
    for s, l in q:
        a = d.get(s, "I")
        if a != "I" and a != l:
            n += 1
    return n % 2 == 1


def _padd(acc, poly, f=1.0, mono=(0, 0)):
    for (a, b), v in poly.items():
        key = (a + mono[0], b + mono[1]); acc[key] = acc.get(key, 0.0) + f * v


def _pmul(p, q):
    out = {}
    for (a, b), v in p.items():
        for (c, d), w in q.items():
            key = (a + c, b + d); out[key] = out.get(key, 0.0) + v * w
    return out


def ring_layers(n):
    """Edges in ring positions, grouped in the layers applied in the order A, B, C."""
    A = [(i, i + 1) for i in range(0, n - 1, 2)]
    B = [(i, i + 1) for i in range(1, n - 1, 2)]
    C = []
    if n > 2:
        (B if n % 2 == 0 else C).append((n - 1, 0))
    return [L for L in (A, B, C) if L]


def heis(string, layers, n):
    """U_M^+ P U_M for a Pauli string in ring positions: {string: poly in (cos b, sin b)}."""
    cur = {string: {(0, 0): 1.0}}
    for L in reversed(layers):
        by_site = {}
        for a, b in L:
            by_site[a] = (a, b); by_site[b] = (a, b)
        for gate in L:
            a, b = gate
            if not any(s in (a, b) for st in cur for s, _ in st):
                continue
            for Q in (((min(a, b), "X"), (max(a, b), "X")), ((min(a, b), "Y"), (max(a, b), "Y"))):
                nxt = {}
                for st, poly in cur.items():
                    if _anti(st, Q):
                        _padd(nxt.setdefault(st, {}), poly, 1.0, (1, 0))
                        ph, qp = smul(Q, st)
                        _padd(nxt.setdefault(qp, {}), poly, 1j * ph, (0, 1))
                    else:
                        _padd(nxt.setdefault(st, {}), poly)
                cur = {s: {m: v for m, v in p.items() if abs(v) > 1e-15} for s, p in nxt.items()}
                cur = {s: p for s, p in cur.items() if p}
    return cur


def to_vars(expansion, ring):
    return {tuple(sorted((ring[s], l) for s, l in st)): p for st, p in expansion.items()}


# ---------------------------------------------------------------- expectations of strings in U_C|D>
class Strings:
    """A set of Pauli strings (in active-variable indices) and their exact expectations <D|U_C^+ P U_C|D>."""

    def __init__(self, strings, h, Jm, r):
        self.strings = list(strings)
        n = len(h); self.n, self.r = n, r
        self.norm = float(math.comb(n, r))
        rows_s, zB, Bm, Zm, ph, hz, m = [], [], [], [], [], [], []
        for si, st in enumerate(self.strings):
            Bs = [s for s, l in st if l in "XY"]; Zs = [s for s, l in st if l == "Z"]
            if len(Bs) % 2:
                continue
            half = len(Bs) // 2
            if r - half < 0 or r - half > n - len(Bs):
                continue
            let = dict(st)
            for sel in itertools.combinations(range(len(Bs)), half):
                z = np.ones(len(Bs)); z[list(sel)] = -1.0
                f = 1.0 + 0j
                for b, zb in zip(Bs, z):
                    if let[b] == "Y":
                        f *= 1j * zb
                rows_s.append(si); zB.append((Bs, z)); ph.append(f)
                hz.append(float(sum(h[b] * zb for b, zb in zip(Bs, z)))); m.append(r - half)
                Bm.append(Bs); Zm.append(Zs)
        R = len(rows_s); self.R = R
        self.row_s = torch.tensor(rows_s, dtype=torch.long, device=DEV)
        self.ph = torch.tensor(np.array(ph, complex), device=DEV)
        self.hz = torch.tensor(np.array(hz), device=DEV)
        self.m = torch.tensor(m, dtype=torch.long, device=DEV)
        # theta_row = sum_b z_b J[b, :]  (rows x n), masks
        Zb = np.zeros((R, n)); Bmask = np.zeros((R, n), bool); Zmask = np.zeros((R, n), bool)
        for i, ((Bs, z), Zs) in enumerate(zip(zB, Zm)):
            Zb[i, Bs] = z; Bmask[i, Bs] = True; Zmask[i, Zs] = True
        Jt = torch.tensor(Jm, device=DEV)
        self.theta = torch.tensor(Zb, device=DEV) @ Jt
        self.Bmask = torch.tensor(Bmask, device=DEV); self.Zsign = torch.tensor(np.where(Zmask, -1.0, 1.0), device=DEV)

    def values(self, gamma):
        """Expectation of every string (complex, len(strings))."""
        out = torch.zeros(len(self.strings), dtype=torch.complex128, device=DEV)
        if self.R == 0:
            return out
        g = float(gamma)
        for c0 in range(0, self.R, CHUNK):
            sl = slice(c0, c0 + CHUNK)
            th = self.theta[sl]
            a = torch.exp(-2j * g * th); b = torch.exp(2j * g * th) * self.Zsign[sl]
            Bm = self.Bmask[sl]
            a = torch.where(Bm, torch.ones_like(a), a); b = torch.where(Bm, torch.zeros_like(b), b)
            coef = torch.zeros((th.shape[0], self.r + 1), dtype=torch.complex128, device=DEV); coef[:, 0] = 1.0
            for w in range(self.n):
                new = coef * a[:, w:w + 1]
                new[:, 1:] += coef[:, :-1] * b[:, w:w + 1]
                coef = new
            val = coef.gather(1, self.m[sl][:, None])[:, 0] * self.ph[sl] * torch.exp(-2j * g * self.hz[sl])
            out.index_add_(0, self.row_s[sl], val)
        return out / self.norm


# ---------------------------------------------------------------- engine for one RQAOA step
class XY1:
    def __init__(self, h, Jm, r, ring=None, train_edges=TRAIN_EDGES, seed=0):
        n = len(h); self.n, self.r = n, r
        self.h, self.Jm = np.asarray(h, float), np.asarray(Jm, float)
        self.ring = list(ring) if ring is not None else list(np.argsort(self.h, kind="stable"))
        pos = {v: i for i, v in enumerate(self.ring)}
        layers = ring_layers(n)
        cache = {}

        def ex(u):
            if u not in cache:
                cache[u] = to_vars(heis(((pos[u], "Z"),), layers, n), self.ring)
            return cache[u]
        iu = np.triu_indices(n, 1)
        E = [(int(i), int(j)) for i, j in zip(*iu) if self.Jm[i, j] != 0.0]
        rng = np.random.default_rng(seed)
        if len(E) > train_edges:
            idx = rng.choice(len(E), train_edges, replace=False); scale = len(E) / train_edges
            Et = [E[t] for t in sorted(idx)]
        else:
            Et, scale = E, 1.0
        self.n_edges, self.n_train_edges = len(E), len(Et)
        sid = {}
        def sidx(st):
            if st not in sid:
                sid[st] = len(sid)
            return sid[st]
        # energy: sum over strings of coef(beta) * E_s(gamma); coefficients as {monomial: complex} per string
        energy = {}
        self.field = []                                    # per u: [(string id, poly)]
        for u in range(n):
            lst = []
            for st, p in ex(u).items():
                i = sidx(st); lst.append((i, p))
                _padd(energy.setdefault(i, {}), p, self.h[u])
            self.field.append(lst)
        for (u, v) in Et:
            w = self.Jm[u, v] * scale
            for su, pu in ex(u).items():
                for sv, pv in ex(v).items():
                    ph, st = smul(su, sv)
                    _padd(energy.setdefault(sidx(st), {}), _pmul(pu, pv), w * ph)
        strings = [None] * len(sid)
        for st, i in sid.items():
            strings[i] = st
        self.S = Strings(strings, self.h, self.Jm, r)
        monos = sorted({m for p in energy.values() for m in p})
        self.monos = monos; mi = {m: a for a, m in enumerate(monos)}
        Cm = np.zeros((len(strings), len(monos)), complex)
        for i, p in energy.items():
            for m, v in p.items():
                Cm[i, mi[m]] += v
        self.Cm = torch.tensor(Cm, device=DEV)
        self.n_strings, self.n_rows = len(strings), self.S.R

    @staticmethod
    def _mono(monos, betas):
        c, s = np.cos(betas), np.sin(betas)
        return np.stack([c ** a * s ** b for a, b in monos], 1)

    def energy_betas(self, gamma, betas):
        Ev = self.S.values(gamma)
        V = (self.Cm.T @ Ev).cpu().numpy()
        return np.real(self._mono(self.monos, betas) @ V), Ev

    def fields(self, gamma, beta, Ev=None):
        Ev = self.S.values(gamma) if Ev is None else Ev
        Ev = Ev.cpu().numpy()
        c, s = math.cos(beta), math.sin(beta)
        return np.array([np.real(sum(Ev[i] * sum(v * c ** a * s ** b for (a, b), v in p.items()) for i, p in lst))
                         for lst in self.field])

    def train(self, gammas, refine=8):
        betas = np.linspace(-math.pi, math.pi, 361, endpoint=False)
        best = (np.inf, None, None); evals = {}
        def at(g):
            if g not in evals:
                e, _ = self.energy_betas(g, betas); a = int(np.argmin(e)); evals[g] = (float(e[a]), float(betas[a]))
            return evals[g]
        for g in gammas:
            e, b = at(float(g))
            if e < best[0]:
                best = (e, float(g), b)
        # golden section on gamma around the best grid point
        gs = sorted(evals); i = gs.index(best[1])
        lo, hi = gs[max(i - 1, 0)], gs[min(i + 1, len(gs) - 1)]
        phi = (math.sqrt(5) - 1) / 2
        x1, x2 = hi - phi * (hi - lo), lo + phi * (hi - lo)
        for _ in range(refine):
            if at(x1)[0] < at(x2)[0]:
                hi = x2; x2 = x1; x1 = hi - phi * (hi - lo)
            else:
                lo = x1; x1 = x2; x2 = lo + phi * (hi - lo)
        g = min(evals, key=lambda t: evals[t][0])
        e, b = evals[g]
        # fine beta around the best
        fb = np.linspace(b - 0.02, b + 0.02, 81)
        ef, Ev = self.energy_betas(g, fb); a = int(np.argmin(ef))
        return g, float(fb[a]), float(ef[a]), Ev, len(evals) + 1


# ---------------------------------------------------------------- state-vector reference (small n)
def sv_check(h, Jm, r, gamma, beta, ring=None):
    n = len(h)
    ring = list(ring) if ring is not None else list(np.argsort(h, kind="stable"))
    idx = np.arange(1 << n); X = (idx[:, None] >> np.arange(n)) & 1; Z = 1 - 2 * X
    feas = X.sum(1) == r
    psi = np.where(feas, 1.0, 0.0).astype(complex); psi /= np.linalg.norm(psi)
    C = Z @ h + np.einsum("si,ij,sj->s", Z, np.triu(Jm, 1), Z)
    psi = psi * np.exp(-1j * gamma * C)
    for L in ring_layers(n):
        for a, b in L:
            va, vb = ring[a], ring[b]
            xa, xb = X[:, va], X[:, vb]
            m = xa != xb
            flip = idx ^ (1 << va) ^ (1 << vb)
            new = psi.copy()
            new[m] = math.cos(beta) * psi[m] - 1j * math.sin(beta) * psi[flip[m]]
            psi = new
    p = np.abs(psi) ** 2
    Mz = Z.T @ p
    Mzz = np.einsum("s,si,sj->ij", p, Z, Z)
    return Mz, Mzz, float(p @ C)


def cmd_check():
    rng = np.random.default_rng(3)
    worst = 0.0
    for n, r in ((7, 2), (8, 3), (9, 4), (10, 3)):
        h = rng.normal(size=n); Jm = rng.normal(size=(n, n)) * 0.7; Jm = np.triu(Jm, 1); Jm = Jm + Jm.T
        eng = XY1(h, Jm, r, train_edges=10 ** 9)
        for gamma, beta in ((0.37, 0.61), (-0.9, 1.3), (1.7, -0.4)):
            Mz, Mzz, E = sv_check(h, Jm, r, gamma, beta, eng.ring)
            e, Ev = eng.energy_betas(gamma, np.array([beta]))
            f = eng.fields(gamma, beta, Ev)
            # pair <Z_u Z_v> through the same machinery
            errs = [abs(e[0] - E), np.abs(f - Mz).max()]
            ex = {u: to_vars(heis(((eng.ring.index(u), "Z"),), ring_layers(n), n), eng.ring) for u in range(n)}
            for u, v in [(0, n - 1), (1, 2), (2, 5)]:
                acc = {}
                for su, pu in ex[u].items():
                    for sv, pv in ex[v].items():
                        ph, st = smul(su, sv); _padd(acc.setdefault(st, {}), _pmul(pu, pv), ph)
                S = Strings(list(acc), h, Jm, r); vals = S.values(gamma).cpu().numpy()
                c, s = math.cos(beta), math.sin(beta)
                zz = np.real(sum(vals[i] * sum(w * c ** a * s ** b for (a, b), w in acc[st].items()) for i, st in enumerate(S.strings)))
                errs.append(abs(zz - Mzz[u, v]))
            worst = max(worst, max(errs))
            print(f"n={n} r={r} gamma={gamma:+.2f} beta={beta:+.2f}  |dE|={errs[0]:.1e} max|dZ|={errs[1]:.1e} max|dZZ|={max(errs[2:]):.1e}"
                  f"  E={E:+.4f}  strings={eng.n_strings} rows={eng.n_rows}")
    print("worst", worst)


# ---------------------------------------------------------------- RQAOA on top
def _pick(M, r, n):
    for a in np.argsort(-np.abs(M), kind="stable"):
        s = 1.0 if M[a] >= 0 else -1.0
        if (s < 0 and r >= 1) or (s > 0 and n - 1 >= r):
            return int(a)
    raise RuntimeError("no allowed fix")


def rqaoa_xy(h0, Jm0, k, nc=10, score=None, log=None, gamma_grid=None, mode="xy"):
    """h0 (n,), Jm0 (n, n) symmetric zero-diagonal Ising couplings (no penalty), exactly k selected.
    mode "coef": the same recursion with M_u = -(h_u - mean h) instead of the XY-QAOA <Z_u> (classical counterpart)."""
    n0 = len(h0)
    h = np.asarray(h0, float).copy(); Jm = np.asarray(Jm0, float).copy()
    act = list(range(n0)); r = k; z = np.zeros(n0); steps = []; prev_g = None
    t0 = time.time()

    def fix(u, s):
        nonlocal r
        for o in act:
            if o != u:
                h[o] += s * Jm[u, o]
        act.remove(u); z[u] = s
        if s < 0:
            r -= 1
    while len(act) > nc and 0 < r < len(act):
        hs = h[act]; Js = Jm[np.ix_(act, act)]
        t1 = time.time()
        if mode == "coef":
            M = -(hs - hs.mean())
            a = _pick(M, r, len(act)); u = act[int(a)]; s = 1.0 if M[a] >= 0 else -1.0
            steps.append({"n": len(act), "r": r, "M": float(M[a]), "fix": int(u), "sign": s})
            fix(u, s)
            continue
        eng = XY1(hs, Js, r, seed=len(act))
        # gamma scale: typical |C(x') - C(x)| of one swap
        rng = np.random.default_rng(len(act))
        d = []
        for _ in range(200):
            sel = rng.choice(len(act), r, replace=False); zz = np.ones(len(act)); zz[sel] = -1
            a = int(rng.choice(sel)); b = int(rng.choice(np.flatnonzero(zz > 0)))
            dC = -2 * hs[a] * zz[a] - 2 * hs[b] * zz[b] - 2 * zz[a] * (Js[a] @ zz - Js[a, b] * zz[b]) - 2 * zz[b] * (Js[b] @ zz - Js[b, a] * zz[a])
            d.append(abs(dC))
        sc = float(np.median(d)) or 1.0
        if prev_g is None:
            gammas = (gamma_grid if gamma_grid is not None else np.linspace(-3.0, 3.0, 25)) / sc
        else:
            gammas = prev_g * np.linspace(0.6, 1.4, 9)
        g, b, e, Ev, nev = eng.train(gammas)
        prev_g = g
        M = eng.fields(g, b, Ev)
        a = _pick(M, r, len(act)); s = 1.0 if M[a] >= 0 else -1.0
        u = act[int(a)]
        row = {"n": len(act), "r": r, "gamma": g, "beta": b, "E": e, "M": float(M[a]), "fix": int(u), "sign": s,
               "strings": eng.n_strings, "rows": eng.n_rows, "evals": nev, "s": time.time() - t1,
               "M_mean": float(M.mean()), "M_spread": float(M.max() - M.min())}
        steps.append(row)
        if log:
            log(row)
        fix(u, s)
    if r == 0:
        for u in list(act):
            fix(u, 1.0)
    elif r == len(act):
        for u in list(act):
            fix(u, -1.0)
    else:
        best = (np.inf, None)
        for sel in itertools.combinations(act, r):
            zz = np.ones(n0); zz[act] = 1.0; zz[list(sel)] = -1.0
            za = zz[act]
            e = float(h[act] @ za + 0.5 * za @ Jm[np.ix_(act, act)] @ za)
            if e < best[0]:
                best = (e, sel)
        for u in list(act):
            fix(u, -1.0 if u in best[1] else 1.0)
    assert int((z < 0).sum()) == k
    return z, {"steps": steps, "seconds": time.time() - t0, "qaoa_steps": len(steps)}


if __name__ == "__main__":
    import sys
    {"check": cmd_check}[sys.argv[1]]()
