#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
INSTALL_DIR="$HOME/.local/share/agyp"   # stable copy — survives repo moves

mkdir -p "$BIN_DIR" "$INSTALL_DIR"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[!] Python 3 not found. Install via: brew install python"
    exit 1
fi

# Install customtkinter
echo "[*] Installing dependencies..."
if ! pip3 install --user --quiet customtkinter 2>/dev/null; then
    pip3 install --quiet customtkinter 2>/dev/null || true
fi

# Verify
if ! python3 -c "import customtkinter" &>/dev/null; then
    echo "[!] customtkinter install failed. Try: pip3 install customtkinter"
    exit 1
fi

# Copy scripts to stable location (survives repo moves)
echo "[*] Installing scripts to $INSTALL_DIR..."
cp "$SCRIPT_DIR/agyp_cli.py" "$INSTALL_DIR/agyp_cli.py"
cp "$SCRIPT_DIR/agyp_gui.py" "$INSTALL_DIR/agyp_gui.py"
chmod +x "$INSTALL_DIR/agyp_cli.py" "$INSTALL_DIR/agyp_gui.py"

# CLI launcher
cat > "$BIN_DIR/agyp-cli" << EOF
#!/usr/bin/env python3
import sys, runpy
sys.argv[0] = "$INSTALL_DIR/agyp_cli.py"
runpy.run_path("$INSTALL_DIR/agyp_cli.py", run_name="__main__")
EOF
chmod +x "$BIN_DIR/agyp-cli"
ln -sf "$BIN_DIR/agyp-cli" "$BIN_DIR/agyp"

# GUI wrapper
cat > "$BIN_DIR/agyp-gui" << EOF
#!/bin/bash
exec python3 "$INSTALL_DIR/agyp_gui.py" "\$@"
EOF
chmod +x "$BIN_DIR/agyp-gui"

# Profile dir
mkdir -p "$HOME/agyp-profiles"

echo -e "\033[34m[+] Antigravity Profiles Suite\033[0m installed!"
echo ""
echo "Commands: agyp  (or agyp-cli),  agyp-gui"
echo "Profiles stored in: ~/agyp-profiles/"
echo ""

if ! echo "$PATH" | grep -q "$BIN_DIR"; then
    echo "[!] Make sure $BIN_DIR is in your PATH."
    echo "    Add to ~/.zshrc:  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
