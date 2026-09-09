$ErrorActionPreference = "Stop"

$cmd = Get-Command sg -ErrorAction SilentlyContinue
if (-not $cmd) {
    $cmd = Get-Command ast-grep -ErrorAction SilentlyContinue
}

if (-not $cmd) {
    Write-Error "ast-grep CLI was not found in PATH. Reopen the terminal after npm global install, or add the npm global bin directory to PATH."
}

Write-Host "Using ast-grep command: $($cmd.Source)"
& $cmd.Source --version

& $cmd.Source scan -r .ast-grep/rules/python-fastapi-app-route.yml backend main.py tests
& $cmd.Source scan -r .ast-grep/rules/python-save-invoice-call.yml backend main.py tests
& $cmd.Source scan -r .ast-grep/rules/python-save-payment-ledger-call.yml backend main.py tests
& $cmd.Source scan -r .ast-grep/rules/python-payment-required-exception.yml backend main.py tests
& $cmd.Source scan -r .ast-grep/rules/python-state-invoices-direct-write.yml backend main.py tests
& $cmd.Source scan -r .ast-grep/rules/python-requests-post-call.yml backend/app/api backend/app/main.py
