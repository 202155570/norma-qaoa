"""Job orchestration: validate -> model -> QUBO/Ising -> QAOA -> candidates -> result + manifest."""

from __future__ import annotations

import time
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from norma_qaoa import ENGINE_NAME, __version__
from norma_qaoa.backends.base import SamplingBackend
from norma_qaoa.backends.registry import create_backend
from norma_qaoa.baseline import exhaustive_baseline, penalty_check
from norma_qaoa.candidates import build_candidates, decide_status
from norma_qaoa.circuits import QaoaSpec, QiskitQaoaCircuit
from norma_qaoa.config import EngineConfig
from norma_qaoa.ising import qubo_to_ising
from norma_qaoa.manifest import HASH_RULE, environment_versions, sha256_of, sha256_text, to_jsonable
from norma_qaoa.policy import assert_backend_allowed
from norma_qaoa.problem import Problem
from norma_qaoa.qaoa import (
    STOP_SIMULATOR_ERROR,
    Budget,
    QaoaOutcome,
    derive_seeds,
    objective_evaluations,
    run_qaoa,
)
from norma_qaoa.qubo import build_qubo
from norma_qaoa.schema import Result, validate_request

BIT_ORDER_NOTE = (
    "final_counts keys are Qiskit little-endian bitstrings (qubit 0 rightmost); "
    "asset i = qubit i; bit_vector fields follow asset_order"
)


@dataclass
class JobOutput:
    result: dict[str, Any]
    manifest: dict[str, Any]


