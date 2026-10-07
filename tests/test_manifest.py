import copy

import numpy as np
import pytest

from conftest import close
from norma_qaoa.engine import run_job
from norma_qaoa.manifest import canonical_json, sha256_of
from norma_qaoa.objective import objective_base, objective_penalized
from norma_qaoa.problem import Problem
from norma_qaoa.schema import validate_request


def test_canonical_json_rules():
    assert canonical_json({"b": 1, "a": [0.1, np.float64(0.2)]}) == '{"a":[0.1,0.2],"b":1}'
    assert sha256_of({"x": 1, "y": 2}) == sha256_of({"y": 2, "x": 1})
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


@pytest.fixture(scope="module")
def two_runs():
    import json

    from conftest import TOY

    raw = json.loads(TOY.read_text(encoding="utf-8"))
    return raw, run_job(copy.deepcopy(raw)), run_job(copy.deepcopy(raw))


def test_hashes_deterministic(two_runs):
    _, a, b = two_runs
    for key in ("input_hash", "qubo_hash", "circuit_hash", "backend_circuit_hash"):
        assert a.manifest[key] == b.manifest[key] and len(a.manifest[key]) == 64
    assert a.result["job_id"] != b.result["job_id"]


def test_input_hash_changes_with_input(two_runs):
    raw, a, _ = two_runs
    r = copy.deepcopy(raw)
    r["model"]["weights"]["risk"] = 1.5
    assert sha256_of(r) != a.manifest["input_hash"]
    assert sha256_of(raw) == a.manifest["input_hash"]


def test_manifest_required_fields(two_runs):
    _, a, _ = two_runs
    m = a.manifest
    for key in (
        "request_id", "job_id", "input_hash", "qubo_hash", "circuit_hash", "scale_factor", "qubits", "depth",
        "seeds", "evaluations", "circuits", "shots", "started_utc", "finished_utc", "elapsed_ms", "trace",
        "versions", "budget", "penalty_check", "backend", "counts_source", "final_counts", "hash_rule",
    ):
        assert key in m, key
    assert set(m["seeds"]) == {"master", "simulator", "transpiler", "optimizer", "random_baseline"}
    for pkg in ("python", "qiskit", "qiskit-aer", "numpy"):
        assert m["versions"][pkg]
    assert m["started_utc"].endswith("Z") and m["hardware_qpu_used"] is False
    assert m["backend"]["kind"] == "local_simulator"
    assert len(m["trace"]) == m["circuits"]
    assert {"gamma", "beta", "cost", "sim_seed"} <= set(m["trace"][0])


def test_result_schema_and_recompute(two_runs):
    raw, a, _ = two_runs
    r = a.result
    assert set(r) == {
        "schema_version", "request_id", "job_id", "status", "stop_reason", "snapshot_id", "model_version",
        "asset_order", "candidates", "execution", "artifact_manifest_id", "proven_infeasible",
    }
    assert r["execution"]["mode"] == "quantum_circuit_simulator" and r["execution"]["hardware_qpu_used"] is False
    assert r["artifact_manifest_id"] == a.manifest["manifest_id"]
    p = Problem.from_request(validate_request(raw))
    for c in r["candidates"]:
        assert set(c) >= {
            "candidate_id", "selected_asset_ids", "bit_vector", "origin", "objective_base", "objective_penalized",
            "components", "feasible", "violations", "sample_count",
        }
        assert close(c["objective_penalized"], objective_penalized(p, c["bit_vector"]))
        assert close(c["objective_base"], objective_base(p, c["bit_vector"]))
        assert c["selected_asset_ids"] == [r["asset_order"][i] for i, b in enumerate(c["bit_vector"]) if b]
        # sample_count must equal the raw counts of that vector
        bitstring = "".join(str(b) for b in reversed(c["bit_vector"]))
        assert c["sample_count"] == a.manifest["final_counts"][bitstring]
