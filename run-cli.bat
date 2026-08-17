@echo off
setlocal
:: Run CLI — uses stable installed copy if available, falls back to local script
set INSTALL_SCRIPT=%LOCALAPPDATA%\agyp\agyp_cli.py
set LOCAL_SCRIPT=%~dp0agyp_cli.py

if exist "%INSTALL_SCRIPT%" (
    python "%INSTALL_SCRIPT%" %*
) else if exist "%LOCAL_SCRIPT%" (
    python "%LOCAL_SCRIPT%" %*
) else (
    echo [!] agyp_cli.py not found. Please run install.bat first.
    pause
)
if errorlevel 1 pause
