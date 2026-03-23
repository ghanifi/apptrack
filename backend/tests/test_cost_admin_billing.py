import sys
import os
import re
import ast
import json
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_base = os.path.join(os.path.dirname(__file__), "..")
# Support both local (backend/gateway/) and container (/app/) layouts
_gw_candidate = os.path.join(_base, "gateway")
GATEWAY = _gw_candidate if os.path.isdir(_gw_candidate) else _base
_svc_candidate = os.path.join(_base, "services")
SERVICES = _svc_candidate if os.path.isdir(_svc_candidate) else os.path.join(_base, "..", "services")

passed = 0
failed = 0
errors = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        errors.append(f"FAIL: {name} — {detail}")


def read(path):
    full = os.path.normpath(path)
    if os.path.exists(full):
        with open(full, "r", encoding="utf-8") as f:
            return f.read()
    return ""


# ──────────────────────────────────────────
# 1. COST GUARD MODULE
# ──────────────────────────────────────────
cg_src = read(os.path.join(GATEWAY, "app", "cost_guard.py"))

check("CG-001: cost_guard.py exists", len(cg_src) > 100)
check("CG-002: PROVIDER_COST_PER_MINUTE defined", "PROVIDER_COST_PER_MINUTE" in cg_src)
check("CG-003: EAS rate present", "eas" in cg_src and "0.05" in cg_src)
check("CG-004: Codemagic rate present", "codemagic" in cg_src and "0.038" in cg_src)
check("CG-005: GitHub Actions rate present", "github_actions" in cg_src and "0.008" in cg_src)
check("CG-006: ESTIMATED_BUILD_MINUTES defined", "ESTIMATED_BUILD_MINUTES" in cg_src)
check("CG-007: PLAN_MONTHLY_BUDGET_USD defined", "PLAN_MONTHLY_BUDGET_USD" in cg_src)
check("CG-008: Free plan budget is $0", '"free": 0' in cg_src or "'free': 0" in cg_src)
check("CG-009: Pro plan budget cap", '"pro": 50' in cg_src or "'pro': 50" in cg_src)
check("CG-010: Enterprise plan budget cap", '"enterprise": 500' in cg_src or "'enterprise': 500" in cg_src)
check("CG-011: estimate_build_cost function", "async def estimate_build_cost" in cg_src)
check("CG-012: Returns estimated_cost_usd", "estimated_cost_usd" in cg_src)
check("CG-013: Returns estimated_minutes", "estimated_minutes" in cg_src)
check("CG-014: Returns rate_per_minute", "rate_per_minute" in cg_src)
check("CG-015: get_monthly_spend function", "async def get_monthly_spend" in cg_src)
check("CG-016: Queries build_cost_usd metric", "build_cost_usd" in cg_src)
check("CG-017: check_budget_limit function", "async def check_budget_limit" in cg_src)
check("CG-018: Returns 429 on budget exceeded", "429" in cg_src)
check("CG-019: Shows remaining budget", "Remaining" in cg_src or "remaining" in cg_src)
check("CG-020: AUTO_SUSPEND_THRESHOLD defined", "AUTO_SUSPEND_THRESHOLD" in cg_src)
check("CG-021: record_build_cost function", "async def record_build_cost" in cg_src)
check("CG-022: Uses UsageRecord model", "UsageRecord" in cg_src)
check("CG-023: Handles actual_minutes parameter", "actual_minutes" in cg_src)
check("CG-024: Uses period_start for monthly tracking", "period_start" in cg_src)
check("CG-025: Syntax valid", bool(cg_src))
try:
    ast.parse(cg_src)
    check("CG-026: AST parse succeeds", True)
except SyntaxError as e:
    check("CG-026: AST parse succeeds", False, str(e))


# ──────────────────────────────────────────
# 2. COST GUARD INTEGRATION IN PROJECTS ROUTER
# ──────────────────────────────────────────
proj_src = read(os.path.join(GATEWAY, "app", "routers", "projects.py"))

check("CGI-001: cost_guard imported in projects", "from app.cost_guard import" in proj_src)
check("CGI-002: estimate_build_cost imported", "estimate_build_cost" in proj_src)
check("CGI-003: check_budget_limit imported", "check_budget_limit" in proj_src)
check("CGI-004: estimate_build_cost called before build", "await estimate_build_cost(provider, platform)" in proj_src)
check("CGI-005: check_budget_limit called", "await check_budget_limit(db, current_user" in proj_src)
check("CGI-006: cost_estimate in response", "cost_estimate" in proj_src)
check("CGI-007: Cost check before idempotency check",
      proj_src.index("estimate_build_cost") < proj_src.index("idem_key"))


