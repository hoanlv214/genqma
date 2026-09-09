# Modern Package Management Guide: `bun` & `uv`

QMA standardizes on modern, high-performance tooling for package management, dependency resolution, and runtime execution:

* **Frontend (`frontend/`)**: Powered by **`bun`** (Fast TypeScript/JavaScript package manager & bundler).
* **Backend (`backend/`)**: Powered by **`uv`** (Blazing-fast Rust-based Python package manager).

---

## 1. Frontend with `bun` (React 18 + Vite)

[Bun](https://bun.sh) replaces `npm`/`yarn`/`pnpm` with instant module resolution and zero-overhead builds.

### Installation

```bash
# macOS & Linux
curl -fsSL https://bun.sh/install | bash

# Windows (PowerShell)
powershell -c "irm bun.sh/install.ps1 | iex"
```

### Common Commands

Navigate to `frontend/`:

```bash
cd frontend

# Install all dependencies with bun
bun install

# Start local development server (Vite + HMR)
bun run dev

# Build production bundle
bun run build

# Preview production build
bun run preview
```

### Why Bun for QMA Frontend?
1. **10-25x Faster Installs**: Parallelized cache and zero-copy symlinks.
2. **Deterministic `bun.lockb`**: Eliminates dependency drift across developer machines and CI.
3. **Native TypeScript Support**: Seamlessly executes scripts without transpile overhead.

---

## 2. Backend with `uv` (FastAPI + Python 3.12+)

[`uv`](https://docs.astral.sh/uv/) replaces `pip`, `virtualenv`, and `poetry` with a single, ultra-fast Rust binary.

### Installation

```bash
# macOS & Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Common Commands

From the project root:

```bash
# Create and activate a fast virtual environment
uv venv
# On Windows PowerShell:
.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate

# Install all dependencies from requirements.txt
uv pip install -r requirements.txt

# Run the FastAPI server directly with uv
uv run uvicorn backend.app.main:app --reload --port 8000

# Run the test suite
uv run pytest tests/ -q
```

### Lockfile & Dependency Management

```bash
# Compile and lock dependencies
uv pip compile requirements.txt -o requirements.lock

# Sync exact locked dependencies
uv pip sync requirements.lock
```

### Why `uv` for QMA Backend?
1. **10-100x Faster than Pip**: Instant sub-second environment installation and cold-starts.
2. **Global Disk-Space Deduplication**: Shares identical wheel caches across projects.
3. **Drop-in Standards Compliance**: Works natively with `pyproject.toml` and standard `requirements.txt`.

---

## 3. Quick Reference Matrix

| Task | Traditional Tool | Modern QMA Standard | Speed Improvement |
|---|---|---|---|
| Frontend Installs | `npm install` | `bun install` | ~15x faster |
| Frontend Dev Server | `npm run dev` | `bun run dev` | ~2x faster startup |
| Backend Environment | `python -m venv` | `uv venv` | ~80x faster |
| Backend Package Install | `pip install -r req.txt` | `uv pip install -r requirements.txt` | ~30x faster |
| Running Backend Tests | `pytest` | `uv run pytest` | Instant invocation |
