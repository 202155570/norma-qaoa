import copy

import pytest

from norma_qaoa.config import EngineConfig
from norma_qaoa.errors import InputValidationError
from norma_qaoa.schema import validate_request


def codes(raw, config=None):
    with pytest.raises(InputValidationError) as ei:
        validate_request(raw, config)
    return {(i.code, i.field) for i in ei.value.issues}


def mutate(raw, fn):
    r = copy.deepcopy(raw)
    fn(r)
    return r


def test_fixtures_valid(toy_raw, synth_raw):
    assert validate_request(toy_raw).constraints.select_k == 2
    assert validate_request(synth_raw).constraints.select_k == 6


@pytest.mark.parametrize(
    "fn, expected",
    [
        (lambda r: r["data"].update(asset_ids=["ETF_A", "ETF_A", "ETF_C", "ETF_D"]), ("DUPLICATE_ID", "data.asset_ids")),
        (lambda r: r["data"].update(utility=[0.7, 0.6, 0.4]), ("DIMENSION_MISMATCH", "data.utility")),
        (lambda r: r["data"].update(utility=[1.2, 0.6, 0.4, 0.5]), ("OUT_OF_RANGE", "data.utility")),
        (lambda r: r["data"].update(utility=[float("nan"), 0.6, 0.4, 0.5]), ("NON_FINITE", "data.utility")),
        (lambda r: r["data"]["covariance_annual"].pop(), ("DIMENSION_MISMATCH", "data.covariance_annual")),
        (lambda r: r["data"]["covariance_annual"][0].__setitem__(1, 0.03), ("NOT_SYMMETRIC", "data.covariance_annual")),
        (
            lambda r: r["data"].update(covariance_annual=[[0.04, 0.1, 0, 0], [0.1, 0.04, 0, 0], [0, 0, 0.01, 0], [0, 0, 0, 0.01]]),
            ("NOT_PSD", "data.covariance_annual"),
        ),
        (lambda r: r["data"]["covariance_annual"][2].__setitem__(2, float("inf")), ("NON_FINITE", "data.covariance_annual")),
        (lambda r: r["data"]["overlap"][0].__setitem__(0, 0.1), ("NONZERO_DIAGONAL", "data.overlap")),
        (lambda r: r["data"]["overlap"][0].__setitem__(1, 0.5), ("NOT_SYMMETRIC", "data.overlap")),
        (
            lambda r: (r["data"]["overlap"][0].__setitem__(1, 1.5), r["data"]["overlap"][1].__setitem__(0, 1.5)),
            ("OUT_OF_RANGE", "data.overlap"),
        ),
        (lambda r: r["data"].update(overlap=None), ("OVERLAP_WEIGHT_WITHOUT_DATA", "model.weights.overlap")),
        (lambda r: r["constraints"].update(select_k=0), ("INVALID_K", "constraints.select_k")),
        (lambda r: r["constraints"].update(select_k=5), ("INVALID_K", "constraints.select_k")),
        (lambda r: r["constraints"].update(must_exclude=["ETF_D"]), ("INCLUDE_EXCLUDE_CONFLICT", "constraints")),
        (lambda r: r["constraints"].update(must_include=["ETF_A", "ETF_B", "ETF_D"]), ("INFEASIBLE_CONSTRAINTS", "constraints.must_include")),
        (lambda r: r["constraints"].update(must_exclude=["ETF_A", "ETF_B", "ETF_C"]), ("INFEASIBLE_CONSTRAINTS", "constraints.must_exclude")),
        (lambda r: r["constraints"].update(must_include=["ETF_Z"]), ("UNKNOWN_ID", "constraints.must_include")),
        (lambda r: r["model"].update(risk_scale=0.0), ("OUT_OF_RANGE", "model.risk_scale")),
        (lambda r: r["model"]["weights"].update(risk=-1.0), ("OUT_OF_RANGE", "model.weights.risk")),
        (lambda r: r["model"]["penalties"].update(fixed=-0.1), ("OUT_OF_RANGE", "model.penalties.fixed")),
        (lambda r: r["execution"].update(allow_qpu=True), ("QPU_NOT_ALLOWED", "execution.allow_qpu")),
        (lambda r: r["execution"].update(depth=2), ("DEPTH_NOT_APPROVED", "execution.depth")),
        (lambda r: r["execution"].update(shots_per_circuit=2048), ("OUT_OF_RANGE", "execution.shots_per_circuit")),
        (lambda r: r["execution"].update(max_objective_evaluations=61), ("OUT_OF_RANGE", "execution.max_objective_evaluations")),
        (lambda r: r["execution"].update(max_starts=2), ("OUT_OF_RANGE", "execution.max_starts")),
        (lambda r: r["execution"].update(max_wall_seconds=301), ("OUT_OF_RANGE", "execution.max_wall_seconds")),
        (lambda r: r["execution"].update(top_k=6), ("OUT_OF_RANGE", "execution.top_k")),
        (lambda r: r["execution"].update(mode="mock"), ("UNSUPPORTED_MODE", "execution.mode")),
        (lambda r: r.update(schema_version="2.0"), ("UNSUPPORTED_SCHEMA_VERSION", "schema_version")),
    ],
)
def test_rejections(toy_raw, fn, expected):
    assert expected in codes(mutate(toy_raw, fn))