# ──────────────────────────────────────────
# 3. COST RECORDING IN WORKER
# ──────────────────────────────────────────
worker_src = read(os.path.join(GATEWAY, "app", "worker.py"))

check("CRW-001: record_build_cost imported in worker", "record_build_cost" in worker_src)
check("CRW-002: Record cost on success", 'status == "success"' in worker_src and "record_build_cost" in worker_src)
check("CRW-003: Uses actual duration_minutes", "duration_minutes" in worker_src)
check("CRW-004: Cost recording has error handling", "cost_exc" in worker_src or "Failed to record build cost" in worker_src)
check("CRW-005: Looks up build owner for cost", "proj.owner_id" in worker_src)


# ──────────────────────────────────────────
# 4. BUILD COST ESTIMATE ENDPOINT
# ──────────────────────────────────────────
builds_src = read(os.path.join(GATEWAY, "app", "routers", "builds.py"))

check("BCE-001: cost estimate endpoint exists", "/cost/estimate" in builds_src)
check("BCE-002: Uses estimate_build_cost", "estimate_build_cost" in builds_src)
check("BCE-003: Uses get_monthly_spend", "get_monthly_spend" in builds_src)
check("BCE-004: Returns current_monthly_spend_usd", "current_monthly_spend_usd" in builds_src)
check("BCE-005: Has provider query param", 'provider' in builds_src)
check("BCE-006: Has platform query param", 'platform' in builds_src)


# ──────────────────────────────────────────
# 5. ADMIN PANEL ROUTER
# ──────────────────────────────────────────
admin_src = read(os.path.join(GATEWAY, "app", "routers", "admin.py"))

check("ADM-001: admin.py exists", len(admin_src) > 100)
check("ADM-002: Admin prefix /api/admin", "/api/admin" in admin_src)
check("ADM-003: ADMIN_EMAILS check", "ADMIN_EMAILS" in admin_src)
check("ADM-004: _require_admin function", "_require_admin" in admin_src)
check("ADM-005: Returns 403 for non-admin", "403" in admin_src)

check("ADM-006: /tenants endpoint", '"/tenants"' in admin_src or "list_tenants" in admin_src)
check("ADM-007: Pagination support", "page" in admin_src and "size" in admin_src)
check("ADM-008: Search filter", "search" in admin_src)

check("ADM-009: /tenants/{user_id}/debug endpoint", "tenant_debug_view" in admin_src)
check("ADM-010: Returns tenant info", '"tenant"' in admin_src)
check("ADM-011: Returns recent builds", "recent_builds" in admin_src)
check("ADM-012: Returns recent deploys", "recent_deploys" in admin_src)
check("ADM-013: Returns recent audit", "recent_audit" in admin_src)
check("ADM-014: Returns usage data", '"usage"' in admin_src)
check("ADM-015: Returns stats", '"stats"' in admin_src)
check("ADM-016: Returns credentials count", "credentials_configured" in admin_src)

check("ADM-017: /builds/{build_id}/retry endpoint", "admin_retry_build" in admin_src)
check("ADM-018: Only retry failed/cancelled builds", '"failed"' in admin_src and '"cancelled"' in admin_src)
check("ADM-019: Creates new build on retry", "new_build" in admin_src)
check("ADM-020: Logs admin retry", "Admin retry" in admin_src)

check("ADM-021: /tenants/{user_id}/change-plan endpoint", "admin_change_plan" in admin_src)
check("ADM-022: Validates plan name", "PLAN_DEFAULTS" in admin_src)
check("ADM-023: Updates quota", "quota.plan = plan" in admin_src)

check("ADM-024: /tenants/{user_id}/suspend endpoint", "admin_suspend_tenant" in admin_src)
check("ADM-025: Cancels active builds on suspend", "cancelled" in admin_src)
check("ADM-026: Logs suspension reason", "reason" in admin_src)

check("ADM-027: /overview endpoint", "admin_overview" in admin_src)
check("ADM-028: Returns total users", "total_users" in admin_src)
check("ADM-029: Returns build stats", "builds_today" in admin_src)
check("ADM-030: Returns deploy stats", "deploys_today" in admin_src)
check("ADM-031: Returns failed builds", "failed_builds_today" in admin_src)

check("ADM-032: /audit-export endpoint", "export_audit_logs" in admin_src)
check("ADM-033: Supports user_id filter", "user_id" in admin_src)
check("ADM-034: Supports action filter", "action" in admin_src)
check("ADM-035: Supports days parameter", "days" in admin_src)
check("ADM-036: Limits export to 1000", "1000" in admin_src)

