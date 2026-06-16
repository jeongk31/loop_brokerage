"""Supabase query helpers with server-side access scoping.

The golden rule: a viewer may only ever see rows they own OR rows flagged
is_family_shared. Scoping is applied in the query (and re-checked on single-row
fetches), never in the template — so changing a URL id can't leak another
user's data.
"""
from typing import Optional

from ..db import get_client

# --- platforms --------------------------------------------------------------

def list_platforms() -> list[dict]:
    c = get_client()
    return c.table("platforms").select("*").order("name").execute().data or []


def create_platform(name: str) -> None:
    get_client().table("platforms").insert({"name": name.strip()}).execute()


def rename_platform(platform_id: str, name: str) -> None:
    get_client().table("platforms").update({"name": name.strip()}).eq("id", platform_id).execute()


def update_user(user_id: str, data: dict) -> None:
    get_client().table("users").update(data).eq("id", user_id).execute()


# --- users (admin selectors) ------------------------------------------------

def list_users() -> list[dict]:
    c = get_client()
    return (
        c.table("users").select("id, display_name, role").order("created_at").execute().data
        or []
    )


# --- holdings ---------------------------------------------------------------

_HOLDING_SELECT = "*, platforms(name), users(display_name)"


def list_holdings(user: dict, scope: str = "all") -> list[dict]:
    c = get_client()
    q = c.table("holdings").select(_HOLDING_SELECT)
    if user["role"] != "admin":
        q = q.or_(f"user_id.eq.{user['id']},is_family_shared.eq.true")
    elif scope == "mine":
        q = q.eq("user_id", user["id"])
    return q.order("created_at", desc=True).execute().data or []


def get_holding(holding_id: str, user: dict) -> Optional[dict]:
    c = get_client()
    rows = (
        c.table("holdings").select(_HOLDING_SELECT).eq("id", holding_id).execute().data
    )
    if not rows:
        return None
    h = rows[0]
    if user["role"] == "admin":
        return h
    if h["user_id"] == user["id"] or h.get("is_family_shared"):
        return h
    return None  # viewer asking for someone else's private holding -> not found


def create_holding(data: dict) -> None:
    get_client().table("holdings").insert(data).execute()


def update_holding(holding_id: str, data: dict) -> None:
    get_client().table("holdings").update(data).eq("id", holding_id).execute()


def delete_holding(holding_id: str) -> None:
    get_client().table("holdings").delete().eq("id", holding_id).execute()


# --- transactions -----------------------------------------------------------

_TX_SELECT = "*, platforms(name), users(display_name)"


def list_transactions(user: dict, scope: str = "all") -> list[dict]:
    c = get_client()
    q = c.table("transactions").select(_TX_SELECT)
    if user["role"] != "admin":
        # Transactions are private — viewers only ever see their own.
        q = q.eq("user_id", user["id"])
    elif scope == "mine":
        q = q.eq("user_id", user["id"])
    return q.order("trade_date", desc=True).execute().data or []


def get_transaction(tx_id: str, user: dict) -> Optional[dict]:
    c = get_client()
    rows = c.table("transactions").select(_TX_SELECT).eq("id", tx_id).execute().data
    if not rows:
        return None
    tx = rows[0]
    if user["role"] == "admin" or tx["user_id"] == user["id"]:
        return tx
    return None


def create_transaction(data: dict) -> None:
    get_client().table("transactions").insert(data).execute()


def update_transaction(tx_id: str, data: dict) -> None:
    get_client().table("transactions").update(data).eq("id", tx_id).execute()


def delete_transaction(tx_id: str) -> None:
    get_client().table("transactions").delete().eq("id", tx_id).execute()


# --- cash balances ----------------------------------------------------------

def get_cash_amount(user_id: str, currency: str) -> float:
    rows = (get_client().table("cash_balances").select("amount")
            .eq("user_id", user_id).eq("currency", currency).execute().data or [])
    return float(rows[0]["amount"]) if rows else 0.0


def adjust_cash(user_id: str, currency: str, delta: float) -> None:
    """Add `delta` (may be negative) to a member's cash for `currency`."""
    new_amount = get_cash_amount(user_id, currency) + delta
    get_client().table("cash_balances").upsert(
        {"user_id": user_id, "currency": currency, "amount": round(new_amount, 2)}
    ).execute()
