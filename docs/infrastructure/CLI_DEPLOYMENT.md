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

## 2. Frontend Deployment (Vercel CLI)

No need to create or configure anything on the Vercel website.

### A. Link Project & Configure Monorepo
```bash
# Link to Vercel (automatically detects Vite):
bun x vercel link --yes --project genqma-frontend
```

### B. Push Environment Variables via CLI
```bash
# Set production environment variables without opening the browser:
echo "https://qma-api-7o9v.onrender.com" | bun x vercel env add VITE_API_BASE_URL production
echo "https://qma-arc-gateway-4elg.onrender.com" | bun x vercel env add VITE_ARC_GATEWAY_URL production
```

### C. Deploy Production Bundle
```bash
# Builds with Bun and deploys directly to production:
bun x vercel --prod
```

---

## 3. Backend & Gateway Deployment (Render CLI & Blueprints)

QMA already includes [`render.yaml`](../../render.yaml), which configures all 3 services (`qma-api`, `qma-arc-gateway`, and `qma-agent-worker`) simultaneously.

### Option A: Using Render Blueprint CLI (IaC - Infrastructure as Code)
```bash
# Launch all 3 services defined in render.yaml directly from terminal:
render blueprint launch
```
Render will automatically create the services, set Python runtime with `uv`, set Node runtime with `npm/bun`, and configure all environment variable mappings.

### Option B: Using Render Deploy Hooks (Fastest 1-Line Trigger)
Each Render service has a secret Deploy Hook URL:
```bash
# Trigger instant redeployment of backend API from CLI:
curl -X POST "$RENDER_API_DEPLOY_HOOK"

# Trigger instant redeployment of Arc Gateway from CLI:
curl -X POST "$RENDER_GATEWAY_DEPLOY_HOOK"
```

---

## 4. One-Command Monorepo Deployment Scripts

Add these to your root environment or `.env` and run from `package.json`:

```bash
# Deploy Database Schema only:
bun run deploy:db

# Deploy Frontend to Vercel:
bun run deploy:fe

# Deploy Everything (DB + Backend + Frontend):
bun run deploy:all
```
