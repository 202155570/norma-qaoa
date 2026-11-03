"""Oracle for the PADO-friendly study units. Exit 0 iff the unit's artifacts meet the plan.

argv: U1 | U2 | U3
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
J = lambda f: json.load(open(os.path.join(HERE, f), encoding="utf-8"))
fails = []


def need(cond, msg):
    if not cond:
        fails.append(msg)


unit = sys.argv[1]
if unit in ("U1", "U2", "U3"):
    t = J("tickers.json"); px = J("prices.json")
    base = [s for g in t["groups"].values() for s in g]
    need(len(px["syms"]) == 150 and len(set(px["syms"])) == 150, "150 unique tickers")
    need(px["syms"][:50] == base, "existing 50 first")
    need(len(px["dates"]) >= 500, "common days >= 500")
    need(len(px.get("sha256", "")) == 64, "data hash recorded")
    for n in (50, 100, 150):
        pb = J(f"problem_{n}.json")
        need(len(pb["syms"]) == n, f"N={n} size")
        need(all(k in pb for k in ("lin", "Q", "h", "J", "lambda", "angles")), f"N={n} orig+variant fields")
        need(pb["max_degree"] <= 3, f"N={n} max degree <= 3")
        need(pb["data_sha256"] == px["sha256"], f"N={n} built from current prices")
if unit in ("U2", "U3"):
    c = J("lc_check.json")
    need(c["pass"] and c["max_abs_diff"] < 1e-9 and {r["p"] for r in c["rows"]} == {1, 2}, "light cone vs full")
    r = J("rank_50.json")
    need(r.get("method") == "exhaustive" and r.get("count") == 15890700, "N=50 exhaustive rank")
    k = J("kill.json")
    need(k.get("N") == 50 and k.get("p") == 1 and set(k.get("errors", {})) >= {"4", "5", "6"} and "pass" in k,
         "kill-question result with w=4,5,6")
if unit == "U3":
    c1 = J("c1_table.json")
    cells = {(row["N"], row["p"]) for row in c1["rows"]}
    if J("kill.json")["pass"]:
        need(cells >= {(n, p) for n in (50, 100, 150) for p in (1, 2)}, "C1 table covers N x p")
        need(all(("error_frac" in row) or row.get("infeasible") for row in c1["rows"]), "C1 cells measured or infeasible")
    c2 = J("c2_table.json")
    need({row["N"] for row in c2["rows"]} == {50, 100, 150}, "C2 table covers N")
    v = open(os.path.join(HERE, "verdict.md"), encoding="utf-8").read()
    need(any(line.startswith("Verdict:") for line in v.splitlines()), "verdict line")
print("PASS" if not fails else "FAIL: " + "; ".join(fails))
sys.exit(1 if fails else 0)
