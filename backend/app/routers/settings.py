from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from backend.app.database import get_db
from backend.app.models import User, UserApiKey, ActivityLog
from backend.app.schemas import ApiKeyConfig, ApiKeyList
from backend.app.auth import get_current_user, get_client_ip
from backend.app.config import settings

router = APIRouter(prefix="/api/settings", tags=["settings"])

PROVIDERS = [
    {"provider": "deepseek", "default_url": settings.DEEPSEEK_BASE_URL, "default_model": settings.DEEPSEEK_MODEL},
    {"provider": "siliconflow", "default_url": settings.SILICONFLOW_BASE_URL, "default_model": settings.SILICONFLOW_MODEL},
]


@router.get("/apikeys", response_model=ApiKeyList)
async def get_api_keys(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserApiKey).where(UserApiKey.user_id == user.id))
    user_keys = {k.provider: k for k in result.scalars().all()}

    keys = []
    for p in PROVIDERS:
        if p["provider"] in user_keys:
            k = user_keys[p["provider"]]
            keys.append(ApiKeyConfig(
                provider=k.provider,
                api_key=mask_key(k.api_key),
                base_url=k.base_url or p["default_url"],
                model=k.model or p["default_model"],
            ))
        else:
            # Show global config status
            global_key = settings.DEEPSEEK_API_KEY if p["provider"] == "deepseek" else settings.SILICONFLOW_API_KEY
            keys.append(ApiKeyConfig(
                provider=p["provider"],
                api_key=mask_key(global_key) if global_key else "",
                base_url=p["default_url"],
                model=p["default_model"],
            ))
    return ApiKeyList(keys=keys)


@router.put("/apikeys")
async def update_api_key(
    data: ApiKeyConfig, request: Request,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    if data.provider not in ("deepseek", "siliconflow"):
        return {"error": "不支持的提供商"}

    result = await db.execute(
        select(UserApiKey).where(UserApiKey.user_id == user.id, UserApiKey.provider == data.provider)
    )
    existing = result.scalar_one_or_none()

    if existing:
        if data.api_key and not data.api_key.startswith("sk-***"):
            existing.api_key = data.api_key
        if data.base_url:
            existing.base_url = data.base_url
        if data.model:
            existing.model = data.model
    else:
        key = UserApiKey(
            user_id=user.id,
            provider=data.provider,
            api_key=data.api_key if not data.api_key.startswith("sk-***") else "",
            base_url=data.base_url,
            model=data.model,
        )
        db.add(key)

    log = ActivityLog(
        user_id=user.id, username=user.username, action="update_apikey",
        detail=f"更新 {data.provider} API配置", ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent", "")[:512],
    )
    db.add(log)
    await db.commit()

    return {"status": "ok", "provider": data.provider}


@router.delete("/apikeys/{provider}")
async def delete_api_key(
    provider: str, request: Request,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(UserApiKey).where(UserApiKey.user_id == user.id, UserApiKey.provider == provider)
    )
    log = ActivityLog(
        user_id=user.id, username=user.username, action="delete_apikey",
        detail=f"删除 {provider} 自定义API配置", ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent", "")[:512],
    )
    db.add(log)
    await db.commit()
    return {"status": "ok"}


def mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return ""
    return key[:3] + "***" + key[-4:]
