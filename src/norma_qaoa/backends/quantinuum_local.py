"""Quantinuum H2-1LE local emulator (pytket-quantinuum[pecos]). Local, noiseless, no network.

The backend is constructed with explicit QuantinuumBackendData(local_emulator=True), so
pytket-quantinuum makes no online queries. Remote submission (qnexus) is not used here.
Circuits are built natively in pytket from the same QaoaSpec as the Qiskit circuit; the
Quantinuum compiler requires numeric angles, so each evaluation is compiled separately.

pytket angles are in half-turns: Rz(a) = exp(-i*pi*a*Z/2), so a = theta/pi.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import numpy as np

from norma_qaoa.circuits import QaoaSpec
from norma_qaoa.errors import BackendUnavailableError

DEVICE = "H2-1LE"


def tket_readout_to_qiskit_bitstring(readout: Sequence[int]) -> str:
    """pytket readout tuple (c[0], c[1], ...) -> Qiskit little-endian bitstring."""
    return "".join(str(int(b)) for b in reversed(readout))


class QuantinuumLocalBackend:
    name = "quantinuum_H2-1LE"
    kind = "local_simulator"
    device_name = DEVICE

    def __init__(self, optimisation_level: int = 2) -> None:
        try:
            from pytket.circuit import Bit, Circuit, OpType
            from pytket.extensions.quantinuum import QuantinuumBackend
            from pytket.extensions.quantinuum.backends.data import H2
        except (ImportError, OSError) as exc:
            raise BackendUnavailableError(
                f"Quantinuum local emulator unavailable ({type(exc).__name__}: {exc}). "
                "Install the 'quantinuum' extra: pip install -e .[quantinuum]"
            ) from exc
        self._Circuit, self._Bit = Circuit, Bit
        # The H2 data constant lists only unitary gates; Measure/Reset (in the dataclass
        # default gate set) are added so measured circuits pass the gate-set predicate.
        data = dataclasses.replace(H2, local_emulator=True, gate_set=H2.gate_set | {OpType.Measure, OpType.Reset})
        self._backend = QuantinuumBackend(device_name=DEVICE, data=data)
        if not self._backend.is_local_emulator:
            raise BackendUnavailableError("QuantinuumBackend is not configured as a local emulator")
        self._opt = optimisation_level
        self._spec: QaoaSpec | None = None

    def prepare(self, spec: QaoaSpec, seed_transpiler: int) -> dict[str, Any]:
        self._spec = spec
        return {
            "backend_circuit_hash": None,
            "compile": {
                "optimisation_level": self._opt,
                "note": "compiled per evaluation (numeric angles required by the Quantinuum compiler)",
            },
            "seed_transpiler_unused": seed_transpiler,
        }

    def _build(self, params: Sequence[float]):
        spec = self._spec
        gammas, betas = spec.split(params)
        c = self._Circuit(spec.n, spec.n)
        for q in range(spec.n):
            c.H(q)
        for g, b in zip(gammas, betas):
            for i, h in spec.z_terms:
                c.Rz(2 * h * g / np.pi, i)
            for i, j, J in spec.zz_terms:
                c.ZZPhase(2 * J * g / np.pi, i, j)
            for q in range(spec.n):
                c.Rx(2 * b / np.pi, q)
        for q in range(spec.n):
            c.Measure(q, q)
        return c

    def run(self, parameter_sets: Sequence[Sequence[float]], shots: int, seed: int) -> list[dict[str, int]]:
        if self._spec is None:
            raise RuntimeError("prepare() must be called before run()")
        circuits = [self._backend.get_compiled_circuit(self._build(ps), optimisation_level=self._opt) for ps in parameter_sets]
        handles = self._backend.process_circuits(circuits, n_shots=shots, seed=int(seed), noisy_simulation=False)
        cbits = [self._Bit(i) for i in range(self._spec.n)]
        out = []
        for h in handles:
            counts = self._backend.get_result(h).get_counts(cbits=cbits)
            out.append({tket_readout_to_qiskit_bitstring(k): int(v) for k, v in counts.items()})
        return out

    def info(self) -> dict[str, Any]:
        versions = {}
        for pkg in ("pytket", "pytket-quantinuum", "pytket-pecos", "quantum-pecos"):
            try:
                versions[pkg] = version(pkg)
            except PackageNotFoundError:
                versions[pkg] = None
        return {
            "name": self.name,
            "kind": self.kind,
            "device_name": self.device_name,
            "noisy_simulation": False,
            "optimisation_level": self._opt,
            "versions": versions,
        }
