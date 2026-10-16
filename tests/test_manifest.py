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
        "request_id", "job_id", "attempt_id", "input_hash", "qubo_hash", "circuit_hash", "scale_factor",
        "qubits", "depth", "seeds", "evaluations", "circuits", "shots", "started_utc", "finished_utc",
        "elapsed_ms", "queue_wait_ms", "container", "resources", "trace",
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


# --------------------------------------------- spec p.19 fields added for container delivery
def test_attempt_id_is_per_attempt_not_per_request(two_runs, toy_raw):
    """A retry keeps request_id and gets a new attempt_id."""
    _, a, b = two_runs
    assert a.manifest["request_id"] == b.manifest["request_id"]
    assert a.manifest["attempt_id"] != b.manifest["attempt_id"]
    assert run_job(copy.deepcopy(toy_raw), attempt_id="attempt-xyz").manifest["attempt_id"] == "attempt-xyz"


def test_container_identity_reads_the_entrypoint_env(monkeypatch):
    from norma_qaoa.manifest import container_identity

    for var in ("NORMA_IMAGE_REF", "NORMA_IMAGE_DIGEST", "NORMA_IMAGE_BUILT_UTC"):
        monkeypatch.delenv(var, raising=False)
    bare = container_identity()
    assert bare["image_ref"] is None and bare["image_digest"] is None

    monkeypatch.setenv("NORMA_IMAGE_REF", "norma-qaoa:0.1.0")
    monkeypatch.setenv("NORMA_IMAGE_DIGEST", "sha256:" + "ab" * 32)
    got = container_identity()
    assert got["image_ref"] == "norma-qaoa:0.1.0"
    assert got["image_digest"] == "sha256:" + "ab" * 32
    assert got["in_container"] is True


def test_resource_usage_shape():
    from norma_qaoa.manifest import resource_usage

    r = resource_usage(1.25)
    assert r["cpu_seconds"] == 1.25
    assert r["gpu"] is None  # the simulator runs on CPU; never claimed otherwise
    for key in ("cpu_user_seconds", "cpu_system_seconds", "max_rss_bytes", "max_rss_scope", "source"):
        assert key in r, key
    # Off POSIX the resource module is absent and the RSS fields are null by design.
    assert r["max_rss_bytes"] is None or (isinstance(r["max_rss_bytes"], int) and r["max_rss_bytes"] > 0)


def test_queue_wait_is_measured_from_accepted_at(two_runs, toy_raw):
    import time as _time

    _, a, _ = two_runs
    assert a.manifest["queue_wait_ms"] is None  # not supplied -> null, never a guessed 0

    out = run_job(copy.deepcopy(toy_raw), accepted_at=_time.time() - 2.0)
    assert out.manifest["queue_wait_ms"] >= 2000


def test_job_resources_are_recorded(two_runs):
    _, a, _ = two_runs
    res = a.manifest["resources"]
    assert isinstance(res["cpu_seconds"], float) and res["cpu_seconds"] >= 0.0
    assert a.manifest["container"]["source"].startswith("environment: ")