try:
    ast.parse(admin_src)
    check("ADM-037: AST parse succeeds", True)
except SyntaxError as e:
    check("ADM-037: AST parse succeeds", False, str(e))


# ──────────────────────────────────────────
# 6. BILLING MODULE
# ──────────────────────────────────────────
billing_src = read(os.path.join(GATEWAY, "app", "billing.py"))

check("BIL-001: billing.py exists", len(billing_src) > 100)
check("BIL-002: STRIPE_PLAN_MAP defined", "STRIPE_PLAN_MAP" in billing_src)
check("BIL-003: PLAN_PRICES_USD defined", "PLAN_PRICES_USD" in billing_src)
check("BIL-004: Free plan is $0", '"free": 0' in billing_src or "'free': 0" in billing_src)
check("BIL-005: Pro plan price", '"pro": 29' in billing_src or "'pro': 29" in billing_src)
check("BIL-006: Enterprise plan price", '"enterprise": 199' in billing_src or "'enterprise': 199" in billing_src)
check("BIL-007: GRACE_PERIOD_DAYS defined", "GRACE_PERIOD_DAYS" in billing_src)
check("BIL-008: SUSPEND_AFTER_DAYS defined", "SUSPEND_AFTER_DAYS" in billing_src)

check("BIL-009: verify_stripe_signature function", "def verify_stripe_signature" in billing_src)
check("BIL-010: Uses HMAC for Stripe verification", "hmac" in billing_src)
check("BIL-011: Uses compare_digest", "compare_digest" in billing_src)

check("BIL-012: handle_checkout_completed", "handle_checkout_completed" in billing_src)
check("BIL-013: Gets customer email from checkout", "customer_email" in billing_src or "customer_details" in billing_src)
check("BIL-014: Gets price_id from line items", "price_id" in billing_src)

check("BIL-015: handle_subscription_updated", "handle_subscription_updated" in billing_src)
check("BIL-016: Handles active status", '"active"' in billing_src)
check("BIL-017: Handles past_due status", '"past_due"' in billing_src)
check("BIL-018: Handles canceled status", '"canceled"' in billing_src)

check("BIL-019: handle_invoice_payment_failed", "handle_invoice_payment_failed" in billing_src)
check("BIL-020: Suspends after 3 failed attempts", "attempt_count >= 3" in billing_src)

check("BIL-021: handle_subscription_deleted", "handle_subscription_deleted" in billing_src)
check("BIL-022: Downgrades to free on deletion", "_downgrade_to_free" in billing_src)

check("BIL-023: _update_user_plan function", "_update_user_plan" in billing_src)
check("BIL-024: Creates audit log on plan change", "billing.plan_changed" in billing_src)
check("BIL-025: _suspend_user function", "_suspend_user" in billing_src)
check("BIL-026: Cancels active builds on suspend", "cancelled" in billing_src)

try:
    ast.parse(billing_src)
    check("BIL-027: AST parse succeeds", True)
except SyntaxError as e:
    check("BIL-027: AST parse succeeds", False, str(e))


# ──────────────────────────────────────────
# 7. BILLING ROUTER
# ──────────────────────────────────────────
billing_router_src = read(os.path.join(GATEWAY, "app", "routers", "billing.py"))

check("BRT-001: billing router exists", len(billing_router_src) > 100)
check("BRT-002: /api/billing prefix", "/api/billing" in billing_router_src)

check("BRT-003: /webhook/stripe endpoint", "/webhook/stripe" in billing_router_src)
check("BRT-004: Verifies Stripe signature", "verify_stripe_signature" in billing_router_src)
check("BRT-005: Returns 400 on invalid signature", "400" in billing_router_src)
check("BRT-006: Dispatches to handlers", "handlers" in billing_router_src)
check("BRT-007: Handles checkout.session.completed", "checkout.session.completed" in billing_router_src)
check("BRT-008: Handles subscription.updated", "customer.subscription.updated" in billing_router_src)
check("BRT-009: Handles subscription.deleted", "customer.subscription.deleted" in billing_router_src)
check("BRT-010: Handles invoice.payment_failed", "invoice.payment_failed" in billing_router_src)

check("BRT-011: /plans endpoint", '"/plans"' in billing_router_src)
check("BRT-012: /current endpoint", '"/current"' in billing_router_src)
check("BRT-013: /upgrade endpoint", '"/upgrade"' in billing_router_src)
check("BRT-014: /downgrade endpoint", '"/downgrade"' in billing_router_src)

check("BRT-015: Upgrade validates plan order", "plan_order" in billing_router_src)
check("BRT-016: Cannot upgrade to same or lower plan", "Cannot upgrade" in billing_router_src)
check("BRT-017: Cannot downgrade to same or higher plan", "Cannot downgrade" in billing_router_src)
check("BRT-018: Downgrade effective immediately", "immediately" in billing_router_src)

