"""
AppTrack -- Organizations Router Tests
========================================
Tests for: create_org, list_orgs, invite_member, remove_member,
           update_role, assign_project

Router: backend/gateway/app/routers/organizations.py
Prefix: /api/organizations (router prefix="/organizations", main.py prefix="/api")
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, Request

from app.routers.organizations import router
from app.dependencies import get_current_user
from app.database import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_app(user_override: dict, db_override: AsyncMock) -> FastAPI:
    """Build a minimal FastAPI app with the organizations router."""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user_override
    app.dependency_overrides[get_db] = lambda: db_override

    # Disable rate limiter for tests
    from app.limiter import limiter
    app.state.limiter = limiter

    @app.middleware("http")
    async def add_client_ip(request: Request, call_next):
        request.state.current_user_id = user_override["id"]
        return await call_next(request)

    return app


def _make_org(org_id="org-001", name="TestOrg", slug="test-org", plan="free"):
    org = MagicMock()
    org.id = org_id
    org.name = name
    org.slug = slug
    org.plan = plan
    org.owner_id = "550e8400-e29b-41d4-a716-446655440000"
    org.max_members = 5
    org.created_at = datetime(2025, 6, 1)
    org.updated_at = datetime(2025, 6, 1)
    return org


def _make_member(member_id="mem-001", org_id="org-001", user_id="user-001", role="member"):
    m = MagicMock()
    m.id = member_id
    m.org_id = org_id
    m.user_id = user_id
    m.role = role
    m.joined_at = datetime(2025, 6, 1)
    m.invited_by = None
    return m


def _make_user(user_id="user-002", name="Jane Doe", email="jane@example.com"):
    u = MagicMock()
    u.id = user_id
    u.name = name
    u.email = email
    u.avatar_url = "https://avatars.example.com/jane.png"
    return u


# ===========================================================================
# 1. create_organization
# ===========================================================================

class TestCreateOrganization:
    """POST /api/organizations"""

    @pytest.mark.anyio
    async def test_create_org_success(self, test_user, mock_db):
        # Slug check returns None (no conflict)
        mock_slug_result = MagicMock()
        mock_slug_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_slug_result

        org_created = _make_org()

        async def fake_refresh(obj):
            obj.id = org_created.id
            obj.name = org_created.name
            obj.slug = org_created.slug
            obj.plan = org_created.plan
            obj.created_at = org_created.created_at

        mock_db.refresh.side_effect = fake_refresh

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/organizations",
                json={"name": "TestOrg", "slug": "test-org"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "TestOrg"
        assert data["slug"] == "test-org"
        assert data["plan"] == "free"
        assert "id" in data
        # Two db.add calls: one for org, one for owner OrgMember
        assert mock_db.add.call_count == 2
        mock_db.commit.assert_awaited_once()

    @pytest.mark.anyio
    async def test_create_org_duplicate_slug(self, test_user, mock_db):
        existing_org = _make_org()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_org
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/organizations",
                json={"name": "TestOrg", "slug": "test-org"},
            )

        assert resp.status_code == 409
        assert "slug" in resp.json()["detail"].lower()

    @pytest.mark.anyio
    async def test_create_org_invalid_slug_format(self, test_user, mock_db):
        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/organizations",
                json={"name": "TestOrg", "slug": "INVALID SLUG!!"},
            )

        assert resp.status_code == 422  # Pydantic pattern validation

    @pytest.mark.anyio
    async def test_create_org_slug_too_short(self, test_user, mock_db):
        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/organizations",
                json={"name": "X", "slug": "x"},
            )

        assert resp.status_code == 422


# ===========================================================================
# 2. list_my_organizations
# ===========================================================================

class TestListOrganizations:
    """GET /api/organizations"""

    @pytest.mark.anyio
    async def test_list_orgs_returns_all(self, test_user, mock_db):
        orgs = [
            _make_org("org-001", "Alpha", "alpha"),
            _make_org("org-002", "Beta", "beta"),
        ]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = orgs
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/organizations")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "Alpha"
        assert data[1]["name"] == "Beta"
        for item in data:
            assert "id" in item
            assert "slug" in item
            assert "plan" in item

    @pytest.mark.anyio
    async def test_list_orgs_empty(self, test_user, mock_db):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/organizations")

        assert resp.status_code == 200
        assert resp.json() == []


# ===========================================================================
# 3. invite_member
# ===========================================================================

class TestInviteMember:
    """POST /api/organizations/{org_id}/members"""

    @pytest.mark.anyio
    async def test_invite_member_success(self, test_user, mock_db):
        caller_member = _make_member(role="owner", user_id=test_user["id"])
        target_user = _make_user("user-new", "New Guy", "new@example.com")
        org = _make_org(org_id="org-001")

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # Caller membership check
                result.scalar_one_or_none.return_value = caller_member
            elif call_count == 2:
                # Find user by email
                result.scalar_one_or_none.return_value = target_user
            elif call_count == 3:
                # Check existing membership (not yet a member)
                result.scalar_one_or_none.return_value = None
            elif call_count == 4:
                # Member count
                result.scalar.return_value = 2
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)
        mock_db.get = AsyncMock(return_value=org)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/organizations/org-001/members",
                json={"email": "new@example.com", "role": "member"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "invited"
        assert data["email"] == "new@example.com"
        assert data["role"] == "member"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.anyio
    async def test_invite_member_not_admin(self, test_user, mock_db):
        """Only owner/admin can invite members."""
        caller_member = _make_member(role="viewer", user_id=test_user["id"])
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = caller_member
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/organizations/org-001/members",
                json={"email": "new@example.com", "role": "member"},
            )

        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_invite_member_invalid_role(self, test_user, mock_db):
        caller_member = _make_member(role="owner", user_id=test_user["id"])

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = caller_member
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/organizations/org-001/members",
                json={"email": "new@example.com", "role": "superadmin"},
            )

        assert resp.status_code == 400
        assert "rol" in resp.json()["detail"].lower() or "Gecersiz" in resp.json()["detail"]

    @pytest.mark.anyio
    async def test_invite_member_user_not_found(self, test_user, mock_db):
        caller_member = _make_member(role="owner", user_id=test_user["id"])

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = caller_member
            elif call_count == 2:
                result.scalar_one_or_none.return_value = None  # user not found
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/organizations/org-001/members",
                json={"email": "ghost@example.com", "role": "member"},
            )

        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_invite_member_already_member(self, test_user, mock_db):
        caller_member = _make_member(role="owner", user_id=test_user["id"])
        target_user = _make_user("user-002", "Jane", "jane@example.com")
        existing_member = _make_member(user_id="user-002")

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = caller_member
            elif call_count == 2:
                result.scalar_one_or_none.return_value = target_user
            elif call_count == 3:
                result.scalar_one_or_none.return_value = existing_member
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/organizations/org-001/members",
                json={"email": "jane@example.com", "role": "member"},
            )

        assert resp.status_code == 409


# ===========================================================================
# 4. remove_member
# ===========================================================================

class TestRemoveMember:
    """DELETE /api/organizations/{org_id}/members/{user_id}"""

    @pytest.mark.anyio
    async def test_remove_member_success(self, test_user, mock_db):
        caller_member = _make_member(role="owner", user_id=test_user["id"])
        target_member = _make_member(member_id="mem-target", user_id="user-target", role="member")

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = caller_member
            elif call_count == 2:
                result.scalar_one_or_none.return_value = target_member
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/organizations/org-001/members/user-target")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "removed"
        assert data["user_id"] == "user-target"
        mock_db.delete.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.anyio
    async def test_remove_member_not_authorized(self, test_user, mock_db):
        """Only owner/admin can remove members."""
        caller_member = _make_member(role="member", user_id=test_user["id"])
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = caller_member
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/organizations/org-001/members/user-target")

        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_remove_self_forbidden(self, test_user, mock_db):
        """Cannot remove yourself from the organization."""
        caller_member = _make_member(role="owner", user_id=test_user["id"])
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = caller_member
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete(f"/api/organizations/org-001/members/{test_user['id']}")

        assert resp.status_code == 400
        assert "Kendinizi" in resp.json()["detail"]

    @pytest.mark.anyio
    async def test_remove_owner_forbidden(self, test_user, mock_db):
        """Cannot remove the organization owner."""
        caller_member = _make_member(role="admin", user_id=test_user["id"])
        owner_member = _make_member(user_id="owner-user", role="owner")

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = caller_member
            elif call_count == 2:
                result.scalar_one_or_none.return_value = owner_member
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/organizations/org-001/members/owner-user")

        assert resp.status_code == 403
        assert "Owner" in resp.json()["detail"]

    @pytest.mark.anyio
    async def test_remove_member_not_found(self, test_user, mock_db):
        caller_member = _make_member(role="owner", user_id=test_user["id"])

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = caller_member
            elif call_count == 2:
                result.scalar_one_or_none.return_value = None
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/organizations/org-001/members/user-ghost")

        assert resp.status_code == 404


# ===========================================================================
# 5. update_member_role
# ===========================================================================

class TestUpdateMemberRole:
    """PUT /api/organizations/{org_id}/members/{user_id}/role"""

    @pytest.mark.anyio
    async def test_update_role_success(self, test_user, mock_db):
        caller_member = _make_member(role="owner", user_id=test_user["id"])
        target_member = _make_member(user_id="user-target", role="member")

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = caller_member
            elif call_count == 2:
                result.scalar_one_or_none.return_value = target_member
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.put("/api/organizations/org-001/members/user-target/role?role=admin")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "updated"
        assert data["role"] == "admin"
        assert target_member.role == "admin"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.anyio
    async def test_update_role_not_owner(self, test_user, mock_db):
        """Only owner can change roles."""
        caller_member = _make_member(role="admin", user_id=test_user["id"])
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = caller_member
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.put("/api/organizations/org-001/members/user-target/role?role=admin")

        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_update_role_invalid_role(self, test_user, mock_db):
        caller_member = _make_member(role="owner", user_id=test_user["id"])
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = caller_member
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.put("/api/organizations/org-001/members/user-target/role?role=superadmin")

        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_role_member_not_found(self, test_user, mock_db):
        caller_member = _make_member(role="owner", user_id=test_user["id"])

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = caller_member
            elif call_count == 2:
                result.scalar_one_or_none.return_value = None
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.put("/api/organizations/org-001/members/user-ghost/role?role=admin")

        assert resp.status_code == 404


# ===========================================================================
# 6. assign_project_to_org
# ===========================================================================

class TestAssignProject:
    """POST /api/organizations/{org_id}/projects/{project_id}"""

    @pytest.mark.anyio
    async def test_assign_project_success(self, test_user, mock_db):
        project = MagicMock()
        project.owner_id = test_user["id"]
        project.org_id = None

        caller_member = _make_member(role="owner", user_id=test_user["id"])
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = caller_member
        mock_db.execute.return_value = mock_result
        mock_db.get = AsyncMock(return_value=project)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/organizations/org-001/projects/proj-001")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "assigned"
        assert data["project_id"] == "proj-001"
        assert data["org_id"] == "org-001"
        assert project.org_id == "org-001"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.anyio
    async def test_assign_project_not_owner(self, test_user, mock_db):
        """Project must belong to the current user."""
        project = MagicMock()
        project.owner_id = "someone-else"
        mock_db.get = AsyncMock(return_value=project)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/organizations/org-001/projects/proj-001")

        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_assign_project_not_org_admin(self, test_user, mock_db):
        """Must be owner/admin of the organization."""
        project = MagicMock()
        project.owner_id = test_user["id"]

        caller_member = _make_member(role="viewer", user_id=test_user["id"])
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = caller_member
        mock_db.execute.return_value = mock_result
        mock_db.get = AsyncMock(return_value=project)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/organizations/org-001/projects/proj-001")

        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_assign_project_not_found(self, test_user, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/organizations/org-001/projects/proj-ghost")

        assert resp.status_code == 404
