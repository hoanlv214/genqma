#!/usr/bin/env python3
"""Sync frontend environment variables and trigger deployment on Vercel.

Usage:
  # View exact frontend env vars without calling Vercel API
  python scripts/vercel_sync.py --dry-run

  # Sync env vars to Vercel via API token
  python scripts/vercel_sync.py --token <VERCEL_TOKEN> --project genqma --sync-env

  # Sync env vars and deploy production frontend
  python scripts/vercel_sync.py --token <VERCEL_TOKEN> --project genqma --all

  # Using Vercel CLI (when already logged in via 'bun x vercel login')
  python scripts/vercel_sync.py --cli --sync-env --deploy
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

VERCEL_API_BASE = "https://api.vercel.com"


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


def build_frontend_env(env: Dict[str, str]) -> Dict[str, str]:
    api_url = env.get("QMA_API_PUBLIC_URL", "https://qma-api.onrender.com")
    genlayer_contract = env.get("GENLAYER_CONTRACT_ADDRESS", "0x1e5B4d7Be22A3f7F4Ecb616bA65123cB03B7cc13")
    studio_url = env.get("GENLAYER_STUDIO_URL", "https://studio-next.genlayer.com")
    explorer_url = env.get("GENLAYER_EXPLORER_URL", "https://explorer-studio-dev.genlayer.com")

    return {
        "VITE_QMA_API_BASE_URL": api_url,
        "VITE_QMA_MCP_PUBLIC_URL": api_url,
        "VITE_GENLAYER_CONTRACT_ADDRESS": genlayer_contract,
        "VITE_GENLAYER_STUDIO_URL": studio_url,
        "VITE_GENLAYER_EXPLORER_URL": explorer_url,
        "VITE_QMA_ENV": "production",
        "VITE_QMA_SYNTHETIC_RUN": "false",
    }


def vercel_request(method: str, path: str, token: str, team_id: Optional[str] = None, data: Optional[Any] = None) -> Any:
    sep = "&" if "?" in path else "?"
    url = f"{VERCEL_API_BASE}{path}"
    if team_id:
        url += f"{sep}teamId={team_id}"

    req = urllib.request.Request(
        url=url,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
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
        print(f"[-] Vercel API HTTP {err.code} on {method} {path}: {error_body}", file=sys.stderr)
        raise
    except Exception as err:
        print(f"[-] Request failed: {err}", file=sys.stderr)
        raise


def sync_via_vercel_cli(frontend_env: Dict[str, str], targets: List[str]) -> bool:
    """Sync env vars using 'bun x vercel env add' via CLI."""
    print("[*] Syncing environment variables using Vercel CLI (bun x vercel)...")
    for key, val in frontend_env.items():
        for target in targets:
            print(f"  [*] Setting {key} for target '{target}'...")
            try:
                # Pipe value into vercel env add <key> <target>
                proc = subprocess.run(
                    ["bun", "x", "vercel", "env", "add", key, target, "--force"],
                    input=f"{val}\n",
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if proc.returncode == 0:
                    print(f"  [+] {key} ({target}) set successfully.")
                else:
                    # Sometimes vercel asks differently or key already exists
                    err = proc.stderr.strip() or proc.stdout.strip()
                    print(f"  [-] Note for {key}: {err}")
            except Exception as e:
                print(f"  [-] CLI error setting {key}: {e}")
    return True


def sync_via_vercel_api(frontend_env: Dict[str, str], token: str, project_id: str, team_id: Optional[str] = None, targets: Optional[List[str]] = None) -> bool:
    """Sync env vars directly using Vercel REST API v10."""
    if targets is None:
        targets = ["production", "preview"]

    print(f"[*] Fetching existing env vars from Vercel for project '{project_id}'...")
    res = vercel_request("GET", f"/v10/projects/{project_id}/env", token, team_id) or {}
    existing_envs = res.get("envs", [])
    existing_by_key: Dict[str, dict] = {e.get("key"): e for e in existing_envs}

    print(f"[+] Found {len(existing_envs)} existing environment variables on Vercel.")

    for key, val in frontend_env.items():
        if key in existing_by_key:
            env_id = existing_by_key[key].get("id")
            current_val = existing_by_key[key].get("value")
            if current_val == val:
                print(f"  [i] {key:32} is already up to date.")
                continue
            print(f"  [*] Updating {key:32} = {val} (id={env_id})...")
            try:
                vercel_request(
                    "PATCH",
                    f"/v10/projects/{project_id}/env/{env_id}",
                    token,
                    team_id,
                    {"value": val, "target": targets, "type": "plain"},
                )
                print(f"  [+] Updated {key}.")
            except Exception as e:
                print(f"  [-] Failed to update {key}: {e}")
        else:
            print(f"  [*] Creating {key:32} = {val}...")
            try:
                vercel_request(
                    "POST",
                    f"/v10/projects/{project_id}/env",
                    token,
                    team_id,
                    {"key": key, "value": val, "target": targets, "type": "plain"},
                )
                print(f"  [+] Created {key}.")
            except Exception as e:
                print(f"  [-] Failed to create {key}: {e}")

    return True


def main():
    parser = argparse.ArgumentParser(description="Automate Vercel environment variables and deployment for QMA Frontend")
    parser.add_argument("--token", default=os.getenv("VERCEL_TOKEN", ""), help="Vercel Access Token")
    parser.add_argument("--project", default=os.getenv("VERCEL_PROJECT_ID", "genqma"), help="Vercel Project Name or ID (default: genqma)")
    parser.add_argument("--team-id", default=os.getenv("VERCEL_TEAM_ID", ""), help="Optional Vercel Team ID")
    parser.add_argument("--env-file", default=".env", help="Path to local .env file (default: .env)")
    parser.add_argument("--cli", action="store_true", help="Use Vercel CLI (bun x vercel) instead of REST API")
    parser.add_argument("--dry-run", action="store_true", help="Print frontend env vars payload without calling Vercel")
    parser.add_argument("--sync-env", action="store_true", help="Sync frontend environment variables to Vercel")
    parser.add_argument("--deploy", action="store_true", help="Deploy production build to Vercel via 'bun x vercel --prod'")
    parser.add_argument("--all", action="store_true", help="Sync env vars and deploy to Vercel Production")

    args = parser.parse_args()

    env_path = Path(args.env_file)
    env = load_env_file(env_path)
    frontend_env = build_frontend_env(env)

    if args.dry_run or (not args.sync_env and not args.deploy and not args.all):
        print("=" * 70)
        print("  QMA Frontend Vercel Environment Preview (Dry Run)")
        print("=" * 70)
        for k, v in frontend_env.items():
            print(f"  {k:36} = {v}")
        print("\n" + "=" * 70)
        print("Usage:")
        print("  # With Vercel Token (Recommended for CI/CD):")
        print("  python scripts/vercel_sync.py --token <TOKEN> --project genqma --all")
        print("\n  # With Vercel CLI (When logged in with 'bun x vercel login'):")
        print("  python scripts/vercel_sync.py --cli --all")
        print("=" * 70)
        return

    # Sync env vars
    if args.sync_env or args.all:
        if args.cli:
            sync_via_vercel_cli(frontend_env, ["production", "preview"])
        else:
            token = args.token.strip()
            if not token:
                print("[-] Error: VERCEL_TOKEN is required for API sync. Pass via --token <TOKEN> or use --cli.", file=sys.stderr)
                sys.exit(1)
            sync_via_vercel_api(frontend_env, token, args.project.strip(), args.team_id.strip() or None)

    # Deploy frontend
    if args.deploy or args.all:
        print("\n[*] Deploying frontend to Vercel Production ('bun x vercel --prod')...")
        try:
            cmd = ["bun", "x", "vercel", "--prod"]
            if args.token:
                cmd.extend(["--token", args.token.strip()])
            proc = subprocess.run(cmd, check=False)
            if proc.returncode == 0:
                print("\n[+] Vercel deployment completed successfully!")
            else:
                print(f"\n[-] Vercel deploy exited with code {proc.returncode}")
        except Exception as e:
            print(f"[-] Deployment failed: {e}", file=sys.stderr)

    print("\n[+] Done!")


if __name__ == "__main__":
    main()
