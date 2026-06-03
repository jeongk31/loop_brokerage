"""Shared stock-split helpers (used for holdings, realized P/L, history)."""
from ..db import get_client


def load_splits() -> dict:
    """ticker -> [(ex_date, ratio), ...] from the stock_splits table."""
    splits: dict = {}
    for r in (get_client().table("stock_splits").select("ticker, ex_date, ratio").execute().data or []):
        splits.setdefault(r["ticker"], []).append((r["ex_date"], float(r["ratio"])))
    return splits


def split_adjust(trades: list[dict], splits: dict) -> list[dict]:
    """Restate pre-split quantities/prices into current (post-split) terms."""
    out = []
    for t in trades:
        qty, price = float(t["quantity"]), float(t["price"])
        for ex_date, ratio in splits.get(t["ticker"], ()):
            if t["trade_date"] < ex_date:
                qty *= ratio
                price /= ratio
        out.append({**t, "_qty": qty, "_price": price})
    return out
