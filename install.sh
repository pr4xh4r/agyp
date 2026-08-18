#!/bin/bash
set -e

# agyp — Linux/macOS CLI-only installer
# Resolve the real user home — prevents issues when run inside an isolated profile env
REAL_HOME="$(getent passwd "$USER" 2>/dev/null | cut -d: -f6 || echo "$HOME")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$REAL_HOME/.local/bin"
INSTALL_DIR="$REAL_HOME/.local/share/agyp"   # stable copy — survives repo moves

mkdir -p "$BIN_DIR" "$INSTALL_DIR"

# ── Python check ──────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "[!] Python 3 not found. Install it with your package manager."
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

# Alias 'agyp' → 'agyp-cli'
ln -sf "$BIN_DIR/agyp-cli" "$BIN_DIR/agyp"

# ── Profile storage directory ─────────────────────────────────────────────────
mkdir -p "$REAL_HOME/agyp-profiles"

echo ""
echo -e "\033[38;2;66;133;244m[+] Antigravity Profiles (CLI)\033[0m installed successfully!"
echo ""
echo "Commands:"
echo -e "  \033[1;37magyp\033[0m           — launch profile manager"
echo -e "  \033[1;37magyp-cli\033[0m       — same as above"
echo -e "  \033[1;37magyp <name>\033[0m    — launch a named profile directly (isolated mode)"
echo ""
echo "Profiles stored in: ~/agyp-profiles/"

# ── PATH hint if needed ───────────────────────────────────────────────────────
if ! echo "$PATH" | grep -q "$BIN_DIR"; then
    echo ""
    echo "[!] $BIN_DIR is not in your PATH."
    echo "    Add this to your shell config (~/.bashrc or ~/.zshrc):"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
