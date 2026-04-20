import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.app.logging_config import request_id_var, user_id_var, session_id_var, new_request_id

logger = logging.getLogger("inkless")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 注入请求上下文
        rid = request.headers.get("X-Request-ID") or new_request_id()
        request_id_var.set(rid)
        user_id_var.set("-")
        session_id_var.set("-")

        start = time.time()
        response: Response = await call_next(request)
        duration = time.time() - start

        logger.info(
            "%s %s status=%d duration=%.3fs ip=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration,
            request.client.host if request.client else "unknown",
        )
        response.headers["X-Request-ID"] = rid
        return response
