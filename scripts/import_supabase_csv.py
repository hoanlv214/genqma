"""Import Supabase CSV row exports into the local PostgreSQL database.

Context: the production backend historically ran on Supabase; the local
PostgreSQL database is now the single source of truth. This script REPLACEs
the contents of the mapped tables with the exported rows (backup is written
first). Tables without a CSV export (euthyna_audit_trail, agent_incidents,
agent_wallets, earn_vault_positions, qma_treasury_policy) are NOT touched.

Usage: python scripts/import_supabase_csv.py [--data-dir data]
Requires: psycopg2 (system python or venv with psycopg2-binary) and DATABASE_URL in .env.
"""

import csv
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, execute_values

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))  # runtime_state payloads exceed the 128KB default

REPO = Path(__file__).resolve().parent.parent
TIMESTAMPISH = {
    "created_at", "updated_at", "expires_at", "paid_at", "saved_at",
    "last_used_at", "lease_expires_at", "started_at", "ended_at",
    "next_run_at", "heartbeat_at", "last_checkpoint_at", "inserted_at",
}

# table -> (csv file, jsonb columns, array columns, bool columns, created_at backfill source)
TABLE_MAP = {
    "qma_invoices": ("qma_invoices_rows.csv", ["invoice"], [], []),
    "qma_paid_reports": ("qma_paid_reports_rows.csv", ["entitlement"], [], []),
    "qma_payment_events": ("qma_payment_events_rows.csv", ["event"], [], []),
    "qma_creator_applications": ("qma_creator_applications_rows.csv", ["application"], [], []),
    "qma_provider_controls": ("qma_provider_controls_rows.csv", ["control"], [], []),
    "agent_sessions": ("agent_sessions_rows.csv", ["runtime_state", "policy"], ["allowed_providers", "allowed_tiers"], []),
    "agent_session_events": ("agent_session_events_rows.csv", ["payload"], [], []),
    "mcp_connections": ("mcp_connections_rows.csv", ["caps"], ["redirect_uris"], []),
    "mcp_auth_codes": ("mcp_auth_codes_rows.csv", ["caps"], [], ["used"]),
    "mcp_spend_ledger": ("mcp_spend_ledger_rows.csv", [], [], []),
}
CREATED_AT_BACKFILL = {"qma_invoices": "inserted_at", "qma_paid_reports": "inserted_at",
                       "qma_payment_events": "inserted_at"}
# Legacy header-bypass rows have no payer; local schema is NOT NULL there.
NULL_FALLBACK = {
    "qma_paid_reports": {"payer_address": "unknown"},
    "qma_payment_events": {"payer_address": "unknown"},
}


def load_env(path: Path) -> dict:
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def coerce(value, column: str, data_type: str, jsonb: set, arrays: set, bools: set):
    if value is None or value == "":
        return None
    if column in jsonb:
        return Json(value if isinstance(value, (dict, list)) else json.loads(value))
    if column in arrays:
        if isinstance(value, str):
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [parsed]
        return value
    if column in bools:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "t", "1", "yes")
    if data_type.startswith("timestamp") and isinstance(value, str):
        return value  # PostgreSQL parses the Supabase ISO text directly
    if data_type == "bigint":
        return int(float(value))  # Supabase exports epoch-with-subseconds as float text
    return value


