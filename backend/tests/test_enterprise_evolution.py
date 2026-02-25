import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-enterprise")
os.environ.setdefault("FERNET_SALT", "test-fernet-salt-enterprise")

results = {"pass": 0, "fail": 0, "tests": []}


def log_test(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results["tests"].append({"name": name, "status": status, "detail": detail})
    if passed:
        results["pass"] += 1
    else:
        results["fail"] += 1
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not passed else ""))


print("=" * 70)
print("  ENTERPRISE EVOLUTION TESTS (v0.8.0)")
print("=" * 70)

# ============================================================
# 1. WAF MIDDLEWARE
# ============================================================
print("\n=== 1. WAF MIDDLEWARE ===")
try:
    from app.waf import WAFMiddleware, _score_request, _check_rate, get_waf_stats, SUSPICIOUS_PATTERNS
    log_test("WAF: Module imports", True)
    log_test("WAF: WAFMiddleware class exists", callable(WAFMiddleware))
    log_test("WAF: _score_request function exists", callable(_score_request))
    log_test("WAF: _check_rate function exists", callable(_check_rate))
    log_test("WAF: get_waf_stats function exists", callable(get_waf_stats))
    log_test("WAF: Suspicious patterns defined", len(SUSPICIOUS_PATTERNS) >= 10)

    stats = get_waf_stats()
    log_test("WAF: get_waf_stats returns blocked_ips", "blocked_ips" in stats)
    log_test("WAF: get_waf_stats returns tracked_ips", "tracked_ips" in stats)
except Exception as e:
    log_test("WAF: Module import", False, str(e))

# ============================================================
# 2. ANOMALY DETECTION
# ============================================================
print("\n=== 2. ANOMALY DETECTION ===")
try:
    from app.anomaly_detection import record_activity, check_tenant_anomalies, get_all_anomalies, THRESHOLDS
    log_test("Anomaly: Module imports", True)
    log_test("Anomaly: record_activity exists", callable(record_activity))
    log_test("Anomaly: check_tenant_anomalies exists", callable(check_tenant_anomalies))
    log_test("Anomaly: get_all_anomalies exists", callable(get_all_anomalies))

    log_test("Anomaly: Thresholds defined", len(THRESHOLDS) >= 5)
    log_test("Anomaly: builds_per_hour threshold", THRESHOLDS["builds_per_hour"]["critical"] == 50)
    log_test("Anomaly: deploys_per_hour threshold", THRESHOLDS["deploys_per_hour"]["critical"] == 30)
    log_test("Anomaly: login_failures threshold", THRESHOLDS["login_failures_per_hour"]["critical"] == 30)

    record_activity("test-tenant", "build_trigger")
    anomalies = check_tenant_anomalies("test-tenant")
    log_test("Anomaly: Single activity no anomaly", len(anomalies) == 0)

    for i in range(55):
        record_activity("flood-tenant", "build_trigger")
    anomalies = check_tenant_anomalies("flood-tenant")
    log_test("Anomaly: Build flood detected", len(anomalies) > 0)
    if anomalies:
        log_test("Anomaly: Flood severity critical", anomalies[0]["severity"] == "critical")
        log_test("Anomaly: Flood type correct", anomalies[0]["type"] == "builds_per_hour")

    all_anomalies = get_all_anomalies()
    log_test("Anomaly: get_all_anomalies returns dict", isinstance(all_anomalies, dict))

except Exception as e:
    log_test("Anomaly: Module import", False, str(e))

# ============================================================
# 3. CREDENTIAL VALIDATION
# ============================================================
print("\n=== 3. CREDENTIAL VALIDATION ===")
try:
    from app.routers.credential_validation import _validate_google_play, _validate_app_store, router as cv_router
    log_test("CredVal: Module imports", True)
    log_test("CredVal: _validate_google_play exists", callable(_validate_google_play))
    log_test("CredVal: _validate_app_store exists", callable(_validate_app_store))
    log_test("CredVal: Router has routes", len(cv_router.routes) >= 2)

    import asyncio

    async def test_invalid_google():
        result = await _validate_google_play("not-json")
        return result
    r = asyncio.run(test_invalid_google())
    log_test("CredVal: Invalid JSON detected", r["valid"] is False)
    log_test("CredVal: Error message for invalid JSON", "Invalid JSON" in r["error"])

    async def test_missing_fields():
        import json
        result = await _validate_google_play(json.dumps({"type": "service_account"}))
        return result
    r = asyncio.run(test_missing_fields())
    log_test("CredVal: Missing fields detected", r["valid"] is False)
    log_test("CredVal: Missing fields listed", "Missing fields" in r["error"])

    async def test_invalid_appstore():
        result = await _validate_app_store("", "", "")
        return result
    r = asyncio.run(test_invalid_appstore())
    log_test("CredVal: Empty AppStore creds rejected", r["valid"] is False)

