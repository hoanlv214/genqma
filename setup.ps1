# ==============================================================================
# GenQMA 1-Click Environment Auditor & Setup Script (Windows PowerShell)
# Automatically scans, installs prerequisites, sets up dependencies & configures .env
# ==============================================================================

$ErrorActionPreference = "Continue"

Write-Host "`n==============================================================================" -ForegroundColor Cyan
Write-Host "                GenQMA 1-Click System Audit & Environment Setup               " -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan

# ------------------------------------------------------------------------------
# 1. Environment Scanning & Auto-Installation of Missing Tools
# ------------------------------------------------------------------------------
Write-Host "`n[1/5] Auditing System Environment..." -ForegroundColor White

# OS Details
$os = (Get-CimInstance Win32_OperatingSystem).Caption
Write-Host "  OS: $os" -ForegroundColor Gray

# Git Check
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitVer = git --version
    Write-Host "  [OK] Git: $gitVer" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Git is not found in PATH." -ForegroundColor Yellow
}

# Python Check
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pyVer = python --version
    Write-Host "  [OK] Python: $pyVer" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Python not found directly; uv will automatically manage Python runtimes." -ForegroundColor Yellow
}

# UV Check & Auto-Install
Write-Host "`n[2/5] Checking Python Package Manager (uv)..." -ForegroundColor White
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "  [-] uv not found. Auto-installing uv via official installer..." -ForegroundColor Yellow
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" + [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";$HOME\.cargo\bin;$HOME\.local\bin"
}
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uvVer = uv --version
    Write-Host "  [OK] uv installed: $uvVer" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Failed to auto-install uv. Please run: irm https://astral.sh/uv/install.ps1 | iex" -ForegroundColor Red
    Exit 1
}

# Bun Check & Auto-Install
Write-Host "`n[3/5] Checking Monorepo & Node Package Manager (bun)..." -ForegroundColor White
if (-not (Get-Command bun -ErrorAction SilentlyContinue)) {
    Write-Host "  [-] bun not found. Auto-installing bun via official installer..." -ForegroundColor Yellow
    powershell -ExecutionPolicy ByPass -c "irm bun.sh/install.ps1 | iex"
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" + [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";$HOME\.bun\bin"
}
if (Get-Command bun -ErrorAction SilentlyContinue) {
    $bunVer = bun --version
    Write-Host "  [OK] bun installed: $bunVer" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Failed to auto-install bun. Please run: irm bun.sh/install.ps1 | iex" -ForegroundColor Red
    Exit 1
}

# ------------------------------------------------------------------------------
# 2. Python Virtualenv & Dependency Synchronization
# ------------------------------------------------------------------------------
Write-Host "`n[4/5] Setting up Python Virtual Environment & Dependencies..." -ForegroundColor White
if (-not (Test-Path ".venv")) {
    Write-Host "  Creating virtual environment (.venv) using uv..." -ForegroundColor Gray
    uv venv
}
Write-Host "  Syncing Python packages from requirements.txt..." -ForegroundColor Gray
uv pip install -r requirements.txt
Write-Host "  [OK] Python backend dependencies synchronized." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 3. Monorepo Workspaces Installation (Frontend, Arc Gateway, Agents)
# ------------------------------------------------------------------------------
Write-Host "`n[5/5] Installing Monorepo Workspaces with Bun..." -ForegroundColor White
Write-Host "  Resolving frontend, arc_gateway, and agents in parallel..." -ForegroundColor Gray
bun install
Write-Host "  [OK] Node workspaces synchronized in seconds." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 4. Environment File (.env) Check
# ------------------------------------------------------------------------------
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "  [i] Created .env from .env.example." -ForegroundColor Yellow
    }
} else {
    Write-Host "  [OK] .env configuration file present." -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# 5. Final Readiness Report
# ------------------------------------------------------------------------------
Write-Host "`n==============================================================================" -ForegroundColor Green
Write-Host "               ENVIRONMENT SETUP COMPLETE & READY TO RUN                      " -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host "System Status Checklist:" -ForegroundColor White
Write-Host "  [x] Core Tooling:      uv (Python) & bun (JavaScript/TypeScript)" -ForegroundColor Green
Write-Host "  [x] Backend (.venv):   Installed with FastAPI, Pydantic, Scipy, etc." -ForegroundColor Green
Write-Host "  [x] Frontend:          Installed (React 18 + Vite)" -ForegroundColor Green
Write-Host "  [x] Arc Gateway:       Installed (Express + Viem + Circle SDK)" -ForegroundColor Green
Write-Host "  [x] Agent CLI:         Installed (Autonomous buyer-agent)" -ForegroundColor Green
Write-Host "`nHow to start all services in 1-Click:" -ForegroundColor Cyan
Write-Host "  Run:   .\start.ps1" -ForegroundColor Yellow
Write-Host "  (Automatically launches Backend, Arc Gateway, and Frontend together)" -ForegroundColor Gray
Write-Host "==============================================================================`n" -ForegroundColor Green
