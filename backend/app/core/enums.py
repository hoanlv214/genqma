"""Canonical string-typed value sets for GenQMA.

Every member value is FROZEN to a literal already live in production storage
or wire format — adopting these enums must never change a serialized byte.
Each member cites one evidence site. Sets that failed verification during the
2026-10-02 preflight scan are intentionally absent (ProviderId,
SessionLeaseStatus — vocabularies still need an inventory pass); incident
severity/status live canonically in `backend.app.schemas.incidents`
(`IncidentSeverity`, `IncidentStatus` — import from there, do not redefine).
"""

from enum import Enum

__all__ = [
    "CFODecisionAction",
    "CreatorClaimStatus",
    "DecisionSource",
    "ERC8183JobStatus",
    "EuthynaAction",
    "EuthynaRecordStatus",
    "GatewayStatus",
    "GenLayerVerdict",
    "IncidentKind",
    "InvoiceStatus",
    "OperationType",
    "ReportTier",
    "SplitLegStatus",
    "TreasuryExecutionStatus",
    "YieldRail",
]


class DecisionSource(str, Enum):
    """Who authored a decision; surfaced as `decision_source` on payloads."""

    FAST_PARSER = "fast_parser"                       # agent_decision.py tier 0
    LAYA_SYSTEM_ONE = "laya_system_one"               # agent_decision.py tier 1
    LLM = "llm"                                       # agent_decision.py tier 2 (_llm_decision)
    SECURITY_SANITIZER = "security_sanitizer"         # agent_decision.py:744
    DETERMINISTIC_FALLBACK = "deterministic_fallback"  # agent_decision.py tier 3
    HEURISTIC = "heuristic"                           # evaluate_cfo_decision ladder
    MODEL = "model"                                   # reserved: CFO LLM proposal tier


class CFODecisionAction(str, Enum):
    """Allowed outcomes of evaluate_cfo_decision; LLM proposals are clamped to this set."""

    SWEEP_IDLE = "SWEEP_IDLE"            # usyc_treasury.py surplus branch
    JIT_REDEEM = "JIT_REDEEM"            # usyc_treasury.py liquidity-deficit branch
    HOLD_AND_EARN = "HOLD_AND_EARN"      # usyc_treasury.py equilibrium branch
    INSOLVENCY_ALERT = "INSOLVENCY_ALERT"  # usyc_treasury.py solvency branch


class TreasuryExecutionStatus(str, Enum):
    PREPARED = "PREPARED"                          # intent built, not yet on-chain
    CONFIRMED_ONCHAIN = "CONFIRMED_ONCHAIN"        # tx confirmed
    LEDGER_ONLY_SIMULATED = "LEDGER_ONLY_SIMULATED"  # earn_kit Morpho simulated mode
    NO_ACTION_REQUIRED = "NO_ACTION_REQUIRED"
    ALERT_EMITTED = "ALERT_EMITTED"


class CreatorClaimStatus(str, Enum):
    """Creator claim lifecycle (CLAIM_RESERVED_STATUSES, creator_claims.py:158)."""

    REQUESTED = "requested"      # providers.py claim endpoint initial status
    SUBMITTED = "submitted"      # relayed to arc_gateway
    PAID = "paid"                # payout confirmed
    FAILED = "failed"            # relay returned upstream 4xx (providers.py:380)
    UNKNOWN = "unknown"          # executor unavailable


class EuthynaRecordStatus(str, Enum):
    VERIFIED_AUDITABLE = "VERIFIED_AUDITABLE"  # schema default
    LIVE_SETTLED = "LIVE_SETTLED"              # euthyna_audit.py record with tx_hash
    DRY_RUN_SIMULATED = "DRY_RUN_SIMULATED"    # euthyna_audit.py prepared intent


class EuthynaAction(str, Enum):
    """Audit action tags. Values are hash-chain payload inputs: historical
    spellings stay (both sweep/redemption spellings exist in stored records).
    Dynamic family `f"AGENT_INCIDENT_{severity}"` (incident_engine) is handled
    by prefix check, not a member."""

    IDLE_SWEEP = "IDLE_SWEEP"                    # treasury sweep (usyc_treasury)
    SWEEP_IDLE = "SWEEP_IDLE"                    # earn_kit.py:652 Morpho rail
    JIT_REDEMPTION = "JIT_REDEMPTION"            # treasury JIT redeem
    JIT_REDEEM = "JIT_REDEEM"                    # earn_kit.py:810 Morpho rail
    X402_PAYMENT = "X402_PAYMENT"
    CREATOR_PAYOUT = "creator_payout"            # arc_verdict_settlement op name
    BUYER_REFUND = "buyer_refund"                # arc_verdict_settlement op name
    VENDOR_PAYOUT = "VENDOR_PAYOUT"              # backend/app/main.py:2231
    STABLEFX_SWAP = "STABLEFX_SWAP"
    RECONCILIATION_AUDIT = "RECONCILIATION_AUDIT"
    INCIDENT_RESOLVED = "INCIDENT_RESOLVED"


class InvoiceStatus(str, Enum):
    """Invoice lifecycle per payment_state_machine.py + docs/agent/PAYMENT_FLOW.md."""

    PENDING = "pending"
    SETTLEMENT_VERIFIED = "settlement_verified"
    VERIFICATION_PENDING = "verification_pending"
    PAID = "paid"
    PARTIAL_PAID = "partial_paid"
    DISPUTED = "disputed"                 # payment_state_machine.py:43-50
    VERIFICATION_REJECTED = "verification_rejected"
    REFUNDED = "refunded"                 # terminal, survives every save
    EXPIRED = "expired"


class GatewayStatus(str, Enum):
    """Circle Gateway settlement statuses (payment_state_machine.py:8-12)."""

    RECEIVED = "received"
    BATCHED = "batched"
    COMPLETED = "completed"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    CANCELED = "canceled"                 # spelling variant accepted via env config
    REVERTED = "reverted"
    EXPIRED_UNSETTLED = "expired_unsettled"


class YieldRail(str, Enum):
    USYC = "USYC"                         # ERC-4626 vault rail (usyc_treasury)
    EARN_KIT_MORPHO = "EARN_KIT_MORPHO"   # usyc_treasury.py yield_rail branch


class ReportTier(str, Enum):
    PREVIEW = "preview"
    FULL = "full"
    AUTO = "auto"                         # internal planning tier (recommendations)


class OperationType(str, Enum):
    """Arc verdict settlement operation names (arc_verdict_settlement.py:76+)."""

    CREATOR_PAYOUT = "creator_payout"
    BUYER_REFUND = "buyer_refund"
    VENDOR_PAYOUT = "VENDOR_PAYOUT"       # backend/app/main.py:2231


class IncidentKind(str, Enum):
    """Incident kind vocabulary. Open set — only spend_guard's two emitters are
    verified verbatim; extend with an evidence citation."""

    SPEND_LIMIT_EXCEEDED = "spend_limit_exceeded"        # spend_guard.py
    CIRCUIT_BREAKER_TRIPPED = "circuit_breaker_tripped"  # spend_guard.py


class ERC8183JobStatus(str, Enum):
    """Escrowed job lifecycle (schemas/agent.py Literal)."""

    READY = "ready"
    FUNDED = "funded"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SETTLED = "settled"


class SplitLegStatus(str, Enum):
    """Per-leg lifecycle in payment_state_machine.py. Open set — only these
    three are verified verbatim today."""

    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"


class GenLayerVerdict(str, Enum):
    """GenLayer consensus verdict (genlayer_arbiter.py, arc_verdict_settlement)."""

    VALID = "VALID"
    INVALID = "INVALID"
