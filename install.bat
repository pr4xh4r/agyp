@echo off
setlocal enabledelayedexpansion
echo [*] Setting up Antigravity Profiles Suite...
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python not found. Please install Python 3.8+ from https://python.org
    echo     Make sure to check "Add Python to PATH" during install!
    pause
    exit /b 1
)

:: Get script directory so paths stay correct regardless of where it is run from
set SCRIPT_DIR=%~dp0
:: Strip trailing backslash
if "%SCRIPT_DIR:~-1%"=="\" set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

:: Determine install dir
set INSTALL_DIR=%LOCALAPPDATA%\agyp

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: Copy scripts to stable location
echo [*] Copying scripts to %INSTALL_DIR%...
copy /Y "%SCRIPT_DIR%\agyp_cli.py" "%INSTALL_DIR%\agyp_cli.py" >nul
copy /Y "%SCRIPT_DIR%\agyp_gui.py" "%INSTALL_DIR%\agyp_gui.py" >nul

:: Create agyp-cli.bat launcher in install dir (so it works from anywhere)
echo @echo off> "%INSTALL_DIR%\agyp-cli.bat"
echo python "%INSTALL_DIR%\agyp_cli.py" %%*>> "%INSTALL_DIR%\agyp-cli.bat"

:: Create agyp-gui.bat launcher in install dir (so it works from anywhere)
echo @echo off> "%INSTALL_DIR%\agyp-gui.bat"
echo pythonw "%INSTALL_DIR%\agyp_gui.py" %%*>> "%INSTALL_DIR%\agyp-gui.bat"

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

:: Add install dir to user PATH if not already there
echo [*] Adding %INSTALL_DIR% to your PATH...
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set CURRENT_PATH=%%b
echo %CURRENT_PATH% | findstr /i "%INSTALL_DIR%" >nul
if errorlevel 1 (
    if defined CURRENT_PATH (
        setx PATH "%CURRENT_PATH%;%INSTALL_DIR%" >nul
    ) else (
        setx PATH "%INSTALL_DIR%" >nul
    )
    echo [+] PATH updated successfully.
) else (
    echo [*] PATH already contains install directory. Skipping.
)

:: Create profile storage directory
if not exist "%USERPROFILE%\agyp-profiles" mkdir "%USERPROFILE%\agyp-profiles"

echo.
echo [+] Installation Complete!
echo.
echo How to launch (open a NEW terminal window after install):
echo   Type 'agyp-cli' anywhere to open the terminal manager.
echo   Type 'agyp-gui' anywhere to open the graphical manager.
echo.
echo Or double-click the .bat files in this folder:
echo   run-cli.bat  -  terminal manager
echo   run-gui.bat  -  graphical manager
echo.
echo Profiles will be stored in: %USERPROFILE%\agyp-profiles\
echo.
pause
