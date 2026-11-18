"""MCX futures: daily bhavcopy -> continuous front-month series per commodity (ratio-adjusted at rollover).
History is kept in mcx_history.json on the data branch and extended every night."""
import json, os, time
from datetime import date, datetime, timedelta, timezone
import requests

BASE = "https://www.mcxindia.com"
PAGE = BASE + "/market-data/bhavcopy"
API = BASE + "/backpage.aspx/GetDateWiseBhavCopy"
HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
       "Accept": "application/json, text/javascript, */*; q=0.01", "Accept-Language": "en-US,en;q=0.9",
       "Origin": BASE, "Referer": PAGE, "X-Requested-With": "XMLHttpRequest"}
FUT = ("FUTCOM", "FUTIDX")


def _k(rec, *names):
    low = {k.lower().replace("_", ""): v for k, v in rec.items()}
    for n in names:
        v = low.get(n.lower().replace("_", ""))
        if v not in (None, ""):
            return v
    return None


def _num(x):
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return 0.0


class MCX:
    def __init__(self):
        self.s = requests.Session(); self.s.headers.update(HDR); self.fmt = None; self.status = "untested"; self.keys = None
        try:
            self.s.get(PAGE, timeout=30)
        except Exception as e:
            self.status = f"page blocked: {e}"

    def day(self, d):
        fmts = [self.fmt] if self.fmt else ["%Y%m%d", "%d/%m/%Y", "%m/%d/%Y"]
        for f in fmts:
            for inst in ("ALL",):
                try:
                    r = self.s.post(API, data=json.dumps({"Date": d.strftime(f), "InstrumentName": inst}),
                                    headers={"Content-Type": "application/json; charset=UTF-8"}, timeout=30)
                    if not r.ok:
                        self.status = f"HTTP {r.status_code}"; continue
                    j = r.json(); data = (j.get("d") or {}).get("Data") if isinstance(j.get("d"), dict) else None
                    if data is None and isinstance(j.get("d"), list):
                        data = j["d"]
                    if data:
                        self.fmt = f; self.status = "ok"; self.keys = self.keys or sorted(data[0].keys())
                        return data
                    self.status = "empty"
                except Exception as e:
                    self.status = f"error: {str(e)[:80]}"
        return []


def build(history_path, max_backfill=330, log=print):
    hist = {"v": 1, "s": {}}
    if os.path.exists(history_path):
        try:
            hist = json.load(open(history_path))
        except Exception:
            pass
    S = hist["s"]; P = hist.setdefault("prev", {})   # P[sym] = {expiry: close} from the previous trading day
    last = max((v["d"][-1] for v in S.values() if v["d"]), default=None)
    today = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    end = today.date() if today.hour >= 23 else today.date() - timedelta(days=1)   # MCX evening session ends ~23:30 IST
    start = (date.fromisoformat(last) + timedelta(days=1)) if last else end - timedelta(days=int(max_backfill * 1.45))
    days = [start + timedelta(days=k) for k in range((end - start).days + 1)]
    days = [d for d in days if d.weekday() < 5]
    m = MCX(); fails = 0; got = 0
    for d in days:
        rows = m.day(d)
        if not rows:
            fails += 1
            if got == 0 and fails >= 8:
                log(f"MCX unreachable ({m.status}); stopping"); break
            time.sleep(0.4); continue
        fails = 0; got += 1
        ds = d.isoformat(); by = {}
        for r in rows:
            inst = str(_k(r, "InstrumentName", "Instrument") or "").upper()
            if inst and inst not in FUT:
                continue
            sym = str(_k(r, "Symbol", "SymbolName") or "").strip().upper()
            exp = str(_k(r, "ExpiryDate", "Expiry") or "").strip()
            c = _num(_k(r, "Close", "ClosePrice", "SettlementPrice", "LTP"))
            if not sym or c <= 0:
                continue
            rec = {"exp": exp, "o": _num(_k(r, "Open", "OpenPrice")) or c, "h": _num(_k(r, "High", "HighPrice")) or c,
                   "l": _num(_k(r, "Low", "LowPrice")) or c, "c": c, "v": _num(_k(r, "Volume", "VolumeLots", "TradedQty")),
                   "oi": _num(_k(r, "OpenInterest", "OI")), "inst": inst}
            by.setdefault(sym, []).append(rec)
        for sym, recs in by.items():
            pick = max(recs, key=lambda x: (x["oi"], x["v"]))           # front month = highest open interest
            ser = S.setdefault(sym, {"d": [], "o": [], "h": [], "l": [], "c": [], "v": [], "exp": "", "inst": pick["inst"]})
            if ser["d"] and ser["d"][-1] >= ds:
                continue
            if ser["exp"] and pick["exp"] != ser["exp"] and ser["c"]:
                old = next((x for x in recs if x["exp"] == ser["exp"]), None)
                k = None
                if old and old["c"] > 0:                                  # ratio back-adjust on rollover (same-day prices)
                    k = pick["c"] / old["c"]
                else:                                                      # old contract gone: use new contract's previous close
                    pc = (P.get(sym) or {}).get(pick["exp"])
                    if pc and ser["c"][-1] > 0:
                        k = pc / ser["c"][-1]
                if k and 0.5 < k < 2:
                    for f in ("o", "h", "l", "c"):
                        ser[f] = [round(x * k, 2) for x in ser[f]]
            ser["exp"] = pick["exp"]
            for f in ("o", "h", "l", "c"):
                ser[f].append(round(pick[f], 2))
            ser["v"].append(int(pick["v"])); ser["d"].append(ds)
        for sym, recs in by.items():
            P[sym] = {x["exp"]: x["c"] for x in recs}
        time.sleep(0.4)
    for v in S.values():                                                   # keep ~15 months
        if len(v["d"]) > 340:
            for f in ("d", "o", "h", "l", "c", "v"):
                v[f] = v[f][-340:]
    hist["status"] = m.status; hist["keys"] = m.keys; hist["days_fetched"] = got
    json.dump(hist, open(history_path, "w"), separators=(",", ":"))
    log(f"MCX: {got} new days, {len(S)} contracts series, status {m.status}")
    return hist
