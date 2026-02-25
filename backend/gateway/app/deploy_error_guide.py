DEPLOY_ERROR_GUIDE = {
    "CREDENTIAL_MISSING": {
        "title": "Store credentials not found",
        "message": "We couldn't find your store API credentials. Please add them before deploying.",
        "steps": [
            "Go to Settings > Store Credentials",
            "For Google Play: Upload your Service Account JSON key",
            "For App Store: Add your Key ID, Issuer ID, and Private Key (.p8)",
            "Save and try deploying again",
        ],
        "links": {
            "Google Play": "https://play.google.com/console/developers",
            "App Store": "https://appstoreconnect.apple.com/access/api",
        },
    },
    "CREDENTIAL_INVALID": {
        "title": "Invalid store credentials",
        "message": "Your store API credentials were rejected. Please verify them.",
        "steps": [
            "Go to Settings > Store Credentials",
            "Use the 'Validate' button to test your credentials",
            "For Google Play: Ensure the Service Account has 'Android Management' permissions",
            "For App Store: Ensure the API key has 'App Manager' or 'Admin' role",
            "Re-upload corrected credentials and try again",
        ],
        "links": {
            "Google Cloud IAM": "https://console.cloud.google.com/iam-admin/serviceaccounts",
            "App Store Connect Keys": "https://appstoreconnect.apple.com/access/api",
        },
    },
    "BUILD_NOT_READY": {
        "title": "Build is not ready for deployment",
        "message": "The build hasn't completed successfully yet. Wait for it to finish or retry.",
        "steps": [
            "Check the build status in your project dashboard",
            "If the build failed, review the error and retry",
            "If the build is still running, wait for it to complete",
            "Only successful builds can be deployed to stores",
        ],
        "links": {},
    },
    "ARTIFACT_EXPIRED": {
        "title": "Build artifact has expired",
        "message": "Build artifacts are kept for 90 days. This build is too old to deploy.",
        "steps": [
            "Start a new build from your project page",
            "Once the build succeeds, deploy it immediately",
            "Tip: Enable auto-deploy to avoid this in the future",
        ],
        "links": {},
    },
    "ARTIFACT_CHECKSUM_MISMATCH": {
        "title": "Build artifact integrity check failed",
        "message": "The build file was corrupted during transfer. This is rare but can happen.",
        "steps": [
            "Retry the build from your project page",
            "If the problem persists, contact support",
        ],
        "links": {},
    },
    "STORE_RATE_LIMIT": {
        "title": "Store API rate limit reached",
        "message": "The app store is temporarily limiting our requests. This resolves automatically.",
        "steps": [
            "Wait 15-30 minutes before trying again",
            "Avoid deploying multiple times in quick succession",
            "Check the store's status page for outages",
        ],
        "links": {
            "Google Play Status": "https://status.cloud.google.com/",
            "Apple System Status": "https://developer.apple.com/system-status/",
        },
    },
    "STORE_REJECT_POLICY": {
        "title": "App rejected by store policies",
        "message": "The store rejected your app during automated checks. Review their guidelines.",
        "steps": [
            "Check your email for rejection details from the store",
            "Review the store's content policy guidelines",
            "Fix the flagged issues in your app code",
            "Rebuild and deploy again",
        ],
        "links": {
            "Google Play Policies": "https://play.google.com/about/developer-content-policy/",
            "App Store Guidelines": "https://developer.apple.com/app-store/review/guidelines/",
        },
    },
    "SIGNING_ERROR": {
        "title": "Code signing failed",
        "message": "The app couldn't be signed for the store. Check your signing configuration.",
        "steps": [
            "For iOS: Ensure your provisioning profile and certificate are valid",
            "For Android: Check your keystore configuration",
            "Verify the bundle ID / package name matches your store listing",
            "Rebuild with correct signing settings",
        ],
        "links": {
            "iOS Code Signing": "https://developer.apple.com/support/code-signing/",
            "Android App Signing": "https://developer.android.com/studio/publish/app-signing",
        },
    },
    "NETWORK_TIMEOUT": {
        "title": "Upload timed out",
        "message": "The connection to the store was interrupted. This can happen with large files.",
        "steps": [
            "Simply retry the deployment — it usually works on the second try",
            "If the problem persists, check the store's status page",
            "Large apps (>100MB) may need multiple attempts",
        ],
        "links": {},
    },
    "QUOTA_EXCEEDED": {
        "title": "You've reached your plan limit",
        "message": "Your current plan doesn't allow more deployments this month.",
        "steps": [
            "Check your usage in Settings > Billing",
            "Upgrade to a higher plan for more deployments",
            "Your limit resets at the start of next month",
        ],
        "links": {},
    },
    "FASTLANE_ERROR": {
        "title": "Fastlane upload failed",
        "message": "Our deployment tool encountered an error. We're trying alternative methods.",
        "steps": [
            "This error is usually temporary — retry in a few minutes",
            "If it persists, we'll automatically try alternative upload methods",
            "Check that your store listing exists and is properly configured",
        ],
        "links": {
            "Fastlane Docs": "https://docs.fastlane.tools/",
        },
    },
}


def get_deploy_error_guide(error_code: str) -> dict:
    guide = DEPLOY_ERROR_GUIDE.get(error_code)
    if not guide:
        return {
            "title": "Deployment error",
            "message": "An unexpected error occurred during deployment.",
            "steps": [
                "Try deploying again",
                "If the problem persists, check your credentials and build status",
                "Contact support if you need help",
            ],
            "links": {},
            "error_code": error_code,
        }
    return {**guide, "error_code": error_code}
