# 阿里云 Windows10 + 二级域名 inkless 部署实操指南

> 目标环境：阿里云 2核2G Windows 10 图形化服务器
>
> 部署目标：把“不存在之书 — Inkless”部署到你自己的服务器上，通过二级域名 `inkless.你的主域名后缀` 访问，并在 **905 端口** 对外提供服务。

---

## 1. 推荐部署方式

**推荐采用“同源部署”**：

- 后端 FastAPI 运行在 **905** 端口
- 前端先在服务器本地构建成静态文件
- 后端直接把前端静态文件一起托管出去

本项目已经具备这个能力：

- [backend/app/main.py](backend/app/main.py) 会在检测到 [frontend/dist](frontend/dist) 存在后，自动托管前端页面
- 前端和 API 同源，登录、注册、游戏请求都走同一个域名和端口
- 这样可以避免 GitHub Pages 的静态站没有后端 API 的问题

也就是说，最终你访问的是：

- 页面地址：
  - http://inkless.你的主域名后缀:905
- 健康检查：
  - http://inkless.你的主域名后缀:905/api/health

---

## 2. 先决条件

### 2.1 服务器资源

当前你的机器是 **2核2G**，对这个项目来说可以先跑起来，适合：

- 自己使用
- 小范围测试
- 少量用户访问

建议：

- 先用 SQLite 跑通
- 后续如果用户量增大，再换 PostgreSQL

### 2.2 需要提前准备的软件

在 Windows 10 服务器上安装：

1. Git
2. Python 3.11+
3. Node.js 20 LTS
4. 可选：Visual C++ 运行库

安装完成后，在 PowerShell 里依次执行：

```powershell
git --version
python --version
node --version
npm --version
```

都能正常输出版本号即可。

---

## 3. 域名与网络配置

### 3.1 阿里云域名解析

进入阿里云域名控制台，为你的主域名增加一条记录：

- 记录类型：A
- 主机记录：inkless
- 记录值：你的服务器公网 IP
- TTL：默认即可

完成后，最终域名会变成：

- inkless.你的主域名后缀

### 3.2 阿里云安全组放行 905

进入 ECS 安全组，新增入方向规则：

- 协议类型：TCP
- 端口范围：905/905
- 授权对象：0.0.0.0/0

如果你还需要远程桌面，确保 3389 已开放。

### 3.3 Windows 防火墙放行 905

以管理员身份打开 PowerShell：

```powershell
New-NetFirewallRule -DisplayName "Inkless-905" -Direction Inbound -Protocol TCP -LocalPort 905 -Action Allow
```

---

## 4. 拉取项目到服务器

建议放到固定目录，例如：

```powershell
mkdir D:\apps -Force
cd D:\apps
git clone https://github.com/falling-feather/Tome.git writegame
cd D:\apps\writegame
```

后续所有命令都默认在这个目录中执行。

---

## 5. 一次性部署

### 方案 A：分两步执行

在项目根目录执行：

```powershell
cd D:\apps\writegame
.\scripts\deploy.ps1
```

这个脚本会：

- 创建 Python 虚拟环境
- 安装后端依赖
- 安装前端依赖
- 构建前端页面
- 初始化 .env 文件

如果脚本执行完没有报错，说明基础环境已经装好了。

### 方案 B：一键部署并直接启动

如果你更希望“一条命令搞定部署并运行”，可以直接执行：

```powershell
cd D:\apps\writegame
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-and-run-905.ps1
```

对应脚本见：

- [scripts/deploy-and-run-905.ps1](../scripts/deploy-and-run-905.ps1)

它会自动：

- 创建虚拟环境
- 安装依赖
- 构建前端
- 生成或修正 `.env` 中的 `HOST/PORT/DEBUG`
- 以 905 端口直接启动服务

---

## 6. 修改生产环境配置

打开 [\.env.example](../.env.example) 对照，然后编辑服务器上的 `.env` 文件：

```powershell
notepad D:\apps\writegame\.env
```

至少要修改这些项：

```env
HOST=0.0.0.0
PORT=905
DEBUG=false

SECRET_KEY=换成你自己的高强度随机字符串
CORS_ORIGINS=http://inkless.你的主域名后缀:905

DEEPSEEK_API_KEY=填写你自己的 Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

SILICONFLOW_API_KEY=
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_MODEL=deepseek-ai/DeepSeek-V3
```

### 6.1 SECRET_KEY 生成方式

在 PowerShell 运行：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

