from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.models import Organization, User
from app.schemas.schemas import UserContext
from app.services.security import decode_access_token, hash_api_key


ROLE_ORDER = {
    "viewer": 1,
    "contributor": 2,
    "analyst": 3,
    "org_admin": 4,
}


def _to_context(user: User, auth_type: str) -> UserContext:
    return UserContext(
        user_id=user.id,
        org_id=user.org_id,
        role=user.role,
        name=user.name,
        auth_type=auth_type,
    )


def _org_admin_context(org: Organization, db: Session, auth_type: str) -> UserContext | None:
    admin = (
        db.query(User)
        .filter(User.org_id == org.id, User.role == "org_admin", User.is_active.is_(True))
        .first()
    )
    if not admin:
        return None
    return _to_context(admin, auth_type=auth_type)


def _from_api_key(db: Session, raw_key: str) -> UserContext:
    key_hash = hash_api_key(raw_key)
    user = (
        db.query(User)
        .filter(User.api_key_hash == key_hash, User.is_active.is_(True))
        .first()
    )
    if user:
        return _to_context(user, auth_type="api_key")

    org = db.query(Organization).filter(Organization.api_key_hash == key_hash).first()
    if org:
        org_ctx = _org_admin_context(org, db, auth_type="api_key")
        if org_ctx:
            return org_ctx

    if settings.allow_plain_api_keys:
        user_plain = (
            db.query(User)
            .filter(User.api_key == raw_key, User.is_active.is_(True))
            .first()
        )
        if user_plain:
            return _to_context(user_plain, auth_type="api_key_legacy")

        org_plain = db.query(Organization).filter(Organization.api_key == raw_key).first()
        if org_plain:
            org_ctx = _org_admin_context(org_plain, db, auth_type="api_key_legacy")
            if org_ctx:
                return org_ctx

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def authenticate_api_key(db: Session, raw_key: str) -> UserContext:
    return _from_api_key(db, raw_key)


def _from_bearer_token(token: str, db: Session) -> UserContext:
    try:
        claims = decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    user_id = int(claims.get("user_id", 0) or 0)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token payload")

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return _to_context(user, auth_type="jwt")


def get_current_user(
    authorization: str = Header(default="", alias="Authorization"),
    x_api_key: str = Header(default="", alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> UserContext:
    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token:
            return _from_bearer_token(token, db)

    if x_api_key:
        return _from_api_key(db, x_api_key)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth credentials")


def require_role(min_role: str):
    def checker(user: UserContext = Depends(get_current_user)) -> UserContext:
        if ROLE_ORDER.get(user.role, 0) < ROLE_ORDER[min_role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return checker
