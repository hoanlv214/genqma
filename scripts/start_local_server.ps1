# GenQMA Local Server Launcher with Cloudflare Tunnel
$Host.UI.RawUI.WindowTitle = "GenQMA Local Server + Cloudflare Tunnel"
$projectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "         GenQMA - Local Server with Cloudflare Tunnel (24/7)          " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $projectRoot

Write-Host "[1/2] Starting FastAPI Backend on http://localhost:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

Write-Host "[2/2] Starting Cloudflare Tunnel to expose localhost:8000 ..." -ForegroundColor Green
Write-Host ""
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host "COPY the generated 'https://xxxx.trycloudflare.com' URL below" -ForegroundColor Yellow
Write-Host "and paste it into vercel.json if routing via Vercel." -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host ""

cloudflared tunnel --url http://localhost:8000
