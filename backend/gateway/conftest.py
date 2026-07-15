"""
AppTrack — Shared test fixtures.

Provides async DB session, mock RabbitMQ channel, authenticated test client,
and common test helpers used across all test files.
"""
import os
import sys
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# ---------------------------------------------------------------------------
# PATH SETUP — ensure gateway app is importable
# ---------------------------------------------------------------------------
gateway_path = os.path.join(os.path.dirname(__file__), "gateway")
sys.path.insert(0, gateway_path)

# Set required env vars before any import
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars!!")
os.environ.setdefault("FERNET_SALT", "test-salt-for-testing-only")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("ENVIRONMENT", "testing")


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db():
    """Mock async database session with common query patterns."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.execute = AsyncMock()
    session.add = AsyncMock()
    session.delete = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_rabbitmq():
    """Mock RabbitMQ channel for event publishing."""
    channel = AsyncMock()
    channel.default_exchange = AsyncMock()
    channel.default_exchange.publish = AsyncMock()
    return channel


@pytest.fixture
def test_user():
    """Standard test user dict matching get_current_user output."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "email": "test@apptrack.io",
        "name": "Test User",
    }


@pytest.fixture
def admin_user():
    """Admin test user."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "email": "admin@apptrack.io",
        "name": "Admin User",
        "is_admin": True,
    }


@pytest.fixture
def auth_headers(test_user):
    """Generate JWT auth headers for test user."""
    from jose import jwt
    token = jwt.encode(
        {"sub": test_user["id"], "email": test_user["email"], "name": test_user["name"], "type": "access"},
        os.environ["SECRET_KEY"],
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(admin_user):
    """Generate JWT auth headers for admin user."""
    from jose import jwt
    token = jwt.encode(
        {"sub": admin_user["id"], "email": admin_user["email"], "name": admin_user["name"], "type": "access"},
        os.environ["SECRET_KEY"],
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_project(test_user):
    """Sample project data."""
    return {
        "id": "660e8400-e29b-41d4-a716-446655440000",
        "owner_id": test_user["id"],
        "name": "test-app",
        "repo_url": "https://github.com/test/test-app",
        "branch": "main",
        "framework": "react-native",
        "status": "active",
    }


@pytest.fixture
def sample_build(sample_project):
    """Sample build data."""
    return {
        "id": "770e8400-e29b-41d4-a716-446655440000",
        "project_id": sample_project["id"],
        "platform": "android",
        "provider": "eas",
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """slowapi bellek-ici sayaclarini sifirla — testler arasi rate limit sizmasini onler."""
    try:
        from app.limiter import limiter
        limiter.reset()
    except Exception:
        pass
    yield
