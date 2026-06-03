"""Daily maintenance — run by the Railway cron.

Idempotent pipeline that keeps everything current:
  1. refresh_splits      — pull new stock splits (yfinance)
  2. derive_holdings     — re-derive holdings (splits change share counts) + transfers
  3. refresh_prices      — update price_cache for held tickers + USD/KRW
  4. build_portfolio_history — append today's snapshot to the value-over-time series

Run:  python scripts/daily_update.py
"""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

STEPS = ["refresh_splits", "derive_holdings", "refresh_prices", "build_portfolio_history"]


def main() -> None:
    here = Path(__file__).resolve().parent
    for step in STEPS:
        print(f"\n=== {step} ===", flush=True)
        try:
            runpy.run_path(str(here / f"{step}.py"), run_name="__main__")
        except SystemExit:
            pass
        except Exception as e:  # noqa: BLE001 — keep going so one failure doesn't block the rest
            print(f"  ! {step} failed: {e!r}", file=sys.stderr)
    print("\nDaily update complete.")


if __name__ == "__main__":
    main()
