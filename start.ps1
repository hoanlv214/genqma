# ==============================================================================
# GenQMA 1-Click Startup Script (Windows PowerShell)
# Concurrently launches Backend API (:8000), Arc Gateway (:3000), and Frontend (:5173)
# ==============================================================================

Write-Host "`n==============================================================================" -ForegroundColor Cyan
Write-Host "                GenQMA 1-Click Service Orchestrator                           " -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan

# 1. Environment Verification
if (-not (Test-Path ".venv") -or -not (Test-Path "node_modules")) {
    Write-Host "[!] Environment not initialized yet. Running .\setup.ps1 first..." -ForegroundColor Yellow
    powershell -ExecutionPolicy Bypass -File .\setup.ps1
}

Write-Host "`n[+] Launching all microservices in dedicated terminal windows..." -ForegroundColor Green
Write-Host "  -> [1/3] Backend API:   http://localhost:8000  (Docs: http://localhost:8000/docs)" -ForegroundColor Cyan
Write-Host "  -> [2/3] Arc Gateway:  http://localhost:3000  (Health: http://localhost:3000/health)" -ForegroundColor Cyan
Write-Host "  -> [3/3] Web Frontend: http://localhost:5173" -ForegroundColor Cyan

# 2. Launch Services in Separate Windows
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle = 'QMA Backend (FastAPI :8000)'; Write-Host '=== QMA FastAPI Backend (Port 8000) ===' -ForegroundColor Cyan; uv run uvicorn main:app --reload --port 8000"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle = 'QMA Arc Gateway (:3000)'; Write-Host '=== QMA Arc Gateway (Port 3000) ===' -ForegroundColor Cyan; bun run dev:gateway"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle = 'QMA Web Frontend (:5173)'; Write-Host '=== QMA React Frontend (Port 5173) ===' -ForegroundColor Cyan; bun run dev:frontend"

# 3. Summary
Write-Host "`n==============================================================================" -ForegroundColor Green
Write-Host "  All services launched successfully in separate console windows!" -ForegroundColor Green
Write-Host "  - Frontend UI:  http://localhost:5173" -ForegroundColor Yellow
Write-Host "  - Backend API:  http://localhost:8000" -ForegroundColor Yellow
Write-Host "  - Arc Gateway:  http://localhost:3000" -ForegroundColor Yellow
Write-Host "`n  To stop all services at once, run: .\stop.ps1" -ForegroundColor Gray
Write-Host "==============================================================================`n" -ForegroundColor Green
