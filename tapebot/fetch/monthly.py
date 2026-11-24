"""Tape Reader Bot - monthly bars + market-cap buckets for the W-pattern tab (runs on GitHub Actions).

Builds monthly.json.gz:
  {"v":1, "generated":..., "amfi":{"period":..,"url":..,"n":..}, "cap":{SYM:[rank, avg_mcap_cr]},
   "sme":[SYM,...], "names":{SYM:name}, "m":{SYM:[[yyyymm,o,h,l,c,v],...]}}
* Market cap: AMFI's half-yearly "Average Market Capitalisation" list (rank 1-100 large, 101-250 mid,
  251+ small per SEBI circular of 6 Oct 2017). The bot splits 251-500 small and 501+ micro.
* MSME: NSE Emerge (SME platform) equity list.
* Monthly OHLCV: Yahoo Finance, 10 years, main-board EQ/BE/BZ + SME symbols.
Rebuilt at most once every 6 days (reuses the previous file otherwise).
"""
import csv, gzip, io, json, os, sys, time
from datetime import datetime, timezone, date
import requests
import pandas as pd
import yfinance as yf

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
FN = os.path.join(OUT, "monthly.json.gz")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept": "*/*", "Referer": "https://www.nseindia.com/"}


def fresh_enough():
    try:
        old = json.load(gzip.open(FN))
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(old["generated"])).days
        if age < 6 and len(old.get("m", {})) > 500 and old.get("cap"):
            print(f"monthly.json.gz is {age} days old - reusing"); return True
    except Exception:
        pass
    return False


def amfi():
    """Latest AMFI categorisation workbook -> {NSE symbol: (rank, avg mcap Rs cr)}."""
    today = date.today(); cands = []
    for y in range(today.year, today.year - 3, -1):
        for dd, mon in (("31", "Dec"), ("30", "Jun")):
            d = date(y, 12 if mon == "Dec" else 6, int(dd))
            if d < today:
                cands.append(f"{dd}{mon}{y}")
    for tag in cands:
        for url in (f"https://portal.amfiindia.com/spages/AverageMarketCapitalization{tag}.xlsx",
                    f"https://portal.amfiindia.com/spages/AverageMarketCapitalization{tag}.xls",
                    f"https://www.amfiindia.com/Themes/Theme1/downloads/AverageMarketCapitalization{tag}.xlsx",
                    f"https://www.amfiindia.com/Themes/Theme1/downloads/AverageMarketCapitalization{tag}.xls"):
            try:
                r = requests.get(url, headers=UA, timeout=60)
                if r.status_code != 200 or len(r.content) < 20000:
                    continue
                raw = pd.read_excel(io.BytesIO(r.content), header=None)
                hdr = None
                for i in range(min(15, len(raw))):
                    row = " | ".join(str(x) for x in raw.iloc[i].tolist()).lower()
                    if "symbol" in row and ("average" in row or "categor" in row):
                        hdr = i; break
                if hdr is None:
                    continue
                cols = [str(x).strip().lower() for x in raw.iloc[hdr].tolist()]
                df = raw.iloc[hdr + 1:].reset_index(drop=True)
                sym_c = next((k for k, c in enumerate(cols) if "nse" in c and "symbol" in c), None)
                avg_c = next((k for k, c in enumerate(cols) if "average" in c), None)
                if sym_c is None or avg_c is None:
                    continue
                out = {}
                for _, row in df.iterrows():
                    rank, sym, mc = row.iloc[0], row.iloc[sym_c], row.iloc[avg_c]
                    try:
                        rank = int(float(rank)); mc = float(str(mc).replace(",", ""))
                    except (TypeError, ValueError):
                        continue
                    if isinstance(sym, str) and sym.strip() and sym.strip() not in ("-", "nan"):
                        out[sym.strip().upper()] = [rank, round(mc, 1)]
                if len(out) > 1000:
                    print("AMFI", tag, url, len(out)); return {"period": tag, "url": url, "n": len(out)}, out
            except Exception as ex:
                print("AMFI try failed", url, ex)
    print("AMFI list not found"); return {"period": None, "url": None, "n": 0}, {}


def sme_list():
    for url in ("https://nsearchives.nseindia.com/emerge/corporates/content/SME_EQUITY_L.csv",
                "https://archives.nseindia.com/emerge/corporates/content/SME_EQUITY_L.csv"):
        try:
            r = requests.get(url, headers=UA, timeout=30)
            if r.status_code == 200 and "SYMBOL" in r.text[:300].upper():
                rows = list(csv.DictReader(io.StringIO(r.text)))
                key = next(k for k in rows[0] if k.strip().upper() == "SYMBOL")
                nk = next((k for k in rows[0] if "NAME" in k.upper()), None)
                out = {x[key].strip().upper(): (x[nk].strip() if nk else "") for x in rows if x.get(key)}
                print("SME symbols", len(out)); return out
        except Exception as ex:
            print("SME list failed", url, ex)
    return {}


def main_board():
    out = {}
    try:
        d = json.load(gzip.open(os.path.join(OUT, "prices.json.gz")))
        for e in d["s"]:
            if e.get("r") in ("EQ", "BE", "BZ"):
                out[e["y"]] = e.get("n", "")
    except Exception as ex:
        print("prices.json.gz unavailable", ex)
    return out


def monthly(syms):
    res = {}
    for i in range(0, len(syms), 100):
        chunk = syms[i:i + 100]; tick = [s + ".NS" for s in chunk]; df = None
        for attempt in range(3):
            try:
                df = yf.download(tick, period="10y", interval="1mo", group_by="ticker", auto_adjust=True,
                                 actions=False, progress=False, threads=True)
                break
            except Exception as ex:
                print("retry", i, ex); time.sleep(5)
        if df is None or df.empty:
            continue
        for s, t in zip(chunk, tick):
            try:
                x = df[t] if len(tick) > 1 else df
                x = x.dropna(subset=["Open", "High", "Low", "Close"])
                rows = [[int(ix.year * 100 + ix.month), round(float(o), 2), round(float(h), 2), round(float(l), 2), round(float(c), 2), int(v or 0)]
                        for ix, o, h, l, c, v in zip(x.index, x["Open"], x["High"], x["Low"], x["Close"], x["Volume"].fillna(0)) if h >= l > 0]
                if len(rows) >= 12:
                    res[s] = rows
            except Exception:
                pass
        time.sleep(1)
    return res


def main():
    if fresh_enough():
        return
    meta, cap = amfi()
    sme = sme_list()
    mb = main_board()
    syms = sorted(set(mb) | set(sme))
    print("symbols to fetch", len(syms))
    m = monthly(syms)
    names = {**{k: v for k, v in sme.items()}, **{k: v for k, v in mb.items()}}
    out = {"v": 1, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "amfi": meta, "cap": cap,
           "sme": sorted(s for s in sme if s in m), "names": {k: names.get(k, "") for k in m}, "m": m}
    with gzip.open(FN, "wt") as f:
        json.dump(out, f, separators=(",", ":"))
    print("monthly:", len(m), "symbols;", len(out["sme"]), "SME;", "AMFI", meta, "bytes", os.path.getsize(FN))


if __name__ == "__main__":
    main()
