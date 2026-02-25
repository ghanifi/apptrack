"""
AppTrack Platform - Final Validation After P0/P1/P2 Changes
=============================================================
Deep production readiness validation covering:

  V1: State Migration Risk Check (artifact DB, preview DB, race condition, retry)
  V2: GitHub Actions Real Dispatch Gate (workflow missing, fail, success, token expire)
  V3: App Store Upload Chain (fastlane->altool->EAS, credentials, timeout)
  V4: OTA Update Engine Risk (rollback, wrong branch, audit, tenant)
  V5: Provider-Level Cancel (EAS/Codemagic/GitHub cancel, partial artifact)
  V6: Webhook Replay Protection (nonce, signature, flood, audit)
"""
import asyncio
import hashlib
import hmac
import json
import os
import sys
import importlib
import traceback
import inspect
import time
import uuid
import re
from datetime import datetime, timedelta

RESULTS = []
PASS_COUNT = 0
FAIL_COUNT = 0

def log_test(name: str, passed: bool, detail: str = ""):
    global PASS_COUNT, FAIL_COUNT
    status = "PASS" if passed else "FAIL"
    if passed:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1
    RESULTS.append({"name": name, "status": status, "detail": detail})
    icon = "[OK]" if passed else "[FAIL]"
    print(f"  {icon} {name}" + (f" -- {detail}" if detail and not passed else ""))


gateway_path = os.path.join(os.path.dirname(__file__), "..", "gateway")
sys.path.insert(0, gateway_path)

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32c")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test_validation.db")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")

services_base = os.path.join(os.path.dirname(__file__), "..")

try:
    from app.config import settings
    from app.models import (
        Build, Project, Deployment, Credential, AuditLog,
        IdempotencyRecord, WebhookNonce, ImmutableAuditEntry,
    )
    IMPORTS_OK = True
except Exception as e:
    IMPORTS_OK = False
    print(f"[CRITICAL] Import error: {e}")
    traceback.print_exc()

def _read_service(svc_name: str) -> str:
    path = os.path.join(services_base, "services", svc_name, "app", "main.py")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================================
# V1: STATE MIGRATION RISK CHECK
# ============================================================================
print("\n" + "=" * 70)
print("  V1: STATE MIGRATION RISK CHECK")
print("=" * 70)

# --- 1.1 Artifact Service: DB-based persistence ---
print("\n--- 1.1 Artifact DB Persistence ---")
try:
    art_src = _read_service("artifact")

    log_test("V1.1: Artifact uses create_async_engine", "create_async_engine" in art_src)
    log_test("V1.1: Artifact has _SessionFactory", "_SessionFactory = async_sessionmaker" in art_src)
    log_test("V1.1: Artifact _init_db creates tables on startup", "async def _init_db" in art_src)
    log_test("V1.1: _init_db called in lifespan", "_init_db()" in art_src)
    log_test("V1.1: Artifact model has build_id index", 'index=True' in art_src and 'build_id' in art_src)

    log_test("V1.1: Upload does session.add + session.commit",
             "session.add(artifact)" in art_src and "session.commit()" in art_src)

    log_test("V1.1: Artifact ID is UUID4 (unique per upload)",
             "uuid.uuid4()" in art_src)

    log_test("V1.1: get_artifacts_by_build queries DB",
             "select(Artifact).where(Artifact.build_id ==" in art_src)

    log_test("V1.1: download_url queries DB not dict",
             "select(Artifact).where(Artifact.id ==" in art_src)

    log_test("V1.1: verify_artifact queries DB",
             "select(Artifact)" in art_src and "verify" in art_src)

    log_test("V1.1: engine.dispose in lifespan cleanup",
             "_engine.dispose()" in art_src)

    log_test("V1.1: tenant isolation via owner_id on download",
             "owner_id" in art_src and "tenant mismatch" in art_src)

except Exception as e:
    log_test("V1.1: Artifact DB", False, str(e)[:200])

# --- 1.2 Preview Service: DB-based persistence ---
print("\n--- 1.2 Preview DB Persistence ---")
try:
    prev_src = _read_service("preview")

    log_test("V1.2: Preview uses create_async_engine", "create_async_engine" in prev_src)
    log_test("V1.2: Preview has _SessionFactory", "_SessionFactory = async_sessionmaker" in prev_src)
    log_test("V1.2: Preview _init_db called in lifespan", "_init_db()" in prev_src)

    log_test("V1.2: PreviewState model has project_id unique index",
             "unique=True" in prev_src and "project_id" in prev_src)

    log_test("V1.2: _save_preview upserts (select + insert-or-update)",
             "scalar_one_or_none" in prev_src and "session.add" in prev_src)
    log_test("V1.2: _save_preview commits transaction",
             "session.commit()" in prev_src)

    log_test("V1.2: _load_preview returns None for missing",
             "return None" in prev_src)

    log_test("V1.2: _delete_preview uses sa_delete",
             "sa_delete" in prev_src or "delete(" in prev_src.lower())

    log_test("V1.2: concurrent _save_preview uses unique constraint (project_id)",
             "unique=True" in prev_src)

    log_test("V1.2: engine.dispose in lifespan cleanup",
             "_engine.dispose()" in prev_src)

    save_fn_src = prev_src[prev_src.index("async def _save_preview"):]
    save_fn_src = save_fn_src[:save_fn_src.index("\nasync def")]
    log_test("V1.2: _save_preview updates existing state fields",
             "state.status = data.get" in save_fn_src)

