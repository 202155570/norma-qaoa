import itertools

import numpy as np
import pytest

from conftest import close, random_request
from norma_qaoa.objective import (
    all_bit_vectors,
    batch_objective,
    components,
    is_feasible,
    objective_base,
    objective_penalized,
    violations,
)
from norma_qaoa.problem import Problem
from norma_qaoa.qubo import build_qubo, evaluate_qubo
from norma_qaoa.schema import validate_request


@pytest.fixture
def toy(toy_raw):
    return Problem.from_request(validate_request(toy_raw))


def test_toy_A_D(toy):
    x = [1, 0, 0, 1]
    c = components(toy, x)
    assert close(c["risk"], 0.26) and close(c["overlap"], 0.0) and close(c["utility"], 0.60)
    assert close(objective_base(toy, x), 0.02)
    assert close(objective_penalized(toy, x), 0.02)
    assert is_feasible(toy, x)


def test_toy_C_D(toy):
    x = [0, 0, 1, 1]
    c = components(toy, x)
    assert close(c["risk"], 0.10) and close(c["overlap"], 0.15) and close(c["utility"], 0.475)
    assert close(objective_base(toy, x), -0.0525)
    assert close(objective_penalized(toy, x), -0.0525)


def test_toy_violations(toy):
    assert violations(toy, [1, 1, 0, 0]) == ["MUST_INCLUDE_MISSING: ETF_D"]
    assert violations(toy, [1, 1, 0, 1]) == ["CARDINALITY: selected 3 != K=2"]
    # F = G + 4*(3-2)^2 for x = A,B,D
    x = [1, 1, 0, 1]
    assert close(objective_penalized(toy, x), objective_base(toy, x) + 4.0)


def _all_x(n):
    return [list(x) for x in itertools.product([0, 1], repeat=n)]


def test_toy_qubo_matches_direct_all_16(toy):
    qubo = build_qubo(toy)
    assert np.allclose(qubo.Q, np.triu(qubo.Q))
    for x in _all_x(4):
        assert close(evaluate_qubo(qubo, x), objective_penalized(toy, x)), x


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("n,k,overlap", [(5, 2, True), (6, 3, False), (7, 1, True), (8, 4, True)])
def test_random_qubo_matches_direct(seed, n, k, overlap):
    p = Problem.from_request(validate_request(random_request(seed, n, k, overlap=overlap)))
    qubo = build_qubo(p)
    for x in _all_x(n):
        assert close(evaluate_qubo(qubo, x), objective_penalized(p, x)), x


def test_k1_overlap_is_zero(toy_raw):
    toy_raw["constraints"]["select_k"] = 1
    p = Problem.from_request(validate_request(toy_raw))
    assert components(p, [0, 0, 1, 1])["overlap"] == 0.0
    qubo = build_qubo(p)
    for x in _all_x(4):
        assert close(evaluate_qubo(qubo, x), objective_penalized(p, x))


def test_batch_matches_scalar():
    p = Problem.from_request(validate_request(random_request(3, 6, 3)))
    X = all_bit_vectors(6)
    F, G, feas = batch_objective(p, X)
    for row, f, g, ok in zip(X, F, G, feas):
        assert close(f, objective_penalized(p, row))
        assert close(g, objective_base(p, row))
        assert ok == is_feasible(p, row)


def test_all_bit_vectors_order():
    X = all_bit_vectors(3)
    assert X[1].tolist() == [1, 0, 0]  # k=1 -> asset 0 selected
    assert X[6].tolist() == [0, 1, 1]
