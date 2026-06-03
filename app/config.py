"""Environment-driven configuration. Loads .env via python-dotenv."""
import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")

    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

    # Session expiry
    PERMANENT_SESSION_LIFETIME = timedelta(
        days=int(os.environ.get("SESSION_DAYS", "7"))
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Set True automatically when served over HTTPS (Railway sets this header).
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"

    @staticmethod
    def supabase_configured() -> bool:
        return bool(Config.SUPABASE_URL and Config.SUPABASE_SERVICE_KEY)
