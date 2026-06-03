"""Generate data/tickers.json — the ticker autocomplete cache.

Source: KRX KIND public listing (회사명 / 시장구분 / 종목코드) for all KOSPI,
KOSDAQ, and KONEX companies. No credentials needed. We add a small curated set
of common US stocks / ETFs so US tickers autocomplete by name too.

Run:  python scripts/build_tickers.py

The app reads this file at startup and can append new entries to it on a live
lookup miss (see app/services/tickers.py), so the cache grows over time.
"""
import json
import sys
from io import StringIO
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "tickers.json"

KIND_URL = (
    "http://kind.krx.co.kr/corpgeneral/corpList.do"
    "?method=download&searchType=13"
)

# 시장구분 -> Yahoo Finance suffix
MARKET_SUFFIX = {"유가": "KS", "코스닥": "KQ", "코넥스": "KN"}

# Curated US / global names so they autocomplete by name as well as ticker.
US_SEED = [
    ("Apple", "AAPL"), ("Microsoft", "MSFT"), ("NVIDIA", "NVDA"),
    ("Alphabet (Google)", "GOOGL"), ("Amazon", "AMZN"), ("Meta", "META"),
    ("Tesla", "TSLA"), ("Netflix", "NFLX"), ("AMD", "AMD"), ("Intel", "INTC"),
    ("Broadcom", "AVGO"), ("Berkshire Hathaway", "BRK-B"), ("Coca-Cola", "KO"),
    ("JPMorgan", "JPM"), ("Visa", "V"), ("Palantir", "PLTR"),
    # Popular ETFs
    ("SPDR S&P 500 ETF", "SPY"), ("Invesco QQQ (Nasdaq 100)", "QQQ"),
    ("Vanguard S&P 500 ETF", "VOO"), ("Vanguard Total Stock Market", "VTI"),
    ("iShares Core S&P 500", "IVV"), ("Schwab US Dividend (SCHD)", "SCHD"),
]


def fetch_krx() -> list[dict]:
    import pandas as pd

    resp = requests.get(KIND_URL, timeout=60)
    resp.encoding = "euc-kr"
    df = pd.read_html(StringIO(resp.text), header=0)[0]
    records = []
    for _, row in df.iterrows():
        market = str(row["시장구분"]).strip()
        suffix = MARKET_SUFFIX.get(market)
        if not suffix:
            continue
        code = str(row["종목코드"]).strip().zfill(6)
        name = str(row["회사명"]).strip()
        records.append(
            {
                "name_ko": name,
                "name_en": "",
                "code": code,
                "ticker": f"{code}.{suffix}",
                "market": market,
            }
        )
    return records


def us_records() -> list[dict]:
    return [
        {"name_ko": "", "name_en": name, "code": "", "ticker": ticker, "market": "US"}
        for name, ticker in US_SEED
    ]


def main() -> None:
    print("Fetching KRX listings from KIND ...")
    try:
        krx = fetch_krx()
    except Exception as e:  # noqa: BLE001
        print(f"ERROR fetching KRX list: {e}", file=sys.stderr)
        sys.exit(1)

    records = krx + us_records()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=0), encoding="utf-8")

    print(f"Wrote {len(records)} tickers ({len(krx)} KRX + {len(us_records())} US) -> {OUT}")
    # Spot check
    samsung = [r for r in records if r["name_ko"] == "삼성전자"]
    if samsung:
        print(f"  spot-check: 삼성전자 -> {samsung[0]['ticker']}")


if __name__ == "__main__":
    main()
