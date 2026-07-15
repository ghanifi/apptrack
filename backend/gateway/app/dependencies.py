from fastapi import HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from app.config import settings
from app.device_fingerprint import generate_fingerprint
from app.tenant_middleware import inject_tenant

bearer_scheme = HTTPBearer()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        token_type = payload.get("type", "access")
        if token_type != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type — use access token")
        if settings.DEVICE_FINGERPRINT_ENABLED:
            token_fp = payload.get("fp")
            if token_fp:
                current_fp = generate_fingerprint(request)
                if current_fp != token_fp:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Session fingerprint mismatch — please re-authenticate",
                    )
        user = {"id": user_id, "email": payload.get("email"), "name": payload.get("name"),
                "is_admin": payload.get("is_admin", False)}
        inject_tenant(request, user)
        return user
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
