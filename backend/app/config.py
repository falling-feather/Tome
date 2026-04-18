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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
