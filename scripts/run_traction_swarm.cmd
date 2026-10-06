@echo off
REM ============================================================
REM QMA Traction Swarm Launcher (operator-side demo traffic)
REM
REM Launches N parallel swarm windows. Each window continuously buys
REM reports from random funded test wallets via the x402 buyer flow
REM (payment settles on Arc testnet, spend guard caps each payer
%% server-side at its daily policy cap).
REM
REM Usage:  run_traction_swarm.cmd [api-base] [instances] [wallet-count]
REM         api-base    default http://localhost:8000
REM         instances   default 3 (parallel swarm windows)
REM         wallet-count default 20
REM Stop:   close each "qma-swarm-N" window (or Ctrl+C inside it).
REM ============================================================
setlocal
set "API_BASE=%~1"
if "%API_BASE%"=="" set "API_BASE=http://localhost:8000"
set "INSTANCES=%~2"
if "%INSTANCES%"=="" set "INSTANCES=3"
set "WALLET_COUNT=%~3"
if "%WALLET_COUNT%"=="" set "WALLET_COUNT=20"

set "WALLETS_FILE=C:\Users\Admin\Downloads\code\buy\qma\.qma-test-wallets.json"
set "REPO_DIR=C:\Users\Admin\Downloads\code\genqma"

if not exist "%WALLETS_FILE%" (
    echo [ERROR] Wallets file not found: %WALLETS_FILE%
    pause
    exit /b 1
)
if not exist "%REPO_DIR%\scripts\qma_agent_swarm.mjs" (
    echo [ERROR] Swarm script not found under %REPO_DIR%
    pause
    exit /b 1
)

cd /d "%REPO_DIR%"
set "QMA_API_URL=%API_BASE%"
set "PROVIDER_IDS=funding_memory,oi_memory"
set "TIERS=preview,full"
set "MIN_DELAY_MS=60000"
set "MAX_DELAY_MS=150000"
set "MAX_PRICE_USDC=0.006"

echo [traction-swarm] api=%API_BASE%  instances=%INSTANCES%  wallets=%WALLET_COUNT%
echo [traction-swarm] providers=%PROVIDER_IDS%  tiers=%TIERS%
echo [traction-swarm] polymarket_divergence/pyth_stress_band are excluded on purpose: their evidence cannot pass GenLayer semantic verification yet (see docs/TECH_DEBT.md #1).

for /l %%i in (1,1,%INSTANCES%) do (
    start "qma-swarm-%%i" cmd /k node scripts\qma_agent_swarm.mjs --live --wallets-file "%WALLETS_FILE%" --wallet-count %WALLET_COUNT% --run-source traction_swarm_%%i
)

echo.
echo [traction-swarm] %INSTANCES% swarm window(s) launched. Watch traction at /traction
echo [traction-swarm] Close each window to stop that instance.
timeout /t 8 >nul
endlocal
