# tg-telethon-session-kit

基于 Telethon 的小工具包：在本地生成一次性 StringSession，在 VPS Docker 中做轻量心跳或拉取/监听登录验证码。

> **安全注意**：`TG_SESSION` 等同根口令，泄露即失控；2FA 也挡不住。不要进日志、截图、Git。

## 项目内容

- `scripts/login_local.py`：本地交互登录，打印 StringSession。
- `scripts/pull_code_once.py`：获取 `777000` 最近的登录验证码。
- `scripts/listen_code.py`：等待下一条来自 `777000` 的验证码。
- `docker/entrypoint.py`：容器入口，支持三种模式（`heartbeat`、`pull_code_once`、`listen_code`）。
- `Dockerfile`：根目录精简 Python 镜像（复制 `docker/entrypoint.py`）。
- `.env.example`：环境变量示例。
- `requirements.txt`：依赖（Telethon 固定版本）。

## 前置准备：如何获取 API ID / API HASH
1. 访问 https://my.telegram.org，使用你的 Telegram 账号登录（手机验证码）。
2. 点击 “API development tools”。
3. 创建应用（名称/描述随意，平台选其他即可）。
4. 创建后页面会显示 `App api_id` 和 `App api_hash`，后续填入环境变量。

## 快速开始（用预构建镜像）

1) 在可信机器安装依赖并生成 StringSession：
```bash
python -m venv .venv && . .venv/Scripts/Activate.ps1  # PowerShell
pip install -r requirements.txt
python scripts/login_local.py
```
妥善保存输出，不要提交版本库。

2) 在 VPS 直接运行预构建镜像（默认 heartbeat 模式）：

**Bash/Linux/macOS：**
```bash
docker run -d --name tg-heartbeat \
  --restart unless-stopped \
  -e TG_API_ID=123456 \
  -e TG_API_HASH="..." \
  -e TG_SESSION="..." \
  -e TG_MODE=heartbeat \
  -e TG_INTERVAL_SECONDS=1209600 \
  -e TG_JITTER_SECONDS=300 \
  ghcr.io/jbtt-2025/tg-session-kit:latest
```

**PowerShell：**
```powershell
docker run -d --name tg-heartbeat `
  --restart unless-stopped `
  --env TG_API_ID=123456 `
  --env TG_API_HASH="..." `
  --env TG_SESSION="..." `
  --env TG_MODE=heartbeat `
  --env TG_INTERVAL_SECONDS=1209600 `
  --env TG_JITTER_SECONDS=300 `
  ghcr.io/jbtt-2025/tg-session-kit:latest
```

## 模式（Docker `TG_MODE`）

- `heartbeat`（默认）：定期调用 `get_me` 后断开，可配置抖动。
- `pull_code_once`：打印 `777000` 最新验证码后退出，适合“新设备登录”。
- `listen_code`：等待下一条验证码，打印后退出。

运行容器时通过 `-e TG_MODE=...` 切换。

## 环境变量

详见 `.env.example`。

- 必填：`TG_API_ID`、`TG_API_HASH`、`TG_SESSION`
- 可选（心跳相关）：`TG_INTERVAL_SECONDS`（默认 14 天）、`TG_JITTER_SECONDS`（默认 300s）、`TG_MODE`

## 必看注意事项

- **同一 StringSession 只能跑在一台机器上**，不要多机并发。
- 使用稳定 VPS IP，避免住宅/变动 IP。
- 心跳间隔建议“天/周”级别，不要分钟级频繁调用。
- 把 `TG_SESSION` 当根密钥，不入日志、不截屏、不提交仓库。
- 容器日志、CI 变量、命令历史都可能泄露；谨慎处理。

## 本地辅助脚本

拉取最近验证码：

**Bash：**
```bash
export TG_API_ID=123456
export TG_API_HASH="..."
export TG_SESSION="..."
python scripts/pull_code_once.py
```

**PowerShell：**
```powershell
$env:TG_API_ID="123456"
$env:TG_API_HASH="..."
$env:TG_SESSION="..."
python scripts/pull_code_once.py
```

监听下一条验证码：
```bash
python scripts/listen_code.py
```

## Docker 运行速查

**Bash：**
```bash
# 拉取最新验证码（一次性）
docker run --rm \
  -e TG_API_ID=123456 \
  -e TG_API_HASH="..." \
  -e TG_SESSION="..." \
  -e TG_MODE=pull_code_once \
  ghcr.io/jbtt-2025/tg-session-kit:latest

# 监听下一条验证码
docker run --rm \
  -e TG_API_ID=123456 \
  -e TG_API_HASH="..." \
  -e TG_SESSION="..." \
  -e TG_MODE=listen_code \
  ghcr.io/jbtt-2025/tg-session-kit:latest
```

**PowerShell：**
```powershell
# 拉取最新验证码（一次性）
docker run --rm `
  --env TG_API_ID=123456 `
  --env TG_API_HASH="..." `
  --env TG_SESSION="..." `
  --env TG_MODE=pull_code_once `
  ghcr.io/jbtt-2025/tg-session-kit:latest

# 监听下一条验证码
docker run --rm `
  --env TG_API_ID=123456 `
  --env TG_API_HASH="..." `
  --env TG_SESSION="..." `
  --env TG_MODE=listen_code `
  ghcr.io/jbtt-2025/tg-session-kit:latest
```

## 其他说明

- 想更像 cron，可用 `--rm` 配合 systemd timer/cron 定期以 `TG_MODE=heartbeat` 运行一次即退出。
- Telethon 版本已固定，升级前确认 Telegram 协议/登录流程兼容。
