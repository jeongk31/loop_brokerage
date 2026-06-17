"""가족 — manage each family member's portfolio (admin only).

Lists every non-admin member with their holdings + cash, and lets the admin buy
or sell on their behalf. A trade is recorded as a transaction (so holdings
re-derive correctly) AND settled in cash: a sell adds proceeds to the member's
cash, a buy subtracts the cost.
"""
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..auth import admin_required, current_user
from ..services import holdings, portfolio, repo

bp = Blueprint("family", __name__)


def _num(v) -> float:
    return float(str(v or 0).replace(",", "").strip() or 0)   # tolerate 1,234,567


@bp.route("/family")
@admin_required
def index():
    # Display order: 엄마, 이정한, 이지안 (then any others).
    order = ["엄마", "이정한", "이지안"]
    rank = {name: i for i, name in enumerate(order)}
    members = sorted(
        (u for u in repo.list_users() if u["role"] != "admin"),
        key=lambda u: rank.get(u["display_name"], len(order)),
    )
    enriched, summ = portfolio.load_view(repo.list_holdings(current_user(), "all"))
    fx = summ["fx"]

    by_owner_id: dict = {}
    for h in enriched:
        by_owner_id.setdefault(h["user_id"], []).append(h)

    cards, lots = [], []
    for u in members:
        hs = by_owner_id.get(u["id"], [])
        cash = portfolio.load_cash([u["id"]], fx)
        val = sum(h["value_krw"] or 0 for h in hs)
        # Collapse to one row per ticker; keep the per-증권사 lots for the sell modal.
        agg = {}
        for h in hs:
            a = agg.get(h["ticker"])
            if not a:
                a = agg[h["ticker"]] = {"ticker": h["ticker"], "name": h["name"],
                                        "ccy": h["currency"], "cur": h.get("current_price"),
                                        "quantity": 0.0, "value_krw": 0.0}
            a["quantity"] += float(h["quantity"])
            a["value_krw"] += h["value_krw"] or 0
            lots.append({"user_id": u["id"], "ticker": h["ticker"], "name": h["name"],
                         "platform_id": h.get("platform_id"),
                         "plat": (h.get("platforms") or {}).get("name", "기타"),
                         "qty": float(h["quantity"]), "ccy": h["currency"],
                         "price": h.get("current_price")})
        cards.append({"id": u["id"], "name": u["display_name"],
                      "holdings": sorted(agg.values(), key=lambda x: -x["value_krw"]),
                      "cash": cash, "value_krw": val, "total": val + cash["total_krw"]})

    return render_template(
        "family.html",
        cards=cards,
        lots=lots,
        members=members,
        platforms=repo.list_platforms(),
        today=date.today().isoformat(),
    )


@bp.route("/family/trade", methods=["POST"])
@admin_required
def trade():
    side = request.form["side"]                       # 'buy' | 'sell'
    user_id = request.form["user_id"]
    currency = request.form.get("currency") or "KRW"
    qty = _num(request.form.get("quantity"))
    price = _num(request.form.get("price"))
    fee = _num(request.form.get("fee"))

    if qty <= 0 or price <= 0:
        flash("수량과 단가를 입력해 주세요.", "error")
        return redirect(url_for("family.index"))

    repo.create_transaction({
        "user_id": user_id,
        "platform_id": request.form.get("platform_id") or None,
        "ticker": request.form["ticker"].strip(),
        "name": request.form["name"].strip(),
        "side": side,
        "trade_date": request.form.get("trade_date") or date.today().isoformat(),
        "quantity": qty,
        "price": price,
        "fee": fee,
        "currency": currency,
        "notes": "가족 관리",
    })

    # Settle cash: sell adds proceeds, buy subtracts cost (both net of fee).
    gross = qty * price
    delta = (gross - fee) if side == "sell" else -(gross + fee)
    repo.adjust_cash(user_id, currency, delta)

    holdings.rederive()                               # keep holdings in sync
    verb = "매도" if side == "sell" else "매수"
    flash(f"{verb} 완료: {request.form['name'].strip()} {qty:g}주.", "success")
    return redirect(url_for("family.index"))
