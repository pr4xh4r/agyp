# Antigravity Profiles Suite (AGYP)

A cross-platform manager for isolated Antigravity environments. Supports Windows, macOS, and Linux.

## 🐧 Linux & 🍏 macOS

### Installation
Open your terminal and run the included bash script:
```bash
bash install.sh
```
This automatically sets up a virtual environment, installs the UI framework, and links the commands globally to `~/.local/bin`.

### Usage
After installation, you can launch the tools from anywhere:
- **CLI Mode:** Type `agyp` or `agyp-cli` in your terminal.
- **GUI Mode:** Type `agyp-gui` in your terminal, or search for "Antigravity Profile Manager" in your application launcher.

---

## 🪟 Windows

### Installation
1. Ensure you have **Python 3** installed and added to your system PATH.
2. Double-click the `install.bat` file in this folder, or run it from Command Prompt:
```cmd
install.bat
```
This script will automatically set up the virtual environment and install the required dependencies (like `customtkinter` for the GUI).

### Usage
On Windows, you can launch the tools by running the provided shortcut scripts in this directory:
- **CLI Mode:** Double-click `run-cli.bat` (or type `python agyp_cli.py` in your terminal).
- **GUI Mode:** Double-click `run-gui.bat` (or type `venv\Scripts\python.exe agyp_gui.py` in your terminal).

You can easily right-click `run-gui.bat` and select **"Send to > Desktop (create shortcut)"** to get a quick launcher on your Windows desktop!

---

## Features
- **Total Isolation**: Each profile creates a sandboxed `HOME` directory under `~/.agy_accounts/`.
- **Zero Configuration**: No complex dependency hell. The CLI uses 100% standard Python libraries, and the GUI safely contains its dependencies in an isolated virtual environment.
- **Cross-Platform Compatibility**: Native keyboard handling and window spawning tailored for Windows, Mac, and Linux.
