#!/bin/bash
set -e

# Resolve the real user home — prevents issues when run inside an isolated profile env
REAL_HOME="$(getent passwd "$USER" | cut -d: -f6)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$REAL_HOME/.local/bin"
DESKTOP_DIR="$REAL_HOME/.local/share/applications"
INSTALL_DIR="$REAL_HOME/.local/share/agyp"   # stable copy — survives repo moves
VENV_DIR="$REAL_HOME/.local/share/agyp-venv"

mkdir -p "$BIN_DIR" "$DESKTOP_DIR" "$INSTALL_DIR"

# ── Dependency check & install ────────────────────────────────────────────────
echo "[*] Checking Python dependencies..."

install_customtkinter() {
    if pip3 install --user --quiet customtkinter 2>/dev/null; then
        return 0
    fi
    # On managed environments (Arch, Debian 12+), use a dedicated venv
    echo "[*] System Python is managed. Creating isolated venv at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --quiet customtkinter
    return 0
}

if python3 -c "import customtkinter" &>/dev/null; then
    echo "[*] customtkinter already installed."
    PYTHON_CMD="python3"
elif [ -f "$VENV_DIR/bin/python3" ] && "$VENV_DIR/bin/python3" -c "import customtkinter" &>/dev/null; then
    echo "[*] customtkinter found in agyp venv."
    PYTHON_CMD="$VENV_DIR/bin/python3"
else
    install_customtkinter
    if python3 -c "import customtkinter" &>/dev/null; then
        PYTHON_CMD="python3"
    else
        PYTHON_CMD="$VENV_DIR/bin/python3"
    fi
fi

# ── Copy scripts to stable location (survives repo moves) ─────────────────────
echo "[*] Installing scripts to $INSTALL_DIR..."
cp "$SCRIPT_DIR/agyp_cli.py" "$INSTALL_DIR/agyp_cli.py"
cp "$SCRIPT_DIR/agyp_gui.py" "$INSTALL_DIR/agyp_gui.py"
chmod +x "$INSTALL_DIR/agyp_cli.py" "$INSTALL_DIR/agyp_gui.py"

# ── CLI launcher ──────────────────────────────────────────────────────────────
cat > "$BIN_DIR/agyp-cli" << EOF
#!/usr/bin/env python3
import sys, runpy
sys.argv[0] = "$INSTALL_DIR/agyp_cli.py"
runpy.run_path("$INSTALL_DIR/agyp_cli.py", run_name="__main__")
EOF
chmod +x "$BIN_DIR/agyp-cli"

# Alias 'agyp' → 'agyp-cli'
ln -sf "$BIN_DIR/agyp-cli" "$BIN_DIR/agyp"

# ── GUI Wrapper ───────────────────────────────────────────────────────────────
cat > "$BIN_DIR/agyp-gui" << EOF
#!/bin/bash
exec "$PYTHON_CMD" "$INSTALL_DIR/agyp_gui.py" "\$@"
EOF
chmod +x "$BIN_DIR/agyp-gui"

# ── Desktop Entry (Linux app launcher) ───────────────────────────────────────
cat > "$DESKTOP_DIR/agyp-gui.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Antigravity Profile Manager
Comment=Manage and launch isolated Antigravity profiles
Exec=$BIN_DIR/agyp-gui
Icon=utilities-terminal
Terminal=false
Categories=Utility;Development;
EOF

# ── Profile storage directory ─────────────────────────────────────────────────
mkdir -p "$REAL_HOME/agyp-profiles"

echo -e "\033[38;2;66;133;244m[+] Antigravity Profiles Suite\033[0m successfully installed!"
echo ""
echo "Available commands:"
echo -e "  \033[1;37magyp\033[0m (or \033[1;37magyp-cli\033[0m)  — Command Line Interface"
echo -e "  \033[1;37magyp-gui\033[0m              — Graphical User Interface"
echo ""
echo "A desktop shortcut has been added to your app launcher."
echo ""
echo "Profiles stored in: ~/agyp-profiles/"

# ── PATH hint if needed ───────────────────────────────────────────────────────
if ! echo "$PATH" | grep -q "$BIN_DIR"; then
    echo ""
    echo "[!] $BIN_DIR is not in your PATH."
    echo "    Add this to your shell config (~/.bashrc or ~/.zshrc):"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
