"""Combine all broker exports in STARTING_DATA/ into one unified transaction file.

Output: STARTING_DATA/summary.csv — one row per real stock BUY/SELL across all
platforms. Per the project rules we keep PRICES ONLY: forex, deposits, dividends,
taxes, fees, interest, cash sweeps and stock-split rows are dropped. Korean stocks
are recorded in KRW, US stocks in USD (native trading currency).

Sources:
  - 삼성증권.xlsx        full transaction history (KRW + USD)
  - IBKR.csv             transaction history (USD; net short positions are intentional)
  - 한국투자증권          two holdings entered by hand (prices below)
  - sarwa/*.pdf          monthly statements (USD) — Trade Entry rows extracted

Also writes STARTING_DATA/sarwa.csv (Sarwa rows only).

Run:  python scripts/build_summary.py
Unmapped names are reported at the end so they can be added to the maps.
"""
import csv
import glob
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SD = ROOT / "STARTING_DATA"
OUT = SD / "summary.csv"

OWNER = "이정규"  # all accounts are the admin's (이정규)

# Tickers to drop entirely (e.g. closed short experiments we no longer track).
EXCLUDE_TICKERS = {"ORCL"}

# --- name -> ticker maps ----------------------------------------------------

# 삼성증권 US names (Korean-described) -> (yahoo ticker, clean English name)
US_NAME_MAP = {
    "USD Global X 나스닥 100 커버드콜 월배당 ETF": ("QYLD", "Global X NASDAQ 100 Covered Call ETF"),
    "USD ProShares QQQ -3배 ETF": ("SQQQ", "ProShares UltraPro Short QQQ"),
    "USD ProShares QQQ 2배 ETF": ("QLD", "ProShares Ultra QQQ"),
    "USD ProShares QQQ 3배 ETF": ("TQQQ", "ProShares UltraPro QQQ"),
    "USD SPDR S&P 500 Trust ETF": ("SPY", "SPDR S&P 500 ETF Trust"),
    "USD 나이키": ("NKE", "Nike"),
    "USD 데이터도그": ("DDOG", "Datadog"),
    "USD 델타 에어라인스": ("DAL", "Delta Air Lines"),
    "USD 애플": ("AAPL", "Apple"),
    "USD 우버": ("UBER", "Uber Technologies"),
    "USD 월트 디즈니": ("DIS", "Walt Disney"),
    "USD 인텔": ("INTC", "Intel"),
    "USD 퀄컴": ("QCOM", "Qualcomm"),
    "USD 테라다인": ("TER", "Teradyne"),
    "USD 테슬라": ("TSLA", "Tesla"),
    "USD 팔란티어 테크놀로지스": ("PLTR", "Palantir Technologies"),
    "USD 페이팔 홀딩스": ("PYPL", "PayPal Holdings"),
    "USD 퓨얼셀 에너지": ("FCEL", "FuelCell Energy"),
}

# Korean names not in the KIND company listing (ETFs, preferred shares, etc.)
KR_OVERRIDE = {
    "KODEX 건설": "117700.KS",
    "KODEX 삼성그룹": "102780.KS",
    "KODEX 조선TOP10": "0115D0.KS",   # 494670 is TIGER 조선TOP10 (wrong fund)
    "삼성전자우": "005935.KS",
    "현대차": "005380.KS",     # Samsung export uses short name; KIND lists 현대자동차
    "현대차우": "005385.KS",
    "SK렌터카": "068400.KS",  # taken private in 2024; ticker kept for history
}

# 한국투자증권 holdings (entered by hand). Prices filled by build_summary
# from historical close on the trade date; see KIS_PRICES below.
KIS_HOLDINGS = [
    # (name, ticker, currency, qty, trade_date)
    ("대우건설", "047040.KS", "KRW", 1, "2022-08-02"),
    # 1 pre-split share bought 2022-10-04 → 2 shares now after the 2025-11-20 2:1 split
    ("ProShares UltraPro QQQ", "TQQQ", "USD", 1, "2022-10-04"),
]
# Historical close prices (native currency) — set by fetch step or by hand.
KIS_PRICES = {
    "047040.KS@2022-08-02": 5210,    # KRW close on 2022-08-02 (Naver Finance)
    "TQQQ@2022-10-04": 46.10,        # raw (pre-2025-split); ÷2 → $23.05/current share
}

KR_BUY = {"매수", "매수_NXT", "융자매수"}
KR_SELL = {"매도", "매도_NXT", "융자매도"}

# Friendly names for Sarwa symbols (transaction table leaves Description blank).
SARWA_NAMES = {
    "AAPL": "Apple", "AMZN": "Amazon", "BND": "Vanguard Total Bond Market ETF",
    "META": "Meta Platforms", "NVDA": "NVIDIA", "PLTR": "Palantir Technologies",
    "QLD": "ProShares Ultra QQQ", "TIP": "iShares TIPS Bond ETF",
    "TQQQ": "ProShares UltraPro QQQ", "USO": "United States Oil Fund",
}


def kr_index() -> dict:
    recs = json.loads((ROOT / "data" / "tickers.json").read_text(encoding="utf-8"))
    return {r["name_ko"]: r["ticker"] for r in recs if r.get("name_ko")}


def num(x) -> float:
    return float(str(x).replace(",", "").strip())


