#!/usr/bin/env bash
# ==============================================================================
# GenQMA 1-Click Environment Auditor & Setup Script (Linux / macOS / Bash)
# Automatically scans, installs prerequisites, sets up dependencies & configures .env
# ==============================================================================
set -e

CYAN='\033[1;36m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

echo -e "\n${CYAN}==============================================================================${NC}"
echo -e "${CYAN}                GenQMA 1-Click System Audit & Environment Setup               ${NC}"
echo -e "${CYAN}==============================================================================${NC}"

# ------------------------------------------------------------------------------
# 1. Environment Scanning & Auto-Installation of Missing Tools
# ------------------------------------------------------------------------------
echo -e "\n${NC}[1/5] Auditing System Environment...${NC}"

# OS Details
OS_TYPE="$(uname -s)"
OS_ARCH="$(uname -m)"
echo -e "  OS: ${GRAY}${OS_TYPE} (${OS_ARCH})${NC}"

# Git Check
if command -v git &> /dev/null; then
    echo -e "  ${GREEN}[OK] Git:${NC} $(git --version)"
else
    echo -e "  ${YELLOW}[WARN] Git is not found in PATH.${NC}"
fi

# Python Check
if command -v python3 &> /dev/null; then
    echo -e "  ${GREEN}[OK] Python:${NC} $(python3 --version)"
elif command -v python &> /dev/null; then
    echo -e "  ${GREEN}[OK] Python:${NC} $(python --version)"
else
    echo -e "  ${YELLOW}[WARN] Python not found directly; uv will automatically manage Python runtimes.${NC}"
fi

# ------------------------------------------------------------------------------
# 2. UV Check & Auto-Install
# ------------------------------------------------------------------------------
echo -e "\n${NC}[2/5] Checking Python Package Manager (uv)...${NC}"
if ! command -v uv &> /dev/null; then
    echo -e "  ${YELLOW}[-] uv not found. Auto-installing uv via official installer...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
fi

if command -v uv &> /dev/null; then
    echo -e "  ${GREEN}[OK] uv installed:${NC} $(uv --version)"
else
    echo -e "  ${RED}[ERROR] Failed to auto-install uv. Please install manually: curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
    exit 1
fi

# ------------------------------------------------------------------------------
# 3. Bun Check & Auto-Install
# ------------------------------------------------------------------------------
echo -e "\n${NC}[3/5] Checking Monorepo & Node Package Manager (bun)...${NC}"
if ! command -v bun &> /dev/null; then
    echo -e "  ${YELLOW}[-] bun not found. Auto-installing bun via official installer...${NC}"
    curl -fsSL https://bun.sh/install | bash
    export PATH="$HOME/.bun/bin:$PATH"
fi

if command -v bun &> /dev/null; then
    echo -e "  ${GREEN}[OK] bun installed:${NC} $(bun --version)"
else
    echo -e "  ${RED}[ERROR] Failed to auto-install bun. Please install manually: curl -fsSL https://bun.sh/install | bash${NC}"
    exit 1
fi

# ------------------------------------------------------------------------------
# 4. Python Virtualenv & Dependency Synchronization
# ------------------------------------------------------------------------------
echo -e "\n${NC}[4/5] Setting up Python Virtual Environment & Dependencies...${NC}"
if [ ! -d ".venv" ]; then
    echo -e "  ${GRAY}Creating virtual environment (.venv) using uv...${NC}"
    uv venv
fi
echo -e "  ${GRAY}Syncing Python packages from requirements.txt...${NC}"
uv pip install -r requirements.txt
echo -e "  ${GREEN}[OK] Python backend dependencies synchronized.${NC}"

# ------------------------------------------------------------------------------
# 5. Monorepo Workspaces Installation (Frontend, Arc Gateway, Agents)
# ------------------------------------------------------------------------------
echo -e "\n${NC}[5/5] Installing Monorepo Workspaces with Bun...${NC}"
echo -e "  ${GRAY}Resolving frontend, arc_gateway, and agents in parallel...${NC}"
bun install
echo -e "  ${GREEN}[OK] Node workspaces synchronized in seconds.${NC}"

# ------------------------------------------------------------------------------
# Environment File (.env) Check
# ------------------------------------------------------------------------------
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "  ${YELLOW}[i] Created .env from .env.example. Please update your environment variables if needed.${NC}"
    fi
else
    echo -e "  ${GREEN}[OK] .env configuration file present.${NC}"
fi

# ------------------------------------------------------------------------------
# Final Readiness Report
# ------------------------------------------------------------------------------
echo -e "\n${GREEN}==============================================================================${NC}"
echo -e "${GREEN}               ENVIRONMENT SETUP COMPLETE & READY TO RUN                      ${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo -e "System Status Checklist:"
echo -e "  ${GREEN}[x] Core Tooling:      uv (Python) & bun (JavaScript/TypeScript)${NC}"
echo -e "  ${GREEN}[x] Backend (.venv):   Installed with FastAPI, Pydantic, Scipy, etc.${NC}"
echo -e "  ${GREEN}[x] Frontend:          Installed (React 18 + Vite)${NC}"
echo -e "  ${GREEN}[x] Arc Gateway:       Installed (Express + Viem + Circle SDK)${NC}"
echo -e "  ${GREEN}[x] Agent CLI:         Installed (Autonomous buyer-agent)${NC}"
echo -e "\n${CYAN}How to start all services in 1-Click:${NC}"
echo -e "  ${YELLOW}Run:   ./start.sh${NC}"
echo -e "  ${GRAY}(Automatically launches Backend, Arc Gateway, and Frontend together)${NC}"
echo -e "${GREEN}==============================================================================\n${NC}"
