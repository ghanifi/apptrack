# Capacitor OTA (Live Update) Integration Guide

## Overview

AppTrack provides OTA (Over-The-Air) updates for Capacitor, Ionic, and Cordova apps. This allows you to push JavaScript/HTML/CSS changes to users without going through app store review.

**Limitations:** OTA updates can only change web assets (JS, CSS, HTML, images). Native code changes (new Capacitor plugins, native modules) still require a full app store release.

## How It Works

1. You build and publish your app normally (with a `runtime_version`)
2. When you make JS-only changes, you run `npm run build` and publish the bundle via AppTrack OTA
3. The app checks AppTrack's `/ota/check/{project_id}` endpoint on launch
4. If a new bundle is available, the app downloads and applies it

## Setup

### 1. Install the OTA Helper

No special plugin is required. The check is a simple HTTP call.

```bash
npm install @capacitor/filesystem @capacitor/preferences
```

### 2. Add the OTA Check to Your App

Create `src/ota-updater.ts`:

```typescript
import { Filesystem, Directory } from '@capacitor/filesystem';
import { Preferences } from '@capacitor/preferences';

const APPTRACK_API = 'https://your-apptrack-instance.com/api';
const PROJECT_ID = 'your-project-id';
const RUNTIME_VERSION = '1.0.0'; // Must match your native app version
const CHANNEL = 'production';

interface OTACheckResponse {
  available: boolean;
  update_id?: string;
  bundle_url?: string;
  runtime_version?: string;
  channel?: string;
  platform?: string;
  message?: string;
}

export async function checkForUpdate(): Promise<OTACheckResponse> {
  const platform = getPlatform();
  const url = `${APPTRACK_API}/ota/check/${PROJECT_ID}?channel=${CHANNEL}&platform=${platform}&runtime_version=${RUNTIME_VERSION}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`OTA check failed: ${response.status}`);
  }
  return response.json();
}

export async function applyUpdate(bundleUrl: string, updateId: string): Promise<void> {
  // Download the bundle
  const download = await Filesystem.downloadFile({
    url: bundleUrl,
    path: `ota-bundles/${updateId}.zip`,
    directory: Directory.Data,
  });

  // Save the active update ID
  await Preferences.set({ key: 'ota_active_update', value: updateId });
  await Preferences.set({ key: 'ota_bundle_path', value: download.path ?? '' });

  // The app should reload to apply the update
  // Implementation depends on your setup — see "Applying Updates" below
}

function getPlatform(): string {
  const ua = navigator.userAgent.toLowerCase();
  if (ua.includes('android')) return 'android';
  if (ua.includes('iphone') || ua.includes('ipad')) return 'ios';
  return 'all';
}
```

### 3. Check on App Launch

In your app's entry point (e.g., `src/main.ts` or `src/App.tsx`):

```typescript
import { checkForUpdate, applyUpdate } from './ota-updater';

async function initOTA() {
  try {
    const result = await checkForUpdate();
    if (result.available && result.bundle_url && result.update_id) {
      console.log(`OTA update available: ${result.message}`);
      await applyUpdate(result.bundle_url, result.update_id);
    }
  } catch (err) {
    // OTA check is non-critical — don't block app startup
    console.warn('OTA check failed:', err);
  }
}

// Run after app is ready
initOTA();
```

## Applying Updates

There are several strategies for applying downloaded bundles:

### Strategy A: Next Launch (Recommended)

Download the bundle in the background. On next app launch, the native layer loads the new bundle instead of the built-in one. This requires a small native plugin or Capacitor's built-in `serverPath` configuration.

### Strategy B: Immediate Reload

After downloading, call `window.location.reload()` to reload the webview. This works if your bundle URL serves the updated `index.html`.

### Strategy C: User Prompt

Show a toast/modal asking the user to restart the app:

```typescript
if (result.available) {
  const shouldUpdate = confirm(`Update available: ${result.message}\nRestart now?`);
  if (shouldUpdate) {
    await applyUpdate(result.bundle_url!, result.update_id!);
    window.location.reload();
  }
}
```

## Publishing Updates via AppTrack

### Dashboard

1. Go to your project in AppTrack
2. Click **Live Updates**
3. Fill in the bundle URL (upload your `dist.zip` to MinIO/S3 first)
4. Select channel and platform
5. Click **Publish**

### API

```bash
curl -X POST https://your-apptrack-instance.com/api/ota/custom-bundle \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "your-project-id",
    "channel": "production",
    "platform": "all",
    "runtime_version": "1.0.0",
    "bundle_url": "https://storage.example.com/bundles/v1.2.zip",
    "message": "Bug fixes and performance improvements"
  }'
```

### Build & Upload Workflow

```bash
# 1. Build your web assets
npm run build

# 2. Zip the output
cd dist && zip -r ../bundle.zip . && cd ..

# 3. Upload to your storage (MinIO, S3, etc.)
mc cp bundle.zip myminio/apptrack-bundles/myapp/v1.2.zip

# 4. Publish via AppTrack API
curl -X POST .../api/ota/custom-bundle \
  -d '{"bundle_url": "https://storage.example.com/bundles/myapp/v1.2.zip", ...}'
```

## Rollback

If an update causes issues, rollback from the AppTrack dashboard or API:

```bash
curl -X POST https://your-apptrack-instance.com/api/ota/rollback \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d 'project_id=your-project-id&channel=production&platform=all'
```

This re-publishes the previous bundle, so the next app check will download the older version.

## Channels

| Channel | Use Case |
|---------|----------|
| `production` | All users |
| `staging` | Internal QA testing |
| `beta` | Beta testers |

Apps should be configured to check the appropriate channel. You can use environment variables or build-time configuration to set the channel.

## Runtime Version Matching

The `runtime_version` parameter ensures that OTA bundles are only delivered to compatible native app versions. If your native code changes (new plugin, updated Capacitor version), bump the runtime version.

Example:
- App v1.0.0 (runtime_version: "1.0.0") — receives OTA bundles with runtime_version "1.0.0"
- App v1.1.0 with new native plugin (runtime_version: "1.1.0") — receives only "1.1.0" bundles
- OTA bundle for JS-only fix — published with runtime_version "1.0.0" reaches all v1.0.0 apps

## Security Notes

- The `/ota/check/{project_id}` endpoint is **public** (no auth required) so mobile apps can call it
- Bundle URLs should use HTTPS
- Consider adding bundle hash verification in your app for integrity checks
- OTA updates bypass app store review — ensure your update process has appropriate internal review
