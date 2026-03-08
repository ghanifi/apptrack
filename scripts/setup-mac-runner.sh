#!/bin/bash
set -euo pipefail

# AppTrack Mac Mini M4 Self-Hosted Runner Setup
# Usage: ./setup-mac-runner.sh <GITHUB_ORG> <GITHUB_REPO> <RUNNER_TOKEN>

GITHUB_ORG="${1:?Usage: $0 <GITHUB_ORG> <GITHUB_REPO> <RUNNER_TOKEN>}"
GITHUB_REPO="${2:?Usage: $0 <GITHUB_ORG> <GITHUB_REPO> <RUNNER_TOKEN>}"
RUNNER_TOKEN="${3:?Usage: $0 <GITHUB_ORG> <GITHUB_REPO> <RUNNER_TOKEN>}"

RUNNER_DIR="$HOME/actions-runner"
RUNNER_LABELS="self-hosted,macos-arm64,apptrack-ios"

echo "=== AppTrack iOS Runner Setup ==="
echo "Org: $GITHUB_ORG | Repo: $GITHUB_REPO"
echo ""

# 1. Install Homebrew if missing
if ! command -v brew &>/dev/null; then
  echo "[1/7] Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv)"
else
  echo "[1/7] Homebrew already installed"
fi

# 2. Install dependencies
echo "[2/7] Installing dependencies..."
brew install node@20 cocoapods fastlane ruby git 2>/dev/null || true
brew link node@20 --force 2>/dev/null || true

# Verify Xcode
if ! xcode-select -p &>/dev/null; then
  echo "WARNING: Xcode is not installed. Install Xcode 15+ from the App Store."
  echo "Then run: sudo xcode-select --switch /Applications/Xcode.app"
fi

# 3. Install xcpretty for build log formatting
echo "[3/7] Installing xcpretty..."
gem install xcpretty 2>/dev/null || sudo gem install xcpretty 2>/dev/null || true

# 4. Download and configure GitHub Actions runner
echo "[4/7] Setting up GitHub Actions runner..."
mkdir -p "$RUNNER_DIR" && cd "$RUNNER_DIR"

RUNNER_VERSION="2.321.0"
RUNNER_ARCH="osx-arm64"
RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"

if [ ! -f "./config.sh" ]; then
  curl -sL "$RUNNER_URL" | tar xz
fi

# 5. Configure runner
echo "[5/7] Configuring runner with labels: $RUNNER_LABELS"
./config.sh \
  --url "https://github.com/$GITHUB_ORG/$GITHUB_REPO" \
  --token "$RUNNER_TOKEN" \
  --labels "$RUNNER_LABELS" \
  --name "apptrack-ios-$(hostname -s)" \
  --work "_work" \
  --replace

# 6. Install as launchd service (auto-start on boot)
echo "[6/7] Installing launchd service..."
PLIST_PATH="$HOME/Library/LaunchAgents/com.apptrack.runner.plist"
cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.apptrack.runner</string>
  <key>ProgramArguments</key>
  <array>
    <string>${RUNNER_DIR}/run.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${RUNNER_DIR}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${RUNNER_DIR}/runner-stdout.log</string>
  <key>StandardErrorPath</key>
  <string>${RUNNER_DIR}/runner-stderr.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
</dict>
</plist>
PLIST

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

# 7. Verify
echo "[7/7] Verifying setup..."
echo ""
./verify-mac-runner.sh 2>/dev/null || bash "$(dirname "$0")/verify-mac-runner.sh" 2>/dev/null || echo "Run verify-mac-runner.sh to check status"

echo ""
echo "=== Setup Complete ==="
echo "Runner will auto-start on login. Check GitHub > Settings > Actions > Runners for 'online' status."
