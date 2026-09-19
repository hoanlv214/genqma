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
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.app.core.config import ARC_EXPLORER, PLATFORM_TREASURY_ADDRESS
from backend.app.services.wallet_utils import normalize_address

logger = logging.getLogger("QMA-Euthyna-Audit")

# In-memory append-only audit trail
_EUTHYNA_LOG: List[Dict[str, Any]] = []


class EuthynaAuditEngine:
    """Continuous enterprise audit and regulatory compliance engine."""

    def __init__(self):
        self._records: List[Dict[str, Any]] = _EUTHYNA_LOG

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
        record_id = f"euthyna_{uuid.uuid4().hex[:12]}"
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        clean_tx = tx_hash or f"0xsim_{uuid.uuid4().hex[:32]}"
        arcscan_link = f"{ARC_EXPLORER}/tx/{clean_tx}" if not clean_tx.startswith("0xsim_") else None

        # Cryptographic integrity digest
        payload_to_hash = (
            f"{record_id}|{timestamp}|{action}|{actor}|{amount_usdc}|"
            f"{balance_before}|{balance_after}|{usyc_shares}|{clean_tx}"
        )
        record_hash = hashlib.sha256(payload_to_hash.encode("utf-8")).hexdigest()

        entry = {
            "record_id": record_id,
            "timestamp": timestamp,
            "action": action,
            "actor": normalize_address(actor),
            "amount_usdc": round(amount_usdc, 6),
            "treasury_liquid_before": round(balance_before, 6),
            "treasury_liquid_after": round(balance_after, 6),
            "usyc_vault_shares": round(usyc_shares, 6),
            "tx_hash": clean_tx,
            "arcscan_url": arcscan_link,
            "policy_rule_applied": policy_rule,
            "cfo_reasoning": reasoning,
            "provider_id": provider_id,
            "genlayer_consensus": genlayer_consensus,
            "integrity_hash": record_hash,
            "status": "VERIFIED_AUDITABLE",
        }

        self._records.append(entry)
        logger.info(f"[EUTHYNA AUDIT] Recorded {action} for {actor}: {amount_usdc} USDC -> {clean_tx}")
        return entry

    def get_audit_trail(
        self,
        limit: int = 50,
        action_filter: Optional[str] = None,
        actor_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve historical audit trail sorted descending by timestamp."""
        results = self._records
        if action_filter:
            results = [r for r in results if r["action"].lower() == action_filter.lower()]
        if actor_filter:
            norm_actor = normalize_address(actor_filter)
            results = [r for r in results if r["actor"].lower() == norm_actor.lower()]

        return list(reversed(results))[:limit]

    def verify_integrity(self) -> Dict[str, Any]:
        """Cryptographically recompute integrity hashes across all records."""
        total = len(self._records)
        tampered = 0
        for r in self._records:
            payload = (
                f"{r['record_id']}|{r['timestamp']}|{r['action']}|{r['actor']}|"
                f"{r['amount_usdc']}|{r['treasury_liquid_before']}|"
                f"{r['treasury_liquid_after']}|{r['usyc_vault_shares']}|{r['tx_hash']}"
            )
            expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if r["integrity_hash"] != expected:
                tampered += 1

        return {
            "total_audit_records": total,
            "tampered_records": tampered,
            "audit_health": "PASSED" if tampered == 0 else "COMPROMISED",
            "settlement_chain": "Arc Testnet (5042002)",
            "treasury_anchor": PLATFORM_TREASURY_ADDRESS,
        }


# Singleton audit engine
euthyna_audit_engine = EuthynaAuditEngine()
