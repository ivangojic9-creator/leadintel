#!/bin/sh
# Installs LeadIntel as a launchd job: runs every 30 minutes, survives reboots.
# Uses a Downloads-external copy dir? No — launchd CAN read Downloads when running
# as your user agent with Full Disk Access for /bin/sh; if collection fails with
# permission errors, move this folder out of ~/Downloads (e.g. ~/LeadIntel) and rerun.
PLIST=~/Library/LaunchAgents/com.ruzica.leadintel.plist
DIR="$(cd "$(dirname "$0")" && pwd)"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.ruzica.leadintel</string>
  <key>ProgramArguments</key>
  <array><string>/usr/bin/python3</string><string>$DIR/run.py</string><string>run</string></array>
  <key>StartInterval</key><integer>1800</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/tmp/leadintel.log</string>
  <key>StandardErrorPath</key><string>/tmp/leadintel.err</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST"
echo "installed: runs every 30 min. Logs: /tmp/leadintel.log"
echo "uninstall: launchctl unload $PLIST && rm $PLIST"
