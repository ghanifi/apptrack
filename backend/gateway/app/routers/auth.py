import secrets
import hashlib
import httpx
from fastapi import APIRouter, HTTPException, status, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from jose import jwt, JWTError
from passlib.context import CryptContext
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.database import get_db
from app.models import User
from app.limiter import limiter
from app.crypto import encrypt, decrypt
from app.audit import record_audit
from app.device_fingerprint import generate_fingerprint

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

REFRESH_TOKEN_EXPIRE_DAYS = 30


def create_access_token(data: dict, fingerprint: str | None = None) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {**data, "exp": expire, "type": "access"}
    if fingerprint:
        payload["fp"] = fingerprint
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode({**data, "exp": expire, "type": "refresh"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _user_response(user: User) -> dict:
    return {"id": user.id, "email": user.email, "name": user.name, "avatar_url": user.avatar_url}


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(name=req.name, email=req.email, hashed_password=pwd_context.hash(req.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"message": "User registered successfully"}


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not user.hashed_password or not pwd_context.verify(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token_data = {"sub": user.id, "email": user.email, "name": user.name}
    fp = generate_fingerprint(request)
    access_token = create_access_token(token_data, fingerprint=fp)
    refresh_token = create_refresh_token(token_data)
    await record_audit(action="user.login", resource_type="user", resource_id=user.id, user_id=user.id, request=request)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": _user_response(user),
    }


@router.get("/github")
def github_oauth_redirect():
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=501, detail="GitHub OAuth not configured")
    state = secrets.token_urlsafe(32)
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&scope=repo,read:user,user:email"
        f"&state={state}"
        f"&redirect_uri={settings.FRONTEND_URL}/auth/github/callback"
    )
    is_secure = settings.FRONTEND_URL.startswith("https")
    redirect = RedirectResponse(url)
    redirect.set_cookie(
        "oauth_state",
        state,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=300,
    )
    return redirect


@router.post("/github/callback")
async def github_callback(
    code: str,
    state: str | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=501, detail="GitHub OAuth not configured")

    cookie_state = request.cookies.get("oauth_state") if request else None
    if cookie_state:
        if not state:
            raise HTTPException(status_code=400, detail="Missing OAuth state parameter")
        if not secrets.compare_digest(cookie_state, state):
            raise HTTPException(status_code=400, detail="Invalid OAuth state — possible CSRF attack")

    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://github.com/login/oauth/access_token",
            json={"client_id": settings.GITHUB_CLIENT_ID, "client_secret": settings.GITHUB_CLIENT_SECRET, "code": code},
            headers={"Accept": "application/json"},
        )
    token_data = token_res.json()
    github_token = token_data.get("access_token")
    if not github_token:
        raise HTTPException(status_code=400, detail="GitHub OAuth failed")

    async with httpx.AsyncClient() as client:
        user_res = await client.get("https://api.github.com/user", headers={"Authorization": f"Bearer {github_token}"})
    gh_user = user_res.json()

    result = await db.execute(select(User).where(User.github_id == str(gh_user["id"])))
    user = result.scalar_one_or_none()
    if not user:
        result2 = await db.execute(select(User).where(User.email == (gh_user.get("email") or "")))
        user = result2.scalar_one_or_none()

    encrypted_token = encrypt(github_token)

    if user:
        user.github_id = str(gh_user["id"])
        user.github_access_token = encrypted_token
        user.avatar_url = gh_user.get("avatar_url")
    else:
        user = User(
            name=gh_user.get("name") or gh_user.get("login"),
            email=gh_user.get("email") or f"{gh_user['login']}@github.local",
            github_id=str(gh_user["id"]),
            github_access_token=encrypted_token,
            avatar_url=gh_user.get("avatar_url"),
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)
    token_data = {"sub": user.id, "email": user.email, "name": user.name}
    fp = generate_fingerprint(request) if request else None
    access_token = create_access_token(token_data, fingerprint=fp)
    refresh_token = create_refresh_token(token_data)
    await record_audit(action="user.github_login", resource_type="user", resource_id=user.id, user_id=user.id, request=request)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": _user_response(user),
    }


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
@limiter.limit("10/minute")
async def refresh_token(request: Request, req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(req.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    result = await db.execute(select(User).where(User.id == payload.get("sub")))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    token_data = {"sub": user.id, "email": user.email, "name": user.name}
    fp = generate_fingerprint(request)
    new_access = create_access_token(token_data, fingerprint=fp)
    new_refresh = create_refresh_token(token_data)
    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
