import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, Text, DateTime, ForeignKey, JSON, Float
)
from sqlalchemy.orm import relationship
from backend.app.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("GameSession", back_populates="user", cascade="all, delete-orphan")
    logs = relationship("ActivityLog", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("UserApiKey", back_populates="user", cascade="all, delete-orphan")


class GameSession(Base):
    __tablename__ = "game_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(256), default="新的冒险")
    scenario = Column(String(64), default="fantasy")
    state = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan",
                            order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("game_sessions.id"), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("GameSession", back_populates="messages")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    username = Column(String(64), default="")
    action = Column(String(64), nullable=False)
    detail = Column(Text, default="")
    ip_address = Column(String(45), default="")
    user_agent = Column(String(512), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="logs")


class UserApiKey(Base):
    __tablename__ = "user_api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False)  # deepseek, siliconflow
    api_key = Column(String(256), default="")
    base_url = Column(String(256), default="")
    model = Column(String(128), default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="api_keys")


class GameEvent(Base):
    __tablename__ = "game_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_key = Column(String(64), unique=True, nullable=False)
    category = Column(String(32), nullable=False)  # environment, character, plot, resource, risk
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=False)
    conditions = Column(JSON, default=dict)
    base_weight = Column(Float, default=1.0)
    cooldown_turns = Column(Integer, default=3)
    effects = Column(JSON, default=dict)
    scenarios = Column(JSON, default=list)  # [] = all scenarios


class WorldEntry(Base):
    """世界书条目 — 分层设定数据 (core / chapter / ephemeral)"""
    __tablename__ = "world_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario = Column(String(64), nullable=False, index=True)      # fantasy / scifi / wuxia / *
    layer = Column(String(16), nullable=False, index=True)          # core / chapter / ephemeral
    category = Column(String(32), nullable=False)                   # lore, character, location, faction, item, rule
    title = Column(String(128), nullable=False)
    keywords = Column(String(512), nullable=False, default="")      # 逗号分隔的关键词
    content = Column(Text, nullable=False)
    chapter_min = Column(Integer, default=0)                        # 生效最小章节 (0=不限)
    chapter_max = Column(Integer, default=0)                        # 生效最大章节 (0=不限)
    priority = Column(Integer, default=0)                           # 越高越优先
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<WorldEntry {self.scenario}/{self.layer}: {self.title}>"


class PromptTemplate(Base):
    """Prompt 模板 — 版本化管理"""
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, index=True)           # system_core / style_guide / ...
    scenario = Column(String(64), nullable=False, default="*")      # * = 通用
    version = Column(Integer, nullable=False, default=1)
    content = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MemoryEntry(Base):
    """五级记忆压缩条目"""
    __tablename__ = "memory_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("game_sessions.id"), nullable=False, index=True)
    level = Column(Integer, nullable=False, index=True)         # 1-5
    content = Column(Text, nullable=False)
    turn_start = Column(Integer, default=0)                     # 覆盖的起始回合
    turn_end = Column(Integer, default=0)                       # 覆盖的结束回合
    chapter = Column(Integer, default=0)                        # 关联章节 (L3+)
    token_estimate = Column(Integer, default=0)                 # 粗略 token 数
    metadata_ = Column("metadata", JSON, default=dict)          # 额外信息
    created_at = Column(DateTime, default=datetime.utcnow)


class CustomStory(Base):
    """用户自编故事 — 导入的小说/故事内容"""
    __tablename__ = "custom_stories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    raw_content = Column(Text, nullable=False)
    parsed_data = Column(JSON, default=dict)       # {characters, locations, world_rules, plot_summary}
    status = Column(String(32), default="pending")  # pending / parsing / ready / error
    error_msg = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="custom_stories")
