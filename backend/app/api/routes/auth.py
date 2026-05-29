from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, Database, get_client_ip
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_access_token, decode_token
from app.models.db.session import Session
from app.models.db.user import User
from app.models.schemas.auth import TokenRequest, TokenResponse
from app.services import audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
async def get_token(
    payload: TokenRequest,
    request: Request,
    db: Database,
) -> TokenResponse:
    settings = get_settings()

    if payload.admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin secret",
        )

    result = await db.execute(
        select(User).where(User.phone_number == payload.phone_number)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            phone_number=payload.phone_number,
            role="admin" if payload.phone_number == settings.ADMIN_PHONE_NUMBER else "user",
        )
        db.add(user)
        await db.flush()

    token = create_access_token(str(user.id), role=user.role)
    decoded = decode_token(token)

    db_session = Session(
        user_id=user.id,
        token_jti=decoded["jti"],
        expires_at=datetime.fromtimestamp(decoded["exp"], tz=timezone.utc),
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(db_session)

    await audit.log_action(
        db,
        action="auth.token_issued",
        user_id=user.id,
        resource_type="session",
        resource_id=decoded["jti"],
        ip_address=get_client_ip(request),
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    current_user: CurrentUser,
    db: Database,
    request: Request,
) -> None:
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    authorization = request.headers.get("Authorization", "")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return

    try:
        payload = decode_token(token)
        jti = payload.get("jti")
        if jti:
            result = await db.execute(select(Session).where(Session.token_jti == jti))
            session = result.scalar_one_or_none()
            if session:
                session.revoked = True
    except Exception:
        pass

    await audit.log_action(
        db,
        action="auth.token_revoked",
        user_id=current_user.id,
        ip_address=get_client_ip(request),
    )
