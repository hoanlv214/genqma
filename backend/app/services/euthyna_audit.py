"""Euthyna Continuous Audit Engine for Autonomous Treasury on Arc.

Inspired by the Byzantine Vestiarion and Athenian Euthyna (the public examination
and accounting of financial stewards).
Provides an immutable, cryptographically verifiable audit log of every decision
made by the autonomous AI CFO:
- USYC Idle Treasury Sweeps
- USYC Just-In-Time Redemptions
- x402 Micropayment Invoices
- GenLayer Multi-Validator Verifications
- Provider Bond Slashes
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.core.config import (
    ARC_CHAIN_ID,
    ARC_EXPLORER,
    PAYMENT_NETWORK_NAME,
    PLATFORM_TREASURY_ADDRESS,
    settings,
)
from backend.app.services.payment_signing import usdc_to_raw
from backend.app.services.wallet_utils import normalize_address

logger = logging.getLogger("QMA-Euthyna-Audit")

_EUTHYNA_LOCK = threading.Lock()

# Canonical audit actions. Historical rows were written under rail-specific
# spellings (Earn Kit used SWEEP_IDLE/JIT_REDEEM, the treasury API uses
# IDLE_SWEEP/JIT_REDEMPTION); new writes are canonicalized here and reads
# expand aliases so both generations aggregate under one action.
ACTION_ALIASES: Dict[str, str] = {
    "SWEEP_IDLE": "IDLE_SWEEP",
    "JIT_REDEEM": "JIT_REDEMPTION",
}


def canonical_action(action: Optional[str]) -> str:
    return ACTION_ALIASES.get(str(action or "").strip(), str(action or "").strip())


def _action_filter_candidates(action_filter: str) -> List[str]:
    """Return the canonical action plus every alias that maps to it."""
    canonical = canonical_action(action_filter)
    candidates = {canonical, str(action_filter).strip()}
    for alias, target in ACTION_ALIASES.items():
        if target == canonical:
            candidates.add(alias)
    return [c for c in candidates if c]


def _get_storage():
    try:
        from backend.app.main import storage_backend
        return storage_backend
    except Exception:
        return None


class EuthynaAuditEngine:
    """Continuous enterprise audit and regulatory compliance engine."""

    def __init__(self, audit_file: Optional[Path] = None):
        self._custom_audit_file = audit_file is not None
        self._audit_file = audit_file or getattr(settings, "euthyna_audit_path", Path("euthyna_audit_trail.json"))
        self._records: List[Dict[str, Any]] = []
        self._load_records()

    def _is_custom_audit_file(self) -> bool:
        if getattr(self, "_custom_audit_file", False):
            return True
        if self._audit_file is None:
            return False
        try:
            return Path(self._audit_file).resolve() != Path("euthyna_audit_trail.json").resolve()
        except Exception:
            return False

    def _load_records(self) -> None:
        """Load persistent audit records from the storage backend, or disk only
        when no backend is configured (standalone scripts and tests)."""
        if not self._is_custom_audit_file():
            st = _get_storage()
            if st is not None and hasattr(st, "load_euthyna_records"):
                try:
                    db_recs = st.load_euthyna_records(limit=5000)
                except Exception as exc:
                    # A database read failure must never silently fall back to a
                    # stale local file: the database is the audit source of truth.
                    logger.error(f"[EUTHYNA AUDIT] Storage backend read failed: {exc}")
                    self._records = []
                    return
                self._records = list(reversed(db_recs)) if isinstance(db_recs, list) else []
                if self._records:
                    logger.info(f"[EUTHYNA AUDIT] Loaded {len(self._records)} persistent audit records from storage backend")
                return

        if self._audit_file and self._audit_file.exists():
            try:
                with open(self._audit_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._records = data
                        logger.info(f"[EUTHYNA AUDIT] Loaded {len(self._records)} persistent audit records from {self._audit_file}")
            except Exception as exc:
                logger.warning(f"[EUTHYNA AUDIT] Could not load records from {self._audit_file}: {exc}")

    def _persist_records(self) -> None:
        """Atomically persist audit records to disk."""
        if not self._audit_file:
            return
        try:
            self._audit_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self._audit_file.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self._records, f, indent=2)
            tmp_file.replace(self._audit_file)
        except Exception as exc:
            logger.error(f"[EUTHYNA AUDIT] Failed to persist audit trail to {self._audit_file}: {exc}")

    def record_action(
        self,
        action: str,
        actor: str,
        amount_usdc: float,
        balance_before: float,
        balance_after: float,
        usyc_shares: float,
        policy_rule: str,
        reasoning: str,
        tx_hash: Optional[str] = None,
        provider_id: Optional[str] = None,
        genlayer_consensus: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an immutable audit entry."""
        action = canonical_action(action)
        record_id = f"euthyna_{uuid.uuid4().hex[:12]}"
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        norm_actor = normalize_address(actor)
        rounded_amount = round(amount_usdc, 6)
        rounded_before = round(balance_before, 6)
        rounded_after = round(balance_after, 6)
        rounded_shares = round(usyc_shares, 6)
        clean_tx = tx_hash.strip() if (tx_hash and isinstance(tx_hash, str) and tx_hash.strip()) else None
        arcscan_link = f"{ARC_EXPLORER}/tx/{clean_tx}" if clean_tx else None

        # Determine predecessor hash for tamper-evident hash chaining
        with _EUTHYNA_LOCK:
            from backend.app.core.state import cross_process_lock

            with cross_process_lock("euthyna_audit_trail"):
                self._load_records()
                prev_hash = "GENESIS"
                if self._records:
                    prev_hash = self._records[-1].get("integrity_hash", "GENESIS")

                # Balance continuity check for the same actor
                prev_actor_record = next(
                    (r for r in reversed(self._records) if r.get("actor") == norm_actor), None
                )
                if prev_actor_record is not None and prev_actor_record.get("treasury_liquid_after") is not None:
                    prev_after = prev_actor_record["treasury_liquid_after"]
                    if abs(prev_after - rounded_before) > 0.000001:
                        logger.warning(
                            f"[EUTHYNA AUDIT] Balance continuity detected for actor {norm_actor}: "
                            f"previous liquid after = {prev_after}, current liquid before = {rounded_before}"
                        )

                # Cryptographic integrity digest with chained previous_hash
                tx_str = clean_tx or ""
                payload_to_hash = (
                    f"{prev_hash}|{record_id}|{timestamp}|{action}|{norm_actor}|{rounded_amount}|"
                    f"{rounded_before}|{rounded_after}|{rounded_shares}|{tx_str}"
                )
                record_hash = hashlib.sha256(payload_to_hash.encode("utf-8")).hexdigest()

                # Differentiate between live on-chain settlement vs simulated/prepared intent
                status = "LIVE_SETTLED" if clean_tx else "DRY_RUN_SIMULATED"

                entry = {
                    "record_id": record_id,
                    "previous_hash": prev_hash,
                    "timestamp": timestamp,
                    "action": action,
                    "actor": norm_actor,
                    "amount_usdc": rounded_amount,
                    "treasury_liquid_before": rounded_before,
                    "treasury_liquid_after": rounded_after,
                    "usyc_vault_shares": rounded_shares,
                    "tx_hash": clean_tx,
                    "arcscan_url": arcscan_link,
                    "policy_rule_applied": policy_rule,
                    "cfo_reasoning": reasoning,
                    "provider_id": provider_id,
                    "genlayer_consensus": genlayer_consensus,
                    "integrity_hash": record_hash,
                    "status": status,
                }

                self._records.append(entry)
                if self._is_custom_audit_file():
                    self._persist_records()
                else:
                    st = _get_storage()
                    if st is None or not hasattr(st, "save_euthyna_record"):
                        # No storage backend configured: the local file is the ledger.
                        self._persist_records()
                    else:
                        try:
                            st.save_euthyna_record(entry)
                        except Exception as exc:
                            logger.critical(f"[EUTHYNA AUDIT] Failed to save euthyna record to storage backend: {exc}")
                            raise

                logger.info(f"[EUTHYNA AUDIT] Recorded {action} [{status}] for {actor}: {amount_usdc} USDC -> {clean_tx or 'INTERNAL'}")
                return entry

    def get_audit_trail(
        self,
        limit: int = 50,
        action_filter: Optional[str] = None,
        actor_filter: Optional[str] = None,
        only_live: bool = False,
    ) -> List[Dict[str, Any]]:
        """Retrieve historical audit trail sorted descending by timestamp."""
        if not self._is_custom_audit_file():
            st = _get_storage()
            if st and hasattr(st, "load_euthyna_records"):
                try:
                    if action_filter:
                        # Historical rows may use alias spellings, so query each
                        # candidate and merge under one ordered result.
                        merged: List[Dict[str, Any]] = []
                        seen_ids: set = set()
                        for candidate in _action_filter_candidates(action_filter):
                            rows = st.load_euthyna_records(
                                limit=limit,
                                action_filter=candidate,
                                actor_filter=actor_filter,
                                only_live=only_live,
                            ) or []
                            for row in rows:
                                record_key = row.get("record_id") or id(row)
                                if record_key in seen_ids:
                                    continue
                                seen_ids.add(record_key)
                                merged.append(row)
                        merged.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
                        return merged[:limit]
                    db_records = st.load_euthyna_records(
                        limit=limit,
                        action_filter=action_filter,
                        actor_filter=actor_filter,
                        only_live=only_live,
                    )
                    if db_records is not None:
                        return db_records
                except Exception as exc:
                    logger.critical(f"[EUTHYNA AUDIT] Storage backend query failed: {exc}")
                    raise

        with _EUTHYNA_LOCK:
            results = self._records
            if only_live:
                results = [r for r in results if r.get("tx_hash")]
            if action_filter:
                allowed = {c.lower() for c in _action_filter_candidates(action_filter)}
                results = [r for r in results if str(r.get("action", "")).lower() in allowed]
            if actor_filter:
                norm_actor = normalize_address(actor_filter)
                results = [r for r in results if r["actor"].lower() == norm_actor.lower()]

            return list(reversed(results))[:limit]

    def _evaluate_integrity(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Cryptographically recompute integrity hashes and verify hash chain across records."""
        total = len(records)
        tampered = 0
        chain_broken = False
        last_hash = "GENESIS"

        for idx, r in enumerate(records):
            tx_str = r.get("tx_hash") or ""
            prev_hash = r.get("previous_hash")

            if prev_hash is not None:
                # Chained record verification
                if idx > 0 and prev_hash != last_hash:
                    tampered += 1
                    chain_broken = True
                payload = (
                    f"{prev_hash}|{r['record_id']}|{r['timestamp']}|{r['action']}|{r['actor']}|"
                    f"{r['amount_usdc']}|{r['treasury_liquid_before']}|"
                    f"{r['treasury_liquid_after']}|{r['usyc_vault_shares']}|{tx_str}"
                )
            else:
                # Backward-compatible unchained record verification for legacy entries
                payload = (
                    f"{r['record_id']}|{r['timestamp']}|{r['action']}|{r['actor']}|"
                    f"{r['amount_usdc']}|{r['treasury_liquid_before']}|"
                    f"{r['treasury_liquid_after']}|{r['usyc_vault_shares']}|{tx_str}"
                )

            expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if r.get("integrity_hash") != expected:
                tampered += 1

            last_hash = r.get("integrity_hash") or ""

        return {
            "total_audit_records": total,
            "tampered_records": tampered,
            "chain_broken": chain_broken,
            "audit_health": "PASSED" if tampered == 0 else "COMPROMISED",
            "settlement_chain": f"{PAYMENT_NETWORK_NAME} ({ARC_CHAIN_ID})",
            "treasury_anchor": PLATFORM_TREASURY_ADDRESS,
        }

    def verify_integrity(self) -> Dict[str, Any]:
        """Cryptographically recompute integrity hashes and verify hash chain across all records."""
        with _EUTHYNA_LOCK:
            mem_result = self._evaluate_integrity(self._records)
            if mem_result["audit_health"] == "COMPROMISED":
                return mem_result

            self._load_records()
            return self._evaluate_integrity(self._records)

    def reconcile_books(
        self,
        payment_events: Optional[List[Dict[str, Any]]] = None,
        treasury_position: Optional[Dict[str, Any]] = None,
        creator_claims_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Independent 3-Way Reconciliation between Ledger, Claims, and Treasury Assets.

        Enforces strict anti-silent-repair principles:
        - Exact integer micro-USDC (raw) comparisons without float drift
        - Declared tolerance = 0 (no hiding behind round-off expense accounts)
        - Explicit detection of imbalances (Surplus vs Deficit)
        - Automatic exclusion of fabricated/disputed records
        """
        from backend.app.services.payment_state_machine import (
            has_fabricated_settlement,
            payment_event_is_final,
        )

        if payment_events is None:
            try:
                from backend.app.repositories.storage import storage_backend, load_payment_ledger
                events = load_payment_ledger(storage_backend)
            except Exception:
                events = []
        else:
            events = payment_events

        # 1. Tally Ledger Events
        total_settled_raw = 0
        total_pending_batch_raw = 0
        disputed_records = 0
        seen_keys = set()

        for event in events:
            if not isinstance(event, dict):
                continue
            if has_fabricated_settlement(event) or str(event.get("settlement_id", "")).startswith(("DRY:", "x402_settle_")):
                disputed_records += 1
                continue

            key = str(event.get("settlement_id") or event.get("invoice_id") or "")
            if key and key in seen_keys:
                continue
            if key:
                seen_keys.add(key)

            raw_str = event.get("amount_raw")
            if raw_str is not None:
                try:
                    amount_raw = int(raw_str)
                except (ValueError, TypeError):
                    amount_raw = usdc_to_raw(event.get("amount_usdc", 0))
            else:
                amount_raw = usdc_to_raw(event.get("amount_usdc", 0))

            if payment_event_is_final(event):
                total_settled_raw += amount_raw
            else:
                total_pending_batch_raw += amount_raw

        # 2. Treasury Reserves
        if treasury_position is None:
            try:
                from backend.app.services.usyc_treasury import usyc_treasury_service
                pos = usyc_treasury_service.query_onchain_position(PLATFORM_TREASURY_ADDRESS)
            except Exception:
                pos = {"usdc_equivalent": 0.0, "usyc_shares": 0.0}
        else:
            pos = treasury_position

        treasury_usdc_equiv = float(pos.get("usdc_equivalent", 0.0))
        treasury_liquid_raw = usdc_to_raw(pos.get("treasury_liquid_usdc", treasury_usdc_equiv))

        # 3. Claims Obligations
        claims_paid_raw = 0
        claims_pending_raw = 0
        if creator_claims_data:
            claims_paid_raw = usdc_to_raw(creator_claims_data.get("paid_usdc", 0.0))
            claims_pending_raw = usdc_to_raw(creator_claims_data.get("pending_usdc", 0.0))

        # Net balance evaluation
        net_liabilities_raw = total_settled_raw - claims_paid_raw
        imbalance_raw = treasury_liquid_raw - net_liabilities_raw

        if imbalance_raw == 0:
            status = "PERFECTLY_RECONCILED"
            message = "All ledger obligations match verified treasury liquid assets exactly."
        elif imbalance_raw > 0:
            status = "SURPLUS_UNALLOCATED"
            message = f"Treasury liquid assets exceed net tracked ledger obligations by {imbalance_raw / 1_000_000:.6f} USDC."
        else:
            status = "DEFICIT_DISCREPANCY_DETECTED"
            message = f"CRITICAL: Treasury liquid assets are short by {abs(imbalance_raw) / 1_000_000:.6f} USDC."

        result = {
            "reconciliation_status": status,
            "message": message,
            "tolerance_raw": 0,
            "imbalance_raw": imbalance_raw,
            "imbalance_usdc": round(imbalance_raw / 1_000_000, 6),
            "ledger_metrics": {
                "total_settled_raw": total_settled_raw,
                "total_settled_usdc": round(total_settled_raw / 1_000_000, 6),
                "total_pending_batch_raw": total_pending_batch_raw,
                "total_pending_batch_usdc": round(total_pending_batch_raw / 1_000_000, 6),
                "disputed_records": disputed_records,
            },
            "claims_metrics": {
                "claims_paid_raw": claims_paid_raw,
                "claims_paid_usdc": round(claims_paid_raw / 1_000_000, 6),
                "claims_pending_raw": claims_pending_raw,
                "claims_pending_usdc": round(claims_pending_raw / 1_000_000, 6),
            },
            "treasury_metrics": {
                "treasury_liquid_raw": treasury_liquid_raw,
                "treasury_liquid_usdc": round(treasury_liquid_raw / 1_000_000, 6),
            },
            "audit_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # Record this in Euthyna immutable log
        self.record_action(
            action="RECONCILIATION_AUDIT",
            actor=PLATFORM_TREASURY_ADDRESS,
            amount_usdc=round(imbalance_raw / 1_000_000, 6),
            balance_before=round(treasury_liquid_raw / 1_000_000, 6),
            balance_after=round((treasury_liquid_raw - imbalance_raw) / 1_000_000, 6),
            usyc_shares=float(pos.get("usyc_shares", 0.0)),
            policy_rule="CONTINUOUS_THREE_WAY_RECONCILIATION",
            reasoning=f"Status: {status}. Imbalance: {result['imbalance_usdc']} USDC across {len(seen_keys)} events.",
        )

        return result


# Singleton audit engine
euthyna_audit_engine = EuthynaAuditEngine()
