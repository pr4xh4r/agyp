@echo off
setlocal
:: Run GUI — uses stable installed copy if available, falls back to local script
:: Uses 'pythonw' so no black console window appears behind the GUI
set INSTALL_SCRIPT=%LOCALAPPDATA%\agyp\agyp_gui.py
set LOCAL_SCRIPT=%~dp0agyp_gui.py

if exist "%INSTALL_SCRIPT%" (
    start "" pythonw "%INSTALL_SCRIPT%" %*
) else if exist "%LOCAL_SCRIPT%" (
    start "" pythonw "%LOCAL_SCRIPT%" %*
) else (
    echo [!] agyp_gui.py not found. Please run install.bat first.
    pause
)
