"""Run regression tests with real local JSON persistence isolated from user data."""
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="qma-financial-tests-") as directory:
        os.environ["QMA_DATA_DIR"] = directory
        for key in ("SUPABASE_URL", "QMA_SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "QMA_SUPABASE_SERVICE_ROLE_KEY"):
            os.environ[key] = ""
        os.environ["QMA_RATE_LIMIT_ENABLED"] = "false"
        os.environ["USER_LLM_API_KEY"] = ""
        import pytest
        args = sys.argv[1:] or [
            "tests/unit/test_financial_integrity.py", "tests/unit/test_payment_state_machine.py",
            "tests/unit/test_arc_verdict_settlement.py", "tests/unit/test_storage_double_claim.py",
            "tests/unit/test_genlayer_sla.py", "tests/unit/test_payment_signing_golden_vectors.py",
            "tests/api_v1/test_api_sessions.py", "tests/api_v1/test_api_agent.py",
            "tests/api_v1/test_api_reports_and_wallets.py", "tests/api_v1/test_api_platform_and_creators.py",
            "tests/api_v1/test_api_wallet_profile_nonce.py", "tests/api_v1/test_api_openapi_docs.py",
            "tests/unit/test_growth_pillars.py", "tests/unit/test_security_race_and_leakage.py",
            "tests/unit/test_x402_seller_and_openapi.py",
            "-q", "--tb=short",
        ]
        raise SystemExit(pytest.main([*args, "--basetemp", str(Path(directory) / "pytest")]))