except Exception as e:
    log_test("CredVal: Module import", False, str(e))

# ============================================================
# 4. DEPLOY SIMULATOR
# ============================================================
print("\n=== 4. DEPLOY SIMULATOR ===")
try:
    from app.routers.deploy_simulator import (
        router as ds_router, ESTIMATED_BUILD_MINUTES,
        ESTIMATED_REVIEW_HOURS, FRAMEWORK_PROVIDER_MAP, _get_tips
    )
    log_test("DeploySim: Module imports", True)
    log_test("DeploySim: Router has routes", len(ds_router.routes) >= 1)
    log_test("DeploySim: Build time estimates exist", len(ESTIMATED_BUILD_MINUTES) >= 3)
    log_test("DeploySim: Review time estimates exist", len(ESTIMATED_REVIEW_HOURS) >= 2)
    log_test("DeploySim: Framework-provider map exists", len(FRAMEWORK_PROVIDER_MAP) >= 5)

    log_test("DeploySim: EAS build times", "eas" in ESTIMATED_BUILD_MINUTES)
    log_test("DeploySim: Codemagic build times", "codemagic" in ESTIMATED_BUILD_MINUTES)
    log_test("DeploySim: Google Play review hours", "google_play" in ESTIMATED_REVIEW_HOURS)
    log_test("DeploySim: App Store review hours", "app_store" in ESTIMATED_REVIEW_HOURS)

    tips = _get_tips("app_store", "production")
    log_test("DeploySim: Production tips generated", len(tips) >= 2)
    tips_internal = _get_tips("google_play", "internal")
    log_test("DeploySim: Internal tips generated", len(tips_internal) >= 1)

except Exception as e:
    log_test("DeploySim: Module import", False, str(e))

# ============================================================
# 5. DEPLOY ERROR GUIDE
# ============================================================
print("\n=== 5. DEPLOY ERROR GUIDE ===")
try:
    from app.deploy_error_guide import DEPLOY_ERROR_GUIDE, get_deploy_error_guide
    log_test("ErrorGuide: Module imports", True)
    log_test("ErrorGuide: Error codes defined", len(DEPLOY_ERROR_GUIDE) >= 10)

    required_codes = [
        "CREDENTIAL_MISSING", "CREDENTIAL_INVALID", "BUILD_NOT_READY",
        "ARTIFACT_EXPIRED", "STORE_RATE_LIMIT", "SIGNING_ERROR",
        "NETWORK_TIMEOUT", "QUOTA_EXCEEDED", "FASTLANE_ERROR",
    ]
    for code in required_codes:
        guide = get_deploy_error_guide(code)
        log_test(f"ErrorGuide: {code} has title", bool(guide.get("title")))
        log_test(f"ErrorGuide: {code} has steps", len(guide.get("steps", [])) >= 1)

    unknown = get_deploy_error_guide("UNKNOWN_CODE")
    log_test("ErrorGuide: Unknown code returns fallback", "Deployment error" in unknown["title"])

except Exception as e:
    log_test("ErrorGuide: Module import", False, str(e))

# ============================================================
# 6. METRICS KPI
# ============================================================
print("\n=== 6. METRICS KPI ===")
try:
    from app.routers.metrics_kpi import router as mk_router
    log_test("KPI: Module imports", True)
    log_test("KPI: Router has routes", len(mk_router.routes) >= 2)

    route_paths = [r.path for r in mk_router.routes if hasattr(r, 'path')]
    log_test("KPI: time-to-first-deploy route", any("time-to-first-deploy" in p for p in route_paths))
    log_test("KPI: platform-kpis route", any("platform-kpis" in p for p in route_paths))

except Exception as e:
    log_test("KPI: Module import", False, str(e))

# ============================================================
# 7. CANARY DEPLOY
# ============================================================
print("\n=== 7. CANARY DEPLOY ===")
try:
    from app.routers.canary import router as canary_router
    log_test("Canary: Module imports", True)
    log_test("Canary: Router has routes", len(canary_router.routes) >= 4)

    route_paths = [r.path for r in canary_router.routes if hasattr(r, 'path')]
    log_test("Canary: canary route exists", any("canary" in p for p in route_paths))
    log_test("Canary: promote route exists", any("promote" in p for p in route_paths))
    log_test("Canary: rollback route exists", any("rollback" in p for p in route_paths))
    log_test("Canary: canary-metrics route exists", any("canary-metrics" in p for p in route_paths))

except Exception as e:
    log_test("Canary: Module import", False, str(e))

