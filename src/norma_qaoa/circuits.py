"""Backend-neutral QAOA circuit description and its Qiskit rendering.

Circuit (depth p): H on every qubit, then per layer l
  cost  : RZ(2*gamma_l*h_i) on i, RZZ(2*gamma_l*J_ij) on (i, j)    [= exp(-i gamma_l H_norm)]
  mixer : RX(2*beta_l) on every qubit                               [= exp(-i beta_l sum X)]
and a final measurement of qubit i into classical bit i.
H_norm is the Ising Hamiltonian divided by scale_factor.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from qiskit import QuantumCircuit, qasm3
from qiskit.circuit import ParameterVector

from norma_qaoa.ising import IsingModel


@dataclass(frozen=True)
class QaoaSpec:
    n: int
    depth: int
    z_terms: tuple[tuple[int, float], ...]  # normalized
    zz_terms: tuple[tuple[int, int, float], ...]  # normalized

    @classmethod
    def from_ising(cls, model: IsingModel, depth: int) -> "QaoaSpec":
        z, zz = model.normalized_terms()
        return cls(n=model.n, depth=depth, z_terms=z, zz_terms=zz)

    def split(self, params: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
        """Engine parameter vector layout: (gamma_1..gamma_p, beta_1..beta_p)."""
        params = np.asarray(params, dtype=float)
        if params.shape != (2 * self.depth,):
            raise ValueError(f"expected {2 * self.depth} parameters, got {params.shape}")
        return params[: self.depth], params[self.depth :]


class QiskitQaoaCircuit:
    def __init__(self, spec: QaoaSpec):
        self.spec = spec
        self.gammas = ParameterVector("gamma", spec.depth)
        self.betas = ParameterVector("beta", spec.depth)
        qc = QuantumCircuit(spec.n)
        qc.h(range(spec.n))
        for layer in range(spec.depth):
            g, b = self.gammas[layer], self.betas[layer]
            for i, h in spec.z_terms:
                qc.rz(2 * h * g, i)
            for i, j, J in spec.zz_terms:
                qc.rzz(2 * J * g, i, j)
            qc.rx(2 * b, range(spec.n))
        qc.measure_all()
        self.circuit = qc

    def values_for(self, circuit: QuantumCircuit, params: Sequence[float]) -> list[float]:
        """Parameter values in `circuit.parameters` order (works for transpiled copies too)."""
        gammas, betas = self.spec.split(params)
        lookup = {self.gammas[i].name: gammas[i] for i in range(self.spec.depth)}
        lookup |= {self.betas[i].name: betas[i] for i in range(self.spec.depth)}
        return [float(lookup[p.name]) for p in circuit.parameters]

    def qasm(self) -> str:
        return qasm3.dumps(self.circuit)
