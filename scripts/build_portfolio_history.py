"""Reconstruct daily portfolio value (KRW) over time and store in portfolio_history.

For each calendar day from the first trade to today:
  value = sum over tickers of  (split-adjusted shares held as-of that day)
          x (that day's close, forward-filled)  x (USD/KRW that day, if USD)

Naver's historical prices are split-adjusted to current share terms, which is
consistent with our split-adjusted share counts — so qty x price = true value.

Run:  python scripts/build_portfolio_history.py
      python scripts/build_portfolio_history.py --dry-run
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_client  # noqa: E402
from app.services import prices  # noqa: E402

# reuse the split logic from derive_holdings
sys.path.insert(0, str(Path(__file__).resolve().parent))
from derive_holdings import load_splits, split_adjust  # noqa: E402

FX_RANGE_URL = "https://api.frankfurter.dev/v1/{start}..{end}?base=USD&symbols=KRW"


def fx_series(axis) -> pd.Series:
    import requests
    start, end = axis[0].date().isoformat(), axis[-1].date().isoformat()
    data = requests.get(FX_RANGE_URL.format(start=start, end=end), timeout=60).json()
    rates = {pd.Timestamp(d): v["KRW"] for d, v in data.get("rates", {}).items()}
    return pd.Series(rates).reindex(axis).ffill().bfill()


def main() -> None:
    dry = "--dry-run" in sys.argv
    client = get_client()

    txs = client.table("transactions").select(
        "platform_id, ticker, trade_date, side, quantity, price, currency").range(0, 999).execute().data or []
    # paginate (defensive; 713 < 1000 so one page, but keep robust)
    start = 1000
    while True:
        page = client.table("transactions").select(
            "platform_id, ticker, trade_date, side, quantity, price, currency").range(start, start + 999).execute().data or []
        if not page:
            break
        txs += page
        start += 1000

    splits = load_splits(client)
    txs = split_adjust(txs, splits)

    earliest = min(t["trade_date"] for t in txs)
    axis = pd.date_range(earliest, pd.Timestamp.today().normalize(), freq="D")
    fx = fx_series(axis)

    # Group per (platform, ticker) — same granularity as derive_holdings, so the
    # long-only clamp on an oversell matches and the latest day equals the live total.
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for t in txs:
        groups[(t["platform_id"], t["ticker"])].append(t)
    print(f"Reconstructing {len(axis)} days across {len(groups)} positions …")

    total = pd.Series(0.0, index=axis)
    skipped = set()
    span_days = (axis[-1] - axis[0]).days + 5
    price_cache: dict = {}
    for (pid, tk), trades in groups.items():
        changes = pd.Series(0.0, index=axis)
        for t in trades:
            d = pd.Timestamp(t["trade_date"])
            if d in changes.index:
                changes.loc[d] += float(t["quantity"]) * (1 if t["side"] == "buy" else -1)
        running, held = 0.0, []        # LONG ONLY: clamp at zero per platform+ticker
        for ch in changes.values:
            running = max(0.0, running + ch)
            held.append(running)
        qty = pd.Series(held, index=axis)
        if qty.abs().max() < 1e-9:
            continue

        if tk not in price_cache:
            hist = prices.history(tk, days=span_days)
            price_cache[tk] = (pd.Series({pd.Timestamp(p["date"]): p["close"] for p in hist})
                               .reindex(axis).ffill()) if hist else None
        close = price_cache[tk]
        if close is None:
            skipped.add(tk)
            continue

        val = qty * close
        if prices.native_currency(tk) == "USD":
            val = val * fx
        total = total.add(val.fillna(0), fill_value=0)
    skipped = sorted(skipped)

    series = [(d.date().isoformat(), round(float(v), 2)) for d, v in total.items() if abs(v) > 0]
    print(f"  {len(series)} non-zero days. latest: {series[-1] if series else None}")
    if skipped:
        print(f"  ⚠️ no price history (excluded): {', '.join(skipped)}")

    if dry:
        print("  sample (monthly):")
        for d, v in series[::30]:
            print(f"    {d}  {v:,.0f}")
        print("(dry run — nothing written)")
        return

    client.table("portfolio_history").delete().neq("snapshot_date", "1900-01-01").execute()
    rows = [{"snapshot_date": d, "value_krw": v} for d, v in series]
    for i in range(0, len(rows), 500):
        client.table("portfolio_history").upsert(rows[i:i + 500]).execute()
    print(f"Done. {len(rows)} daily snapshots written.")


if __name__ == "__main__":
    main()
