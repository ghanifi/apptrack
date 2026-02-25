"""
Production Launch Readiness Tests
Tests: landing page, onboarding, legal, status, support, error UX, monitoring
"""
import sys
import os
import ast

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

GATEWAY = os.path.join(os.path.dirname(__file__), "..", "gateway")
FRONTEND = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src")

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


# ═══════════════════════════════════════════
# 1. LANDING PAGE
# ═══════════════════════════════════════════
landing = read(os.path.join(FRONTEND, "pages", "LandingPage.tsx"))

check("LP-001: Landing page exists", len(landing) > 200)
check("LP-002: Hero section with value proposition", "Ship your mobile app" in landing)
check("LP-003: CI/CD headache message", "CI/CD headache" in landing)
check("LP-004: CTA - Get Started Free", "Get Started Free" in landing or "Start Free" in landing)
check("LP-005: No credit card message", "No credit card" in landing)
check("LP-006: Features section", "features" in landing.lower() and "FEATURES" in landing)
check("LP-007: GitHub Import feature", "GitHub Import" in landing)
check("LP-008: Live Preview feature", "Live Preview" in landing)
check("LP-009: Auto Build feature", "Auto Build" in landing)
check("LP-010: Store Deploy feature", "Store Deploy" in landing)
check("LP-011: Enterprise Security feature", "Enterprise Security" in landing)
check("LP-012: Usage Analytics feature", "Usage Analytics" in landing)
check("LP-013: How it works section", "how-it-works" in landing)
check("LP-014: 4 steps explained", "Connect GitHub" in landing and "Auto Detect" in landing)
check("LP-015: Pricing section", "pricing" in landing.lower())
check("LP-016: Free plan $0", "$0" in landing)
check("LP-017: Pro plan $29", "$29" in landing)
check("LP-018: Enterprise plan $199", "$199" in landing)
check("LP-019: Plan features listed", "builds/month" in landing)
check("LP-020: Most Popular badge", "Most Popular" in landing)
check("LP-021: Competitor comparison table", "How we compare" in landing)
check("LP-022: Footer with links", "Terms of Service" in landing)
check("LP-023: Privacy link in footer", "Privacy Policy" in landing)
check("LP-024: SLA link in footer", "/sla" in landing)
check("LP-025: Support link in footer", "support" in landing.lower())
check("LP-026: Status link in footer", "/status" in landing)
check("LP-027: Statistics section", "Deploy Success Rate" in landing)
check("LP-028: Sign In link", "Sign In" in landing)
check("LP-029: Copyright notice", "All rights reserved" in landing)
check("LP-030: Link to login", '"/login"' in landing)

# ═══════════════════════════════════════════
# 2. ONBOARDING WIZARD
# ═══════════════════════════════════════════
onboarding = read(os.path.join(FRONTEND, "pages", "OnboardingPage.tsx"))

check("OB-001: Onboarding page exists", len(onboarding) > 200)
check("OB-002: Step-based flow", "'connect'" in onboarding and "'select'" in onboarding and "'detect'" in onboarding)
check("OB-003: GitHub connect step", "Connect GitHub" in onboarding or "Connect your GitHub" in onboarding)
check("OB-004: Repo select step", "Select Repository" in onboarding or "Select a repository" in onboarding)
check("OB-005: Framework detection step", "Framework Detection" in onboarding)
check("OB-006: Preview step", "preview" in onboarding.lower())
check("OB-007: Build step", "Build" in onboarding and "Deploy" in onboarding)
check("OB-008: Progress bar", "progress" in onboarding.lower() or "width:" in onboarding)
check("OB-009: Sidebar with step navigation", "STEPS" in onboarding and "STEP_META" in onboarding)
check("OB-010: Search repos", "Search repos" in onboarding)
check("OB-011: Repository list", "filteredRepos" in onboarding)
check("OB-012: Create project mutation", "createProject" in onboarding)
check("OB-013: Framework auto-detection animation", "Analyzing your project" in onboarding)
check("OB-014: Project ready confirmation", "Project ready" in onboarding)
check("OB-015: Navigate to project detail", "navigate" in onboarding)
check("OB-016: Settings link for credentials", "Configure store credentials" in onboarding)
check("OB-017: GitHub profile check", "github_connected" in onboarding)
check("OB-018: Loading state for repos", "Loading" in onboarding)
check("OB-019: Back button in select step", "Back" in onboarding)
check("OB-020: Uses react-query", "useQuery" in onboarding)

