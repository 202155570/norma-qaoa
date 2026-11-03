"""Parse the raw chart responses into one price table for the 150-ETF universe.

Adjusted close per day (UTC date). A ticker qualifies if it has >= 504 trading days (2 years);
a failing ticker of the 100 added ones is replaced by the next qualifying spare. The table
keeps the last 504 days common to all 150, the existing 50 first, in tickers.json order.

argv: <tickers.json> <rawdir> <out.json>      (run with python -I)
"""

import hashlib
import json
import os
import sys
import time

DAYS = 504
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
raw, out = sys.argv[2], sys.argv[3]


def load(s):
    p = os.path.join(raw, s + ".json")
    if not os.path.exists(p):
        return None
    r = json.load(open(p, encoding="utf-8"))["chart"]["result"][0]
    ts = r.get("timestamp") or []
    adj = r["indicators"].get("adjclose", [{}])[0].get("adjclose") or r["indicators"]["quote"][0]["close"]
    d = {time.strftime("%Y-%m-%d", time.gmtime(t)): float(v) for t, v in zip(ts, adj) if v is not None and v > 0}
    return d if len(d) >= DAYS else None


base = [s for g in cfg["groups"].values() for s in g]
series = {s: load(s) for s in base}
bad = [s for s, v in series.items() if v is None]
if bad:
    sys.exit(f"existing tickers without 2y history: {bad}")
spares = iter(cfg["spare"])
added, replaced = [], []
for g in cfg["added"].values():
    for s in g:
        v = load(s)
        while v is None:
            r = next(spares); replaced.append((s, r)); s, v = r, load(r)
        series[s] = v; added.append(s)
syms = base + added
common = sorted(set.intersection(*(set(series[s]) for s in syms)))
if len(common) < DAYS:
    sys.exit(f"only {len(common)} common days")
dates = common[-DAYS:]
prices = [[series[s][d] for d in dates] for s in syms]
blob = json.dumps({"syms": syms, "dates": dates, "prices": prices}, separators=(",", ":"))
json.dump({"syms": syms, "base50": base, "replaced": replaced, "dates": dates, "prices": prices,
           "sha256": hashlib.sha256(blob.encode()).hexdigest(), "common_days_total": len(common)},
          open(out, "w"), separators=(",", ":"))
print(f"{len(syms)}개, 공통 거래일 {len(common)}일 중 최근 {DAYS}일 ({dates[0]} ~ {dates[-1]}), 대체 {replaced}")
