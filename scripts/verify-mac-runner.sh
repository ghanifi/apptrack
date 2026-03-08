#!/bin/bash
# AppTrack Mac Mini Runner Health Check

echo "=== AppTrack iOS Runner Health Check ==="
echo ""

check() {
  local name="$1"
  local cmd="$2"
  local result
  result=$(eval "$cmd" 2>/dev/null) || result="NOT INSTALLED"
  printf "  %-25s %s\n" "$name:" "$result"
}

echo "System:"
check "macOS" "sw_vers -productVersion"
check "Architecture" "uname -m"
check "Hostname" "hostname -s"
check "Disk Free" "df -h / | tail -1 | awk '{print \$4}'"
check "RAM" "sysctl -n hw.memsize | awk '{printf \"%.0f GB\", \$1/1073741824}'"
check "CPU Cores" "sysctl -n hw.ncpu"

echo ""
echo "Development Tools:"
check "Xcode" "xcodebuild -version 2>/dev/null | head -1"
check "Xcode CLT" "xcode-select -p"
check "Node.js" "node --version"
check "npm" "npm --version"
check "CocoaPods" "pod --version"
check "Fastlane" "fastlane --version 2>/dev/null | head -1"
check "Ruby" "ruby --version | awk '{print \$2}'"
check "Java" "java -version 2>&1 | head -1"
check "Git" "git --version"

echo ""
echo "Runner Status:"
RUNNER_DIR="$HOME/actions-runner"
if [ -f "$RUNNER_DIR/.runner" ]; then
  check "Runner Config" "echo 'Configured'"
  check "Runner Name" "cat $RUNNER_DIR/.runner 2>/dev/null | python3 -c \"import sys,json;print(json.load(sys.stdin).get('agentName','unknown'))\" 2>/dev/null || echo 'unknown'"
else
  check "Runner Config" "echo 'NOT CONFIGURED'"
fi

if pgrep -f "actions-runner" >/dev/null 2>&1; then
  check "Runner Process" "echo 'RUNNING'"
else
  check "Runner Process" "echo 'NOT RUNNING'"
fi

PLIST="$HOME/Library/LaunchAgents/com.apptrack.runner.plist"
if [ -f "$PLIST" ]; then
  check "LaunchAgent" "echo 'Installed'"
else
  check "LaunchAgent" "echo 'NOT INSTALLED'"
fi

echo ""
echo "=== Check Complete ==="
