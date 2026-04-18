from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.database import get_db
from backend.app.models import User, ActivityLog
from backend.app.schemas import UserRegister, UserLogin, TokenResponse, UserInfo
from backend.app.auth import hash_password, verify_password, create_access_token, get_current_user, get_client_ip

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(data: UserRegister, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        is_admin=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    log = ActivityLog(
        user_id=user.id, username=user.username, action="register",
        detail=f"注册账号", ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent", "")[:512],
    )
    db.add(log)
    await db.commit()

    token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=token, username=user.username, is_admin=user.is_admin)


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        log = ActivityLog(
            user_id=None, username=data.username, action="login_failed",
            detail="登录失败：密码错误或用户不存在", ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent", "")[:512],
        )
        db.add(log)
        await db.commit()
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    log = ActivityLog(
        user_id=user.id, username=user.username, action="login",
        detail="登录成功", ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent", "")[:512],
    )
    db.add(log)
    await db.commit()

    token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=token, username=user.username, is_admin=user.is_admin)


@router.get("/me", response_model=UserInfo)
async def get_me(user: User = Depends(get_current_user)):
    return UserInfo(id=user.id, username=user.username, is_admin=user.is_admin, created_at=user.created_at)
