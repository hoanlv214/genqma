# 100% Zero-UI Production Deployment Guide (CLI Only)

[← Quay lại README.md](../../README.md) &nbsp;·&nbsp; [Hướng dẫn Quản lý Package (`uv` & `bun`)](../package-managers.md)

QMA supports full deployment and configuration directly from your terminal using **Supabase CLI**, **Vercel CLI**, and **Render CLI / API**. You do **not** need to open any web dashboard.

---

## Prerequisites (1-Time Authentication)

Before running deploy commands, authenticate each CLI once from your terminal:

```bash
# 1. Supabase CLI
bun x supabase login
# (Prompts for your Personal Access Token from https://supabase.com/dashboard/account/tokens)

# 2. Vercel CLI
bun x vercel login
# (Authenticates via browser confirmation or email token)

# 3. Render CLI
# On Windows: winget install render.cli
# On Linux/macOS: brew install render
render login
```

---

## 1. Database Deployment (Supabase CLI)

No need to open Supabase SQL Editor.

### A. Create a New Supabase Project via CLI
```bash
# Get your Org ID:
bun x supabase orgs list

# Create production database project in Singapore (ap-southeast-1):
bun x supabase projects create genqma-prod \
  --org-id <YOUR_ORG_ID> \
  --db-password "<STRONG_PASSWORD>" \
  --region ap-southeast-1
```

### B. Link and Apply Schema DDL
```bash
# Link local repo to project:
bun x supabase link --project-ref <PROJECT_REF>

# Push complete SQL schema, functions, triggers, and performance indexes:
bun x supabase db execute -f scripts/schema.sql
bun x supabase db execute -f scripts/supabase_perf_indexes.sql
```

### C. Retrieve Credentials for `.env` via CLI
```bash
# Prints project API URL, anon key, and service role key:
bun x supabase status
```

---

## 2. Frontend Deployment (Vercel Automation)

No need to open the Vercel dashboard or copy-paste variables one by one.

### A. 1-Command Automated Sync & Production Deploy
```bash
# Sync all VITE_* variables from .env & deploy to Vercel Production:
bun run deploy:vercel
# (Or: python scripts/vercel_sync.py --token <VERCEL_TOKEN> --all)
```

### B. Sync Environment Variables Only (No Deploy)
```bash
# Using local Vercel CLI session:
bun run deploy:vercel:env

# Or using Vercel Personal Access Token:
python scripts/vercel_sync.py --token <VERCEL_TOKEN> --project genqma --sync-env
```

The script automatically syncs:
- `VITE_QMA_API_BASE_URL` -> `https://qma-api.onrender.com`
- `VITE_QMA_MCP_PUBLIC_URL` -> `https://qma-api.onrender.com`
- `VITE_GENLAYER_CONTRACT_ADDRESS` -> `0x1e5B4d7Be22A3f7F4Ecb616bA65123cB03B7cc13`
- `VITE_GENLAYER_STUDIO_URL` -> `https://studio-next.genlayer.com`
- `VITE_GENLAYER_EXPLORER_URL` -> `https://explorer-studio-dev.genlayer.com`
- `VITE_QMA_ENV` -> `production`
- `VITE_QMA_SYNTHETIC_RUN` -> `false`

---

## 3. Backend & Gateway Deployment (Render Automation)

QMA provides [`scripts/render_sync.py`](../../scripts/render_sync.py) to manage the entire multi-service lifecycle across Render accounts and workspaces:

### A. Automated Env Sync & Distributed Deploy (Recommended)
```bash
# Sync all secrets and config from .env + trigger redeployment for active services:
bun run deploy:render
# (Or: python scripts/render_sync.py --api-key <RENDER_API_KEY> --distributed --sync-env --deploy)
```

### B. Status & Inspection
```bash
# Check real-time build and live health status across all services:
bun run deploy:render:status

# Inspect environment variables currently active on Render:
bun run deploy:render:inspect
```

### C. Cross-Workspace Discovery
If services are spread across different Render workspaces (e.g. `Hoàn Lại Văn's Workspace` and `penn`), `--distributed` automatically detects the live deployed instance of each target service:
- `qma-api` (`srv-d9cp4r61a83c739i2h7g`) on `Hoàn Lại Văn's Workspace`
- `qma-arc-gateway` (`srv-d9cp4re1a83c739i2h80`) on `Hoàn Lại Văn's Workspace`
- `qma-agent-worker` (`srv-d9ic5af41pts73b10s20`) on `penn`

---

## 4. CI/CD Pipeline (GitHub Actions Example)

You can run continuous deployment on push to `main` by adding secrets `RENDER_API_KEY` and `VERCEL_TOKEN` to your repository:

```yaml
name: Deploy Production (Render & Vercel)

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Sync Env & Deploy Render
        env:
          RENDER_API_KEY: ${{ secrets.RENDER_API_KEY }}
        run: |
          python scripts/render_sync.py --api-key $RENDER_API_KEY --distributed --sync-env --deploy

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
      - name: Sync Env & Deploy Vercel
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
        run: |
          python scripts/vercel_sync.py --token $VERCEL_TOKEN --project genqma --all
```

---

## 5. Summary of Quick CLI Commands

```bash
# 1. Apply Supabase SQL schema:
bun run deploy:db

# 2. Deploy GenLayer Intelligent Contract:
bun run deploy:genlayer

# 3. Deploy Render services (Backend + Gateway + Worker):
bun run deploy:render

# 4. Check Render deployment status:
bun run deploy:render:status

# 5. Deploy Frontend to Vercel:
bun run deploy:vercel
```
