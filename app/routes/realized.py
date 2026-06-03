"""Realized gains/losses (from sells, average-cost, split-adjusted)."""
from flask import Blueprint, render_template

from ..auth import current_user, login_required, view_scope
from ..services import portfolio, prices, repo

bp = Blueprint("realized", __name__)


@bp.route("/realized")
@login_required
def index():
    user = current_user()
    txs = repo.list_transactions(user, view_scope())
    cache = prices.get_cached()
    fx = float(cache.get(prices.FX_KEY, {}).get("price") or 0) or None
    r = portfolio.realized_pl(txs, fx)
    return render_template("realized.html", realized=r)
