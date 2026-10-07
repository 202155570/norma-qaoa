from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
TOY = ROOT / "fixtures" / "toy_4.json"
SYNTH = ROOT / "fixtures" / "synthetic_12_6.json"

# Spec p.18 tolerance: abs 1e-8 + rel 1e-6.
ATOL, RTOL = 1e-8, 1e-6


def close(a: float, b: float) -> bool:
    return abs(a - b) <= ATOL + RTOL * abs(b)


@pytest.fixture
def toy_raw() -> dict:
    return json.loads(TOY.read_text(encoding="utf-8"))


@pytest.fixture
def synth_raw() -> dict:
    return json.loads(SYNTH.read_text(encoding="utf-8"))


def random_request(seed: int, n: int, k: int, *, overlap: bool = True, n_inc: int = 1, n_exc: int = 1) -> dict:
    """Random valid request (PSD covariance, symmetric zero-diagonal overlap)."""
    rng = np.random.default_rng(seed)
    a = rng.normal(size=(n, n))
    cov = (a @ a.T) * 0.01
    ov = rng.uniform(0, 1, size=(n, n)) * (rng.uniform(size=(n, n)) < 0.5)
    ov = np.triu(ov, 1)
    ov = ov + ov.T
    ids = [f"A{i}" for i in range(n)]
    perm = rng.permutation(n)
    inc = [ids[i] for i in perm[:n_inc]]
    exc = [ids[i] for i in perm[n_inc : n_inc + n_exc]]
    raw = json.loads(TOY.read_text(encoding="utf-8"))
    raw = copy.deepcopy(raw)
    raw["data"].update(
        asset_ids=ids,
        utility=rng.uniform(0, 1, size=n).tolist(),
        covariance_annual=cov.tolist(),
        overlap=ov.tolist() if overlap else None,
    )
    raw["constraints"] = {"select_k": k, "must_include": inc, "must_exclude": exc}
    raw["model"]["risk_scale"] = float(rng.uniform(0.02, 0.2))
    raw["model"]["weights"] = {
        "risk": float(rng.uniform(0, 2)),
        "overlap": float(rng.uniform(0, 1)) if overlap else 0.0,
        "utility": float(rng.uniform(0, 1)),
    }
    raw["model"]["penalties"] = {"cardinality": float(rng.uniform(0.5, 5)), "fixed": float(rng.uniform(0.5, 5))}
    return raw
