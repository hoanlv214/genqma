import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests


ROOT = Path(__file__).resolve().parents[1]

TIER_PRICE_USDC = {
    "preview": 0.001,
    "full": 0.005,
}

ARC_GATEWAY_API = os.getenv("QMA_CIRCLE_GATEWAY_API", "https://gateway-api-testnet.circle.com")
ARC_EXPLORER = os.getenv("QMA_ARC_EXPLORER", "https://testnet.arcscan.app")
ARC_GATEWAY_WALLET = os.getenv(
    "QMA_ARC_GATEWAY_WALLET",
    "0x0077777d7EBA4688BDeF3E311b846F25870A19B9",
)
PAYMENT_WALLET_ADDRESS = os.getenv("QMA_PAYMENT_WALLET_ADDRESS", "")
PAYMENT_RESOURCE_TYPE = "qma_signal_report"
ARC_GATEWAY_TX_CACHE = None
ARC_SCAN_MAX_PAGES = 20

EVENT_COMPARE_FIELDS = (
    "payer_address",
    "amount_usdc",
    "gateway_status",
    "transaction_hash",
    "explorer_url",
    "paid_at",
)
INVOICE_COMPARE_FIELDS = (
    "status",
    "settlement_id",
    "payer_address",
    "paid_at",
)
INVOICE_JSON_COMPARE_FIELDS = (
    "status",
    "settlement_id",
    "payer_address",
    "paid_at",
    "gateway_status",
    "transaction_hash",
    "explorer_url",
    "amount_raw",
    "amount",
)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def normalize_address(value) -> str:
    return str(value or "").strip().lower()


def project_ref(url: str) -> str:
    host = urlparse(url).hostname or url
    return host.split(".")[0]


def mask_ref(url: str) -> str:
    ref = project_ref(url)
    return ref if len(ref) <= 8 else f"{ref[:4]}...{ref[-4:]}"


