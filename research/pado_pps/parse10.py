"""10-year price table: the 150 study ETFs that trade over the whole 10-year window.

A ticker is kept if its first adjusted close is within 10 calendar days of the earliest first
date among the 150 (i.e. it was listed before the window began). The table keeps the dates
common to all kept tickers.

argv: <tickers.json> <rawdir> <out.json>      (run with python -I)
"""

import datetime
import hashlib
import json
import os
import sys
import time

cfg = json.load(open(sys.argv[1], encoding="utf-8"))
raw, out = sys.argv[2], sys.argv[3]
syms = [s for g in cfg["groups"].values() for s in g] + [s for g in cfg["added"].values() for s in g]
series = {}
for s in syms:
    r = json.load(open(os.path.join(raw, s + ".json"), encoding="utf-8"))["chart"]["result"][0]
    adj = r["indicators"].get("adjclose", [{}])[0].get("adjclose") or r["indicators"]["quote"][0]["close"]
    series[s] = {time.strftime("%Y-%m-%d", time.gmtime(t)): float(v)
                 for t, v in zip(r.get("timestamp") or [], adj) if v is not None and v > 0}
first = {s: min(v) for s, v in series.items()}
start = min(first.values())
lim = (datetime.date.fromisoformat(start) + datetime.timedelta(days=10)).isoformat()
kept = [s for s in syms if first[s] <= lim]
dropped = sorted((first[s], s) for s in syms if first[s] > lim)
dates = sorted(set.intersection(*(set(series[s]) for s in kept)))
prices = [[series[s][d] for d in dates] for s in kept]
blob = json.dumps({"syms": kept, "dates": dates, "prices": prices}, separators=(",", ":"))
json.dump({"syms": kept, "dates": dates, "prices": prices, "dropped": dropped,
           "sha256": hashlib.sha256(blob.encode()).hexdigest()}, open(out, "w"), separators=(",", ":"))
print(len(kept), "kept,", len(dates), "common days", dates[0], dates[-1])
print("dropped", len(dropped), dropped)
