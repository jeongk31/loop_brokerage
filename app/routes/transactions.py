"""Transactions: scoped list for everyone; add/edit/delete for admin only."""
from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from ..auth import admin_required, current_user, login_required, view_scope
from ..services import holdings, repo

bp = Blueprint("transactions", __name__)


def _num(v) -> float:
    return float(str(v or 0).replace(",", "").strip() or 0)   # tolerate 1,234,567


def _form_to_tx() -> dict:
    return {
        "user_id": request.form["user_id"],
        "platform_id": request.form.get("platform_id") or None,
        "ticker": request.form["ticker"].strip(),
        "name": request.form["name"].strip(),
        "side": request.form["side"],
        "trade_date": request.form["trade_date"],
        "quantity": _num(request.form.get("quantity")),
        "price": _num(request.form.get("price")),
        "fee": _num(request.form.get("fee")),
        "currency": request.form.get("currency") or "KRW",
        "notes": request.form.get("notes") or None,
    }


def _settles_cash(tx: dict) -> bool:
    """Whether this transaction moves the member's cash.

    True for non-admin family members, mirroring the 가족 page 매수/매도 modal,
    EXCEPT historical reconstruction entries (notes starting with '가족(실거래'),
    whose cash is managed separately by the import scripts. Admin (이정규) trades
    are intentionally left cash-free.
    """
    user = repo.get_user(tx["user_id"])
    if not user or user["role"] == "admin":
        return False
    return not (tx.get("notes") or "").startswith("가족(실거래")


def _cash_args(tx: dict) -> tuple:
    return (tx["user_id"], tx["side"], float(tx["quantity"]),
            float(tx["price"]), float(tx["fee"]), tx["currency"])


def _is_family_sell(tx: dict) -> bool:
    """A 매도 for a non-admin member — only allowed via the 가족 tab, not here."""
    if tx["side"] != "sell":
        return False
    user = repo.get_user(tx["user_id"])
    return bool(user and user["role"] != "admin")


@bp.route("/transactions")
@login_required
def list_view():
    from datetime import date
    from ..auth import is_admin
    user = current_user()
    return render_template(
        "transactions.html",
        transactions=repo.list_transactions(user, view_scope()),
        users=repo.list_users() if is_admin() else [],
        platforms=repo.list_platforms(),
        today=date.today().isoformat(),
    )


@bp.route("/transactions/new", methods=["GET", "POST"])
@admin_required
def new():
    if request.method == "POST":
        tx = _form_to_tx()
        if _is_family_sell(tx):
            flash("가족 구성원의 매도는 '가족' 탭에서만 가능합니다.", "error")
            return redirect(url_for("transactions.list_view"))
        repo.create_transaction(tx)
        if _settles_cash(tx):                     # deduct/add cash for family members
            repo.settle_trade_cash(*_cash_args(tx))
        holdings.rederive()                       # keep holdings in sync
        flash("거래를 추가했습니다.", "success")
        return redirect(url_for("transactions.list_view"))
    return render_template(
        "add_transaction.html",
        tx=None,
        users=repo.list_users(),
        platforms=repo.list_platforms(),
    )


@bp.route("/transactions/<tx_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(tx_id):
    user = current_user()
    tx = repo.get_transaction(tx_id, user)
    if not tx:
        abort(404)
    if request.method == "POST":
        new_tx = _form_to_tx()
        if _is_family_sell(new_tx):
            flash("가족 구성원의 매도는 '가족' 탭에서만 가능합니다.", "error")
            return redirect(url_for("transactions.list_view"))
        if _settles_cash(tx):                     # undo the old trade's cash effect
            repo.reverse_trade_cash(*_cash_args(tx))
        repo.update_transaction(tx_id, new_tx)
        if _settles_cash(new_tx):                 # apply the edited trade's cash effect
            repo.settle_trade_cash(*_cash_args(new_tx))
        holdings.rederive()
        flash("거래를 수정했습니다.", "success")
        return redirect(url_for("transactions.list_view"))
    return render_template(
        "add_transaction.html",
        tx=tx,
        users=repo.list_users(),
        platforms=repo.list_platforms(),
    )


@bp.route("/transactions/<tx_id>/delete", methods=["POST"])
@admin_required
def delete(tx_id):
    tx = repo.get_transaction(tx_id, current_user())
    if tx and _settles_cash(tx):                  # refund the deleted trade's cash
        repo.reverse_trade_cash(*_cash_args(tx))
    repo.delete_transaction(tx_id)
    holdings.rederive()
    flash("거래를 삭제했습니다.", "success")
    return redirect(url_for("transactions.list_view"))
