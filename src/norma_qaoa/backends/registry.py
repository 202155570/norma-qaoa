"""Backend selection. A failing backend is never replaced by another one automatically."""

from __future__ import annotations

from norma_qaoa.backends.base import SamplingBackend
from norma_qaoa.config import EngineConfig
from norma_qaoa.errors import ConfigError

BACKEND_NAMES = ("aer", "quantinuum_local")


def create_backend(config: EngineConfig) -> SamplingBackend:
    if config.backend == "aer":
        from norma_qaoa.backends.aer import AerBackend

        return AerBackend()
    if config.backend == "quantinuum_local":
        from norma_qaoa.backends.quantinuum_local import QuantinuumLocalBackend

        return QuantinuumLocalBackend(optimisation_level=config.tket_optimisation_level)
    raise ConfigError(f"unknown backend {config.backend!r}; choose from {BACKEND_NAMES}")
