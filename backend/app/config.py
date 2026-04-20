import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./writegame.db"
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_MODEL: str = "deepseek-ai/DeepSeek-V3"

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    ADMIN_USERNAME: str = "falling-feather"

    CORS_ORIGINS: str = "*"  # 逗号分隔白名单, 如 "http://localhost:5173,https://example.com"

    APP_VERSION: str = "2.9.0"

    # 审计代理阈值 — 累计问题数 ≥ 此值时触发 LLM 重写, ×1.6 时降级到安全模板
    AUDIT_REWRITE_THRESHOLD: int = 5

    # 每用户每日 LLM 动作上限 (0 = 不限制)
    DAILY_ACTION_LIMIT: int = 200

    # 嵌入向量召回 (P1-13)
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_PROVIDER: str = "openai"  # 复用 user_api_keys 中对应 provider 的 base_url + api_key
    EMBEDDING_ENABLED: bool = True
    EMBEDDING_WEIGHT: float = 50.0  # cosine 相似度乘以此权重后并入 keyword 评分

    # OpenTelemetry 可观测性 (P1-22)
    OTEL_ENABLED: bool = False  # 总开关；关闭时完全跳过 OTel 初始化
    OTEL_SERVICE_NAME: str = "inkless-backend"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""  # 如 "http://localhost:4318"，留空则仅打印到控制台
    OTEL_CONSOLE_EXPORT: bool = True  # 是否同时输出 span 到控制台（开发期排错）
    OTEL_SAMPLE_RATIO: float = 1.0  # 0.0 ~ 1.0，1.0 = 全量

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


# ---------------------------------------------------------------------------
# 启动期安全检查 (v1.0+)
# ---------------------------------------------------------------------------
_DEFAULT_SECRET_KEY = "change-this-in-production"

if settings.SECRET_KEY == _DEFAULT_SECRET_KEY and not settings.DEBUG:
    raise RuntimeError(
        "SECRET_KEY 仍为默认值且当前不在 DEBUG 模式。"
        "请在 .env 中设置 SECRET_KEY=<至少32位随机字符串> 后再启动服务。"
        "可用 `python -c \"import secrets;print(secrets.token_urlsafe(48))\"` 生成。"
    )
