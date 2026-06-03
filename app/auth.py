"""Login-code authentication + role-based access control.

Login codes are never stored in raw form — only a salted Werkzeug hash. Because
salted hashes can't be looked up by value, login iterates all users (there are
only ~4) and verifies with check_password_hash.
"""
import secrets
from functools import wraps
from typing import Optional

from flask import abort, redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_client

# Unambiguous alphabet (no 0/O, 1/I/l) for login codes.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def gen_code(n: int = 8) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(n))


def hash_code(code: str) -> str:
    """Hash a login code for storage. Used by seed_users.py and Settings."""
    return generate_password_hash(code.strip())


def verify_code(code: str) -> Optional[dict]:
    """Return the matching user dict if the code is valid, else None."""
    code = (code or "").strip()
    if not code:
        return None
    client = get_client()
    resp = client.table("users").select("id, display_name, role, code_hash").execute()
    for user in resp.data or []:
        if check_password_hash(user["code_hash"], code):
            return user
    return None


def login_user(user: dict) -> None:
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    session["display_name"] = user["display_name"]
    session.permanent = True


def logout_user() -> None:
    session.clear()


def current_user() -> Optional[dict]:
    """Lightweight current-user view straight from the session (no DB hit)."""
    if "user_id" not in session:
        return None
    return {
        "id": session["user_id"],
        "role": session.get("role"),
        "display_name": session.get("display_name"),
    }


def is_admin() -> bool:
    return session.get("role") == "admin"


def view_scope() -> str:
    """'all' (everyone — admin only) or 'mine' (own data). Viewers are always 'mine'."""
    if not is_admin():
        return "mine"
    return session.get("scope", "all")


# --- decorators -------------------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        if session.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped
