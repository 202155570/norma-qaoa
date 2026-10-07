import math

from conftest import close, random_request
from norma_qaoa.baseline import exhaustive_baseline, penalty_check, random_baseline
from norma_qaoa.objective import is_feasible
from norma_qaoa.problem import Problem
from norma_qaoa.schema import validate_request


def test_toy_exhaustive(toy_raw):
    p = Problem.from_request(validate_request(toy_raw))
    ex = exhaustive_baseline(p)
    assert ex.n_k_subsets == 6
    assert ex.n_feasible == 3  # ETF_D fixed, choose 1 of 3
    opt = ex.optimum
    assert opt.bit_vector == (0, 0, 1, 1)
    assert close(opt.objective_penalized, -0.0525) and close(opt.objective_base, -0.0525)
    assert [r.rank for r in ex.ranking] == [1, 2, 3]
    assert ex.rank_of(0.02) == 2
    d = ex.to_dict(p)
    assert d["origin"] == "classical_baseline"
    assert d["optimum"]["selected_asset_ids"] == ["ETF_C", "ETF_D"]


def test_synthetic_counts(synth_raw):
    p = Problem.from_request(validate_request(synth_raw))
    ex = exhaustive_baseline(p)
    assert ex.n_k_subsets == 924
    assert ex.n_feasible == math.comb(11, 5) == 462
    assert all(is_feasible(p, r.bit_vector) for r in ex.ranking)
    fs = [r.objective_penalized for r in ex.ranking]
    assert fs == sorted(fs)


def test_exclude_respected():
    p = Problem.from_request(validate_request(random_request(4, 7, 3, n_inc=1, n_exc=2)))
    ex = exhaustive_baseline(p)
    assert ex.n_feasible == math.comb(7 - 1 - 2, 2)


def test_penalty_check_toy(toy_raw):
    p = Problem.from_request(validate_request(toy_raw))
    pc = penalty_check(p)
    assert pc["passed"] and pc["n_bit_vectors"] == 16
    assert pc["argmin_bit_vector"] == [0, 0, 1, 1]


def test_penalty_check_detects_weak_penalty(toy_raw):
    toy_raw["model"]["penalties"] = {"cardinality": 0.0, "fixed": 0.0}
    p = Problem.from_request(validate_request(toy_raw))
    pc = penalty_check(p)
    assert not pc["passed"] and "warning" in pc
    # penalties untouched
    assert p.Lk == 0.0 and p.Lf == 0.0


def test_random_baseline_reproducible(toy_raw):
    p = Problem.from_request(validate_request(toy_raw))
    a = random_baseline(p, 1024, 5)
    b = random_baseline(p, 1024, 5)
    assert a == b
    assert 0 < a["feasible_ratio"] < 1
    assert a["origin"] == "classical_baseline"
