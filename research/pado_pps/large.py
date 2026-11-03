"""Large-N map: train on the PADO surrogate at w_train, check at w_train+1 (w-convergence) and,
where the light cone fits (largest ball <= 20 qubits), against the exact energy and the
exact-trained chain.

Universes as in build.py (N=50 original 50; N=100 + every other added; N=150 all).
One (N, d) per call so a stop line can cut a single configuration.

argv: <N> <d> <pmax> <w_train> <out.jsonl>
"""

import json
import os
import sys
import time

import numpy as np

import ppsl
from lc import LightCone

HERE = os.path.dirname(os.path.abspath(__file__))
PX = json.load(open(os.path.join(HERE, "prices.json")))
ALL = PX["syms"]; P_ALL = np.array(PX["prices"]).T
base = PX["base50"]; added = [s for s in ALL if s not in base]
UNIV = {50: base, 100: base + added[0::2], 150: ALL}


def peak_rss_gb():
    try:
        import psutil
        mi = psutil.Process().memory_info()
        return round(getattr(mi, "peak_wset", mi.rss) / 2 ** 30, 2)
    except Exception:
        return None


def max_ball(n, J, p):
    """largest reverse-light-cone ball over all terms, without building any state"""
    adj = [[] for _ in range(n)]
    for i, j, _ in J:
        adj[i].append(j); adj[j].append(i)
    best = 0
    for sup in [(i,) for i in range(n)] + [(i, j) for i, j, _ in J]:
        seen = set(sup); front = set(sup)
        for _ in range(p):
            front = {v for u in front for v in adj[u]} - seen
            seen |= front
        best = max(best, len(seen))
    return best


class _LC:
    def __init__(self, m):
        self.m = m

    def energy(self, x):
        return self.m.energy(x)

    def fg(self, x):
        e = self.m.energy(x)
        g = np.array([(self.m.energy(x + 1e-6 * np.eye(len(x))[k]) - self.m.energy(x - 1e-6 * np.eye(len(x))[k])) / 2e-6
                      for k in range(len(x))])
        return e, g


if __name__ == "__main__":
    n, d, pmax, wt, out = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    syms = UNIV[n]
    pb = ppsl.tune_lambda(ppsl.make_problem(P_ALL[:, [ALL.index(s) for s in syms]], syms, d))
    h, J = pb["h"], pb["J"]
    lc_ok = {p: LightCone(n, h, J, p) for p in (1, 2) if max_ball(n, J, p) <= 20}
    ex_chain = ppsl.chain(lambda p: _LC(lc_ok[p]), max(lc_ok)) if lc_ok else {}
    info = {}
    pps = ppsl.chain(lambda p: ppsl.PPS(n, h, J, p, wt), pmax, log=lambda p, f, t, c: info.__setitem__(p, (f, t, c)))
    E1 = None
    for p, x in pps.items():
        t0 = time.time()
        chk = ppsl.PPS(n, h, J, p, wt + 1)
        e_chk = chk.energy(x)
        row = {"N": n, "d": d, "max_degree": pb["max_degree"], "lambda": pb["lambda"], "edges": len(J), "p": p,
               "w_train": wt, "E_pps_train": info[p][0], "E_pps_check": e_chk, "w_check": wt + 1,
               "compile_train_s": info[p][2], "train_s": info[p][1], "compile_check_s": chk.compile_s,
               "angles": x, "peak_rss_gb": peak_rss_gb()}
        if p in lc_ok:
            row["E_exact_of_pps_angles"] = lc_ok[p].energy(np.array(x))
            row["E_exact_trained"] = lc_ok[p].energy(np.array(ex_chain[p]))
            row["max_ball"] = lc_ok[p].max_ball
        if p == 1:
            E1 = row.get("E_exact_of_pps_angles", e_chk)
        row["E1_ref"] = E1
        extra = E1 - e_chk
        row["w_gap_over_extra_gain"] = abs(e_chk - info[p][0]) / extra if p > 1 and extra > 1e-9 else None
        open(out, "a").write(json.dumps(row) + "\n")
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items() if k != "angles"}),
              flush=True)

