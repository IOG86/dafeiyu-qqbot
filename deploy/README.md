# 大肥鱼 QQ 机器人 — 部署说明（轻量化版）

AstrBot + SnowLuma（真实 Linux QQ + OneBot v11），部署在阿里云 ECS `203.0.113.10`
（Ubuntu 22.04.5 LTS，2 vCPU，**1.6 GiB 可用内存**，40 GiB 系统盘）。

所有服务端口只绑定 `127.0.0.1`，只能通过 **SSH 隧道**访问；公网仅放行 22。

> 本文档对应 **2026-10-28 重置系统后的轻量化重部署**。旧系统曾因公网回程丢包导致 SSH 无法使用，
> 重置系统盘后链路恢复，随后按"省内存 / 省 IOPS"方案重新部署。

## 1. 访问地址与密码

| 服务 | 本机地址（经 SSH 隧道） | 账号 | 密码 |
|---|---|---|---|
| AstrBot 管理面板 | http://127.0.0.1:6185 | `astrbot` | `change-me-panel` |
| SnowLuma 面板 | http://127.0.0.1:5099 | `admin`（只校验密码） | `change-me-panel` |
| noVNC 远程桌面 | http://127.0.0.1:6081 | — | `change-me-vnc` |

noVNC 免密直达：

```
http://127.0.0.1:6081/vnc.html?autoconnect=1&password=change-me-vnc&resize=scale
```

已绑定 QQ：**大肥鱼🐟🐟🐟🐟**（`1000000001`）。

## 2. 轻量化配置（关键，不要随意改大）

| 项目 | 值 | 原因 |
|---|---|---|
| `shm_size`（SnowLuma） | **512m** | 默认 64M 会让 Chromium 白屏；1G 太吃内存 |
| `SNOWLUMA_SCREEN` | **1024x640x16** | 16bit 比 24bit 更省内存，刚好放下 QQ 登录窗 |
| `SNOWLUMA_LOG_LEVEL` | **error** | 减少写盘 |
| AstrBot `log_level` | **WARNING** | 减少写盘 |
| AstrBot `mem_limit` | 450m（swap 上限 700m） | 防止单容器拖死整机 |
| SnowLuma `mem_limit` | 900m（swap 上限 1400m） | 同上 |
| zram 交换 | 512 MiB，priority 100 | 压缩交换，不占磁盘 IO |
| swapfile | 2 GiB | 兜底 |
| sysctl | swappiness=100、dirty_background_ratio=5、dirty_ratio=10、page-cluster=0 | 避免小写入积压成回写雪崩 |
| 看门狗 | `io-watchdog.timer` 每 30s | I/O 或内存压力连续 3 次超阈值 → 自动只停 QQ 容器，保住 SSH |

## 3. 文件位置

服务器 `/opt/qqbot/`：

| 路径 | 说明 |
|---|---|
| `docker-compose.yml` | 轻量化编排定义 |
| `.env` | VNC / WebUI / OneBot token（权限 600） |
| `astrbot/data/` | AstrBot 数据、`cmd_config.json` |
| `snowluma/data/config/` | `onebot.json`（全局）、`onebot_1000000001.json`（账号级）、`webui.json`、`vnc-password` |
| `snowluma/config`、`snowluma/local` | QQ 客户端配置与登录态（**不要删**） |
| `pull.sh` / `/var/log/qqbot-pull.log` | 拉镜像脚本与日志 |

本机 `deploy/`：`docker-compose.lite.yml`、`.env`、`tunnel.ps1`、`启动隧道.bat`、`remote/*.sh`。

## 4. 常用运维

```bash
ssh -i <key.pem> root@203.0.113.10
cd /opt/qqbot

docker compose ps                  # 状态
docker compose logs -f astrbot     # 框架日志（WARNING 级别，较安静）
docker compose logs -f snowluma    # QQ 日志（error 级别）
docker compose restart astrbot
docker compose restart snowluma
```

判断 QQ 在线（token 每次重装会重新生成，从 onebot.json 读）：

```bash
TOKEN=$(python3 -c "import json;print(json.load(open('/opt/qqbot/snowluma/data/config/onebot.json'))['networks']['httpServers'][0]['accessToken'])")
docker exec snowluma curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:3000/get_status
docker exec snowluma curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:3000/get_login_info
```

看门狗日志：`tail -20 /var/log/io-watchdog.log`

## 5. 常见问题

**二维码过期**：有效期约 60 秒。在 noVNC 里点二维码区域的「刷新」，然后立刻扫码。

**重启后要重新扫码**：登录时勾选「自动登录」可避免；已登录时也可在 QQ 设置里打开。

**AstrBot 面板看不到"适配器已连接"**：日志级别是 WARNING，这行是 INFO 被屏蔽了。
用 AstrBot 的 `/api/platform/stats` 或 SnowLuma 面板的「连接」页确认即可。

**改 AstrBot 密码**：

```bash
docker exec astrbot astrbot conf set dashboard.password '新密码'   # ≥8 位，含大小写+数字
docker restart astrbot
```

**改 noVNC 密码**：改 `/opt/qqbot/.env` 的 `VNC_PASSWD`（8 位 ASCII），再
`docker compose up -d --force-recreate snowluma`。

**改 SnowLuma 面板密码**：登录后在界面里改（≥10 位，含大小写、特殊字符、无空格）。

## 6. 注意事项

- 这台机器只有 **1.6 GiB 可用内存**，是硬约束，不要再叠加其他服务。
- 不要在服务器/容器里执行 `apt-get update`、`docker build`、大批量 `scp` 等写入密集型操作
  —— 这是此前两次把机器写死的诱因。
- 若 SSH 又不通但控制台云助手可用：大概率是公网回程链路问题，重启实例通常能恢复。
- **LLM 已配置**：DeepSeek（`deepseek-chat`），2026-10-28 实测 `check_one` 返回 `available`，
  端到端对话测试通过。如需更换，去 AstrBot 面板 →「服务提供商」修改 `deepseek` 这条。
  Key 以明文存在 `/opt/qqbot/astrbot/data/cmd_config.json`，注意该文件不要外传。
- 隧道断开时双击 [启动隧道.bat](启动隧道.bat) 重开。

## 7. 当前验证结果（2026-10-28 19:16）

| 检查项 | 结果 |
|---|---|
| OneBot `get_status` | `{"online":true,"good":true}` |
| OneBot `get_login_info` | `user_id=1000000001, nickname=大肥鱼🐟🐟🐟🐟` |
| SnowLuma `/api/connections` | `astrbot` wsClient → `status=ok, 已连接` |
| AstrBot `/api/platform/stats` | `aiocqhttp` → `running`, `errors=0` |
| 内存 | used ≈ 714 MB / available ≈ 724 MB，zram ≈ 668 MB |
| I/O 压力 | full avg10 ≈ 1.8%，load ≈ 0.23 |
| 看门狗 | 运行中，无告警事件 |
