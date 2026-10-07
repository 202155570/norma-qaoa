"""QAOA parameter search with a hard, job-wide evaluation budget and wall-clock deadline.

Strategy (max_starts = 1):
  1. grid_size x grid_size grid over (gamma, beta)
  2. COBYLA from the best grid point with the remaining budget
  3. one final sampling at the lowest-cost parameters seen in steps 1-2

One evaluation = bind parameters -> sample -> F (original units) per sample -> shot-weighted mean.
"""

from __future__ import annotations

import time
import warnings
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.optimize import minimize

from norma_qaoa.backends.base import SamplingBackend
from norma_qaoa.circuits import QaoaSpec
from norma_qaoa.config import EngineConfig
from norma_qaoa.errors import ConfigError
from norma_qaoa.ising import bitstring_to_bit_vector
from norma_qaoa.objective import is_feasible, objective_penalized
from norma_qaoa.problem import Problem

STOP_TIME_LIMIT = "TIME_LIMIT"
STOP_SIMULATOR_ERROR = "SIMULATOR_ERROR"


class BudgetExhausted(Exception):
    pass


class TimeLimitReached(Exception):
    pass


class SimulatorError(Exception):
    pass


def derive_seeds(master: int) -> dict[str, int]:
    children = np.random.SeedSequence(master).spawn(4)
    vals = [int(c.generate_state(1, dtype=np.uint32)[0]) for c in children]
    return {
        "master": master,
        "simulator": vals[0],
        "transpiler": vals[1],
        "optimizer": vals[2],  # recorded; COBYLA itself is deterministic
        "random_baseline": vals[3],
    }


@dataclass(frozen=True)
class Budget:
    max_objective_evaluations: int
    grid_points: int
    cobyla_max: int
    final_counted: bool

    @classmethod
    def plan(cls, max_evals: int, config: EngineConfig) -> "Budget":
        grid = config.grid_size**2
        reserved = 1 if config.count_final_in_budget else 0
        cobyla = max_evals - grid - reserved
        if cobyla < 0:
            raise ConfigError(
                f"max_objective_evaluations={max_evals} is smaller than grid {grid}"
                f" + final sampling {reserved}; reduce grid_size"
            )
        return cls(max_evals, grid, cobyla, config.count_final_in_budget)

    @property
    def optimization_limit(self) -> int:
        return self.grid_points + self.cobyla_max

    def to_dict(self) -> dict:
        return {
            "max_objective_evaluations": self.max_objective_evaluations,
            "grid_points": self.grid_points,
            "cobyla_max_evaluations": self.cobyla_max,
            "final_sampling_counted_in_budget": self.final_counted,
            "counting_rule": (
                "grid + cobyla + final_sampling <= max_objective_evaluations"
                if self.final_counted
                else "grid + cobyla <= max_objective_evaluations; final sampling is an extra circuit"
            ),
        }


@dataclass
class EvalRecord:
    index: int
    phase: str  # grid | cobyla | final
    gamma: list[float]
    beta: list[float]
    cost: float  # shot-weighted mean F, original units
    sim_seed: int
    shots: int
    feasible_shots: int
    t_ms: int

    def to_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class QaoaOutcome:
    trace: list[EvalRecord] = field(default_factory=list)
    counts: dict[str, int] | None = None
    counts_source: dict[str, Any] | None = None
    stop: str | None = None  # None (normal) | TIME_LIMIT | SIMULATOR_ERROR
    error: str | None = None
    best_params: list[float] | None = None
    cobyla_message: str | None = None

    @property
    def circuits_total(self) -> int:
        return len(self.trace)

    @property
    def shots_total(self) -> int:
        return sum(r.shots for r in self.trace)