def _utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def run_job(
    raw: dict[str, Any],
    config: EngineConfig | None = None,
    *,
    backend: SamplingBackend | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> JobOutput:
    config = config or EngineConfig()
    t0 = clock()
    started_wall = time.time()

    req = validate_request(raw, config)
    ex = req.execution
    deadline = t0 + ex.max_wall_seconds
    budget = Budget.plan(ex.max_objective_evaluations, config)

    problem = Problem.from_request(req)
    qubo = build_qubo(problem)
    ising = qubo_to_ising(qubo)
    spec = QaoaSpec.from_ising(ising, ex.depth)
    qiskit_circuit = QiskitQaoaCircuit(spec)
    pcheck = penalty_check(problem)

    backend = backend or create_backend(config)
    assert_backend_allowed(backend, req, config)
    seeds = derive_seeds(ex.seed)

    try:
        prep = backend.prepare(spec, seed_transpiler=seeds["transpiler"])
        outcome = run_qaoa(
            problem,
            spec,
            backend,
            shots=ex.shots_per_circuit,
            budget=budget,
            config=config,
            sim_seed=seeds["simulator"],
            deadline=deadline,
            t0=t0,
            clock=clock,
        )
    except Exception as exc:  # failure while preparing the circuit on the backend
        prep = {}
        outcome = QaoaOutcome(stop=STOP_SIMULATOR_ERROR, error=f"{type(exc).__name__}: {exc}")

    candidates = [] if outcome.stop == STOP_SIMULATOR_ERROR else build_candidates(
        problem, outcome.counts, ex.top_k, repair=config.classical_repair
    )
    status, stop_reason = decide_status(len(candidates), ex.top_k, outcome.stop)
    proven_infeasible = False
    if not candidates and outcome.stop != STOP_SIMULATOR_ERROR:
        proven_infeasible = exhaustive_baseline(problem).n_feasible == 0

    elapsed_ms = int(round((clock() - t0) * 1000))
    finished_wall = time.time()
    job_id = str(uuid.uuid4())
    manifest_id = f"manifest-{job_id}"
    n_evals = objective_evaluations(outcome, budget)

    result = Result.model_validate(
        {
            "schema_version": req.schema_version,
            "request_id": req.request_id,
            "job_id": job_id,
            "status": status,
            "stop_reason": stop_reason,
            "snapshot_id": req.data.snapshot_id,
            "model_version": req.model.version,
            "asset_order": list(problem.asset_ids),
            "candidates": candidates,
            "execution": {
                "mode": "quantum_circuit_simulator",
                "requested_algorithm": "QAOA",
                "backend_name": backend.name,
                "hardware_qpu_used": backend.kind == "hardware_qpu",
                "elapsed_ms": elapsed_ms,
                "shots_total": outcome.shots_total,
                "objective_evaluations": n_evals,
                "circuits_total": outcome.circuits_total,
                "seed": ex.seed,
                "qubits": problem.n,
                "depth": ex.depth,
            },
            "artifact_manifest_id": manifest_id,
            "proven_infeasible": proven_infeasible,
        }
    ).model_dump(exclude_none=False)
    for c in result["candidates"]:
        if c.get("repair") is None:
            c.pop("repair", None)

    warnings_ = []
    if not pcheck["passed"]:
        warnings_.append(pcheck["warning"])
    if outcome.stop == "TIME_LIMIT":
        warnings_.append("max_wall_seconds reached; candidates come only from samples already obtained")
    if outcome.counts_source and outcome.counts_source["phase"] != "final":
        warnings_.append("final sampling not executed; candidates taken from the lowest-cost evaluation's samples")

    manifest = to_jsonable(
        {
            "manifest_id": manifest_id,
            "schema_version": req.schema_version,
            "request_id": req.request_id,
            "job_id": job_id,
            "snapshot_id": req.data.snapshot_id,
            "model_version": req.model.version,
            "engine": {"name": ENGINE_NAME, "version": __version__},
            "status": status,
            "stop_reason": stop_reason,
            "error": outcome.error,
            "hash_rule": HASH_RULE,
            "input_hash": sha256_of(raw),
            "qubo_hash": sha256_of({"asset_order": list(problem.asset_ids), "Q": qubo.Q, "const": qubo.const}),
            "circuit_hash": sha256_text(qiskit_circuit.qasm()),
            "backend_circuit_hash": prep.get("backend_circuit_hash"),
            "qubo": {"convention": "F(x) = sum_{i<=j} Q_ij x_i x_j + const; upper triangular, diagonal = linear terms",
                     "const": qubo.const},
            "ising": {"mapping": "x_i = (1 - Z_i)/2", "offset": ising.offset, "scale_factor": ising.scale_factor,
                      "n_z_terms": len(ising.z_terms), "n_zz_terms": len(ising.zz_terms)},
            "scale_factor": ising.scale_factor,
            "qubits": problem.n,
            "ancilla_qubits": 0,
            "depth": ex.depth,
            "seeds": seeds,
            "evaluations": n_evals,
            "circuits": outcome.circuits_total,
            "shots": {"per_circuit": ex.shots_per_circuit, "total": outcome.shots_total},
            "budget": budget.to_dict(),
            "started_utc": _utc(started_wall),
            "finished_utc": _utc(finished_wall),
            "elapsed_ms": elapsed_ms,
            "max_wall_seconds": ex.max_wall_seconds,
            "time_limit_rule": "deadline checked before every circuit; a running circuit is not interrupted",
            "optimizer": {
                "strategy": "grid_then_cobyla",
                "grid_size": config.grid_size,
                "gamma_range": list(config.gamma_range),
                "beta_range": list(config.beta_range),
                "cobyla_rhobeg": config.cobyla_rhobeg,
                "cobyla_message": outcome.cobyla_message,
                "best_params": outcome.best_params,
                "max_starts": ex.max_starts,
            },
            "trace": [r.to_dict() for r in outcome.trace],
            "counts_source": outcome.counts_source,
            "bit_order": BIT_ORDER_NOTE,
            "final_counts": outcome.counts,
            "candidate_origins": dict(Counter(c["origin"] for c in result["candidates"])),
            "postprocessing": {"classical_repair": config.classical_repair},
            "penalty_check": pcheck,
            "warnings": warnings_,
            "backend": {**backend.info(), "prepare": prep},
            "hardware_qpu_used": backend.kind == "hardware_qpu",
            "config": config.model_dump(),
            "versions": environment_versions(),
        }
    )
    return JobOutput(result=result, manifest=manifest)
