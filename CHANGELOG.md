# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-03

### Added
- Pydantic response models for all major API routers (projects, builds, organizations, auth)
- CONTRIBUTING.md with development guidelines and code style rules
- CHANGELOG.md with full version history
- MIT LICENSE file
- Makefile with dev, test, lint, build, migrate, and clean targets
- Comprehensive OpenAPI documentation with response_model on all endpoints

### Changed
- Upgraded endpoint decorators with explicit response_model annotations
- Improved type safety across all router response schemas

## [0.9.0] - 2026-02-28

### Added
- Organization management (create org, invite members, assign roles, assign projects)
- SSO/OIDC integration for enterprise authentication
- OTA updates support (EAS + custom bundle delivery)
- AI-powered build diagnosis endpoint
- AI-powered cost prediction endpoint
- AI-powered provider recommendation endpoint
- Support ticket system
- Kubernetes hardening: ServiceMonitor, TLS Ingress, PodDisruptionBudget, HPA, backup CronJob, security headers
- Test infrastructure: pytest (backend) + Vitest (frontend), 150+ test functions
- OpenAPI docstrings for 126+ endpoints with Turkish descriptions
- Pre-commit hooks configuration (Ruff, trailing whitespace, YAML/JSON validation)
- CI/CD GitHub Actions workflows (ci.yml, cd.yml)
- Frontend: ErrorBoundary, LoadingSpinner, NotFoundPage components
- Frontend: Zod schemas for runtime validation
- Frontend: environment variable management (env.ts)
- Frontend: Vitest configuration and test setup

### Changed
- Removed all simulation/mock responses from production code (Zero Mock Data rule)
- Connected RBAC and deploy policies to real database queries
- Standardized health check endpoints across all services
- Fixed silent exception handling with proper logging
- Implemented graceful shutdown for all microservices

### Fixed
- Silent exception swallowing in background workers
- Graceful shutdown signal handling in all services

## [0.8.0] - 2026-02-20

### Added
- WAF (Web Application Firewall) middleware with SQL injection and XSS protection
- Anomaly detection for API request patterns
- Credential validation endpoint with provider-specific checks
- Deploy simulator for pre-deploy validation
- Canary deployment support with gradual rollout and automatic rollback
- Compliance checker engine for store guideline validation
- Review simulator for app store approval prediction
- KPI metrics dashboard with Prometheus integration
- Confetti celebration animation on successful deploys
- Deploy error guide with categorized troubleshooting
- Kubernetes base manifests (gateway, services, networking)
- Helm chart for production deployment
- Abuse guard for build spam prevention
- Cost guard with budget limit enforcement
- Build idempotency (duplicate build detection)

### Changed
- Enhanced security middleware stack (WAF + rate limiting + abuse guard)

## [0.7.0] - 2026-02-14

### Added
- Store metadata management panel with multi-locale support
- Phone mockup preview for store listings
- Icon and screenshot upload with drag-and-drop reorder
- Store metadata form (title, short description, full description per locale)
- Store readiness checklist with validation
- Store listing preview component
- Landing page conversion optimization: 3 value propositions, pain points section, testimonials
- Stronger CTAs on landing page
- Visual proof mockups (3-step UI demonstration)
- Trust bar with risk reducers

## [0.6.0] - 2026-02-07

### Added
- Store enterprise upgrade with 15 locale support (EN, TR, DE, FR, ES, IT, PT-BR, JA, KO, ZH-CN, ZH-TW, AR, NL, RU, HI)
- Compliance check engine for store guidelines
- Pre-publish review simulation
- Icon validation (dimensions, format, transparency)
- Screenshot reorder with drag-and-drop
- RBAC system (Admin, Lead, Developer, Viewer roles)
- Audit logging (SOC2 compliant, immutable hash chain)
- Feature flags with per-environment toggles
- Billing and usage tracking
- Webhook management for GitHub push events
- Backup and restore endpoints
- Deploy policies (approval workflows, environment restrictions)
- Immutable audit log with hash chain verification
- Credential management with Fernet encryption and key rotation
- Device fingerprinting for token security

### Changed
- Migrated to async SQLAlchemy for all database operations
- Enhanced GitHub OAuth with CSRF state protection
