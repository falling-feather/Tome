from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
import re


# ---- Auth ----
class UserRegister(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    is_admin: bool


class UserInfo(BaseModel):
    id: int
    username: str
    is_admin: bool
    created_at: datetime


# ---- Game Session ----
class SessionCreate(BaseModel):
    title: str = "新的冒险"
    scenario: str = "fantasy"
    character_name: str = "旅行者"
    character_class: str = "战士"
    story_id: Optional[int] = None  # 自编故事 ID


class SessionRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)


class SessionInfo(BaseModel):
    id: str
    title: str
    scenario: str
    state: dict
    created_at: datetime
    updated_at: datetime


class SessionList(BaseModel):
    sessions: List[SessionInfo]


# ---- Messages ----
class ActionInput(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        # Strip leading/trailing whitespace
        v = v.strip()
        # Collapse excessive whitespace / newlines
        v = re.sub(r"\s{5,}", "    ", v)
        if not v:
            raise ValueError("内容不能为空")
        return v


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    metadata_: Optional[dict] = None
    created_at: datetime


class ChatHistory(BaseModel):
    messages: List[MessageOut]
    state: dict


# ---- Admin ----
class LogEntry(BaseModel):
    id: int
    user_id: Optional[int]
    username: str
    action: str
    detail: str
    ip_address: str
    user_agent: str
    created_at: datetime


class LogList(BaseModel):
    logs: List[LogEntry]
    total: int
    page: int
    page_size: int


class AdminStats(BaseModel):
    total_users: int
    total_sessions: int
    total_messages: int
    total_logs: int
    recent_users: List[UserInfo]


# ---- Settings ----
class ApiKeyConfig(BaseModel):
    provider: str  # deepseek, siliconflow
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class ApiKeyList(BaseModel):
    keys: List[ApiKeyConfig]
