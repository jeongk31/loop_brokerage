"""Settings — admin only: rename users, regenerate login codes, manage platforms."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..auth import gen_code, hash_code
from ..auth import admin_required
from ..services import repo

bp = Blueprint("settings", __name__)


@bp.route("/settings")
@admin_required
def index():
    from ..db import get_client
    rows = get_client().table("cash_balances").select("user_id, currency, amount").execute().data or []
    cash: dict = {}
    for r in rows:
        cash.setdefault(r["user_id"], {})[r["currency"]] = float(r["amount"])
    return render_template("settings.html", users=repo.list_users(),
                           platforms=repo.list_platforms(), cash=cash)


@bp.route("/settings/cash/<user_id>", methods=["POST"])
@admin_required
def set_cash(user_id):
    from ..db import get_client
    c = get_client()
    for ccy in ("KRW", "USD"):
        amt = (request.form.get(ccy) or "").strip()
        c.table("cash_balances").upsert(
            {"user_id": user_id, "currency": ccy, "amount": float(amt) if amt else 0}
        ).execute()
    flash("현금 잔액을 저장했습니다.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/settings/users/<user_id>/rename", methods=["POST"])
@admin_required
def rename_user(user_id):
    name = request.form.get("display_name", "").strip()
    if name:
        repo.update_user(user_id, {"display_name": name})
        flash("이름을 변경했습니다.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/settings/users/<user_id>/regenerate", methods=["POST"])
@admin_required
def regenerate_code(user_id):
    code = gen_code()
    repo.update_user(user_id, {"code_hash": hash_code(code)})
    flash(f"새 로그인 코드: {code} — 지금 저장하세요 (다시 표시되지 않습니다).", "success")
    return redirect(url_for("settings.index"))


@bp.route("/settings/platforms/new", methods=["POST"])
@admin_required
def new_platform():
    name = request.form.get("name", "").strip()
    if name:
        repo.create_platform(name)
        flash("증권사를 추가했습니다.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/settings/platforms/<platform_id>/rename", methods=["POST"])
@admin_required
def rename_platform(platform_id):
    name = request.form.get("name", "").strip()
    if name:
        repo.rename_platform(platform_id, name)
        flash("증권사 이름을 변경했습니다.", "success")
    return redirect(url_for("settings.index"))
