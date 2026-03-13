# Self-Hosted iOS Runner — Mac Mini M4 Setup Guide

> **NOT (v2.1):** AppTrack artık varsayılan olarak GitHub'ın ücretsiz `macos-latest` hosted runner'ını kullanmaktadır. Self-hosted runner **opsiyoneldir** — sadece özel gereksinimler (private network, özel Xcode sürümü, yüksek build hacmi) için gereklidir. Çoğu kullanıcı bu rehbere ihtiyaç duymaz.

## Hardware Requirements

- **Mac Mini M4** (or any Apple Silicon Mac)
- macOS 14+ (Sonoma or later)
- 16 GB RAM minimum
- 256 GB SSD minimum (Xcode alone ~30 GB)
- Stable internet connection

## Network Configuration

The runner needs outbound access to:
- `github.com` (443) — Runner registration + workflow dispatch
- `*.actions.githubusercontent.com` (443) — Artifact upload/download
- Your AppTrack gateway webhook URL

For private networks, consider [Tailscale](https://tailscale.com) for secure connectivity without port forwarding.

## Quick Setup

```bash
# 1. Get a runner token from GitHub:
#    Repository > Settings > Actions > Runners > New self-hosted runner
#    Copy the token shown

# 2. Run the setup script:
./scripts/setup-mac-runner.sh <GITHUB_ORG> <GITHUB_REPO> <RUNNER_TOKEN>

# 3. Verify:
./scripts/verify-mac-runner.sh
```

## Manual Setup Steps

### 1. Install Xcode

```bash
# Install from Mac App Store, then:
sudo xcode-select --switch /Applications/Xcode.app
xcodebuild -license accept
```

### 2. Install Dependencies

```bash
brew install node@20 cocoapods fastlane ruby git
brew link node@20 --force
gem install xcpretty
```

### 3. Register GitHub Runner

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
curl -sL https://github.com/actions/runner/releases/latest/download/actions-runner-osx-arm64-2.321.0.tar.gz | tar xz
./config.sh \
  --url https://github.com/ORG/REPO \
  --token YOUR_TOKEN \
  --labels "self-hosted,macos-arm64,apptrack-ios" \
  --name "apptrack-ios-$(hostname -s)"
```

### 4. Auto-Start as Service

The setup script creates a launchd service at `~/Library/LaunchAgents/com.apptrack.runner.plist`.

Manual control:
```bash
# Start
launchctl load ~/Library/LaunchAgents/com.apptrack.runner.plist

# Stop
launchctl unload ~/Library/LaunchAgents/com.apptrack.runner.plist

# Check status
launchctl list | grep apptrack
```

## Security Best Practices

### Keychain Isolation
Each build creates a temporary keychain (`apptrack-build-<id>.keychain-db`) that is deleted after the build completes. This prevents certificate leakage between builds.

### Build Cleanup
The workflow templates automatically clean up:
- Temporary keychains
- Downloaded certificates and profiles
- Build intermediates

### Access Control
- Use a dedicated macOS user for the runner
- Enable FileVault disk encryption
- Disable auto-login if the Mac is in a shared space
- Rotate the GitHub runner token periodically

## Monitoring

### Check Runner Status
```bash
# Local check
./scripts/verify-mac-runner.sh

# GitHub API check
gh api repos/ORG/REPO/actions/runners --jq '.runners[] | {name, status, labels: [.labels[].name]}'
```

### Disk Space
Xcode caches and DerivedData can grow large. Clean periodically:
```bash
# Clean Xcode derived data
rm -rf ~/Library/Developer/Xcode/DerivedData/*

# Clean CocoaPods cache
pod cache clean --all

# Clean npm cache
npm cache clean --force
```

### Auto-Restart
The launchd `KeepAlive` flag ensures the runner restarts if it crashes. Logs are at:
- `~/actions-runner/runner-stdout.log`
- `~/actions-runner/runner-stderr.log`

## Cost

- **Hardware**: Mac Mini M4 ~$599 one-time
- **Electricity**: ~$5/month
- **GitHub Actions minutes**: Free (self-hosted runners don't count against quota)
- **Total recurring**: ~$5/month
