"""
审计日志工具函数 — 统一封装日志写入，失败不影响业务响应
"""
import logging
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import User, ActivityLog
from backend.app.auth import get_client_ip

logger = logging.getLogger("inkless")


async def audit_log(
    db: AsyncSession,
    *,
    user: User | None = None,
    user_id: int | None = None,
    username: str = "",
    action: str,
    detail: str = "",
    request: Request | None = None,
) -> None:
    """
    写入一条审计日志。失败只打 warning，不抛异常、不回滚外部事务。

    用法::

        await audit_log(db, user=user, action="login", detail="登录成功", request=request)
    """
    try:
        entry = ActivityLog(
            user_id=user.id if user else user_id,
            username=user.username if user else username,
            action=action,
            detail=detail[:2000],
            ip_address=get_client_ip(request) if request else "",
            user_agent=(request.headers.get("User-Agent", "")[:512]) if request else "",
        )
        db.add(entry)
        await db.commit()
    except Exception as exc:
        logger.warning("审计日志写入失败: %s", exc, exc_info=True)
        try:
            await db.rollback()
        except Exception:
            pass
