"""Backend contract.

Bit-order contract: `run()` returns, per parameter set, a dict mapping a bitstring in the
Qiskit convention (little-endian: qubit 0 is the rightmost character) to a shot count.
Adapters for SDKs with other conventions (e.g. pytket readout tuples) convert to this
form themselves; the asset-order conversion then happens only in
`norma_qaoa.ising.bitstring_to_bit_vector`. Every adapter must pass
tests/test_backend_conformance.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, Protocol, runtime_checkable

from norma_qaoa.circuits import QaoaSpec

BackendKind = Literal["local_simulator", "cloud_emulator", "hardware_qpu"]
KNOWN_KINDS: tuple[str, ...] = ("local_simulator", "cloud_emulator", "hardware_qpu")


@runtime_checkable
class SamplingBackend(Protocol):
    name: str  # reported as execution.backend_name
    kind: BackendKind
    device_name: str

    def prepare(self, spec: QaoaSpec, seed_transpiler: int) -> dict[str, Any]:
        """Build/compile the parameterized circuit once. Returns manifest details."""
        ...

    def run(self, parameter_sets: Sequence[Sequence[float]], shots: int, seed: int) -> list[dict[str, int]]:
        """Sample each parameter set (gamma_1..gamma_p, beta_1..beta_p). One circuit per set."""
        ...

    def info(self) -> dict[str, Any]:
        """Library versions, device and options for the manifest."""
        ...
