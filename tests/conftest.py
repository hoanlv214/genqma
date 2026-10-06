import os
import tempfile

os.environ["QMA_STORAGE_BACKEND"] = "json"          # forces Priority 2 in create_storage_backend
os.environ["QMA_SPEND_GUARD_LEDGER"] = "0"          # unit tests never exercise the durable spend ledger
os.environ["QMA_STABLEFX_LIVE_RATE"] = "0"          # unit tests never hit the live Hermes FX feed
os.environ["QMA_EARN_ONCHAIN_METRICS"] = "0"        # unit tests never read vault metrics over RPC
os.environ["QMA_EARN_SNAPSHOT_SAMPLER"] = "0"       # unit tests never start the background sampler
os.environ["QMA_SIGNAL_VERIFIABILITY_GATE"] = "0"  # unit tests never run the sale-time evidence gate
for _k in ("DATABASE_URL", "POSTGRES_URL", "QMA_DATABASE_URL"):
    os.environ.pop(_k, None)                        # cannot fall through to Postgres
_ISOLATION_DIR = tempfile.mkdtemp(prefix="qma_test_data_")
os.environ["QMA_DATA_DIR"] = _ISOLATION_DIR         # JSON ledgers land here, not repo root

"""Global Pytest configuration and shared fixtures for QMA API tests."""

import pytest
from fastapi.testclient import TestClient

import backend.app.main as app_module

# Ensure any env vars re-loaded by backend.app.core.config.load_local_env() are purged
for _k in ("DATABASE_URL", "POSTGRES_URL", "QMA_DATABASE_URL"):
    os.environ.pop(_k, None)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "storage_backend: mark test as requiring a real storage backend (Postgres/Supabase)"
    )


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


@pytest.fixture(autouse=True)
def isolate_test_treasury(tmp_path):
    """Isolate corporate treasury policy file and memory cache across test runs."""
    test_policy_file = tmp_path / "test_treasury_policy.json"
    from backend.app.core.config import settings
    old_policy_path = settings.treasury_policy_path
    object.__setattr__(settings, "treasury_policy_path", test_policy_file)

    from backend.app.services.usyc_treasury import usyc_treasury_service
    old_service_file = usyc_treasury_service._policy_file
    old_service_policy = usyc_treasury_service._policy

    usyc_treasury_service._policy_file = test_policy_file
    usyc_treasury_service._policy = None

    yield

    object.__setattr__(settings, "treasury_policy_path", old_policy_path)
    usyc_treasury_service._policy_file = old_service_file
    usyc_treasury_service._policy = old_service_policy

