"""Small-N map: PPS-trained vs exact-trained angles, scored exactly (full state vector).

Instances: random 20-ETF subsets of the 150 (seeded), variant with degree cap d, lambda tuned.
argv: selftest
      run <d,...> <inst,...> <pmax> <w,...> <out.jsonl>

Resumable: a (d, inst, w) whose pmax row is already in out.jsonl is skipped, and the exact
chain of each (d, inst) is cached in cache/exact_d<d>_i<inst>_p<pmax>.json.
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
P_ALL = np.array(PX["prices"]).T
NS = 20


def instance(seed, d):
    idx = np.sort(np.random.default_rng(1000 + seed).choice(P_ALL.shape[1], NS, replace=False))
    pb = ppsl.make_problem(P_ALL[:, idx], [PX["syms"][i] for i in idx], d)
    return ppsl.tune_lambda(pb)


if __name__ == "__main__":
    if sys.argv[1] == "selftest":
        pb = instance(0, 3)
        ex = ppsl.ExactSV(NS, pb["h"], pb["J"])
        rng = np.random.default_rng(0)
        for p in (1, 2):
            lcm = LightCone(NS, pb["h"], pb["J"], p)
            x = rng.uniform(-1, 1, 2 * p)
            e, g = ex.fg(x)
            fd = np.array([(ex.energy(x + 1e-6 * np.eye(2 * p)[k]) - ex.energy(x - 1e-6 * np.eye(2 * p)[k])) / 2e-6
                           for k in range(2 * p)])
            ps = ppsl.PPS(NS, pb["h"], pb["J"], p, NS)
            print(f"p={p}: sv {e:+.10f} lc {lcm.energy(x):+.10f} pps(w=n) {ps.energy(x):+.10f}  grad err {np.abs(g-fd).max():.1e}")
            assert abs(e - lcm.energy(x)) < 1e-9 and abs(e - ps.energy(x)) < 1e-9 and np.abs(g - fd).max() < 1e-5
        print("selftest PASS"); sys.exit()
    ds = [int(v) for v in sys.argv[2].split(",")]
    insts, pmax = [int(v) for v in sys.argv[3].split(",")], int(sys.argv[4])
    ws = [int(v) for v in sys.argv[5].split(",")]
    out = sys.argv[6]
    done = set()
    if os.path.exists(out):
        for line in open(out):
            r = json.loads(line)
            if r["p"] == pmax:
                done.add((r["d"], r["inst"], r["w"]))
    os.makedirs(os.path.join(HERE, "cache"), exist_ok=True)
    for d in ds:
        for s in insts:
            if all((d, s, w) in done for w in ws):
                continue
            t0 = time.time()
            pb = instance(s, d)
            ex = ppsl.ExactSV(NS, pb["h"], pb["J"])
            cpath = os.path.join(HERE, "cache", f"exact_d{d}_i{s}_p{pmax}.json")
            if os.path.exists(cpath):
                exact = {int(p): x for p, x in json.load(open(cpath)).items()}
            else:
                exact = ppsl.chain(lambda p: ex, pmax)
                json.dump({p: list(map(float, x)) for p, x in exact.items()}, open(cpath, "w"))
            Eex = {p: ex.energy(x) for p, x in exact.items()}
            for w in ws:
                if (d, s, w) in done:
                    continue
                comp = {}
                pps = ppsl.chain(lambda p: ppsl.PPS(NS, pb["h"], pb["J"], p, w), pmax,
                                 log=lambda p, f, t, c: comp.__setitem__(p, (f, t, c)))
                for p, x in pps.items():
                    Ep = ex.energy(x)
                    row = {"N": NS, "d": d, "inst": s, "max_degree": pb["max_degree"], "lambda": pb["lambda"],
                           "w": w, "p": p, "E_exact_trained": Eex[p], "E_pps_trained_scored": Ep,
                           "E_pps_own": comp[p][0], "E1": Eex[1],
                           "capture": (Eex[1] - Ep) / (Eex[1] - Eex[p]) if p > 1 and Eex[1] - Eex[p] > 1e-9 else None,
                           "extra_gain_exact": Eex[1] - Eex[p], "pps_train_s": comp[p][1], "compile_s": comp[p][2],
                           "angles_pps": x, "angles_exact": exact[p]}
                    open(out, "a").write(json.dumps(row) + "\n")
                    cap = row["capture"]
                    print(f"d={d} inst={s} w={w} p={p}: exact {Eex[p]:+.4f}  pps->exact {Ep:+.4f}  pps self {comp[p][0]:+.4f}"
                          f"  capture {'-' if cap is None else f'{cap:.3f}'}  (compile {comp[p][2]:.0f}s, train {comp[p][1]:.0f}s)",
                          flush=True)
            print(f"  instance done {time.time()-t0:.0f}s", flush=True)
