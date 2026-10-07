"""Request/result contract (spec 09, 10, Appendix A) and request validation.

Validation never fills in, estimates or corrects values. Every violation is reported
with a code and a field path.
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from norma_qaoa.config import EngineConfig
from norma_qaoa.errors import InputValidationError, Issue

SUPPORTED_SCHEMA_VERSIONS = ("1.0",)
MAX_ASSETS = 16
# Spec p.9 / p.17 execution limits.
MAX_TOP_K = 5
MAX_SHOTS_PER_CIRCUIT = 1024
MAX_OBJECTIVE_EVALUATIONS = 60
MAX_STARTS = 1
MAX_WALL_SECONDS = 300

_STRICT = ConfigDict(strict=True, extra="forbid")


# ---------------------------------------------------------------- request ---
class Data(BaseModel):
    # Extra operational metadata (profile_id, observation window, source_versions...) is kept.
    model_config = ConfigDict(strict=True, extra="allow")

    snapshot_id: str
    as_of_utc: str
    base_currency: str
    source_kind: str | None = None
    asset_ids: list[str]
    utility: list[float]
    covariance_annual: list[list[float]]
    # Required but nullable: "no overlap data" must be an explicit null (spec p.11).
    overlap: list[list[float]] | None


class Constraints(BaseModel):
    model_config = _STRICT

    select_k: int
    must_include: list[str]
    must_exclude: list[str]


class Weights(BaseModel):
    model_config = _STRICT

    risk: float
    overlap: float
    utility: float


class Penalties(BaseModel):
    model_config = _STRICT

    cardinality: float
    fixed: float


class Model(BaseModel):
    model_config = _STRICT

    version: str
    risk_scale: float
    weights: Weights
    penalties: Penalties


class Execution(BaseModel):
    model_config = _STRICT

    mode: str
    algorithm: str
    depth: int
    max_wall_seconds: float
    max_objective_evaluations: int
    max_starts: int
    shots_per_circuit: int
    seed: int
    allow_qpu: bool
    top_k: int


class Request(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")

    schema_version: str
    request_id: str
    data: Data
    constraints: Constraints
    model: Model
    execution: Execution


# ----------------------------------------------------------------- result ---
class Components(BaseModel):
    risk: float
    overlap: float
    utility: float


class Candidate(BaseModel):
    candidate_id: str
    selected_asset_ids: list[str]
    bit_vector: list[int]
    origin: Literal["simulator_sample", "classical_repair", "classical_baseline", "mock"]
    objective_base: float
    objective_penalized: float
    components: Components
    feasible: bool
    violations: list[str]
    # Number of times this bit vector appeared in the circuit samples. Not a forecast.
    sample_count: int | None
    repair: dict[str, Any] | None = None


class ExecutionSummary(BaseModel):
    mode: str
    requested_algorithm: str
    backend_name: str
    hardware_qpu_used: bool
    elapsed_ms: int | None
    shots_total: int
    objective_evaluations: int
    circuits_total: int
    seed: int | None
    qubits: int
    depth: int


class Result(BaseModel):
    schema_version: str
    request_id: str
    job_id: str
    status: Literal["SUCCEEDED", "PARTIAL", "FAILED"]
    stop_reason: str
    snapshot_id: str
    model_version: str
    asset_order: list[str]
    candidates: list[Candidate]
    execution: ExecutionSummary
    artifact_manifest_id: str
    proven_infeasible: bool


# ------------------------------------------------------------- validation ---
def _matrix(value: list[list[float]], n: int, field: str, issues: list[Issue]) -> np.ndarray | None:
    if len(value) != n or any(len(row) != n for row in value):
        issues.append(Issue("DIMENSION_MISMATCH", field, f"must be {n}x{n}"))
        return None
    m = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(m)):
        issues.append(Issue("NON_FINITE", field, "contains NaN or infinity"))
        return None
    return m


def _is_symmetric(m: np.ndarray, atol: float) -> bool:
    scale = max(1.0, float(np.max(np.abs(m)))) if m.size else 1.0
    return bool(np.all(np.abs(m - m.T) <= atol * scale))


def validate_request(raw: dict[str, Any], config: EngineConfig | None = None) -> Request:
    """Parse and validate a request dict. Raises InputValidationError listing every issue found."""
    config = config or EngineConfig()
    try:
        req = Request.model_validate(raw)
    except ValidationError as exc:
        issues = [
            Issue("SCHEMA", ".".join(str(p) for p in e["loc"]) or "<root>", e["msg"])
            for e in exc.errors()
        ]
        raise InputValidationError(issues) from None

    issues: list[Issue] = []
    add = lambda code, field, msg: issues.append(Issue(code, field, msg))  # noqa: E731

    if req.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        add("UNSUPPORTED_SCHEMA_VERSION", "schema_version", f"supported: {SUPPORTED_SCHEMA_VERSIONS}")

    d, c, m, e = req.data, req.constraints, req.model, req.execution

    # asset_ids
    ids = d.asset_ids
    n = len(ids)
    if n == 0:
        add("EMPTY", "data.asset_ids", "at least one asset is required")
    if n > MAX_ASSETS:
        add("TOO_MANY_ASSETS", "data.asset_ids", f"N={n} exceeds {MAX_ASSETS}")
    if len(set(ids)) != n:
        dup = sorted({a for a in ids if ids.count(a) > 1})
        add("DUPLICATE_ID", "data.asset_ids", f"duplicates: {dup}")
    if any(not a for a in ids):
        add("EMPTY_ID", "data.asset_ids", "asset IDs must be non-empty strings")

    # utility
    if len(d.utility) != n:
        add("DIMENSION_MISMATCH", "data.utility", f"length {len(d.utility)} != N={n}")
    else:
        u = np.asarray(d.utility, dtype=float)
        if not np.all(np.isfinite(u)):
            add("NON_FINITE", "data.utility", "contains NaN or infinity")
        elif np.any(u < 0) or np.any(u > 1):
            add("OUT_OF_RANGE", "data.utility", "values must satisfy 0 <= u <= 1")

    # covariance
    cov = _matrix(d.covariance_annual, n, "data.covariance_annual", issues)
    if cov is not None and n > 0:
        if not _is_symmetric(cov, config.symmetry_atol):
            add("NOT_SYMMETRIC", "data.covariance_annual", "matrix is not symmetric")
        else:
            min_eig = float(np.linalg.eigvalsh(cov).min())
            if min_eig < config.psd_min_eigenvalue:
                add(
                    "NOT_PSD",
                    "data.covariance_annual",
                    f"minimum eigenvalue {min_eig!r} < {config.psd_min_eigenvalue!r} (no auto-correction)",
                )

    # overlap
    if d.overlap is None:
        if m.weights.overlap != 0:
            add("OVERLAP_WEIGHT_WITHOUT_DATA", "model.weights.overlap", "must be 0 when data.overlap is null")
    else:
        ov = _matrix(d.overlap, n, "data.overlap", issues)
        if ov is not None and n > 0:
            if not _is_symmetric(ov, config.symmetry_atol):
                add("NOT_SYMMETRIC", "data.overlap", "matrix is not symmetric")
            if np.any(ov < 0) or np.any(ov > 1):
                add("OUT_OF_RANGE", "data.overlap", "values must satisfy 0 <= O <= 1")
            if np.any(np.diag(ov) != 0):
                add("NONZERO_DIAGONAL", "data.overlap", "diagonal must be 0")

    # constraints
    k = c.select_k
    if not (0 < k <= n):
        add("INVALID_K", "constraints.select_k", f"must satisfy 0 < K <= N (K={k}, N={n})")
    inc, exc_ = c.must_include, c.must_exclude
    for name, lst in (("must_include", inc), ("must_exclude", exc_)):
        unknown = [a for a in lst if a not in ids]
        if unknown:
            add("UNKNOWN_ID", f"constraints.{name}", f"not in asset_ids: {unknown}")
        if len(set(lst)) != len(lst):
            add("DUPLICATE_ID", f"constraints.{name}", "contains duplicates")
    both = sorted(set(inc) & set(exc_))
    if both:
        add("INCLUDE_EXCLUDE_CONFLICT", "constraints", f"in both include and exclude: {both}")
    if len(set(inc)) > k:
        add("INFEASIBLE_CONSTRAINTS", "constraints.must_include", f"|include|={len(set(inc))} > K={k}")
    if n - len(set(exc_)) < k:
        add("INFEASIBLE_CONSTRAINTS", "constraints.must_exclude", f"N-|exclude|={n - len(set(exc_))} < K={k}")

    # model
    if not (np.isfinite(m.risk_scale) and m.risk_scale > 0):
        add("OUT_OF_RANGE", "model.risk_scale", "must be finite and > 0")
    for grp, obj in (("weights", m.weights), ("penalties", m.penalties)):
        for key, val in obj.model_dump().items():
            if not (np.isfinite(val) and val >= 0):
                add("OUT_OF_RANGE", f"model.{grp}.{key}", "must be finite and >= 0")

    # execution
    if e.allow_qpu:
        add("QPU_NOT_ALLOWED", "execution.allow_qpu", "real QPU execution is not allowed")
    if e.mode != "quantum_circuit_simulator":
        add("UNSUPPORTED_MODE", "execution.mode", "only 'quantum_circuit_simulator' is supported")
    if e.algorithm != "QAOA":
        add("UNSUPPORTED_ALGORITHM", "execution.algorithm", "only 'QAOA' is supported")
    if e.depth < 1:
        add("OUT_OF_RANGE", "execution.depth", "must be >= 1")
    elif e.depth > 1 and not config.allow_depth_gt_1:
        add("DEPTH_NOT_APPROVED", "execution.depth", "depth > 1 requires the allow_depth_gt_1 config flag")
    if not (0 < e.max_wall_seconds <= MAX_WALL_SECONDS):
        add("OUT_OF_RANGE", "execution.max_wall_seconds", f"must satisfy 0 < s <= {MAX_WALL_SECONDS}")
    if not (1 <= e.max_objective_evaluations <= MAX_OBJECTIVE_EVALUATIONS):
        add("OUT_OF_RANGE", "execution.max_objective_evaluations", f"must be 1..{MAX_OBJECTIVE_EVALUATIONS}")
    if e.max_starts != MAX_STARTS:
        add("OUT_OF_RANGE", "execution.max_starts", f"must be {MAX_STARTS}")
    if not (1 <= e.shots_per_circuit <= MAX_SHOTS_PER_CIRCUIT):
        add("OUT_OF_RANGE", "execution.shots_per_circuit", f"must be 1..{MAX_SHOTS_PER_CIRCUIT}")
    if e.seed < 0:
        add("OUT_OF_RANGE", "execution.seed", "must be >= 0")
    if not (1 <= e.top_k <= MAX_TOP_K):
        add("OUT_OF_RANGE", "execution.top_k", f"must be 1..{MAX_TOP_K}")

    if issues:
        raise InputValidationError(issues)
    return req