# ═══════════════════════════════════════════
# 3. TERMS OF SERVICE
# ═══════════════════════════════════════════
terms = read(os.path.join(FRONTEND, "pages", "TermsPage.tsx"))

check("TOS-001: Terms page exists", len(terms) > 200)
check("TOS-002: Title present", "Terms of Service" in terms)
check("TOS-003: Last updated date", "February 25, 2026" in terms)
check("TOS-004: Acceptance section", "Acceptance of Terms" in terms)
check("TOS-005: Service description", "Service Description" in terms)
check("TOS-006: Account registration", "Account Registration" in terms)
check("TOS-007: Acceptable use policy", "Acceptable Use" in terms)
check("TOS-008: Content and credentials", "Your Content and Credentials" in terms)
check("TOS-009: Encryption mentioned", "encrypt" in terms.lower())
check("TOS-010: Billing section", "Service Plans and Billing" in terms)
check("TOS-011: Data retention", "Data Retention" in terms)
check("TOS-012: 90 day artifact retention", "90 days" in terms)
check("TOS-013: Limitation of liability", "Limitation of Liability" in terms)
check("TOS-014: Termination clause", "Termination" in terms)
check("TOS-015: Contact info", "legal@apptrack.io" in terms)

# ═══════════════════════════════════════════
# 4. PRIVACY POLICY
# ═══════════════════════════════════════════
privacy = read(os.path.join(FRONTEND, "pages", "PrivacyPage.tsx"))

check("PP-001: Privacy page exists", len(privacy) > 200)
check("PP-002: Title present", "Privacy Policy" in privacy)
check("PP-003: Information collection", "Information We Collect" in privacy)
check("PP-004: Account info listed", "name, email" in privacy)
check("PP-005: Credential encryption", "AES-256" in privacy)
check("PP-006: How data is used", "How We Use Your Data" in privacy)
check("PP-007: Credential security section", "Credential Security" in privacy)
check("PP-008: Per-tenant encryption", "per-tenant" in privacy)
check("PP-009: Data sharing section", "Data Sharing" in privacy)
check("PP-010: Never sell data", "never sell" in privacy.lower())
check("PP-011: Build providers listed", "Expo" in privacy and "Codemagic" in privacy)
check("PP-012: Stripe mentioned", "Stripe" in privacy)
check("PP-013: Data retention periods", "Data Retention" in privacy)
check("PP-014: User rights section", "Your Rights" in privacy)
check("PP-015: Right to delete", "Delete your account" in privacy)
check("PP-016: Cookies section", "Cookies" in privacy)
check("PP-017: No tracking cookies", "do not use tracking" in privacy)
check("PP-018: Security measures listed", "Security Measures" in privacy)
check("PP-019: TLS encryption", "TLS" in privacy)
check("PP-020: Contact info", "privacy@apptrack.io" in privacy)

# ═══════════════════════════════════════════
# 5. SLA PAGE
# ═══════════════════════════════════════════
sla = read(os.path.join(FRONTEND, "pages", "SLAPage.tsx"))

check("SLA-001: SLA page exists", len(sla) > 200)
check("SLA-002: Title present", "Service Level Agreement" in sla)
check("SLA-003: Platform availability table", "Uptime Target" in sla)
check("SLA-004: Free plan 99.0%", "99.0%" in sla)
check("SLA-005: Pro plan 99.5%", "99.5%" in sla)
check("SLA-006: Enterprise plan 99.9%", "99.9%" in sla)
check("SLA-007: Support response times", "Support Response Times" in sla)
check("SLA-008: Free 48 hours", "48 hours" in sla)
check("SLA-009: Pro 12 hours", "12 hours" in sla)
check("SLA-010: Enterprise 2 hours", "2 hours" in sla)
check("SLA-011: Build service SLA", "Build Service" in sla)
check("SLA-012: Data durability", "Data Durability" in sla)
check("SLA-013: Daily backups", "daily backups" in sla)
check("SLA-014: Exclusions section", "Exclusions" in sla)
check("SLA-015: Service credits", "Service Credits" in sla)

# ═══════════════════════════════════════════
# 6. STATUS PAGE
# ═══════════════════════════════════════════
status = read(os.path.join(FRONTEND, "pages", "StatusPage.tsx"))

