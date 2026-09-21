"""Real Arc Testnet/Circle/GenLayer integration, isolated from production storage.

Run with network access: python scripts/live_financial_integrity.py
Persists checkpoints under ignored scratch/ so reruns never blindly repay.
"""
import os
from pathlib import Path
import subprocess
import sys
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.core.config import load_local_env


def main():
    load_local_env()
    directory = ROOT / "scratch" / "live-financial-integrity"
    directory.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(QMA_DATA_DIR=str(directory), QMA_ARC_GATEWAY_URL="http://127.0.0.1:8768",
               QMA_BACKEND_INTERNAL_URL="http://127.0.0.1:8767", PORT="8768",
               QMA_RATE_LIMIT_ENABLED="false")
    for key in ("SUPABASE_URL", "QMA_SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "QMA_SUPABASE_SERVICE_ROLE_KEY"):
        env[key] = ""
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    processes, logs = [], []
    try:
        for name, command, health in [
            ("backend", [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8767", "--no-access-log"], "http://127.0.0.1:8767/api/v1/health"),
            ("gateway", ["node", "node_modules/tsx/dist/cli.mjs", "arc_gateway/server.ts"], "http://127.0.0.1:8768/health"),
        ]:
            # Never attach to or terminate an existing user service.
            import socket
            port = int(health.split(":")[-1].split("/")[0])
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    raise RuntimeError(f"Test port {port} is occupied")
            log = (directory / f"{name}.log").open("w", encoding="utf-8")
            logs.append(log)
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=flags)
            processes.append(process)
            for _ in range(60):
                if process.poll() is not None:
                    raise RuntimeError(f"{name} exited; inspect the private local log")
                try:
                    if requests.get(health, timeout=2).ok:
                        break
                except requests.RequestException:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError(f"{name} readiness timeout")
            print(f"{name}: ready", flush=True)
        completed = subprocess.run(["node", "scripts/live_financial_buyer.mjs"], cwd=ROOT, env=env,
                                   creationflags=flags, capture_output=True, text=True)
        # Only the buyer's deliberately sanitized structured output is public.
        print(completed.stdout, flush=True)
        return completed.returncode
    finally:
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        for log in logs:
            log.close()


if __name__ == "__main__":
    raise SystemExit(main())
