"""Prepare the IBM hardware run (README 8): circuits' problems, PPS-trained angles, exact predictions.

Runs in .venv (needs ppsl, lc, torch). Writes ibm/spec.json, read by ibm_run.py (.venv-ibm, qiskit).

Circuits (d=3, angles trained on padopauli at w=5):
  N=20 instance 0, p=1..3   exact reference: full state vector
  N=50,             p=1..2  exact reference: light cone
  N=100,            p=1     exact reference: light cone
Each entry also carries the ORIGINAL MaiQ objective (lin, Q, k=6) for the repair/scoring step
of experiment A. For N=50/100 it is problem_<N>.json; for N=20 it is rebuilt from the same
formula as ppsl.make_problem and checked against problem_50.json.

argv: (none)
"""

import json
import os

import numpy as np
from scipy.stats import rankdata

import large
import ppsl
import small
from lc import LightCone

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = [("N20_d3_i0", 20, (1, 2, 3)), ("N50_d3", 50, (1, 2)), ("N100_d3", 100, (1,))]


def original(P):
    """ORIGINAL MaiQ objective G(T) = sum lin_T + sum_{pairs in T} Q (as in ppsl.make_problem)."""
    n = P.shape[1]
    ret = [P[-1] / P[-1 - d_] - 1.0 for d_ in (63, 126, 252)]
    S = (rankdata(sum(ret) / 3.0, method="average") - 1.0) / (n - 1)
    rho = np.corrcoef(np.diff(np.log(P[-127:]), axis=0).T)
    Q = ppsl.WC * np.maximum(rho, 0.0) + ppsl.WCAP * (rho > ppsl.RHO_CAP)
    np.fill_diagonal(Q, 0.0)
    return -ppsl.WS * S, Q, S


if __name__ == "__main__":
    # the rebuilt original objective must match the stored one
    p50 = json.load(open(os.path.join(HERE, "problem_50.json")))
    lin, Q, _ = original(large.P_ALL[:, [large.ALL.index(s) for s in p50["syms"]]])
    assert np.abs(lin - np.array(p50["lin"])).max() < 1e-12 and np.abs(Q - np.array(p50["Q"])).max() < 1e-12

    rows = [json.loads(l) for l in open(os.path.join(HERE, "small.jsonl"))]
    lrows = [json.loads(l) for l in open(os.path.join(HERE, "large.jsonl"))]
    spec = []
    for key, n, ps in PLAN:
        if n == 20:
            pb = small.instance(0, 3)
            idx = [list(small.PX["syms"]).index(s) for s in pb["syms"]]
            lin, Q, S = original(small.P_ALL[:, idx])
            ang = {r["p"]: r["angles_pps"] for r in rows if (r["d"], r["w"], r["inst"]) == (3, 5, 0)}
            ex = ppsl.ExactSV(n, pb["h"], pb["J"])
            pred = lambda p, x: ex.energy(x)
            src = "state vector"
        else:
            pb = json.load(open(os.path.join(HERE, f"problem_{n}.json")))
            lin, Q, S = np.array(pb["lin"]), np.array(pb["Q"]), np.array(pb["score"])
            ang = {r["p"]: r["angles"] for r in lrows if (r["N"], r["d"], r["w_train"]) == (n, 3, 5) and "angles" in r}
            pred = lambda p, x: LightCone(n, np.array(pb["h"]), pb["J"], p).energy(np.array(x))
            src = "light cone"
        for p in ps:
            x = list(map(float, ang[p]))
            spec.append({"key": f"{key}_p{p}", "n": n, "p": p, "syms": list(pb["syms"]), "k": 6,
                         "h": list(map(float, pb["h"])), "J": [[int(i), int(j), float(v)] for i, j, v in pb["J"]],
                         "angles": x, "E_exact": float(pred(p, x)), "E_exact_source": src,
                         "lin": lin.tolist(), "Q": Q.tolist(), "score": list(map(float, S))})
            print(spec[-1]["key"], "E_exact", round(spec[-1]["E_exact"], 4), flush=True)
    os.makedirs(os.path.join(HERE, "ibm"), exist_ok=True)
    json.dump(spec, open(os.path.join(HERE, "ibm", "spec.json"), "w"))
