#!/usr/bin/env python3
"""Sync environment variables, resume services, and trigger deploys on Render.com across workspaces.

Usage:
  # View exact env var payload for each service without calling Render API
  python scripts/render_sync.py --dry-run

  # List all workspaces and their services
  python scripts/render_sync.py --api-key <KEY> --list

  # Sync env vars to a specific workspace (e.g. 'penn' or "Hoàn Lại Văn's Workspace")
  python scripts/render_sync.py --api-key <KEY> --workspace penn --sync-env

  # Sync env vars, resume any suspended service, and trigger deploy on workspace 'penn'
  python scripts/render_sync.py --api-key <KEY> --workspace penn --all --resume
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RENDER_API_BASE = "https://api.render.com/v1"


def load_env_file(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            trimmed = line.strip()
            if not trimmed or trimmed.startswith("#") or "=" not in trimmed:
                continue
            key, val = trimmed.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            env[key] = val
    return env


def build_service_env_configs(env: Dict[str, str]) -> Dict[str, Dict[str, str]]:
    """Builds the canonical environment variable dictionary for each service."""
    arc_gateway_internal_secret = env.get("QMA_ARC_GATEWAY_INTERNAL_SECRET", "pass")
    access_token_secret = env.get("QMA_ACCESS_TOKEN_SECRET", "replace-with-a-long-random-secret")
    split_url_secret = env.get("QMA_SPLIT_LEG_URL_SECRET", f"split-url:{access_token_secret}")
    split_receipt_secret = env.get("QMA_SPLIT_RECEIPT_SECRET", f"split-receipt:{access_token_secret}")

    api_public_url = "https://qma-api.onrender.com"
    arc_gateway_public_url = "https://qma-arc-gateway.onrender.com"
    frontend_url = "https://genqma.vercel.app"

    # 1. qma-api (FastAPI Python backend)
    api_vars = {
        "QMA_HISTORICAL_DB_PATH": env.get("QMA_HISTORICAL_DB_PATH", "data/sample_funding_historical_analysis.csv"),
        "QMA_BACKTEST_OUTCOME_PATH": env.get("QMA_BACKTEST_OUTCOME_PATH", "data/sample_trading_analysis.csv"),
        "QMA_ARC_GATEWAY_URL": arc_gateway_public_url,
        "QMA_ARC_GATEWAY_INTERNAL_SECRET": arc_gateway_internal_secret,
        "QMA_ARC_SELLER_ADDRESS": env.get("QMA_ARC_SELLER_ADDRESS", "0x23e7c029a287a83d80b2e084e008211658dda11d"),
        "QMA_ARC_SETTLEMENT_RECONCILE_SECONDS": "30",
        "QMA_FUNDING_MEMORY_OWNER_WALLET": env.get("QMA_FUNDING_MEMORY_OWNER_WALLET", "0xb40971a5d88f31c7b8d88bf93f7d044f1383bf01"),
        "QMA_OI_MEMORY_OWNER_WALLET": env.get("QMA_OI_MEMORY_OWNER_WALLET", env.get("QMA_FUNDING_MEMORY_OWNER_WALLET", "0xb40971a5d88f31c7b8d88bf93f7d044f1383bf01")),
        "QMA_ADMIN_WALLET": env.get("QMA_ADMIN_WALLET", "0x1c684cd494d940418e271d51c889486e27c0aed0"),
        "QMA_WITHDRAW_RELAYER_ADDRESS": env.get("QMA_WITHDRAW_RELAYER_ADDRESS", "0xe29d54cf74b3a3b0be7d2e2274e68539daab651b"),
        "QMA_WITHDRAW_RELAYER_PRIVATE_KEY": env.get("QMA_WITHDRAW_RELAYER_PRIVATE_KEY", ""),
        "QMA_WITHDRAW_MODE": env.get("QMA_WITHDRAW_MODE", "platform_relayed"),
        "SUPABASE_URL": env.get("SUPABASE_URL", ""),
        "SUPABASE_SERVICE_ROLE_KEY": env.get("SUPABASE_SERVICE_ROLE_KEY", ""),
        "SUPABASE_SCHEMA": env.get("SUPABASE_SCHEMA", "public"),
        "QMA_ACCESS_TOKEN_SECRET": access_token_secret,
        "QMA_SPLIT_LEG_URL_SECRET": split_url_secret,
        "QMA_SPLIT_RECEIPT_SECRET": split_receipt_secret,
        "QMA_ADMIN_TOKEN": env.get("QMA_ADMIN_TOKEN", "1"),
        "QMA_SETTLEMENT_RAIL": env.get("QMA_SETTLEMENT_RAIL", "circle_gateway_x402"),
        "QMA_DEFAULT_SETTLEMENT_MODE": env.get("QMA_DEFAULT_SETTLEMENT_MODE", "x402_direct_split"),
        "GENLAYER_NETWORK": env.get("GENLAYER_NETWORK", "studio-next"),
        "GENLAYER_RPC_ENDPOINT": env.get("GENLAYER_RPC_ENDPOINT", "https://studio-next.genlayer.com/api"),
        "GENLAYER_CONTRACT_ADDRESS": env.get("GENLAYER_CONTRACT_ADDRESS", "0x1e5B4d7Be22A3f7F4Ecb616bA65123cB03B7cc13"),
        "GENLAYER_PRIVATE_KEY": env.get("GENLAYER_PRIVATE_KEY", ""),
        "QMA_MCP_API_BASE_URL": api_public_url,
        "QMA_MCP_CONNECT_BASE_URL": frontend_url,
        "QMA_LLM_PROVIDER": env.get("QMA_LLM_PROVIDER", "gemini"),
        "QMA_LLM_MODEL": env.get("QMA_LLM_MODEL", "gemini-2.5-flash"),
    }
    if env.get("OPENAI_API_KEY"):
        api_vars["OPENAI_API_KEY"] = env["OPENAI_API_KEY"]
    if env.get("GEMINI_API_KEY"):
        api_vars["GEMINI_API_KEY"] = env["GEMINI_API_KEY"]
    if env.get("DEEP_SEEK_API_KEY"):
        api_vars["DEEP_SEEK_API_KEY"] = env["DEEP_SEEK_API_KEY"]
    if env.get("GROQ_API_KEY"):
        api_vars["GROQ_API_KEY"] = env["GROQ_API_KEY"]
    if env.get("OPENROUTER_API_KEY"):
        api_vars["OPENROUTER_API_KEY"] = env["OPENROUTER_API_KEY"]

    # 2. qma-arc-gateway (Node.js Express service)
    gateway_vars = {
        "QMA_BACKEND_INTERNAL_URL": api_public_url,
        "QMA_ARC_GATEWAY_INTERNAL_SECRET": arc_gateway_internal_secret,
        "QMA_SPLIT_LEG_URL_SECRET": split_url_secret,
        "QMA_SPLIT_RECEIPT_SECRET": split_receipt_secret,
        "QMA_ARC_SELLER_ADDRESS": env.get("QMA_ARC_SELLER_ADDRESS", "0x23e7c029a287a83d80b2e084e008211658dda11d"),
        "CIRCLE_CONSOLE_API_KEY": env.get("CIRCLE_CONSOLE_API_KEY", ""),
        "CIRCLE_ENTITY_SECRET": env.get("CIRCLE_ENTITY_SECRET", ""),
        "TREASURY_WALLET_ID": env.get("TREASURY_WALLET_ID", ""),
        "QMA_GATEWAY_MAX_FEE_RAW": env.get("QMA_GATEWAY_MAX_FEE_RAW", "2010000"),
        "QMA_WITHDRAW_RELAYER_ADDRESS": env.get("QMA_WITHDRAW_RELAYER_ADDRESS", "0xe29d54cf74b3a3b0be7d2e2274e68539daab651b"),
        "QMA_WITHDRAW_RELAYER_PRIVATE_KEY": env.get("QMA_WITHDRAW_RELAYER_PRIVATE_KEY", ""),
        "QMA_CIRCLE_GATEWAY_API": env.get("QMA_CIRCLE_GATEWAY_API", "https://gateway-api-testnet.circle.com"),
        "QMA_ARC_EXPLORER": env.get("QMA_ARC_EXPLORER", "https://testnet.arcscan.app"),
    }
    if env.get("QMA_GATEWAY_DELEGATE_WALLET_ID"):
        gateway_vars["QMA_GATEWAY_DELEGATE_WALLET_ID"] = env["QMA_GATEWAY_DELEGATE_WALLET_ID"]
    if env.get("QMA_GATEWAY_DELEGATE_ADDRESS"):
        gateway_vars["QMA_GATEWAY_DELEGATE_ADDRESS"] = env["QMA_GATEWAY_DELEGATE_ADDRESS"]

    # 3. qma-agent-worker (Node.js background worker)
    worker_vars = {
        "API_BASE_URL": api_public_url,
        "QMA_API_URL": api_public_url,
        "QMA_ARC_GATEWAY_URL": arc_gateway_public_url,
        "QMA_ARC_GATEWAY_INTERNAL_SECRET": arc_gateway_internal_secret,
        "QMA_WORKER_MAX_CONCURRENT_SESSIONS": env.get("QMA_WORKER_MAX_CONCURRENT_SESSIONS", "10"),
        "AGENT_PRIVATE_KEY": env.get("AGENT_PRIVATE_KEY", ""),
        "QMA_LLM_PROVIDER": env.get("QMA_LLM_PROVIDER", "gemini"),
        "QMA_LLM_MODEL": env.get("QMA_LLM_MODEL", "gemini-2.5-flash"),
        "PORT": "10000",
    }
    if env.get("QMA_API_KEY"):
        worker_vars["QMA_API_KEY"] = env["QMA_API_KEY"]
    elif env.get("QMA_ADMIN_TOKEN"):
        worker_vars["QMA_API_KEY"] = env["QMA_ADMIN_TOKEN"]
    if env.get("OPENAI_API_KEY"):
        worker_vars["OPENAI_API_KEY"] = env["OPENAI_API_KEY"]
    if env.get("GEMINI_API_KEY"):
        worker_vars["GEMINI_API_KEY"] = env["GEMINI_API_KEY"]
    if env.get("GROQ_API_KEY"):
        worker_vars["GROQ_API_KEY"] = env["GROQ_API_KEY"]
    if env.get("OPENROUTER_API_KEY"):
        worker_vars["OPENROUTER_API_KEY"] = env["OPENROUTER_API_KEY"]

    return {
        "qma-api": api_vars,
        "qma-arc-gateway": gateway_vars,
        "qma-agent-worker": worker_vars,
    }


def render_request(method: str, path: str, api_key: str, data: Optional[Any] = None) -> Any:
    url = f"{RENDER_API_BASE}{path}"
    req = urllib.request.Request(
        url=url,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")

    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as err:
        error_body = err.read().decode("utf-8")
        print(f"[-] Render API HTTP {err.code} on {method} {path}: {error_body}", file=sys.stderr)
        raise
    except Exception as err:
        print(f"[-] Request failed: {err}", file=sys.stderr)
        raise


def mask_secret(key: str, val: str) -> str:
    if not val:
        return "<EMPTY>"
    secret_keywords = ("KEY", "SECRET", "PASSWORD", "PRIVATE", "TOKEN")
    if any(k in key.upper() for k in secret_keywords) and len(val) > 8:
        return f"{val[:4]}...{val[-4:]}"
    return val


def get_all_workspaces_and_services(api_key: str) -> List[Tuple[dict, List[dict]]]:
    """Returns a list of tuples: (owner_dict, list_of_services)."""
    owners_res = render_request("GET", "/owners?limit=100", api_key) or []
    owners = [item.get("owner", item) for item in owners_res]
    if not owners:
        # Fallback: query /services without ownerId
        direct_services = render_request("GET", "/services?limit=100", api_key) or []
        svcs = [s.get("service", s) for s in direct_services]
        return [({"id": "default", "name": "Default Workspace"}, svcs)]

    result = []
    for owner in owners:
        owner_id = owner.get("id")
        services_res = render_request("GET", f"/services?ownerId={owner_id}&limit=100", api_key) or []
        svcs = [s.get("service", s) for s in services_res]
        result.append((owner, svcs))
    return result


def main():
    parser = argparse.ArgumentParser(description="Sync env vars and deploy QMA services on Render across workspaces")
    parser.add_argument("--api-key", default=os.getenv("RENDER_API_KEY", ""), help="Render API key (rnd_...)")
    parser.add_argument("--env-file", default=".env", help="Path to local .env file (default: .env)")
    parser.add_argument("--workspace", default="", help="Target specific workspace name or ID (e.g. 'penn')")
    parser.add_argument("--dry-run", action="store_true", help="Print env var configs without calling Render API")
    parser.add_argument("--list", action="store_true", help="List all Render workspaces and services")
    parser.add_argument("--distributed", action="store_true", help="Target active distributed services across workspaces: qma-api & qma-arc-gateway in Workspace 1, qma-agent-worker in Workspace 2")
    parser.add_argument("--sync-env", action="store_true", help="Sync environment variables to target services")
    parser.add_argument("--deploy", action="store_true", help="Trigger deploy for target services")
    parser.add_argument("--status", action="store_true", help="Check status of latest deployment for target services")
    parser.add_argument("--resume", action="store_true", help="Resume (un-suspend) any suspended target services")
    parser.add_argument("--inspect", default="", help="Inspect current env vars on Render for a service or 'all'")
    parser.add_argument("--all", action="store_true", help="Sync env vars, resume suspended services, and trigger redeploy")

    args = parser.parse_args()

    env_path = Path(args.env_file)
    env = load_env_file(env_path)
    service_configs = build_service_env_configs(env)

    if args.dry_run or (not args.list and not args.sync_env and not args.deploy and not args.all and not args.inspect and not args.status):
        print("=" * 70)
        print("  QMA Render Services Configuration Preview (Dry Run)")
        print("=" * 70)
        for service_name, config in service_configs.items():
            print(f"\n[{service_name}] ({len(config)} environment variables):")
            for k, v in config.items():
                print(f"  {k:36} = {mask_secret(k, v)}")
        print("\n" + "=" * 70)
        print("Usage:")
        print("  python scripts/render_sync.py --api-key <KEY> --list")
        print("  python scripts/render_sync.py --api-key <KEY> --distributed --inspect all")
        print("  python scripts/render_sync.py --api-key <KEY> --distributed --sync-env")
        print("  python scripts/render_sync.py --api-key <KEY> --distributed --deploy")
        print("  python scripts/render_sync.py --api-key <KEY> --distributed --all")
        print("=" * 70)
        return

    api_key = args.api_key.strip()
    if not api_key:
        print("[-] Error: RENDER_API_KEY is required. Pass via --api-key <KEY> or set RENDER_API_KEY env var.", file=sys.stderr)
        sys.exit(1)

    print("[*] Connecting to Render API...")
    workspaces = get_all_workspaces_and_services(api_key)

    target_service_names = ["qma-api", "qma-arc-gateway", "qma-agent-worker"]

    print("\n" + "=" * 70)
    print(f"  Render Accounts / Workspaces Overview ({len(workspaces)} found)")
    print("=" * 70)

    for idx, (owner, services) in enumerate(workspaces, 1):
        owner_name = owner.get("name", "Unknown")
        owner_id = owner.get("id", "Unknown")
        owner_email = owner.get("email", "")
        print(f"\n[{idx}] Workspace: '{owner_name}' (ID: {owner_id}, Email: {owner_email})")
        print(f"    Total services: {len(services)}")
        for s in services:
            s_name = s.get("name", "")
            s_id = s.get("id", "")
            s_type = s.get("type", "")
            suspended = s.get("suspended")
            status_str = "SUSPENDED" if suspended == "suspended" or suspended is True else "DEPLOYED/ACTIVE"
            url = s.get("serviceDetails", {}).get("url", "")
            is_target = " [TARGET SERVICE]" if s_name in target_service_names else ""
            print(f"    - {s_name:25} (id={s_id}, status={status_str:15}, type={s_type}){is_target}")
            if url:
                print(f"      URL: {url}")

    if args.list:
        return

    # Select target services
    matched_services: Dict[str, dict] = {}

    if args.distributed or (not args.workspace):
        print("\n[*] Distributed architecture mode: finding active deployed services across workspaces...")
        # Auto-match active deployed services across all workspaces
        for name in target_service_names:
            deployed_svc = None
            any_svc = None
            for owner, svcs in workspaces:
                for s in svcs:
                    if s.get("name") == name:
                        is_suspended = s.get("suspended") == "suspended" or s.get("suspended") is True
                        s_info = {
                            "id": s.get("id"),
                            "name": name,
                            "workspace": owner.get("name"),
                            "workspace_id": owner.get("id"),
                            "suspended": is_suspended,
                            "url": s.get("serviceDetails", {}).get("url", ""),
                        }
                        if not is_suspended:
                            deployed_svc = s_info
                            break
                        if any_svc is None:
                            any_svc = s_info
                if deployed_svc:
                    break
            
            chosen = deployed_svc or any_svc
            if chosen:
                matched_services[name] = chosen
                status_str = "SUSPENDED" if chosen["suspended"] else "DEPLOYED/ACTIVE"
                print(f"    -> {name:20} => ID: {chosen['id']} [{status_str}] in '{chosen['workspace']}'")
            else:
                print(f"    -> [!] Service '{name}' not found in any workspace!")

    elif args.workspace:
        w_query = args.workspace.lower().strip()
        selected_owner = None
        selected_services = []
        for owner, svcs in workspaces:
            if w_query in owner.get("name", "").lower() or w_query == owner.get("id", "").lower():
                selected_owner = owner
                selected_services = svcs
                break
        if not selected_owner:
            print(f"\n[-] Error: Workspace '{args.workspace}' not found. Please choose one from the list above.", file=sys.stderr)
            sys.exit(1)

        print(f"\n[*] Operating on single Workspace: '{selected_owner.get('name')}' (ID: {selected_owner.get('id')})")
        for s in selected_services:
            s_name = s.get("name")
            if s_name in target_service_names:
                is_suspended = s.get("suspended") == "suspended" or s.get("suspended") is True
                matched_services[s_name] = {
                    "id": s.get("id"),
                    "name": s_name,
                    "workspace": selected_owner.get("name"),
                    "workspace_id": selected_owner.get("id"),
                    "suspended": is_suspended,
                    "url": s.get("serviceDetails", {}).get("url", ""),
                }

    if args.inspect:
        target = args.inspect.strip().lower()
        for name in target_service_names:
            if target not in ("all", name.lower()):
                continue
            if name not in matched_services:
                print(f"  [!] Service '{name}' not found in workspace.")
                continue
            svc_id = matched_services[name]["id"]
            current_vars = render_request("GET", f"/services/{svc_id}/env-vars", api_key) or []
            print(f"\n[Current Env Vars on Render for {name} (id={svc_id})]:")
            for item in current_vars:
                ev = item.get("envVar", item)
                k = ev.get("key", "")
                v = ev.get("value", "")
                print(f"  {k:36} = {mask_secret(k, v)}")
        return

    # Resume suspended services if requested
    if args.resume or args.all:
        print("\n[*] Checking for suspended services to resume...")
        for name in target_service_names:
            if name not in matched_services:
                continue
            svc = matched_services[name]
            svc_id = svc["id"]
            if svc.get("suspended") == "suspended" or svc.get("suspended") is True:
                print(f"  [*] Resuming suspended service {name} (id={svc_id})...")
                try:
                    render_request("POST", f"/services/{svc_id}/resume", api_key)
                    print(f"  [+] Service {name} resumed successfully.")
                except Exception as err:
                    print(f"  [-] Failed to resume {name}: {err}")
            else:
                print(f"  [i] Service {name} is already active.")

    # Sync env vars
    if args.sync_env or args.all:
        print("\n[*] Syncing environment variables (preserving existing custom keys)...")
        for name in target_service_names:
            if name not in matched_services:
                print(f"  [!] Service '{name}' not found in target selection. Skipping.")
                continue
            svc_id = matched_services[name]["id"]
            vars_dict = service_configs.get(name, {})

            # 1. Fetch current env vars from Render to preserve any service-specific existing keys
            current_vars_res = render_request("GET", f"/services/{svc_id}/env-vars", api_key) or []
            merged_dict: Dict[str, str] = {}
            for item in current_vars_res:
                ev = item.get("envVar", item)
                k = ev.get("key")
                v = ev.get("value")
                if k:
                    merged_dict[k] = v

            # 2. Overlay our canonical configuration
            added_keys = []
            updated_keys = []
            for k, v in vars_dict.items():
                if v:
                    if k not in merged_dict:
                        added_keys.append(k)
                    elif merged_dict[k] != v:
                        updated_keys.append(k)
                    merged_dict[k] = v

            env_payload = [{"key": k, "value": v} for k, v in merged_dict.items()]

            print(f"  [*] Updating {name} (id={svc_id}): total={len(env_payload)}, new={len(added_keys)}, modified={len(updated_keys)}...")
            if added_keys:
                print(f"      + Added: {', '.join(added_keys[:8])}{'...' if len(added_keys) > 8 else ''}")
            if updated_keys:
                print(f"      ~ Updated: {', '.join(updated_keys[:8])}{'...' if len(updated_keys) > 8 else ''}")

            try:
                render_request("PUT", f"/services/{svc_id}/env-vars", api_key, env_payload)
                print(f"  [+] {name} env vars updated successfully.")
            except Exception as err:
                print(f"  [-] Failed to update {name}: {err}")

    # Trigger deploys
    if args.deploy or args.all:
        print("\n[*] Triggering deployments...")
        for name in target_service_names:
            if name not in matched_services:
                continue
            svc_id = matched_services[name]["id"]
            print(f"  [*] Triggering deploy for {name} (id={svc_id})...")
            try:
                deploy = render_request("POST", f"/services/{svc_id}/deploys", api_key, {"clearCache": "do_not_clear"})
                deploy_id = deploy.get("id") if deploy else "unknown"
                print(f"  [+] Deploy triggered for {name}: deploy_id={deploy_id}")
            except Exception as err:
                print(f"  [-] Failed to trigger deploy for {name}: {err}")

    # Status check
    if args.status:
        print("\n[*] Checking deployment status for target services...")
        for name in target_service_names:
            if name not in matched_services:
                continue
            svc_id = matched_services[name]["id"]
            try:
                deploys = render_request("GET", f"/services/{svc_id}/deploys?limit=1", api_key) or []
                if deploys:
                    dep = deploys[0].get("deploy", deploys[0])
                    d_id = dep.get("id")
                    d_status = dep.get("status")
                    d_created = dep.get("createdAt")
                    d_finished = dep.get("finishedAt")
                    print(f"  - {name:20} (id={svc_id}): Deploy {d_id} => STATUS: {d_status} (created: {d_created}, finished: {d_finished})")
                else:
                    print(f"  - {name:20} (id={svc_id}): No deploy history found.")
            except Exception as err:
                print(f"  [-] Failed to get deploy status for {name}: {err}")

    print("\n[+] Done!")


if __name__ == "__main__":
    main()
