"""Current prices + FX, cached in the `price_cache` table.

Source: Naver Finance (reliable for both Korean and US tickers; no rate limits,
unlike yfinance which is blocked in some environments). Korean tickers use the
6-digit code; US tickers probe Naver's exchange suffixes (.O NASDAQ, .K NYSE,
.A AMEX). USD/KRW comes from the ECB (Frankfurter).

The app READS from price_cache (fast); scripts/refresh_prices.py (and the future
Railway cron) WRITE to it. Prices are stored in each ticker's native currency.
"""
import json
import re
from datetime import date, datetime, timedelta
from functools import lru_cache

import requests

from ..db import get_client

FX_KEY = "USDKRW"          # special row in price_cache for the FX rate
# Naver world-stock codes: .O NASDAQ, .K NYSE, .A AMEX; some ETFs use the bare symbol.
US_SUFFIXES = ("O", "K", "A", "")
TIMEOUT = 15


def native_currency(ticker: str) -> str:
    return "KRW" if ticker.endswith((".KS", ".KQ", ".KN")) else "USD"


# --- fetchers ---------------------------------------------------------------

def _fetch_kr(ticker: str):
    code = ticker.split(".")[0]
    end = date.today().strftime("%Y%m%d")
    start = (date.today() - timedelta(days=12)).strftime("%Y%m%d")
    url = (f"https://api.finance.naver.com/siseJson.naver?symbol={code}"
           f"&requestType=1&startTime={start}&endTime={end}&timeframe=day")
    txt = requests.get(url, timeout=TIMEOUT).text.replace("'", '"')
    rows = json.loads(re.sub(r",\s*]", "]", txt.strip()))
    data = [r for r in rows[1:] if isinstance(r, list) and len(r) >= 5]
    if not data:
        return None
    last = data[-1]
    return float(last[4]), f"{last[0][:4]}-{last[0][4:6]}-{last[0][6:8]}"


def _fetch_us(ticker: str):
    for sfx in US_SUFFIXES:
        symbol = f"{ticker}.{sfx}" if sfx else ticker
        try:
            d = requests.get(f"https://api.stock.naver.com/stock/{symbol}/basic",
                             timeout=TIMEOUT).json()
            px = d.get("closePrice")
            if px:
                px = float(str(px).replace(",", ""))
                asof = (d.get("localTradedAt") or "")[:10] or date.today().isoformat()
                return px, asof
        except Exception:  # noqa: BLE001
            continue
    return None


def fetch_price(ticker: str):
    """(price, as_of) in native currency, or None."""
    try:
        return _fetch_kr(ticker) if native_currency(ticker) == "KRW" else _fetch_us(ticker)
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=256)
def history(ticker: str, days: int = 365) -> list[dict]:
    """Daily [{date, close}] for the last `days`, native currency, via Naver (cached)."""
    end = date.today()
    start = end - timedelta(days=days)
    if native_currency(ticker) == "KRW":
        code = ticker.split(".")[0]
        url = (f"https://api.finance.naver.com/siseJson.naver?symbol={code}"
               f"&requestType=1&startTime={start:%Y%m%d}&endTime={end:%Y%m%d}&timeframe=day")
        try:
            txt = requests.get(url, timeout=TIMEOUT).text.replace("'", '"')
            rows = json.loads(re.sub(r",\s*]", "]", txt.strip()))
            return [{"date": f"{r[0][:4]}-{r[0][4:6]}-{r[0][6:8]}", "close": float(r[4])}
                    for r in rows[1:] if isinstance(r, list) and len(r) >= 5]
        except Exception:  # noqa: BLE001
            return []
    # US: probe Naver world-stock chart suffixes.
    for sfx in US_SUFFIXES:
        symbol = f"{ticker}.{sfx}" if sfx else ticker
        try:
            url = (f"https://api.stock.naver.com/chart/foreign/item/{symbol}/day"
                   f"?startDateTime={start:%Y%m%d}&endDateTime={end:%Y%m%d}")
            data = requests.get(url, timeout=TIMEOUT).json()
            if data:
                return [{"date": f"{d['localDate'][:4]}-{d['localDate'][4:6]}-{d['localDate'][6:8]}",
                         "close": float(d["closePrice"])} for d in data]
        except Exception:  # noqa: BLE001
            continue
    return []


def fetch_fx_usdkrw():
    try:
        d = requests.get("https://api.frankfurter.dev/v1/latest?base=USD&symbols=KRW",
                         timeout=TIMEOUT).json()
        return float(d["rates"]["KRW"]), d.get("date", date.today().isoformat())
    except Exception:  # noqa: BLE001
        return None


# --- cache read/write -------------------------------------------------------

def get_cached() -> dict:
    """ticker -> {price, as_of} from price_cache (includes FX under 'USDKRW')."""
    rows = get_client().table("price_cache").select("ticker, price, as_of, fetched_at").execute().data or []
    return {r["ticker"]: r for r in rows}


def upsert_price(ticker: str, price: float, as_of: str) -> None:
    get_client().table("price_cache").upsert({
        "ticker": ticker, "price": price, "as_of": as_of,
        "fetched_at": datetime.utcnow().isoformat(),
    }).execute()


def refresh(tickers: list[str]) -> dict:
    """Fetch + cache prices for the given tickers and the FX rate. Returns stats."""
    ok, failed = [], []
    for t in sorted(set(tickers)):
        res = fetch_price(t)
        if res:
            upsert_price(t, res[0], res[1])
            ok.append(t)
        else:
            failed.append(t)
    fx = fetch_fx_usdkrw()
    if fx:
        upsert_price(FX_KEY, fx[0], fx[1])
    return {"ok": ok, "failed": failed, "fx": fx[0] if fx else None}
