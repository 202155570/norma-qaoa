"""Single gate for hardware and external-transfer policy.

- hardware_qpu   : always refused (spec p.9 allow_qpu=false; p.3 changes need approval by both parties)
- cloud_emulator : refused unless config.allow_external_transfer (spec 16, prior approval for transfer)
"""

from __future__ import annotations

from norma_qaoa.backends.base import KNOWN_KINDS, SamplingBackend
from norma_qaoa.config import EngineConfig
from norma_qaoa.errors import BackendNotAllowedError
from norma_qaoa.schema import Request


def assert_backend_allowed(backend: SamplingBackend, request: Request, config: EngineConfig) -> None:
    kind = getattr(backend, "kind", None)
    if kind not in KNOWN_KINDS:
        raise BackendNotAllowedError(f"backend {backend!r} has unknown kind {kind!r}")
    if request.execution.allow_qpu:
        raise BackendNotAllowedError("execution.allow_qpu=true is not allowed")
    if kind == "hardware_qpu":
        raise BackendNotAllowedError(
            f"backend {backend.name!r} is real QPU hardware; QPU execution is not approved (allow_qpu=false)"
        )
    if kind == "cloud_emulator" and not config.allow_external_transfer:
        raise BackendNotAllowedError(
            f"backend {backend.name!r} sends data to an external service; allow_external_transfer is off"
        )
