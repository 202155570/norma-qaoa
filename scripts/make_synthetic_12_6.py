"""Generate fixtures/synthetic_12_6.json (N=12, K=6) from a fixed seed.

Covariance is A @ A.T rescaled by a diagonal matrix D to annual-volatility levels
(D A A^T D = (DA)(DA)^T, so it stays PSD). Data is synthetic and contains no real
market information.

Usage: python scripts/make_synthetic_12_6.py [--out fixtures/synthetic_12_6.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

GENERATOR_SEED = 20261001
N, K = 12, 6


def build() -> dict:
    rng = np.random.default_rng(GENERATOR_SEED)
    ids = [f"SYN_{i + 1:02d}" for i in range(N)]

    a = rng.normal(size=(N, N))
    target_vol = rng.uniform(0.08, 0.30, size=N)
    raw = a @ a.T
    dscale = np.diag(target_vol / np.sqrt(np.diag(raw)))
    cov = dscale @ raw @ dscale
    cov = np.round((cov + cov.T) / 2, 8)
    min_eig = float(np.linalg.eigvalsh(cov).min())
    assert min_eig > 0, f"covariance not PD after rounding: {min_eig}"

    utility = np.round(rng.uniform(0.2, 0.9, size=N), 3)

    overlap = np.zeros((N, N))
    for i in range(N):
        for j in range(i + 1, N):
            if rng.uniform() < 0.3:
                overlap[i, j] = overlap[j, i] = round(float(rng.uniform(0.05, 0.6)), 2)

    include = [ids[int(rng.integers(N))]]

    return {
        "schema_version": "1.0",
        "request_id": "synthetic-12-6-001",
        "data": {
            "snapshot_id": "synthetic-12-6-20261001",
            "as_of_utc": "2026-10-01T00:00:00Z",
            "base_currency": "USD",
            "source_kind": "synthetic_fixture",
            "generator": {"script": "scripts/make_synthetic_12_6.py", "seed": GENERATOR_SEED},
            "asset_ids": ids,
            "utility": utility.tolist(),
            "covariance_annual": cov.tolist(),
            "overlap": overlap.tolist(),
        },
        "constraints": {"select_k": K, "must_include": include, "must_exclude": []},
        "model": {
            "version": "selection-v1-draft",
            "risk_scale": 0.05,
            "weights": {"risk": 1.0, "overlap": 0.25, "utility": 0.4},
            "penalties": {"cardinality": 4.0, "fixed": 4.0},
        },
        "execution": {
            "mode": "quantum_circuit_simulator",
            "algorithm": "QAOA",
            "depth": 1,
            "max_wall_seconds": 300,
            "max_objective_evaluations": 60,
            "max_starts": 1,
            "shots_per_circuit": 1024,
            "seed": 11,
            "allow_qpu": False,
            "top_k": 5,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_12_6.json"))
    args = ap.parse_args()
    Path(args.out).write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
