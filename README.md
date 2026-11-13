# 大肥鱼 · DeepSeek × QQ 机器人

一台 1.6 GB 内存的阿里云 ECS 上跑起来的 QQ 机器人：AstrBot + SnowLuma（真实 Linux QQ）+ OneBot v11 反向 WebSocket，聊天用 DeepSeek，识图用智谱 GLM-4V。

## 它做什么

- 群聊 / 私聊接话，能认图（图片先由 GLM-4V 转述，再交给 DeepSeek）
- 70 张表情包，由模型在回复末尾写 `[[表情:名字]]` 自己挑，插件解析后发真实图片
- 人格包四件套：人设 / 表达习惯 / 台词库 / 边界，改 md 文件即改人格

## 架构

```
QQ 客户端（SnowLuma，Linux QQ + Xvfb + noVNC）
   │  OneBot v11 反向 WebSocket
   ▼
AstrBot（容器，127.0.0.1:6185）
   │  HTTPS 出站
   ├── DeepSeek API（聊天）
   └── 智谱 GLM-4V（识图）
```

所有管理面板只绑 `127.0.0.1`，本机通过 `ssh -L` 隧道访问；公网只开 22 端口。

## 几个数字

- 机器：2 vCPU / 1.6 GB / Ubuntu 22.04，swap + zram
- 容器：AstrBot 450 MB 上限、SnowLuma 900 MB 上限、shm 512 MB
- 成本：DeepSeek 日耗从 1.3 元压到 0.3–0.5 元（轮数、上下文裁剪、关后台任务、日限额）
- 4 个插件里自研 2 个：表情包、人格包
- 3 级看门狗：30 秒采 I/O 与内存、2 分钟拉起 QQ 容器、5 分钟查掉线

## 目录

- `docs/项目知识总结.md` —— 把踩过的坑翻成网络工程知识（分层排障、Linux、Docker、OneBot、LLM 成本）
- `docs/使用教程.md` —— 部署、人格、表情包、Cookie、成本收紧
- `console/` —— 本机控制台（纯 Python 标准库 HTTP 服务）：状态 / 余额 / 表情包 / 规则 / 聊天测试 / 日志
- `persona/` —— AstrBot 人格包插件 + 四件套人格文件
- `deploy/` —— compose、SSH 隧道脚本、运维脚本

## 一次真实的排障（这个项目最值钱的部分）

SSH 卡在 `Connection timed out during banner exchange`：先测 TCP 能连 → 裸 socket 能读到 banner → 服务端日志 `kex_exchange_identification: read: Connection reset` → 服务器自连正常 ⇒ 判定是链路侧应用层丢包，最后靠重置系统盘恢复。完整 10 个故障复盘在 `docs/项目知识总结.md`。

## 说明

- 本仓库是**脱敏后的整理版**：服务器 IP、面板密码、QQ 号、`.pem`、API Key 全部移除，文档里的地址用保留地址（`203.0.113.10`）代替，密码用 `change-me-panel` / `change-me-vnc` 占位。
- 项目里的代码和文档有 AI 编程助手参与（插件、控制台、脚本）；部署、参数调整、排障是我自己做的。
- 想复现：先看 `docs/使用教程.md`，把占位符换成你自己的再执行。
