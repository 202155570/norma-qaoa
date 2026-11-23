"""RQAOA that keeps the cardinality constraint (A) and keeps several paths (B). Exploratory.

Same step as rqaoa.rqaoa (train depth-p QAOA on the current Ising problem, read M_i = <Z_i> and
M_ij = <Z_i Z_j>, fix z_u = sign(M_i) or tie z_v = sign(M_ij) z_u), with two changes:

A  count-aware decisions. Every active variable u stands for a cluster of original variables
   (itself plus the ones tied to it); cnt[u] = (number selected if z_u = -1, number if z_u = +1),
   (1, 0) at the start. r = k - number already selected by fixes. A move is allowed only if the
   remaining clusters can still select exactly r (subset sum over the cnt pairs, bitset DP).
   Candidates are tried in order of |M|; the first allowed one is taken. After every move,
   clusters with only one allowed value are fixed without QAOA (r = 0 -> all the rest out, etc.).
   The final <= NC clusters are enumerated over the assignments with exactly r selected.
   The correlations still come from the Ising problem given (with or without a penalty term);
   on the feasible set a quadratic penalty is constant, so the enumeration is exact there.
B  beam of width b. Each path proposes its b best allowed moves; children are scored by the sum
   of log|M| of their QAOA moves (forced moves add 0), duplicates (same substitutions) merged, the
   best b kept. Each surviving path is finished by the enumeration; the answer is the path with
   the lowest objective G (the problem's own objective, as when picking the best of b samples).
   b = 1 is A alone.

rqaoa_k(h0, J0, k, p, make_engine, beam=1, score=None) -> (z, info)
  score(z) -> objective to minimise among the finished paths (default: Ising energy)
"""

import math
import time

import numpy as np
import torch

import rqaoa as R


def _sums(pairs):
    m = 1
    for a, b in pairs:
        m = (m << a) | (m << b)
    return m


def _can(pairs, r):
    return r >= 0 and (_sums(pairs) >> r) & 1 == 1


class State:
    def __init__(self, h, J, cnt, r, subs, score, prev, nq):
        self.h, self.J, self.cnt, self.r, self.subs, self.score, self.prev, self.nq = h, J, cnt, r, subs, score, prev, nq

    def copy(self):
        return State(dict(self.h), dict(self.J), dict(self.cnt), self.r, list(self.subs), self.score, self.prev, self.nq)

    def sig(self):
        return tuple(sorted(self.subs))

    # ---- moves (exact substitutions, as rqaoa.rqaoa)
    def fix(self, u, sgn):
        for (i, j) in [key for key in self.J if u in key]:
            o = j if i == u else i
            self.h[o] += sgn * self.J.pop((i, j))
        self.h.pop(u)
        a, b = self.cnt.pop(u)
        self.r -= a if sgn < 0 else b
        self.subs.append(("fix", u, sgn))

    def tie(self, v, u, sgn):
        for (i, j) in [key for key in self.J if v in key]:
            o = j if i == v else i
            val = self.J.pop((i, j))
            if o != u:
                key = (min(o, u), max(o, u)); self.J[key] = self.J.get(key, 0.0) + sgn * val
                if abs(self.J[key]) < 1e-14:
                    self.J.pop(key)
        self.h[u] += sgn * self.h.pop(v)
        au, bu = self.cnt[u]; av, bv = self.cnt.pop(v)
        self.cnt[u] = (au + av, bu + bv) if sgn > 0 else (au + bv, bu + av)
        self.subs.append(("tie", v, u, sgn))

    def allowed_fix(self, u, sgn):
        a, b = self.cnt[u]
        return _can([c for w, c in self.cnt.items() if w != u], self.r - (a if sgn < 0 else b))

    def allowed_tie(self, v, u, sgn):
        au, bu = self.cnt[u]; av, bv = self.cnt[v]
        merged = (au + av, bu + bv) if sgn > 0 else (au + bv, bu + av)
        return _can([c for w, c in self.cnt.items() if w not in (u, v)] + [merged], self.r)

    def propagate(self):
        """Fix every cluster that has only one allowed value; repeat until none. Returns #forced."""
        n = 0
        while True:
            forced = None
            for u in sorted(self.cnt):
                lo, hi = self.allowed_fix(u, -1.0), self.allowed_fix(u, 1.0)
                assert lo or hi, "infeasible state"
                if lo != hi:
                    forced = (u, -1.0 if lo else 1.0); break
            if forced is None:
                return n
            self.fix(*forced); n += 1


