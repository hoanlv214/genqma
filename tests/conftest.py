"""Global Pytest configuration and shared fixtures for QMA API tests."""

import pytest
from fastapi.testclient import TestClient

import backend.app.main as app_module


@pytest.fixture
def api_client():
    """Provides a TestClient connected to the modular FastAPI application."""
    return TestClient(app_module.app)


@pytest.fixture
def reset_app_state():
    """Resets memory state (invoices, payment_events, paid_reports) before each test."""
    old_invoices = app_module.state.invoices_db
    old_events = app_module.state.payment_events
    old_reports = app_module.state.paid_reports

    app_module.state.invoices_db = {}
    app_module.state.payment_events = []
    app_module.state.paid_reports = {}

    yield

    app_module.state.invoices_db = old_invoices
    app_module.state.payment_events = old_events
    app_module.state.paid_reports = old_reports


@pytest.fixture(autouse=True)
def isolate_test_audit_trail(tmp_path):
    """Isolate euthyna audit trail so test runs don't pollute runtime audit trail file."""
    test_audit_file = tmp_path / "test_euthyna_audit.json"
    from backend.app.core.config import settings
    old_audit_path = settings.euthyna_audit_path
    object.__setattr__(settings, "euthyna_audit_path", test_audit_file)

    from backend.app.services.euthyna_audit import euthyna_audit_engine
    old_file = euthyna_audit_engine._audit_file
    old_records = list(euthyna_audit_engine._records)

    euthyna_audit_engine._audit_file = test_audit_file
    euthyna_audit_engine._records = []

    yield

    object.__setattr__(settings, "euthyna_audit_path", old_audit_path)
    euthyna_audit_engine._audit_file = old_file
    euthyna_audit_engine._records = old_records
