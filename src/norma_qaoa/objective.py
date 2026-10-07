"""Direct evaluation of F(x) = G(x) + P(x) from the spec 06 definitions (no QUBO involved).

Components are unweighted:
  risk(x)    = x^T C x / K^2
  overlap(x) = 2 * sum_{i<j} O_ij x_i x_j / (K (K-1))      (0 when K=1 or overlap is null)
  utility(x) = sum_i u_i x_i / K
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from norma_qaoa.problem import Problem


def _vec(x: Sequence[int]) -> np.ndarray:
    return np.asarray(x, dtype=float)


def components(p: Problem, x: Sequence[int]) -> dict[str, float]:
    v = _vec(x)
    K = p.K
    risk = float(v @ p.C @ v) / K**2
    if p.overlap_active:
        upper = sum(p.O[i, j] * v[i] * v[j] for i in range(p.n) for j in range(i + 1, p.n))
        overlap = 2.0 * float(upper) / (K * (K - 1))
    else:
        overlap = 0.0
    utility = float(p.u @ v) / K
    return {"risk": risk, "overlap": overlap, "utility": utility}


def objective_base(p: Problem, x: Sequence[int]) -> float:
    """G(x) = a*risk + b*overlap - d*utility."""
    c = components(p, x)
    return p.a * c["risk"] + p.b * c["overlap"] - p.d * c["utility"]


def penalty(p: Problem, x: Sequence[int]) -> float:
    """P(x) = Lk*(sum x - K)^2 + Lf*sum_{include}(1-x_i) + Lf*sum_{exclude} x_i."""
    v = _vec(x)
    card = (v.sum() - p.K) ** 2
    inc = sum(1.0 - v[i] for i in p.include)
    exc = sum(v[i] for i in p.exclude)
    return float(p.Lk * card + p.Lf * inc + p.Lf * exc)


def objective_penalized(p: Problem, x: Sequence[int]) -> float:
    """F(x) = G(x) + P(x)."""
    return objective_base(p, x) + penalty(p, x)


def violations(p: Problem, x: Sequence[int]) -> list[str]:
    v = [int(b) for b in x]
    out = []
    if sum(v) != p.K:
        out.append(f"CARDINALITY: selected {sum(v)} != K={p.K}")
    for i in p.include:
        if v[i] != 1:
            out.append(f"MUST_INCLUDE_MISSING: {p.asset_ids[i]}")
    for i in p.exclude:
        if v[i] != 0:
            out.append(f"MUST_EXCLUDE_SELECTED: {p.asset_ids[i]}")
    return out


def is_feasible(p: Problem, x: Sequence[int]) -> bool:
    return not violations(p, x)


# ----------------------------------------------------- vectorized (rows = x) ---
def batch_objective(p: Problem, X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (F, G, feasible_mask) for each row of the 0/1 matrix X (shape M x N)."""
    X = np.asarray(X, dtype=float)
    K = p.K
    risk = np.einsum("mi,ij,mj->m", X, p.C, X) / K**2
    if p.overlap_active:
        overlap = np.einsum("mi,ij,mj->m", X, p.O, X) / (K * (K - 1))  # O symmetric, zero diag
    else:
        overlap = np.zeros(X.shape[0])
    utility = X @ p.u / K
    G = p.a * risk + p.b * overlap - p.d * utility
    s = X.sum(axis=1)
    inc = X[:, list(p.include)] if p.include else np.ones((X.shape[0], 0))
    exc = X[:, list(p.exclude)] if p.exclude else np.zeros((X.shape[0], 0))
    P = p.Lk * (s - K) ** 2 + p.Lf * (1.0 - inc).sum(axis=1) + p.Lf * exc.sum(axis=1)
    feasible = (s == K) & np.all(inc == 1, axis=1) & np.all(exc == 0, axis=1)
    return G + P, G, feasible


def all_bit_vectors(n: int) -> np.ndarray:
    """All 2^n bit vectors; row k has x_i = (k >> i) & 1 (asset i = bit i of k)."""
    k = np.arange(2**n, dtype=np.int64)[:, None]
    return ((k >> np.arange(n)) & 1).astype(np.int8)
