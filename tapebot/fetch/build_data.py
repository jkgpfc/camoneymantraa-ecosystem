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
ETF_URLS = ["https://nsearchives.nseindia.com/content/equities/eq_etfseclist.csv",
            "https://archives.nseindia.com/content/equities/eq_etfseclist.csv"]
PREV_ETF = os.path.join(OUT, "etfs.csv")
# Indices with exchange-traded futures/options. Yahoo symbol -> bot symbol, display name.
INDEX_TICKERS = {
    "^NSEI": ("NIFTY50", "NIFTY 50"),
    "^NSEBANK": ("BANKNIFTY", "NIFTY BANK"),
    "NIFTY_FIN_SERVICE.NS": ("FINNIFTY", "NIFTY FINANCIAL SERVICES"),
    "NIFTY_MID_SELECT.NS": ("MIDCPNIFTY", "NIFTY MIDCAP SELECT"),
    "^NSMIDCP": ("NIFTYNXT50", "NIFTY NEXT 50"),
    "^BSESN": ("SENSEX", "BSE SENSEX"),
    "BSE-BANK.BO": ("BANKEX", "BSE BANKEX"),
    # US indices
    "^GSPC": ("US:SPX", "S&P 500"), "^DJI": ("US:DOW", "Dow Jones Industrial Average"),
    "^IXIC": ("US:NASDAQ", "Nasdaq Composite"), "^NDX": ("US:NDX", "Nasdaq 100"),
    "^RUT": ("US:RUSSELL2000", "Russell 2000"), "^SOX": ("US:SOX", "PHLX Semiconductor"),
    "^VIX": ("US:VIX", "CBOE Volatility Index"),
}
# Global commodity futures (USD) - shown as benchmarks, not MCX prices
GLOBAL_TICKERS = {
    "GC=F": ("GL:GOLD", "COMEX Gold (USD/oz)"), "SI=F": ("GL:SILVER", "COMEX Silver (USD/oz)"),
    "HG=F": ("GL:COPPER", "COMEX Copper (USD/lb)"), "PL=F": ("GL:PLATINUM", "NYMEX Platinum (USD/oz)"),
    "PA=F": ("GL:PALLADIUM", "NYMEX Palladium (USD/oz)"), "ALI=F": ("GL:ALUMINIUM", "COMEX Aluminium (USD/t)"),
    "CL=F": ("GL:CRUDEOIL", "NYMEX WTI Crude (USD/bbl)"), "BZ=F": ("GL:BRENT", "ICE Brent Crude (USD/bbl)"),
    "NG=F": ("GL:NATGAS", "NYMEX Natural Gas (USD/MMBtu)"), "CT=F": ("GL:COTTON", "ICE Cotton (USc/lb)"),
    "INR=X": ("GL:USDINR", "USD/INR"),
}


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