def _decode(n0, st, zact):
    z = np.zeros(n0)
    for u, s in zact.items():
        z[u] = s
    for s in reversed(st.subs):
        if s[0] == "fix":
            z[s[1]] = s[2]
        else:
            z[s[1]] = s[3] * z[s[2]]
    return z


def _finish(n0, st):
    act = sorted(st.h); pos = {u: a for a, u in enumerate(act)}
    if not act:
        assert st.r == 0
        return _decode(n0, st, {})
    hv = np.array([st.h[u] for u in act]); Jr = [(pos[i], pos[j], v) for (i, j), v in st.J.items()]
    zs = 1 - 2 * ((np.arange(1 << len(act))[:, None] >> np.arange(len(act))) & 1)
    A = np.array([st.cnt[u][0] for u in act]); B = np.array([st.cnt[u][1] for u in act])
    sel = np.where(zs < 0, A[None], B[None]).sum(1)
    e = zs @ hv + sum(v * zs[:, i] * zs[:, j] for i, j, v in Jr)
    e = np.where(sel == st.r, e, np.inf)
    assert np.isfinite(e).any()
    zb = zs[int(np.argmin(e))]
    return _decode(n0, st, {u: float(zb[pos[u]]) for u in act})


def _children(st, make_engine, p, b):
    act = sorted(st.h); pos = {u: a for a, u in enumerate(act)}
    hv = np.array([st.h[u] for u in act])
    E = [((pos[i], pos[j]), v) for (i, j), v in sorted(st.J.items())]
    x, eng, e_q, _ = R.qaoa(lambda q: make_engine(len(act), hv, E, q), hv, E, p, st.prev)
    with torch.no_grad():
        M = eng.obs(torch.tensor(x)).numpy()
    out = []
    for a in np.argsort(-np.abs(M), kind="stable"):
        sgn = 1.0 if M[a] >= 0 else -1.0
        if a < len(act):
            u = act[a]
            if not st.allowed_fix(u, sgn):
                continue
            c = st.copy(); c.fix(u, sgn)
        else:
            (pi, pj), _ = E[a - len(act)]
            u, v = act[pi], act[pj]
            if not st.allowed_tie(v, u, sgn):
                continue
            c = st.copy(); c.tie(v, u, sgn)
        c.score += math.log(max(abs(float(M[a])), 1e-300)); c.prev = x; c.nq += 1
        c.propagate()
        out.append(c)
        if len(out) == b:
            break
    assert out, "no allowed move"
    return out


def rqaoa_k(h0, J0, k, p, make_engine, beam=1, score=None, nc=None):
    nc = R.NC if nc is None else nc
    n0 = len(h0)
    h = {i: float(h0[i]) for i in range(n0)}
    J = {}
    for i, j, v in J0:
        key = (min(i, j), max(i, j)); J[key] = J.get(key, 0.0) + float(v)
    st = State(h, J, {i: (1, 0) for i in range(n0)}, k, [], 0.0, None, 0)
    forced0 = st.propagate()
    beams, t0, levels = [st], time.time(), 0
    while any(len(s.h) > nc for s in beams):
        nxt, done = {}, []
        for s in beams:
            if len(s.h) <= nc:
                done.append(s); continue
            for c in _children(s, make_engine, p, beam):
                if c.sig() not in nxt or nxt[c.sig()].score < c.score:
                    nxt[c.sig()] = c
        pool = done + list(nxt.values())
        beams = sorted(pool, key=lambda s: -s.score)[:beam]
        levels += 1
    score = score or (lambda z: R.energy_z(z, h0, J0))
    fin = []
    for s in beams:
        z = _finish(n0, s)
        assert int((z < 0).sum()) == k
        fin.append((score(z), z, s))
    fin.sort(key=lambda t: t[0])
    best = fin[0]
    info = {"levels": levels, "forced_at_start": forced0, "paths": len(fin), "path_scores": [f[0] for f in fin],
            "best_path_rank_by_confidence": int(sorted(range(len(fin)), key=lambda i: -fin[i][2].score).index(0)),
            "qaoa_moves": best[2].nq, "seconds": time.time() - t0}
    return best[1], info
