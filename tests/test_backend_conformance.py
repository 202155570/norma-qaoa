"""Every backend must return Qiskit-convention bitstrings (see backends/base.py).

Deterministic circuit from the QAOA path itself: with only Z terms h_i = +/-1,
gamma = pi/4 and beta = -pi/4, the state after H, RZ(pi/2*h_i), RX(-pi/2) is |1> for
h_i = +1 and |0> for h_i = -1 on each qubit. So the measured bit vector must equal
[h_i == +1]. A reversed bit order fails this test.
"""

import math

import numpy as np
import pytest

from norma_qaoa.backends.registry import create_backend
from norma_qaoa.circuits import QaoaSpec
from norma_qaoa.config import EngineConfig
from norma_qaoa.errors import BackendUnavailableError
from norma_qaoa.ising import bitstring_to_bit_vector

BACKENDS = ["aer", "quantinuum_local"]


def make_backend(name):
    try:
        return create_backend(EngineConfig(backend=name))
    except BackendUnavailableError as exc:
        pytest.skip(f"{name} unavailable on this machine: {exc}")


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("ones", [(0,), (1,), (0, 2), (5,), (0, 1, 2, 3, 4, 5), ()])
def test_bit_order(name, ones):
    n = 6
    spec = QaoaSpec(n=n, depth=1, z_terms=tuple((i, 1.0 if i in ones else -1.0) for i in range(n)), zz_terms=())
    backend = make_backend(name)
    backend.prepare(spec, seed_transpiler=1)
    (counts,) = backend.run([(math.pi / 4, -math.pi / 4)], shots=64, seed=3)
    assert sum(counts.values()) == 64
    assert len(counts) == 1, counts
    (bitstring,) = counts
    assert bitstring_to_bit_vector(bitstring, n) == [1 if i in ones else 0 for i in range(n)]


@pytest.mark.parametrize("name", BACKENDS)
def test_batch_and_seed(name):
    spec = QaoaSpec(n=3, depth=1, z_terms=((0, 0.3), (2, -0.7)), zz_terms=((0, 1, 0.5),))
    backend = make_backend(name)
    backend.prepare(spec, seed_transpiler=1)
    a = backend.run([(0.4, 0.3), (1.0, 0.2)], shots=200, seed=9)
    b = backend.run([(0.4, 0.3), (1.0, 0.2)], shots=200, seed=9)
    assert len(a) == 2 and all(sum(c.values()) == 200 for c in a)
    assert a == b


def test_cross_backend_distribution():
    """Same parameters on two backends: bit distributions agree within sampling noise."""
    backends = []
    for name in BACKENDS:
        try:
            backends.append(create_backend(EngineConfig(backend=name)))
        except BackendUnavailableError as exc:
            pytest.skip(f"needs every backend; {name} unavailable: {exc}")
    spec = QaoaSpec(n=4, depth=1, z_terms=((0, 0.5), (1, -0.2), (3, 0.9)), zz_terms=((0, 1, 0.4), (2, 3, -0.6)))
    shots = 4000
    dists = []
    for be in backends:
        be.prepare(spec, seed_transpiler=1)
        (counts,) = be.run([(0.7, 0.4)], shots=shots, seed=5)
        v = np.zeros(16)
        for k, c in counts.items():
            v[int(k, 2)] = c / shots
        dists.append(v)
    tvd = 0.5 * np.abs(dists[0] - dists[1]).sum()
    assert tvd < 0.06, tvd
