"""Classical reference computations. These are comparison data, never quantum results."""

from __future__ import annotations

import bisect
import itertools
import math
from dataclasses import dataclass

import numpy as np

from norma_qaoa.objective import (
    all_bit_vectors,
    batch_objective,
    components,
    objective_base,
    objective_penalized,
)
from norma_qaoa.problem import Problem

BASELINE_ORIGIN = "classical_baseline"
RANK_TOL = 1e-9


@dataclass(frozen=True)
class RankedCombo:
    rank: int
    bit_vector: tuple[int, ...]
    objective_penalized: float
    objective_base: float

    def to_dict(self, p: Problem) -> dict:
        return {
            "rank": self.rank,
            "selected_asset_ids": [p.asset_ids[i] for i, b in enumerate(self.bit_vector) if b],
            "bit_vector": list(self.bit_vector),
            "origin": BASELINE_ORIGIN,
            "objective_base": self.objective_base,
            "objective_penalized": self.objective_penalized,
            "components": components(p, self.bit_vector),
        }


@dataclass(frozen=True)
class ExhaustiveResult:
    n_k_subsets: int  # C(N, K)
    ranking: tuple[RankedCombo, ...]  # every feasible combination, F ascending

    @property
    def n_feasible(self) -> int:
        return len(self.ranking)

    @property
    def optimum(self) -> RankedCombo | None:
        return self.ranking[0] if self.ranking else None

    def rank_of(self, f_value: float) -> int:
        """Competition rank of an objective value among feasible combinations (1 = best)."""
        fs = [r.objective_penalized for r in self.ranking]
        return 1 + bisect.bisect_left(fs, f_value - RANK_TOL)

    def optimal_bit_vectors(self) -> list[tuple[int, ...]]:
        if not self.ranking:
            return []
        best = self.ranking[0].objective_penalized
        return [r.bit_vector for r in self.ranking if r.objective_penalized <= best + RANK_TOL]

    def to_dict(self, p: Problem) -> dict:
        return {
            "origin": BASELINE_ORIGIN,
            "n_assets": p.n,
            "select_k": p.K,
            "n_k_subsets": self.n_k_subsets,
            "n_feasible": self.n_feasible,
            "optimum": self.optimum.to_dict(p) if self.optimum else None,
            "ranking": [r.to_dict(p) for r in self.ranking],
        }


def exhaustive_baseline(p: Problem) -> ExhaustiveResult:
    """Enumerate every feasible combination (include fixed to 1, exclude to 0, |x| = K)."""
    free = [i for i in range(p.n) if i not in p.include and i not in p.exclude]
    need = p.K - len(p.include)
    rows = []
    if need >= 0:
        for chosen in itertools.combinations(free, need):
            x = [0] * p.n
            for i in (*p.include, *chosen):
                x[i] = 1
            rows.append((objective_penalized(p, x), objective_base(p, x), tuple(x)))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    fs = [r[0] for r in rows]
    ranking = [
        RankedCombo(rank=1 + bisect.bisect_left(fs, f - RANK_TOL), bit_vector=x, objective_penalized=f, objective_base=g)
        for f, g, x in rows
    ]
    return ExhaustiveResult(n_k_subsets=math.comb(p.n, p.K), ranking=tuple(ranking))


def penalty_check(p: Problem) -> dict:
    """Is the minimum of F over all 2^N bit vectors feasible? Penalties are never adjusted here."""
    X = all_bit_vectors(p.n)
    F, _, feasible = batch_objective(p, X)
    k = int(np.argmin(F))
    min_feasible = float(F[feasible].min()) if feasible.any() else None
    min_infeasible = float(F[~feasible].min()) if (~feasible).any() else None
    passed = bool(feasible[k])
    out = {
        "passed": passed,
        "n_bit_vectors": int(len(F)),
        "argmin_bit_vector": X[k].tolist(),
        "argmin_feasible": passed,
        "min_objective_penalized": float(F[k]),
        "min_feasible_objective_penalized": min_feasible,
        "min_infeasible_objective_penalized": min_infeasible,
        "margin_infeasible_minus_feasible": (
            None if min_feasible is None or min_infeasible is None else min_infeasible - min_feasible
        ),
    }
    if not passed:
        out["warning"] = (
            "Lowest F over all bit vectors is infeasible: penalties may be insufficient. "
            "Penalties were not changed."
        )
    return out


def random_baseline(p: Problem, shots: int, seed: int) -> dict:
    """Uniform random bit vectors, same count as the QAOA final sampling shots."""
    rng = np.random.default_rng(seed)
    X = rng.integers(0, 2, size=(shots, p.n), dtype=np.int8)
    F, _, feasible = batch_objective(p, X)
    n_feas = int(feasible.sum())
    best_idx = int(np.argmin(np.where(feasible, F, np.inf))) if n_feas else None
    return {
        "origin": BASELINE_ORIGIN,
        "method": "uniform_random_bit_vectors",
        "shots": shots,
        "seed": seed,
        "feasible_shots": n_feas,
        "feasible_ratio": n_feas / shots if shots else 0.0,
        "distinct_feasible": int(len({tuple(r) for r in X[feasible]})) if n_feas else 0,
        "best_objective_penalized": float(F[best_idx]) if best_idx is not None else None,
        "best_bit_vector": X[best_idx].tolist() if best_idx is not None else None,
    }
