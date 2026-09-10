#!/usr/bin/env bash
# ==============================================================================
# GenQMA 1-Click Startup Script (Linux / macOS / Bash)
# Concurrently launches Backend API (:8000), Arc Gateway (:3000), and Frontend (:5173)
# ==============================================================================
set -e

CYAN='\033[1;36m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
GRAY='\033[0;37m'
NC='\033[0m'

echo -e "\n${CYAN}==============================================================================${NC}"
echo -e "${CYAN}                GenQMA 1-Click Service Orchestrator                           ${NC}"
echo -e "${CYAN}==============================================================================${NC}"

# 1. Environment Verification
if [ ! -d ".venv" ] || [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}[!] Environment not initialized yet. Running ./setup.sh first...${NC}"
    chmod +x ./setup.sh && ./setup.sh
fi

echo -e "\n${GREEN}[+] Launching all microservices concurrently...${NC}"
echo -e "  -> ${CYAN}[1/3] Backend API:   http://localhost:8000  (Docs: http://localhost:8000/docs)${NC}"
echo -e "  -> ${CYAN}[2/3] Arc Gateway:  http://localhost:3000  (Health: http://localhost:3000/health)${NC}"
echo -e "  -> ${CYAN}[3/3] Web Frontend: http://localhost:5173${NC}"
echo -e "\n${YELLOW}Press Ctrl+C anytime to cleanly stop all services.${NC}\n"

# Trap INT and TERM signals to kill child processes
cleanup() {
    echo -e "\n${YELLOW}Stopping all services...${NC}"
    kill $(jobs -p) 2>/dev/null || true
    echo -e "${GREEN}All services stopped cleanly.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Start services
uv run uvicorn main:app --reload --port 8000 &
P1=$!

bun run dev:gateway &
P2=$!

bun run dev:frontend &
P3=$!

wait $P1 $P2 $P3
