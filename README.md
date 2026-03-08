# AppTrack

Mobile app CI/CD and Store management platform. Build, test, deploy and manage your mobile applications from a single dashboard.

## Supported Frameworks & Languages

AppTrack supports **9 mobile/web frameworks** across **6 programming languages**, covering the entire spectrum from native to hybrid to progressive web apps:

### Native Frameworks

| Framework | Language | Platforms | Build Provider | Workflow |
|-----------|----------|-----------|----------------|----------|
| **Swift** | Swift | iOS | GitHub Actions (Self-Hosted Mac Mini M4) | `build-ios.yml` |
| **Kotlin** | Kotlin | Android | GitHub Actions | `build-android.yml` |

### Cross-Platform Frameworks

| Framework | Language | Platforms | Build Provider | Workflow |
|-----------|----------|-----------|----------------|----------|
| **React Native** | JavaScript / TypeScript | iOS, Android | EAS Build | Expo managed |
| **Flutter** | Dart | iOS, Android | Codemagic | Codemagic managed |
| **Expo** | JavaScript / TypeScript | iOS, Android | EAS Build | Expo managed |

### Hybrid Frameworks (Capacitor Ecosystem)

| Framework | Language | Platforms | Build Provider | Workflow |
|-----------|----------|-----------|----------------|----------|
| **Capacitor** | JavaScript / TypeScript | iOS, Android | GitHub Actions | `build-capacitor-ios.yml`, `build-capacitor-android.yml` |
| **Ionic** | JavaScript / TypeScript | iOS, Android | GitHub Actions | Capacitor workflows shared |
| **Cordova** | JavaScript / TypeScript | iOS, Android | GitHub Actions | Capacitor workflows shared |

### Progressive Web Apps

| Framework | Language | Platforms | Build Provider | Workflow |
|-----------|----------|-----------|----------------|----------|
| **PWA** | JavaScript / TypeScript | Android (TWA), Web | GitHub Actions | `build-pwa-android.yml`, `build-pwa.yml` |

### Language Summary

| Language | Frameworks | Detection Method |
|----------|-----------|-----------------|
| **Swift** | Swift (native iOS) | `.swift` files, `Package.swift`, `*.xcodeproj` |
| **Kotlin** | Kotlin (native Android) | `build.gradle.kts`, `*.kt` files |
| **Dart** | Flutter | `pubspec.yaml` with flutter dependency |
| **JavaScript / TypeScript** | React Native, Expo, Capacitor, Ionic, Cordova, PWA | `package.json` + framework-specific configs |

> Framework detection is fully automatic. When you connect a GitHub repository, AppTrack analyzes the project structure and identifies the correct framework, language, and available build targets.

---

