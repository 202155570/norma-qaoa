"""Collect c1.jsonl and rank_<N>.json into c1_table.json and c2_table.json (criteria v1)."""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
rows = {}
for line in open(os.path.join(HERE, "c1.jsonl")):
    r = json.loads(line)
    rows[(r["N"], r["p"], r["w"])] = r                        # last measurement per config wins
c1 = sorted(rows.values(), key=lambda r: (r["N"], r["p"], r["w"]))
for r in c1:
    r["within_limits"] = r["compile_s"] <= 2400 and (r["peak_rss_gb"] or 0) <= 8.0
    r["meets_10pct"] = r["error_frac"] <= 0.10 and r["within_limits"]
cells = {}
for r in c1:
    cells.setdefault((r["N"], r["p"]), []).append(r["meets_10pct"])
c1_pass = all(any(v) for v in cells.values()) and len(cells) == 6
json.dump({"criterion": "|PPS - exact| <= 10% of gain at some w in {4,5,6}, compile <= 40 min, RSS <= 8 GB",
           "rows": c1, "cells_pass": {f"{n},{p}": any(v) for (n, p), v in cells.items()}, "pass": c1_pass},
          open(os.path.join(HERE, "c1_table.json"), "w"), indent=1)
c2 = []
for n in (50, 100, 150):
    r = json.load(open(os.path.join(HERE, f"rank_{n}.json")))
    r["pass"] = r["percentile"] <= 0.01
    c2.append(r)
json.dump({"criterion": "variant k=6 optimum within the original objective's top 1%", "rows": c2,
           "pass": all(r["pass"] for r in c2)}, open(os.path.join(HERE, "c2_table.json"), "w"), indent=1)
print("C1", c1_pass, {f"{n},{p}": any(v) for (n, p), v in cells.items()})
print("C2", [(r["N"], r["percentile"], r["pass"]) for r in c2])
