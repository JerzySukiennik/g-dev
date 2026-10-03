#!/bin/bash
# Install and start the LaunchAgent that keeps G-Dev training. Remove with:
#   launchctl bootout gui/$(id -u)/fun.gzowo.g-dev.chain && rm ~/Library/LaunchAgents/fun.gzowo.g-dev.chain.plist
set -e
cp "$(dirname "$0")/fun.gzowo.g-dev.chain.plist" ~/Library/LaunchAgents/
rm -f "$(dirname "$0")/STOP"
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/fun.gzowo.g-dev.chain.plist
echo "chain started, log: ~/Library/Logs/g-dev-chain.log"
