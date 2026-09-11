#!/usr/bin/env bash
set -Eeuo pipefail

echo "========================================="
echo "   Uninstalling JARVIS Linux Assistant   "
echo "========================================="

# 1. Stop and disable systemd user service
if command -v systemctl &> /dev/null && [ -d /run/systemd/system ]; then
    echo "Stopping and disabling systemd user service..."
    systemctl --user stop jarvis.service 2>/dev/null || true
    systemctl --user disable jarvis.service 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/jarvis.service"
    systemctl --user daemon-reload 2>/dev/null || true
fi

# 2. Remove desktop application shortcuts and icons
echo "Removing desktop application shortcuts..."
rm -f "$HOME/.local/share/applications/jarvis.desktop"
rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/jarvis.png"
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

# 3. Remove executable binary symlink
echo "Removing executable binary symlink..."
rm -f "$HOME/.local/bin/jarvis"

# 4. Remove installation files
INSTALL_DIR="${JARVIS_INSTALL_DIR:-$HOME/.local/share/jarvis}"
if [ -d "$INSTALL_DIR" ]; then
    echo "Removing installation files at $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
fi

# 5. Optional data purge if requested via --purge flag
if [[ "${1:-}" == "--purge" ]]; then
    echo "Purging user state, configuration, and cache..."
    rm -rf "$HOME/.config/jarvis"
    rm -rf "$HOME/.local/state/jarvis"
    rm -rf "$HOME/.cache/jarvis"
fi

echo "========================================="
echo "JARVIS has been successfully uninstalled."
echo "========================================="
