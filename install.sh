#!/bin/bash
set -e

BIN_DIR="/home/pr4xh4r/.local/bin"
DESKTOP_DIR="/home/pr4xh4r/.local/share/applications"

mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"

# Install CLI
cp agyp_cli.py "$BIN_DIR/agyp-cli"
chmod +x "$BIN_DIR/agyp-cli"

# Also link 'agyp' to CLI for backward compatibility if desired
ln -sf "$BIN_DIR/agyp-cli" "$BIN_DIR/agyp"

# Install GUI
cp agyp_gui.py "$BIN_DIR/agyp-gui"
chmod +x "$BIN_DIR/agyp-gui"

# Create Desktop Entry for GUI
cat << 'EOF' > "$DESKTOP_DIR/agyp-gui.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=Antigravity Profile Manager
Comment=Manage and launch isolated Antigravity profiles
Exec=/home/pr4xh4r/.local/bin/agyp-gui
Icon=utilities-terminal
Terminal=false
Categories=Utility;Development;
EOF

echo -e "\033[38;2;66;133;244m[+] Antigravity Profiles Suite\033[0m successfully installed!"
echo "Available commands:"
echo -e "  \033[1;37magyp-cli\033[0m (or 'agyp') - Command Line Interface"
echo -e "  \033[1;37magyp-gui\033[0m            - Graphical User Interface"
echo "A desktop shortcut has also been added to your app launcher."
