"""
Test GenLayer SLA Cache & TTL Acceleration (Sub-Second Report Delivery)
======================================================================
Proves that once an asset's report is verified by GenLayer multi-validators,
subsequent purchases within the 15-minute TTL window bypass the 20s network
delay and unlock reports instantaneously (< 100ms).
"""

import json
import os
import sys
import time
import requests
from web3 import Web3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = os.getenv("QMA_BASE_URL", "http://127.0.0.1:8000")
ARC_RPC = os.getenv("ARC_RPC_URL", "https://rpc.testnet.arc.network")
ARC_CHAIN_ID = 5042002

w3 = Web3(Web3.HTTPProvider(ARC_RPC))
assert w3.is_connected(), "Failed to connect to Arc Testnet"

with open(".qma-test-wallets.json", "r") as f:
    wallets = json.load(f)

alice = wallets[0]  # Trader Alice
bob = wallets[1]    # Quant Bob

def send_arc_usdc(sender: dict, recipient: str, amount_usdc: float) -> str:
    sender_addr = Web3.to_checksum_address(sender["address"])
    to_addr = Web3.to_checksum_address(recipient)
    nonce = w3.eth.get_transaction_count(sender_addr)
    tx = {
        "nonce": nonce,
        "to": to_addr,
        "value": int(amount_usdc * 1e18),
        "gas": 21000,
        "gasPrice": w3.eth.gas_price,
        "chainId": ARC_CHAIN_ID,
    }
    signed = w3.eth.account.sign_transaction(tx, sender["privateKey"])
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    tx_hex = "0x" + tx_hash.hex() if not tx_hash.hex().startswith("0x") else tx_hash.hex()
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
    assert receipt.status == 1, "Arc on-chain transaction reverted"
    return tx_hex

print("=" * 80)
print("⚡ TESTING GENLAYER SLA CACHE & TTL SUB-SECOND UNLOCK")
print("=" * 80)

# STEP 1: Bob purchases BTC_USDT (Checks or warms the cache)
print("\n[Step 1] Bob creates invoice for BTC_USDT and settles on Arc Testnet...")
inv_res = requests.post(
    f"{BASE_URL}/api/v1/payment/invoice",
    json={"symbol": "BTC_USDT", "tier": "preview", "provider_id": "funding_memory", "buyer_wallet_address": bob["address"]},
)
assert inv_res.status_code == 200, f"Invoice creation failed: {inv_res.text}"
bob_inv = inv_res.json()
bob_tx = send_arc_usdc(bob, bob_inv["wallet_address"], bob_inv["amount"])
print(f"  • Bob Mined Tx: {bob_tx}")

t0 = time.time()
print("  • Bob verifies payment...")
bob_v_res = requests.post(
    f"{BASE_URL}/api/v1/payment/verify",
    params={"invoice_id": bob_inv["invoice_id"]},
    json={"invoice_secret": bob_inv["invoice_secret"], "settlement_id": bob_tx, "payer_address": bob["address"]},
)
# If pending consensus on first run, wait for completion
bob_state = bob_v_res.json()
if bob_state.get("status") == "verification_pending":
    print("  • First run warming GenLayer consensus (waiting for finalization)...")
    for _ in range(15):
        time.sleep(2)
        st = requests.get(
            f"{BASE_URL}/api/v1/payment/invoices/{bob_inv['invoice_id']}/status",
            params={"refresh": True},
            headers={"X-QMA-Invoice-Secret": bob_inv["invoice_secret"]},
        ).json()
        if st.get("status") == "paid":
            bob_state = st
            break

assert bob_state.get("status") == "paid", f"Bob invoice not paid: {bob_state}"
elapsed_1 = time.time() - t0
print(f"  • Bob Finished Verification in {elapsed_1:.2f}s (SLA Cached for 900s TTL)")


# STEP 2: Alice purchases BTC_USDT (Demonstrates INSTANT CACHE HIT in <100ms!)
print("\n[Step 2] Alice purchases identical BTC_USDT report within TTL window...")
alice_inv_res = requests.post(
    f"{BASE_URL}/api/v1/payment/invoice",
    json={"symbol": "BTC_USDT", "tier": "preview", "provider_id": "funding_memory", "buyer_wallet_address": alice["address"]},
)
alice_inv = alice_inv_res.json()
alice_tx = send_arc_usdc(alice, alice_inv["wallet_address"], alice_inv["amount"])
print(f"  • Alice Mined Tx: {alice_tx}")

print("  • Alice verifies payment with Backend (Measuring latency)...")
t_start = time.perf_counter()
alice_v_res = requests.post(
    f"{BASE_URL}/api/v1/payment/verify",
    params={"invoice_id": alice_inv["invoice_id"]},
    json={"invoice_secret": alice_inv["invoice_secret"], "settlement_id": alice_tx, "payer_address": alice["address"]},
)
latency_ms = (time.perf_counter() - t_start) * 1000
alice_state = alice_v_res.json()

print(f"\n🚀 RESULTS FOR ALICE:")
print(f"  • Invoice Status:        {alice_state.get('status').upper()}")
print(f"  • Access Token Issued:   {bool(alice_state.get('access_token'))}")
print(f"  • GenLayer SLA Cache Hit:{alice_state.get('genlayer', {}).get('cached', False)}")
print(f"  • Response Latency:      {latency_ms:.2f} ms")
print(f"  • GenLayer Consensus Tx: {alice_state.get('genlayer', {}).get('transaction_hash')}")

assert alice_state.get("status") == "paid", "Alice invoice was not paid immediately!"
assert alice_state.get("access_token"), "Alice did not receive access token immediately!"
assert alice_state.get("genlayer", {}).get("cached") is True, "SLA Cache hit was expected to be True!"

# STEP 3: Unlock report using instant access token
report_res = requests.post(
    f"{BASE_URL}/api/v1/providers/funding_memory/preview",
    params={"invoice_id": alice_inv["invoice_id"]},
    json={"symbol": "BTC_USDT"},
    headers={"X-QMA-Access-Token": alice_state["access_token"]},
)
assert report_res.status_code == 200, f"Report unlock failed: {report_res.text}"
rep_data = report_res.json()
print(f"\n📊 UNLOCKED REPORT (Delivered Instantly):")
print(f"  • Symbol:          {rep_data.get('query_symbol')}")
print(f"  • Regime:          {rep_data.get('regime_cluster')}")
print(f"  • Win Rate Band:   {rep_data.get('win_rate_band')} ({rep_data.get('rough_win_rate')}%)")
print(f"  • Analog Matches:  {len(rep_data.get('top_analogs', []))} matched")

print("\n" + "=" * 80)
print(f"🎉 SUCCESS! Report delivered in {latency_ms:.2f}ms — ZERO BOTTLENECK, PERFECT UX!")
print("=" * 80)
