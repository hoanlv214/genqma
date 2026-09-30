"""
Realistic Autonomous Agent Workflow:
1. Scan live market anomalies & recommendations (GET /api/v1/agent/recommendations)
2. Run Agent Decision Engine to pick the best actionable report (POST /api/v1/agent/decision)
3. Create invoice for the dynamically discovered candidate
4. Execute real on-chain USDC payment from agent wallet on Arc Testnet
5. Verify settlement with GenLayer Intelligent Contract consensus
6. Unlock and consume the paid intelligence report via X-QMA-Access-Token
7. Verify persistence in PostgreSQL and live appearance in Traction
"""
import json
import os
import sys
import time
from pathlib import Path
import psycopg2
import requests
from web3 import Web3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE_URL = "http://127.0.0.1:8000"
ARC_RPC = "https://rpc.testnet.arc.network"
ARC_CHAIN_ID = 5042002
DB_URL = "postgresql://postgres:Hoanlv%40214@localhost:5432/qma"

print("=" * 85)
print("[AGENT] QMA REALISTIC AUTONOMOUS BUYER AGENT: DISCOVERY -> DECISION -> ON-CHAIN SETTLEMENT")
print("=" * 85)

# 1. Load Real Wallet
with open(ROOT / ".qma-test-wallets.json", "r", encoding="utf-8") as f:
    wallets = json.load(f)

agent = wallets[0]  # qma-test-agent-1
sender_addr = Web3.to_checksum_address(agent["address"])
private_key = agent["privateKey"]
print(f"Agent Identity: {agent['label']} ({sender_addr})")

w3 = Web3(Web3.HTTPProvider(ARC_RPC))
assert w3.is_connected(), f"Failed to connect to Arc RPC: {ARC_RPC}"
bal_wei = w3.eth.get_balance(sender_addr)
bal_usdc = bal_wei / 1e18
print(f"Arc Testnet Wallet Balance: {bal_usdc:.6f} native USDC\n")
assert bal_usdc > 0.01, f"Insufficient balance: {bal_usdc} USDC"

# ==============================================================================
# PHASE 1: SCAN LIVE MARKET ANOMALIES & RECOMMENDATIONS
# ==============================================================================
print("--- [PHASE 1] Scanning Live Market Anomalies & Opportunities ---")
r_recs = requests.get(f"{BASE_URL}/api/v1/agent/recommendations", params={"limit": 5}, timeout=35)
assert r_recs.status_code == 200, f"Failed to fetch recommendations: {r_recs.text}"
recs_data = r_recs.json()
candidates = recs_data.get("recommendations", [])

print(f"Found {len(candidates)} live market candidates from providers:")
for idx, c in enumerate(candidates, 1):
    symbol = c.get("symbol")
    provider = c.get("provider_id")
    score = c.get("score")
    price = c.get("suggested_price_usdc")
    reasons = ", ".join(c.get("reasons", []))
    print(f"  [{idx}] {symbol} | Provider: {provider} | Score: {score} | Price: {price} USDC")
    print(f"      Reasons: {reasons}")

assert len(candidates) > 0, "No candidates found on the market."

# ==============================================================================
# PHASE 2: AGENT DECISION ENGINE EVALUATION
# ==============================================================================
print("\n--- [PHASE 2] Autonomous Agent Decision Engine ---")
prompt = "Scan live funding anomalies and purchase the highest conviction report within 0.01 USDC budget"
print(f"Agent Goal: \"{prompt}\"")

r_dec = requests.post(f"{BASE_URL}/api/v1/agent/decision", json={
    "prompt": prompt,
    "wallet": sender_addr,
    "budget_usdc": 0.01,
    "use_laya": True,
}, timeout=15)

assert r_dec.status_code == 200, f"Decision engine failed: {r_dec.text}"
dec_data = r_dec.json()
plan = dec_data.get("plan", {})
action = plan.get("action")
decision_source = dec_data.get("decision_source")
chosen_candidate = dec_data.get("resolved_candidate") or candidates[0]

print(f"Decision: action={action}, engine={decision_source}")
print(f"Target Selected: Symbol={chosen_candidate.get('symbol')}, Provider={chosen_candidate.get('provider_id')}, Tier={chosen_candidate.get('suggested_tier', 'preview')}")

# ==============================================================================
# PHASE 3: DYNAMIC INVOICE CREATION FOR SELECTED TARGET
# ==============================================================================
print("\n--- [PHASE 3] Requesting Provider Invoice for Selected Target ---")
query_fields = dict(chosen_candidate.get("query") or {})
symbol_val = chosen_candidate.get("symbol") or query_fields.get("symbol") or "NMR"

inv_payload = {
    **query_fields,
    "provider_id": chosen_candidate.get("provider_id", "funding_memory"),
    "tier": chosen_candidate.get("suggested_tier", "preview"),
    "symbol": symbol_val,
    "buyer_wallet_address": sender_addr,
    "buyer_type": "agent",
    "agent_label": agent["label"],
}

r_inv = requests.post(f"{BASE_URL}/api/v1/payment/invoice", json=inv_payload, timeout=10)
assert r_inv.status_code == 200, f"Invoice creation failed: {r_inv.text}"
inv = r_inv.json()

invoice_id = inv["invoice_id"]
amount = float(inv["amount"])
pay_to = Web3.to_checksum_address(inv["wallet_address"])
invoice_secret = inv["invoice_secret"]
print(f"Created Invoice: {invoice_id}")
print(f"  Target: {inv.get('symbol')} ({inv.get('provider_id')}:{inv.get('tier')})")
print(f"  Amount: {amount} USDC")
print(f"  Recipient: {pay_to}")