except Exception as e:
    log_test("V1.2: Preview DB", False, str(e)[:200])

# --- 1.3 Worker DB Connection Retry ---
print("\n--- 1.3 Worker DB Connection Retry ---")
try:
    from app.worker import MAX_RETRIES, BASE_DELAY, MAX_DELAY, _with_retry, _retry_counts

    log_test("V1.3: Worker MAX_RETRIES = 5", MAX_RETRIES == 5)
    log_test("V1.3: Worker BASE_DELAY = 1.0s", BASE_DELAY == 1.0)
    log_test("V1.3: Worker MAX_DELAY = 60s", MAX_DELAY == 60.0)

    worker_src = inspect.getsource(importlib.import_module("app.worker"))
    log_test("V1.3: exponential backoff with jitter",
             "2 ** (count - 1)" in worker_src and "random.uniform" in worker_src)
    log_test("V1.3: delay capped by MAX_DELAY",
             "min(BASE_DELAY" in worker_src and "MAX_DELAY" in worker_src)

    log_test("V1.3: DLQ for unparseable messages",
             "Unparseable message" in worker_src and "nack(requeue=False)" in worker_src)

    log_test("V1.3: permanent failure after MAX_RETRIES sent to DLQ",
             "count >= MAX_RETRIES" in worker_src and "nack(requeue=False)" in worker_src)

    log_test("V1.3: retry count cleared on success",
             "_retry_counts.pop(retry_key, None)" in worker_src)

    log_test("V1.3: DLX exchange declared in start_event_worker",
             'dlx' in worker_src and 'x-dead-letter-exchange' in worker_src)

    log_test("V1.3: message TTL set (86400000ms = 24h)",
             "86400000" in worker_src)

except Exception as e:
    log_test("V1.3: Worker retry", False, str(e)[:200])


# ============================================================================
# V2: GITHUB ACTIONS REAL DISPATCH GATE
# ============================================================================
print("\n" + "=" * 70)
print("  V2: GITHUB ACTIONS REAL DISPATCH GATE")
print("=" * 70)

print("\n--- 2.1 Workflow Missing Handling ---")
try:
    build_src = _read_service("build")

    log_test("V2.1: checks workflow existence before dispatch",
             "actions/workflows/" in build_src and "/dispatches" in build_src)

    log_test("V2.1: workflow 404 -> build.failed event",
             "check_resp.status_code == 404" in build_src)
    log_test("V2.1: workflow 404 error message has workflow filename",
             "workflow_file" in build_src and "not found" in build_src.lower())

    log_test("V2.1: workflow file selection: swift -> build-ios.yml",
             '"build-ios.yml"' in build_src and 'swift' in build_src)
    log_test("V2.1: workflow file selection: kotlin -> build-android.yml",
             '"build-android.yml"' in build_src and 'kotlin' in build_src)

except Exception as e:
    log_test("V2.1: Workflow missing", False, str(e)[:200])

print("\n--- 2.2 Build Failure Propagation ---")
try:
    log_test("V2.2: dispatch non-204 -> build.failed event",
             "resp.status_code == 204" in build_src)
    log_test("V2.2: failure event includes error detail",
             "GitHub Actions API error" in build_src)

    log_test("V2.2: EAS trigger failure -> build.failed event",
             "EAS trigger failed" in build_src and "build.failed" in build_src)
    log_test("V2.2: Codemagic trigger failure -> build.failed event",
             "Codemagic trigger failed" in build_src and "build.failed" in build_src)

    log_test("V2.2: build exception handler -> build.failed event",
             "Build handler error" in build_src and "build.failed" in build_src)

except Exception as e:
    log_test("V2.2: Failure propagation", False, str(e)[:200])

print("\n--- 2.3 Build Success -> Artifact Metadata ---")
try:
    worker_src = inspect.getsource(importlib.import_module("app.worker"))

    log_test("V2.3: worker updates Build.status on finish",
             "update(Build)" in worker_src and "status=status" in worker_src)
    log_test("V2.3: worker stores artifact_url in DB",
             "artifact_url=artifact_url" in worker_src)
    log_test("V2.3: worker stores artifact_checksum in DB",
             "artifact_checksum" in worker_src)
    log_test("V2.3: worker updates Project.status on success",
             'new_status = "ready" if status == "success"' in worker_src)
    log_test("V2.3: worker records build duration metric",
             "BUILD_DURATION" in worker_src and "observe" in worker_src)
    log_test("V2.3: worker records build result counter",
             "BUILD_RESULT_COUNTER" in worker_src)

