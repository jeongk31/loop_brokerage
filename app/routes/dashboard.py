"""Role-aware dashboard with live valuation (current value, P/L, return %)."""
from flask import Blueprint, render_template

from collections import defaultdict

from ..auth import current_user, is_admin, login_required, view_scope
from ..services import portfolio, repo

bp = Blueprint("dashboard", __name__)


def _combine_by_ticker(holdings):
    """Combine a member's holdings by ticker (one row per stock, not per 증권사)."""
    agg = {}
    for h in holdings:
        a = agg.get(h["ticker"])
        if not a:
            a = agg[h["ticker"]] = {"name": h["name"], "ticker": h["ticker"],
                                    "quantity": 0.0, "value_krw": 0.0, "cost_krw": 0.0}
        a["quantity"] += float(h["quantity"])
        a["value_krw"] += h["value_krw"] or 0
        a["cost_krw"] += h.get("cost_krw") or 0
    for a in agg.values():
        cost = a["cost_krw"]
        a["return_pct"] = ((a["value_krw"] - cost) / cost * 100) if cost else None
    return sorted(agg.values(), key=lambda x: -x["value_krw"])


def _alloc_by_ticker(enriched, top=9):
    """[(name, value_krw)] grouped by ticker, top N + 기타."""
    agg, names = defaultdict(float), {}
    for h in enriched:
        if h["value_krw"]:
            agg[h["ticker"]] += h["value_krw"]
            names[h["ticker"]] = h["name"]
    rows = sorted(((names[t], v) for t, v in agg.items()), key=lambda x: -x[1])
    if len(rows) > top:
        rows = rows[:top] + [("기타", sum(v for _, v in rows[top:]))]
    return rows


@bp.route("/")
@login_required
def index():
    user = current_user()
    scope = view_scope()
    holdings = repo.list_holdings(user, scope)
    transactions = repo.list_transactions(user, scope)

    enriched, summ = portfolio.load_view(holdings)
    realized = portfolio.realized_pl(transactions, summ["fx"])

    # Cash for the in-scope users (이정규 has none; family does).
    if user["role"] == "admin":
        scoped_ids = [u["id"] for u in repo.list_users()] if scope == "all" else [user["id"]]
    else:
        scoped_ids = [user["id"]]
    cash = portfolio.load_cash(scoped_ids, summ["fx"])
    total_assets = summ["total_value_krw"] + cash["total_krw"]

    # 가족 overview (admin only): every other member's holdings + cash, regardless of scope.
    family_overview = []
    if user["role"] == "admin":
        all_en, _ = portfolio.load_view(repo.list_holdings(user, "all"))
        by_owner: dict = {}
        for h in all_en:
            by_owner.setdefault((h.get("users") or {}).get("display_name"), []).append(h)
        for u in repo.list_users():
            if u["role"] == "admin":
                continue
            hs = by_owner.get(u["display_name"], [])
            val = sum(h["value_krw"] or 0 for h in hs)
            ucash = portfolio.load_cash([u["id"]], summ["fx"])
            family_overview.append({"name": u["display_name"],
                                    "holdings": _combine_by_ticker(hs),
                                    "value_krw": val, "cash": ucash,
                                    "total": val + ucash["total_krw"]})

    owners, plats_present, holdings_js = [], [], []
    for h in enriched:
        o = (h.get("users") or {}).get("display_name", "?")
        p = (h.get("platforms") or {}).get("name", "기타")
        if o not in owners:
            owners.append(o)
        if p not in plats_present:
            plats_present.append(p)
        holdings_js.append({
            "id": h.get("id"), "owner": o, "plat": p,
            "ticker": h["ticker"], "name": h["name"],
            "qty": float(h["quantity"]), "avg": float(h["avg_cost"]),
            "cur": h.get("current_price"), "ccy": h["currency"],
            "value": h.get("value"), "value_krw": h.get("value_krw") or 0,
            "cost": h.get("cost_basis") or 0, "pl": h.get("pl"),
            "ret": h.get("return_pct"),
        })

    # Loans + net worth + value-over-time are admin-only (whole-family / private).
    if is_admin():
        hist_dates, hist_values = portfolio.history_series()       # family total (precomputed)
    else:
        hist_dates, hist_values = portfolio.user_history(enriched, cash["total_krw"], summ["fx"])

    alloc_market = [(("국내" if c == "KRW" else "해외(USD)"), v)
                    for c, v in summ["by_currency"]]

    # Include cash as a slice so 자산 배분 reflects total assets.
    alloc_platform = list(summ["by_platform"])
    alloc_ticker = _alloc_by_ticker(enriched)
    if cash["total_krw"] > 0:
        alloc_platform.append(("현금", cash["total_krw"]))
        alloc_ticker.append(("현금", cash["total_krw"]))
        alloc_market.append(("현금", cash["total_krw"]))

    return render_template(
        "dashboard.html",
        summary=summ,
        family_overview=family_overview,
        holdings_js=holdings_js,
        owners=owners,
        plats_present=plats_present,
        cash=cash,
        total_assets=total_assets,
        recent_tx=transactions[:6],
        holding_count=len(holdings),
        tx_count=len(transactions),
        realized=realized,
        hist_dates=hist_dates,
        hist_values=hist_values,
        alloc_platform=alloc_platform,
        alloc_ticker=alloc_ticker,
        alloc_market=alloc_market,
    )
