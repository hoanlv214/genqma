import os
import sys
import json
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, '.')
from backend.app.services.genlayer_arbiter import _submit_via_node

payload = {
    "invoice_id": "inv_test_node_check",
    "buyer": "0xf5987818ebbee812eb730b6a395d66e664412cf5",
    "provider": "0xb40971a5d88f31c7b8d88bf93f7d044f1383bf01",
    "symbol": "BTC",
    "expected_anomaly": "Verify BTC market anomaly against live MEXC evidence: strategy=funding_arbitrage, declared_confidence=0.9",
    "query_hash": "2ff793fb01988e1f94630cee09e05f074a6d2370780695edf0001c95af936f84",
    "report_hash": "c875f3175ff6525dadabca4dbbe3dc29a8c80d5089d19784f506b587b38986d9",
    "verification_manifest": json.dumps({
        "claims": {
            "declared_confidence": 0.9,
            "recommended_strategy": "funding_arbitrage"
        },
        "invoice_id": "inv_test_node_check",
        "query_hash": "2ff793fb01988e1f94630cee09e05f074a6d2370780695edf0001c95af936f84",
        "symbol": "BTC"
    }),
    "evidence_url": "https://contract.mexc.com/api/v1/contract/funding_rate/BTC_USDT"
}

print("Running _submit_via_node...")
try:
    res = _submit_via_node(payload)
    print("Result from _submit_via_node:")
    print(json.dumps(res, indent=2))
except Exception as e:
    print("Error:", type(e), e)