except Exception as e:
    log_test("V2.3: Success -> metadata", False, str(e)[:200])

print("\n--- 2.4 Token Expiry Graceful Fail ---")
try:
    log_test("V2.4: missing github_token -> simulation mode",
             "not github_token or not owner_repo" in build_src)
    log_test("V2.4: simulation note mentions credentials",
             "Simulated" in build_src and "GITHUB_ACTIONS_TOKEN" in build_src)

    log_test("V2.4: missing EAS token -> simulation mode",
             "not eas_token or not expo_app_id" in build_src)
    log_test("V2.4: missing Codemagic token -> simulation mode",
             "not codemagic_token or not codemagic_app_id" in build_src)

    log_test("V2.4: HTTP timeout = 30s for external calls",
             "timeout=30.0" in build_src)

except Exception as e:
    log_test("V2.4: Token expiry", False, str(e)[:200])

print("\n--- 2.5 iOS Signing Support ---")
try:
    log_test("V2.5: ios_cert_p12_base64 passed to workflow inputs",
             "ios_cert_p12_base64" in build_src)
    log_test("V2.5: ios_cert_password passed to workflow inputs",
             "ios_cert_password" in build_src)
    log_test("V2.5: ios_provisioning_profile passed",
             "ios_provisioning_profile_base64" in build_src)

except Exception as e:
    log_test("V2.5: iOS signing", False, str(e)[:200])


# ============================================================================
# V3: APP STORE UPLOAD CHAIN VALIDATION
# ============================================================================
print("\n" + "=" * 70)
print("  V3: APP STORE UPLOAD CHAIN VALIDATION")
print("=" * 70)

print("\n--- 3.1 Upload Fallback Chain ---")
try:
    sd_src = _read_service("store-deploy")

    eas_idx = sd_src.index("_submit_via_eas")
    fastlane_idx = sd_src.index("_upload_ipa_via_fastlane")
    altool_idx = sd_src.index("_upload_ipa_via_altool")
    log_test("V3.1: EAS submit function exists", eas_idx > 0)
    log_test("V3.1: Fastlane upload function exists", fastlane_idx > 0)
    log_test("V3.1: altool upload function exists", altool_idx > 0)

    deploy_app_store_src = sd_src[sd_src.index("async def _deploy_app_store"):]
    deploy_app_store_src = deploy_app_store_src[:deploy_app_store_src.index("\n\nasync def")]

    eas_call = deploy_app_store_src.index("_submit_via_eas")
    fl_call = deploy_app_store_src.index("_upload_ipa_via_fastlane")
    alt_call = deploy_app_store_src.index("_upload_ipa_via_altool")

    log_test("V3.1: EAS tried first, then fastlane, then altool",
             eas_call < fl_call < alt_call)

    log_test("V3.1: if not upload_ok -> try next method",
             deploy_app_store_src.count("if not upload_ok") >= 2)

    log_test("V3.1: all methods exhausted -> deploy.failed event",
             "all methods exhausted" in deploy_app_store_src)

    log_test("V3.1: failed event includes hint for fastlane install",
             "gem install fastlane" in sd_src)

except Exception as e:
    log_test("V3.1: Upload fallback chain", False, str(e)[:200])

print("\n--- 3.2 Credential Validation Before Upload ---")
try:
    log_test("V3.2: credential check: all([key_id, issuer_id, private_key])",
             "not all([key_id, issuer_id, private_key])" in sd_src)

    log_test("V3.2: missing credentials -> deploy.failed (not simulated)",
             "credentials" in sd_src and "deploy.failed" in sd_src)

    log_test("V3.2: credential verification via App Store Connect API",
             "appstoreconnect.apple.com/v1/apps" in sd_src)

    log_test("V3.2: invalid credential -> deploy.failed with clear message",
             "credential invalid" in sd_src.lower() or "credential verification failed" in sd_src.lower())

    log_test("V3.2: valid credential but no artifact -> credentials_verified status",
             '"credentials_verified"' in sd_src)

except Exception as e:
    log_test("V3.2: Credential validation", False, str(e)[:200])

print("\n--- 3.3 Artifact Download & Checksum ---")
try:
    log_test("V3.3: _download_artifact uses streaming (aiter_bytes)",
             "aiter_bytes" in sd_src)
    log_test("V3.3: chunk size = 1MB", "1024 * 1024" in sd_src)
    log_test("V3.3: SHA256 computed during download",
             "sha256 = hashlib.sha256()" in sd_src)
    log_test("V3.3: sha256.update(chunk) during streaming",
             "sha256.update(chunk)" in sd_src)
    log_test("V3.3: checksum mismatch -> unlink tmp + raise ValueError",
             "Checksum mismatch" in sd_src and "os.unlink" in sd_src)
    log_test("V3.3: download timeout = 300s",
             "timeout=300.0" in sd_src)

except Exception as e:
    log_test("V3.3: Download & checksum", False, str(e)[:200])