def test_too_many_assets(toy_raw):
    n = 17
    r = mutate(toy_raw, lambda r: None)
    r["data"].update(
        asset_ids=[f"A{i}" for i in range(n)],
        utility=[0.5] * n,
        covariance_annual=[[0.01 if i == j else 0.0 for j in range(n)] for i in range(n)],
        overlap=None,
    )
    r["model"]["weights"]["overlap"] = 0.0
    r["constraints"]["must_include"] = []
    assert ("TOO_MANY_ASSETS", "data.asset_ids") in codes(r)


def test_missing_fields_are_not_filled(toy_raw):
    r = mutate(toy_raw, lambda r: r["data"].pop("overlap"))
    assert ("SCHEMA", "data.overlap") in codes(r)
    r = mutate(toy_raw, lambda r: r["constraints"].pop("must_exclude"))
    assert ("SCHEMA", "constraints.must_exclude") in codes(r)
    r = mutate(toy_raw, lambda r: r["execution"].pop("seed"))
    assert ("SCHEMA", "execution.seed") in codes(r)


def test_type_strictness(toy_raw):
    r = mutate(toy_raw, lambda r: r["constraints"].update(select_k="2"))
    assert ("SCHEMA", "constraints.select_k") in codes(r)
    r = mutate(toy_raw, lambda r: r["execution"].update(unknown_field=1))
    assert ("SCHEMA", "execution.unknown_field") in codes(r)


def test_overlap_null_with_zero_weight_ok(toy_raw):
    r = mutate(toy_raw, lambda r: (r["data"].update(overlap=None), r["model"]["weights"].update(overlap=0.0)))
    assert validate_request(r).data.overlap is None


def test_depth_flag(toy_raw):
    r = mutate(toy_raw, lambda r: r["execution"].update(depth=2))
    assert validate_request(r, EngineConfig(allow_depth_gt_1=True)).execution.depth == 2


def test_psd_tiny_negative_tolerated(toy_raw):
    # Eigenvalue -1e-12 is within the -1e-10 tolerance; the matrix is not modified.
    r = mutate(toy_raw, lambda r: None)
    r["data"]["covariance_annual"] = [[1.0, 1.0, 0, 0], [1.0, 1.0 - 2e-12, 0, 0], [0, 0, 0.01, 0], [0, 0, 0, 0.01]]
    req = validate_request(r)
    assert req.data.covariance_annual[1][1] == 1.0 - 2e-12
