"""PADO Pauli-propagation surrogate for the variant QAOA, one configuration per call.

Circuit: H on every qubit (|+>^n), then p times  RZ(2 g h_i), RZZ(2 g J_ij), RX(2 b),
i.e. exp(-i g C) exp(-i b sum X) as in lc.py. Observable C = sum h Z + sum J ZZ.
Exact <C> comes from the light cone at the same angles (optimised exactly in lam.py).

argv: selftest                     12-qubit piece, w = 12 (no truncation) vs light cone
      run <N> <p> <w> <out.jsonl>  one row: exact, PPS, error / gain, compile s, peak RSS
"""

import json
import os
import sys
import time
from collections import deque

import numpy as np
import torch
from padopauli import Circuit

from ppsl import PADO_PRESET

from lc import LightCone

HERE = os.path.dirname(os.path.abspath(__file__))


def peak_rss_gb():
    try:
        import psutil
        mi = psutil.Process().memory_info()
        return round(getattr(mi, "peak_wset", mi.rss) / 2 ** 30, 2)
    except Exception:
        return None


def build(n, h, edges, p, w):
    qc = Circuit(n_qubits=n)
    meta = []                                       # (layer, kind 0=gamma 1=beta, coefficient)
    for i in range(n):
        qc.h(i)
    for l in range(p):
        for i in range(n):
            qc.rz(i, param_idx=len(meta)); meta.append((l, 0, 2.0 * h[i]))
        for i, j, v in edges:
            qc.rzz(i, j, param_idx=len(meta)); meta.append((l, 0, 2.0 * v))
        for i in range(n):
            qc.rx(i, param_idx=len(meta)); meta.append((l, 1, 2.0))
    obs = [("Z", [i], float(h[i])) for i in range(n)] + [("ZZ", [i, j], float(v)) for i, j, v in edges]
    t0 = time.time()
    qc.compile(observables=[obs], preset=PADO_PRESET, dtype="float64", max_weight=w, verbosity=0)
    lay = np.array([m[0] for m in meta]); kind = np.array([m[1] for m in meta])
    coef = np.array([m[2] for m in meta])

    def ev(x):
        x = np.asarray(x, float)
        th = coef * np.where(kind == 0, x[lay], x[p + lay])
        return float(torch.as_tensor(qc.expvals(torch.tensor(th, dtype=torch.float64))[0]).detach())
    return ev, time.time() - t0


if __name__ == "__main__":
    if sys.argv[1] == "selftest":
        pb = json.load(open(os.path.join(HERE, "problem_50.json")))
        adj = {}
        for i, j, _ in pb["J"]:
            adj.setdefault(i, []).append(j); adj.setdefault(j, []).append(i)
        seen, dq = [0], deque([0])
        while dq and len(seen) < 12:
            for v in adj.get(dq.popleft(), []):
                if v not in seen and len(seen) < 12:
                    seen.append(v); dq.append(v)
        loc = {q: a for a, q in enumerate(seen)}
        h = np.array(pb["h"])[seen]
        edges = [(loc[i], loc[j], v) for i, j, v in pb["J"] if i in loc and j in loc]
        rng = np.random.default_rng(3)
        for p in (1, 2):
            ev, _ = build(12, h, edges, p, 12)
            m = LightCone(12, h, edges, p)
            for _ in range(2):
                x = np.concatenate([rng.uniform(-1, 1, p), rng.uniform(-1, 1, p)])
                a, b = ev(x), m.energy(x)
                print(f"p={p}: PPS {a:+.12f}  exact {b:+.12f}  |d| {abs(a-b):.1e}")
                assert abs(a - b) < 1e-9
        print("selftest PASS")
    elif sys.argv[1] == "run":
        n, p, w, out = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
        pb = json.load(open(os.path.join(HERE, f"problem_{n}.json")))
        x = np.array(pb["angles"][str(p)])
        exact = pb["E"][str(p)]
        ev, tc = build(n, np.array(pb["h"]), pb["J"], p, w)
        t0 = time.time(); v = ev(x); te = time.time() - t0
        # context, not a criterion: the coupling part of the exact energy at these angles
        m = LightCone(n, np.array(pb["h"]), pb["J"], p)
        e_terms = m.expvals(x)
        zz_part = float(e_terms[n:] @ np.array([v_ for *_, v_ in pb["J"]]))
        gain = -exact                                   # start state |+>^n has <C> = 0
        row = {"N": n, "p": p, "w": w, "exact": exact, "pps": v, "error": v - exact,
               "gain": gain, "error_frac": abs(v - exact) / gain, "zz_part": zz_part,
               "error_frac_of_zz": abs(v - exact) / abs(zz_part) if zz_part else None,
               "compile_s": tc, "eval_s": te, "peak_rss_gb": peak_rss_gb(),
               "padopauli": __import__("padopauli").__version__}
        open(out, "a").write(json.dumps(row) + "\n")
        print(json.dumps(row), flush=True)
