"""Download 3 years of daily prices per ticker from Yahoo's public chart API (no login).

Browser User-Agent, one request per second, one retry after 5 s on 429. A response that is
not chart JSON (e.g. a bot-protection page) stops the run instead of being worked around.
Raw responses are saved untouched to <rawdir>/<SYM>.json; parse.py reads them.

argv: <tickers.json> <rawdir>      (run with python -I)
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
URL = "https://query2.finance.yahoo.com/v8/finance/chart/{}?range={}&interval=1d&events=div,split"

cfg = json.load(open(sys.argv[1], encoding="utf-8"))
raw = sys.argv[2]
RANGE = sys.argv[3] if len(sys.argv) > 3 else "3y"
syms = [s for g in cfg["groups"].values() for s in g] + [s for g in cfg["added"].values() for s in g] + cfg["spare"]
for s in syms:
    out = os.path.join(raw, s + ".json")
    if os.path.exists(out):
        continue
    for attempt in range(2):
        try:
            req = urllib.request.Request(URL.format(s, RANGE), headers={"User-Agent": UA, "Accept": "application/json"})
            body = urllib.request.urlopen(req, timeout=30).read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0:
                time.sleep(5); continue
            if e.code == 404:
                body = None; break
            sys.exit(f"{s}: HTTP {e.code} - stopping")
    if body is None:
        print(f"{s}: 404", flush=True)
    else:
        if not body.lstrip().startswith(b"{"):
            sys.exit(f"{s}: non-JSON response ({body[:80]!r}) - stopping")
        open(out, "wb").write(body)
        print(f"{s}: {len(body):,} bytes", flush=True)
    time.sleep(1.0)
