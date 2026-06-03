"""Flask application factory."""
from flask import Flask

from .config import Config


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # Make session permanent (so PERMANENT_SESSION_LIFETIME applies) on each request.
    from flask import session

    @app.before_request
    def _make_session_permanent():
        session.permanent = True

    # Jinja number formatting (None-safe).
    def _num(v, dec=0):
        if v is None:
            return "—"
        return f"{float(v):,.{dec}f}"

    def _pct(v, dec=1):
        if v is None:
            return "—"
        return f"{float(v):+,.{dec}f}%"

    def _signed(v, dec=0):
        if v is None:
            return "—"
        return f"{float(v):+,.{dec}f}"

    app.jinja_env.filters["num"] = _num
    app.jinja_env.filters["pct"] = _pct
    app.jinja_env.filters["signed"] = _signed

    # Expose current user + role to all templates.
    from .auth import current_user, view_scope

    @app.context_processor
    def _inject_user():
        user = current_user()
        return {
            "current_user": user,
            "is_admin": bool(user and user.get("role") == "admin"),
            "scope": view_scope(),
        }

    # Blueprints
    from .routes.auth_routes import bp as auth_bp
    from .routes.dashboard import bp as dashboard_bp
    from .routes.holdings import bp as holdings_bp
    from .routes.transactions import bp as transactions_bp
    from .routes.autocomplete import bp as autocomplete_bp
    from .routes.settings import bp as settings_bp
    from .routes.charts import bp as charts_bp
    from .routes.realized import bp as realized_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(holdings_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(autocomplete_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(charts_bp)
    app.register_blueprint(realized_bp)

    return app
