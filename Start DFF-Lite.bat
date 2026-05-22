@echo off
rem Start DFF-Lite.bat — Launcher for DFF-Lite
rem Copyright (c) 2026 Bishnu Mahali
rem See LICENSE file in the repository root for full license text.

title DFF-Lite — Advanced Filename Duplicate Finder

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.10+ and make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo Checking dependencies...
python -c "import rapidfuzz, typer, rich, yaml, pydantic" 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] Dependencies seem to be missing. Installing now...
    python -m pip install -r "%~dp0HELPER\requirements.txt"
)

echo Starting DFF-Lite CLI Console...
echo --------------------------------------------------
python "%~dp0DFF-Lite.py" --help
echo --------------------------------------------------
echo [INFO] You can run DFF-Lite in Command Prompt or PowerShell using:
echo python "%~dp0DFF-Lite.py" scan ^<folders^>
echo python "%~dp0DFF-Lite.py" compare ^<folders^>
echo.
pause
