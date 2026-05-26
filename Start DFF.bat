@echo off
:: Launcher for Duplicate File Finder Pro
:: https://github.com/BishnuMahali/Duplicate-File-Finder
:: Prefers Python GUI, falls back to PowerShell WPF GUI

title Duplicate File Finder PRO — Launcher
color 0B
echo.
echo  ========================================
echo     DUPLICATE FILE FINDER PRO SUITE
echo  ========================================
echo.

:: ------------------------------------------
:: 1. Check if Python is available
:: ------------------------------------------
where python >nul 2>nul
if %errorlevel% neq 0 goto :NO_PYTHON

:: Verify Python actually runs (not a Windows Store stub)
python --version >nul 2>nul
if %errorlevel% neq 0 goto :NO_PYTHON

echo  [OK] Python detected: 
python --version
echo.

:: ------------------------------------------
:: 2. Check dependencies for Python GUI
:: ------------------------------------------
echo  Checking Python dependencies...
python -c "import customtkinter, send2trash" >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo  [!] Missing dependencies for DFF-Pro Python GUI.
    echo.
    choice /C YN /M "  Install required packages now? (Y=Install, N=Use PowerShell GUI instead)"
    if errorlevel 2 goto :LAUNCH_PS
    echo.
    echo  Installing dependencies...
    python -m pip install -r "%~dp0HELPER\requirements.txt"
    if %errorlevel% neq 0 (
        echo.
        echo  [ERROR] Failed to install dependencies.
        echo  Falling back to PowerShell WPF GUI...
        timeout /t 2 >nul
        goto :LAUNCH_PS
    )
    echo.
    echo  [OK] Dependencies installed successfully.
    echo.
)

:: ------------------------------------------
:: 3. Launch Python GUI (preferred)
:: ------------------------------------------
echo  Launching DFF-Pro Python GUI...
echo.
python "%~dp0DFF-Pro.py"
goto :EOF

:: ------------------------------------------
:: FALLBACK: No Python available
:: ------------------------------------------
:NO_PYTHON
echo  [!] Python was NOT found on this system.
echo.
echo  The DFF-Pro Python GUI provides the best experience with:
echo    - Tokyo Night premium dark mode theme
echo    - GPU-accelerated video fingerprinting
echo    - Advanced perceptual matching engine
echo    - Smart auto-selection rules for cleanup
echo.
echo  You can install Python from: https://www.python.org/downloads/
echo  (Make sure to check "Add Python to PATH" during installation)
echo.
choice /C YN /M "  Launch PowerShell WPF GUI instead? (Y=Launch, N=Exit)"
if errorlevel 2 goto :EOF

:: ------------------------------------------
:: Launch PowerShell WPF GUI (fallback)
:: ------------------------------------------
:LAUNCH_PS
echo.
echo  Launching PowerShell WPF GUI...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Duplicate_File_Finder_GUI.ps1"
goto :EOF

:EOF
