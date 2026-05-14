#!/bin/zsh
# Install the hourly local scrape launchd job.
# Usage:
#   bash scripts/install_launchd.sh         # install + load
#   bash scripts/install_launchd.sh uninstall

set -e
PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/com.usama.job-scraper-local.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.usama.job-scraper-local.plist"

if [ "$1" = "uninstall" ]; then
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    rm -f "$PLIST_DEST"
    echo "Uninstalled."
    exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents"
cp "$PLIST_SRC" "$PLIST_DEST"
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"
echo "Installed and loaded: $PLIST_DEST"
echo ""
echo "Scrape runs every hour at :17 minutes past."
echo "Logs:"
echo "  stdout: .launchd.stdout.log"
echo "  stderr: .launchd.stderr.log"
echo ""
echo "Test now: ./.venv/bin/python3 scripts/scrape_local.py --window 24h --sources indeed --max-keywords 3"
