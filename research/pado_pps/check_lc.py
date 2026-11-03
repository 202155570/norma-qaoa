"""Light-cone simulator vs full 2^20 state vector on a 20-ETF piece of the N=50 variant.

The 20 qubits are a BFS-connected region of the variant graph (so the light cones overlap and
cross the region), with a nonzero lambda; 3 random angle sets at p = 1 and p = 2.
Writes lc_check.json.
"""

import json
import os
from collections import deque

import numpy as np

from lc import LightCone, full_energy

HERE = os.path.dirname(os.path.abspath(__file__))
pb = json.load(open(os.path.join(HERE, "problem_50.json")))
adj = {}
for i, j, _ in pb["J"]:
    adj.setdefault(i, []).append(j); adj.setdefault(j, []).append(i)
seen, dq = [0], deque([0])
while dq and len(seen) < 20:
    u = dq.popleft()
    for v in adj.get(u, []):
        if v not in seen and len(seen) < 20:
            seen.append(v); dq.append(v)
loc = {q: a for a, q in enumerate(seen)}
lam = 0.3
h = np.array(pb["h0"])[seen] - lam / 2
edges = [(loc[i], loc[j], v) for i, j, v in pb["J"] if i in loc and j in loc]
rng = np.random.default_rng(1)
rows = []
for p in (1, 2):
    lcs = LightCone(20, h, edges, p)
    for _ in range(3):
        x = np.concatenate([rng.uniform(-1.5, 1.5, p), rng.uniform(-1, 1, p)])
        ef, wf = full_energy(20, h, edges, x)
        el, wl = lcs.energy(x), lcs.weight(x)
        rows.append({"p": p, "x": x.tolist(), "full_E": ef, "lc_E": el, "dE": abs(ef - el),
                     "full_w": wf, "lc_w": wl, "dw": abs(wf - wl), "max_ball": lcs.max_ball})
        print(f"p={p} E full {ef:+.12f} lc {el:+.12f} |d| {abs(ef-el):.1e}   weight |d| {abs(wf-wl):.1e}  ball {lcs.max_ball}")
out = {"n": 20, "edges": len(edges), "lambda": lam, "rows": rows,
       "max_abs_diff": max(max(r["dE"], r["dw"]) for r in rows)}
out["pass"] = out["max_abs_diff"] < 1e-9
json.dump(out, open(os.path.join(HERE, "lc_check.json"), "w"), indent=1)
print("PASS" if out["pass"] else "FAIL", out["max_abs_diff"])
