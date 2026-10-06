"""Policy vs Model: read-only research snapshot of QMA autonomous decision data.

Reproduces every number quoted in docs/research/POLICY_VS_MODEL.md directly from
the live database. The script never writes: it opens one read-only connection,
aggregates three tables (euthyna_audit_trail, agent_incidents, qma_payment_events)
and prints a markdown snapshot.

Usage:
    .venv/Scripts/python.exe scripts/research/policy_vs_model.py
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

import psycopg2


def connect():
    if load_dotenv:
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set; refusing to guess a connection target.")
    return psycopg2.connect(url)


def fetch_all(cur, sql: str):
    try:
        cur.execute(sql)
        return cur.fetchall()
    except psycopg2.Error as exc:
        print(f"> query skipped ({exc.__class__.__name__}: {str(exc).splitlines()[0][:90]})")
        conn = cur.connection
        conn.rollback()
        return []


def main() -> None:
    conn = connect()
    cur = conn.cursor()

    print("## Euthyna audit trail (CFO actions)")
    rows = fetch_all(
        cur,
        """
        SELECT CASE action
                 WHEN 'SWEEP_IDLE' THEN 'IDLE_SWEEP'
                 WHEN 'JIT_REDEEM' THEN 'JIT_REDEMPTION'
                 ELSE action
               END AS canonical_action,
               count(*), count(tx_hash),
               min(created_at)::date, max(created_at)::date
        FROM euthyna_audit_trail
        GROUP BY 1
        ORDER BY count(*) DESC
        """,
    )
    total = sum(r[1] for r in rows)
    with_tx = sum(r[2] for r in rows)
    if rows:
        span = f"{rows[0][3]} to {max(r[4] for r in rows)}"
        print(f"Total records: {total} ({span}); {with_tx} carry an on-chain tx hash.")
        print()
        print("| Action | Records | With tx hash |")
        print("| :--- | ---: | ---: |")
        for action, count, tx_count, _min_d, _max_d in rows:
            print(f"| `{action}` | {count} | {tx_count} |")
    print()

    print("## Policy interventions (agent_incidents)")
    rows = fetch_all(
        cur,
        """
        SELECT category, rule, status, count(*),
               min(created_at)::date, max(created_at)::date
        FROM agent_incidents
        GROUP BY category, rule, status
        ORDER BY count(*) DESC
        """,
    )
    if rows:
        print("| Category | Rule | Status | Count | Window |")
        print("| :--- | :--- | :--- | ---: | :--- |")
        for category, rule, status, count, min_d, max_d in rows:
            window = min_d.isoformat() if min_d == max_d else f"{min_d} to {max_d}"
            print(f"| `{category}` | `{rule}` | {status} | {count} | {window} |")
    else:
        print("No incidents recorded.")
    print()

    print("## Spend guard ledger (durable policy interventions)")
    rows = fetch_all(
        cur,
        """
        SELECT event_type, count(*), round(coalesce(sum(amount_usdc), 0), 4) AS volume_usdc,
               min(created_at)::date, max(created_at)::date
        FROM qma_spend_guard_events
        GROUP BY event_type
        ORDER BY count(*) DESC
        """,
    )
    if rows:
        print("| Event type | Count | Volume (USDC) | Window |")
        print("| :--- | ---: | ---: | :--- |")
        for event_type, count, volume, min_d, max_d in rows:
            window = min_d.isoformat() if min_d == max_d else f"{min_d} to {max_d}"
            print(f"| `{event_type}` | {count} | {volume} | {window} |")
    else:
        print("No spend guard events recorded (ledger introduced with migration 0014).")
    print()

    print("## Settlement ledger (qma_payment_events)")
    rows = fetch_all(
        cur,
        """
        SELECT gateway_status, count(*), round(sum(amount_usdc), 4)
        FROM qma_payment_events
        GROUP BY gateway_status
        ORDER BY count(*) DESC
        """,
    )
    if rows:
        total_events = sum(r[1] for r in rows)
        total_volume = sum(r[2] or 0 for r in rows)
        print(f"Total events: {total_events}; volume {total_volume} USDC.")
        print()
        print("| Gateway status | Events | Volume (USDC) |")
        print("| :--- | ---: | ---: |")
        for status, count, volume in rows:
            print(f"| {status} | {count} | {volume} |")
    print()

    rows = fetch_all(
        cur,
        """
        SELECT provider_id, count(*), round(sum(amount_usdc), 4)
        FROM qma_payment_events
        GROUP BY provider_id
        ORDER BY count(*) DESC
        """,
    )
    if rows:
        print("| Provider | Sales | Volume (USDC) |")
        print("| :--- | ---: | ---: |")
        for provider, count, volume in rows:
            print(f"| `{provider}` | {count} | {volume} |")

    conn.close()


if __name__ == "__main__":
    main()
