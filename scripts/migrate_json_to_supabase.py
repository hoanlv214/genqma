import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storage import SupabaseStorage  # noqa: E402


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_json(path: Path, fallback):
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    return data if isinstance(data, type(fallback)) else fallback


def main() -> int:
    load_env_file(ROOT / ".env")
    supabase_url = os.getenv("SUPABASE_URL") or os.getenv("QMA_SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("QMA_SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        print("Missing SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        return 1

    storage = SupabaseStorage(
        url=supabase_url,
        service_role_key=service_key,
        schema=os.getenv("SUPABASE_SCHEMA", "public"),
    )

    payment_events = load_json(ROOT / "payment_ledger.json", [])
    paid_reports = load_json(ROOT / "paid_reports.json", {})
    invoices = load_json(ROOT / "invoices.json", {})

    print(f"Uploading {len(payment_events)} payment events...")
    storage.save_payment_events(payment_events)
    print(f"Uploading {len(paid_reports)} paid report entitlements...")
    storage.save_paid_reports(paid_reports)
    print(f"Uploading {len(invoices)} invoices...")
    for invoice in invoices.values():
        if isinstance(invoice, dict):
            storage.save_invoice(invoice)

    print("Supabase migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
