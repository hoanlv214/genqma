import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests


ROOT = Path(__file__).resolve().parents[1]


CORE_TABLES = {
    "qma_payment_events": "event_id",
    "qma_paid_reports": "entitlement_id",
    "qma_invoices": "invoice_id",
}

OPTIONAL_TABLES = {
    "qma_creator_applications": "application_id",
}

TABLES = {
    **CORE_TABLES,
    **OPTIONAL_TABLES,
}


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def project_ref(url: str) -> str:
    host = urlparse(url).hostname or url
    return host.split(".")[0]


def mask_ref(url: str) -> str:
    ref = project_ref(url)
    if len(ref) <= 8:
        return ref
    return f"{ref[:4]}...{ref[-4:]}"


class SupabaseProject:
    def __init__(self, *, url: str, service_role_key: str, schema: str = "public", timeout: int = 20):
        self.url = url.rstrip("/")
        self.rest_url = f"{self.url}/rest/v1"
        self.schema = schema
        self.timeout = timeout
        self.headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Profile": schema,
            "Content-Profile": schema,
        }

    def request(self, method: str, table: str, *, params=None, json_body=None, headers=None):
        merged_headers = dict(self.headers)
        if headers:
            merged_headers.update(headers)
        response = requests.request(
            method,
            f"{self.rest_url}/{table}",
            params=params,
            json=json_body,
            headers=merged_headers,
            timeout=self.timeout,
        )
        if not response.ok:
            raise RuntimeError(
                f"{method} {table} on {mask_ref(self.url)} failed "
                f"with {response.status_code}: {response.text[:500]}"
            )
        if response.status_code == 204 or not response.text:
            return None, response
        return response.json(), response

    def count(self, table: str) -> int:
        _, response = self.request(
            "GET",
            table,
            params={"select": "*"},
            headers={
                "Prefer": "count=exact",
                "Range-Unit": "items",
                "Range": "0-0",
            },
        )
        content_range = response.headers.get("Content-Range", "")
        if "/" not in content_range:
            return 0
        return int(content_range.rsplit("/", 1)[1])

    def fetch_rows(self, table: str, *, batch_size: int):
        offset = 0
        while True:
            end = offset + batch_size - 1
            rows, _ = self.request(
                "GET",
                table,
                params={"select": "*"},
                headers={
                    "Range-Unit": "items",
                    "Range": f"{offset}-{end}",
                },
            )
            rows = rows or []
            if not rows:
                break
            yield rows
            if len(rows) < batch_size:
                break
            offset += batch_size

    def upsert_rows(self, table: str, rows: list[dict], *, conflict: str) -> None:
        if not rows:
            return
        self.request(
            "POST",
            table,
            params={"on_conflict": conflict},
            json_body=rows,
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )


def build_project(prefix: str, *, fallback_current: bool = False) -> SupabaseProject:
    url = os.getenv(f"{prefix}_SUPABASE_URL")
    key = os.getenv(f"{prefix}_SUPABASE_SERVICE_ROLE_KEY")
    if fallback_current:
        url = url or os.getenv("SUPABASE_URL") or os.getenv("QMA_SUPABASE_URL")
        key = key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("QMA_SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            f"Missing {prefix}_SUPABASE_URL and {prefix}_SUPABASE_SERVICE_ROLE_KEY"
            + (" or SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY" if fallback_current else "")
        )
    return SupabaseProject(
        url=url,
        service_role_key=key,
        schema=os.getenv(f"{prefix}_SUPABASE_SCHEMA") or os.getenv("SUPABASE_SCHEMA", "public"),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy QMA rows from an old Supabase project into a new Supabase project."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write rows to the new Supabase project. Without this flag, the script only prints a dry run.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Rows to fetch/upsert per batch.",
    )
    parser.add_argument(
        "--tables",
        nargs="*",
        choices=sorted(TABLES),
        default=sorted(CORE_TABLES),
        help="Optional subset of tables to migrate.",
    )
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Also migrate optional tables such as qma_creator_applications when they exist.",
    )
    return parser.parse_args()


def migrate_table(old_project: SupabaseProject, new_project: SupabaseProject, table: str, *, batch_size: int, apply: bool):
    conflict = TABLES[table]
    old_count = old_project.count(table)
    new_before = new_project.count(table)
    print(f"{table}: old={old_count}, new_before={new_before}, conflict={conflict}")

    if not apply:
        return {"table": table, "old": old_count, "new_before": new_before, "new_after": new_before}

    copied = 0
    for rows in old_project.fetch_rows(table, batch_size=batch_size):
        new_project.upsert_rows(table, rows, conflict=conflict)
        copied += len(rows)
        print(f"  copied {copied}/{old_count}")

    new_after = new_project.count(table)
    print(f"  done: new_after={new_after}")
    return {"table": table, "old": old_count, "new_before": new_before, "new_after": new_after}


def main() -> int:
    load_env_file(ROOT / ".env")
    args = parse_args()

    old_project = build_project("OLD")
    new_project = build_project("NEW", fallback_current=True)

    if old_project.url == new_project.url:
        print("Old and new Supabase URLs are identical. Refusing to migrate into the same project.")
        return 1

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"Mode: {mode}")
    print(f"Old project: {mask_ref(old_project.url)}")
    print(f"New project: {mask_ref(new_project.url)}")
    print("")

    results = []
    try:
        tables = sorted(TABLES) if args.include_optional else args.tables
        for table in tables:
            results.append(
                migrate_table(
                    old_project,
                    new_project,
                    table,
                    batch_size=args.batch_size,
                    apply=args.apply,
                )
            )
    except RuntimeError as exc:
        print(f"\nMigration failed: {exc}")
        print("Make sure the new project schema has been created from docs/SUPABASE.md first.")
        return 1

    print("\nSummary")
    for item in results:
        print(
            f"- {item['table']}: old={item['old']}, "
            f"new_before={item['new_before']}, new_after={item['new_after']}"
        )
    if not args.apply:
        print("\nDry run only. Re-run with --apply to copy rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
