"""Pollution tripwire tests to verify pytest suite runs against isolated JSON storage."""

import os
from storage import JsonStorage
import backend.app.main as app_module


def test_tests_run_on_json_backend():
    assert os.environ.get("QMA_STORAGE_BACKEND") == "json"
    assert not os.environ.get("DATABASE_URL")
    assert not os.environ.get("POSTGRES_URL")
    assert not os.environ.get("QMA_DATABASE_URL")
    assert os.environ.get("QMA_DATA_DIR")


def test_main_storage_handle_is_json_storage():
    """Assert backend.app.main storage handle is JsonStorage with backend_name 'json'."""
    assert isinstance(app_module.storage_backend, JsonStorage)
    assert getattr(app_module.storage_backend, "backend_name", None) == "json"
