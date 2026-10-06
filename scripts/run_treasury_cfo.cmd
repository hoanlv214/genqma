@echo off
REM ============================================================
REM QMA Treasury / CFO Operator Loop
REM
REM Runs scripts\treasury_cfo_loop.mjs: every cycle it reads the
REM on-chain treasury position, sweeps idle USDC above the operating
REM reserve into USYC (server-side rails + Euthyna audit), and triggers
REM a CFO decision evaluation.
REM
REM Usage:  run_treasury_cfo.cmd [api-base] [interval-seconds]
REM Stop:   close the "qma-treasury-loop" window (or Ctrl+C).
REM ============================================================
setlocal
set "API_BASE=%~1"
if "%API_BASE%"=="" set "API_BASE=http://localhost:8000"
set "INTERVAL=%~2"
if "%INTERVAL%"=="" set "INTERVAL=1800"

set "REPO_DIR=C:\Users\Admin\Downloads\code\genqma"
cd /d "%REPO_DIR%"
set "QMA_API_URL=%API_BASE%"
set "QMA_TREASURY_LOOP_INTERVAL_SECONDS=%INTERVAL%"

echo [treasury-cfo] api=%API_BASE% interval=%INTERVAL%s
start "qma-treasury-loop" cmd /k node scripts\treasury_cfo_loop.mjs --api "%API_BASE%"
echo [treasury-cfo] loop window launched.
timeout /t 5 >nul
endlocal
