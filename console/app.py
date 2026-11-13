#!/usr/bin/env python3
"""大肥鱼控制台 —— 运行在你自己的电脑上（127.0.0.1:8090）

- 只监听本机回环，不对外暴露
- 服务器操作走 SSH（读状态、改规则、传表情包、重启容器）
- 聊天测试走 SSH 隧道到 AstrBot（127.0.0.1:6185）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEY = HERE.parent / ".ssh" / "your-key.pem"
HOST = "root@203.0.113.10"
SERVER_API = "/opt/qqbot/console/server_api.py"
PORT = 8090
CACHE_DIR = HERE / "cache" / "stickers"
_LAST_SYNC = 0.0

SSH_BASE = [
    "ssh",
    "-i", str(KEY),
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=NUL",
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=20",
    "-o", "ServerAliveInterval=15",
    "-o", "ServerAliveCountMax=3",
    HOST,
]

_status_cache: tuple[float, dict] | None = None


def sync_stickers(force: bool = False):
    """把服务器上的表情包同步到本地缓存，供页面预览。"""
    global _LAST_SYNC
    now = time.time()
    if not force and now - _LAST_SYNC < 30:
        return
    _LAST_SYNC = now
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        "scp", "-i", str(KEY),
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=NUL",
        "-r", f"{HOST}:/opt/qqbot/astrbot/data/dafeiyu_console/stickers/.",
        str(CACHE_DIR),
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=60)
    except Exception:
        pass


def ssh_call(subcmd: str, stdin_data: str | None = None, timeout: int = 60) -> dict:
    cmd = SSH_BASE + [f"python3 {SERVER_API} {subcmd}"]
    try:
        p = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        out = (p.stdout or "").strip()
        if not out:
            return {"ok": False, "error": f"无输出；stderr={((p.stderr or '')[:300])}"}
        # 取最后一个 JSON 行
        for line in reversed(out.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                return json.loads(line)
        return {"ok": False, "error": f"非 JSON 输出: {out[:300]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "SSH 调用超时"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------- AstrBot 聊天（走隧道） ----------------

def astrbot_login() -> str | None:
    body = json.dumps({"username": "astrbot", "password": "change-me-panel"}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:6185/api/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode()).get("data", {}).get("token")


def astrbot_chat(message: str) -> dict:
    try:
        jwt = astrbot_login()
    except Exception as exc:
        return {"ok": False, "error": f"AstrBot 面板连不上（隧道没开？）: {exc}"}
    if not jwt:
        return {"ok": False, "error": "AstrBot 登录失败"}

    # 新建 webchat 会话
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:6185/api/v1/chat/sessions/new?platform_id=webchat",
            headers={"Authorization": f"Bearer {jwt}"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            sid = json.loads(r.read().decode())["data"]["session_id"]
    except Exception as exc:
        return {"ok": False, "error": f"创建会话失败: {exc}"}

    # 发消息（SSE 流式）
    body = json.dumps({"message": message, "session_id": sid}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:6185/api/v1/chat",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {jwt}"},
        method="POST",
    )
    parts: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                try:
                    evt = json.loads(payload)
                except Exception:
                    continue
                if evt.get("type") == "plain" and evt.get("data"):
                    parts.append(str(evt["data"]))
                elif evt.get("type") == "complete":
                    break
    except Exception as exc:
        return {"ok": False, "error": f"对话失败: {exc}"}
    return {"ok": True, "reply": "".join(parts) or "（模型没有返回文本）"}


# ---------------- HTTP ----------------

class Handler(BaseHTTPRequestHandler):
    server_version = "DafeiyuConsole/1.0"

    def log_message(self, fmt, *args):  # 安静
        pass

    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path in ("/", "/index.html"):
                html = (HERE / "index.html").read_bytes()
                self._send(200, html, "text/html; charset=utf-8")
                return
            if path.startswith("/cache/stickers/"):
                from urllib.parse import unquote
                name = os.path.basename(unquote(path.split("/", 3)[-1]))
                f = CACHE_DIR / name
                if f.is_file():
                    ext = f.suffix.lower().lstrip(".")
                    ctype = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                             "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp"}.get(ext, "application/octet-stream")
                    self._send(200, f.read_bytes(), ctype)
                else:
                    self._send(404, b"not found", "text/plain")
                return
            if path == "/api/overview":
                global _status_cache
                now = time.time()
                if _status_cache and now - _status_cache[0] < 6:
                    self._json(_status_cache[1])
                    return
                data = ssh_call("status", timeout=45)
                _status_cache = (now, data)
                self._json(data)
                return
            if path == "/api/balance":
                self._json(ssh_call("balance", timeout=40))
                return
            if path == "/api/qq_cookie":
                self._json(ssh_call("cookie", timeout=40))
                return
            if path == "/api/stickers":
                d = ssh_call("stickers", timeout=40)
                if d.get("ok"):
                    sync_stickers()
                self._json(d)
                return
            if path == "/api/logs":
                self._json(ssh_call("logs 120", timeout=45))
                return
            self._json({"ok": False, "error": "not found"}, 404)
        except Exception as exc:
            self._json({"ok": False, "error": str(exc)}, 500)

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            body = self._body()
            if path == "/api/chat":
                msg = str(body.get("message") or "").strip()
                if not msg:
                    self._json({"ok": False, "error": "消息为空"})
                    return
                self._json(astrbot_chat(msg))
                return
            if path == "/api/rules":
                payload = body.get("rules") or {}
                self._json(ssh_call("save_rules", json.dumps(payload, ensure_ascii=False), timeout=40))
                return
            if path == "/api/upload":
                name = os.path.basename(str(body.get("name") or ""))
                data_b64 = str(body.get("data_b64") or "")
                if not name or not data_b64:
                    self._json({"ok": False, "error": "缺少文件名或数据"})
                    return
                payload = json.dumps({"name": name, "data_b64": data_b64})
                self._json(ssh_call("upload", payload, timeout=120))
                return
            if path == "/api/delete_sticker":
                payload = json.dumps({"name": body.get("name") or ""})
                self._json(ssh_call("delete_sticker", payload, timeout=40))
                return
            if path == "/api/test_rule":
                payload = json.dumps({"text": str(body.get("text") or "")})
                self._json(ssh_call("test_rule", payload, timeout=40))
                return
            if path == "/api/restart":
                target = str(body.get("target") or "")
                self._json(ssh_call(f"restart {target}", timeout=120))
                return
            self._json({"ok": False, "error": "not found"}, 404)
        except Exception as exc:
            self._json({"ok": False, "error": str(exc)}, 500)


def main():
    if not KEY.exists():
        print(f"[!] 找不到 SSH 密钥: {KEY}")
        sys.exit(1)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("=" * 56)
    print("  大肥鱼控制台已启动")
    print(f"  打开浏览器访问: http://127.0.0.1:{PORT}")
    print("  按 Ctrl+C 停止")
    print("=" * 56)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
