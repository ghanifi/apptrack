"""
Build Failure Auto-Diagnosis Router
====================================
Pattern-based error diagnosis engine that matches build log output against
known error patterns organized by framework (gradle, xcode, expo, flutter,
general). Provides diagnosis text, fix suggestions, severity scoring,
and auto-fixable flagging for failed builds.
"""

import re
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.dependencies import get_current_user
from app.database import get_db
from app.models import Build, Project

router = APIRouter(prefix="/api/build-diagnosis", tags=["build-diagnosis"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pattern-based error knowledge base
# Each entry: regex pattern, diagnosis, fix suggestion, optional auto_fix flag
# ---------------------------------------------------------------------------

BUILD_ERROR_PATTERNS: dict[str, list[dict]] = {
    "gradle": [
        {
            "id": "gradle_oom",
            "pattern": r"java\.lang\.OutOfMemoryError|GC overhead limit exceeded",
            "diagnosis": "Gradle build ran out of heap memory during compilation.",
            "fix": "Increase Gradle heap size in gradle.properties: org.gradle.jvmargs=-Xmx4096m. "
                   "Also consider enabling gradle.properties: org.gradle.daemon=true.",
            "auto_fix": True,
        },
        {
            "id": "gradle_dependency_resolution",
            "pattern": r"Could not resolve (?:all )?(?:files|dependencies) for configuration",
            "diagnosis": "Gradle failed to resolve one or more dependencies. A dependency may be unavailable or the repository is unreachable.",
            "fix": "Check your internet connection, verify the dependency coordinates in build.gradle, "
                   "and ensure the correct repositories (mavenCentral, google) are declared.",
            "auto_fix": False,
        },
        {
            "id": "gradle_sdk_not_found",
            "pattern": r"SDK location not found|failed to find target.*android-\d+",
            "diagnosis": "The Android SDK or a required SDK platform version was not found.",
            "fix": "Set the ANDROID_HOME environment variable, or install the required SDK platform "
                   "version via sdkmanager. Ensure local.properties points to the correct SDK path.",
            "auto_fix": False,
        },
        {
            "id": "gradle_min_sdk",
            "pattern": r"uses-sdk:minSdkVersion \d+ cannot be smaller than version \d+",
            "diagnosis": "A dependency requires a higher minSdkVersion than your project declares.",
            "fix": "Raise minSdkVersion in your app/build.gradle to match the dependency requirement, "
                   "or find an older version of the dependency that supports your current minSdkVersion.",
            "auto_fix": True,
        },
        {
            "id": "gradle_duplicate_class",
            "pattern": r"Duplicate class .+ found in modules",
            "diagnosis": "Two or more dependencies include the same class, causing a compile-time conflict.",
            "fix": "Use './gradlew app:dependencies' to find the conflicting libraries and exclude "
                   "the duplicate transitive dependency in build.gradle.",
            "auto_fix": False,
        },
        {
            "id": "gradle_jetifier",
            "pattern": r"AndroidX|android\.enableJetifier|support-v4",
            "diagnosis": "Project has a mix of AndroidX and legacy Android Support Library dependencies.",
            "fix": "Ensure android.useAndroidX=true and android.enableJetifier=true are set in "
                   "gradle.properties. Migrate all dependencies to AndroidX equivalents.",
            "auto_fix": True,
        },
    ],
    "xcode": [
        {
            "id": "xcode_signing",
            "pattern": r"Code Sign error|No signing certificate|Signing Identity|provisioning profile",
            "diagnosis": "Xcode code signing failed. The signing certificate or provisioning profile is missing or expired.",
            "fix": "Go to Settings > iOS Signing and use 'Auto-Generate Certificates' (no Mac needed). "
                   "Or manually upload a valid distribution certificate and provisioning profile. "
                   "Ensure the correct team and bundle identifier match your Apple Developer account.",
            "auto_fix": False,
        },
        {
            "id": "xcode_module_not_found",
            "pattern": r"No such module '(\w+)'|module '(\w+)' not found",
            "diagnosis": "Xcode cannot find a required Swift module. The CocoaPod or Swift Package may not be installed.",
            "fix": "Run 'pod install' or resolve Swift Package Manager dependencies. "
                   "Ensure the module is listed in your Podfile or Package.swift.",
            "auto_fix": True,
        },
        {
            "id": "xcode_deployment_target",
            "pattern": r"deployment target.*is less than|IPHONEOS_DEPLOYMENT_TARGET",
            "diagnosis": "The minimum iOS deployment target is lower than what a dependency requires.",
            "fix": "Raise the iOS deployment target in your Xcode project settings and Podfile "
                   "to match the dependency's minimum requirement (commonly iOS 13.0+).",
            "auto_fix": True,
        },
        {
            "id": "xcode_swift_version",
            "pattern": r"compiled with.*Swift \d+\.\d+.*cannot be imported by.*Swift \d+",
            "diagnosis": "Swift version mismatch between the project and a pre-compiled dependency.",
            "fix": "Update the dependency to a version compiled with your Swift toolchain, "
                   "or switch your Xcode version to match. Run 'pod update' if using CocoaPods.",
            "auto_fix": False,
        },
        {
            "id": "xcode_bitcode",
            "pattern": r"bitcode.*not.*enabled|ENABLE_BITCODE",
            "diagnosis": "Bitcode compilation setting mismatch between your app and a linked framework.",
            "fix": "Set ENABLE_BITCODE to NO in your Xcode build settings (Apple no longer requires Bitcode "
                   "since Xcode 14). Ensure all linked frameworks also disable Bitcode.",
            "auto_fix": True,
        },
    ],
    "expo": [
        {
            "id": "expo_config_plugin",
            "pattern": r"Config plugin.*not found|couldn't find.*plugin",
            "diagnosis": "An Expo config plugin referenced in app.json/app.config.js could not be resolved.",
            "fix": "Install the missing config plugin package with 'npx expo install <plugin>'. "
                   "Verify the plugin name and version in your app.json plugins array.",
            "auto_fix": True,
        },
        {
            "id": "expo_sdk_mismatch",
            "pattern": r"expo-modules-core.*version.*incompatible|SDK version mismatch",
            "diagnosis": "The Expo SDK version does not match one or more installed expo packages.",
            "fix": "Run 'npx expo install --fix' to align all Expo packages to the correct SDK version. "
                   "Ensure app.json specifies the correct sdkVersion.",
            "auto_fix": True,
        },
        {
            "id": "expo_native_module",
            "pattern": r"Native module.*cannot be null|TurboModuleRegistry|requireNativeComponent",
            "diagnosis": "A native module is not linked. This happens in Expo managed workflow when "
                   "using a package that requires custom native code.",
            "fix": "If using managed workflow, create a development build with 'eas build --profile development'. "
                   "If using bare workflow, run 'npx expo prebuild' and rebuild.",
            "auto_fix": False,
        },
        {
            "id": "expo_metro_bundler",
            "pattern": r"Metro bundler.*error|Unable to resolve module|BUNDLE_ERROR",
            "diagnosis": "Metro bundler failed to resolve a JavaScript module or bundle the application.",
            "fix": "Clear Metro cache with 'npx expo start --clear'. Check for typos in import paths. "
                   "Delete node_modules and run 'npm install' or 'yarn install' again.",
            "auto_fix": True,
        },
        {
            "id": "expo_eas_credentials",
            "pattern": r"EAS_BUILD.*credentials|eas-cli.*credential.*error",
            "diagnosis": "EAS Build could not find or validate the required build credentials.",
            "fix": "Run 'eas credentials' to configure or update your credentials. "
                   "For iOS, ensure your Apple Developer account is connected. "
                   "For Android, set up a keystore via 'eas credentials --platform android'.",
            "auto_fix": False,
        },
    ],
    "flutter": [
        {
            "id": "flutter_pub_get",
            "pattern": r"pub get failed|version solving failed|Because .+ depends on",
            "diagnosis": "Flutter package resolution (pub get) failed due to dependency version conflicts.",
            "fix": "Run 'flutter pub upgrade --major-versions' to resolve conflicts. "
                   "Check pubspec.yaml for overly restrictive version constraints. "
                   "Try 'flutter pub cache repair' if the cache is corrupted.",
            "auto_fix": True,
        },
        {
            "id": "flutter_gradle_plugin",
            "pattern": r"Plugin project :(\w+) not found|plugin.*not found.*build\.gradle",
            "diagnosis": "A Flutter plugin's native Android implementation could not be found by Gradle.",
            "fix": "Run 'flutter clean && flutter pub get'. Delete the .gradle folder in android/. "
                   "Ensure the plugin is correctly listed in pubspec.yaml.",
            "auto_fix": True,
        },
        {
            "id": "flutter_cocoapods",
            "pattern": r"CocoaPods could not find compatible versions|pod install.*error",
            "diagnosis": "CocoaPods dependency resolution failed for the iOS build of your Flutter project.",
            "fix": "Delete ios/Podfile.lock and ios/Pods, then run 'cd ios && pod install --repo-update'. "
                   "Ensure your macOS has the latest CocoaPods gem installed.",
            "auto_fix": True,
        },
        {
            "id": "flutter_dart_sdk",
            "pattern": r"requires SDK version|dart.*sdk.*constraint|current Dart SDK version",
            "diagnosis": "The Dart SDK version does not satisfy a package constraint.",
            "fix": "Upgrade Flutter and Dart to the latest stable channel with 'flutter upgrade'. "
                   "Update the Dart SDK constraint in pubspec.yaml environment section.",
            "auto_fix": False,
        },
        {
            "id": "flutter_null_safety",
            "pattern": r"null safety|non-nullable|--no-sound-null-safety",
            "diagnosis": "A dependency has not migrated to Dart null safety, causing compilation errors.",
            "fix": "Upgrade the offending dependency to a null-safe version. If unavailable, "
                   "temporarily run with '--no-sound-null-safety' flag, but plan to migrate.",
            "auto_fix": False,
        },
    ],
    "general": [
        {
            "id": "general_node_modules",
            "pattern": r"node_modules.*not found|Cannot find module|MODULE_NOT_FOUND",
            "diagnosis": "Node.js modules are missing. The dependencies were not installed before the build.",
            "fix": "Run 'npm install' or 'yarn install' before building. "
                   "If using a CI provider, ensure the install step precedes the build step.",
            "auto_fix": True,
        },
        {
            "id": "general_disk_space",
            "pattern": r"No space left on device|ENOSPC|disk quota exceeded",
            "diagnosis": "The build machine ran out of disk space during compilation.",
            "fix": "Clean build caches and temporary files. If using a CI provider, "
                   "select a machine with more storage or reduce artifact sizes. "
                   "Run 'docker system prune' if using Docker-based builds.",
            "auto_fix": False,
        },
        {
            "id": "general_timeout",
            "pattern": r"Build timed out|ETIMEDOUT|timeout.*exceeded|deadline exceeded",
            "diagnosis": "The build exceeded the maximum allowed duration and was terminated.",
            "fix": "Increase the build timeout in your CI configuration. "
                   "Optimize build times by enabling caching, parallelism, or incremental builds. "
                   "Consider splitting large monorepo builds into smaller targets.",
            "auto_fix": False,
        },
        {
            "id": "general_permission_denied",
            "pattern": r"Permission denied|EACCES|operation not permitted",
            "diagnosis": "The build process lacks file system permissions for a required operation.",
            "fix": "Check file permissions on build scripts (chmod +x). "
                   "Ensure the CI runner has adequate privileges. "
                   "Avoid running builds as root unless necessary.",
            "auto_fix": False,
        },
        {
            "id": "general_network",
            "pattern": r"network.*unreachable|ENETUNREACH|getaddrinfo.*ENOTFOUND|fetch failed",
            "diagnosis": "A network request failed during the build, likely a dependency download.",
            "fix": "Retry the build — transient network issues are common. "
                   "If persistent, check the registry status (npmjs.com, pub.dev, etc). "
                   "Consider using a package mirror or private registry.",
            "auto_fix": False,
        },
        {
            "id": "general_oom",
            "pattern": r"Killed.*signal 9|out of memory|OOMKilled|Cannot allocate memory",
            "diagnosis": "The build process was killed by the operating system due to memory exhaustion.",
            "fix": "Increase the memory allocation for the build machine or container. "
                   "Reduce parallelism (e.g., fewer Gradle workers, lower Node.js max-old-space-size). "
                   "Optimize memory-hungry compilation steps.",
            "auto_fix": False,
        },
        {
            "id": "general_env_var",
            "pattern": r"environment variable.*not set|missing.*env.*variable|undefined.*ENV",
            "diagnosis": "A required environment variable is not set in the build environment.",
            "fix": "Configure the missing environment variable in your CI/CD provider settings or .env file. "
                   "Check your build scripts for references to undefined variables.",
            "auto_fix": False,
        },
    ],
}


def _match_error_patterns(log_output: str, framework: str | None = None) -> list[dict]:
    """
    Match build log output against known error patterns.

    Checks framework-specific patterns first (if framework is known), then
    always checks the general patterns. Returns a list of matched diagnoses
    with deduplication by pattern id.

    Args:
        log_output: The raw build log text to analyze.
        framework: Optional framework hint (gradle, xcode, expo, flutter)
                   to prioritize framework-specific patterns.

    Returns:
        List of dicts, each containing: id, framework_group, diagnosis, fix, auto_fix.
    """
    matches: list[dict] = []
    seen_ids: set[str] = set()

    # Determine which framework groups to scan
    scan_groups: list[str] = []
    if framework:
        framework_lower = framework.lower()
        # Map common framework names to our pattern groups
        framework_map = {
            "expo": "expo",
            "react_native": "expo",
            "react-native": "expo",
            "flutter": "flutter",
            "swift": "xcode",
            "swiftui": "xcode",
            "kotlin": "gradle",
            "android": "gradle",
            "gradle": "gradle",
            "xcode": "xcode",
            "ios": "xcode",
        }
        mapped = framework_map.get(framework_lower)
        if mapped:
            scan_groups.append(mapped)

    # Always include general patterns at the end
    # Also scan all framework groups if no specific one is given
    if not scan_groups:
        scan_groups = ["gradle", "xcode", "expo", "flutter"]
    scan_groups.append("general")

    for group in scan_groups:
        patterns = BUILD_ERROR_PATTERNS.get(group, [])
        for entry in patterns:
            if entry["id"] in seen_ids:
                continue
            try:
                if re.search(entry["pattern"], log_output, re.IGNORECASE | re.MULTILINE):
                    matches.append({
                        "id": entry["id"],
                        "framework_group": group,
                        "diagnosis": entry["diagnosis"],
                        "fix": entry["fix"],
                        "auto_fix": entry.get("auto_fix", False),
                    })
                    seen_ids.add(entry["id"])
            except re.error:
                logger.warning("Invalid regex pattern in %s: %s", entry["id"], entry["pattern"])

    return matches


def _calculate_severity(diagnoses: list[dict]) -> str:
    """
    Calculate the overall severity of matched diagnoses.

    Severity levels:
    - critical: 4+ issues found, or contains disk/memory/signing errors
    - high: 2-3 issues found, or contains dependency resolution failures
    - medium: 1 issue found
    - low: 0 issues (should not normally happen for failed builds)

    Args:
        diagnoses: List of matched diagnosis dicts.

    Returns:
        Severity string: "critical", "high", "medium", or "low".
    """
    if not diagnoses:
        return "low"

    count = len(diagnoses)
    critical_ids = {
        "general_oom", "general_disk_space", "xcode_signing",
        "general_permission_denied",
    }
    high_ids = {
        "gradle_dependency_resolution", "flutter_pub_get",
        "expo_sdk_mismatch", "gradle_oom",
    }

    matched_ids = {d["id"] for d in diagnoses}

    if count >= 4 or matched_ids & critical_ids:
        return "critical"
    if count >= 2 or matched_ids & high_ids:
        return "high"
    return "medium"


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@router.post("/diagnose/{build_id}")
async def diagnose_build(
    build_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Diagnose a failed build by matching its log output against known error patterns.

    Retrieves the build from the database, verifies it belongs to the current user
    and is in a 'failed' state, then runs the log output through the pattern-matching
    engine. Returns a list of diagnoses with severity and auto-fixability information.

    - **build_id**: UUID of the build to diagnose.
    """
    result = await db.execute(select(Build).where(Build.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    # Verify ownership through project
    proj_result = await db.execute(select(Project).where(Project.id == build.project_id))
    project = proj_result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Build not found")

    if build.status != "failed":
        raise HTTPException(
            status_code=400,
            detail=f"Build is not in failed state (current: {build.status}). "
                   "Only failed builds can be diagnosed.",
        )

    if not build.log_output:
        return {
            "build_id": build_id,
            "project_id": build.project_id,
            "status": build.status,
            "diagnoses": [],
            "severity": "low",
            "auto_fixable": False,
            "message": "No build log output available for diagnosis. "
                       "The build may not have produced logs before failing.",
        }

    # Use project framework as a hint for pattern matching
    framework_hint = project.framework if project else None
    diagnoses = _match_error_patterns(build.log_output, framework=framework_hint)
    severity = _calculate_severity(diagnoses)
    auto_fixable = any(d["auto_fix"] for d in diagnoses)

    logger.info(
        "Build diagnosis: build_id=%s diagnoses=%d severity=%s auto_fixable=%s user=%s",
        build_id, len(diagnoses), severity, auto_fixable, current_user["id"],
    )

    return {
        "build_id": build_id,
        "project_id": build.project_id,
        "platform": build.platform,
        "provider": build.provider,
        "framework": framework_hint,
        "status": build.status,
        "diagnoses": diagnoses,
        "diagnosis_count": len(diagnoses),
        "severity": severity,
        "auto_fixable": auto_fixable,
    }


@router.get("/patterns")
async def list_patterns(
    current_user: dict = Depends(get_current_user),
):
    """
    List all known build error patterns organized by framework group.

    Returns the complete pattern knowledge base including pattern IDs, regex patterns,
    diagnosis text, fix suggestions, and auto-fix flags. Useful for debugging and
    understanding what errors the diagnosis engine can detect.
    """
    result = {}
    total_count = 0

    for framework_group, patterns in BUILD_ERROR_PATTERNS.items():
        group_patterns = []
        for entry in patterns:
            group_patterns.append({
                "id": entry["id"],
                "pattern": entry["pattern"],
                "diagnosis": entry["diagnosis"],
                "fix": entry["fix"],
                "auto_fix": entry.get("auto_fix", False),
            })
        result[framework_group] = group_patterns
        total_count += len(group_patterns)

    return {
        "framework_groups": list(BUILD_ERROR_PATTERNS.keys()),
        "total_patterns": total_count,
        "patterns": result,
    }