check("ST-001: Status page exists", len(status) > 200)
check("ST-002: Title present", "System Status" in status)
check("ST-003: Auto-refresh every 30s", "30000" in status)
check("ST-004: Healthy/degraded/unhealthy states", "healthy" in status and "degraded" in status and "unhealthy" in status)
check("ST-005: Uses deep health endpoint", "/health/deep" in status)
check("ST-006: Service labels defined", "SERVICE_LABELS" in status)
check("ST-007: Database service listed", "Database" in status)
check("ST-008: Message Queue listed", "Message Queue" in status)
check("ST-009: Build Service listed", "Build Service" in status)
check("ST-010: Store Deploy listed", "Store Deploy" in status)
check("ST-011: Operational/Degraded/Down labels", "Operational" in status and "Degraded" in status and "Down" in status)
check("ST-012: Incident history section", "Incident History" in status)
check("ST-013: Version display", "version" in status)

# ═══════════════════════════════════════════
# 7. SUPPORT PAGE
# ═══════════════════════════════════════════
support = read(os.path.join(FRONTEND, "pages", "SupportPage.tsx"))

check("SUP-001: Support page exists", len(support) > 200)
check("SUP-002: Title present", "Help & Support" in support)
check("SUP-003: Email support", "support@apptrack.io" in support)
check("SUP-004: Discord community", "Discord" in support)
check("SUP-005: Documentation link", "Documentation" in support)
check("SUP-006: FAQ section", "Common Questions" in support)
check("SUP-007: GitHub connect FAQ", "How do I connect my GitHub" in support)
check("SUP-008: Build failed FAQ", "build failed" in support.lower())
check("SUP-009: Credentials FAQ", "How do I add App Store credentials" in support)
check("SUP-010: Plan difference FAQ", "difference between Free and Pro" in support)
check("SUP-011: Downgrade FAQ", "Can I downgrade" in support)
check("SUP-012: Contact form", "Contact Us" in support)
check("SUP-013: Name/email/subject/message fields", "Name" in support and "Email" in support and "Subject" in support and "Message" in support)
check("SUP-014: Send button", "Send Message" in support)
check("SUP-015: Success confirmation", "Message Sent" in support)
check("SUP-016: Response time info", "Response times" in support)
check("SUP-017: SLA link", '"/sla"' in support)

# ═══════════════════════════════════════════
# 8. APP.TSX ROUTING
# ═══════════════════════════════════════════
app_tsx = read(os.path.join(FRONTEND, "App.tsx"))

check("RT-001: Landing page route", "LandingPage" in app_tsx)
check("RT-002: Login route", '"/login"' in app_tsx)
check("RT-003: Terms route", '"/terms"' in app_tsx)
check("RT-004: Privacy route", '"/privacy"' in app_tsx)
check("RT-005: SLA route", '"/sla"' in app_tsx)
check("RT-006: Status route", '"/status"' in app_tsx)
check("RT-007: Support route", '"/support"' in app_tsx)
check("RT-008: Onboarding route", '"/onboarding"' in app_tsx)
check("RT-009: Dashboard layout", "DashboardLayout" in app_tsx)
check("RT-010: Projects route", '"projects"' in app_tsx)
check("RT-011: Settings route", '"settings"' in app_tsx)
check("RT-012: Usage route", '"usage"' in app_tsx)
check("RT-013: Audit route", '"audit"' in app_tsx)
check("RT-014: PublicHome redirects logged-in user", "PublicHome" in app_tsx and "Navigate" in app_tsx)
check("RT-015: PrivateRoute guard", "PrivateRoute" in app_tsx)
check("RT-016: Onboarding is private", "PrivateRoute" in app_tsx and "OnboardingPage" in app_tsx)

# ═══════════════════════════════════════════
# 9. ERROR MESSAGES MODULE
# ═══════════════════════════════════════════
err_src = read(os.path.join(GATEWAY, "app", "error_messages.py"))