把输出结果复制到 `.env` 的 SECRET_KEY 中。

### 6.2 关于 CORS_ORIGINS

如果你采用同源部署并且所有访问都走同一个域名端口，推荐写成：

```env
CORS_ORIGINS=http://inkless.你的主域名后缀:905
```

如果以后加 HTTPS，再改成：

```env
CORS_ORIGINS=https://inkless.你的主域名后缀
```

---

## 7. 启动服务

### 7.1 临时前台启动（首次验证用）

```powershell
cd D:\apps\writegame
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 905
```

看到 Uvicorn 启动成功后，不要关掉窗口。

### 7.2 浏览器验证

先在服务器本机浏览器打开：

- http://127.0.0.1:905/api/health

如果返回类似：

```json
{"status":"ok","version":"..."}
```

再打开：

- http://127.0.0.1:905

确认登录页能正常打开。

最后再用外网访问：

- http://inkless.你的主域名后缀:905

---

## 8. 让服务重启后自动运行

Windows 生产环境建议使用以下两种方式之一。

### 方案 A：任务计划程序

优点：系统自带，不额外安装工具。

#### 步骤

1. 打开“任务计划程序”
2. 创建任务
3. 名称填写：Inkless
4. 触发器选择：计算机启动时
5. 操作选择：启动程序
6. 程序填写：

```text
powershell.exe
```

7. 参数填写：

```text
-ExecutionPolicy Bypass -File "D:\apps\writegame\scripts\start-prod-905.ps1"
```

### 方案 B：NSSM 注册为 Windows 服务

优点：更适合长期常驻运行。

你可以下载安装 NSSM，然后把下面的脚本注册为服务启动入口。

---

## 9. 推荐新增的生产启动脚本

已为本仓库准备了可直接使用的生产脚本：

- [scripts/start-prod-905.ps1](../scripts/start-prod-905.ps1)

它会：

- 自动进入项目目录
- 激活虚拟环境
- 按 905 端口启动服务
- 关闭热重载，适合生产环境

手动执行方式：

```powershell
cd D:\apps\writegame
powershell -ExecutionPolicy Bypass -File .\scripts\start-prod-905.ps1
```

---

## 10. 日常更新流程

以后更新代码时，按下面顺序操作：

```powershell
cd D:\apps\writegame
git pull
.\scripts\deploy.ps1
```

如果你更新了 `.env`，无需覆盖它。

然后重启服务即可。

---

## 11. 日志与排错

### 11.1 启动失败

优先检查：

- Python 是否正确安装
- Node 是否正确安装
- `.env` 是否填写完整
- 905 端口是否被别的程序占用

查看端口占用：

```powershell
netstat -ano | findstr :905
```

### 11.2 域名打不开

依次检查：

1. 域名是否解析到了正确公网 IP
2. 安全组是否放行 905
3. Windows 防火墙是否放行 905
4. Uvicorn 是否真的在运行

### 11.3 登录失败

如果页面能打开但登录失败，通常排查：

- `.env` 中 API Key 是否正确
- 后端日志是否报错
- 数据库文件是否可写

### 11.4 健康检查

任何时候都可以访问：

- http://inkless.你的主域名后缀:905/api/health

只要这个接口返回 ok，说明服务本身是活的。

---

## 12. 建议的第一阶段上线方案

对于你现在的环境，**最务实的第一阶段方案** 是：

- 使用阿里云 Windows 10 服务器
- 使用 SQLite
- 使用二级域名 `inkless`
- 直接开放 **905** 端口
- 通过 FastAPI 同时提供前端页面和 API

这套方案最省事，能最快做到“真实可用”。

---

## 13. 第二阶段优化建议（可后做）

等第一阶段跑稳定后，再考虑：

1. 换成 HTTPS
2. 用 Caddy / Nginx 做反向代理
3. 去掉地址里的 `:905`
4. 使用 PostgreSQL
5. 接入自动备份和日志轮转

---

## 14. 你下一步只要照着做

最短路径如下：

1. 给 `inkless` 加 A 记录，指向服务器公网 IP
2. 安全组和 Windows 防火墙放行 905
3. 在服务器上执行 [scripts/deploy-and-run-905.ps1](../scripts/deploy-and-run-905.ps1)
4. 打开 `.env`，补全 `SECRET_KEY` 和 API Key
5. 浏览器打开：
   - http://inkless.你的主域名后缀:905

只要这一步通了，项目就已经不再依赖 GitHub Pages，而是在你自己的服务器域名上真实运行了。
