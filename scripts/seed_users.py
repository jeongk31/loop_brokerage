"""Seed the four family users with random login codes.

Run once after creating the schema:

    python scripts/seed_users.py

It prints each user's plaintext login code ONCE — save them somewhere safe.
Only the salted hash is stored in the database. Re-running skips users whose
display_name already exists (use --reset to wipe and recreate).
"""
import secrets
import string
import sys
from pathlib import Path

# Allow running as a plain script: add project root to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import hash_code  # noqa: E402
from app.db import get_client  # noqa: E402

# (display_name, role). Rename display names freely; codes are generated.
USERS = [
    ("관리자", "admin"),      # Admin
    ("어머니", "viewer"),     # Mother
    ("형제1", "viewer"),      # Sibling 1
    ("형제2", "viewer"),      # Sibling 2
]

# Unambiguous alphabet (no 0/O, 1/I/l).
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def gen_code(n: int = 8) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(n))


def main(reset: bool = False) -> None:
    client = get_client()

    existing = {
        u["display_name"]
        for u in (client.table("users").select("display_name").execute().data or [])
    }

    if reset and existing:
        # Delete all users (cascades to holdings/transactions). Be careful.
        client.table("users").delete().neq("display_name", "").execute()
        existing = set()
        print("⚠️  Reset: existing users deleted.\n")

    print("Save these login codes — they are shown only once:\n")
    print(f"{'User':<10} {'Role':<8} Login code")
    print("-" * 34)

    for display_name, role in USERS:
        if display_name in existing:
            print(f"{display_name:<10} {role:<8} (exists — skipped)")
            continue
        code = gen_code()
        client.table("users").insert(
            {"display_name": display_name, "role": role, "code_hash": hash_code(code)}
        ).execute()
        print(f"{display_name:<10} {role:<8} {code}")

    print("\nDone. Family members log in at /login with their code.")


if __name__ == "__main__":
    main(reset="--reset" in sys.argv)