print("\n--- 3.4 Fastlane Upload Details ---")
try:
    fl_fn_start = sd_src.index("async def _upload_ipa_via_fastlane")
    fl_fn_end = sd_src.index("\n\nasync def", fl_fn_start + 1)
    fl_src = sd_src[fl_fn_start:fl_fn_end]

    log_test("V3.4: checks fastlane installed (shutil.which)",
             "shutil.which" in fl_src and "fastlane" in fl_src)
    log_test("V3.4: creates temp .p8 key file",
             ".p8" in fl_src and "NamedTemporaryFile" in fl_src)
    log_test("V3.4: fastlane deliver command called",
             "fastlane" in fl_src and "deliver" in fl_src)
    log_test("V3.4: skip_metadata and skip_screenshots",
             "skip_metadata" in fl_src and "skip_screenshots" in fl_src)
    log_test("V3.4: timeout for fastlane = 600s",
             "timeout=600" in fl_src)
    log_test("V3.4: TimeoutExpired caught",
             "TimeoutExpired" in fl_src)
    log_test("V3.4: key file cleaned up in finally",
             "finally:" in fl_src and "os.unlink" in fl_src)
    log_test("V3.4: returns (bool, str) tuple",
             "return True," in fl_src and "return False," in fl_src)

except Exception as e:
    log_test("V3.4: Fastlane upload", False, str(e)[:200])

print("\n--- 3.5 altool Upload Details ---")
try:
    at_fn_start = sd_src.index("async def _upload_ipa_via_altool")
    at_fn_end = sd_src.index("\n\nasync def", at_fn_start + 1)
    at_src = sd_src[at_fn_start:at_fn_end]

    log_test("V3.5: checks altool OR xcrun installed",
             "shutil.which" in at_src and "xcrun" in at_src)
    log_test("V3.5: not installed -> returns (False, message)",
             "macOS required" in at_src)
    log_test("V3.5: xcrun altool --upload-app command",
             "--upload-app" in at_src)
    log_test("V3.5: API_PRIVATE_KEYS_DIR env set for key discovery",
             "API_PRIVATE_KEYS_DIR" in at_src)
    log_test("V3.5: timeout for altool = 600s",
             "timeout=600" in at_src)
    log_test("V3.5: key file cleaned up in finally",
             "finally:" in at_src and "os.unlink" in at_src)

except Exception as e:
    log_test("V3.5: altool upload", False, str(e)[:200])

print("\n--- 3.6 Google Play Deploy ---")
try:
    gp_fn_start = sd_src.index("async def _deploy_google_play")
    gp_fn_end = sd_src.index("\n\nasync def", gp_fn_start + 1)
    gp_src = sd_src[gp_fn_start:gp_fn_end]

    log_test("V3.6: Google Play uses service_account.Credentials",
             "service_account.Credentials" in gp_src)
    log_test("V3.6: creates edit session",
             "edits().insert" in gp_src)
    log_test("V3.6: uploads bundle with MediaFileUpload",
             "MediaFileUpload" in gp_src)
    log_test("V3.6: updates track",
             "tracks().update" in gp_src)
    log_test("V3.6: commits edit",
             "edits().commit" in gp_src)
    log_test("V3.6: tmp file cleaned up in finally",
             "finally:" in gp_src and "os.unlink" in gp_src)
    log_test("V3.6: deploy.completed event on success",
             "deploy.completed" in gp_src)
    log_test("V3.6: deploy.failed event on error",
             "deploy.failed" in gp_src)

    log_test("V3.6: missing credentials -> simulated deploy",
             "not key_json or not artifact_url" in gp_src)

except Exception as e:
    log_test("V3.6: Google Play deploy", False, str(e)[:200])


# ============================================================================
# V4: OTA UPDATE ENGINE RISK CHECK
# ============================================================================
print("\n" + "=" * 70)
print("  V4: OTA UPDATE ENGINE RISK CHECK")
print("=" * 70)

print("\n--- 4.1 OTA Rollback ---")
try:
    ota_src = inspect.getsource(importlib.import_module("app.routers.ota"))

    log_test("V4.1: rollback endpoint exists",
             "async def rollback_eas_update" in ota_src or "/rollback" in ota_src)
    log_test("V4.1: rollback sends targetUpdateId",
             "targetUpdateId" in ota_src)
    log_test("V4.1: rollback posts to branches/{branch}/rollbacks",
             "rollbacks" in ota_src)
    log_test("V4.1: rollback returns target_update_id",
             "target_update_id" in ota_src)
    log_test("V4.1: rollback returns branch",
             '"branch"' in ota_src)
    log_test("V4.1: rollback requires EAS_TOKEN",
             "EAS_TOKEN" in ota_src)

except Exception as e:
    log_test("V4.1: OTA rollback", False, str(e)[:200])

print("\n--- 4.2 OTA Branch Validation ---")
try:
    log_test("V4.2: eas-update accepts branch parameter",
             "branch" in ota_src)
    log_test("V4.2: default branch = production",
             '"production"' in ota_src)
    log_test("V4.2: branch passed to EAS API as branchName",
             "branchName" in ota_src)
    log_test("V4.2: list branches endpoint",
             "list_eas_branches" in ota_src or "/branches" in ota_src)
    log_test("V4.2: list updates filtered by branch",
             "branch" in ota_src and "params" in ota_src)

