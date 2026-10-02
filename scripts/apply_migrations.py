#!/usr/bin/env python3
"""Database Migration Runner for QMA.

Applies migrations in `supabase/migrations/` in deterministic order to any
PostgreSQL database (Local Docker, Neon, Supabase, Render Postgres).

Usage:
    python scripts/apply_migrations.py [--status] [--database-url postgresql://...]
"""

import os
import sys
import glob
import logging
from urllib.parse import urlparse, unquote

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("QMA-Migrations")

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None


def get_database_url() -> str:
    # Check env
    url = (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("QMA_DATABASE_URL")
        or os.getenv("SUPABASE_DB_URL")
    )
    if url:
        return url

    # Try loading from .env
    env_paths = [".env", "qma-api.env", "backend/.env"]
    for path in env_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DATABASE_URL=") or line.startswith("POSTGRES_URL="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def apply_migrations(database_url: str, dry_run: bool = False, status_only: bool = False) -> bool:
    if psycopg2 is None:
        logger.error("psycopg2 is not installed. Please install psycopg2-binary to run migrations.")
        return False

    if not database_url:
        logger.warning("DATABASE_URL is not set. Cannot connect to PostgreSQL.")
        return False

    logger.info(f"Connecting to database...")
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
    except Exception as exc:
        logger.error(f"Failed to connect to database: {exc}")
        return False

    try:
        with conn.cursor() as cur:
            # Ensure schema_migrations table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            conn.commit()

            cur.execute("SELECT version FROM public.schema_migrations;")
            applied = {row[0] for row in cur.fetchall()}

        # Discover migration files
        migrations_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "supabase", "migrations")
        if not os.path.isdir(migrations_dir):
            logger.error(f"Migrations directory not found at: {migrations_dir}")
            return False

        migration_files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))
        if not migration_files:
            logger.warning(f"No SQL migration files found in {migrations_dir}")
            return True

        logger.info(f"Found {len(migration_files)} migration files in {migrations_dir}")

        for file_path in migration_files:
            version = os.path.basename(file_path)
            is_applied = version in applied

            if status_only:
                status_str = "[APPLIED]" if is_applied else "[PENDING]"
                logger.info(f"{status_str} {version}")
                continue

            if is_applied:
                logger.info(f"Skipping {version} (already applied)")
                continue

            logger.info(f"Applying migration: {version}...")
            with open(file_path, "r", encoding="utf-8") as f:
                sql_content = f.read()

            if dry_run:
                logger.info(f"[DRY-RUN] Would apply {version} ({len(sql_content)} bytes)")
                continue

            with conn.cursor() as cur:
                try:
                    cur.execute(sql_content)
                    cur.execute(
                        "INSERT INTO public.schema_migrations (version) VALUES (%s);",
                        (version,)
                    )
                    conn.commit()
                    logger.info(f"Successfully applied {version}")
                except Exception as exc:
                    conn.rollback()
                    logger.error(f"Failed to apply {version}: {exc}")
                    return False

        logger.info("All database migrations processed successfully.")
        return True
    finally:
        conn.close()


if __name__ == "__main__":
    db_url = ""
    status = False
    dry = False

    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--status":
            status = True
        elif arg == "--dry-run":
            dry = True
        elif arg.startswith("--database-url="):
            db_url = arg.split("=", 1)[1]
        elif arg == "--database-url" and i + 1 < len(args):
            db_url = args[i + 1]

    if not db_url:
        db_url = get_database_url()

    success = apply_migrations(db_url, dry_run=dry, status_only=status)
    sys.exit(0 if success else 1)
