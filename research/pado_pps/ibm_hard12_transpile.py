"""Local-only transpile check for running p=1 QAOA on two of the 12 hard problems (N = 100, k = 15) on IBM
hardware. No account access: targets are an offline 10 x 12 square lattice (stand-in for ibm_phoenix, Nighthawk r2,
120 qubits, CZ) and FakeFez (Heron r2, 156 qubits, heavy-hex). Exploratory.

Circuits (angles fixed and nonzero; the gate count does not depend on them):
  std   |+>^n, exp(-i g (C + P (sum x - k)^2)), exp(-i b sum X): the quadratic penalty couples every pair -> K_100
  xy    |1^k 0^(n-k)>, exp(-i g C) on the objective's edges only, ring XY mixer (XX + YY on i, i+1 mod n);
        keeps exactly k (a cheap product start in place of the Dicke state)
Routing: (a) SABRE at optimization level 3; (b) for std only, an explicit line swap network (odd-even
transposition) on a snake path through the lattice, the textbook way to do all pairs on a line.
Reported: CZ count, 2q depth, and a retained-signal estimate exp(-a * CZ) with a = 6.1e-4 fitted on the
2026-11-09 ibm_phoenix N = 20 runs (ibm/result_hard_hw.json; optimistic for 100 qubits).
Runs in .venv-ibm. argv: <out.json> [sabre_seeds]
"""

import json
import math
import os
import sys
import time

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import XXPlusYYGate
from qiskit.transpiler import CouplingMap
from qiskit_ibm_runtime.fake_provider import FakeFez

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hard  # noqa: E402

A_CZ = 6.1e-4
KEYS = [("N100_k15_corr_c_0.3_s16", 100, 15, "corr_c", 0.3, 16.0), ("N100_k15_corr_c_1.0_s16", 100, 15, "corr_c", 1.0, 16.0)]
BASIS = ["cz", "rz", "sx", "x"]


def edges_of(Q):
    n = len(Q)
    return [(i, j) for i in range(n) for j in range(i + 1, n) if Q[i, j] != 0.0]


def std_circuit(n, g=0.4, b=0.3, measure=True):
    qc = QuantumCircuit(n)
    qc.h(range(n))
    for i in range(n):
        for j in range(i + 1, n):
            qc.rzz(g * 0.1, i, j)
    for i in range(n):
        qc.rz(g * 0.2, i)
    qc.rx(2 * b, range(n))
    if measure:
        qc.measure_all()
    return qc


def xy_circuit(n, k, E, g=0.4, b=0.3):
    qc = QuantumCircuit(n)
    qc.x(range(k))
    for i, j in E:
        qc.rzz(g * 0.1, i, j)
    for i in range(n):
        qc.rz(g * 0.2, i)
    for par in (0, 1):
        for i in range(par, n, 2):
            qc.append(XXPlusYYGate(2 * b), [i, (i + 1) % n])
    qc.measure_all()
    return qc


def stats(tq):
    ops = tq.count_ops()
    cz = int(ops.get("cz", 0)) + int(ops.get("cx", 0)) + int(ops.get("ecr", 0))
    d2 = tq.depth(lambda ins: ins.operation.num_qubits == 2)
    return {"cz": cz, "depth_2q": d2, "depth": tq.depth(), "retained_est": math.exp(-A_CZ * cz)}


def snake(rows, cols):
    return [r * cols + (c if r % 2 == 0 else cols - 1 - c) for r in range(rows) for c in range(cols)]


def swap_network(n, cmap, path):
    """All-pairs RZZ via the line swap network (odd-even transposition): n layers on a path of n physical qubits;
    each layer applies RZZ to neighbouring slots whose pair has not met yet, then SWAPs them. Every pair meets once."""
    qc = QuantumCircuit(n)
    qc.h(range(n))
    pos = list(range(n))                     # pos[slot] = logical qubit in that slot
    met = set()
    for layer in range(n):
        for s in range(layer % 2, n - 1, 2):
            a, b_ = pos[s], pos[s + 1]
            pr = (min(a, b_), max(a, b_))
            if pr not in met:
                qc.rzz(0.04, s, s + 1); met.add(pr)
            qc.swap(s, s + 1); pos[s], pos[s + 1] = b_, a
    assert len(met) == n * (n - 1) // 2, len(met)
    for s in range(n):
        qc.rz(0.08, s)
    qc.rx(0.6, range(n))
    qc.measure_all()
    return transpile(qc, coupling_map=cmap, basis_gates=BASIS, initial_layout=path[:n], optimization_level=3,
                     routing_method="none", seed_transpiler=1)


def main(out, seeds):
    grid = CouplingMap.from_grid(10, 12)
    fez = FakeFez()
    res = {"targets": {"grid10x12": "square lattice stand-in for ibm_phoenix (Nighthawk r2, 120q)",
                       "FakeFez": "Heron r2 156q heavy-hex"}, "A_CZ": A_CZ, "runs": []}
    for key, N, k, fam, dens, s in KEYS:
        lin, Q = hard.make(N, k, fam, dens, s)
        E = edges_of(Q)
        circs = {"xy": xy_circuit(N, k, E)}
        if key == KEYS[0][0]:
            circs["std"] = std_circuit(N)                # K_100 regardless of the instance
        for name, qc in circs.items():
            for tname, kw in (("grid10x12", {"coupling_map": grid, "basis_gates": BASIS}), ("FakeFez", {"backend": fez})):
                best = None; t0 = time.time()
                for sd in range(seeds):
                    tq = transpile(qc, optimization_level=3, seed_transpiler=sd, **kw)
                    st = stats(tq)
                    if best is None or st["cz"] < best["cz"]:
                        best = st
                rec = {"key": key, "edges": len(E) if name == "xy" else N * (N - 1) // 2, "circuit": name, "target": tname, "routing": "sabre",
                       "seconds": time.time() - t0, **best}
                res["runs"].append(rec); print(json.dumps(rec), flush=True)
        if key != KEYS[0][0]:
            json.dump(res, open(os.path.join(HERE, out), "w"), indent=1); continue
        t0 = time.time()
        tq = swap_network(N, grid, snake(10, 12))
        rec = {"key": "any N=100", "edges": N * (N - 1) // 2, "circuit": "std", "target": "grid10x12", "routing": "line swap network",
               "seconds": time.time() - t0, **stats(tq)}
        res["runs"].append(rec); print(json.dumps(rec), flush=True)
        json.dump(res, open(os.path.join(HERE, out), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 2)
