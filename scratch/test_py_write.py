import os
import json
from dotenv import load_dotenv
load_dotenv()
from backend.app.services.genlayer_arbiter import _create_client, _contract_address

client, acct = _create_client()
print('Account address:', acct.address)
manifest = json.dumps({
    "claims": {"bias": "arbitrage"},
    "invoice_id": "inv_test_dryrun_py",
    "query_hash": "a76675178891a2acea7082da3531e6703a777a61eff2919e0a7c415674830d3c",
    "symbol": "BTC"
})
try:
    print('Testing write_contract with genlayer_py...')
    tx = client.write_contract(
        account=acct,
        address=_contract_address(),
        function_name="submit_and_verify",
        args=[
            "inv_test_dryrun_py",
            "0x2c03cd73ad36230a3c5be43d51d72fdca32f53d4",
            "0x3333333333333333333333333333333333333333",
            "BTC",
            "Test anomaly",
            "a76675178891a2acea7082da3531e6703a777a61eff2919e0a7c415674830d3c",
            "9f4857493ddee03f4348fc1256f3eff2623d6e85e7890b2756c8ec737e8c1b57",
            manifest,
            "https://contract.mexc.com/api/v1/contract/ticker?symbol=BTC_USDT"
        ],
        value=0
    )
    print("SUCCESS! Tx hash:", tx)
except Exception as e:
    print("write_contract exception:", type(e), e)
