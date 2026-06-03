"""Supabase client singleton.

Uses the service-role key, so it bypasses RLS. ALL access control is enforced
in application code (see app/auth.py and app/services/repo.py). Keep the
service key on the server only — never expose it to templates or the client.
"""
from functools import lru_cache

from supabase import Client, create_client

from .config import Config


@lru_cache(maxsize=1)
def get_client() -> Client:
    if not Config.supabase_configured():
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_KEY in your .env file."
        )
    return create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_KEY)
