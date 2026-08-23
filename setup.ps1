# LUMO-Term Setup Script (Windows)
#
# Thin wrapper around install.py, which does the actual cross-platform work.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Error "[ERROR] Python not found. Please install Python 3.10+"
    exit 1
}

& $python.Source (Join-Path $ScriptDir "install.py") @args
exit $LASTEXITCODE
