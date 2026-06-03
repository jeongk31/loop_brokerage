"""Ticker autocomplete API."""
from flask import Blueprint, jsonify, request

from ..auth import login_required
from ..services import tickers

bp = Blueprint("autocomplete", __name__)


@bp.route("/api/tickers/search")
@login_required
def search():
    q = request.args.get("q", "")
    return jsonify(tickers.search(q, limit=10))
