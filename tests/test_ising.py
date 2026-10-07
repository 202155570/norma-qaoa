"""Endianness tests: Ising diagonal * scale + offset == F(x) for every bitstring."""

import pytest

from conftest import close, random_request
from norma_qaoa.ising import bitstring_to_bit_vector, ising_energy, qubo_to_ising
from norma_qaoa.objective import objective_penalized
from norma_qaoa.problem import Problem
from norma_qaoa.qubo import build_qubo, evaluate_qubo
from norma_qaoa.schema import validate_request


def check_all_bitstrings(p: Problem):
    qubo = build_qubo(p)
    model = qubo_to_ising(qubo)
    op = model.operator(normalized=True)
    diag = op.to_matrix(sparse=True).diagonal().real
    n = p.n
    assert len(diag) == 2**n
    for k in range(2**n):
        bitstring = format(k, f"0{n}b")  # Qiskit convention: qubit 0 is the rightmost char
        x = bitstring_to_bit_vector(bitstring, n)
        f_direct = objective_penalized(p, x)
        f_qubo = evaluate_qubo(qubo, x)
        f_ising = diag[k] * model.scale_factor + model.offset
        assert close(f_qubo, f_direct), (bitstring, f_qubo, f_direct)
        assert close(f_ising, f_direct), (bitstring, f_ising, f_direct)
        assert close(ising_energy(model, x), f_direct)


def test_toy_all_16(toy_raw):
    check_all_bitstrings(Problem.from_request(validate_request(toy_raw)))


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("n,k,overlap", [(3, 1, True), (5, 2, False), (6, 3, True), (8, 3, True)])
def test_random_all_bitstrings(seed, n, k, overlap):
    check_all_bitstrings(Problem.from_request(validate_request(random_request(seed, n, k, overlap=overlap))))


def test_asymmetric_problem_catches_reversal(toy_raw):
    # Only ETF_A (asset 0) has utility; selecting it must map to the rightmost bit.
    toy_raw["data"]["utility"] = [1.0, 0.0, 0.0, 0.0]
    p = Problem.from_request(validate_request(toy_raw))
    model = qubo_to_ising(build_qubo(p))
    assert bitstring_to_bit_vector("0001", 4) == [1, 0, 0, 0]
    assert bitstring_to_bit_vector("1000", 4) == [0, 0, 0, 1]
    assert ising_energy(model, [1, 0, 0, 1]) != ising_energy(model, [0, 0, 1, 1])


def test_normalization():
    p = Problem.from_request(validate_request(random_request(1, 6, 3)))
    model = qubo_to_ising(build_qubo(p))
    op = model.operator(normalized=True)
    assert max(abs(c) for c in op.coeffs) == pytest.approx(1.0)


def test_bitstring_validation():
    with pytest.raises(ValueError):
        bitstring_to_bit_vector("012", 3)
    with pytest.raises(ValueError):
        bitstring_to_bit_vector("01", 3)
