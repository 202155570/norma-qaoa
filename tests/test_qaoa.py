import copy

import pytest

from norma_qaoa.backends.aer import AerBackend
from norma_qaoa.config import EngineConfig
from norma_qaoa.engine import run_job
from norma_qaoa.errors import ConfigError
from norma_qaoa.qaoa import Budget, derive_seeds


class StepClock:
    """Fake monotonic clock: advances `step` seconds on every call."""

    def __init__(self, step: float):
        self.t, self.step = 1000.0, step

    def __call__(self) -> float:
        self.t += self.step
        return self.t


def phases(manifest):
    out = {}
    for r in manifest["trace"]:
        out[r["phase"]] = out.get(r["phase"], 0) + 1
    return out


def test_budget_default_60(toy_raw):
    out = run_job(toy_raw)
    m, ex = out.manifest, out.result["execution"]
    ph = phases(m)
    assert ph["grid"] == 49 and ph["final"] == 1 and ph["cobyla"] <= 10
    assert ex["objective_evaluations"] == len(m["trace"]) == ex["circuits_total"] <= 60
    assert ex["shots_total"] == 1024 * ex["circuits_total"]
    assert m["budget"]["final_sampling_counted_in_budget"] is True
    assert m["counts_source"] == {"phase": "final", "evaluation_index": len(m["trace"])}


def test_budget_final_not_counted(toy_raw):
    out = run_job(toy_raw, EngineConfig(count_final_in_budget=False))
    m, ex = out.manifest, out.result["execution"]
    ph = phases(m)
    assert ph["grid"] == 49 and ph["cobyla"] <= 11 and ph["final"] == 1
    assert ex["objective_evaluations"] == ph["grid"] + ph["cobyla"] <= 60
    assert ex["circuits_total"] == ex["objective_evaluations"] + 1


def test_budget_too_small_for_grid(toy_raw):
    toy_raw["execution"]["max_objective_evaluations"] = 40
    with pytest.raises(ConfigError):
        run_job(toy_raw)
    out = run_job(toy_raw, EngineConfig(grid_size=5))
    assert phases(out.manifest)["grid"] == 25
    assert out.result["execution"]["objective_evaluations"] <= 40


def test_budget_plan():
    b = Budget.plan(60, EngineConfig())
    assert (b.grid_points, b.cobyla_max, b.optimization_limit) == (49, 10, 59)


def test_reproducible_with_same_seed(toy_raw):
    a = run_job(copy.deepcopy(toy_raw)).manifest
    b = run_job(copy.deepcopy(toy_raw)).manifest
    assert a["final_counts"] == b["final_counts"]
    assert [r["cost"] for r in a["trace"]] == [r["cost"] for r in b["trace"]]
    assert a["seeds"] == b["seeds"] == derive_seeds(7)


def test_time_limit_mid_grid(toy_raw):
    toy_raw["execution"]["top_k"] = 2
    toy_raw["execution"]["max_wall_seconds"] = 20
    out = run_job(toy_raw, clock=StepClock(1.0))
    r, m = out.result, out.manifest
    assert r["stop_reason"] == "TIME_LIMIT"
    assert r["status"] == "PARTIAL"  # spec p.5: compute limit -> PARTIAL even with >= top_k candidates
    assert len(r["candidates"]) == 2
    assert "final" not in phases(m) and len(m["trace"]) < 49
    assert m["counts_source"]["phase"] == "best_evaluation"
    assert all(c["origin"] == "simulator_sample" for c in r["candidates"])


def test_time_limit_before_any_circuit(toy_raw):
    toy_raw["execution"]["max_wall_seconds"] = 1
    out = run_job(toy_raw, clock=StepClock(10.0))
    r = out.result
    assert (r["status"], r["stop_reason"]) == ("FAILED", "TIME_LIMIT")
    assert r["candidates"] == [] and r["execution"]["circuits_total"] == 0
    assert r["proven_infeasible"] is False


class BrokenAer(AerBackend):
    def run(self, parameter_sets, shots, seed):
        raise RuntimeError("simulated backend crash")


def test_simulator_error_no_fallback(toy_raw):
    out = run_job(toy_raw, backend=BrokenAer())
    r, m = out.result, out.manifest
    assert (r["status"], r["stop_reason"]) == ("FAILED", "SIMULATOR_ERROR")
    assert r["candidates"] == []
    assert r["execution"]["backend_name"] == "aer_simulator"
    assert "simulated backend crash" in m["error"]


def test_depth_2_with_flag(toy_raw):
    toy_raw["execution"]["depth"] = 2
    out = run_job(toy_raw, EngineConfig(allow_depth_gt_1=True))
    t = out.manifest["trace"]
    assert all(len(r["gamma"]) == 2 and len(r["beta"]) == 2 for r in t)
    assert out.result["execution"]["depth"] == 2


def test_quantinuum_local_job(toy_raw):
    from norma_qaoa.errors import BackendUnavailableError

    try:
        out = run_job(toy_raw, EngineConfig(backend="quantinuum_local", grid_size=3))
    except BackendUnavailableError as exc:
        pytest.skip(f"quantinuum_local unavailable: {exc}")
    r = out.result
    assert r["execution"]["backend_name"] == "quantinuum_H2-1LE"
    assert r["execution"]["hardware_qpu_used"] is False
    assert r["candidates"] and r["candidates"][0]["selected_asset_ids"] == ["ETF_C", "ETF_D"]
