"""Import complete legacy creator claims without overwriting newer database rows."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    import json
    from backend.app.core.config import settings
    from storage import create_storage_backend, SupabaseStorage
    backend = create_storage_backend(**{key: str(getattr(settings, value)) for key, value in {
        "ledger_path": "payment_ledger_path", "reports_path": "paid_reports_path", "invoices_path": "invoices_path",
        "creators_path": "creator_applications_path", "provider_controls_path": "provider_controls_path",
    }.items()})
    if not isinstance(backend, SupabaseStorage):
        raise SystemExit("Supabase is not configured.")
    records = json.loads(settings.creator_claims_path.read_text(encoding="utf-8")) if settings.creator_claims_path.exists() else []
    existing = {row["claim_id"] for row in backend.load_creator_claims()}
    pending = [row for row in records if row["claim_id"] not in existing]
    if "--apply" not in sys.argv:
        print(f"Would import {len(pending)} claims; use --apply to execute after reviewing the source ledger.")
    else:
        for row in pending:
            backend._request("POST", "qma_creator_claims", params={"on_conflict": "claim_id"},
                json_body=[{"claim_id": row["claim_id"], "claim": row}], prefer="resolution=ignore-duplicates,return=minimal")
        print(f"Imported {len(pending)} legacy claims without overwriting existing records.")