def main() -> int:
    data_dir = REPO / (sys.argv[sys.argv.index("--data-dir") + 1] if "--data-dir" in sys.argv else "data")
    env = load_env(REPO / ".env")
    conn = psycopg2.connect(env["DATABASE_URL"])
    cur = conn.cursor()

    # 1. backup current contents of every table we are about to replace
    backup = {}
    for table in TABLE_MAP:
        cur.execute(f"SELECT to_jsonb(x) FROM (SELECT * FROM {table}) x")
        backup[table] = [r[0] for r in cur.fetchall()]
    out = REPO / "scratch" / "reports" / "db_pre_csv_import_backup.json"
    out.write_text(json.dumps(backup, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"backup written: {out} ({ {k: len(v) for k, v in backup.items()} })")

    # 2. truncate all tables in ONE statement (FKs between them are allowed this way)
    cur.execute(f"TRUNCATE TABLE {', '.join(TABLE_MAP)}")

    # 3. insert
    for table, (filename, jsonb_cols, array_cols, bool_cols) in TABLE_MAP.items():
        path = data_dir / filename
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name=%s AND table_schema='public'", (table,))
        db_cols = {name: dtype for name, dtype in cur.fetchall()}
        if not path.exists() or path.stat().st_size == 0:
            print(f"{table}: csv empty/missing -> nothing to insert")
            continue
        with path.open(encoding="utf-8", newline="") as fh:
            reader = list(csv.DictReader(fh))
        if not reader:
            print(f"{table}: csv has no rows -> nothing to insert")
            continue
        common = [c for c in reader[0].keys() if c in db_cols]
        # bigint columns receiving non-numeric values (e.g. uuid ids) are dropped so
        # the column's sequence default assigns them (only valid when a default exists)
        for col in list(common):
            if db_cols.get(col) == "bigint":
                sample = [r.get(col) for r in reader if r.get(col) not in (None, "")]
                if sample:
                    try:
                        int(float(sample[0]))
                    except ValueError:
                        if db_cols[col] == "bigint":
                            cur.execute(
                                "SELECT column_default FROM information_schema.columns WHERE table_name=%s AND table_schema='public' AND column_name=%s",
                                (table, col),
                            )
                            if cur.fetchone()[0]:
                                common.remove(col)
        if db_cols.get("created_at") and "created_at" not in common and CREATED_AT_BACKFILL.get(table) in reader[0]:
            common.append("created_at")
        if table == "mcp_spend_ledger" and "owner_wallet" not in common and "owner_wallet" in db_cols:
            common.append("owner_wallet")  # value comes from owner_backfill (NOT NULL column)
        rows = []
        fallback = NULL_FALLBACK.get(table, {})
        owner_backfill = {}
        if table == "mcp_spend_ledger":
            # legacy spend rows lack owner_wallet; the owning connection (imported
            # earlier in TABLE_MAP order) is the semantic source
            cur.execute("SELECT client_id, owner_wallet FROM mcp_connections")
            owner_backfill = {cid: (ow or "unknown") for cid, ow in cur.fetchall()}
        for row in reader:
            values = []
            for col in common:
                raw = row.get(col)
                if (raw is None or raw == "") and col in fallback:
                    raw = fallback[col]
                if (raw is None or raw == "") and col == "owner_wallet" and owner_backfill:
                    raw = owner_backfill.get(row.get("connection_id"), "unknown")
                if col == "created_at" and "created_at" not in reader[0]:
                    values.append(coerce(row.get(CREATED_AT_BACKFILL[table]), "created_at", db_cols["created_at"], jsonb_cols, array_cols, bool_cols))
                else:
                    values.append(coerce(raw, col, db_cols.get(col, "text"), jsonb_cols, array_cols, bool_cols))
            rows.append(tuple(values))
        execute_values(
            cur,
            f"INSERT INTO {table} ({', '.join(common)}) VALUES %s",
            rows,
            page_size=500,
        )
        print(f"{table}: replaced with {len(rows)} rows ({len(common)} cols)")

    conn.commit()

    # 4. verification
    print("\n--- post-import counts ---")
    for table in TABLE_MAP:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"{table}: {cur.fetchone()[0]}")
    cur.execute("SELECT status, COUNT(*) FROM qma_invoices GROUP BY 1 ORDER BY 2 DESC")
    print("invoice statuses:", cur.fetchall())
    cur.execute("SELECT COUNT(*) FROM qma_payment_events WHERE event_id IS NULL")
    print("payment_events missing event_id:", cur.fetchone()[0])
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
