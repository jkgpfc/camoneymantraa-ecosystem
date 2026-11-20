"""Tape Reader Bot - intraday bars for the Grid ladder backtest (runs on GitHub Actions after build_data.py).
Downloads 5-minute bars (last 60 days) and 1-minute bars (last 7 days) from Yahoo Finance for:
  * every symbol in intraday_list.txt (PSU stocks + watchlist), and
  * the most liquid NSE equities by median daily turnover in prices.json.gz (top N).
Writes intraday.json.gz: {"v":1,"generated":..., "tf":{"5m":{SYM:[t,o,h,l,c]...}, "1m":{...}}}
where t is minutes since the Unix epoch (IST bars) and prices are rounded to 2 decimals.
"""
import gzip, json, os, statistics, sys, time
from datetime import datetime, timezone
import yfinance as yf

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
TOP_N = int(os.environ.get("INTRADAY_TOP_N", "150"))
HERE = os.path.dirname(os.path.abspath(__file__))


def wanted():
    syms = []
    p = os.path.join(HERE, "intraday_list.txt")
    if os.path.exists(p):
        for line in open(p):
            line = line.split("#")[0].strip()
            syms += [s.strip().upper() for s in line.replace(",", " ").split() if s.strip()]
    try:
        d = json.load(gzip.open(os.path.join(OUT, "prices.json.gz")))
        liq = []
        for e in d["s"]:
            if e.get("r") not in ("EQ", "BE") or len(e.get("c", [])) < 60:
                continue
            to = [c * v for c, v in zip(e["c"][-120:], e["v"][-120:]) if c and v]
            if to:
                liq.append((statistics.median(to), e["y"]))
        syms += [s for _, s in sorted(liq, reverse=True)[:TOP_N]]
    except Exception as ex:
        print("liquidity list unavailable:", ex)
    seen, out = set(), []
    for s in syms:
        if s not in seen:
            seen.add(s); out.append(s)
    return out


def pull(syms, period, interval):
    res = {}
    for i in range(0, len(syms), 40):
        chunk = syms[i:i + 40]
        tick = [s + ".NS" for s in chunk]
        for attempt in range(3):
            try:
                df = yf.download(tick, period=period, interval=interval, group_by="ticker", auto_adjust=False,
                                 actions=False, progress=False, threads=True, prepost=False)
                break
            except Exception as ex:
                print("retry", interval, i, ex); time.sleep(5); df = None
        if df is None or df.empty:
            continue
        for s, t in zip(chunk, tick):
            try:
                x = df[t] if len(tick) > 1 else df
                x = x.dropna(subset=["Open", "High", "Low", "Close"])
                if x.empty:
                    continue
                idx = x.index.tz_convert("Asia/Kolkata") if x.index.tz is not None else x.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
                rows = []
                for ts, o, h, l, c in zip(idx, x["Open"], x["High"], x["Low"], x["Close"]):
                    m = ts.hour * 60 + ts.minute
                    if 555 <= m < 930 and h >= l > 0:
                        rows.append([int(ts.timestamp() // 60), round(float(o), 2), round(float(h), 2), round(float(l), 2), round(float(c), 2)])
                if len(rows) > 50:
                    res[s] = rows
            except Exception as ex:
                print("skip", s, interval, ex)
        time.sleep(1)
    return res


def main():
    syms = wanted()
    print("intraday symbols:", len(syms))
    out = {"v": 1, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tf": {}}
    out["tf"]["5m"] = pull(syms, "60d", "5m")
    out["tf"]["1m"] = pull(syms, "7d", "1m")
    print({k: len(v) for k, v in out["tf"].items()})
    with gzip.open(os.path.join(OUT, "intraday.json.gz"), "wt") as f:
        json.dump(out, f, separators=(",", ":"))
    print("bytes", os.path.getsize(os.path.join(OUT, "intraday.json.gz")))


if __name__ == "__main__":
    main()
