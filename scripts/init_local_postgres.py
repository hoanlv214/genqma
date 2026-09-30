import json
import os
import sys
import time
from pathlib import Path
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extras import Json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DB_USER = "postgres"
DB_PASS = "Hoanlv@214"
DB_HOST = "localhost"
DB_PORT = 5432
TARGET_DB = "qma"


def load_json(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, type(fallback)) else fallback
    except Exception as e:
        print(f"Error loading {path.name}: {e}")
        return fallback


def create_database_if_not_exists():
    print(f"Checking if database '{TARGET_DB}' exists...")
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        dbname="postgres",
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (TARGET_DB,))
    exists = cur.fetchone() is not None
    if not exists:
        print(f"Creating database '{TARGET_DB}'...")
        cur.execute(f'CREATE DATABASE "{TARGET_DB}";')
        print(f"Database '{TARGET_DB}' created successfully.")
    else:
        print(f"Database '{TARGET_DB}' already exists.")
    cur.close()
    conn.close()


def run_schema(conn):
    print("Running scripts/schema.sql...")
    schema_path = ROOT / "scripts" / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()
    print("Schema applied successfully.")


def migrate_data(conn):
    print("\nStarting data migration from local JSON files to PostgreSQL...")
    cur = conn.cursor()

    # 1. Payment Events
    payment_events = load_json(ROOT / "payment_ledger.json", [])
    print(f"Migrating {len(payment_events)} payment events...")
    inserted_events = 0
    for evt in payment_events:
        if not isinstance(evt, dict):
            continue
        event_id = evt.get("event_id") or evt.get("id") or evt.get("transaction_hash")
        if not event_id:
            continue
        cur.execute(
            """
            INSERT INTO public.qma_payment_events (
                event_id, invoice_id, settlement_id, payer_address, symbol, tier,
                provider_id, amount_usdc, gateway_status, transaction_hash,
                explorer_url, paid_at, event
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO UPDATE SET
                settlement_id = EXCLUDED.settlement_id,
                gateway_status = EXCLUDED.gateway_status,
                event = EXCLUDED.event;
            """,
            (
                str(event_id),
                evt.get("invoice_id"),
                evt.get("settlement_id"),
                evt.get("payer_address"),
                evt.get("symbol"),
                evt.get("tier"),
                evt.get("provider_id", "funding_memory"),
                evt.get("amount_usdc"),
                evt.get("gateway_status"),
                evt.get("transaction_hash"),
                evt.get("explorer_url"),
                evt.get("paid_at"),
                Json(evt),
            ),
        )
        inserted_events += 1
    conn.commit()
    print(f" -> Inserted/updated {inserted_events} payment events.")

    # 2. Paid Reports
    paid_reports = load_json(ROOT / "paid_reports.json", {})
    print(f"Migrating {len(paid_reports)} paid reports...")
    inserted_reports = 0
    report_items = paid_reports.items() if isinstance(paid_reports, dict) else [(r.get("entitlement_id"), r) for r in paid_reports if isinstance(r, dict)]
    for ent_id, rep in report_items:
        if not isinstance(rep, dict):
            continue
        key = ent_id or rep.get("entitlement_id")
        if not key:
            continue
        cur.execute(
            """
            INSERT INTO public.qma_paid_reports (
                entitlement_id, payer_address, symbol, tier, provider_id,
                query_hash, settlement_id, paid_at, saved_at, entitlement
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (entitlement_id) DO UPDATE SET
                settlement_id = EXCLUDED.settlement_id,
                entitlement = EXCLUDED.entitlement;
            """,
            (
                str(key),
                rep.get("payer_address") or "unknown",
                rep.get("symbol") or "BTC_USDT",
                rep.get("tier") or "preview",
                rep.get("provider_id", "funding_memory"),
                rep.get("query_hash"),
                rep.get("settlement_id"),
                rep.get("paid_at"),
                rep.get("saved_at"),
                Json(rep),
            ),
        )
        inserted_reports += 1
    conn.commit()
    print(f" -> Inserted/updated {inserted_reports} paid reports.")

    # 3. Invoices
    invoices = load_json(ROOT / "invoices.json", {})
    print(f"Migrating {len(invoices)} invoices...")
    inserted_invoices = 0
    inv_items = invoices.items() if isinstance(invoices, dict) else [(i.get("invoice_id"), i) for i in invoices if isinstance(i, dict)]
    for inv_id, inv in inv_items:
        if not isinstance(inv, dict):
            continue
        key = inv_id or inv.get("invoice_id")
        if not key:
            continue
        cur.execute(
            """
            INSERT INTO public.qma_invoices (
                invoice_id, status, settlement_id, payer_address, symbol, tier,
                provider_id, query_hash, created_at, expires_at, paid_at, invoice
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (invoice_id) DO UPDATE SET
                status = EXCLUDED.status,
                settlement_id = EXCLUDED.settlement_id,
                paid_at = EXCLUDED.paid_at,
                invoice = EXCLUDED.invoice;
            """,
            (
                str(key),
                inv.get("status", "pending"),
                inv.get("settlement_id"),
                inv.get("payer_address"),
                inv.get("symbol"),
                inv.get("tier"),
                inv.get("provider_id", "funding_memory"),
                inv.get("query_hash"),
                inv.get("created_at"),
                inv.get("expires_at"),
                inv.get("paid_at"),
                Json(inv),
            ),
        )
        inserted_invoices += 1
    conn.commit()
    print(f" -> Inserted/updated {inserted_invoices} invoices.")

    # 4. Creator Applications
    creator_apps = load_json(ROOT / "creator_applications.json", [])
    print(f"Migrating {len(creator_apps)} creator applications...")
    inserted_creators = 0
    app_list = creator_apps.values() if isinstance(creator_apps, dict) else creator_apps
    for app in app_list:
        if not isinstance(app, dict):
            continue
        app_id = app.get("application_id") or app.get("id")
        if not app_id:
            continue
        cur.execute(
            """
            INSERT INTO public.qma_creator_applications (
                application_id, creator_wallet, provider_id, status,
                created_at, updated_at, application
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (application_id) DO UPDATE SET
                status = EXCLUDED.status,
                updated_at = EXCLUDED.updated_at,
                application = EXCLUDED.application;
            """,
            (
                str(app_id),
                app.get("creator_wallet") or "0x0000000000000000000000000000000000000000",
                app.get("provider_id") or "unknown",
                app.get("status", "pending"),
                app.get("created_at"),
                app.get("updated_at"),
                Json(app),
            ),
        )
        inserted_creators += 1
    conn.commit()
    print(f" -> Inserted/updated {inserted_creators} creator applications.")

    # 5. Provider Controls
    provider_controls = load_json(ROOT / "provider_controls.json", {})
    print(f"Migrating {len(provider_controls)} provider controls...")
    inserted_controls = 0
    ctrl_items = provider_controls.items() if isinstance(provider_controls, dict) else []
    for pid, ctrl in ctrl_items:
        if not isinstance(ctrl, dict):
            ctrl = {"enabled": bool(ctrl)}
        cur.execute(
            """
            INSERT INTO public.qma_provider_controls (
                provider_id, enabled, updated_at, control
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (provider_id) DO UPDATE SET
                enabled = EXCLUDED.enabled,
                updated_at = EXCLUDED.updated_at,
                control = EXCLUDED.control;
            """,
            (
                str(pid),
                ctrl.get("enabled", True),
                ctrl.get("updated_at") or int(time.time()),
                Json(ctrl),
            ),
        )
        inserted_controls += 1
    conn.commit()
    print(f" -> Inserted/updated {inserted_controls} provider controls.")

    # 6. Agent Wallets
    agent_wallets = load_json(ROOT / "agent_wallets.json", [])
    print(f"Migrating {len(agent_wallets)} agent wallets...")
    inserted_wallets = 0
    for w in agent_wallets:
        if not isinstance(w, dict):
            continue
        addr = w.get("address") or w.get("wallet_address") or w.get("owner_wallet")
        if not addr:
            continue
        cur.execute(
            """
            INSERT INTO public.agent_wallets (
                address, status, balance_usdc, gateway_balance_usdc, metadata
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (address) DO UPDATE SET
                status = EXCLUDED.status,
                balance_usdc = EXCLUDED.balance_usdc,
                gateway_balance_usdc = EXCLUDED.gateway_balance_usdc,
                metadata = EXCLUDED.metadata;
            """,
            (
                str(addr),
                w.get("status", "active"),
                w.get("balance_usdc", 0.0),
                w.get("gateway_balance_usdc", 0.0),
                Json(w),
            ),
        )
        inserted_wallets += 1
    conn.commit()
    print(f" -> Inserted/updated {inserted_wallets} agent wallets.")

    # 7. Agent Sessions
    agent_sessions = load_json(ROOT / "agent_sessions.json", [])
    print(f"Migrating {len(agent_sessions)} agent sessions...")
    inserted_sessions = 0
    for s in agent_sessions:
        if not isinstance(s, dict):
            continue
        sid = s.get("id") or s.get("session_id")
        if not sid:
            continue
        cur.execute(
            """
            INSERT INTO public.agent_sessions (
                id, owner_wallet, status, task, budget_usdc, max_price_usdc,
                allowed_providers, allowed_tiers, execution_mode, runtime_state,
                policy, lease_owner, run_generation
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                runtime_state = EXCLUDED.runtime_state,
                policy = EXCLUDED.policy,
                lease_owner = EXCLUDED.lease_owner,
                run_generation = EXCLUDED.run_generation;
            """,
            (
                str(sid),
                s.get("owner_wallet") or "0x0000000000000000000000000000000000000000",
                s.get("status", "queued"),
                s.get("task", ""),
                s.get("budget_usdc", 0.0),
                s.get("max_price_usdc", 0.0),
                s.get("allowed_providers") or ["funding_memory"],
                s.get("allowed_tiers") or ["preview", "full"],
                s.get("execution_mode", "dry_run"),
                Json(s.get("runtime_state") or {}),
                Json(s.get("policy") or {}),
                s.get("lease_owner"),
                s.get("run_generation", 0),
            ),
        )
        inserted_sessions += 1
    conn.commit()
    print(f" -> Inserted/updated {inserted_sessions} agent sessions.")

    cur.close()


def print_summary(conn):
    print("\n--- DATABASE VERIFICATION SUMMARY ---")
    cur = conn.cursor()
    tables = [
        "qma_payment_events",
        "qma_paid_reports",
        "qma_invoices",
        "qma_creator_applications",
        "qma_provider_controls",
        "agent_wallets",
        "agent_sessions",
        "agent_session_events",
        "mcp_connections",
        "mcp_auth_codes",
        "mcp_spend_ledger",
    ]
    for tbl in tables:
        cur.execute(f"SELECT COUNT(*) FROM public.{tbl};")
        cnt = cur.fetchone()[0]
        print(f"  public.{tbl:<28} : {cnt:>6} rows")
    cur.close()


def main():
    try:
        create_database_if_not_exists()
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            dbname=TARGET_DB,
        )
        run_schema(conn)
        migrate_data(conn)
        print_summary(conn)
        conn.close()
        print("\nLOCAL POSTGRESQL INITIALIZATION & MIGRATION COMPLETE!")
        return 0
    except Exception as e:
        print(f"\nFATAL ERROR during initialization/migration: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
