@echo off
title GenQMA - Complete Local Server Suite
echo ======================================================================
echo          GenQMA - 1-Click All-in-One Local Server (24/7)
echo ======================================================================
echo.
echo Starting all local services:
echo   [1/4] FastAPI Backend   - http://localhost:8000
echo   [2/4] Arc Gateway       - http://localhost:3000
echo   [3/4] Agent Worker      - Autonomous Session Background Engine
echo   [4/4] Cloudflare Tunnel - Exposing to Internet via HTTPS
echo ======================================================================
echo.

cd /d "%~dp0"

:: Ensure explicit local environment defaults
set QMA_API_URL=http://localhost:8000
set QMA_ARC_GATEWAY_URL=http://localhost:3000
set QMA_ARC_GATEWAY_INTERNAL_SECRET=123a

:: 1. Launch FastAPI Backend
echo [1/4] Starting FastAPI Backend on port 8000...
start "GenQMA [1/4] FastAPI Backend" cmd /k "python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

:: 2. Launch Arc Gateway
echo [2/4] Starting Arc Gateway on port 3000...
start "GenQMA [2/4] Arc Gateway" cmd /k "cd arc_gateway && npm start"

:: 3. Launch Agent Worker
echo [3/4] Starting Agent Worker...
start "GenQMA [3/4] Agent Worker" cmd /k "set QMA_API_URL=http://localhost:8000&& set QMA_ARC_GATEWAY_URL=http://localhost:3000&& set QMA_ARC_GATEWAY_INTERNAL_SECRET=123a&& cd agents && npm run start:worker"

:: Wait 3 seconds for local ports to open
timeout /t 3 /nobreak >nul

:: 4. Launch Static Ngrok Tunnel
echo [4/4] Starting Ngrok Tunnel with Static Domain...
echo.
echo ======================================================================
echo Ngrok Static URL: https://driveway-expansive-onyx.ngrok-free.dev
echo Exposing http://localhost:8000 to the Internet 24/7 (Never changes!)
echo ======================================================================
echo.
ngrok http 8000 --url https://driveway-expansive-onyx.ngrok-free.dev

pause
