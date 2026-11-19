"""Nightly extras for the most liquid stocks:
   news.json  - up to 4 Google News headlines per stock from the last 21 days (title, publisher, link, time)
   results.json - latest quarterly revenue / net profit with YoY and QoQ change (Yahoo), refreshed in rotation
"""
import json, os, re, time, html
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
STRIP = re.compile(r"\b(limited|ltd\.?)\b", re.I)
GENERIC = {"india", "indian", "the", "and", "of", "corporation", "company", "co", "corp", "industries", "enterprises", "finance", "financial", "bank", "power", "energy", "infra", "ltd"}
# headlines that are tips, price predictions or market roundups, not company news
NOISE = re.compile(r"prediction|target price|buy,? sell or hold|stocks? to (buy|watch)|share price (today|live)|stock price live|live updates?|technical (view|outlook)|top (gainers|losers)|stocks in news|multibagger|penny stock|should you buy|trade setup|ask profit|intraday pick", re.I)
KEY = re.compile(r"result|profit|revenue|earning|q[1-4]|order|contract|dividend|acqui|merger|demerger|stake|board|approv|rating|guidance|block deal|bulk deal|qip|bonus|split|buyback|raises|fund ?rais|bond|ncd|ipo|ofs|promoter|pledge|resign|appoint|ceo|md\b|cfo|plant|capacity|launch|expan|sebi|penalt|tax|default|downgrade|upgrade", re.I)


def _clean_name(name):
    return re.sub(r"\s+", " ", STRIP.sub("", name or "").replace("&", " and ")).strip()


def _query(sym, name):
    n = _clean_name(name)
    return f'"{n}"' if len(n) >= 4 else f'"{sym}" NSE'


def _matches(title, sym, name):
    t = title.lower()
    if re.search(r"(?<![a-z0-9])" + re.escape(sym.lower()) + r"(?![a-z0-9])", t):
        return True
    words = [w for w in re.findall(r"[a-z0-9]+", _clean_name(name).lower())]
    if not words:
        return False
    if " ".join(words) in t:
        return True
    distinct = [w for w in words if w not in GENERIC and len(w) >= 3]
    lead = " ".join(words[:2]) if len(words) >= 2 else words[0]
    if len(words) >= 2 and re.search(r"(?<![a-z0-9])" + re.escape(lead) + r"(?![a-z0-9])", t):
        return True                                          # e.g. "power finance", "state bank"
    return bool(distinct) and all(re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", t) for w in distinct[:2])


def _news_one(args):
    sym, name = args
    url = "https://news.google.com/rss/search"
    try:
        r = requests.get(url, params={"q": _query(sym, name) + " when:21d", "hl": "en-IN", "gl": "IN", "ceid": "IN:en"}, headers=UA, timeout=20)
        if not r.ok:
            return sym, None
        root = ET.fromstring(r.content)
        out = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=21)
        for it in root.iter("item"):
            title = html.unescape(it.findtext("title") or "").strip()
            src = it.find("source")
            pub = src.text.strip() if src is not None and src.text else ""
            if pub and title.endswith(" - " + pub):
                title = title[: -len(pub) - 3]
            try:
                dt = parsedate_to_datetime(it.findtext("pubDate"))
            except Exception:
                continue
            if dt < cutoff or NOISE.search(title) or not _matches(title, sym, name):
                continue
            out.append({"t": title[:180], "p": pub[:40], "u": it.findtext("link") or "", "d": dt.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M")})
        out.sort(key=lambda x: x["d"], reverse=True)
        out.sort(key=lambda x: 0 if KEY.search(x["t"]) else 1)      # company-event headlines first, newest first within each group
        seen, uniq = set(), []
        for x in out:                                   # drop near-duplicate headlines
            k = re.sub(r"\W+", "", x["t"].lower())[:60]
            if k in seen:
                continue
            seen.add(k); uniq.append(x)
        return sym, uniq[:4]
    except Exception:
        return sym, None


def build_news(items, out_dir, log=print):
    res, ok = {}, 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        for sym, v in ex.map(_news_one, items):
            if v is not None:
                ok += 1
                if v:
                    res[sym] = v
    json.dump({"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "n": res}, open(os.path.join(out_dir, "news.json"), "w"), separators=(",", ":"))
    log(f"news: {ok}/{len(items)} queried, {len(res)} with recent headlines")
    return {"queried": len(items), "ok": ok, "with_news": len(res)}


def _results_one(sym):
    import yfinance as yf
    try:
        q = yf.Ticker(sym + ".NS").quarterly_income_stmt
        if q is None or q.empty:
            return sym, None
        q = q.reindex(sorted(q.columns, reverse=True), axis=1)
        def row(*names):
            for n in names:
                if n in q.index:
                    return [None if v != v else float(v) for v in q.loc[n].tolist()]
            return None
        rev = row("Total Revenue", "Operating Revenue")
        pat = row("Net Income", "Net Income Common Stockholders")
        if not rev and not pat:
            return sym, None
        def chg(a, i, j):
            try:
                if a and a[i] is not None and a[j] not in (None, 0):
                    return round((a[i] / abs(a[j]) - 1) * 100, 1) if a[j] > 0 else None
            except Exception:
                pass
            return None
        rec = {"q": q.columns[0].strftime("%Y-%m-%d")}
        if rev and rev[0] is not None:
            rec.update(rev=round(rev[0] / 1e7, 1), revQ=chg(rev, 0, 1), revY=chg(rev, 0, 4) if len(rev) > 4 else None)
        if pat and pat[0] is not None:
            rec.update(pat=round(pat[0] / 1e7, 1), patQ=chg(pat, 0, 1), patY=chg(pat, 0, 4) if len(pat) > 4 else None)
        return sym, rec
    except Exception:
        return sym, None


def build_results(symbols, out_dir, per_night=350, log=print):
    path = os.path.join(out_dir, "results.json")
    old = {}
    if os.path.exists(path):
        try:
            old = json.load(open(path)).get("r", {})
        except Exception:
            pass
    keep = {s: old[s] for s in symbols if s in old}
    order = sorted(symbols, key=lambda s: keep.get(s, {}).get("at", ""))   # never fetched / oldest first
    todo = order[:per_night]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    got = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        for sym, rec in ex.map(_results_one, todo):
            if rec:
                rec["at"] = today; keep[sym] = rec; got += 1
            elif sym in keep:
                keep[sym]["at"] = today
    json.dump({"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "r": keep}, open(path, "w"), separators=(",", ":"))
    log(f"results: refreshed {got}/{len(todo)}, {len(keep)} stocks on file")
    return {"refreshed": got, "tried": len(todo), "on_file": len(keep)}
