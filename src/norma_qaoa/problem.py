"""Validated request -> numeric problem. All arrays follow asset_ids order."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from norma_qaoa.schema import Request


@dataclass(frozen=True)
class Problem:
    asset_ids: tuple[str, ...]
    C: np.ndarray  # covariance_annual / risk_scale
    O: np.ndarray | None  # overlap, None when not provided
    u: np.ndarray
    K: int
    include: tuple[int, ...]
    exclude: tuple[int, ...]
    a: float  # weights.risk
    b: float  # weights.overlap
    d: float  # weights.utility
    Lk: float  # penalties.cardinality
    Lf: float  # penalties.fixed

    @property
    def n(self) -> int:
        return len(self.asset_ids)

    @property
    def overlap_active(self) -> bool:
        """Overlap term is defined as 0 when K=1 or overlap is null."""
        return self.O is not None and self.K > 1

    @classmethod
    def from_request(cls, req: Request) -> "Problem":
        ids = tuple(req.data.asset_ids)
        index = {a: i for i, a in enumerate(ids)}
        m = req.model
        return cls(
            asset_ids=ids,
            C=np.asarray(req.data.covariance_annual, dtype=float) / m.risk_scale,
            O=None if req.data.overlap is None else np.asarray(req.data.overlap, dtype=float),
            u=np.asarray(req.data.utility, dtype=float),
            K=req.constraints.select_k,
            include=tuple(sorted(index[a] for a in req.constraints.must_include)),
            exclude=tuple(sorted(index[a] for a in req.constraints.must_exclude)),
            a=m.weights.risk,
            b=m.weights.overlap,
            d=m.weights.utility,
            Lk=m.penalties.cardinality,
            Lf=m.penalties.fixed,
        )
