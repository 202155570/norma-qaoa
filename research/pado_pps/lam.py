"""Choose lambda so that p=1 QAOA (optimal angles) selects k = 6 ETFs on average, then optimise
p = 2 at that lambda. All expectations exact (light cone). Adds to problem_<N>.json:
  lambda, h (= h0 - lambda/2), angles {1, 2}, E {1, 2}, weight {1, 2}.
The start state |+>^n has <C> = 0 (no constant in C), so the QAOA gain is -E.

argv: <N,...>
"""

import json
import math
import os
import sys
import time

import numpy as np
from scipy.optimize import brentq, minimize

from lc import LightCone

HERE = os.path.dirname(os.path.abspath(__file__))


def interp(x):
    p = len(x) // 2
    out = []
    for v in (x[:p], x[p:]):
        v = np.concatenate([[0.0], v, [0.0]])
        out.append([(i / p) * v[i] + ((p - i) / p) * v[i + 1] for i in range(p + 1)])
    return np.concatenate(out)


def opt_p1(pb, lam):
    h = np.array(pb["h0"]) - lam / 2
    m = LightCone(len(h), h, pb["J"], 1)
    grid = [np.array([g, b]) for g in np.linspace(-2.0, 2.0, 21) for b in np.linspace(-0.75, 0.75, 13)]
    vals = [m.energy(x) for x in grid]
    starts = [grid[a] for a in np.argsort(vals)[:3]]
    r = min((minimize(m.energy, s, method="L-BFGS-B") for s in starts), key=lambda r: r.fun)
    return r.x, r.fun, m.weight(r.x)


if __name__ == "__main__":
    for n in [int(v) for v in sys.argv[1].split(",")]:
        path = os.path.join(HERE, f"problem_{n}.json")
        pb = json.load(open(path)); k = pb["k"]
        t0 = time.time()
        f = lambda lam: opt_p1(pb, lam)[2] - k
        lo, hi = 0.0, 0.5
        while f(hi) > 0:
            lo, hi = hi, hi * 2
        lam = brentq(f, lo, hi, xtol=1e-4)
        x1, e1, w1 = opt_p1(pb, lam)
        h = np.array(pb["h0"]) - lam / 2
        m2 = LightCone(n, h, pb["J"], 2)
        r = minimize(m2.energy, interp(x1), method="L-BFGS-B")
        x2, e2, w2 = r.x, r.fun, m2.weight(r.x)
        pb.update({"lambda": lam, "h": h.tolist(), "angles": {"1": x1.tolist(), "2": x2.tolist()},
                   "E": {"1": e1, "2": e2}, "weight": {"1": w1, "2": w2}, "max_ball_p2": m2.max_ball})
        json.dump(pb, open(path, "w"))
        print(f"N={n}: lambda {lam:.4f}  p=1 E {e1:+.4f} (weight {w1:.3f}) x {np.round(x1, 4).tolist()}"
              f"  p=2 E {e2:+.4f} (weight {w2:.3f})  ball {m2.max_ball}  [{time.time()-t0:.0f}s]", flush=True)