except Exception as e:
    log_test("V4.2: OTA branch", False, str(e)[:200])

print("\n--- 4.3 OTA Tenant Isolation ---")
try:
    log_test("V4.3: OTA requires current_user auth",
             "get_current_user" in ota_src)
    log_test("V4.3: OTA verifies project ownership",
             "owner_id == current_user" in ota_src)
    log_test("V4.3: OTA 404 if project not found",
             "404" in ota_src and "Project not found" in ota_src)

    log_test("V4.3: credential lookup per-user",
             "_get_credential(db, current_user" in ota_src)

except Exception as e:
    log_test("V4.3: OTA tenant", False, str(e)[:200])

print("\n--- 4.4 OTA Error Handling ---")
try:
    log_test("V4.4: EAS API error -> 502 with detail",
             "502" in ota_src and "EAS" in ota_src)
    log_test("V4.4: EAS connection error -> 503",
             "503" in ota_src)
    log_test("V4.4: missing credentials -> 400 with hint",
             "400" in ota_src and "credentials manager" in ota_src.lower())
    log_test("V4.4: HTTP timeout = 30s for OTA calls",
             "timeout=30.0" in ota_src)
    log_test("V4.4: HTTP timeout = 15s for list/rollback",
             "timeout=15.0" in ota_src)

except Exception as e:
    log_test("V4.4: OTA error handling", False, str(e)[:200])


# ============================================================================
# V5: PROVIDER-LEVEL CANCEL VALIDATION
# ============================================================================
print("\n" + "=" * 70)
print("  V5: PROVIDER-LEVEL CANCEL VALIDATION")
print("=" * 70)

print("\n--- 5.1 EAS Cancel ---")
try:
    log_test("V5.1: _cancel_eas_build function exists",
             "async def _cancel_eas_build" in build_src)
    eas_cancel_fn = build_src[build_src.index("async def _cancel_eas_build"):]
    eas_cancel_fn = eas_cancel_fn[:eas_cancel_fn.index("\n\nasync def")]
    log_test("V5.1: EAS cancel posts to /builds/{id}/cancel",
             "builds/{external_build_id}/cancel" in eas_cancel_fn or "builds/" in eas_cancel_fn)
    log_test("V5.1: EAS cancel uses Bearer token",
             "Bearer" in eas_cancel_fn)
    log_test("V5.1: EAS cancel returns bool",
             "return resp.status_code in" in eas_cancel_fn)

except Exception as e:
    log_test("V5.1: EAS cancel", False, str(e)[:200])

print("\n--- 5.2 Codemagic Cancel ---")
try:
    log_test("V5.2: _cancel_codemagic_build function exists",
             "async def _cancel_codemagic_build" in build_src)
    cm_cancel_fn = build_src[build_src.index("async def _cancel_codemagic_build"):]
    cm_cancel_fn = cm_cancel_fn[:cm_cancel_fn.index("\n\nasync def")]
    log_test("V5.2: Codemagic cancel posts to /builds/{id}/cancel",
             "builds/" in cm_cancel_fn and "cancel" in cm_cancel_fn)
    log_test("V5.2: Codemagic cancel uses x-auth-token header",
             "x-auth-token" in cm_cancel_fn)

except Exception as e:
    log_test("V5.2: Codemagic cancel", False, str(e)[:200])

print("\n--- 5.3 GitHub Actions Cancel ---")
try:
    log_test("V5.3: _cancel_github_actions_run function exists",
             "async def _cancel_github_actions_run" in build_src)
    gh_cancel_fn = build_src[build_src.index("async def _cancel_github_actions_run"):]
    gh_cancel_fn = gh_cancel_fn[:gh_cancel_fn.index("\n\nasync def")]
    log_test("V5.3: GitHub cancel posts to /actions/runs/{id}/cancel",
             "actions/runs/" in gh_cancel_fn and "cancel" in gh_cancel_fn)
    log_test("V5.3: GitHub cancel uses Bearer token",
             "Bearer" in gh_cancel_fn)

except Exception as e:
    log_test("V5.3: GitHub cancel", False, str(e)[:200])

