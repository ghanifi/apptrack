# AppTrack

Mobile app CI/CD and Store management platform. Build, test, deploy and manage your mobile applications from a single dashboard.

## Features

- **Multi-Framework Support**: React Native, Flutter, Expo, Swift, Kotlin
- **CI/CD Pipeline**: Automated builds via EAS, Codemagic, GitHub Actions
- **Store Deployment**: Google Play and App Store publishing
- **Live Preview**: Real-time app preview with device emulation
- **RBAC & SSO**: Role-based access control with OIDC/SAML support
- **Organization Management**: Team collaboration with member roles
- **AI-Powered Insights**: Build failure diagnosis, cost prediction, provider recommendations
- **Audit & Compliance**: Immutable audit logs, deploy policies, compliance checks
- **Canary Deployments**: Gradual rollout with automatic rollback
- **Feature Flags**: Runtime feature toggles per environment
- **OTA Updates**: Over-the-air updates via EAS and custom bundles
- **Store Metadata**: Multi-locale store listing management with icon/screenshot upload

## Architecture

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
| Store Deploy | 8008 | Google Play / App Store publishing |
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
git clone <repo-url> && cd applook

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

The API gateway exposes 31 tagged endpoint groups including auth, projects, builds, deployments, credentials, preview, webhooks, audit, feature-flags, usage, OTA updates, store metadata, RBAC, billing, canary deployments, compliance, and AI-powered diagnosis/prediction endpoints.

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
applook/
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
├── .github/workflows/        # CI/CD pipelines (ci.yml, cd.yml)
├── .pre-commit-config.yaml   # Pre-commit hooks (Ruff, trailing whitespace, YAML/JSON)
├── docker-compose.yml
├── env.example
└── Makefile
```

## License

MIT License -- see [LICENSE](LICENSE) for details.
