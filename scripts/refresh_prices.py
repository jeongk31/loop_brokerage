"""Refresh price_cache for every ticker currently held + the USD/KRW rate.

Run on demand, and (later) from the Railway daily cron alongside refresh_splits
and derive_holdings.

Run:  python scripts/refresh_prices.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_client  # noqa: E402
from app.services import prices  # noqa: E402


def main() -> None:
    client = get_client()
    tickers = sorted({h["ticker"] for h in
                      (client.table("holdings").select("ticker").execute().data or [])})
    print(f"Refreshing prices for {len(tickers)} held tickers …")
    stats = prices.refresh(tickers)
    print(f"  ok: {len(stats['ok'])}, failed: {len(stats['failed'])}")
    if stats["failed"]:
        print(f"  failed: {', '.join(stats['failed'])}")
    print(f"  USD/KRW: {stats['fx']}")


if __name__ == "__main__":
    main()