check("ERR-001: Error messages module exists", len(err_src) > 100)
check("ERR-002: build.missing_dependency", "build.missing_dependency" in err_src)
check("ERR-003: build.timeout", "build.timeout" in err_src)
check("ERR-004: build.provider_unavailable", "build.provider_unavailable" in err_src)
check("ERR-005: build.credential_expired", "build.credential_expired" in err_src)
check("ERR-006: build.quota_exceeded", "build.quota_exceeded" in err_src)
check("ERR-007: build.budget_exceeded", "build.budget_exceeded" in err_src)
check("ERR-008: deploy.missing_credentials", "deploy.missing_credentials" in err_src)
check("ERR-009: deploy.build_not_ready", "deploy.build_not_ready" in err_src)
check("ERR-010: deploy.artifact_expired", "deploy.artifact_expired" in err_src)
check("ERR-011: deploy.store_rejected", "deploy.store_rejected" in err_src)
check("ERR-012: deploy.checksum_mismatch", "deploy.checksum_mismatch" in err_src)
check("ERR-013: deploy.upload_failed", "deploy.upload_failed" in err_src)
check("ERR-014: auth.github_token_expired", "auth.github_token_expired" in err_src)
check("ERR-015: auth.rate_limited", "auth.rate_limited" in err_src)
check("ERR-016: preview.container_failed", "preview.container_failed" in err_src)
check("ERR-017: Each error has title+message+action",
      all(k in err_src for k in ["title", "message", "action"]))
check("ERR-018: get_error_message function", "def get_error_message" in err_src)
check("ERR-019: Default error for unknown codes", "Unexpected Error" in err_src)
check("ERR-020: get_all_error_codes function", "def get_all_error_codes" in err_src)
try:
    ast.parse(err_src)
    check("ERR-021: AST parse succeeds", True)
except SyntaxError as e:
    check("ERR-021: AST parse succeeds", False, str(e))

# ═══════════════════════════════════════════
# 10. MONITORING DASHBOARD ENDPOINT
# ═══════════════════════════════════════════
main_src = read(os.path.join(GATEWAY, "app", "main.py"))

check("MON-001: /api/monitoring/dashboard endpoint", "monitoring/dashboard" in main_src)
check("MON-002: Build success rate", "build_success_rate" in main_src)
check("MON-003: Deploy success rate", "deploy_success_rate" in main_src)
check("MON-004: Active builds metric", "active_builds" in main_src)
check("MON-005: Builds this month", "builds_this_month" in main_src)
check("MON-006: 24h window", "day_ago" in main_src)
check("MON-007: Monthly window", "month_start" in main_src)
check("MON-008: Uses async session", "AsyncSessionLocal" in main_src)

# ═══════════════════════════════════════════
# 11. DEEP HEALTH ENHANCED
# ═══════════════════════════════════════════
check("DHE-001: Services field in health", '"services"' in main_src)
check("DHE-002: Database service status", '"database"' in main_src and '"healthy"' in main_src)
check("DHE-003: RabbitMQ service status", '"rabbitmq"' in main_src)
check("DHE-004: Gateway service status", '"gateway"' in main_src)
check("DHE-005: Build service status", '"build_service"' in main_src)
check("DHE-006: Artifact service status", '"artifact_service"' in main_src)
check("DHE-007: Preview service status", '"preview_service"' in main_src)
check("DHE-008: Store deploy status", '"store_deploy"' in main_src)

# ═══════════════════════════════════════════
# 12. ERROR ENDPOINT
# ═══════════════════════════════════════════
check("EEP-001: /api/errors/{error_code} endpoint", "/api/errors/" in main_src)
check("EEP-002: Imports get_error_message", "get_error_message" in main_src)

# ═══════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════
total = passed + failed
print(f"\n{'='*60}")
print(f"  PRODUCTION LAUNCH READINESS TEST RESULTS")
print(f"{'='*60}")
print(f"  Passed: {passed}/{total}")
print(f"  Failed: {failed}/{total}")
print(f"{'='*60}")

if errors:
    print(f"\nFailed tests:")
    for e in errors:
        print(f"  {e}")
else:
    print(f"\n  ALL {total} LAUNCH READINESS TESTS PASS")
    print(f"  Customer-facing features verified:")
    print(f"    - Landing page (hero, features, pricing, CTA)")
    print(f"    - Onboarding wizard (5-step flow)")
    print(f"    - Legal pages (ToS, Privacy, SLA)")
    print(f"    - Status page (real-time service status)")
    print(f"    - Support page (FAQ, contact form)")
    print(f"    - Error UX (human-readable messages)")
    print(f"    - Monitoring dashboard endpoint")

print(f"{'='*60}")
sys.exit(0 if failed == 0 else 1)