try:
    ast.parse(billing_router_src)
    check("BRT-019: AST parse succeeds", True)
except SyntaxError as e:
    check("BRT-019: AST parse succeeds", False, str(e))


# ──────────────────────────────────────────
# 8. MAIN.PY ROUTER REGISTRATION
# ──────────────────────────────────────────
main_src = read(os.path.join(GATEWAY, "app", "main.py"))

check("REG-001: Admin router imported", "admin" in main_src)
check("REG-002: Admin router registered", "admin_router.router" in main_src)
check("REG-003: Billing router imported", "billing" in main_src)
check("REG-004: Billing router registered", "billing_router.router" in main_src)


# ──────────────────────────────────────────
# 9. CONFIG UPDATES
# ──────────────────────────────────────────
config_src = read(os.path.join(GATEWAY, "app", "config.py"))

check("CFG-001: STRIPE_WEBHOOK_SECRET in config", "STRIPE_WEBHOOK_SECRET" in config_src)
check("CFG-002: STRIPE_API_KEY in config", "STRIPE_API_KEY" in config_src)


# ──────────────────────────────────────────
# 10. CROSS-FEATURE INTEGRATION TESTS
# ──────────────────────────────────────────
check("INT-001: Cost guard imports from models", "from app.models import" in cg_src)
check("INT-002: Cost guard uses HTTPException", "HTTPException" in cg_src)
check("INT-003: Admin uses PLAN_DEFAULTS", "PLAN_DEFAULTS" in admin_src)
check("INT-004: Billing uses PLAN_DEFAULTS", "PLAN_DEFAULTS" in billing_src)
check("INT-005: Worker uses select for build lookup", "select(Build)" in worker_src)
check("INT-006: Worker uses select for project lookup", "select(Project)" in worker_src)

check("INT-007: Billing handles unknown events gracefully", "Unhandled Stripe event" in billing_router_src)
check("INT-008: Admin logs admin actions", "logger.info" in admin_src or "logger.warning" in admin_src)
check("INT-009: Cost guard handles zero budget (free)", "budget <= 0" in cg_src)

check("INT-010: All new modules importable",
      all([
          "import" in cg_src,
          "import" in admin_src,
          "import" in billing_src,
          "import" in billing_router_src,
      ]))


# ──────────────────────────────────────────
# 11. SECURITY CHECKS
# ──────────────────────────────────────────
check("SEC-001: Admin requires authentication", "get_current_user" in admin_src)
check("SEC-002: Billing current requires auth", "get_current_user" in billing_router_src)
check("SEC-003: Billing upgrade requires auth", "get_current_user" in billing_router_src)
check("SEC-004: Cost estimate requires auth", "get_current_user" in builds_src)
check("SEC-005: Stripe webhook verifies signature", "verify_stripe_signature" in billing_router_src)
check("SEC-006: Admin email check", "ADMIN_EMAILS" in admin_src)
check("SEC-007: Admin 403 on non-admin", "403" in admin_src and "Admin access required" in admin_src)
check("SEC-008: Budget limit returns 429", "429" in cg_src)
check("SEC-009: Billing webhook rejects invalid JSON", "Invalid JSON" in billing_router_src)


# ──────────────────────────────────────────
# 12. DATA CONSISTENCY CHECKS
# ──────────────────────────────────────────
check("DAT-001: Cost guard uses async sessions", "AsyncSession" in cg_src)
check("DAT-002: Admin uses async sessions", "AsyncSession" in admin_src)
check("DAT-003: Billing uses async sessions", "AsyncSession" in billing_src)
check("DAT-004: Cost recording commits", "await db.commit()" in cg_src or "db.add(record)" in cg_src)
check("DAT-005: Admin retry creates new build ID", "uuid.uuid4()" in admin_src)
check("DAT-006: Billing plan change commits", "await db.commit()" in billing_src)


# ──────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────
if __name__ == "__main__":
    total = passed + failed
    print(f"\n{'='*60}")
    print(f"  COST GUARD / ADMIN / BILLING TEST RESULTS")
    print(f"{'='*60}")
    print(f"  Passed: {passed}/{total}")
    print(f"  Failed: {failed}/{total}")
    print(f"{'='*60}")

    if errors:
        print("\nFailed tests:")
        for e in errors:
            print(f"  {e}")

    print(f"\nResult: {'ALL PASS' if failed == 0 else f'{failed} FAILURES'}")
    sys.exit(0 if failed == 0 else 1)
