"""Build the comprehensive `tickers` table in Supabase.

Sources (all free, no key):
  - US stocks : api.nasdaq.com screener/stocks   (NYSE/NASDAQ/AMEX)
  - US ETFs   : api.nasdaq.com screener/etf       (incl. leveraged: TQQQ, SOXL, …)
  - KR stocks : KRX KIND corpList                 (KOSPI/KOSDAQ/KONEX)
  - KR ETFs   : Naver etfItemList                 (KODEX, TIGER, …)

Yahoo ticker convention: US = symbol as-is; KR = <code>.<KS|KQ|KN> (ETFs = .KS).

Run:  python scripts/build_tickers_db.py            # fetch + load into Supabase
      python scripts/build_tickers_db.py --dry-run  # fetch + print counts only
"""
import json
import sys
from io import StringIO
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
NASDAQ_HDRS = {"User-Agent": UA, "Accept": "application/json"}

MARKET_SUFFIX = {"유가": "KS", "코스닥": "KQ", "코넥스": "KN"}
CHUNK = 500


def norm_us(symbol: str) -> str:
    """NASDAQ symbol -> Yahoo ticker (class shares use '-')."""
    return symbol.strip().upper().replace("/", "-").replace("^", "-P")


def fetch_us(kind: str, typ: str) -> list[dict]:
    url = f"https://api.nasdaq.com/api/screener/{kind}?download=true"
    data = requests.get(url, headers=NASDAQ_HDRS, timeout=60).json()
    block = data["data"]
    rows = block.get("rows") or block.get("data", {}).get("rows") or []
    out = []
    for r in rows:
        sym = norm_us(r.get("symbol", ""))
        name = (r.get("name") or r.get("companyName") or "").strip()
        if not sym or not name:
            continue
        out.append({"ticker": sym, "name": name, "code": "",
                    "market": "ETF" if typ == "etf" else "US",
                    "country": "US", "type": typ})
    return out


def fetch_kr_stocks() -> list[dict]:
    import pandas as pd

    url = ("http://kind.krx.co.kr/corpgeneral/corpList.do"
           "?method=download&searchType=13")
    resp = requests.get(url, timeout=60)
    resp.encoding = "euc-kr"
    df = pd.read_html(StringIO(resp.text), header=0)[0]
    out = []
    for _, row in df.iterrows():
        suffix = MARKET_SUFFIX.get(str(row["시장구분"]).strip())
        if not suffix:
            continue
        code = str(row["종목코드"]).strip().zfill(6)
        out.append({"ticker": f"{code}.{suffix}", "name": str(row["회사명"]).strip(),
                    "code": code, "market": str(row["시장구분"]).strip(),
                    "country": "KR", "type": "stock"})
    return out


def fetch_kr_etfs() -> list[dict]:
    url = "https://finance.naver.com/api/sise/etfItemList.nhn"
    raw = requests.get(url, timeout=60).content
    data = json.loads(raw.decode("cp949"))
    out = []
    for it in data["result"]["etfItemList"]:
        code = str(it["itemcode"]).strip().zfill(6)
        out.append({"ticker": f"{code}.KS", "name": str(it["itemname"]).strip(),
                    "code": code, "market": "ETF", "country": "KR", "type": "etf"})
    return out


def main() -> None:
    dry = "--dry-run" in sys.argv

    print("Fetching sources …")
    us_stocks = fetch_us("stocks", "stock")
    us_etfs = fetch_us("etf", "etf")
    kr_stocks = fetch_kr_stocks()
    kr_etfs = fetch_kr_etfs()
    print(f"  US stocks: {len(us_stocks)}")
    print(f"  US ETFs  : {len(us_etfs)}")
    print(f"  KR stocks: {len(kr_stocks)}")
    print(f"  KR ETFs  : {len(kr_etfs)}")

    # Dedup by ticker (US stocks win over an accidental ETF dupe, etc.)
    by_ticker: dict = {}
    for rec in us_stocks + us_etfs + kr_stocks + kr_etfs:
        by_ticker.setdefault(rec["ticker"], rec)
    records = list(by_ticker.values())
    print(f"  TOTAL unique: {len(records)}")

    if dry:
        for t in ("AAPL", "TQQQ", "SOXL", "005930.KS", "069500.KS"):
            hit = by_ticker.get(t)
            print(f"  check {t}: {hit['name'] if hit else 'MISSING'}")
        print("\n(dry run — nothing written)")
        return

    from app.db import get_client

    client = get_client()
    written = 0
    for i in range(0, len(records), CHUNK):
        client.table("tickers").upsert(records[i:i + CHUNK]).execute()
        written += len(records[i:i + CHUNK])
        print(f"  upserted {written}/{len(records)}")
    print(f"\nDone. {written} tickers in Supabase.")


if __name__ == "__main__":
    main()
