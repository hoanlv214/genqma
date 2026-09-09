"""Compatibility views for existing QMA records."""

from backend.app.runtime.compat.legacy_qma import (
    LegacyAliasView,
    deliverable_to_legacy_report,
    entitlement_view_to_legacy,
    legacy_alias_view,
    legacy_entitlement_to_view,
    legacy_invoice_to_purchase_view,
    legacy_report_to_deliverable,
    purchase_view_to_legacy_invoice,
)

__all__ = [
    "LegacyAliasView",
    "deliverable_to_legacy_report",
    "entitlement_view_to_legacy",
    "legacy_alias_view",
    "legacy_entitlement_to_view",
    "legacy_invoice_to_purchase_view",
    "legacy_report_to_deliverable",
    "purchase_view_to_legacy_invoice",
]