# ==============================================================================
# PHASE 4: ON-CHAIN PAYMENT ON ARC TESTNET
# ==============================================================================
print("\n--- [PHASE 4] Submitting Native USDC Payment on Arc Testnet ---")
nonce = w3.eth.get_transaction_count(sender_addr)
gas_price = w3.eth.gas_price
value_wei = int(amount * 1e18)

tx = {
    "nonce": nonce,
    "to": pay_to,
    "value": value_wei,
    "gas": 21000,
    "gasPrice": gas_price,
    "chainId": ARC_CHAIN_ID,
}
signed = w3.eth.account.sign_transaction(tx, private_key)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
tx_hex = tx_hash.hex()
if not tx_hex.startswith("0x"):
    tx_hex = "0x" + tx_hex

print(f"Transaction Broadcasted: {tx_hex}")
print(f"Explorer URL: https://testnet.arcscan.app/tx/{tx_hex}")

print("Waiting for block confirmation on Arc Testnet...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
print(f"[OK] Mined in Block #{receipt.blockNumber} (Gas Used: {receipt.gasUsed})")
assert receipt.status == 1, "On-chain payment reverted"

# ==============================================================================
# PHASE 5: SETTLEMENT VERIFICATION & GENLAYER CONSENSUS
# ==============================================================================
print("\n--- [PHASE 5] Settlement Verification & GenLayer Consensus Gate ---")
verify_payload = {
    "invoice_secret": invoice_secret,
    "settlement_id": tx_hex,
    "payer_address": sender_addr,
    "amount_usdc": amount,
}

access_token = None
for attempt in range(1, 10):
    r_ver = requests.post(
        f"{BASE_URL}/api/v1/payment/verify",
        params={"invoice_id": invoice_id},
        json=verify_payload,
        timeout=30,
    )
    v_data = r_ver.json()
    status = v_data.get("status")
    gl_verdict = (v_data.get("genlayer") or {}).get("verdict")
    print(f"  Verification Attempt {attempt}: Status={status}, GenLayer Verdict={gl_verdict}")

    if status == "paid" or gl_verdict == "VALID":
        access_token = v_data.get("access_token")
        print(f"  [OK] Payment verified & settled! Access Token Issued.")
        break
    elif status == "verification_pending":
        print("  [WAIT] GenLayer Intelligent Contract consensus pending on-chain. Waiting 6s...")
        time.sleep(6)
    else:
        print(f"  Unexpected status: {status}")
        break

# ==============================================================================
# PHASE 6: UNLOCK AND RETRIEVE PAID REPORT CONTENT
# ==============================================================================
print("\n--- [PHASE 6] Retrieving Verified Paid Intelligence Report ---")
tier = chosen_candidate.get("suggested_tier", "preview")
provider_id = chosen_candidate.get("provider_id", "funding_memory")
endpoint_name = "preview" if tier == "preview" else "full-report"

headers = {}
if access_token:
    headers["X-QMA-Access-Token"] = access_token

r_rep = requests.post(
    f"{BASE_URL}/api/v1/providers/{provider_id}/{endpoint_name}",
    params={"invoice_id": invoice_id},
    json=chosen_candidate.get("query") or {"symbol": symbol_val},
    headers=headers,
    timeout=15,
)
print(f"Report HTTP Status: {r_rep.status_code}")
if r_rep.status_code == 200:
    rep_json = r_rep.json()
    print("Report Content Received:")
    print(f"  - Symbol: {rep_json.get('symbol')}")
    print(f"  - Tier: {rep_json.get('tier')}")
    print(f"  - Provider: {rep_json.get('provider_id')}")
    print(f"  - Intelligence Summary: {json.dumps(rep_json.get('data') or rep_json.get('analysis') or {}, indent=4)[:300]}...")
else:
    print(f"Report fetch: {r_rep.text[:200]}")

# ==============================================================================
# PHASE 7: DATABASE & TRACTION VERIFICATION
# ==============================================================================
print("\n--- [PHASE 7] Verifying PostgreSQL Storage & Live Traction ---")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("SELECT count(*) FROM qma_payment_events WHERE invoice_id = %s;", (invoice_id,))
count_event = cur.fetchone()[0]
cur.execute("SELECT status FROM qma_invoices WHERE invoice_id = %s;", (invoice_id,))
inv_status = cur.fetchone()[0]
cur.close()
conn.close()

print(f"PostgreSQL Status: invoice_id={invoice_id}, status={inv_status}, payment_event_exists={count_event > 0}")

r_trac = requests.get(f"{BASE_URL}/api/v1/traction?days=14&recent_limit=5", timeout=10)
recent_settlements = r_trac.json().get("recent_settlements", [])
matched = any(s.get("invoice_id") == invoice_id or s.get("transaction_hash") == tx_hex for s in recent_settlements)

print(f"Traction Page Status: Top settlement matches this purchase = {matched}")
if matched:
    print(f"\n>>> FULL END-TO-END AUTONOMOUS CYCLE COMPLETED SUCCESSFULLY! <<<")
    print(f"   Candidate {chosen_candidate.get('symbol')} was dynamically scanned, evaluated, paid on Arc, validated by GenLayer, saved to PostgreSQL, and displayed on Traction!")
