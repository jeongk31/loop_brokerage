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
from ..services import repo

bp = Blueprint("transactions", __name__)


def _form_to_tx() -> dict:
    return {
        "user_id": request.form["user_id"],
        "platform_id": request.form.get("platform_id") or None,
        "ticker": request.form["ticker"].strip(),
        "name": request.form["name"].strip(),
        "side": request.form["side"],
        "trade_date": request.form["trade_date"],
        "quantity": float(request.form.get("quantity") or 0),
        "price": float(request.form.get("price") or 0),
        "fee": float(request.form.get("fee") or 0),
        "currency": request.form.get("currency") or "KRW",
        "notes": request.form.get("notes") or None,
    }


@bp.route("/transactions")
@login_required
def list_view():
    user = current_user()
    return render_template(
        "transactions.html", transactions=repo.list_transactions(user, view_scope())
    )


@bp.route("/transactions/new", methods=["GET", "POST"])
@admin_required
def new():
    if request.method == "POST":
        repo.create_transaction(_form_to_tx())
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
        repo.update_transaction(tx_id, _form_to_tx())
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
    repo.delete_transaction(tx_id)
    flash("거래를 삭제했습니다.", "success")
    return redirect(url_for("transactions.list_view"))
