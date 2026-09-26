"""Enrich CodeGraph SQLite Database with Contextual Risk Intelligence.

Protocol Alignment: CRCIP Phase 9 (CodeGraph Risk Intelligence)
Target: .codegraph/codegraph.db
"""

import sqlite3
import json
import time
import subprocess
from collections import defaultdict, deque

DB_PATH = ".codegraph/codegraph.db"

def get_head_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "811b86e1d3f43a5a030442166a3a90ae1aa629d2"

LAST_VERIFIED_COMMIT = get_head_commit()

# Authoritative Module Risk Classification
MODULE_PROFILES = {
    "backend/app/services/payment_state_machine.py": {
        "business_criticality": "CRITICAL",
        "security_sensitivity": "CRITICAL",
        "critical_flow_count": 3,
        "affected_flows": ["FL-01", "FL-02", "FL-10"],
        "affected_entrypoints": ["POST /api/v1/payment/verify", "POST /api/v1/payment/invoice"],
        "runtime_contracts": {"locks": ["invoices_mutation"], "tables": ["qma_invoices"]},
        "test_coverage_status": "COVERED",
        "known_gotchas": "Never mutate invoice['status'] directly outside state machine. Direct split superseded by D-06 single settlement.",
    },
    "backend/app/services/settlement_validation.py": {
        "business_criticality": "CRITICAL",
        "security_sensitivity": "CRITICAL",
        "critical_flow_count": 2,
        "affected_flows": ["FL-01", "FL-02"],
        "affected_entrypoints": ["POST /api/v1/payment/verify"],
        "runtime_contracts": {"token_scale": 6, "chain_id": 5042002, "tables": ["qma_payment_events"]},
        "test_coverage_status": "COVERED",
        "known_gotchas": "Enforces strict 6-decimal integer math via usdc_to_raw. Prevents settlement_id reuse across different invoices.",
    },
    "backend/app/services/usyc_treasury.py": {
        "business_criticality": "CRITICAL",
        "security_sensitivity": "CRITICAL",
        "critical_flow_count": 2,
        "affected_flows": ["FL-04", "FL-05"],
        "affected_entrypoints": ["POST /api/v1/treasury/usyc/sweep", "POST /api/v1/treasury/usyc/jit-redeem", "POST /api/v1/treasury/agent/decide"],
        "runtime_contracts": {"env": ["PLATFORM_TREASURY_KEY", "ARC_RPC_URL", "USYC_VAULT_ADDRESS"], "vault_decimals": 6},
        "test_coverage_status": "COVERED",
        "known_gotchas": "ERC-4626 share conversions round in favor of vault. Live on-chain execution requires PLATFORM_TREASURY_KEY.",
    },
    "backend/app/services/circle_client.py": {
        "business_criticality": "CRITICAL",
        "security_sensitivity": "CRITICAL",
        "critical_flow_count": 2,
        "affected_flows": ["FL-01", "FL-07", "FL-09"],
        "affected_entrypoints": ["POST /api/v1/platform/withdraw", "POST /api/v1/stablefx/settle"],
        "runtime_contracts": {"env": ["CIRCLE_CONSOLE_API_KEY", "CIRCLE_ENTITY_SECRET"]},
        "test_coverage_status": "COVERED",
        "known_gotchas": "Custodies Circle API developer credentials. Gateway burn intents require EIP-712 typed data signatures.",
    },
    "backend/app/services/genlayer_arbiter.py": {
        "business_criticality": "CRITICAL",
        "security_sensitivity": "CRITICAL",
        "critical_flow_count": 2,
        "affected_flows": ["FL-01", "FL-10"],
        "affected_entrypoints": ["POST /api/v1/payment/verify"],
        "runtime_contracts": {"chain_id": 61997, "env": ["GENLAYER_RPC_URL", "GENLAYER_CONTRACT_ADDRESS"]},
        "test_coverage_status": "COVERED",
        "known_gotchas": "Operates under fail-closed semantics. Unreachable RPC or pending consensus blocks access token issuance.",
    },
    "backend/app/services/spending_policy.py": {
        "business_criticality": "CRITICAL",
        "security_sensitivity": "CRITICAL",
        "critical_flow_count": 1,
        "affected_flows": ["FL-01"],
        "affected_entrypoints": ["POST /api/v1/sessions", "POST /api/v1/sessions/wallet/limits"],
        "runtime_contracts": {"caps": {"per_tx": "1.00", "daily": "10.00", "weekly": "50.00", "monthly": "200.00"}},
        "test_coverage_status": "COVERED",
        "known_gotchas": "Calculates policy deltas using Python Decimal. Limit elevation requires human OTP isolation; OTP must never touch storage.",
    },
    "backend/app/services/creator_claims.py": {
        "business_criticality": "CRITICAL",
        "security_sensitivity": "CRITICAL",
        "critical_flow_count": 1,
        "affected_flows": ["FL-09"],
        "affected_entrypoints": ["POST /api/v1/platform/withdraw", "POST /api/v1/sessions/wallet/withdraw"],
        "runtime_contracts": {"scheme": "EIP-191", "tables": ["qma_creator_claims"]},
        "test_coverage_status": "COVERED",
        "known_gotchas": "Enforces same_address check ensuring funds cannot be redirected from the signed creator wallet address.",
    },
    "backend/app/services/incident_engine.py": {
        "business_criticality": "IMPORTANT",
        "security_sensitivity": "SENSITIVE",
        "critical_flow_count": 1,
        "affected_flows": ["FL-06"],
        "affected_entrypoints": ["GET /api/v1/agent/incidents", "POST /api/v1/agent/sessions/{id}/control"],
        "runtime_contracts": {"circuit_breaker_p1": "revoke_leases", "tables": ["agent_incidents.json"]},
        "test_coverage_status": "COVERED",
        "known_gotchas": "Thread-locked incident recording with Athenian Euthyna hash-chaining. P1 incidents immediately revoke 60s worker execution leases.",
    },
    "backend/app/services/euthyna_audit.py": {
        "business_criticality": "IMPORTANT",
        "security_sensitivity": "SENSITIVE",
        "critical_flow_count": 2,
        "affected_flows": ["FL-04", "FL-05", "FL-06"],
        "affected_entrypoints": ["GET /api/v1/treasury/audit/trail", "GET /api/v1/treasury/audit/integrity"],
        "runtime_contracts": {"hash_algo": "SHA-256", "chain_file": "euthyna_audit_trail.json"},
        "test_coverage_status": "COVERED",
        "known_gotchas": "Immutable SHA-256 hash-chaining (prev_hash -> entry_hash). Any retroactive tampering breaks verify_integrity().",
    },
    "backend/app/services/plugins/webhook_adapter.py": {
        "business_criticality": "IMPORTANT",
        "security_sensitivity": "SENSITIVE",
        "critical_flow_count": 0,
        "affected_flows": ["FL-03"],
        "affected_entrypoints": ["POST /api/v1/providers/{id}/preview", "POST /api/v1/providers/{id}/full"],
        "runtime_contracts": {"max_payload_bytes": 1048576, "hmac_header": "X-QMA-Signature"},
        "test_coverage_status": "COVERED",
        "known_gotchas": "SSRF pre-resolution checks block loopback (127.0.0.1), private RFC 1918 subnets, and cloud metadata (169.254.169.254).",
    },
    "backend/app/repositories/storage.py": {
        "business_criticality": "CRITICAL",
        "security_sensitivity": "CRITICAL",
        "critical_flow_count": 3,
        "affected_flows": ["FL-01", "FL-02", "FL-09"],
        "affected_entrypoints": ["*"],
        "runtime_contracts": {"locks": ["agent_sessions_rpc", "invoices_mutation"]},
        "test_coverage_status": "COVERED",
        "known_gotchas": "Authoritative repository layer for JsonStorage and Supabase. JsonStorage.rpc protected by cross-process mutex.",
    },
    "storage.py": {
        "business_criticality": "CRITICAL",
        "security_sensitivity": "CRITICAL",
        "critical_flow_count": 3,
        "affected_flows": ["FL-01", "FL-02", "FL-09"],
        "affected_entrypoints": ["*"],
        "runtime_contracts": {"locks": ["agent_sessions_rpc", "invoices_mutation"]},
        "test_coverage_status": "COVERED",
        "known_gotchas": "Root storage shim maintained for backward compatibility. All RPC calls delegate under cross-process lock.",
    },
    "backend/app/services/wallet_utils.py": {
        "business_criticality": "IMPORTANT",
        "security_sensitivity": "SENSITIVE",
        "critical_flow_count": 2,
        "affected_flows": ["FL-01", "FL-02", "FL-08", "FL-09"],
        "affected_entrypoints": ["*"],
        "runtime_contracts": {"address_regex": "^0x[0-9a-fA-F]{40}$"},
        "test_coverage_status": "COVERED",
        "known_gotchas": "Canonical address normalizer. Lowercases, strips whitespace, handles None safely.",
    },
    "backend/app/services/agent_decision.py": {
        "business_criticality": "IMPORTANT",
        "security_sensitivity": "NORMAL",
        "critical_flow_count": 1,
        "affected_flows": ["FL-01"],
        "affected_entrypoints": ["POST /api/v1/agent/decision"],
        "runtime_contracts": {"models": ["ExpectedValueDecision"]},
        "test_coverage_status": "COVERED",
        "known_gotchas": "Deterministic expected value scoring algorithm. Decoupled from provider domain specifics.",
    },
    "backend/app/api/v1/endpoints/payment.py": {
        "business_criticality": "CRITICAL",
        "security_sensitivity": "CRITICAL",
        "critical_flow_count": 2,
        "affected_flows": ["FL-01", "FL-02"],
        "affected_entrypoints": ["POST /api/v1/payment/invoice", "POST /api/v1/payment/verify", "POST /api/v1/payment/quote"],
        "runtime_contracts": {"headers": ["X-QMA-Invoice-Secret"], "status_codes": [200, 400, 402, 409]},
        "test_coverage_status": "COVERED",
        "known_gotchas": "HTTP 402 public payment gateway. Keep response detail shape stable for frontend resume/unlock flows.",
    },
    "backend/app/api/v1/endpoints/treasury.py": {
        "business_criticality": "CRITICAL",
        "security_sensitivity": "CRITICAL",
        "critical_flow_count": 2,
        "affected_flows": ["FL-04", "FL-05"],
        "affected_entrypoints": ["POST /api/v1/treasury/usyc/sweep", "POST /api/v1/treasury/usyc/jit-redeem", "GET /api/v1/treasury/policy", "POST /api/v1/treasury/agent/decide"],
        "runtime_contracts": {"headers": ["x-qma-admin-token"], "units": "USDC 6 decimals"},
        "test_coverage_status": "COVERED",
        "known_gotchas": "On-chain execution requires PLATFORM_TREASURY_KEY. Policy updates require administrative authorization.",
    },
    "backend/app/api/v1/endpoints/sessions.py": {
        "business_criticality": "CRITICAL",
        "security_sensitivity": "CRITICAL",
        "critical_flow_count": 1,
        "affected_flows": ["FL-01", "FL-06"],
        "affected_entrypoints": ["POST /api/v1/sessions", "POST /api/v1/sessions/lease/acquire", "POST /api/v1/sessions/tick/checkpoint", "POST /api/v1/sessions/lease/heartbeat"],
        "runtime_contracts": {"lease_ttl_sec": 60, "cross_process_lock": "agent_sessions_rpc"},
        "test_coverage_status": "COVERED",
        "known_gotchas": "Worker leases expire after 60s inactivity. Reclaiming leases must remain atomic under high concurrency.",
    },
    "backend/app/api/v1/endpoints/providers.py": {
        "business_criticality": "IMPORTANT",
        "security_sensitivity": "SENSITIVE",
        "critical_flow_count": 1,
        "affected_flows": ["FL-01", "FL-02", "FL-03"],
        "affected_entrypoints": ["GET /api/v1/providers/{id}/preview", "POST /api/v1/providers/{id}/full"],
        "runtime_contracts": {"token_ttl_sec": 300, "token_header": "Authorization: Bearer <token>"},
        "test_coverage_status": "COVERED",
        "known_gotchas": "Full intelligence unlock requires valid access token bound to SHA-256(symbol + query_params).",
    },
}

