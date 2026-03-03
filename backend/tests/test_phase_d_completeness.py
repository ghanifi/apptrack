"""
AppTrack Phase D Completeness Tests
====================================
Tests for: ConfigurationError, deploy policies, RBAC, webhooks,
           immutable audit, support tickets, organizations, SSO models.
"""
import os
import sys
import asyncio
import importlib
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# --- Test environment setup ---
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars")
os.environ.setdefault("FERNET_SALT", "test-fernet-salt-for-testing")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test_phase_d.db")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("SERVICE_TOKEN_SECRET", "test-service-secret")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test-stripe-secret")
os.environ.setdefault("STRIPE_API_KEY", "test-stripe-key")
os.environ.setdefault("EAS_WEBHOOK_SECRET", "test-eas-secret")
os.environ.setdefault("CODEMAGIC_WEBHOOK_SECRET", "test-cm-secret")
os.environ.setdefault("ENVIRONMENT", "testing")

RESULTS = []
PASS_COUNT = 0
FAIL_COUNT = 0


def log_test(name: str, passed: bool, detail: str = ""):
    global PASS_COUNT, FAIL_COUNT
    status = "[OK]" if passed else "[FAIL]"
    if passed:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1
    msg = f"  {status} {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    RESULTS.append({"name": name, "passed": passed, "detail": detail})


# ====================================================================
# TEST GROUP 1: BUILD SERVICE — ConfigurationError (Mock Kaldirma)
# ====================================================================
print("\n=== BUILD SERVICE: ConfigurationError Tests ===")

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "build"))
    # ConfigurationError sinifini import et
    from app.main import ConfigurationError
    log_test("ConfigurationError class exists", True)
except ImportError as e:
    log_test("ConfigurationError class exists", False, str(e))

try:
    from app.main import ConfigurationError
    err = ConfigurationError("test message")
    log_test("ConfigurationError is an Exception", isinstance(err, Exception))
    log_test("ConfigurationError message correct", str(err) == "test message")
except Exception as e:
    log_test("ConfigurationError instantiation", False, str(e))

# Simulate: EAS trigger without token should raise
try:
    from app.main import _trigger_eas
    log_test("_trigger_eas function exists", callable(_trigger_eas))
except ImportError:
    log_test("_trigger_eas function exists", False, "import failed — build service may need full env")


# ====================================================================
# TEST GROUP 2: STORE DEPLOY — ConfigurationError
# ====================================================================
print("\n=== STORE DEPLOY: ConfigurationError Tests ===")

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "store-deploy"))
    from app.main import ConfigurationError as DeployConfigError
    log_test("Store Deploy ConfigurationError exists", True)
except ImportError as e:
    log_test("Store Deploy ConfigurationError exists", False, str(e))


# ====================================================================
# TEST GROUP 3: DEPLOY POLICY ENFORCEMENT
# ====================================================================
print("\n=== DEPLOY POLICY ENFORCEMENT Tests ===")

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))
    from app.routers.deploy_policies import evaluate_deploy_policies, POLICY_TYPES
    log_test("evaluate_deploy_policies importable", True)
    log_test("POLICY_TYPES has 6 types", len(POLICY_TYPES) == 6,
             f"found {len(POLICY_TYPES)}: {POLICY_TYPES}")
except ImportError as e:
    log_test("deploy_policies import", False, str(e))

# Policy types completeness check
try:
    expected_types = [
        "branch_restriction", "approval_required", "time_window",
        "artifact_age_limit", "artifact_signature", "build_status_check"
    ]
    from app.routers.deploy_policies import POLICY_TYPES
    for ptype in expected_types:
        log_test(f"Policy type '{ptype}' exists", ptype in POLICY_TYPES)
except Exception as e:
    log_test("Policy types check", False, str(e))


# ====================================================================
# TEST GROUP 4: RBAC PERMISSION FUNCTIONS
# ====================================================================
print("\n=== RBAC PERMISSION Tests ===")