## End-to-End Publishing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          AppTrack — Publishing Pipeline                          │
└─────────────────────────────────────────────────────────────────────────────────┘

  PHASE 1: PROJECT SETUP
  ─────────────────────────────────────────────────────────────────────────────

  ┌──────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────────┐
  │  GitHub   │────▶│  Repo Sync   │────▶│  Framework    │────▶│  Project     │
  │  OAuth    │     │  Service     │     │  Detection    │     │  Created     │
  │  Connect  │     │  (8003)      │     │  (8004)       │     │  Ready       │
  └──────────┘     └──────────────┘     └───────────────┘     └──────┬───────┘
                    Clone & analyze      Auto-detect:                  │
                    repository           9 frameworks                  │
                                         6 languages                   │
                                                                       ▼
  PHASE 2: CREDENTIAL MANAGEMENT
  ─────────────────────────────────────────────────────────────────────────────

  ┌────────────────────────────────────────────────────────────────────────────┐
  │                         SECURE CREDENTIAL VAULT                            │
  │                    Fernet Encryption (AES-128-CBC)                          │
  │                    Zero plaintext storage + Key rotation                    │
  │                                                                            │
  │  ┌─────────────┐ ┌─────────────┐ ┌──────────────┐ ┌────────────────────┐ │
  │  │ Google Play  │ │ App Store   │ │ GitHub       │ │ Netlify / Vercel   │ │
  │  │ Service Key  │ │ API Key +   │ │ Actions      │ │ Deploy Token       │ │
  │  │ (JSON)       │ │ P8 Key      │ │ PAT Token    │ │                    │ │
  │  └─────────────┘ └─────────────┘ └──────────────┘ └────────────────────┘ │
  │                                                                            │
  │  ┌──────────────────────────────┐ ┌────────────────────────────────────┐  │
  │  │ iOS Signing                  │ │ Android Signing                    │  │
  │  │ P12 Certificate (base64)     │ │ Keystore (base64)                  │  │
  │  │ Certificate Password         │ │ Keystore Password                  │  │
  │  │ Provisioning Profile (base64)│ │ Key Alias + Key Password           │  │
  │  └──────────────────────────────┘ └────────────────────────────────────┘  │
  └────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
  PHASE 3: BUILD
  ─────────────────────────────────────────────────────────────────────────────

  ┌────────────────────────────────────────────────────────────────────────────┐
  │                           BUILD PIPELINE                                    │
  │                                                                            │
  │   ┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐ │
  │   │ Trigger   │───▶│ Provider     │───▶│ Build        │───▶│ Artifact   │ │
  │   │ Build     │    │ Selection    │    │ Execution    │    │ Storage    │ │
  │   │ (API)     │    │ (WORKFLOW_MAP│    │              │    │ (MinIO)    │ │
  │   └──────────┘    └──────────────┘    └──────────────┘    └────────────┘ │
  │                                                                            │
  │   Build Providers:                                                         │
  │   ┌──────────────────────────────────────────────────────────────────────┐ │
  │   │                                                                      │ │
  │   │  EAS Build ──────── React Native, Expo                               │ │
  │   │  Codemagic ──────── Flutter                                          │ │
  │   │  GitHub Actions ─── Swift, Kotlin, Capacitor, Ionic, Cordova, PWA    │ │
  │   │  Self-Hosted ────── iOS builds via Mac Mini M4 (Apple Silicon)       │ │
  │   │                                                                      │ │
  │   └──────────────────────────────────────────────────────────────────────┘ │
  │                                                                            │
  │   Workflow Routing (WORKFLOW_MAP):                                          │
  │   ┌────────────────┬──────────────────────────┬────────────────────────┐  │
  │   │ Framework       │ Android                  │ iOS                    │  │
  │   ├────────────────┼──────────────────────────┼────────────────────────┤  │
  │   │ Capacitor       │ build-capacitor-android   │ build-capacitor-ios    │  │
  │   │ Ionic           │ build-capacitor-android   │ build-capacitor-ios    │  │
  │   │ Cordova         │ build-capacitor-android   │ build-capacitor-ios    │  │
  │   │ PWA             │ build-pwa-android (TWA)   │ —                      │  │
  │   │ PWA (Web)       │ build-pwa.yml             │ —                      │  │
  │   │ Swift           │ —                         │ build-ios              │  │
  │   │ Kotlin          │ build-android             │ —                      │  │
  │   └────────────────┴──────────────────────────┴────────────────────────┘  │
  │                                                                            │
  │   Output Artifacts:                                                        │
  │   ├── Android: Signed APK / AAB                                            │
  │   ├── iOS: Signed IPA (via Mac Mini M4 self-hosted runner)                 │
  │   ├── Web: Static build (dist.zip)                                         │
  │   └── PWA Android: TWA APK (via Bubblewrap)                                │
  └────────────────────────────────────────────────────────────────────────────┘
                                         │
                               ┌─────────┴─────────┐
                               ▼                     ▼
                     ┌──────────────┐      ┌──────────────────┐
                     │  Build OK    │      │  Build Failed    │
                     └──────┬───────┘      └────────┬─────────┘
                            │                       │
                            │                ┌──────▼─────────┐
                            │                │ AI Diagnosis    │
                            │                │ 30 error        │
                            │                │ patterns        │
                            │                │ + fix suggest.  │
                            │                └────────────────┘
                            ▼
  PHASE 4: DEPLOYMENT
  ─────────────────────────────────────────────────────────────────────────────

  ┌────────────────────────────────────────────────────────────────────────────┐
  │                           DEPLOY TARGETS                                    │
  │                                                                            │
  │   ┌────────────────┐  ┌────────────────┐  ┌─────────────────────────────┐ │
  │   │  Google Play    │  │  App Store     │  │  Web (Netlify / Vercel)     │ │
  │   │  Console API    │  │  Connect API   │  │  Static Hosting             │ │
  │   │                 │  │                │  │                             │ │
  │   │  • Upload APK   │  │  • Upload IPA  │  │  • Upload dist.zip         │ │
  │   │  • Select track  │  │  • TestFlight  │  │  • Auto SSL + CDN         │ │
  │   │  • Rollout %    │  │  • Submit for  │  │  • Custom domain           │ │
  │   │  • Canary deploy│  │    review      │  │  • Preview URL             │ │
  │   └────────────────┘  └────────────────┘  └─────────────────────────────┘ │
  │                                                                            │
  │   Deploy Tracks:                                                           │
  │   ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────────┐   │
  │   │ Internal  │───▶│   Beta    │───▶│  Staging  │───▶│  Production   │   │
  │   │ Testing   │    │TestFlight │    │  %10→%50  │    │  %100 Live    │   │
  │   └───────────┘    └───────────┘    └───────────┘    └───────────────┘   │
  │                                                                            │
  │   Canary Deployment:                                                       │
  │   %10 → %25 → %50 → %100 (auto-rollback on error rate spike)             │
  └────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
  PHASE 5: POST-DEPLOY & OTA
  ─────────────────────────────────────────────────────────────────────────────

  ┌────────────────────────────────────────────────────────────────────────────┐
  │                                                                            │
  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
  │   │ Audit Log    │  │ KPI Metrics  │  │ OTA Updates  │  │ Webhooks    │ │
  │   │ (Immutable)  │  │ (Prometheus) │  │              │  │             │ │
  │   │              │  │              │  │ Channels:    │  │ Slack       │ │
  │   │ SOC2-ready   │  │ Build time   │  │ • production │  │ Discord     │ │
  │   │ Hash chain   │  │ Success rate │  │ • staging    │  │ Email       │ │
  │   │ Tamper-proof │  │ Cost/build   │  │ • beta       │  │ Custom URL  │ │
  │   └──────────────┘  └──────────────┘  │              │  └─────────────┘ │
  │                                        │ Features:    │                   │
  │                                        │ • Hot-fix JS │                   │
  │                                        │ • No rebuild │                   │
  │                                        │ • Rollback   │                   │
  │                                        │ • Runtime    │                   │
  │                                        │   version    │                   │
  │                                        │   matching   │                   │
  │                                        └──────────────┘                   │
  └────────────────────────────────────────────────────────────────────────────┘
```

---

## OTA (Over-The-Air) Live Updates

AppTrack provides built-in OTA update support for Capacitor, Ionic, and Cordova applications. Ship JavaScript/HTML/CSS changes instantly without rebuilding the native binary or going through app store review.

```
  Developer                  AppTrack                    Mobile App
  ─────────                  ────────                    ──────────
      │                          │                            │
      │  npm run build           │                            │
      │  Upload dist.zip         │                            │
      │─────────────────────────▶│                            │
      │                          │  Store bundle              │
      │                          │  in MinIO                  │
      │                          │                            │
      │                          │         GET /api/ota/check │
      │                          │◀───────────────────────────│
      │                          │                            │
      │                          │  { available: true,        │
      │                          │    bundle_url: "...",      │
      │                          │    runtime_version: "1.2"} │
      │                          │───────────────────────────▶│
      │                          │                            │
      │                          │                  Download  │
      │                          │                  & Apply   │
      │                          │                  Bundle    │
      │                          │                            │
      │  Rollback (if needed)    │                            │
      │─────────────────────────▶│                            │
      │                          │  Re-publish                │
      │                          │  previous version          │
      │                          │───────────────────────────▶│
```

**Channels**: `production`, `staging`, `beta` — target different user groups.

**Public Endpoint**: `GET /api/ota/check/{project_id}` requires no authentication, so mobile apps can check for updates directly.

---

## iOS Build — Self-Hosted Mac Mini M4

For iOS builds, AppTrack uses a self-hosted GitHub Actions runner on Apple Silicon (Mac Mini M4) with zero cloud cost:

```
  GitHub Actions                    Mac Mini M4 (Self-Hosted)
  ──────────────                    ─────────────────────────
       │                                    │
       │  workflow_dispatch                 │
       │  build-capacitor-ios.yml           │
       │───────────────────────────────────▶│
       │                                    │  npm ci
       │                                    │  npm run build
       │                                    │  npx cap sync ios
       │                                    │  pod install
       │                                    │
       │                                    │  Create temp keychain
       │                                    │  Import P12 certificate
       │                                    │  Install provisioning profile
       │                                    │
       │                                    │  xcodebuild archive
       │                                    │  xcodebuild -exportArchive
       │                                    │
       │                  Upload IPA        │
       │◀───────────────────────────────────│
       │                                    │  Cleanup keychain
       │  Webhook callback                  │
       │  build.finished                    │
       │                                    │
```

**Runner Labels**: `self-hosted, macos-arm64, apptrack-ios`

**Cost**: $0/month (hardware one-time, ~$5/month electricity)

---

## Features

- **Multi-Framework Support**: React Native, Flutter, Expo, Swift, Kotlin, Capacitor, Ionic, Cordova, PWA
- **CI/CD Pipeline**: Automated builds via EAS, Codemagic, GitHub Actions, Self-Hosted Runners
- **Store Deployment**: Google Play, App Store, and Web (Netlify/Vercel) publishing
- **OTA Live Updates**: Over-the-air JavaScript bundle updates with channel-based rollout
- **Live Preview**: Real-time app preview with device emulation
- **RBAC & SSO**: Role-based access control with OIDC/SAML support
- **Organization Management**: Team collaboration with member roles
- **AI-Powered Insights**: Build failure diagnosis, cost prediction, provider recommendations
- **Audit & Compliance**: Immutable audit logs, deploy policies, compliance checks
- **Canary Deployments**: Gradual rollout with automatic rollback
- **Feature Flags**: Runtime feature toggles per environment
- **Store Metadata**: Multi-locale store listing management with icon/screenshot upload
- **iOS Signing Management**: P12 certificate + provisioning profile management via UI
- **Android Signing**: Keystore upload and signing key forwarding to build workflows
- **Cost Guard**: Build cost estimation and budget enforcement per provider

## Architecture

```
                              ┌─────────────────┐
                              │   Client (SPA)   │
                              │  React + Vite    │
                              │  Port: 3000      │
                              └────────┬─────────┘
                                       │ HTTPS
                              ┌────────▼─────────┐
                              │   Nginx Ingress   │
                              │   TLS + Headers   │
                              │   Rate Limiting   │
                              └────────┬─────────┘
                                       │
                              ┌────────▼─────────┐
                              │   API Gateway     │
                              │   FastAPI (8000)  │
                              │   WAF + Auth +    │
                              │   RBAC + Routing  │
                              └────────┬─────────┘
                                       │
                 ┌─────────────────────┼─────────────────────┐
                 │                     │                     │
        ┌────────▼──────┐    ┌────────▼──────┐    ┌────────▼──────┐
        │  Auth (8001)  │    │ Build (8006)  │    │ Deploy(8008)  │
        │  OAuth + JWT  │    │ CI/CD Orch.   │    │ Store Publish │
        └───────────────┘    └───────┬───────┘    └───────────────┘
                                     │
            ┌────────────────────────┼────────────────────────┐
            │                        │                        │
   ┌────────▼──────┐       ┌────────▼──────┐       ┌────────▼──────┐
   │ RepoSync(8003)│       │Artifact(8007) │       │Preview (8005) │
   │ Git Clone     │       │ MinIO S3      │       │ Live Preview  │
   └───────────────┘       └───────────────┘       └───────────────┘

        ┌───────────────────────────────────────────────────┐
        │                 Infrastructure                     │
        │                                                    │
        │  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
        │  │PostgreSQL│  │ RabbitMQ │  │   MinIO (S3)   │  │
        │  │  16      │  │  3.13    │  │   Storage      │  │
        │  └──────────┘  └──────────┘  └────────────────┘  │
        │                                                    │
        │  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
        │  │Prometheus│  │ Grafana  │  │   Redis        │  │
        │  │Metrics   │  │Dashboard │  │   Rate Limit   │  │
        │  └──────────┘  └──────────┘  └────────────────┘  │
        └───────────────────────────────────────────────────┘
```

| Service | Port | Description |
|---------|------|-------------|
| Gateway API | 8000 | Main API gateway (FastAPI) |
| Auth Service | 8001 | Authentication & OAuth |
| Project Service | 8002 | Project CRUD & management |
| Repo Sync | 8003 | Git repository synchronization |
| Framework Detection | 8004 | Auto-detect project framework |
| Preview | 8005 | Live app preview & screenshots |
| Build Service | 8006 | CI/CD build orchestration |
| Artifact Service | 8007 | Build artifact storage (MinIO) |
| Store Deploy | 8008 | Google Play / App Store / Web publishing |
| Frontend | 3000 | React SPA (Vite + Tailwind) |

### Infrastructure
- **Database**: PostgreSQL 16
- **Message Queue**: RabbitMQ 3.13
- **Object Storage**: MinIO (S3-compatible)
- **Monitoring**: Prometheus + Grafana (via `--profile monitoring`)
- **Container Orchestration**: Kubernetes + Helm

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 20+ (for frontend development)
- Python 3.12+ (for backend development)

### Run with Docker Compose
```bash
# Clone the repository
git clone <repo-url> && cd apptrack

# Copy environment file
cp env.example .env

# Start all services
docker compose up -d

# Access the application
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/api/docs
# RabbitMQ:  http://localhost:15672
# MinIO:     http://localhost:9001

# Start with monitoring (Prometheus + Grafana)
docker compose --profile monitoring up -d
# Grafana: http://localhost:3001
```

### Development Setup

#### Backend
```bash
cd backend/gateway
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Testing

```bash
# Backend tests
cd backend && python -m pytest --cov --cov-report=term-missing -q

# Frontend tests
cd frontend && npm run test:run

# All tests via Makefile
make test
```

## API Documentation

Interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

## Environment Variables

See `env.example` at the project root for all configuration options.

Key variables:
| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://apptrack:apptrack@postgres:5432/apptrack` |
| `SECRET_KEY` | JWT signing key | (required) |
| `FERNET_SALT` | Credential encryption salt | (required) |
| `GITHUB_CLIENT_ID` | GitHub OAuth app ID | (optional) |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth app secret | (optional) |
| `RABBITMQ_USER` | RabbitMQ username | `apptrack` |
| `RABBITMQ_PASS` | RabbitMQ password | `apptrack_secret` |
| `MINIO_ROOT_USER` | MinIO access key | `minioadmin` |
| `MINIO_ROOT_PASSWORD` | MinIO secret key | `minioadmin` |
| `APPETIZE_API_TOKEN` | Appetize.io API token for native preview | (optional) |
| `ENABLE_LIVE_PREVIEW` | Enable live preview containers | `true` |

## Deployment

### Kubernetes (Helm)
```bash
helm install apptrack k8s/helm/apptrack -f k8s/helm/apptrack/values.yaml
```

Infrastructure manifests are available under `k8s/base/` (gateway, services, networking) and `infra/k8s/` (monitoring, TLS, PDB, HPA, backups, secrets).

### Database Migrations
```bash
cd backend/gateway
alembic upgrade head
```

### Docker Build (Production)
All services use multi-stage Docker builds with non-root users. The frontend builds to a static Nginx container.

```bash
docker compose build --parallel
```

## Project Structure

```
apptrack/
├── backend/
│   ├── gateway/              # FastAPI API gateway (port 8000)
│   │   ├── app/
│   │   │   ├── main.py       # Application entry point
│   │   │   ├── routers/      # 28+ API routers
│   │   │   ├── models.py     # SQLAlchemy models
│   │   │   └── ...
│   │   ├── alembic.ini       # Database migration config
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── services/
│   │   ├── auth/             # Authentication service (8001)
│   │   ├── project/          # Project management (8002)
│   │   ├── repo-sync/        # Git sync (8003)
│   │   ├── framework-detection/  # Framework detection (8004)
│   │   ├── preview/          # Live preview (8005)
│   │   ├── build/            # Build orchestration (8006)
│   │   ├── artifact/         # Artifact storage (8007)
│   │   └── store-deploy/     # Store publishing (8008)
│   ├── pyproject.toml        # Ruff config & project metadata
│   └── requirements-test.txt
├── frontend/                 # React SPA
│   ├── src/
│   ├── package.json
│   ├── vite.config.ts
│   ├── Dockerfile
│   └── .env.example
├── infra/
│   ├── nginx/                # Nginx reverse proxy config
│   ├── prometheus/           # Prometheus config & alert rules
│   ├── grafana/              # Grafana dashboards & datasources
│   ├── postgres/             # Database init scripts
│   └── k8s/                  # K8s infra (monitoring, TLS, PDB, HPA, backups)
├── k8s/
│   ├── base/                 # Base K8s manifests
│   └── helm/apptrack/        # Helm chart
├── scripts/
│   ├── setup-mac-runner.sh   # Mac Mini M4 self-hosted runner setup
│   └── verify-mac-runner.sh  # Runner health check
├── docs/
│   ├── workflow-templates/   # GitHub Actions workflow templates
│   │   ├── build-capacitor-android.yml
│   │   ├── build-capacitor-ios.yml
│   │   └── build-pwa-android.yml
│   ├── self-hosted-ios-runner.md
│   └── capacitor-ota-plugin.md
├── .github/workflows/        # CI/CD pipelines (ci.yml, cd.yml)
├── .pre-commit-config.yaml   # Pre-commit hooks (Ruff, trailing whitespace, YAML/JSON)
├── docker-compose.yml
├── env.example
└── Makefile
```

## License

MIT License -- see [LICENSE](LICENSE) for details.
