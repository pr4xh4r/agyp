@echo off
echo [*] Setting up Antigravity Profiles Suite...
echo.

:: Create Virtual Environment
echo [*] Creating virtual environment...
python -m venv venv

:: Install Requirements
echo [*] Installing GUI dependencies...
call venv\Scripts\activate.bat
pip install customtkinter

echo.
echo [+] Installation Complete!
echo.
echo You can now use the provided batch files to launch the tools:
echo  - Double-click 'run-cli.bat' for the terminal manager.
echo  - Double-click 'run-gui.bat' for the graphical manager.
pause
