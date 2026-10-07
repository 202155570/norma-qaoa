"""QUBO built directly from spec 06 (upper-triangular convention, diagonal = linear terms).

F(x) = sum_{i<=j} Q_ij x_i x_j + const
  Q_ii       = a*C_ii/K^2 - d*u_i/K + Lk*(1-2K) - Lf*[i in include] + Lf*[i in exclude]
  Q_ij (i<j) = 2a*C_ij/K^2 + 2b*O_ij/(K(K-1)) + 2Lk     (overlap part omitted when K=1 or null)
  const      = Lk*K^2 + Lf*|include|
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from norma_qaoa.problem import Problem


@dataclass(frozen=True)
class Qubo:
    Q: np.ndarray  # upper triangular, N x N
    const: float


def build_qubo(p: Problem) -> Qubo:
    n, K = p.n, p.K
    Q = np.zeros((n, n))
    for i in range(n):
        q = p.a * p.C[i, i] / K**2 - p.d * p.u[i] / K + p.Lk * (1 - 2 * K)
        if i in p.include:
            q -= p.Lf
        if i in p.exclude:
            q += p.Lf
        Q[i, i] = q
        for j in range(i + 1, n):
            q = 2 * p.a * p.C[i, j] / K**2 + 2 * p.Lk
            if p.overlap_active:
                q += 2 * p.b * p.O[i, j] / (K * (K - 1))
            Q[i, j] = q
    const = p.Lk * K**2 + p.Lf * len(p.include)
    return Qubo(Q=Q, const=float(const))


def evaluate_qubo(qubo: Qubo, x: Sequence[int]) -> float:
    v = np.asarray(x, dtype=float)
    return float(v @ qubo.Q @ v) + qubo.const
