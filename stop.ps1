# ==============================================================================
# GenQMA 1-Click Stop Script (Windows PowerShell)
# Stops all processes listening on QMA dev ports (8000, 3000, 5173)
# ==============================================================================

Write-Host "`nStopping all active QMA development services..." -ForegroundColor Cyan

$ports = @(8000, 3000, 5173)
foreach ($port in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conns) {
        foreach ($conn in $conns) {
            $pidToStop = $conn.OwningProcess
            if ($pidToStop -and $pidToStop -ne 0) {
                try {
                    Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
                    Write-Host "  [Stopped] Process PID $pidToStop on port $port" -ForegroundColor Green
                } catch {
                    Write-Host "  [Skip] Could not stop PID $pidToStop on port $port" -ForegroundColor Yellow
                }
            }
        }
    } else {
        Write-Host "  [-] Port $port is already free." -ForegroundColor Gray
    }
}

Write-Host "`nAll QMA services have been stopped.`n" -ForegroundColor Green
