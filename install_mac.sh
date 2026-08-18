#!/bin/bash
set -e

# agyp — macOS CLI-only installer
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
INSTALL_DIR="$HOME/.local/share/agyp"   # stable copy — survives repo moves

mkdir -p "$BIN_DIR" "$INSTALL_DIR"

# ── Python check ──────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "[!] Python 3 not found. Install via: brew install python"
    exit 1
fi
echo "[*] Python 3 found: $(python3 --version)"

# ── Copy CLI script to stable location ───────────────────────────────────────
echo "[*] Installing agyp_cli.py to $INSTALL_DIR..."
cp "$SCRIPT_DIR/agyp_cli.py" "$INSTALL_DIR/agyp_cli.py"
chmod +x "$INSTALL_DIR/agyp_cli.py"

# ── CLI launcher ──────────────────────────────────────────────────────────────
cat > "$BIN_DIR/agyp-cli" << EOF
#!/usr/bin/env python3
import sys, runpy
sys.argv[0] = "$INSTALL_DIR/agyp_cli.py"
runpy.run_path("$INSTALL_DIR/agyp_cli.py", run_name="__main__")
EOF
chmod +x "$BIN_DIR/agyp-cli"
ln -sf "$BIN_DIR/agyp-cli" "$BIN_DIR/agyp"

# ── Profile storage directory ─────────────────────────────────────────────────
mkdir -p "$HOME/agyp-profiles"

echo ""
echo -e "\033[34m[+] Antigravity Profiles (CLI)\033[0m installed successfully!"
echo ""
echo "Commands:"
echo "  agyp           — launch profile manager"
echo "  agyp-cli       — same as above"
echo "  agyp <name>    — launch a named profile directly (isolated mode)"
echo ""
echo "Profiles stored in: ~/agyp-profiles/"

if ! echo "$PATH" | grep -q "$BIN_DIR"; then
    echo ""
    echo "[!] Make sure $BIN_DIR is in your PATH."
    echo "    Add to ~/.zshrc:  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
