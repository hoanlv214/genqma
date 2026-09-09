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
