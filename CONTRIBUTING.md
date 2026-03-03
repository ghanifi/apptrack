# Contributing to AppTrack

Thank you for your interest in contributing to AppTrack!

## Development Environment

### Prerequisites
- Docker & Docker Compose
- Python 3.12+
- Node.js 20+
- Git

### Setup
```bash
git clone <repo-url> && cd applook
docker compose up -d          # Start infrastructure
cd backend/gateway && pip install -r requirements.txt
cd frontend && npm install
```

## Branch Naming Convention

- `feature/<description>` — New features
- `fix/<description>` — Bug fixes
- `docs/<description>` — Documentation
- `refactor/<description>` — Code refactoring
- `test/<description>` — Adding or updating tests

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add build cost prediction endpoint
fix: resolve race condition in preview container cleanup
docs: update API documentation for deploy endpoints
test: add unit tests for canary deployment router
```

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with tests
3. Ensure all tests pass: `make test`
4. Ensure linting passes: `make lint`
5. Submit a PR with a clear description
6. Request review from at least one maintainer

## Code Style

### Python (Backend)
- Formatter: [Ruff](https://github.com/astral-sh/ruff)
- Line length: 120 characters
- Type hints for function signatures
- Async/await for all I/O operations
- Docstrings in Turkish for internal endpoints

### TypeScript (Frontend)
- ESLint with TypeScript plugin
- Functional components with hooks
- Zustand for global state, React Query for server state
- Tailwind CSS for styling

## Testing

### Backend
```bash
cd backend && pytest --cov
```

### Frontend
```bash
cd frontend && npm run test:run
```

## Important Rules

- **Zero Mock Data**: Never return hardcoded success in production code. If credentials are missing, raise `ConfigurationError`.
- **Test files only**: Mock data is only allowed in test files.
- **Dark Theme**: All UI components use dark theme (bg-gray-900 base).