class Evaluator:
    def __init__(
        self,
        problem: Problem,
        spec: QaoaSpec,
        backend: SamplingBackend,
        shots: int,
        sim_seed: int,
        deadline: float,
        clock: Callable[[], float],
        t0: float,
    ):
        self.p, self.spec, self.backend = problem, spec, backend
        self.shots, self.sim_seed = shots, sim_seed
        self.deadline, self.clock, self.t0 = deadline, clock, t0
        self.trace: list[EvalRecord] = []
        self._f_cache: dict[str, tuple[float, bool]] = {}
        self.best: tuple[float, list[float], dict[str, int], int] | None = None  # cost, params, counts, index

    def _f(self, bitstring: str) -> tuple[float, bool]:
        hit = self._f_cache.get(bitstring)
        if hit is None:
            x = bitstring_to_bit_vector(bitstring, self.p.n)
            hit = (objective_penalized(self.p, x), is_feasible(self.p, x))
            self._f_cache[bitstring] = hit
        return hit

    def cost_of(self, counts: dict[str, int]) -> tuple[float, int]:
        total = sum(counts.values())
        acc, feas = 0.0, 0
        for b, c in counts.items():
            f, ok = self._f(b)
            acc += f * c
            feas += c if ok else 0
        return acc / total, feas

    def run_circuit(self, params: Sequence[float], phase: str) -> tuple[float, dict[str, int]]:
        if self.clock() >= self.deadline:
            raise TimeLimitReached()
        params = [float(v) for v in params]
        index = len(self.trace) + 1
        seed = (self.sim_seed + index) % 2**32
        try:
            (counts,) = self.backend.run([params], shots=self.shots, seed=seed)
        except Exception as exc:  # no automatic fallback to another backend
            raise SimulatorError(f"{type(exc).__name__}: {exc}") from exc
        cost, feas = self.cost_of(counts)
        gammas, betas = self.spec.split(params)
        self.trace.append(
            EvalRecord(
                index=index,
                phase=phase,
                gamma=gammas.tolist(),
                beta=betas.tolist(),
                cost=cost,
                sim_seed=seed,
                shots=sum(counts.values()),
                feasible_shots=feas,
                t_ms=int(round((self.clock() - self.t0) * 1000)),
            )
        )
        if phase != "final" and (self.best is None or cost < self.best[0]):
            self.best = (cost, params, counts, index)
        return cost, counts


def grid_points(config: EngineConfig, depth: int) -> list[list[float]]:
    gs = np.linspace(*config.gamma_range, config.grid_size)
    bs = np.linspace(*config.beta_range, config.grid_size)
    # depth > 1: the same (gamma, beta) on every layer during the grid phase.
    return [[float(g)] * depth + [float(b)] * depth for g in gs for b in bs]


def run_qaoa(
    problem: Problem,
    spec: QaoaSpec,
    backend: SamplingBackend,
    *,
    shots: int,
    budget: Budget,
    config: EngineConfig,
    sim_seed: int,
    deadline: float,
    t0: float,
    clock: Callable[[], float] = time.monotonic,
) -> QaoaOutcome:
    ev = Evaluator(problem, spec, backend, shots, sim_seed, deadline, clock, t0)
    out = QaoaOutcome()
    opt_count = 0

    def opt_eval(x: Sequence[float], phase: str) -> float:
        nonlocal opt_count
        if opt_count >= budget.optimization_limit:
            raise BudgetExhausted()
        opt_count += 1
        cost, _ = ev.run_circuit(x, phase)
        return cost

    try:
        for x in grid_points(config, spec.depth)[: budget.grid_points]:
            opt_eval(x, "grid")
        if budget.cobyla_max > 0 and ev.best is not None:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    res = minimize(
                        lambda x: opt_eval(x, "cobyla"),
                        np.asarray(ev.best[1]),
                        method="COBYLA",
                        options={"maxiter": budget.cobyla_max, "rhobeg": config.cobyla_rhobeg},
                    )
                out.cobyla_message = str(res.message)
            except BudgetExhausted:
                out.cobyla_message = "stopped by evaluation budget"
        out.best_params = list(ev.best[1])
        _, counts = ev.run_circuit(out.best_params, "final")
        out.counts = counts
        out.counts_source = {"phase": "final", "evaluation_index": len(ev.trace)}
    except TimeLimitReached:
        out.stop = STOP_TIME_LIMIT
        if ev.best is not None:
            # Spec decision: no further circuits; use the samples of the lowest-cost evaluation.
            out.best_params = list(ev.best[1])
            out.counts = ev.best[2]
            out.counts_source = {"phase": "best_evaluation", "evaluation_index": ev.best[3]}
    except SimulatorError as exc:
        out.stop = STOP_SIMULATOR_ERROR
        out.error = str(exc)
    out.trace = ev.trace
    return out


def objective_evaluations(outcome: QaoaOutcome, budget: Budget) -> int:
    n_opt = sum(1 for r in outcome.trace if r.phase != "final")
    n_final = sum(1 for r in outcome.trace if r.phase == "final")
    return n_opt + (n_final if budget.final_counted else 0)
