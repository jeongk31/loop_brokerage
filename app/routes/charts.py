"""Charts: allocation (platform/currency), top holdings, per-stock price history."""
from flask import Blueprint, jsonify, render_template, request

from ..auth import current_user, is_admin, login_required, view_scope
from ..services import portfolio, prices, repo

bp = Blueprint("charts", __name__)


@bp.route("/charts")
@login_required
def index():
    user = current_user()
    enriched, summ = portfolio.load_view(repo.list_holdings(user, view_scope()))
    valued = [h for h in enriched if h["value_krw"]]

    # value-over-time is the whole-family total → admin only
    hist_dates, hist_values = portfolio.history_series() if is_admin() else ([], [])
    top = sorted(valued, key=lambda h: -h["value_krw"])[:10]
    return render_template(
        "charts.html",
        hist_dates=hist_dates,
        hist_values=hist_values,
        by_platform=summ["by_platform"],
        by_currency=[(("국내" if c == "KRW" else "해외(USD)"), v) for c, v in summ["by_currency"]],
        top_labels=[f"{h['name']}" for h in top],
        top_values=[round(h["value_krw"]) for h in top],
        tickers=[{"ticker": h["ticker"], "name": h["name"]}
                 for h in sorted(valued, key=lambda h: -h["value_krw"])],
    )


@bp.route("/api/price-history")
@login_required
def price_history():
    ticker = request.args.get("ticker", "").strip()
    days = min(int(request.args.get("days", 365)), 1825)
    if not ticker:
        return jsonify({"points": []})
    pts = prices.history(ticker, days=days)
    return jsonify({"ticker": ticker, "points": pts})
