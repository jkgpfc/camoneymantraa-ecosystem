"""Tape Reader Bot - nightly data build (runs on GitHub Actions).
Downloads ~15 months of daily bars for every NSE equity (+ NIFTY 50) from Yahoo Finance
and writes one gzipped JSON file that the bot loads directly from GitHub.
"""
import csv, gzip, io, json, os, sys, time
from datetime import datetime, timezone
import pandas as pd
import requests
import yfinance as yf

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept": "*/*", "Referer": "https://www.nseindia.com/"}
LIST_URLS = ["https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
             "https://archives.nseindia.com/content/equities/EQUITY_L.csv"]
PREV_LIST = os.path.join(OUT, "symbols.csv")


def get_symbols():
    for u in LIST_URLS:
        try:
            r = requests.get(u, headers=UA, timeout=30)
            if r.ok and "SYMBOL" in r.text[:200]:
                rows = list(csv.DictReader(io.StringIO(r.text)))
                out = []
                for x in rows:
                    x = {k.strip().upper(): (v or "").strip() for k, v in x.items()}
                    if x.get("SERIES", "EQ") in ("EQ", "BE", "BZ", "SM", "ST") and x.get("SYMBOL"):
                        out.append((x["SYMBOL"], x.get("NAME OF COMPANY", ""), x.get("SERIES", "EQ")))
                if len(out) > 500:
                    with open(PREV_LIST, "w", newline="") as f:
                        csv.writer(f).writerows([("SYMBOL", "NAME", "SERIES")] + out)
                    print(f"NSE list: {len(out)} symbols")
                    return out
        except Exception as e:
            print("list fetch failed:", e)
    if os.path.exists(PREV_LIST):
        with open(PREV_LIST) as f:
            out = [tuple(r) for r in list(csv.reader(f))[1:]]
        print(f"Using previous list: {len(out)} symbols")
        return out
    sys.exit("No symbol list available")


def frames(df, tickers):
    if df is None or df.empty:
        return
    if isinstance(df.columns, pd.MultiIndex):
        lv = set(df.columns.get_level_values(0))
        for t in tickers:
            if t in lv:
                yield t, df[t]
    else:
        yield tickers[0], df


def main():
    syms = get_symbols()
    meta = {s: (n, sr) for s, n, sr in syms}
    tick = {"^NSEI": "NIFTY50", **{f"{s}.NS": s for s, _, _ in syms}}
    names = list(tick)
    data = {}
    for i in range(0, len(names), 100):
        chunk = names[i:i + 100]
        for attempt in range(4):
            try:
                df = yf.download(chunk, period="15mo", interval="1d", group_by="ticker", auto_adjust=False,
                                 actions=False, threads=True, progress=False)
                break
            except Exception as e:
                print("retry", e); time.sleep(15 * (attempt + 1)); df = None
        for t, f in frames(df, chunk):
            f = f.dropna(subset=["Close"])
            f = f[f["Close"] > 0]
            if len(f) < 5:
                continue
            data[tick[t]] = f
        print(f"{min(i + 100, len(names))}/{len(names)} requested, {len(data)} with data", flush=True)
        time.sleep(1.5)
    if len(data) < 300:
        sys.exit(f"Too few symbols fetched ({len(data)}); keeping previous data")
    # drop today's bar if the run happens before the close is final (runs are scheduled after 18:30 IST)
    dates = sorted({d.strftime("%Y-%m-%d") for f in data.values() for d in f.index})
    didx = {d: k for k, d in enumerate(dates)}
    out = {"v": 1, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "dates": dates, "s": []}
    for sym, f in data.items():
        n, sr = meta.get(sym, ("NIFTY 50", "IDX") if sym == "NIFTY50" else ("", "EQ"))
        di = [didx[d.strftime("%Y-%m-%d")] for d in f.index]
        r = lambda col: [round(float(x), 2) for x in f[col]]
        vol = [int(x) if pd.notna(x) else 0 for x in f["Volume"]]
        out["s"].append({"y": sym, "n": n, "r": sr, "i": di, "o": r("Open"), "h": r("High"), "l": r("Low"), "c": r("Close"), "v": vol})
    raw = json.dumps(out, separators=(",", ":")).encode()
    with gzip.open(os.path.join(OUT, "prices.json.gz"), "wb", compresslevel=9) as g:
        g.write(raw)
    info = {"generated": out["generated"], "lastSession": dates[-1], "symbols": len(out["s"]), "bytes": os.path.getsize(os.path.join(OUT, "prices.json.gz"))}
    with open(os.path.join(OUT, "info.json"), "w") as f:
        json.dump(info, f)
    print(info)


if __name__ == "__main__":
    main()
