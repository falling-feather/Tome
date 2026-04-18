# 不存在之书 — Inkless

一个基于大语言模型驱动的 AI 互动叙事平台。通过多角色分段对话、世界书、记忆压缩与多智能体审计，实现高自由度沉浸式文字冒险体验。

## 系统架构

```
前端 (React + TypeScript)
  ├── 登录/注册页面
  ├── 游戏主界面 (会话列表 + 对话面板 + 状态面板)
  ├── 管理员控制台 (概览 + 日志 + 用户 + 世界书管理)
  └── API 配置设置页

后端 (FastAPI + Python)
  ├── 认证系统 (JWT)
  ├── 游戏引擎 (状态机 + 事件池 + 动作校验)
  ├── LLM 服务 (DeepSeek / 硅基流动，断路器 + 自动降级)
  ├── 世界书 + Prompt 分层装配器 + 后处理管道
  ├── 五级记忆压缩 (L1原始→L5核心)
  ├── 多智能体审计 (角色/世界观/叙事/审计代理)
  ├── 稳定性加固 (断路器/重试/限流/健康指标)
  ├── 管理接口 (日志/用户/统计/世界书/健康)
  └── 存储层 (SQLite / PostgreSQL)
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18, TypeScript, Vite, React Router |
| 后端 | Python 3.11+, FastAPI, SQLAlchemy (async) |
| 数据库 | SQLite (默认) / PostgreSQL (生产) |
| LLM | DeepSeek API, 硅基流动 API (OpenAI 兼容) |
| 部署 | Docker, Docker Compose |

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+
- npm

### 一键部署

**Windows (PowerShell):**
```powershell
.\scripts\deploy.ps1
.\scripts\start.ps1
```

**Linux/macOS:**
```bash
chmod +x scripts/*.sh
./scripts/deploy.sh
./scripts/start.sh
```

### 手动部署

```bash
# 1. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .\.venv\Scripts\Activate.ps1  # Windows

# 2. 安装后端依赖
pip install -r backend/requirements.txt

# 3. 安装并构建前端
cd frontend
npm install
npm run build
cd ..

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填写 API Key

# 5. 启动服务
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### 开发模式

```bash
# 终端 1: 后端 (自动重载)
python -m uvicorn backend.app.main:app --reload --port 8000

# 终端 2: 前端开发服务器
cd frontend
npm run dev
```

前端开发服务器运行在 `http://localhost:3000`，API 请求会自动代理到后端。

## 环境配置

复制 `.env.example` 为 `.env` 并修改：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库连接 | `sqlite+aiosqlite:///./writegame.db` |
| `SECRET_KEY` | JWT 密钥 | 随机生成 |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | - |
| `SILICONFLOW_API_KEY` | 硅基流动 API Key | - |
| `PORT` | 服务端口 | `8000` |

## 账号说明

- **管理员账号**: `falling-feather` (首次启动自动创建)
- **普通用户**: 通过注册页面自行注册
- 管理员登录后进入控制台，可查看用户日志、操作记录、IP 等信息
- 普通用户登录后进入游戏界面

## 功能特性

### 游戏系统
- LLM 驱动的实时叙事生成（流式输出）
- 多世界设定（奇幻 / 科幻 / 武侠）
- 角色创建（名称 + 职业）
- 显式状态机（6 状态 + 21 事件 + 动作校验 + 死亡豁免）
- Roguelike 事件池（12+ 随机事件，权重触发 + 冷却机制）
- 多会话管理（创建 / 切换 / 删除）
- RAG 世界书检索（25+ 词条，关键词匹配 + 章节过滤）
- 六层 Prompt 装配（核心规则→风格→世界观→状态→状态规则→事件）
- AI 输出后处理（meta 移除、物品/NPC/金币提取、一致性检查）
- 五级记忆压缩（原始→近期→章节→弧线→核心）
- 多智能体审计（角色代理 + 世界观代理 + 叙事代理 + 审计代理）
- 降级模板兜底（审计失败时安全回退）

### 管理后台
- 系统概览统计（用户数、会话数、消息数）
- 操作日志查询（支持按用户名和操作类型筛选）
- 用户管理列表
- 世界书 CRUD 管理（场景/层级筛选、批量管理）
- 系统健康看板（断路器状态、限流统计、性能指标）
- 分页浏览

### API 配置
- 用户级 API Key 管理
- 支持 DeepSeek + 硅基流动双通道
- 自定义 Base URL 和模型名称
- 全局/用户配置优先级

### UI 设计
- 科技风/极简风格（白 + 浅蓝 + 黑色系）
- 响应式布局（弹性适配不同尺寸）
- 无过度圆角和纯色块
- 流畅的过渡动画

## 项目结构

```
writegame/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置管理
│   │   ├── database.py          # 数据库初始化
│   │   ├── models.py            # ORM 模型 (7+ 表)
│   │   ├── schemas.py           # Pydantic 模式
│   │   ├── auth.py              # JWT 认证
│   │   ├── middleware.py         # 请求日志中间件
│   │   ├── routers/
│   │   │   ├── auth.py          # 登录/注册接口
│   │   │   ├── game.py          # 游戏会话接口
│   │   │   ├── admin.py         # 管理后台接口 (含世界书/健康)
│   │   │   └── settings.py      # API配置接口
│   │   └── services/
│   │       ├── llm_service.py   # LLM 调用 (断路器+降级)
│   │       ├── game_engine.py   # 游戏引擎 (状态机+事件池)
│   │       ├── world_book.py    # 世界书检索服务
│   │       ├── prompt_assembler.py  # Prompt 分层装配
│   │       ├── post_processor.py    # AI输出后处理
│   │       ├── memory_service.py    # 五级记忆压缩
│   │       ├── agents.py        # 多智能体审计系统
│   │       └── resilience.py    # 断路器/重试/限流/指标
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # 路由配置
│   │   ├── api/client.ts        # API 客户端
│   │   ├── stores/auth.tsx      # 认证状态管理
│   │   ├── components/          # 复用组件
│   │   ├── pages/               # 页面组件
│   │   └── styles/              # CSS 样式
│   ├── package.json
│   └── vite.config.ts
├── scripts/
│   ├── deploy.sh / deploy.ps1   # 一键部署
│   └── start.sh / start.ps1     # 快速启动
├── docs/                         # 项目文档
├── .env.example                  # 环境变量模板
├── docker-compose.yml            # Docker 编排
├── Dockerfile                    # 容器构建
└── README.md
```

## API 接口

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/auth/register` | 注册 | - |
| POST | `/api/auth/login` | 登录 | - |
| GET | `/api/auth/me` | 当前用户 | 需要 |
| POST | `/api/game/sessions` | 创建会话 | 需要 |
| GET | `/api/game/sessions` | 会话列表 | 需要 |
| GET | `/api/game/sessions/:id` | 会话详情 | 需要 |
| DELETE | `/api/game/sessions/:id` | 删除会话 | 需要 |
| POST | `/api/game/sessions/:id/action` | 提交行动 (SSE) | 需要 |
| GET | `/api/admin/stats` | 管理统计 | 管理员 |
| GET | `/api/admin/logs` | 操作日志 | 管理员 |
| GET | `/api/admin/users` | 用户列表 | 管理员 |
| GET/POST/PUT/DELETE | `/api/admin/world-entries` | 世界书管理 | 管理员 |
| GET/PUT | `/api/admin/prompt-templates` | Prompt模板管理 | 管理员 |
| GET | `/api/admin/health` | 系统健康报告 | 管理员 |
| GET | `/api/settings/apikeys` | 获取API配置 | 需要 |
| PUT | `/api/settings/apikeys` | 更新API配置 | 需要 |
| DELETE | `/api/settings/apikeys/:provider` | 删除API配置 | 需要 |

## 里程碑进度

参见 `docs/03-详细工作计划与里程碑.md`

| 里程碑 | 内容 | 状态 |
|--------|------|------|
| M1 | MVP 最小闭环 | ✅ 完成 |
| M2 | 状态机 + 事件池 | ✅ 完成 |
| M3 | RAG 世界书 + Prompt 分层 | ✅ 完成 |
| M4 | 五级记忆压缩 | ✅ 完成 |
| M5 | 多智能体编排与审计 | ✅ 完成 |
| M6 | 稳定性加固 | ✅ 完成 |

## 许可证

MIT License
