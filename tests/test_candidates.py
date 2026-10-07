import pytest

from conftest import close
from norma_qaoa.candidates import build_candidates, decide_status, greedy_repair
from norma_qaoa.problem import Problem
from norma_qaoa.schema import validate_request


@pytest.fixture
def toy(toy_raw):
    return Problem.from_request(validate_request(toy_raw))


# Qiskit bitstrings for toy (asset i = qubit i = i-th char from the right):
CD = "1100"  # ETF_C, ETF_D  F=-0.0525
AD = "1001"  # ETF_A, ETF_D  F= 0.02
BD = "1010"  # ETF_B, ETF_D  F= 0.096
AB = "0011"  # infeasible (no ETF_D)
NONE = "0000"  # infeasible


def test_sort_filter_dedupe(toy):
    counts = {BD: 50, AD: 10, CD: 3, AB: 900, NONE: 61}
    cands = build_candidates(toy, counts, top_k=5)
    assert [c["selected_asset_ids"] for c in cands] == [["ETF_C", "ETF_D"], ["ETF_A", "ETF_D"], ["ETF_B", "ETF_D"]]
    assert [c["sample_count"] for c in cands] == [3, 10, 50]
    assert [c["candidate_id"] for c in cands] == ["cand-01", "cand-02", "cand-03"]
    assert all(c["origin"] == "simulator_sample" and c["feasible"] and c["violations"] == [] for c in cands)
    assert close(cands[0]["objective_penalized"], -0.0525)
    assert cands[0]["bit_vector"] == [0, 0, 1, 1]


def test_top_k_cut(toy):
    cands = build_candidates(toy, {BD: 1, AD: 1, CD: 1}, top_k=2)
    assert [c["bit_vector"] for c in cands] == [[0, 0, 1, 1], [1, 0, 0, 1]]


def test_no_counts(toy):
    assert build_candidates(toy, None, 5) == []
    assert build_candidates(toy, {AB: 10}, 5) == []


def test_repair_off_by_default_and_labelled_when_on(toy):
    counts = {AD: 4, NONE: 7, AB: 2}
    assert len(build_candidates(toy, counts, 5)) == 1
    cands = build_candidates(toy, counts, 5, repair=True)
    origins = [(c["selected_asset_ids"], c["origin"]) for c in cands]
    assert origins[0] == (["ETF_A", "ETF_D"], "simulator_sample")
    rep = [c for c in cands if c["origin"] == "classical_repair"]
    assert rep and all(c["sample_count"] is None for c in rep)
    src = rep[0]["repair"]["sources"][0]
    assert "source_bit_vector" in src and src["changes"]
    # never duplicates a directly sampled vector
    assert len({tuple(c["bit_vector"]) for c in cands}) == len(cands)


def test_greedy_repair(toy):
    y, changes = greedy_repair(toy, [0, 0, 0, 0])
    assert y == (0, 0, 1, 1)  # add ETF_D (include), then lowest-F free asset ETF_C
    assert changes[0] == {"asset_id": "ETF_D", "from": 0, "to": 1, "reason": "must_include"}
    y, _ = greedy_repair(toy, [1, 1, 0, 0])
    assert y == (1, 0, 0, 1)


@pytest.mark.parametrize(
    "n, k, stop, expected",
    [
        (5, 5, None, ("SUCCEEDED", "COMPLETED")),
        (3, 5, None, ("PARTIAL", "TOP_K_NOT_REACHED")),
        (0, 5, None, ("FAILED", "NO_FEASIBLE_SAMPLE")),
        (5, 5, "TIME_LIMIT", ("PARTIAL", "TIME_LIMIT")),
        (2, 5, "TIME_LIMIT", ("PARTIAL", "TIME_LIMIT")),
        (0, 5, "TIME_LIMIT", ("FAILED", "TIME_LIMIT")),
        (0, 5, "SIMULATOR_ERROR", ("FAILED", "SIMULATOR_ERROR")),
    ],
)
def test_status_table(n, k, stop, expected):
    assert decide_status(n, k, stop) == expected
