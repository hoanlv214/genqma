# Modern Package Management Guide: `bun` & `uv`

QMA standardizes on modern, high-performance tooling for package management, dependency resolution, and runtime execution:

* **Monorepo & Frontend / Node Services**: Powered by **`bun`** (Fast TypeScript/JavaScript package manager, bundler & workspaces).
* **Backend (`backend/`)**: Powered by **`uv`** (Blazing-fast Rust-based Python package manager).

---

## 1. 1-Click Environment Setup & Service Runner

Anyone cloning the repository can set up and run the entire environment in seconds with 1-click scripts:

### Setup Environment (Scans system, installs missing tools & syncs all packages)
```powershell
# On Windows PowerShell:
.\setup.ps1

# On Linux / macOS (Bash):
chmod +x ./setup.sh && ./setup.sh
```

These scripts automatically:
1. Scan the environment (OS, Git, Python runtimes).
2. Auto-install `uv` and `bun` if missing on the machine.
3. Create `.venv` and install all Python dependencies via `uv pip install -r requirements.txt`.
4. Install all monorepo workspaces (`frontend`, `arc_gateway`, `agents`) via `bun install`.
5. Copy `.env.example` to `.env` if not already present.
6. Generate a comprehensive readiness checklist.

### Start All Services (Concurrent runner for Backend + Gateway + Frontend)
```powershell
# On Windows PowerShell:
.\start.ps1
# (To stop all running services on Windows: .\stop.ps1)

# On Linux / macOS (Bash):
chmod +x ./start.sh && ./start.sh
# (Press Ctrl+C to stop all services simultaneously)
```

> For production deployment without web interfaces, see the [CLI Deployment Guide](infrastructure/CLI_DEPLOYMENT.md).

---

## 2. Monorepo Workspaces with `bun`

Root `package.json` configures Bun workspaces:
```json
"workspaces": [
  "frontend",
  "arc_gateway",
  "agents"
]
```

### Common Commands from Root

```bash
# Install ALL dependencies across frontend, arc_gateway, agents in 1 shot:
bun install

# Run Frontend dev server:
bun run dev:frontend

# Build Frontend production bundle:
bun run build:frontend

# Run Arc Gateway server:
bun run dev:gateway

# Build all packages:
bun run build:all
```

### Why Bun for QMA?
1. **15-25x Faster Installs**: Parallelized cache, zero-copy symlinks, deterministic `bun.lockb`.
2. **Monorepo Native**: Single `bun install` at the root links all sub-projects.
3. **Native TypeScript**: Executes TypeScript files (`server.ts`, scripts) directly without `tsx` or transpile overhead.
4. **Instant Dev Startup**: Vite starts up in ~200ms with Bun.

---

## 3. Backend with `uv` (FastAPI + Python 3.12+)

[`uv`](https://docs.astral.sh/uv/) replaces `pip`, `virtualenv`, and `poetry` with a single ultra-fast Rust binary.

### Common Commands from Root

```bash
# 1. Create virtual environment (.venv) in ~50ms:
uv venv

# 2. Install all dependencies from requirements.txt or pyproject.toml:
uv pip install -r requirements.txt

# 3. Run FastAPI dev server directly with uv (auto-detects virtual environment):
uv run uvicorn main:app --reload --port 8000

# 4. Run test suite:
uv run pytest tests/ -q

# 5. Lock dependencies reproducibly:
uv lock
# Or compile requirements.lock:
uv pip compile requirements.txt -o requirements.lock
```

### Why `uv` for QMA Backend?
1. **10-100x Faster than Pip**: Parallelized downloads and pre-compiled wheel caching.
2. **Automatic Virtualenv Detection**: `uv run` finds `.venv` automatically without requiring manual `activate`.
3. **PEP 621 Standard**: Natively reads `pyproject.toml` and `uv.lock`.

---

## 4. Production Cloud Deployments

### Vercel (`vercel.json`)
Frontend deployment on Vercel is configured to use Bun:
```json
{
  "framework": "vite",
  "installCommand": "cd frontend && bun install",
  "buildCommand": "cd frontend && bun run build"
}
```

### Render (`render.yaml`)
Backend build on Render uses `uv` to speed up deployment builds from 90s to 5s:
```yaml
buildCommand: pip install uv && uv pip install --system -r requirements.txt
startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## 5. Quick Reference Matrix

| Task | Traditional Tool | Modern QMA Standard | Speed Improvement |
|---|---|---|---|
| Monorepo Install (All 3 projects) | 3x `npm install` | `bun install` (at root) | ~20x faster |
| Frontend Dev Server | `npm run dev` | `bun run dev:frontend` | ~2x faster |
| Backend Virtualenv | `python -m venv` | `uv venv` | ~80x faster (~50ms) |
| Backend Package Install | `pip install -r req.txt` | `uv pip install -r requirements.txt` | ~30x faster |
| Running Backend Tests | `pytest` | `uv run pytest` | Instant invocation |
| Render Cloud Build | `pip install -r req.txt` | `uv pip install --system -r req.txt` | ~15x faster |