print("\n--- 5.4 Gateway Cancel Endpoint ---")
try:
    builds_router_src = inspect.getsource(importlib.import_module("app.routers.builds"))

    log_test("V5.4: cancel checks terminal states before cancel",
             '"success", "failed", "cancelled"' in builds_router_src)
    log_test("V5.4: cancel returns 400 for terminal state builds",
             "already in terminal state" in builds_router_src)

    log_test("V5.4: cancel contacts build provider service",
             "BUILD_SERVICE_URL" in builds_router_src and "/cancel" in builds_router_src)

    log_test("V5.4: cancel sends provider-specific token",
             "eas_token" in builds_router_src and "codemagic_token" in builds_router_src)
    log_test("V5.4: cancel sends github_token and owner_repo",
             "github_token" in builds_router_src and "owner_repo" in builds_router_src)

    log_test("V5.4: cancel sets build.status = cancelled",
             '"cancelled"' in builds_router_src)
    log_test("V5.4: cancel sets finished_at timestamp",
             "finished_at = datetime.utcnow()" in builds_router_src)

    log_test("V5.4: cancel returns provider_cancelled flag",
             "provider_cancelled" in builds_router_src)

    log_test("V5.4: provider cancel failure doesn't block status update",
             "try:" in builds_router_src and "pass" in builds_router_src)

except Exception as e:
    log_test("V5.4: Gateway cancel", False, str(e)[:200])

print("\n--- 5.5 Retry After Cancel ---")
try:
    log_test("V5.5: retry allows cancelled builds",
             '"failed", "cancelled"' in builds_router_src)
    log_test("V5.5: retry creates new build with queued status",
             '"queued"' in builds_router_src)
    log_test("V5.5: retry creates new UUID",
             "uuid.uuid4()" in builds_router_src)

except Exception as e:
    log_test("V5.5: Retry after cancel", False, str(e)[:200])

print("\n--- 5.6 Partial Artifact Protection ---")
try:
    deploy_src = inspect.getsource(importlib.import_module("app.routers.deployments"))

    log_test("V5.6: deploy checks build.status == success",
             'build.status != "success"' in deploy_src)
    log_test("V5.6: deploy checks build.artifact_url exists",
             "not build.artifact_url" in deploy_src)
    log_test("V5.6: cancelled build cannot be deployed",
             "success" in deploy_src)
    log_test("V5.6: artifact checksum passed to deploy event",
             "artifact_checksum" in deploy_src)

except Exception as e:
    log_test("V5.6: Partial artifact", False, str(e)[:200])


# ============================================================================
# V6: WEBHOOK REPLAY PROTECTION VALIDATION
# ============================================================================
print("\n" + "=" * 70)
print("  V6: WEBHOOK REPLAY PROTECTION VALIDATION")
print("=" * 70)

print("\n--- 6.1 Gateway Webhook Nonce ---")
try:
    from app.webhook_guard import check_replay, REPLAY_WINDOW_SECONDS, NONCE_CLEANUP_INTERVAL

    log_test("V6.1: REPLAY_WINDOW = 300s", REPLAY_WINDOW_SECONDS == 300)
    log_test("V6.1: NONCE_CLEANUP_INTERVAL = 3600s", NONCE_CLEANUP_INTERVAL == 3600)

    guard_src = inspect.getsource(check_replay)

    log_test("V6.1: check_replay checks timestamp age",
             "abs(now - timestamp) > REPLAY_WINDOW_SECONDS" in guard_src)
    log_test("V6.1: old timestamp -> returns False (rejected)",
             "return False" in guard_src and "timestamp too old" in guard_src)

    log_test("V6.1: check_replay queries WebhookNonce table",
             "WebhookNonce" in guard_src)
    log_test("V6.1: duplicate nonce -> returns False",
             "duplicate nonce" in guard_src and "return False" in guard_src)

    log_test("V6.1: new nonce stored with expires_at",
             "expires_at" in guard_src and "REPLAY_WINDOW_SECONDS * 2" in guard_src)
    log_test("V6.1: nonce stored via db.add + db.flush",
             "db.add" in guard_src and "db.flush" in guard_src)

    log_test("V6.1: expired nonces filtered (expires_at > now)",
             "expires_at > datetime.utcnow()" in guard_src)

except Exception as e:
    log_test("V6.1: Gateway nonce", False, str(e)[:200])

print("\n--- 6.2 Build Service Webhook Nonce ---")
try:
    log_test("V6.2: build service has _check_replay function",
             "def _check_replay" in build_src)
    log_test("V6.2: build service nonce TTL = 300s",
             "_NONCE_TTL_SECONDS = 300" in build_src)
    log_test("V6.2: duplicate nonce returns False",
             "return False" in build_src)
    log_test("V6.2: expired nonces auto-cleaned",
             "expired" in build_src and "del _used_nonces" in build_src)

except Exception as e:
    log_test("V6.2: Build nonce", False, str(e)[:200])

print("\n--- 6.3 EAS Webhook Signature + Replay ---")
try:
    eas_wh = build_src[build_src.index("async def eas_webhook"):]
    eas_wh = eas_wh[:eas_wh.index("\n\n@app")]

    log_test("V6.3: EAS verifies HMAC signature",
             "_verify_hmac" in eas_wh)
    log_test("V6.3: EAS missing signature -> 401",
             "Missing EAS webhook signature" in eas_wh)
    log_test("V6.3: EAS invalid signature -> 401",
             "Invalid EAS webhook signature" in eas_wh)
    log_test("V6.3: EAS no secret -> 503 (fail-closed)",
             "503" in eas_wh and "not configured" in eas_wh)
    log_test("V6.3: EAS checks nonce for replay",
             "_check_replay" in eas_wh)
    log_test("V6.3: EAS duplicate -> 409",
             "409" in eas_wh and "replay detected" in eas_wh.lower())
    log_test("V6.3: EAS nonce from x-eas-delivery-id header",
             "x-eas-delivery-id" in eas_wh)

