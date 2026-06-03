"""Login / logout routes."""
from flask import Blueprint, redirect, render_template, request, session, url_for

from ..auth import login_user, logout_user, verify_code

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard.index"))

    error = None
    if request.method == "POST":
        code = request.form.get("code", "")
        user = verify_code(code)
        if user:
            login_user(user)
            return redirect(url_for("dashboard.index"))
        error = "로그인 코드가 올바르지 않습니다."  # Invalid login code.

    return render_template("login.html", error=error)


@bp.route("/healthz")
def healthz():
    """Diagnostic: shows what config the container sees (no secret values)."""
    from ..config import Config
    url = Config.SUPABASE_URL or ""
    return {
        "supabase_url_set": bool(url),
        "supabase_url_preview": url.replace("https://", "")[:24],
        "service_key_set": bool(Config.SUPABASE_SERVICE_KEY),
        "service_key_len": len(Config.SUPABASE_SERVICE_KEY or ""),
        "secret_key_custom": Config.SECRET_KEY != "dev-insecure-change-me",
    }


@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/scope/<mode>")
def set_scope(mode):
    """Admin view scope: 'all' (whole family) or 'mine' (이정규 only)."""
    if session.get("role") == "admin" and mode in ("all", "mine"):
        session["scope"] = mode
    return redirect(request.referrer or url_for("dashboard.index"))
