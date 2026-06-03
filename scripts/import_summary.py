"""Import STARTING_DATA/summary.csv into Supabase `transactions`.

- Maps each row's `owner` (display_name) to a user id.
- Creates any missing `platforms` by name and maps to platform_id.
- Inserts all rows as transactions (fee=0, per the prices-only rule).

This is a full reload of the imported platforms: it first DELETES existing
transactions for those platforms, so re-running is safe and idempotent.

Run:  python scripts/import_summary.py
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_client  # noqa: E402

CSV_PATH = Path(__file__).resolve().parent.parent / "STARTING_DATA" / "summary.csv"
CHUNK = 200


def main() -> None:
    client = get_client()

    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8-sig")))
    if not rows:
        print("summary.csv is empty — run scripts/build_summary.py first.")
        return

    # users: display_name -> id
    users = {
        u["display_name"]: u["id"]
        for u in (client.table("users").select("id, display_name").execute().data or [])
    }
    missing_owners = {r["owner"] for r in rows} - set(users)
    if missing_owners:
        print(f"ERROR: owners not found as users: {missing_owners}")
        print("Run scripts/seed_users.py first (or fix the owner names).")
        sys.exit(1)

    # platforms: name -> id (create missing)
    platforms = {
        p["name"]: p["id"]
        for p in (client.table("platforms").select("id, name").execute().data or [])
    }
    for name in sorted({r["platform"] for r in rows}):
        if name not in platforms:
            new = client.table("platforms").insert({"name": name}).execute().data[0]
            platforms[name] = new["id"]
            print(f"  created platform: {name}")

    # Full reload: delete existing transactions for these platforms.
    plat_ids = list({platforms[r["platform"]] for r in rows})
    client.table("transactions").delete().in_("platform_id", plat_ids).execute()

    # Build + insert in chunks.
    records = [
        {
            "user_id": users[r["owner"]],
            "platform_id": platforms[r["platform"]],
            "ticker": r["ticker"],
            "name": r["name"],
            "side": r["side"],
            "trade_date": r["trade_date"],
            "quantity": float(r["quantity"]),
            "price": float(r["price"]),
            "fee": 0,
            "currency": r["currency"],
        }
        for r in rows
    ]

    inserted = 0
    for i in range(0, len(records), CHUNK):
        client.table("transactions").insert(records[i:i + CHUNK]).execute()
        inserted += len(records[i:i + CHUNK])
        print(f"  inserted {inserted}/{len(records)}")

    # Summary
    by_plat: dict = {}
    for r in rows:
        by_plat[r["platform"]] = by_plat.get(r["platform"], 0) + 1
    print(f"\nDone. {inserted} transactions imported.")
    for p, n in sorted(by_plat.items()):
        print(f"  {p}: {n}")


if __name__ == "__main__":
    main()