def parse_jsonb(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def first_present(*values):
    for value in values:
        if value is not None and value != "":
            return value
    return None


def equivalent(value_a, value_b) -> bool:
    if value_a in (None, "") and value_b in (None, ""):
        return True
    try:
        return float(value_a) == float(value_b)
    except (TypeError, ValueError):
        return str(value_a or "") == str(value_b or "")


def event_needs_update(before: dict, after: dict) -> bool:
    return any(not equivalent(before.get(field), after.get(field)) for field in EVENT_COMPARE_FIELDS)


def invoice_needs_update(before: dict, after: dict) -> bool:
    if any(not equivalent(before.get(field), after.get(field)) for field in INVOICE_COMPARE_FIELDS):
        return True
    before_invoice = parse_jsonb(before.get("invoice"))
    after_invoice = parse_jsonb(after.get("invoice"))
    return any(
        not equivalent(before_invoice.get(field), after_invoice.get(field))
        for field in INVOICE_JSON_COMPARE_FIELDS
    )


def parse_iso_utc(value: str) -> float:
    if not value:
        return 0.0
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def paid_at_from_settlement(settlement: dict):
    for key in ("updatedAt", "completedAt", "createdAt"):
        ts = parse_iso_utc(settlement.get(key, ""))
        if ts:
            return ts
    return None


def raw_usdc_to_float(raw_amount):
    if raw_amount is None or raw_amount == "":
        return None
    try:
        return int(str(raw_amount)) / 1_000_000
    except (TypeError, ValueError):
        return None


class SupabaseRest:
    def __init__(self, *, url: str, service_role_key: str, schema: str = "public", timeout: int = 25):
        self.url = url.rstrip("/")
        self.rest_url = f"{self.url}/rest/v1"
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
            return None
        return response.json()

    def fetch_all(self, table: str, *, select: str = "*", order: str | None = None, batch_size: int = 500):
        rows = []
        offset = 0
        while True:
            params = {"select": select}
            if order:
                params["order"] = order
            batch = self.request(
                "GET",
                table,
                params=params,
                headers={
                    "Range-Unit": "items",
                    "Range": f"{offset}-{offset + batch_size - 1}",
                },
            ) or []
            rows.extend(batch)
            if len(batch) < batch_size:
                return rows
            offset += batch_size

    def upsert(self, table: str, rows: list[dict], *, conflict: str):
        if not rows:
            return
        self.request(
            "POST",
            table,
            params={"on_conflict": conflict},
            json_body=rows,
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )


def build_supabase() -> SupabaseRest:
    url = os.getenv("SUPABASE_URL") or os.getenv("QMA_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("QMA_SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
    return SupabaseRest(
        url=url,
        service_role_key=key,
        schema=os.getenv("SUPABASE_SCHEMA", "public"),
    )


def refresh_runtime_config() -> None:
    global ARC_GATEWAY_API, ARC_EXPLORER, ARC_GATEWAY_WALLET, PAYMENT_WALLET_ADDRESS
    ARC_GATEWAY_API = os.getenv("QMA_CIRCLE_GATEWAY_API", ARC_GATEWAY_API)
    ARC_EXPLORER = os.getenv("QMA_ARC_EXPLORER", ARC_EXPLORER)
    ARC_GATEWAY_WALLET = os.getenv("QMA_ARC_GATEWAY_WALLET", ARC_GATEWAY_WALLET)
    PAYMENT_WALLET_ADDRESS = os.getenv("QMA_PAYMENT_WALLET_ADDRESS", PAYMENT_WALLET_ADDRESS)


def fetch_circle_settlement(settlement_id: str) -> dict:
    response = requests.get(f"{ARC_GATEWAY_API}/v1/x402/transfers/{settlement_id}", timeout=15)
    if response.status_code == 404:
        return {"status": "not_found"}
    if not response.ok:
        return {"status": "lookup_failed", "error": f"{response.status_code}: {response.text[:250]}"}
    return response.json()


def load_arc_gateway_transactions() -> tuple[list, str | None]:
    global ARC_GATEWAY_TX_CACHE
    if ARC_GATEWAY_TX_CACHE is not None:
        return ARC_GATEWAY_TX_CACHE
    transactions = []
    params = {"filter": "to"}
    for _ in range(max(1, ARC_SCAN_MAX_PAGES)):
        try:
            response = requests.get(
                f"{ARC_EXPLORER}/api/v2/addresses/{ARC_GATEWAY_WALLET}/transactions",
                params=params,
                timeout=20,
            )
        except requests.RequestException as exc:
            ARC_GATEWAY_TX_CACHE = (transactions, str(exc))
            return ARC_GATEWAY_TX_CACHE
        if not response.ok:
            ARC_GATEWAY_TX_CACHE = (transactions, f"Arcscan returned {response.status_code}")
            return ARC_GATEWAY_TX_CACHE
        data = response.json()
        transactions.extend(data.get("items", []))
        next_params = data.get("next_page_params")
        if not next_params:
            break
        params = {**next_params, "filter": "to"}
    ARC_GATEWAY_TX_CACHE = (transactions, None)
    return ARC_GATEWAY_TX_CACHE


def find_arc_batch_tx(settlement: dict) -> dict:
    status_value = settlement.get("status")
    if status_value not in {"completed", "confirmed"}:
        return {"transaction_hash": None, "explorer_url": None, "gateway_status": status_value}

    updated_ts = parse_iso_utc(settlement.get("updatedAt", ""))
    if not updated_ts:
        return {"transaction_hash": None, "explorer_url": None, "gateway_status": status_value}

    transactions, error = load_arc_gateway_transactions()
    if error:
        return {
            "transaction_hash": None,
            "explorer_url": None,
            "gateway_status": status_value,
            "error": error,
        }

    best_tx = None
    best_delta = None
    for tx in transactions:
        if tx.get("method") != "submitBatch":
            continue
        tx_ts = parse_iso_utc(tx.get("timestamp", ""))
        if not tx_ts:
            continue
        delta = abs(tx_ts - updated_ts)
        if delta <= 1800 and (best_delta is None or delta < best_delta):
            best_tx = tx
            best_delta = delta
    if best_tx:
        tx_hash = best_tx.get("hash")
        return {
            "transaction_hash": tx_hash,
            "explorer_url": f"{ARC_EXPLORER}/tx/{tx_hash}" if tx_hash else None,
            "gateway_status": status_value,
        }
    return {"transaction_hash": None, "explorer_url": None, "gateway_status": status_value}


def report_invoice(report_row: dict) -> dict:
    entitlement = parse_jsonb(report_row.get("entitlement"))
    report = parse_jsonb(entitlement.get("report"))
    invoice = parse_jsonb(report.get("invoice"))
    if not invoice:
        invoice = parse_jsonb(entitlement.get("invoice"))
    return invoice


def report_to_event(report_row: dict, settlement_cache: dict[str, dict], refresh_settlements: bool) -> dict | None:
    settlement_id = report_row.get("settlement_id")
    if not settlement_id:
        return None
    invoice = report_invoice(report_row)
    tier = first_present(report_row.get("tier"), invoice.get("tier"), "full")
    amount = first_present(invoice.get("amount"), TIER_PRICE_USDC.get(str(tier).lower()))
    settlement = settlement_cache.get(settlement_id) or {}
    batch = find_arc_batch_tx(settlement) if refresh_settlements and settlement else {}
    gateway_status = first_present(
        invoice.get("gateway_status"),
        batch.get("gateway_status"),
        settlement.get("status"),
        "completed",
    )
    event = {
        "event_id": settlement_id,
        "invoice_id": invoice.get("invoice_id"),
        "settlement_id": settlement_id,
        "payer_address": normalize_address(first_present(report_row.get("payer_address"), invoice.get("payer_address"))),
        "symbol": first_present(report_row.get("symbol"), invoice.get("symbol")),
        "tier": tier,
        "provider_id": first_present(report_row.get("provider_id"), invoice.get("provider_id"), "funding_memory"),
        "amount_usdc": amount,
        "gateway_status": gateway_status,
        "transaction_hash": first_present(invoice.get("transaction_hash"), batch.get("transaction_hash")),
        "explorer_url": first_present(invoice.get("explorer_url"), batch.get("explorer_url")),
        "paid_at": first_present(report_row.get("paid_at"), invoice.get("paid_at"), paid_at_from_settlement(settlement), report_row.get("saved_at")),
    }
    event["event"] = {
        **event,
        "amount_raw": first_present(invoice.get("amount_raw"), settlement.get("amount")),
        "buyer_type": first_present(invoice.get("buyer_type"), "human"),
        "provider_owner_wallet": first_present(invoice.get("owner_wallet"), PAYMENT_WALLET_ADDRESS),
        "seller_address": PAYMENT_WALLET_ADDRESS,
        "resource_type": first_present(invoice.get("resource_type"), PAYMENT_RESOURCE_TYPE),
        "query_hash": first_present(report_row.get("query_hash"), invoice.get("query_hash")),
        "source": "repair_supabase_payments",
    }
    event["event"] = {key: value for key, value in event["event"].items() if value is not None and value != ""}
    return event


def merge_invoice(invoice_row: dict, source: dict, settlement: dict | None = None, batch: dict | None = None) -> dict:
    invoice = parse_jsonb(invoice_row.get("invoice"))
    settlement = settlement or {}
    batch = batch or {}
    status = first_present(source.get("status"), invoice_row.get("status"), invoice.get("status"))
    settlement_id = first_present(source.get("settlement_id"), invoice_row.get("settlement_id"), invoice.get("settlement_id"))
    paid_at = first_present(source.get("paid_at"), invoice_row.get("paid_at"), invoice.get("paid_at"), paid_at_from_settlement(settlement))
    payer_address = normalize_address(first_present(source.get("payer_address"), invoice_row.get("payer_address"), invoice.get("payer_address")))
    if settlement_id and paid_at and payer_address:
        status = "paid"
    if settlement.get("fromAddress") and not payer_address:
        payer_address = normalize_address(settlement.get("fromAddress"))
    amount_raw = first_present(source.get("amount_raw"), invoice.get("amount_raw"), settlement.get("amount"))
    amount_usdc = first_present(source.get("amount_usdc"), invoice.get("amount"), raw_usdc_to_float(amount_raw))

    invoice.update({
        "invoice_id": first_present(invoice_row.get("invoice_id"), invoice.get("invoice_id"), source.get("invoice_id")),
        "status": status,
        "settlement_id": settlement_id,
        "payer_address": payer_address,
        "paid_at": paid_at,
        "gateway_status": first_present(source.get("gateway_status"), batch.get("gateway_status"), settlement.get("status"), invoice.get("gateway_status")),
        "transaction_hash": first_present(source.get("transaction_hash"), batch.get("transaction_hash"), invoice.get("transaction_hash")),
        "explorer_url": first_present(source.get("explorer_url"), batch.get("explorer_url"), invoice.get("explorer_url")),
        "amount_raw": amount_raw,
        "amount": amount_usdc,
        "buyer_type": first_present(source.get("buyer_type"), invoice.get("buyer_type"), "human"),
    })
    invoice = {key: value for key, value in invoice.items() if value is not None}
    return {
        "invoice_id": invoice["invoice_id"],
        "status": status,
        "settlement_id": settlement_id,
        "payer_address": payer_address,
        "symbol": first_present(invoice_row.get("symbol"), invoice.get("symbol"), source.get("symbol")),
        "tier": first_present(invoice_row.get("tier"), invoice.get("tier"), source.get("tier")),
        "provider_id": first_present(invoice_row.get("provider_id"), invoice.get("provider_id"), source.get("provider_id"), "funding_memory"),
        "query_hash": first_present(invoice_row.get("query_hash"), invoice.get("query_hash"), source.get("query_hash")),
        "created_at": first_present(invoice_row.get("created_at"), invoice.get("created_at")),
        "expires_at": first_present(invoice_row.get("expires_at"), invoice.get("expires_at")),
        "paid_at": paid_at,
        "invoice": invoice,
    }


def event_patch(event_row: dict, settlement: dict, batch: dict) -> dict:
    event = parse_jsonb(event_row.get("event"))
    amount_raw = first_present(event.get("amount_raw"), settlement.get("amount"))
    amount_usdc = first_present(event_row.get("amount_usdc"), event.get("amount_usdc"), raw_usdc_to_float(amount_raw))
    patched = {
        **event_row,
        "payer_address": normalize_address(first_present(event_row.get("payer_address"), event.get("payer_address"), settlement.get("fromAddress"))),
        "amount_usdc": amount_usdc,
        "gateway_status": first_present(batch.get("gateway_status"), settlement.get("status"), event_row.get("gateway_status")),
        "transaction_hash": first_present(event_row.get("transaction_hash"), event.get("transaction_hash"), batch.get("transaction_hash")),
        "explorer_url": first_present(event_row.get("explorer_url"), event.get("explorer_url"), batch.get("explorer_url")),
        "paid_at": first_present(event_row.get("paid_at"), event.get("paid_at"), paid_at_from_settlement(settlement)),
    }
    event.update({
        **patched,
        "amount_raw": amount_raw,
        "seller_address": first_present(event.get("seller_address"), PAYMENT_WALLET_ADDRESS),
    })
    patched["event"] = {key: value for key, value in event.items() if value is not None and value != ""}
    return patched


def summarize(rows: list[dict], table: str) -> dict:
    def row_settlement(row):
        payload = parse_jsonb(row.get("invoice")) if table == "qma_invoices" else {}
        return first_present(row.get("settlement_id"), payload.get("settlement_id"))

    def row_tx(row):
        payload = parse_jsonb(row.get("invoice")) if table == "qma_invoices" else {}
        return first_present(row.get("transaction_hash"), payload.get("transaction_hash"))

    def row_payer(row):
        payload = parse_jsonb(row.get("invoice")) if table == "qma_invoices" else {}
        return first_present(row.get("payer_address"), payload.get("payer_address"))

    def row_paid_at(row):
        payload = parse_jsonb(row.get("invoice")) if table == "qma_invoices" else {}
        return first_present(row.get("paid_at"), payload.get("paid_at"))

    return {
        "table": table,
        "rows": len(rows),
        "missing_settlement": sum(1 for row in rows if not row_settlement(row)),
        "missing_payer": sum(1 for row in rows if not row_payer(row)),
        "missing_paid_at": sum(1 for row in rows if row_paid_at(row) in (None, "")),
        "missing_tx": sum(1 for row in rows if row_settlement(row) and not row_tx(row)),
    }


def final_status(value) -> bool:
    return str(value or "").lower() in {"completed", "confirmed"}


def invoice_needs_settlement_refresh(row: dict) -> bool:
    if not row.get("settlement_id"):
        return False
    invoice = parse_jsonb(row.get("invoice"))
    return (
        not row.get("transaction_hash")
        and (
            not invoice.get("transaction_hash")
            or not final_status(first_present(invoice.get("gateway_status"), row.get("status")))
        )
    )


def event_needs_settlement_refresh(row: dict) -> bool:
    return bool(
        row.get("settlement_id")
        and (not row.get("transaction_hash") or not final_status(row.get("gateway_status")))
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Repair QMA Supabase payment rows from paid reports, invoices, and optional Circle settlement lookup."
    )
    parser.add_argument("--apply", action="store_true", help="Write repairs. Default is dry-run.")
    parser.add_argument("--refresh-settlements", action="store_true", help="Call Circle Gateway and Arcscan for settlement status/tx backfill.")
    parser.add_argument("--arcscan-pages", type=int, default=20, help="Arcscan gateway transaction pages to scan when matching completed batches.")
    parser.add_argument("--limit", type=int, default=0, help="Limit rows written per table during testing.")
    parser.add_argument("--batch-size", type=int, default=500)
    return parser.parse_args()


def main() -> int:
    load_env_file(ROOT / ".env")
    refresh_runtime_config()
    args = parse_args()
    global ARC_SCAN_MAX_PAGES
    ARC_SCAN_MAX_PAGES = max(1, args.arcscan_pages)
    supabase = build_supabase()

    invoices = supabase.fetch_all("qma_invoices", batch_size=args.batch_size)
    reports = supabase.fetch_all("qma_paid_reports", batch_size=args.batch_size)
    events = supabase.fetch_all("qma_payment_events", batch_size=args.batch_size)

    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print(f"Project: {mask_ref(supabase.url)}")
    print(f"Refresh settlements: {'yes' if args.refresh_settlements else 'no'}")
    print("")
    for item in (
        summarize(invoices, "qma_invoices"),
        summarize(reports, "qma_paid_reports"),
        summarize(events, "qma_payment_events"),
    ):
        print(
            f"{item['table']}: rows={item['rows']}, "
            f"missing_settlement={item['missing_settlement']}, "
            f"missing_payer={item['missing_payer']}, "
            f"missing_paid_at={item['missing_paid_at']}, "
            f"missing_tx={item['missing_tx']}"
        )
    print("")

    events_by_settlement = {row.get("settlement_id"): row for row in events if row.get("settlement_id")}
    events_by_invoice = {row.get("invoice_id"): row for row in events if row.get("invoice_id")}
    reports_by_invoice = {}
    for report in reports:
        invoice = report_invoice(report)
        invoice_id = invoice.get("invoice_id")
        if invoice_id:
            reports_by_invoice[invoice_id] = report

    settlement_ids = {
        row.get("settlement_id")
        for row in events
        if event_needs_settlement_refresh(row)
    }
    settlement_ids.update(
        row.get("settlement_id")
        for row in invoices
        if invoice_needs_settlement_refresh(row)
    )
    settlement_ids.update(
        row.get("settlement_id")
        for row in reports
        if row.get("settlement_id") and row.get("settlement_id") not in events_by_settlement
    )
    settlement_ids.discard(None)
    settlement_ids.discard("")
    settlement_cache: dict[str, dict] = {}
    if args.refresh_settlements:
        print(f"Looking up {len(settlement_ids)} settlements from Circle Gateway...")
        for index, settlement_id in enumerate(sorted(settlement_ids), start=1):
            settlement_cache[settlement_id] = fetch_circle_settlement(settlement_id)
            if index % 25 == 0:
                print(f"  checked {index}/{len(settlement_ids)}")

        status_counts = {}
        unresolved = []
        for settlement_id, settlement in settlement_cache.items():
            batch = find_arc_batch_tx(settlement)
            status = first_present(batch.get("gateway_status"), settlement.get("status"), "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            if not batch.get("transaction_hash"):
                unresolved.append((settlement_id, status))
        if status_counts:
            status_text = ", ".join(f"{status}={count}" for status, count in sorted(status_counts.items()))
            print(f"Settlement status: {status_text}")
        if unresolved:
            print("Settlements still without Arcscan tx:")
            for settlement_id, status in unresolved[:12]:
                print(f"  - {settlement_id}: {status}")
            if len(unresolved) > 12:
                print(f"  ... {len(unresolved) - 12} more")

    repaired_events = []
    for event in events:
        settlement_id = event.get("settlement_id")
        if not settlement_id:
            continue
        settlement = settlement_cache.get(settlement_id) or {}
        batch = find_arc_batch_tx(settlement) if settlement else {}
        patch = event_patch(event, settlement, batch)
        if event_needs_update(event, patch):
            repaired_events.append(patch)

    backfilled_events = []
    for report in reports:
        settlement_id = report.get("settlement_id")
        if settlement_id and settlement_id not in events_by_settlement:
            event = report_to_event(report, settlement_cache, args.refresh_settlements)
            if event:
                backfilled_events.append(event)

    repaired_invoices = []
    for invoice_row in invoices:
        invoice_id = invoice_row.get("invoice_id")
        source = events_by_invoice.get(invoice_id) or {}
        report = reports_by_invoice.get(invoice_id)
        if report and not source:
            source = report_to_event(report, settlement_cache, args.refresh_settlements) or {}
        settlement_id = first_present(source.get("settlement_id"), invoice_row.get("settlement_id"))
        settlement = settlement_cache.get(settlement_id) or {}
        batch = find_arc_batch_tx(settlement) if settlement else {}
        patch = merge_invoice(invoice_row, source, settlement, batch)
        if invoice_needs_update(invoice_row, patch):
            repaired_invoices.append(patch)

    if args.limit > 0:
        repaired_events = repaired_events[:args.limit]
        backfilled_events = backfilled_events[:args.limit]
        repaired_invoices = repaired_invoices[:args.limit]

    print("Planned repairs")
    print(f"- update qma_payment_events: {len(repaired_events)}")
    print(f"- insert/backfill qma_payment_events from qma_paid_reports: {len(backfilled_events)}")
    print(f"- update qma_invoices: {len(repaired_invoices)}")

    stuck_received = [
        row for row in [*repaired_events, *backfilled_events]
        if row.get("gateway_status") == "received" and not row.get("transaction_hash")
    ]
    if stuck_received:
        print(f"- still pending on Circle/Arc batch: {len(stuck_received)}")

    if not args.apply:
        print("\nDry run only. Re-run with --apply to write repairs.")
        return 0

    supabase.upsert("qma_payment_events", repaired_events, conflict="event_id")
    supabase.upsert("qma_payment_events", backfilled_events, conflict="event_id")
    supabase.upsert("qma_invoices", repaired_invoices, conflict="invoice_id")
    print("\nRepair writes complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
