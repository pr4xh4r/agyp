@echo off
setlocal
:: Run GUI — uses stable installed copy if available, falls back to local script
set INSTALL_DIR=%USERPROFILE%\AppData\Local\agyp\agyp_gui.py
set LOCAL_DIR=%~dp0agyp_gui.py

if exist "%INSTALL_DIR%" (
    start "" pythonw "%INSTALL_DIR%" %*
) else (
    start "" pythonw "%LOCAL_DIR%" %*
)