try:
    from app.routers.rbac import check_permission, require_permission, get_user_permissions
    log_test("check_permission importable", callable(check_permission))
    log_test("require_permission importable", callable(require_permission))
    log_test("get_user_permissions importable", callable(get_user_permissions))
except ImportError as e:
    log_test("RBAC functions import", False, str(e))


# ====================================================================
# TEST GROUP 5: WEBHOOK RECEIVERS (EAS + Codemagic)
# ====================================================================
print("\n=== WEBHOOK RECEIVER Tests ===")

try:
    from app.routers.webhooks import router as webhook_router
    routes = [r.path for r in webhook_router.routes]
    log_test("Webhook /github route exists", any("/github" in r for r in routes))
    log_test("Webhook /eas route exists", any("/eas" in r for r in routes))
    log_test("Webhook /codemagic route exists", any("/codemagic" in r for r in routes))
except ImportError as e:
    log_test("Webhook router import", False, str(e))

try:
    from app.routers.webhooks import _verify_signature
    import hmac
    import hashlib
    secret = "test-secret"
    body = b'{"test": true}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    result = _verify_signature(body, sig, secret)
    log_test("HMAC signature verification works", result is True)
except Exception as e:
    log_test("HMAC verification", False, str(e))


# ====================================================================
# TEST GROUP 6: IMMUTABLE AUDIT — Hash Chaining
# ====================================================================
print("\n=== IMMUTABLE AUDIT Tests ===")

try:
    from app.routers.immutable_audit import compute_entry_hash, GENESIS_HASH
    log_test("compute_entry_hash importable", callable(compute_entry_hash))
    log_test("GENESIS_HASH is 64 zeros", GENESIS_HASH == "0" * 64)

    # Deterministic hash test
    h1 = compute_entry_hash(1, "user1", "create", "project", "proj1", {}, GENESIS_HASH, datetime(2024, 1, 1))
    h2 = compute_entry_hash(1, "user1", "create", "project", "proj1", {}, GENESIS_HASH, datetime(2024, 1, 1))
    log_test("Hash computation is deterministic", h1 == h2)

    # Different input -> different hash
    h3 = compute_entry_hash(2, "user1", "create", "project", "proj1", {}, h1, datetime(2024, 1, 1))
    log_test("Different sequence_number -> different hash", h1 != h3)
except Exception as e:
    log_test("Immutable audit hash tests", False, str(e))


# ====================================================================
# TEST GROUP 7: SUPPORT TICKET MODEL
# ====================================================================
print("\n=== SUPPORT TICKET Tests ===")

try:
    from app.models import SupportTicket
    log_test("SupportTicket model importable", True)
    log_test("SupportTicket has __tablename__", SupportTicket.__tablename__ == "support_tickets")
except ImportError as e:
    log_test("SupportTicket import", False, str(e))

try:
    from app.routers.support import router as support_router
    routes = [r.path for r in support_router.routes]
    log_test("Support POST route exists", any(r == "" or r == "/" for r in routes))
except ImportError as e:
    log_test("Support router import", False, str(e))


# ====================================================================
# TEST GROUP 8: ORGANIZATION MODEL
# ====================================================================
print("\n=== ORGANIZATION Tests ===")

try:
    from app.models import Organization, OrgMember
    log_test("Organization model importable", True)
    log_test("OrgMember model importable", True)
    log_test("Organization table name", Organization.__tablename__ == "organizations")
    log_test("OrgMember table name", OrgMember.__tablename__ == "org_members")
except ImportError as e:
    log_test("Organization models import", False, str(e))

try:
    from app.routers.organizations import router as org_router
    routes = [r.path for r in org_router.routes]
    log_test("Org create route exists", any(r == "" or r == "/" for r in routes))
    log_test("Org members route exists", any("/members" in r for r in routes))