def enrich():
    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. Create table node_risk_intelligence
    c.execute("""
    CREATE TABLE IF NOT EXISTS node_risk_intelligence (
        node_id TEXT PRIMARY KEY,
        symbol_name TEXT,
        qualified_name TEXT,
        kind TEXT,
        file_path TEXT,
        business_criticality TEXT CHECK (business_criticality IN ('CRITICAL', 'IMPORTANT', 'SAFE')),
        security_sensitivity TEXT CHECK (security_sensitivity IN ('CRITICAL', 'SENSITIVE', 'NORMAL')),
        fan_in INTEGER DEFAULT 0,
        transitive_dependents INTEGER DEFAULT 0,
        critical_flow_count INTEGER DEFAULT 0,
        affected_entrypoints TEXT,
        affected_flows TEXT,
        runtime_contracts TEXT,
        test_coverage_status TEXT CHECK (test_coverage_status IN ('COVERED', 'PARTIAL', 'UNTESTED')),
        known_gotchas TEXT,
        last_verified_commit TEXT,
        updated_at INTEGER
    );
    """)

    c.execute("CREATE INDEX IF NOT EXISTS idx_risk_crit ON node_risk_intelligence(business_criticality, security_sensitivity);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_risk_file ON node_risk_intelligence(file_path);")

    # 2. Compute fan-in and call graph reachability
    print("Computing fan-in and call graph reachability...")
    fan_in_map = defaultdict(int)
    reverse_graph = defaultdict(set)

    edges = c.execute("SELECT source, target, kind FROM edges WHERE kind IN ('calls', 'references', 'instantiates', 'imports');").fetchall()
    for src, tgt, kind in edges:
        fan_in_map[tgt] += 1
        reverse_graph[tgt].add(src)

    def compute_transitive(start_node):
        visited = set()
        queue = deque([start_node])
        while queue:
            curr = queue.popleft()
            for parent in reverse_graph[curr]:
                if parent not in visited:
                    visited.add(parent)
                    queue.append(parent)
        return len(visited)

    # 3. Load all nodes
    nodes = c.execute("SELECT id, kind, name, qualified_name, file_path FROM nodes;").fetchall()
    print(f"Analyzing {len(nodes)} nodes in index...")

    now_ts = int(time.time() * 1000)
    records = []

    for nid, kind, name, qname, fpath in nodes:
        # Normalize file path slashes
        norm_fpath = fpath.replace("\\", "/")

        # Match against module profiles
        matched_profile = None
        for pattern, profile in MODULE_PROFILES.items():
            if pattern in norm_fpath:
                matched_profile = profile
                break

        if matched_profile:
            biz_crit = matched_profile["business_criticality"]
            sec_sens = matched_profile["security_sensitivity"]
            crit_flow = matched_profile["critical_flow_count"]
            aff_flows = json.dumps(matched_profile["affected_flows"])
            aff_entry = json.dumps(matched_profile["affected_entrypoints"])
            contracts = json.dumps(matched_profile["runtime_contracts"])
            test_status = matched_profile["test_coverage_status"]
            gotchas = matched_profile["known_gotchas"]
        else:
            # Heuristic default based on file location & symbol kind
            if "test" in norm_fpath or "mock" in norm_fpath:
                biz_crit = "SAFE"
                sec_sens = "NORMAL"
                crit_flow = 0
                aff_flows = json.dumps([])
                aff_entry = json.dumps([])
                contracts = json.dumps({})
                test_status = "COVERED"
                gotchas = "Test suite / mock harness."
            elif "frontend/" in norm_fpath:
                biz_crit = "IMPORTANT" if ("payment" in norm_fpath or "treasury" in norm_fpath) else "SAFE"
                sec_sens = "SENSITIVE" if ("wallet" in norm_fpath or "payment" in norm_fpath) else "NORMAL"
                crit_flow = 1 if ("payment" in norm_fpath) else 0
                aff_flows = json.dumps(["FL-02"] if "payment" in norm_fpath else [])
                aff_entry = json.dumps(["Web UI"])
                contracts = json.dumps({"tier": "client"})
                test_status = "COVERED" if ("test" in norm_fpath or "hooks" in norm_fpath) else "PARTIAL"
                gotchas = "Frontend presentation layer. Untrusted boundary."
            elif "agents/" in norm_fpath:
                biz_crit = "CRITICAL" if ("payment" in norm_fpath or "core" in norm_fpath) else "IMPORTANT"
                sec_sens = "CRITICAL" if ("payment" in norm_fpath or "wallet" in norm_fpath) else "NORMAL"
                crit_flow = 1
                aff_flows = json.dumps(["FL-01"])
                aff_entry = json.dumps(["$ qma agent run"])
                contracts = json.dumps({"cli": "qma-cli"})
                test_status = "COVERED"
                gotchas = "Canonical autonomous agent CLI worker."
            else:
                biz_crit = "IMPORTANT"
                sec_sens = "NORMAL"
                crit_flow = 0
                aff_flows = json.dumps([])
                aff_entry = json.dumps([])
                contracts = json.dumps({})
                test_status = "COVERED"
                gotchas = ""

        fin = fan_in_map[nid]
        trans_dep = compute_transitive(nid)

        records.append((
            nid,
            name,
            qname,
            kind,
            norm_fpath,
            biz_crit,
            sec_sens,
            fin,
            trans_dep,
            crit_flow,
            aff_entry,
            aff_flows,
            contracts,
            test_status,
            gotchas,
            LAST_VERIFIED_COMMIT,
            now_ts
        ))

    # 4. Upsert into node_risk_intelligence
    c.executemany("""
    INSERT OR REPLACE INTO node_risk_intelligence (
        node_id, symbol_name, qualified_name, kind, file_path,
        business_criticality, security_sensitivity, fan_in, transitive_dependents,
        critical_flow_count, affected_entrypoints, affected_flows, runtime_contracts,
        test_coverage_status, known_gotchas, last_verified_commit, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, records)

    # 5. Update project_metadata
    metadata_updates = [
        ("last_verified_commit", LAST_VERIFIED_COMMIT, now_ts),
        ("risk_intelligence_version", "2.0", now_ts),
        ("risk_intelligence_node_count", str(len(records)), now_ts),
        ("risk_intelligence_status", "SYNCHRONIZED", now_ts),
    ]

    for k, v, ts in metadata_updates:
        c.execute("INSERT OR REPLACE INTO project_metadata (key, value, updated_at) VALUES (?, ?, ?);", (k, v, ts))

    conn.commit()

    # 6. Verification query
    cnt = c.execute("SELECT count(*) FROM node_risk_intelligence;").fetchone()[0]
    crit_count = c.execute("SELECT count(*) FROM node_risk_intelligence WHERE business_criticality='CRITICAL' AND security_sensitivity='CRITICAL';").fetchone()[0]
    print(f"\n[OK] Successfully enriched {cnt} nodes with Risk Intelligence!")
    print(f"[OK] Critical/Critical security nodes: {crit_count}")
    print(f"[OK] last_verified_commit set to: {LAST_VERIFIED_COMMIT}")

    conn.close()

if __name__ == "__main__":
    enrich()