# ============================================================
# 8. COMPLIANCE ENGINE
# ============================================================
print("\n=== 8. COMPLIANCE ENGINE ===")
try:
    from app.routers.compliance import router as compliance_router, RETENTION_POLICIES
    log_test("Compliance: Module imports", True)
    log_test("Compliance: Router has routes", len(compliance_router.routes) >= 4)

    log_test("Compliance: Retention policies defined", len(RETENTION_POLICIES) >= 6)
    log_test("Compliance: audit_logs retention", "audit_logs" in RETENTION_POLICIES)
    log_test("Compliance: build_artifacts retention", "build_artifacts" in RETENTION_POLICIES)
    log_test("Compliance: immutable_audit retention", "immutable_audit" in RETENTION_POLICIES)

    log_test("Compliance: Audit log retention >= 365", RETENTION_POLICIES["audit_logs"]["default_days"] >= 365)
    log_test("Compliance: Immutable audit retention >= 2555", RETENTION_POLICIES["immutable_audit"]["default_days"] >= 2555)
    log_test("Compliance: Nonce retention short", RETENTION_POLICIES["webhook_nonces"]["default_days"] <= 30)

    route_paths = [r.path for r in compliance_router.routes if hasattr(r, 'path')]
    log_test("Compliance: retention-policies route", any("retention" in p for p in route_paths))
    log_test("Compliance: purge-expired route", any("purge" in p for p in route_paths))
    log_test("Compliance: legal-hold route", any("legal-hold" in p for p in route_paths))
    log_test("Compliance: audit-export route", any("audit-export" in p for p in route_paths))
    log_test("Compliance: data-locality route", any("data-locality" in p for p in route_paths))

except Exception as e:
    log_test("Compliance: Module import", False, str(e))

# ============================================================
# 9. IMMUTABLE AUDIT HELPER
# ============================================================
print("\n=== 9. IMMUTABLE AUDIT HELPER ===")
try:
    from app.audit import record_audit, record_audit_with_db, create_immutable_audit, _compute_hash
    log_test("Audit: record_audit exists", callable(record_audit))
    log_test("Audit: record_audit_with_db exists", callable(record_audit_with_db))
    log_test("Audit: create_immutable_audit exists", callable(create_immutable_audit))
    log_test("Audit: _compute_hash exists", callable(_compute_hash))

    h1 = _compute_hash(1, "test", "project", "p1", {}, "0" * 64)
    h2 = _compute_hash(1, "test", "project", "p1", {}, "0" * 64)
    log_test("Audit: Hash is deterministic", h1 == h2)

    h3 = _compute_hash(2, "test", "project", "p1", {}, h1)
    log_test("Audit: Different sequence different hash", h3 != h1)
    log_test("Audit: Hash is sha256 length", len(h1) == 64)

except Exception as e:
    log_test("Audit: Module import", False, str(e))

# ============================================================
# 10. K8S MANIFESTS
# ============================================================
print("\n=== 10. KUBERNETES MANIFESTS ===")
try:
    import yaml

    k8s_base = os.path.join(os.path.dirname(__file__), "..", "..", "k8s", "base")
    helm_dir = os.path.join(os.path.dirname(__file__), "..", "..", "k8s", "helm", "apptrack")

    for f in ["gateway.yaml", "services.yaml", "networking.yaml"]:
        path = os.path.join(k8s_base, f)
        exists = os.path.exists(path)
        log_test(f"K8s: {f} exists", exists)
        if exists:
            with open(path) as fh:
                docs = list(yaml.safe_load_all(fh.read()))
                log_test(f"K8s: {f} valid YAML", len(docs) > 0)

    chart_path = os.path.join(helm_dir, "Chart.yaml")
    values_path = os.path.join(helm_dir, "values.yaml")

    log_test("K8s: Helm Chart.yaml exists", os.path.exists(chart_path))
    log_test("K8s: Helm values.yaml exists", os.path.exists(values_path))

    if os.path.exists(chart_path):
        with open(chart_path) as f:
            chart = yaml.safe_load(f)
            log_test("K8s: Chart version 0.8.0", chart.get("version") == "0.8.0")
            log_test("K8s: Chart name apptrack", chart.get("name") == "apptrack")

    if os.path.exists(values_path):
        with open(values_path) as f:
            values = yaml.safe_load(f)
            log_test("K8s: HPA enabled", values.get("autoscaling", {}).get("enabled") is True)
            log_test("K8s: Ingress enabled", values.get("ingress", {}).get("enabled") is True)
            log_test("K8s: PostgreSQL enabled", values.get("postgresql", {}).get("enabled") is True)
            log_test("K8s: RabbitMQ enabled", values.get("rabbitmq", {}).get("enabled") is True)
            log_test("K8s: Feature flags present", "featureFlags" in values)
            log_test("K8s: Gateway replicas >= 2", values.get("replicaCount", {}).get("gateway", 0) >= 2)

except ImportError:
    print("  [SKIP] PyYAML not installed — skipping K8s YAML validation")
