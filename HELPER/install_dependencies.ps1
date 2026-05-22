# install_dependencies.ps1 — Setup script for DFF-Lite
# Copyright (c) 2026 Bishnu Mahali
# See LICENSE file in the repository root for full license text.

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "⚡ DFF-Lite Dependency Installer ⚡" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Check Python installation
$pythonCheck = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCheck) {
    Write-Host "❌ Python is not installed or not in your PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ and check 'Add Python to PATH' during installation." -ForegroundColor Yellow
    Exit 1
}

$pythonVersion = & python --version 2>&1
Write-Host "✓ Found Python: $pythonVersion" -ForegroundColor Green

# Install requirements
Write-Host "⏳ Installing required packages via pip..." -ForegroundColor Yellow
& python -m pip install --upgrade pip
& python -m pip install -r "$PSScriptRoot\requirements.txt"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Dependencies successfully installed!" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to install dependencies. Please run 'pip install -r HELPER/requirements.txt' manually." -ForegroundColor Red
}