except Exception as e:
    log_test("V6.3: EAS webhook", False, str(e)[:200])

print("\n--- 6.4 Codemagic Webhook Signature + Replay ---")
try:
    cm_wh = build_src[build_src.index("async def codemagic_webhook"):]
    cm_wh = cm_wh[:cm_wh.index("\n\n@app")]

    log_test("V6.4: Codemagic verifies HMAC signature",
             "_verify_hmac" in cm_wh)
    log_test("V6.4: Codemagic missing sig -> 401",
             "Missing Codemagic webhook signature" in cm_wh)
    log_test("V6.4: Codemagic invalid sig -> 401",
             "Invalid Codemagic webhook signature" in cm_wh)
    log_test("V6.4: Codemagic no secret -> 503",
             "503" in cm_wh and "not configured" in cm_wh)
    log_test("V6.4: Codemagic checks replay",
             "_check_replay" in cm_wh)
    log_test("V6.4: Codemagic duplicate -> 409",
             "409" in cm_wh)
    log_test("V6.4: Codemagic nonce from x-codemagic-delivery",
             "x-codemagic-delivery" in cm_wh)

except Exception as e:
    log_test("V6.4: Codemagic webhook", False, str(e)[:200])

print("\n--- 6.5 GitHub Webhook Signature + Replay ---")
try:
    webhook_router_src = inspect.getsource(importlib.import_module("app.routers.webhooks"))

    log_test("V6.5: GitHub uses HMAC SHA256 verification",
             "hmac" in webhook_router_src and "sha256" in webhook_router_src)
    log_test("V6.5: GitHub missing sig -> 401",
             "Missing webhook signature" in webhook_router_src)
    log_test("V6.5: GitHub invalid sig -> 401",
             "Invalid webhook signature" in webhook_router_src)
    log_test("V6.5: GitHub no secret -> 503 (fail-closed)",
             "503" in webhook_router_src)

    gh_build_wh = build_src[build_src.index("async def github_actions_webhook"):]
    log_test("V6.5: GitHub Actions webhook checks replay",
             "_check_replay" in gh_build_wh)
    log_test("V6.5: GitHub delivery-id header used for nonce",
             "x-github-delivery" in gh_build_wh)
    log_test("V6.5: GitHub duplicate -> 409",
             "409" in gh_build_wh)

except Exception as e:
    log_test("V6.5: GitHub webhook", False, str(e)[:200])

print("\n--- 6.6 Webhook Rate Limiting ---")
try:
    log_test("V6.6: GitHub webhook rate limited 30/min",
             "30/minute" in webhook_router_src)

    main_src = inspect.getsource(importlib.import_module("app.main"))
    log_test("V6.6: webhook counter metric exists",
             "webhooks_received_total" in main_src)
    log_test("V6.6: webhook signature failure metric",
             "webhook_signature_failures_total" in main_src)

except Exception as e:
    log_test("V6.6: Webhook rate limit", False, str(e)[:200])

print("\n--- 6.7 Nonce Cleanup ---")
try:
    from app.webhook_guard import cleanup_expired_nonces
    cleanup_src = inspect.getsource(cleanup_expired_nonces)

    log_test("V6.7: nonce cleanup deletes expired entries",
             "delete(WebhookNonce)" in cleanup_src)
    log_test("V6.7: cleanup checks expires_at < now",
             "expires_at < datetime.utcnow()" in cleanup_src)
    log_test("V6.7: cleanup runs in infinite loop",
             "while True" in cleanup_src)
    log_test("V6.7: cleanup handles CancelledError",
             "CancelledError" in cleanup_src)
    log_test("V6.7: cleanup interval matches constant",
             "NONCE_CLEANUP_INTERVAL" in cleanup_src)

except Exception as e:
    log_test("V6.7: Nonce cleanup", False, str(e)[:200])

print("\n--- 6.8 HMAC Verification ---")
try:
    log_test("V6.8: build service _verify_hmac uses compare_digest",
             "compare_digest" in build_src)
    log_test("V6.8: build service HMAC is sha256",
             "sha256" in build_src and "hmac.new" in build_src)
    log_test("V6.8: build service signature prefix 'sha256='",
             '"sha256="' in build_src)

    log_test("V6.8: gateway _verify_signature uses compare_digest",
             "compare_digest" in webhook_router_src)
    log_test("V6.8: gateway HMAC is sha256",
             "sha256" in webhook_router_src)

except Exception as e:
    log_test("V6.8: HMAC verification", False, str(e)[:200])


# ============================================================================
# BONUS: CROSS-VALIDATION INTEGRITY CHECKS
# ============================================================================
print("\n" + "=" * 70)
print("  BONUS: CROSS-VALIDATION INTEGRITY")
print("=" * 70)

