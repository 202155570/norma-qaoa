"""Independent validation on prices before 2016-11 (never used by bt.py / diag.py / cand.py).
Rules fixed in oos_prereg.md (written before the download).

argv: build <rawdir> <out.json>   price table for the validation window; prints counts and dates only
      run                         one run: C1_signal vs base, writes oos_result.json, oos_holdings.json
Run with python -I.
"""

import hashlib
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
END = "2016-10-31"
MIN_ETFS = 40


def build(raw, out):
    p10 = json.load(open(os.path.join(HERE, "prices10.json")))
    series = {}
    for s in p10["syms"]:
        f = os.path.join(raw, s + ".json")
        if not os.path.exists(f):
            continue
        r = json.load(open(f, encoding="utf-8"))["chart"]["result"][0]
        assert r["meta"].get("dataGranularity") == "1d", (s, r["meta"].get("dataGranularity"))
        adj = r["indicators"].get("adjclose", [{}])[0].get("adjclose") or r["indicators"]["quote"][0]["close"]
        series[s] = {time.strftime("%Y-%m-%d", time.gmtime(t)): float(v)
                     for t, v in zip(r.get("timestamp") or [], adj) if v is not None and v > 0}
    start = min(series["BIL"])
    late = sorted((min(v), s) for s, v in series.items() if min(v) > start)
    cand = [s for s in p10["syms"] if s in series and min(series[s]) <= start]
    spy_days = {d for d in series["SPY"] if start <= d <= END}
    gaps = {s: len(spy_days - set(series[s])) for s in cand}
    holes = sorted((g, s) for s, g in gaps.items() if g > 0.01 * len(spy_days))
    kept = [s for s in cand if gaps[s] <= 0.01 * len(spy_days)]
    dates = sorted(d for d in set.intersection(*(set(series[s]) for s in kept)) if start <= d <= END)
    prices = [[series[s][d] for d in dates] for s in kept]
    # data check on the overlap with prices10.json (already-seen period, not part of the verdict)
    i10 = {d: i for i, d in enumerate(p10["dates"])}
    worst = []
    for s in kept:
        row = p10["prices"][p10["syms"].index(s)]
        common = sorted(d for d in series[s] if d in i10)
        a = np.array([series[s][d] for d in common]); b = np.array([row[i10[d]] for d in common])
        worst.append((float(np.abs(a[1:] / a[:-1] - b[1:] / b[:-1]).max()), s, len(common)))
    worst.sort(reverse=True)
    blob = json.dumps({"syms": kept, "dates": dates, "prices": prices}, separators=(",", ":"))
    json.dump({"syms": kept, "dates": dates, "prices": prices, "start": start, "end": END,
               "listed_later": late, "dropped_for_gaps": holes, "no_file": [s for s in p10["syms"] if s not in series],
               "overlap_check": {"days": worst[0][2], "max_abs_daily_return_diff": worst[0][0], "worst": worst[:5],
                                 "tickers_over_1e-3": sum(w[0] > 1e-3 for w in worst)},
               "sha256": hashlib.sha256(blob.encode()).hexdigest()}, open(out, "w"), separators=(",", ":"))
    print(f"window {start} -> {END}: {len(kept)} ETFs kept, {len(dates)} common days ({len(spy_days)} SPY days)")
    print(f"listed after {start}: {len(late)}; dropped for gaps: {holes}; no file: {[s for s in p10['syms'] if s not in series]}")
    print("overlap check (daily returns vs prices10.json): worst", [(round(w[0], 6), w[1], w[2]) for w in worst[:5]])
    print("kept:", " ".join(kept))
    if len(kept) < MIN_ETFS:
        print(f"STOP: fewer than {MIN_ETFS} ETFs")


def run_once():
    sys.path.insert(0, HERE)        # -I drops the script directory; cand.py and bt.py are our own modules
    import cand
    px = json.load(open(os.path.join(HERE, "prices_old.json")))
    syms, dates = px["syms"], px["dates"]
    assert len(syms) >= MIN_ETFS and dates[-1] <= END
    P = np.array(px["prices"]).T
    t0 = time.time()
    out = cand.run(P, dates, syms, 10 ** 6)
    reb = out["reb"]; N = len(out["rf"]); nper = len(reb) - 1; h = nper // 2; cut = reb[h] - reb[0]
    full, rand = cand.table(out, 0, N, 0, nper)
    first, rand1 = cand.table(out, 0, cut, 0, h)
    last, rand2 = cand.table(out, cut, N, h, nper)
    others = ["C2_mv4", "C2_mv12", "C2_mv36", "C3_trend", "C4_invvol", "all_mv4"]
    pairs = [("C1_signal", "base")] + [(m, "base") for m in others] + [("C1_signal", "equal"), ("base", "equal")]
    d = cand.diff_ci(out, 0, N, pairs); d1 = cand.diff_ci(out, 0, cut, pairs); d2 = cand.diff_ci(out, cut, N, pairs)
    D = d["C1_signal-base"]
    verdict = "confirmed" if D["point"] > 0 and D["ci95"][0] > 0 else "same direction, not confirmed" if D["point"] > 0 else "rejected"
    res = {"prereg_sha256": hashlib.sha256(open(os.path.join(HERE, "oos_prereg.md"), "rb").read()).hexdigest(),
           "data_sha256": px["sha256"], "versions": {"python": sys.version.split()[0], "numpy": np.__version__},
           "period": [dates[reb[0]], dates[reb[-1]]], "half_split": dates[reb[h]], "rebalances": nper, "n_etfs": len(syms),
           "verdict": verdict, "full": full, "first_half": first, "last_half": last,
           "random_full": rand, "random_first": rand1, "random_last": rand2,
           "sharpe_diff_full": d, "sharpe_diff_first": d1, "sharpe_diff_last": d2,
           "bil_filled_slots": out["fills"], "eligible_min": min(out["n_elig"]), "eligible_median": float(np.median(out["n_elig"])),
           "shrinkage_mean": float(np.mean(out["deltas"])), "overlap_check": px["overlap_check"],
           "deviations": ["fetch.py with range=max returns monthly bars; daily prices were downloaded with fetch_p.py "
                          "(explicit period 2007-05-01..2018-01-01, same source and rules) into rawold/ instead of rawmax/"],
           "seconds": round(time.time() - t0, 1)}
    json.dump(res, open(os.path.join(HERE, "oos_result.json"), "w"), indent=1)
    json.dump(out["holdings"], open(os.path.join(HERE, "oos_holdings.json"), "w"))
    names = ["base", "C1_signal"] + others + ["score_only", "equal", "spy"]
    cand.show(f"FULL  {res['period']} ({nper} rebalances, {len(syms)} ETFs)", full, rand, names)
    cand.show(f"FIRST -> {res['half_split']}", first, rand1, names)
    cand.show(f"LAST  {res['half_split']} ->", last, rand2, names)
    for k in d:
        print(f"  diff {k:>16}: full {d[k]['point']:+.3f} [{d[k]['ci95'][0]:+.3f}, {d[k]['ci95'][1]:+.3f}]"
              f"   first {d1[k]['point']:+.3f}   last {d2[k]['point']:+.3f}")
    print("  BIL-filled slots", {m: v for m, v in out["fills"].items() if v}, " eligible min/median", res["eligible_min"], res["eligible_median"])
    print("VERDICT:", verdict, " seconds", res["seconds"])


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(sys.argv[2], sys.argv[3])
    else:
        assert sys.argv[1] == "run"
        run_once()
