@echo off
setlocal
echo [*] Setting up Antigravity Profiles Suite...
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python not found. Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

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

echo.
echo [+] Installation Complete!
echo.
echo You can now use the provided batch files to launch the tools:
echo   - Double-click 'run-cli.bat' for the terminal manager.
echo   - Double-click 'run-gui.bat' for the graphical manager.
echo.
pause