def get_etfs():
    for u in ETF_URLS:
        try:
            r = requests.get(u, headers=UA, timeout=30)
            if r.ok and "symbol" in r.text[:300].lower():
                rows = list(csv.DictReader(io.StringIO(r.text)))
                out = []
                for x in rows:
                    x = {(k or "").strip().lower(): (v or "").strip() for k, v in x.items()}
                    sym = x.get("symbol", "")
                    name = x.get("securityname") or x.get("security name") or x.get("underlying") or ""
                    if sym:
                        out.append((sym.upper(), name, "ETF"))
                if len(out) > 20:
                    with open(PREV_ETF, "w", newline="") as f:
                        csv.writer(f).writerows([("SYMBOL", "NAME", "SERIES")] + out)
                    print(f"NSE ETF list: {len(out)} ETFs")
                    return out
        except Exception as e:
            print("ETF list fetch failed:", e)
    if os.path.exists(PREV_ETF):
        with open(PREV_ETF) as f:
            return [tuple(r) for r in list(csv.reader(f))[1:]]
    print("No ETF list; continuing without ETFs")
    return []


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
    have = {s for s, _, _ in syms}
    syms += [e for e in get_etfs() if e[0] not in have]
    meta = {s: (n, sr) for s, n, sr in syms}
    for y, (s, n) in INDEX_TICKERS.items():
        meta[s] = (n, "IDX")
    for y, (s, n) in GLOBAL_TICKERS.items():
        meta[s] = (n, "GLB")
    tick = {**{y: s for y, (s, n) in INDEX_TICKERS.items()}, **{y: s for y, (s, n) in GLOBAL_TICKERS.items()}, **{f"{s}.NS": s for s, _, _ in syms}}
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
    # indices Yahoo does not carry under the first code: try alternates one by one
    ALT = {"MIDCPNIFTY": ["NIFTY_MIDCAP_SELECT.NS", "^NIFTYMIDSELECT", "NIFTYMIDSELECT.NS"],
           "BANKEX": ["^BSEBANK", "BSEBANK.BO", "^BSEBANKEX"]}
    for sym, alts in ALT.items():
        if sym in data:
            continue
        for y in alts:
            try:
                f = yf.download(y, period="15mo", interval="1d", auto_adjust=False, actions=False, progress=False)
                if isinstance(f.columns, pd.MultiIndex):
                    f.columns = f.columns.get_level_values(0)
                f = f.dropna(subset=["Close"])
                f = f[f["Close"] > 0]
                if len(f) >= 100:
                    data[sym] = f
                    print(f"{sym}: using Yahoo code {y}")
                    break
            except Exception as e:
                print(f"{sym} via {y} failed: {e}")
        if sym not in data:
            print(f"{sym}: not available on Yahoo")
    if len(data) < 300:
        sys.exit(f"Too few symbols fetched ({len(data)}); keeping previous data")
    # MCX futures (continuous front month), kept as history on the data branch
    mcx_info = {}
    try:
        import mcx
        h = mcx.build(os.path.join(OUT, "mcx_history.json"))
        mcx_info = {"status": h.get("status"), "keys": h.get("keys"), "days": h.get("days_fetched"), "series": 0}
        for sym, v in h["s"].items():
            if len(v["d"]) < 20:
                continue
            idx = pd.to_datetime(v["d"])
            data["MCX:" + sym] = pd.DataFrame({"Open": v["o"], "High": v["h"], "Low": v["l"], "Close": v["c"], "Volume": v["v"]}, index=idx)
            meta["MCX:" + sym] = (f"MCX {sym} futures ({v.get('inst', 'FUTCOM')}, continuous)", "MCX")
            mcx_info["series"] += 1
    except Exception as e:
        mcx_info = {"status": f"failed: {str(e)[:120]}"}
    print("MCX", mcx_info)
    dates = sorted({d.strftime("%Y-%m-%d") for f in data.values() for d in f.index})
    didx = {d: k for k, d in enumerate(dates)}
    out = {"v": 1, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "dates": dates, "s": []}
    for sym, f in data.items():
        n, sr = meta.get(sym, ("", "EQ"))
        di = [didx[d.strftime("%Y-%m-%d")] for d in f.index]
        r = lambda col: [round(float(x), 2) for x in f[col]]
        vol = [int(x) if pd.notna(x) else 0 for x in f["Volume"]]
        out["s"].append({"y": sym, "n": n, "r": sr, "i": di, "o": r("Open"), "h": r("High"), "l": r("Low"), "c": r("Close"), "v": vol})
    raw = json.dumps(out, separators=(",", ":")).encode()
    with gzip.open(os.path.join(OUT, "prices.json.gz"), "wb", compresslevel=9) as g:
        g.write(raw)
    # news + quarterly results for the most liquid stocks
    extras_info = {}
    try:
        import extras
        liq = []
        for sym, f in data.items():
            if meta.get(sym, ("", ""))[1] not in ("EQ", "BE", "BZ", "SM", "ST", "ETF"):
                continue
            t = (f["Close"] * f["Volume"]).tail(20).median()
            if t == t:
                liq.append((float(t), sym))
        liq.sort(reverse=True)
        top_news = [(s, meta.get(s, ("", ""))[0]) for _, s in liq[:700] if meta.get(s, ("", ""))[1] != "ETF"]
        extras_info["news"] = extras.build_news(top_news, OUT)
        extras_info["results"] = extras.build_results([s for _, s in liq[:1500] if meta.get(s, ("", ""))[1] != "ETF"], OUT)
    except Exception as e:
        extras_info["error"] = str(e)[:150]
    print("extras", extras_info)
    idx_ok = sorted(s for s in data if meta.get(s, ("", ""))[1] == "IDX")
    etf_n = sum(1 for s in data if meta.get(s, ("", ""))[1] == "ETF")
    glb = sorted(s for s in data if meta.get(s, ("", ""))[1] == "GLB")
    info = {"generated": out["generated"], "lastSession": dates[-1], "symbols": len(out["s"]), "indices": idx_ok, "etfs": etf_n, "global": glb, "mcx": mcx_info, "extras": extras_info, "bytes": os.path.getsize(os.path.join(OUT, "prices.json.gz"))}
    with open(os.path.join(OUT, "info.json"), "w") as f:
        json.dump(info, f)
    print(info)


if __name__ == "__main__":
    main()
