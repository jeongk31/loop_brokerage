"""Holdings: scoped list for everyone; create/edit/delete for admin only."""
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
from ..services import portfolio, repo

bp = Blueprint("holdings", __name__)


def _form_to_holding() -> dict:
    return {
        "user_id": request.form["user_id"],
        "platform_id": request.form.get("platform_id") or None,
        "ticker": request.form["ticker"].strip(),
        "name": request.form["name"].strip(),
        "quantity": float(request.form.get("quantity") or 0),
        "avg_cost": float(request.form.get("avg_cost") or 0),
        "is_family_shared": request.form.get("is_family_shared") == "on",
    }


@bp.route("/holdings")
@login_required
def list_view():
    # Holdings are now listed on the dashboard; keep this route as a redirect.
    return redirect(url_for("dashboard.index"))


@bp.route("/prices/refresh", methods=["POST"])
@admin_required
def refresh_prices():
    from ..services import prices
    tickers = [h["ticker"] for h in repo.list_holdings(current_user(), view_scope())]
    stats = prices.refresh(tickers)
    flash(f"시세 업데이트 완료 ({len(stats['ok'])}종목). USD/KRW {stats['fx']}", "success")
    return redirect(url_for("dashboard.index"))


@bp.route("/holdings/new", methods=["GET", "POST"])
@admin_required
def new():
    if request.method == "POST":
        repo.create_holding(_form_to_holding())
        flash("보유 종목을 추가했습니다.", "success")
        return redirect(url_for("dashboard.index"))
    return render_template(
        "holding_form.html",
        holding=None,
        users=repo.list_users(),
        platforms=repo.list_platforms(),
    )


@bp.route("/holdings/<holding_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(holding_id):
    user = current_user()
    holding = repo.get_holding(holding_id, user)
    if not holding:
        abort(404)
    if request.method == "POST":
        repo.update_holding(holding_id, _form_to_holding())
        flash("보유 종목을 수정했습니다.", "success")
        return redirect(url_for("dashboard.index"))
    return render_template(
        "holding_form.html",
        holding=holding,
        users=repo.list_users(),
        platforms=repo.list_platforms(),
    )


@bp.route("/holdings/<holding_id>/delete", methods=["POST"])
@admin_required
def delete(holding_id):
    repo.delete_holding(holding_id)
    flash("보유 종목을 삭제했습니다.", "success")
    return redirect(url_for("dashboard.index"))
