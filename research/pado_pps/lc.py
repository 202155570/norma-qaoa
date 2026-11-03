"""Exact QAOA expectations on a sparse Ising problem by reverse light cones.

QAOA:  |+>^n,  then p times  exp(-i g_l C) exp(-i b_l sum X),  C = sum h_i Z_i + sum J_ij Z_i Z_j.
<Z_i> and <Z_i Z_j> after p layers depend only on the qubits within graph distance p of the
term's support. Gates on the edge of that ball either commute through or act on qubits the
operator never reaches, so simulating the subgraph induced by the ball (all its fields and
edges) is exact. With maximum degree 3 the ball holds at most 14 qubits at p = 2.

full_energy() is a plain 2^n state-vector simulation used to check lc on small n.
"""

import math
from collections import deque

import numpy as np


def _zvals(m):
    idx = np.arange(1 << m)
    return 1.0 - 2.0 * ((idx[:, None] >> np.arange(m)[None, :]) & 1)       # (2^m, m) entries +-1


def _mix(psi, m, b):
    c, s = math.cos(b), -1j * math.sin(b)
    psi = psi.reshape((2,) * m)
    for q in range(m):
        a0 = np.take(psi, 0, axis=m - 1 - q); a1 = np.take(psi, 1, axis=m - 1 - q)
        psi = np.stack([c * a0 + s * a1, s * a0 + c * a1], axis=m - 1 - q)
    return psi.reshape(-1)


class LightCone:
    def __init__(self, n, h, edges, p):
        self.n, self.p = n, p
        self.h = np.asarray(h, float); self.edges = [(int(i), int(j), float(v)) for i, j, v in edges]
        adj = [[] for _ in range(n)]
        for i, j, _ in self.edges:
            adj[i].append(j); adj[j].append(i)
        self.terms = [("Z", (i,), self.h[i]) for i in range(n)] + [("ZZ", (i, j), v) for i, j, v in self.edges]
        self.cache = []
        for kind, sup, w in self.terms:
            dist = {q: 0 for q in sup}; dq = deque(sup)
            while dq:
                u = dq.popleft()
                if dist[u] < p:
                    for v in adj[u]:
                        if v not in dist:
                            dist[v] = dist[u] + 1; dq.append(v)
            ball = sorted(dist); loc = {q: a for a, q in enumerate(ball)}; m = len(ball)
            Z = _zvals(m)
            diag = Z @ self.h[ball]
            for i, j, v in self.edges:
                if i in loc and j in loc:
                    diag = diag + v * Z[:, loc[i]] * Z[:, loc[j]]
            obs = np.prod(Z[:, [loc[q] for q in sup]], axis=1)
            self.cache.append((m, diag, obs, sup))
        self.max_ball = max(c[0] for c in self.cache)

    def expvals(self, x):
        """<term> for every term (fields first, then edges)."""
        x = np.asarray(x, float); p = len(x) // 2
        out = np.empty(len(self.cache))
        for t, (m, diag, obs, _) in enumerate(self.cache):
            psi = np.full(1 << m, (1 << m) ** -0.5, dtype=np.complex128)
            for l in range(p):
                psi = _mix(psi * np.exp(-1j * x[l] * diag), m, x[p + l])
            out[t] = float(np.abs(psi) ** 2 @ obs)
        return out

    def energy(self, x):
        ev = self.expvals(x)
        return float(ev @ np.array([w for *_, w in self.terms]))

    def weight(self, x):
        """expected number of selected assets, x_i = (1 - Z_i)/2"""
        return float((1.0 - self.expvals(x)[: self.n]).sum() / 2.0)


def full_energy(n, h, edges, x):
    x = np.asarray(x, float); p = len(x) // 2
    Z = _zvals(n)
    diag = Z @ np.asarray(h, float)
    for i, j, v in edges:
        diag = diag + v * Z[:, i] * Z[:, j]
    psi = np.full(1 << n, (1 << n) ** -0.5, dtype=np.complex128)
    for l in range(p):
        psi = _mix(psi * np.exp(-1j * x[l] * diag), n, x[p + l])
    pr = np.abs(psi) ** 2
    return float(pr @ diag), float((pr @ (1.0 - Z)).sum() / 2.0)
