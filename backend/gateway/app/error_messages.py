ERROR_MESSAGES = {
    "build.missing_dependency": {
        "title": "Missing Dependency",
        "message": "Your project is missing a required dependency. Check your package.json or pubspec.yaml.",
        "action": "Review build logs and install missing packages.",
    },
    "build.framework_not_detected": {
        "title": "Framework Not Detected",
        "message": "We couldn't identify your project's framework. Make sure your repo has the correct config files (package.json, pubspec.yaml, etc).",
        "action": "Verify your repo structure matches the expected framework layout.",
    },
    "build.timeout": {
        "title": "Build Timeout",
        "message": "Your build exceeded the maximum time limit. This usually happens with very large projects or slow dependencies.",
        "action": "Check for large asset files or slow dependency downloads. Try again.",
    },
    "build.provider_unavailable": {
        "title": "Build Provider Unavailable",
        "message": "The build provider (EAS/Codemagic/GitHub Actions) is temporarily unavailable.",
        "action": "Wait a few minutes and try again. Check the Status page for updates.",
    },
    "build.credential_expired": {
        "title": "Build Credentials Expired",
        "message": "Your build provider token has expired.",
        "action": "Go to Settings > Credentials and update your EAS or Codemagic token.",
    },
    "build.quota_exceeded": {
        "title": "Build Quota Reached",
        "message": "You've reached your monthly build limit for your current plan.",
        "action": "Upgrade your plan or wait for next billing cycle.",
    },
    "build.budget_exceeded": {
        "title": "Budget Limit Reached",
        "message": "This build would exceed your monthly budget cap.",
        "action": "Check your usage in Usage & Billing page. Upgrade for higher limits.",
    },
    "deploy.missing_credentials": {
        "title": "Store Credentials Missing",
        "message": "We don't have the required credentials to deploy to the store.",
        "action": "Go to Settings > Credentials and add your App Store / Google Play keys.",
    },
    "deploy.build_not_ready": {
        "title": "Build Not Ready",
        "message": "The build hasn't completed successfully yet. You can only deploy successful builds.",
        "action": "Wait for the build to finish or restart it.",
    },
    "deploy.artifact_expired": {
        "title": "Build Artifact Expired",
        "message": "This build is older than 24 hours. Store requirements may have changed.",
        "action": "Trigger a fresh build and deploy from the new artifact.",
    },
    "deploy.store_rejected": {
        "title": "Store Rejected",
        "message": "The app store rejected the upload. This could be due to signing, metadata, or policy issues.",
        "action": "Check deploy logs for the specific rejection reason.",
    },
    "deploy.checksum_mismatch": {
        "title": "Artifact Integrity Error",
        "message": "The build artifact checksum doesn't match. The file may have been corrupted during transfer.",
        "action": "Rebuild your project and try deploying again.",
    },
    "deploy.upload_failed": {
        "title": "Upload Failed",
        "message": "All upload methods failed (EAS Submit, Fastlane, altool).",
        "action": "Check your credentials and network. Review deploy logs for details.",
    },
    "auth.github_token_expired": {
        "title": "GitHub Connection Expired",
        "message": "Your GitHub authorization has expired.",
        "action": "Go to Settings and reconnect your GitHub account.",
    },
    "auth.rate_limited": {
        "title": "Too Many Requests",
        "message": "You're making requests too quickly. Please slow down.",
        "action": "Wait a moment and try again.",
    },
    "preview.container_failed": {
        "title": "Preview Failed to Start",
        "message": "The preview container couldn't start. This may be due to project configuration issues.",
        "action": "Check your project's dev server configuration.",
    },
}


def get_error_message(error_code: str) -> dict:
    default = {
        "title": "Unexpected Error",
        "message": "Something went wrong. Our team has been notified.",
        "action": "Try again. If the problem persists, contact support.",
    }
    result = ERROR_MESSAGES.get(error_code, default)
    result["code"] = error_code
    return result


def get_all_error_codes() -> list[str]:
    return list(ERROR_MESSAGES.keys())
