#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# SwingEdge Scanner — Mac Setup Script
# Run this ONCE to install everything and schedule the daily scan
# Usage: bash setup_mac.sh
# ═══════════════════════════════════════════════════════════════

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON=$(which python3)
SCANNER="$SCRIPT_DIR/scanner.py"
PLIST_NAME="com.swingEdge.scanner"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
LOG_DIR="$SCRIPT_DIR/logs"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║       SwingEdge Scanner — Mac Setup              ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Install Python packages ──────────────────────────
echo "📦 Installing Python packages..."
pip3 install yfinance pandas numpy requests --upgrade --quiet
echo "   ✅ yfinance, pandas, numpy, requests installed"
echo ""

# ── Step 2: Create logs directory ────────────────────────────
mkdir -p "$LOG_DIR"
echo "📁 Log directory: $LOG_DIR"
echo ""

# ── Step 3: Test scanner ──────────────────────────────────────
echo "🧪 Running test scan (10 stocks)..."
echo "   This will take ~1 minute..."
cd "$SCRIPT_DIR"
python3 "$SCANNER" --test
echo ""

if [ -f "$SCRIPT_DIR/data.json" ]; then
    echo "   ✅ data.json created successfully"
    SIZE=$(wc -c < "$SCRIPT_DIR/data.json")
    echo "   Size: $SIZE bytes"
else
    echo "   ❌ data.json not found — check scanner errors above"
    exit 1
fi
echo ""

# ── Step 4: Create launchd plist (Mac scheduler) ──────────────
echo "⏰ Setting up daily 4:30 PM schedule..."

mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCANNER</string>
        <string>--push</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>16</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/scanner_stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/scanner_stderr.log</string>

    <key>RunAtLoad</key>
    <false/>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

echo "   ✅ Created: $PLIST_PATH"

# ── Step 5: Load the schedule ─────────────────────────────────
# Unload first in case it was already loaded
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"
echo "   ✅ Scheduled: scanner will run daily at 4:30 PM IST"
echo ""

# ── Step 6: Verify schedule ───────────────────────────────────
echo "📋 Verifying schedule..."
if launchctl list | grep -q "$PLIST_NAME"; then
    echo "   ✅ Schedule active and loaded"
else
    echo "   ⚠️  Schedule may not have loaded — try: launchctl load $PLIST_PATH"
fi
echo ""

# ── Done ──────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════╗"
echo "║              Setup Complete! ✅                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  📅 Scanner runs: Daily at 4:30 PM (auto)"
echo "  📂 Output file:  $SCRIPT_DIR/data.json"
echo "  📋 Logs:         $LOG_DIR/"
echo "  🌐 Dashboard:    https://udayshankar448.github.io/swingEdge/"
echo ""
echo "  MANUAL COMMANDS:"
echo "  Run now:         python3 $SCANNER"
echo "  Test mode:       python3 $SCANNER --test"
echo "  Run + push:      python3 $SCANNER --push"
echo "  Check logs:      tail -f $LOG_DIR/scanner_stdout.log"
echo "  Stop schedule:   launchctl unload $PLIST_PATH"
echo "  Start schedule:  launchctl load $PLIST_PATH"
echo ""