except Exception as e:
    log_test("K8s: Manifests", False, str(e))

# ============================================================
# 11. FRONTEND COMPONENTS
# ============================================================
print("\n=== 11. FRONTEND COMPONENTS ===")
try:
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src")

    confetti_path = os.path.join(frontend_dir, "components", "ui", "Confetti.tsx")
    log_test("FE: Confetti.tsx exists", os.path.exists(confetti_path))
    if os.path.exists(confetti_path):
        with open(confetti_path, encoding="utf-8") as f:
            content = f.read()
            log_test("FE: Confetti has animation", "confetti-fall" in content)
            log_test("FE: Confetti has colors", "COLORS" in content)
            log_test("FE: Confetti has duration prop", "duration" in content)

    error_guide_path = os.path.join(frontend_dir, "components", "ui", "DeployErrorGuide.tsx")
    log_test("FE: DeployErrorGuide.tsx exists", os.path.exists(error_guide_path))
    if os.path.exists(error_guide_path):
        with open(error_guide_path, encoding="utf-8") as f:
            content = f.read()
            log_test("FE: ErrorGuide fetches deploy-errors", "deploy-errors" in content)
            log_test("FE: ErrorGuide has retry button", "onRetry" in content)
            log_test("FE: ErrorGuide shows steps", "steps" in content)

    onboarding_path = os.path.join(frontend_dir, "pages", "OnboardingPage.tsx")
    if os.path.exists(onboarding_path):
        with open(onboarding_path, encoding="utf-8") as f:
            content = f.read()
            log_test("FE: Onboarding has credentials step", "'credentials'" in content)
            log_test("FE: Onboarding has build step", "'build'" in content)
            log_test("FE: Onboarding has deploy step", "'deploy'" in content)
            log_test("FE: Onboarding uses Confetti", "Confetti" in content)
            log_test("FE: Onboarding has Google Play tab", "google_play" in content)
            log_test("FE: Onboarding has App Store tab", "app_store" in content)
            log_test("FE: Onboarding has 7 steps", content.count("num:") >= 7)

    roadmap_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "ENTERPRISE_ROADMAP.md")
    log_test("Docs: Enterprise roadmap exists", os.path.exists(roadmap_path))
    if os.path.exists(roadmap_path):
        with open(roadmap_path, encoding="utf-8") as f:
            content = f.read()
            log_test("Docs: Roadmap has risk analysis", "Risk Analysis" in content)
            log_test("Docs: Roadmap has migration order", "Migration Order" in content)
            log_test("Docs: Roadmap has phase breakdown", "Phase 0" in content and "Phase 5" in content)

except Exception as e:
    log_test("Frontend: Components", False, str(e))

# ============================================================
# 12. GATEWAY MAIN INTEGRATION
# ============================================================
print("\n=== 12. GATEWAY MAIN INTEGRATION ===")
try:
    from app.main import app as fastapi_app
    log_test("Gateway: App version 0.8.0", fastapi_app.version == "0.8.0")

    route_paths = [r.path for r in fastapi_app.routes if hasattr(r, 'path')]
    log_test("Gateway: /api/deploy-errors route", any("deploy-errors" in p for p in route_paths))
    log_test("Gateway: /api/credentials/validate route", any("validate" in p for p in route_paths))
    log_test("Gateway: /api/metrics route", any("metrics" in p for p in route_paths))
    log_test("Gateway: /api/compliance route", any("compliance" in p for p in route_paths))

    gateway_main_content = open(os.path.join(os.path.dirname(__file__), "..", "gateway", "app", "main.py"), encoding="utf-8").read()
    log_test("Gateway: WAFMiddleware registered", "WAFMiddleware" in gateway_main_content)
    log_test("Gateway: credential_validation imported", "credential_validation" in gateway_main_content)
    log_test("Gateway: deploy_simulator imported", "deploy_simulator" in gateway_main_content)
    log_test("Gateway: metrics_kpi imported", "metrics_kpi" in gateway_main_content)
    log_test("Gateway: canary imported", "canary" in gateway_main_content)
    log_test("Gateway: compliance imported", "compliance" in gateway_main_content)

except Exception as e:
    log_test("Gateway: Main integration", False, str(e))

# ============================================================
# SUMMARY
# ============================================================
total = results["pass"] + results["fail"]
print("\n" + "=" * 70)
print(f"  ENTERPRISE EVOLUTION TEST RESULTS (v0.8.0)")
print(f"  Passed: {results['pass']}/{total}")
print(f"  Failed: {results['fail']}/{total}")
print("=" * 70)

if results["fail"] > 0:
    print("\n  Failed tests:")
    for t in results["tests"]:
        if t["status"] == "FAIL":
            print(f"    [FAIL] {t['name']}: {t['detail']}")

print()
sys.exit(0 if results["fail"] == 0 else 1)
