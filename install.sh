#!/bin/bash
set -e

# Resolve the real user home — prevents issues when run inside an isolated profile env
REAL_HOME="$(getent passwd "$USER" | cut -d: -f6)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$REAL_HOME/.local/bin"
DESKTOP_DIR="$REAL_HOME/.local/share/applications"
VENV_DIR="$REAL_HOME/.local/share/agyp-venv"

mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"

# ── Dependency check & install ────────────────────────────────────────────────
echo "[*] Checking Python dependencies..."

install_customtkinter() {
    # Try pip with --user first (standard)
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
elif [ -f "$REAL_HOME/.local/share/agyp-venv/bin/python3" ] && "$REAL_HOME/.local/share/agyp-venv/bin/python3" -c "import customtkinter" &>/dev/null; then
    echo "[*] customtkinter found in agyp venv."
    PYTHON_CMD="$REAL_HOME/.local/share/agyp-venv/bin/python3"
else
    install_customtkinter
    # Check which python now has it
    if python3 -c "import customtkinter" &>/dev/null; then
        PYTHON_CMD="python3"
    else
        PYTHON_CMD="$REAL_HOME/.local/share/agyp-venv/bin/python3"
    fi
fi

# ── CLI ───────────────────────────────────────────────────────────────────────
cp "$SCRIPT_DIR/agyp_cli.py" "$BIN_DIR/agyp-cli"
chmod +x "$BIN_DIR/agyp-cli"

# Alias 'agyp' → 'agyp-cli'
ln -sf "$BIN_DIR/agyp-cli" "$BIN_DIR/agyp"

# ── GUI Wrapper ───────────────────────────────────────────────────────────────
# Bake the resolved python path so it always works
cat > "$BIN_DIR/agyp-gui" << EOF
#!/bin/bash
exec "$PYTHON_CMD" "$SCRIPT_DIR/agyp_gui.py" "\$@"
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
mkdir -p "$REAL_HOME/.agyp-profiles"

echo -e "\033[38;2;66;133;244m[+] Antigravity Profiles Suite\033[0m successfully installed!"
echo "Available commands:"
echo -e "  \033[1;37magyp-cli\033[0m (or 'agyp') - Command Line Interface"
echo -e "  \033[1;37magyp-gui\033[0m            - Graphical User Interface"
echo "A desktop shortcut has also been added to your app launcher."
