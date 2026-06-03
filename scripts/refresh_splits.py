"""Populate the stock_splits table.

Two layers:
  1. SEED — a handful of well-established splits for tickers in your ledger,
     inserted via the Supabase client (works anywhere). Marked source='seed'.
  2. yfinance — authoritative split history for every distinct US ticker you've
     traded. yfinance is rate-limited in the build sandbox, so run this from your
     own machine / Railway to fetch the complete set. Marked source='yfinance'.

yfinance rows upsert over seed rows for the same (ticker, ex_date).

Run:  python scripts/refresh_splits.py            # seed + yfinance
      python scripts/refresh_splits.py --seed-only # seed only (no network)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_client  # noqa: E402

# Web-researched splits (2019–2026) for every ticker in the ledger.
# ratio: forward N-for-1 -> N; reverse 1-for-N -> 1/N. Applied only to trades
# BEFORE ex_date, so entries predating a ticker's first trade are harmless.
SEED = [
    # --- US single names ---
    ("AAPL",  "2020-08-31", 4.0),
    ("AMZN",  "2022-06-06", 20.0),
    ("GOOGL", "2022-07-18", 20.0),
    ("NVDA",  "2021-07-20", 4.0),
    ("NVDA",  "2024-06-10", 10.0),
    ("TSLA",  "2020-08-31", 5.0),
    ("TSLA",  "2022-08-25", 3.0),
    ("FCEL",  "2019-05-09", 1.0 / 12),   # 1-for-12 reverse
    ("FCEL",  "2024-11-11", 1.0 / 30),   # 1-for-30 reverse
    # --- US ETFs (leveraged split frequently, both directions) ---
    ("TQQQ",  "2021-01-21", 2.0),
    ("TQQQ",  "2022-01-13", 2.0),
    ("TQQQ",  "2025-11-20", 2.0),
    ("QLD",   "2020-08-18", 2.0),
    ("QLD",   "2021-05-25", 2.0),
    ("QLD",   "2025-11-20", 2.0),
    ("SQQQ",  "2019-05-24", 0.25),       # 1-for-4
    ("SQQQ",  "2020-08-18", 0.2),        # 1-for-5
    ("SQQQ",  "2022-01-13", 0.2),
    ("SQQQ",  "2024-11-07", 0.2),
    ("SQQQ",  "2025-11-20", 0.2),
    ("USO",   "2020-04-29", 0.125),      # 1-for-8 reverse
    # --- Korean (액면분할 forward; + 무상증자 bonus issues Yahoo treats as splits) ---
    ("035720.KS", "2021-04-15", 5.0),    # 카카오 5:1 액면분할
    ("058470.KQ", "2025-04-25", 5.0),    # 리노공업 5:1 액면분할
    ("403870.KQ", "2023-03-16", 4.0),    # HPSP 300% 무상증자
    ("048410.KQ", "2025-07-24", 2.0),    # 현대바이오 1:1 무상증자
]


def is_us(ticker: str) -> bool:
    return not ticker.endswith((".KS", ".KQ", ".KN"))


def seed(client) -> None:
    rows = [{"ticker": t, "ex_date": d, "ratio": r, "source": "research"} for t, d, r in SEED]
    client.table("stock_splits").upsert(rows, on_conflict="ticker,ex_date").execute()
    print(f"Seeded {len(rows)} researched splits.")


def from_yfinance(client) -> None:
    import yfinance as yf

    tickers = sorted({
        t["ticker"]
        for t in (client.table("transactions").select("ticker").execute().data or [])
        if is_us(t["ticker"])
    })
    print(f"Fetching splits from yfinance for {len(tickers)} US tickers …")
    rows, failed = [], []
    for tk in tickers:
        try:
            s = yf.Ticker(tk).splits
            for dt, ratio in s.items():
                d = str(dt)[:10]
                if d >= "2015-01-01":
                    rows.append({"ticker": tk, "ex_date": d,
                                 "ratio": float(ratio), "source": "yfinance"})
        except Exception:  # noqa: BLE001
            failed.append(tk)
    if rows:
        client.table("stock_splits").upsert(rows, on_conflict="ticker,ex_date").execute()
    print(f"  upserted {len(rows)} splits from yfinance.")
    if failed:
        print(f"  could not fetch (rate-limited / no data): {len(failed)} tickers")
        print(f"  -> {', '.join(failed[:15])}{' …' if len(failed) > 15 else ''}")
        print("  Re-run later (or from a non-rate-limited network) to complete.")


def main() -> None:
    client = get_client()
    seed(client)
    if "--seed-only" not in sys.argv:
        from_yfinance(client)

    total = client.table("stock_splits").select("ticker", count="exact").limit(1).execute().count
    print(f"\nstock_splits now has {total} rows.")


if __name__ == "__main__":
    main()
