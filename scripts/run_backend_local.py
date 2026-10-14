"""Local backend launcher: loads .env, forces the Postgres backend, runs uvicorn.

Kept as a file (not an inline -c string) so the exact environment contract is
reviewable and so a silent process death is visible in a restart-loop log.
"""

import os
import sys

# Script mode puts scripts/ first on sys.path; the uvicorn import string
# "main:app" resolves against the repo root, so add it explicitly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

os.environ["QMA_STORAGE_BACKEND"] = "postgres"
# The traction swarm legitimately polls invoice status from one IP while
# several buyer instances run; the shared default (20/min) trips 429s that
# waste the buyers' bounded poll windows. Local operator allowance only.
os.environ.setdefault("QMA_RATE_LIMIT_INVOICE_PER_MIN", "60")

database_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or os.getenv("QMA_DATABASE_URL")
if not database_url:
    print("\n[CRITICAL ERROR] QMA_STORAGE_BACKEND is set to postgres, but DATABASE_URL is missing!", file=sys.stderr)
    print("Please ensure DATABASE_URL is defined in .env (e.g. postgresql://postgres:password@localhost:5432/qma).", file=sys.stderr)
    sys.exit(1)

# Pre-flight check: strictly verify local PostgreSQL connection before launching uvicorn
try:
    import psycopg2
    from urllib.parse import urlparse
    parsed = urlparse(database_url)
    db_target = f"{parsed.hostname}:{parsed.port or 5432}/{parsed.path.lstrip('/')}"
    print(f"[*] Pre-flight check: Verifying self-hosted PostgreSQL connection to {db_target} ...")
    conn = psycopg2.connect(database_url, connect_timeout=5)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
        tbl_count = cur.fetchone()[0]
    conn.close()
    print(f"[OK] Self-hosted PostgreSQL verified! Active tables in public schema: {tbl_count}")
except Exception as exc:
    print(f"\n[CRITICAL ERROR] Cannot connect to self-hosted PostgreSQL: {exc}", file=sys.stderr)
    print("Ensure PostgreSQL is running locally on port 5432 and credentials in .env are correct.", file=sys.stderr)
    print("NO SILENT FALLBACK TO JSON IS PERMITTED.", file=sys.stderr)
    sys.exit(1)

import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
