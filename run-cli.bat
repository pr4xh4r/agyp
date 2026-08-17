@echo off
setlocal
:: Run CLI — uses stable installed copy if available, falls back to local script
set INSTALL_DIR=%USERPROFILE%\AppData\Local\agyp\agyp_cli.py
set LOCAL_DIR=%~dp0agyp_cli.py

if exist "%INSTALL_DIR%" (
    python "%INSTALL_DIR%" %*
) else (
    python "%LOCAL_DIR%" %*
)
if errorlevel 1 pause