def parse_samsung(idx: dict, unmapped: set) -> list[dict]:
    df = pd.read_excel(SD / "삼성증권.xlsx", sheet_name="Col1", header=1)
    df = df[df["거래일자"].notna()]
    rows = []
    for _, r in df.iterrows():
        kind = str(r["거래명"]).strip()
        name = str(r["종목명"]).strip()
        is_us = kind.startswith("미국")
        if is_us:
            side = "sell" if "매도" in kind else "buy"
            mapped = US_NAME_MAP.get(name)
            if not mapped:
                unmapped.add(f"[삼성/US] {name}")
                continue
            ticker, disp = mapped
            currency = "USD"
        elif kind in KR_BUY or kind in KR_SELL:
            side = "buy" if kind in KR_BUY else "sell"
            ticker = KR_OVERRIDE.get(name) or idx.get(name)
            if not ticker:
                unmapped.add(f"[삼성/KR] {name}")
                continue
            disp = name
            currency = "KRW"
        else:
            continue  # forex / dividends / etc — skip
        rows.append(
            {
                "platform": "삼성증권",
                "owner": OWNER,
                "side": side,
                "trade_date": str(r["거래일자"])[:10],
                "ticker": ticker,
                "name": disp,
                "quantity": num(r["수량"]),
                "price": num(r["단가"]),
                "currency": currency,
            }
        )
    return rows


def parse_ibkr() -> list[dict]:
    rows = []
    with open(SD / "IBKR.csv", newline="", encoding="utf-8") as f:
        for rec in csv.reader(f):
            if len(rec) < 9 or rec[0] != "Transaction History" or rec[1] != "Data":
                continue
            # Date,Account,Description,TxType,Symbol,Qty,Price,PriceCcy,Gross,Comm,Net
            date, _acct, desc, txtype, symbol, qty, price, ccy = rec[2:10]
            if txtype not in ("Buy", "Sell") or symbol in ("-", ""):
                continue
            rows.append(
                {
                    "platform": "IBKR",
                    "owner": OWNER,
                    "side": txtype.lower(),
                    "trade_date": date,
                    "ticker": symbol,
                    "name": desc.title(),
                    "quantity": abs(num(qty)),
                    "price": num(price),
                    "currency": ccy or "USD",
                }
            )
    return rows


def parse_kis(unfilled: list) -> list[dict]:
    rows = []
    for name, ticker, ccy, qty, date in KIS_HOLDINGS:
        price = KIS_PRICES.get(f"{ticker}@{date}")
        if price is None:
            unfilled.append(f"{name} ({ticker}) @ {date}")
        rows.append(
            {
                "platform": "한국투자증권",
                "owner": OWNER,
                "side": "buy",
                "trade_date": date,
                "ticker": ticker,
                "name": name,
                "quantity": qty,
                "price": price if price is not None else "",
                "currency": ccy,
            }
        )
    return rows


def parse_sarwa() -> list[dict]:
    """Extract Trade Entry buy/sell rows from every Sarwa monthly PDF (USD).

    Each statement's Transaction table covers one month, so concatenating all
    statements gives the full trade history with no overlap. Cash sweeps, stock
    splits, dividends and interest rows are ignored.
    """
    import fitz  # PyMuPDF

    rows = []
    for path in sorted(glob.glob(str(SD / "sarwa" / "*.pdf"))):
        doc = fitz.open(path)
        for page in doc:
            for tab in page.find_tables().tables:
                for r in tab.extract():
                    if len(r) < 7:
                        continue
                    etype = (r[1] or "").replace("\n", " ").strip()
                    side = (r[2] or "").strip().lower()
                    if etype != "Trade Entry" or side not in ("buy", "sell"):
                        continue
                    sym = (r[3] or "").strip()
                    qty = abs(num((r[5] or "").replace("\n", "").replace("-", "")))
                    price = num((r[6] or "").replace("$", "").replace("\n", ""))
                    m, d, y = r[0].strip().split("/")
                    rows.append(
                        {
                            "platform": "Sarwa",
                            "owner": OWNER,
                            "side": side,
                            "trade_date": f"{y}-{m}-{d}",
                            "ticker": sym,
                            "name": SARWA_NAMES.get(sym, sym),
                            "quantity": qty,
                            "price": price,
                            "currency": "USD",
                        }
                    )
    return rows


FIELDS = ["platform", "owner", "side", "trade_date", "ticker", "name",
          "quantity", "price", "currency"]


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    idx = kr_index()
    unmapped: set = set()
    unfilled: list = []

    sarwa_rows = parse_sarwa()
    sarwa_rows.sort(key=lambda x: x["trade_date"])
    write_csv(SD / "sarwa.csv", sarwa_rows)

    rows = (parse_samsung(idx, unmapped) + parse_ibkr()
            + parse_kis(unfilled) + sarwa_rows)
    rows = [r for r in rows if r["ticker"] not in EXCLUDE_TICKERS]
    rows.sort(key=lambda x: (x["platform"], x["trade_date"]))
    write_csv(OUT, rows)

    by_plat: dict = {}
    for r in rows:
        by_plat[r["platform"]] = by_plat.get(r["platform"], 0) + 1
    print(f"Wrote {len(rows)} transactions -> {OUT}")
    for p, n in sorted(by_plat.items()):
        print(f"  {p}: {n}")
    if unmapped:
        print("\n⚠️  Unmapped names (add to maps):")
        for u in sorted(unmapped):
            print("   ", u)
    if unfilled:
        print("\n⚠️  한국투자증권 prices still TBD (fill KIS_PRICES):")
        for u in unfilled:
            print("   ", u)


if __name__ == "__main__":
    main()
