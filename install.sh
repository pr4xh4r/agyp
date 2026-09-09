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
VERSION=$(python3 -c "import re; print(re.search(r'VERSION = \"([^\"]+)\"', open('$INSTALL_DIR/agyp_cli.py').read()).group(1))" 2>/dev/null || echo "?")
echo -e "\033[38;2;66;133;244m[+] Antigravity Profiles v$VERSION\033[0m installed successfully!"
echo ""
echo "Commands:"
echo -e "  \033[1;37magyp\033[0m                      — launch profile manager (interactive)"
echo -e "  \033[1;37magyp <name>\033[0m               — launch a named profile (isolated mode)"
echo -e "  \033[1;37magyp list\033[0m                 — list all profiles + emails"
echo -e "  \033[1;37magyp info <name>\033[0m          — detailed profile info"
echo -e "  \033[1;37magyp rename <old> <new>\033[0m   — rename a profile"
echo -e "  \033[1;37magyp delete <name>\033[0m        — delete a profile"
echo -e "  \033[1;37magyp duplicate <src> <dst>\033[0m — clone a profile (tokens stripped)"
echo -e "  \033[33magyp reset-auth <name>\033[0m    — \033[33mclear tokens → force fresh login\033[0m"
echo ""
echo "Profiles stored in: ~/agyp-profiles/"

# ── PATH hint if needed ───────────────────────────────────────────────────────
if ! echo "$PATH" | grep -q "$BIN_DIR"; then
    echo ""
    echo "[!] $BIN_DIR is not in your PATH."
    echo "    Add this to your shell config (~/.bashrc or ~/.zshrc):"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
