from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Household, Profile

bearer = HTTPBearer(auto_error=False)


def create_access_token(*, subject: str, household_id: str, profile_id: str, demo: bool = True) -> str:
    from datetime import datetime, timedelta, timezone

    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject, "household_id": household_id, "profile_id": profile_id,
        "demo": demo, "iss": settings.jwt_issuer, "iat": now,
        "token_use": "access",
        "exp": now + timedelta(minutes=settings.jwt_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_refresh_token(*, subject: str, household_id: str, profile_id: str, demo: bool = False, days: int = 30) -> str:
    from datetime import datetime, timedelta, timezone

    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject, "household_id": household_id, "profile_id": profile_id,
        "demo": demo, "iss": settings.jwt_issuer, "iat": now,
        "token_use": "refresh",
        "exp": now + timedelta(days=days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_refresh_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.jwt_issuer, options={"require": ["sub", "exp", "iss"]})
        if claims.get("token_use") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type; refresh token required")
        return claims
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token") from exc


@lru_cache(maxsize=4)
def _cognito_jwks_client(region: str, pool_id: str) -> PyJWKClient:
    url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"
    return PyJWKClient(url, cache_keys=True, lifespan=3600)


def _decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    if settings.cognito_user_pool_id and settings.cognito_app_client_id:
        issuer = f"https://cognito-idp.{settings.aws_region}.amazonaws.com/{settings.cognito_user_pool_id}"
        try:
            signing_key = _cognito_jwks_client(settings.aws_region, settings.cognito_user_pool_id).get_signing_key_from_jwt(token)
            claims = jwt.decode(token, signing_key.key, algorithms=["RS256"], issuer=issuer, options={"verify_aud": False, "require": ["sub", "exp", "iss"]})
        except Exception as exc:
            # JWKS/network failures must not leak provider details into API responses.
            raise HTTPException(status_code=401, detail="Invalid identity token or identity provider unavailable") from exc
        if claims.get("token_use") != "access" or claims.get("client_id") != settings.cognito_app_client_id:
            raise HTTPException(status_code=401, detail="Invalid identity token type or client")
        return claims
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.jwt_issuer, options={"require": ["sub", "exp", "iss"]})
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session") from exc


def get_authenticated_identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict[str, Any]:
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    claims = _decode_token(credentials.credentials)
    return {"sub": claims["sub"], "claims": claims, "demo": bool(claims.get("demo", False))}


def get_current_user(
    identity: dict[str, Any] = Depends(get_authenticated_identity),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    claims = identity["claims"]
    subject = identity["sub"]
    household_id = claims.get("household_id") or (db.scalar(select(Household.id).where(Household.owner_sub == subject)))
    household = db.get(Household, household_id) if household_id else None
    if not household or household.owner_sub != subject:
        raise HTTPException(status_code=403, detail="Complete household onboarding before using this resource")
    profile_id = claims.get("profile_id") or db.scalar(select(Profile.id).where(Profile.household_id == household.id).order_by(Profile.created_at).limit(1))
    profile = db.get(Profile, profile_id) if profile_id else None
    if not profile or profile.household_id != household.id:
        raise HTTPException(status_code=403, detail="Profile is not authorized for this household")
    return {"sub": subject, "household_id": household.id, "profile_id": profile.id, "demo": identity["demo"]}


def assert_household_access(user: dict[str, Any], household_id: str) -> None:
    if user["household_id"] != household_id:
        raise HTTPException(status_code=404, detail="Resource not found")
