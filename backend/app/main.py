import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select

from backend.app.config import settings
from backend.app.logging_config import setup_logging
from backend.app.database import init_db, async_session
from backend.app.models import User
from backend.app.auth import hash_password
from backend.app.middleware import RequestLoggingMiddleware
from backend.app.routers import auth, game, admin
from backend.app.routers import settings as settings_router
from backend.app.routers import stories as stories_router

setup_logging()
logger = logging.getLogger("inkless")

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


async def seed_admin():
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == settings.ADMIN_USERNAME))
        if result.scalar_one_or_none() is None:
            admin_user = User(
                username=settings.ADMIN_USERNAME,
                password_hash=hash_password("mic820323"),
                is_admin=True,
            )
            db.add(admin_user)
            await db.commit()
            logger.info(f"管理员账号 '{settings.ADMIN_USERNAME}' 已创建")


async def seed_world_data():
    """种子世界书和 Prompt 模板"""
    from backend.app.services.world_book import WorldBookService
    from backend.app.services.prompt_assembler import PromptAssembler
    async with async_session() as db:
        wb = WorldBookService(db)
        await wb.seed_if_empty()
        pa = PromptAssembler(db)
        await pa.seed_if_empty()


async def seed_game_events():
    """种子事件池（仅在空表时从内置常量初始化）"""
    from backend.app.services.game_engine import seed_events_if_empty

    async with async_session() as db:
        await seed_events_if_empty(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("正在初始化数据库...")
    await init_db()
    await seed_admin()
    await seed_world_data()
    await seed_game_events()
    logger.info("不存在之书 (Inkless) 服务启动完成")
    yield
    logger.info("不存在之书 (Inkless) 服务关闭")


app = FastAPI(
    title="不存在之书 — Inkless",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

_cors_origins = (
    [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    if settings.CORS_ORIGINS != "*"
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=settings.CORS_ORIGINS != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

# Register routers
app.include_router(auth.router)
app.include_router(game.router)
app.include_router(admin.router)
app.include_router(settings_router.router)
app.include_router(stories_router.router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
    }


# Serve frontend static files
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="static")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
