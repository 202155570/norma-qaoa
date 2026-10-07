"""Qiskit Aer (CPU) via SamplerV2."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from importlib.metadata import version
from typing import Any

from qiskit import qasm3, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.primitives import SamplerV2

from norma_qaoa.circuits import QaoaSpec, QiskitQaoaCircuit

_BACKEND_OPTIONS = {"device": "CPU", "method": "automatic"}


class AerBackend:
    name = "aer_simulator"
    kind = "local_simulator"
    device_name = "AerSimulator(CPU)"

    def __init__(self) -> None:
        self._sim = AerSimulator(**_BACKEND_OPTIONS)
        self._qaoa: QiskitQaoaCircuit | None = None
        self._tqc = None

    def prepare(self, spec: QaoaSpec, seed_transpiler: int) -> dict[str, Any]:
        self._qaoa = QiskitQaoaCircuit(spec)
        self._tqc = transpile(self._qaoa.circuit, backend=self._sim, seed_transpiler=seed_transpiler, optimization_level=1)
        text = qasm3.dumps(self._tqc)
        return {
            "backend_circuit_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "transpile": {"optimization_level": 1, "seed_transpiler": seed_transpiler},
            "transpiled_depth": self._tqc.depth(),
            "transpiled_ops": {k: int(v) for k, v in self._tqc.count_ops().items()},
        }

    def run(self, parameter_sets: Sequence[Sequence[float]], shots: int, seed: int) -> list[dict[str, int]]:
        if self._tqc is None:
            raise RuntimeError("prepare() must be called before run()")
        sampler = SamplerV2(seed=seed, options={"backend_options": dict(_BACKEND_OPTIONS)})
        pubs = [(self._tqc, self._qaoa.values_for(self._tqc, ps)) for ps in parameter_sets]
        result = sampler.run(pubs, shots=shots).result()
        return [{k: int(v) for k, v in r.join_data().get_counts().items()} for r in result]

    def info(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "device_name": self.device_name,
            "backend_options": dict(_BACKEND_OPTIONS),
            "versions": {"qiskit": version("qiskit"), "qiskit-aer": version("qiskit-aer")},
        }
