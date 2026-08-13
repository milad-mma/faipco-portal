"""Endpoint های Authentication: یک فرم ورود یکپارچه برای مدیریت و پرسنل، refresh، دریافت اطلاعات کاربر جاری."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserOut
from app.services.auth_service import AuthError, AuthLockedError, AuthService

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    فرم ورود یکپارچه: همان دو فیلد (username/password) هم برای مدیریت
    (یوزرنیم + رمز عبور) و هم برای پرسنل (کد پرسنلی + کد ملی) کار می‌کند —
    منطق تشخیص در AuthService.login() انجام می‌شود.
    """
    service = AuthService(db)
    try:
        access_token, refresh_token = await service.login(payload.username, payload.password)
    except AuthLockedError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": str(e.retry_after_seconds)},
        )
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        access_token, new_refresh_token = await service.refresh(payload.refresh_token)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.get("/me", response_model=UserOut)
async def read_current_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await AuthService(db).get_me(current_user)


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    try:
        await service.change_password(current_user, payload.current_password, payload.new_password)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