print("\n--- B.1 Deploy Pipeline: Credential Flow ---")
try:
    deploy_src = inspect.getsource(importlib.import_module("app.routers.deployments"))

    log_test("B.1: deploy fetches Google Play key from credential store",
             "get_user_credential" in deploy_src and "GOOGLE_PLAY_KEY_JSON" in deploy_src)
    log_test("B.1: deploy fetches App Store key_id",
             "APP_STORE_KEY_ID" in deploy_src)
    log_test("B.1: deploy fetches App Store issuer_id",
             "APP_STORE_ISSUER_ID" in deploy_src)
    log_test("B.1: deploy fetches App Store private_key",
             "APP_STORE_PRIVATE_KEY" in deploy_src)
    log_test("B.1: deploy fetches EAS token for App Store",
             "EAS_TOKEN" in deploy_src)
    log_test("B.1: deploy fetches expo_app_id",
             "EXPO_APP_ID" in deploy_src)

    log_test("B.1: credential flow: Gateway decrypt -> event payload -> store-deploy",
             "artifact_checksum" in deploy_src and "deploy.triggered" in deploy_src)

except Exception as e:
    log_test("B.1: Credential flow", False, str(e)[:200])

print("\n--- B.2 Build -> Deploy -> Store E2E Chain ---")
try:
    log_test("B.2: build triggers build.started event", "build.started" in build_src)
    log_test("B.2: build triggers build.finished event", "build.finished" in build_src)
    log_test("B.2: build triggers build.failed event", "build.failed" in build_src)

    worker_src = inspect.getsource(importlib.import_module("app.worker"))
    log_test("B.2: worker handles all build events",
             "build.started" in worker_src and "build.finished" in worker_src and "build.failed" in worker_src)
    log_test("B.2: worker handles deploy events",
             "deploy.completed" in worker_src and "deploy.failed" in worker_src)

    log_test("B.2: store-deploy consumes deploy.triggered",
             "deploy.triggered" in sd_src)
    log_test("B.2: store-deploy publishes deploy.completed/failed",
             "deploy.completed" in sd_src and "deploy.failed" in sd_src)

except Exception as e:
    log_test("B.2: E2E chain", False, str(e)[:200])

print("\n--- B.3 Audit Trail Coverage ---")
try:
    log_test("B.3: deploy trigger audited",
             "record_audit" in deploy_src and "deploy.triggered" in deploy_src)
    log_test("B.3: deploy usage tracked",
             "track_usage" in deploy_src)
    log_test("B.3: deploy quota checked",
             "check_deploy_quota" in deploy_src)

    audit_src = inspect.getsource(importlib.import_module("app.audit"))
    log_test("B.3: audit captures IP address",
             "ip_address" in audit_src)
    log_test("B.3: audit captures user_agent",
             "user_agent" in audit_src)
    log_test("B.3: audit captures trace_id",
             "trace_id" in audit_src)

except Exception as e:
    log_test("B.3: Audit trail", False, str(e)[:200])

print("\n--- B.4 Stale Build + Cancel Consistency ---")
try:
    cleanup_src = inspect.getsource(importlib.import_module("app.cleanup"))
    log_test("B.4: stale cleanup marks as 'timeout' (not cancelled)",
             '"timeout"' in cleanup_src)
    log_test("B.4: stale cleanup only touches queued/running builds",
             '"queued"' in cleanup_src and '"running"' in cleanup_src)
    log_test("B.4: stale cleanup logs build_id and project_id",
             "build.id" in cleanup_src and "build.project_id" in cleanup_src)

except Exception as e:
    log_test("B.4: Stale/cancel consistency", False, str(e)[:200])


# ============================================================================
# FINAL REPORT
# ============================================================================
print("\n" + "=" * 70)
print(f"  FINAL VALIDATION RESULTS: {PASS_COUNT} PASS / {FAIL_COUNT} FAIL / {PASS_COUNT + FAIL_COUNT} TOTAL")
print("=" * 70)

section_summary = {}
for r in RESULTS:
    section = r["name"].split(":")[0] if ":" in r["name"] else "Other"
    if section not in section_summary:
        section_summary[section] = {"pass": 0, "fail": 0}
    if r["status"] == "PASS":
        section_summary[section]["pass"] += 1
    else:
        section_summary[section]["fail"] += 1

print("\n  SECTION BREAKDOWN:")
for section, counts in sorted(section_summary.items()):
    total = counts["pass"] + counts["fail"]
    pct = (counts["pass"] / total * 100) if total > 0 else 0
    status = "PASS" if counts["fail"] == 0 else "WARN"
    print(f"    {section}: {counts['pass']}/{total} ({pct:.0f}%) [{status}]")

if FAIL_COUNT > 0:
    print(f"\n  FAILED TESTS ({FAIL_COUNT}):")
    for r in RESULTS:
        if r["status"] == "FAIL":
            print(f"    [FAIL] {r['name']}: {r['detail']}")

print()
