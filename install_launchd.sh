#!/usr/bin/env bash
# install_launchd.sh — install Ornery-Kiwi as a macOS login item via launchd
set -euo pipefail

LABEL="com.ornery-kiwi.agent"
PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/com.ornery-kiwi.agent.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs"

# ── Resolve Python interpreter ────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "ERROR: python3 not found in PATH." >&2
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Python:      $PYTHON_BIN"
echo "Project:     $PROJECT_DIR"
echo "Plist dest:  $PLIST_DEST"
echo ""

# ── Substitute placeholders ──────────────────────────────────────────────────
mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

sed \
    -e "s|PYTHON_BIN|$PYTHON_BIN|g" \
    -e "s|PROJECT_DIR|$PROJECT_DIR|g" \
    -e "s|HOME_DIR|$HOME|g" \
    "$PLIST_SRC" > "$PLIST_DEST"

echo "Wrote $PLIST_DEST"

# ── Load / reload ────────────────────────────────────────────────────────────
if launchctl list "$LABEL" &>/dev/null 2>&1; then
    echo "Unloading existing agent..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

launchctl load "$PLIST_DEST"
echo ""
echo "Ornery-Kiwi agent loaded. It will auto-start on every login."
echo ""
echo "  Check status:  launchctl list $LABEL"
echo "  View logs:     tail -f $LOG_DIR/ornery-kiwi.log"
echo "  View errors:   tail -f $LOG_DIR/ornery-kiwi.err"
echo "  Stop:          launchctl unload $PLIST_DEST"
echo "  Start:         launchctl load   $PLIST_DEST"
