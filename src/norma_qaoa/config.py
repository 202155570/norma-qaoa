"""Engine configuration (NORMA side). Not part of the request contract."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EngineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: Literal["aer", "quantinuum_local"] = "aer"

    # Parameter search: grid -> COBYLA -> final sampling.
    grid_size: int = Field(7, ge=1)
    gamma_range: tuple[float, float] = (0.0, math.pi)
    beta_range: tuple[float, float] = (0.0, math.pi / 2)
    cobyla_rhobeg: float = Field(0.25, gt=0)
    # Open question: does the final sampling count toward max_objective_evaluations?
    count_final_in_budget: bool = True

    # depth > 1 requires separate approval (spec p.9).
    allow_depth_gt_1: bool = False
    # Off by default. When on, repaired candidates are labelled origin="classical_repair".
    classical_repair: bool = False
    # Cloud emulators send data to a third party (spec 16). No cloud adapter exists yet.
    allow_external_transfer: bool = False

    # Input checks.
    symmetry_atol: float = Field(1e-12, ge=0)
    psd_min_eigenvalue: float = -1e-10

    # Quantinuum local emulator options.
    tket_optimisation_level: int = Field(2, ge=0, le=3)

    @model_validator(mode="after")
    def _check_ranges(self) -> "EngineConfig":
        for name in ("gamma_range", "beta_range"):
            lo, hi = getattr(self, name)
            if not (math.isfinite(lo) and math.isfinite(hi) and lo <= hi):
                raise ValueError(f"{name} must be finite with lo <= hi")
        return self

    @classmethod
    def load(cls, path: str | Path | None) -> "EngineConfig":
        if path is None:
            return cls()
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
