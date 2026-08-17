#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"

mkdir -p "$BIN_DIR"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[!] Python 3 not found. Install via: brew install python"
    exit 1
fi

# Install customtkinter
echo "[*] Installing dependencies..."
pip3 install --user --quiet customtkinter 2>/dev/null || pip3 install --quiet customtkinter 2>/dev/null || true

# Verify
if ! python3 -c "import customtkinter" &>/dev/null; then
    echo "[!] customtkinter install failed. Try: pip3 install customtkinter"
    exit 1
fi

# CLI
cp "$SCRIPT_DIR/agyp_cli.py" "$BIN_DIR/agyp-cli"
chmod +x "$BIN_DIR/agyp-cli"
ln -sf "$BIN_DIR/agyp-cli" "$BIN_DIR/agyp"

# GUI wrapper
cat > "$BIN_DIR/agyp-gui" << EOF
#!/bin/bash
exec python3 "$SCRIPT_DIR/agyp_gui.py" "\$@"
EOF
chmod +x "$BIN_DIR/agyp-gui"

# Profile dir
mkdir -p "$HOME/.agyp-profiles"

echo -e "\033[34m[+] Antigravity Profiles Suite\033[0m installed!"
echo "Commands: agyp-cli, agyp-gui"
echo "Note: Make sure $BIN_DIR is in your PATH"
echo "      Add to ~/.zshrc: export PATH=\"\$HOME/.local/bin:\$PATH\""