except ImportError as e:
    log_test("Organization router import", False, str(e))


# ====================================================================
# TEST GROUP 9: SSO PROVIDER MODEL
# ====================================================================
print("\n=== SSO PROVIDER Tests ===")

try:
    from app.models import SSOProvider
    log_test("SSOProvider model importable", True)
    log_test("SSOProvider table name", SSOProvider.__tablename__ == "sso_providers")
except ImportError as e:
    log_test("SSOProvider import", False, str(e))

try:
    from app.routers.sso import router as sso_router
    routes = [r.path for r in sso_router.routes]
    log_test("SSO providers route exists", any("/providers" in r for r in routes))
    log_test("SSO authorize route exists", any("/authorize" in r for r in routes))
    log_test("SSO callback route exists", any("/callback" in r for r in routes))
except ImportError as e:
    log_test("SSO router import", False, str(e))


# ====================================================================
# TEST GROUP 10: OTA UPDATE MODEL
# ====================================================================
print("\n=== OTA UPDATE Tests ===")

try:
    from app.models import OTAUpdate
    log_test("OTAUpdate model importable", True)
    log_test("OTAUpdate table name", OTAUpdate.__tablename__ == "ota_updates")
except ImportError as e:
    log_test("OTAUpdate import", False, str(e))

try:
    from app.routers.ota import router as ota_router
    routes = [r.path for r in ota_router.routes]
    log_test("OTA custom-bundle route exists", any("custom-bundle" in r for r in routes))
except ImportError as e:
    log_test("OTA router import", False, str(e))


# ====================================================================
# TEST GROUP 11: CRYPTO MODULE
# ====================================================================
print("\n=== CRYPTO Tests ===")

try:
    from app.crypto import encrypt, decrypt, encrypt_for_tenant, decrypt_for_tenant

    # Basic encrypt/decrypt
    original = "my-secret-credential-value"
    encrypted = encrypt(original)
    decrypted = decrypt(encrypted)
    log_test("Encrypt/decrypt roundtrip", decrypted == original)
    log_test("Encrypted value prefixed with v1:", encrypted.startswith("v1:"))

    # Tenant encryption
    tenant_encrypted = encrypt_for_tenant("tenant-secret", "org-123")
    tenant_decrypted = decrypt_for_tenant(tenant_encrypted, "org-123")
    log_test("Tenant encrypt/decrypt roundtrip", tenant_decrypted == "tenant-secret")
    log_test("Tenant encrypted starts with t1:", tenant_encrypted.startswith("t1:"))
except Exception as e:
    log_test("Crypto module tests", False, str(e))


# ====================================================================
# TEST GROUP 12: CONFIG VALIDATION
# ====================================================================
print("\n=== CONFIG VALIDATION Tests ===")

try:
    from app.config import Settings
    log_test("Settings class importable", True)

    # Check ENVIRONMENT field exists
    fields = Settings.model_fields
    log_test("ENVIRONMENT field exists", "ENVIRONMENT" in fields)
    log_test("EAS_WEBHOOK_SECRET field exists", "EAS_WEBHOOK_SECRET" in fields)
    log_test("CODEMAGIC_WEBHOOK_SECRET field exists", "CODEMAGIC_WEBHOOK_SECRET" in fields)
except Exception as e:
    log_test("Config validation tests", False, str(e))


# ====================================================================
# SUMMARY
# ====================================================================
print(f"\n{'='*60}")
print(f"  TOTAL: {PASS_COUNT + FAIL_COUNT}  |  PASSED: {PASS_COUNT}  |  FAILED: {FAIL_COUNT}")
print(f"{'='*60}")

if FAIL_COUNT > 0:
    print("\nFailed tests:")
    for r in RESULTS:
        if not r["passed"]:
            print(f"  x {r['name']}: {r['detail']}")

sys.exit(1 if FAIL_COUNT > 0 else 0)
