"""QUBO -> Ising (x_i = (1 - Z_i)/2) and the single bit-order conversion point.

Bit order: asset i <-> qubit i. Qiskit Pauli labels and measured bitstrings are
little-endian (qubit 0 is the rightmost character). `bitstring_to_bit_vector` is the
only place where a measured bitstring is turned into an asset-ordered bit vector.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from qiskit.quantum_info import SparsePauliOp

from norma_qaoa.qubo import Qubo


@dataclass(frozen=True)
class IsingModel:
    n: int
    z_terms: tuple[tuple[int, float], ...]  # (i, h_i)        for h_i Z_i
    zz_terms: tuple[tuple[int, int, float], ...]  # (i, j, J_ij) for J_ij Z_i Z_j, i < j
    offset: float
    scale_factor: float  # max |coef| over Z/ZZ terms; the circuit uses coef / scale_factor

    def operator(self, normalized: bool = False) -> SparsePauliOp:
        s = self.scale_factor if normalized else 1.0
        terms = [("Z", [i], h / s) for i, h in self.z_terms]
        terms += [("ZZ", [i, j], J / s) for i, j, J in self.zz_terms]
        if not terms:
            return SparsePauliOp.from_sparse_list([("", [], 0.0)], num_qubits=self.n)
        return SparsePauliOp.from_sparse_list(terms, num_qubits=self.n)

    def normalized_terms(self) -> tuple[tuple[tuple[int, float], ...], tuple[tuple[int, int, float], ...]]:
        s = self.scale_factor
        return (
            tuple((i, h / s) for i, h in self.z_terms),
            tuple((i, j, J / s) for i, j, J in self.zz_terms),
        )


def qubo_to_ising(qubo: Qubo) -> IsingModel:
    """F(x) = <z|H|z> + offset, with H = sum h_i Z_i + sum J_ij Z_i Z_j."""
    Q = qubo.Q
    n = Q.shape[0]
    h = np.zeros(n)
    J: dict[tuple[int, int], float] = {}
    offset = qubo.const
    for i in range(n):
        # Q_ii x_i = Q_ii/2 (1 - Z_i)
        offset += Q[i, i] / 2
        h[i] -= Q[i, i] / 2
        for j in range(i + 1, n):
            q = Q[i, j]
            if q == 0.0:
                continue
            # Q_ij x_i x_j = Q_ij/4 (1 - Z_i - Z_j + Z_i Z_j)
            offset += q / 4
            h[i] -= q / 4
            h[j] -= q / 4
            J[(i, j)] = J.get((i, j), 0.0) + q / 4
    z_terms = tuple((i, float(h[i])) for i in range(n) if h[i] != 0.0)
    zz_terms = tuple((i, j, float(v)) for (i, j), v in sorted(J.items()) if v != 0.0)
    coefs = [abs(c) for _, c in z_terms] + [abs(c) for *_, c in zz_terms]
    scale = max(coefs) if coefs and max(coefs) > 0 else 1.0
    return IsingModel(n=n, z_terms=z_terms, zz_terms=zz_terms, offset=float(offset), scale_factor=float(scale))


def bitstring_to_bit_vector(bitstring: str, n: int) -> list[int]:
    """Qiskit little-endian bitstring -> bit vector in asset_ids order (x_i = qubit i)."""
    s = bitstring.replace(" ", "")
    if len(s) != n or any(ch not in "01" for ch in s):
        raise ValueError(f"bitstring {bitstring!r} is not a {n}-bit 0/1 string")
    return [int(s[n - 1 - i]) for i in range(n)]


def ising_energy(model: IsingModel, x: list[int]) -> float:
    """<z|H|z> + offset for an asset-ordered bit vector (z_i = 1 - 2 x_i). Used by tests/checks."""
    z = 1 - 2 * np.asarray(x, dtype=float)
    e = sum(h * z[i] for i, h in model.z_terms) + sum(J * z[i] * z[j] for i, j, J in model.zz_terms)
    return float(e) + model.offset
