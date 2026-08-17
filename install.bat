@echo off
setlocal enabledelayedexpansion
echo [*] Setting up Antigravity Profiles Suite...
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python not found. Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

:: Get script directory so paths stay correct regardless of where it is run from
set SCRIPT_DIR=%~dp0
:: Strip trailing backslash
if "%SCRIPT_DIR:~-1%"=="\" set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

:: Determine USERPROFILE-based install dir
set INSTALL_DIR=%USERPROFILE%\AppData\Local\agyp

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: Copy scripts to stable location
echo [*] Copying scripts to %INSTALL_DIR%...
copy /Y "%SCRIPT_DIR%\agyp_cli.py" "%INSTALL_DIR%\agyp_cli.py" >nul
copy /Y "%SCRIPT_DIR%\agyp_gui.py" "%INSTALL_DIR%\agyp_gui.py" >nul

:: Install customtkinter (--user works on restricted/corporate machines)
echo [*] Installing GUI dependencies...
pip install --user --quiet customtkinter
if errorlevel 1 (
    pip install --quiet customtkinter
)
if errorlevel 1 (
    echo [!] Failed to install customtkinter. Try running as Administrator.
    pause
    exit /b 1
)

:: Create profile storage directory
if not exist "%USERPROFILE%\agyp-profiles" mkdir "%USERPROFILE%\agyp-profiles"

echo.
echo [+] Installation Complete!
echo.
echo You can now use the provided batch files to launch the tools:
echo   - Double-click 'run-cli.bat' for the terminal manager.
echo   - Double-click 'run-gui.bat' for the graphical manager.
echo.
echo Profiles will be stored in: %USERPROFILE%\agyp-profiles\
echo.
pause
