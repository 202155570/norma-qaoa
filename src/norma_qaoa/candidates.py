"""Counts -> candidates, optional classical repair, and job status.

Order: bit vector (asset order) -> feasible only -> dedupe -> sort by
(objective_penalized asc, objective_base asc, sample_count desc) -> first top_k.
Missing candidates are never fabricated. sample_count is only the circuit output
distribution.
"""

from __future__ import annotations

from collections.abc import Sequence

from norma_qaoa.ising import bitstring_to_bit_vector
from norma_qaoa.objective import components, is_feasible, objective_base, objective_penalized, violations
from norma_qaoa.problem import Problem
from norma_qaoa.qaoa import STOP_SIMULATOR_ERROR, STOP_TIME_LIMIT

ORIGIN_SAMPLE = "simulator_sample"
ORIGIN_REPAIR = "classical_repair"

SUCCEEDED, PARTIAL, FAILED = "SUCCEEDED", "PARTIAL", "FAILED"
STOP_COMPLETED = "COMPLETED"
STOP_TOP_K_NOT_REACHED = "TOP_K_NOT_REACHED"
STOP_NO_FEASIBLE_SAMPLE = "NO_FEASIBLE_SAMPLE"


def _candidate(p: Problem, x: tuple[int, ...], origin: str, sample_count: int | None, repair: dict | None = None) -> dict:
    return {
        "selected_asset_ids": [p.asset_ids[i] for i, b in enumerate(x) if b],
        "bit_vector": list(x),
        "origin": origin,
        "objective_base": objective_base(p, x),
        "objective_penalized": objective_penalized(p, x),
        "components": components(p, x),
        "feasible": is_feasible(p, x),
        "violations": violations(p, x),
        "sample_count": sample_count,
        **({"repair": repair} if repair is not None else {}),
    }


def aggregate_counts(p: Problem, counts: dict[str, int]) -> dict[tuple[int, ...], int]:
    agg: dict[tuple[int, ...], int] = {}
    for bitstring, c in counts.items():
        x = tuple(bitstring_to_bit_vector(bitstring, p.n))
        agg[x] = agg.get(x, 0) + int(c)
    return agg


def _sort_key(c: dict):
    sc = c["sample_count"] if c["sample_count"] is not None else 0
    return (c["objective_penalized"], c["objective_base"], -sc, c["bit_vector"])


def greedy_repair(p: Problem, x: Sequence[int]) -> tuple[tuple[int, ...], list[dict]]:
    """Fix include/exclude, then add/remove free bits one at a time (lowest F first) until |x| = K."""
    y = list(int(b) for b in x)
    changes = []

    def flip(i: int, to: int, reason: str):
        changes.append({"asset_id": p.asset_ids[i], "from": y[i], "to": to, "reason": reason})
        y[i] = to

    for i in p.include:
        if y[i] != 1:
            flip(i, 1, "must_include")
    for i in p.exclude:
        if y[i] != 0:
            flip(i, 0, "must_exclude")
    fixed = set(p.include) | set(p.exclude)
    while sum(y) != p.K:
        target = 0 if sum(y) > p.K else 1
        options = [i for i in range(p.n) if i not in fixed and y[i] != target]

        def f_after(i: int) -> float:
            z = list(y)
            z[i] = target
            return objective_penalized(p, z)

        best = min(options, key=lambda i: (f_after(i), i))
        flip(best, target, "cardinality")
    return tuple(y), changes


def build_candidates(p: Problem, counts: dict[str, int] | None, top_k: int, repair: bool = False) -> list[dict]:
    if not counts:
        return []
    agg = aggregate_counts(p, counts)
    sampled = [_candidate(p, x, ORIGIN_SAMPLE, c) for x, c in agg.items() if is_feasible(p, x)]
    sampled.sort(key=_sort_key)
    chosen = sampled[:top_k]

    if repair and len(chosen) < top_k:
        # Repaired candidates only fill remaining slots; they never displace direct samples.
        sampled_vectors = {tuple(c["bit_vector"]) for c in sampled}
        repaired: dict[tuple[int, ...], dict] = {}
        for x, c in sorted(agg.items(), key=lambda kv: (-kv[1], kv[0])):
            if is_feasible(p, x):
                continue
            y, changes = greedy_repair(p, x)
            if y in sampled_vectors:
                continue
            src = {"source_bit_vector": list(x), "source_sample_count": c, "changes": changes}
            if y not in repaired:
                repaired[y] = _candidate(p, y, ORIGIN_REPAIR, None, {"sources": [src]})
            else:
                repaired[y]["repair"]["sources"].append(src)
        extra = sorted(repaired.values(), key=_sort_key)
        chosen += extra[: top_k - len(chosen)]

    return [{"candidate_id": f"cand-{i + 1:02d}", **c} for i, c in enumerate(chosen)]


def decide_status(n_candidates: int, top_k: int, stop: str | None) -> tuple[str, str]:
    if stop == STOP_SIMULATOR_ERROR:
        return FAILED, STOP_SIMULATOR_ERROR
    if stop == STOP_TIME_LIMIT:
        # Spec p.5: ended by a compute limit -> PARTIAL even when top_k candidates exist.
        return (PARTIAL if n_candidates >= 1 else FAILED), STOP_TIME_LIMIT
    if n_candidates >= top_k:
        return SUCCEEDED, STOP_COMPLETED
    if n_candidates >= 1:
        return PARTIAL, STOP_TOP_K_NOT_REACHED
    return FAILED, STOP_NO_FEASIBLE_SAMPLE
