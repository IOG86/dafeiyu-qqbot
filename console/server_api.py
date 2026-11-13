#!/usr/bin/env python3
"""服务器侧辅助接口：由本机控制台通过 SSH 调用，输出 JSON。"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

DATA_DIR = Path("/opt/qqbot/astrbot/data/dafeiyu_console")
STICKER_DIR = DATA_DIR / "stickers"
RULES_PATH = DATA_DIR / "rules.json"
ASTRBOT_CFG = Path("/opt/qqbot/astrbot/data/cmd_config.json")
ONEBOT_CFG = Path("/opt/qqbot/snowluma/data/config/onebot.json")
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

DEFAULT_RULES = {
    "enabled": True,
    "random_probability": 0.15,
    "rules": [],
}


def run(cmd: list[str], timeout: int = 20) -> str:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return f"ERR: {exc}"


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def astrbot_jwt() -> str | None:
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:6185/api/auth/login",
            data=json.dumps({"username": "astrbot", "password": "change-me-panel"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode()).get("data", {}).get("token")
    except Exception:
        return None


def onebot_token() -> str | None:
    cfg = read_json(ONEBOT_CFG, {})
    try:
        return cfg["networks"]["httpServers"][0]["accessToken"]
    except Exception:
        return None


def deepseek_key() -> str | None:
    cfg = read_json(ASTRBOT_CFG, {}) or {}
    # 1) provider 条目自带 key
    for p in (cfg.get("provider") or []):
        keys = p.get("key") or []
        if isinstance(keys, list) and keys:
            return str(keys[0])
    # 2) provider -> provider_source_id -> provider_sources[].key（AstrBot 4.29 的归一化结构）
    sources = {str(s.get("id")): s for s in (cfg.get("provider_sources") or []) if isinstance(s, dict)}
    for p in (cfg.get("provider") or []):
        src = sources.get(str(p.get("provider_source_id") or ""))
        if src:
            keys = src.get("key") or []
            if isinstance(keys, list) and keys:
                return str(keys[0])
    # 3) 任意一个带 key 的 source
    for s in (cfg.get("provider_sources") or []):
        keys = (s or {}).get("key") or []
        if isinstance(keys, list) and keys:
            return str(keys[0])
    return None


# ---------------- commands ----------------

def cmd_status():
    out = {}

    # 容器
    ps = run(["docker", "ps", "--format", "{{.Names}}|{{.Status}}"])
    containers = []
    for line in ps.strip().splitlines():
        if "|" in line:
            n, s = line.split("|", 1)
            containers.append({"name": n, "status": s})
    out["containers"] = containers

    # QQ / OneBot
    tok = onebot_token()
    qq = {"online": False, "nickname": "", "user_id": ""}
    if tok:
        r = run(["docker", "exec", "snowluma", "curl", "-sS", "-m", "6",
                 "-H", f"Authorization: Bearer {tok}",
                 "http://127.0.0.1:3000/get_status"])
        try:
            d = json.loads(r[r.index("{"):]).get("data") or {}
            qq["online"] = bool(d.get("online"))
        except Exception:
            pass
        r = run(["docker", "exec", "snowluma", "curl", "-sS", "-m", "6",
                 "-H", f"Authorization: Bearer {tok}",
                 "http://127.0.0.1:3000/get_login_info"])
        try:
            d = json.loads(r[r.index("{"):]).get("data") or {}
            qq["nickname"] = d.get("nickname", "")
            qq["user_id"] = str(d.get("user_id", ""))
        except Exception:
            pass
    out["qq"] = qq

    # 资源
    try:
        mem = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            mem[k] = int(v.strip().split()[0])
        out["memory"] = {
            "total_mb": round(mem["MemTotal"] / 1024),
            "available_mb": round(mem["MemAvailable"] / 1024),
            "used_mb": round((mem["MemTotal"] - mem["MemAvailable"]) / 1024),
            "swap_used_mb": round((mem["SwapTotal"] - mem["SwapFree"]) / 1024),
        }
    except Exception:
        out["memory"] = {}

    io_full = 0.0
    try:
        for line in Path("/proc/pressure/io").read_text().splitlines():
            if line.startswith("full"):
                m = re.search(r"avg10=([\d.]+)", line)
                if m:
                    io_full = float(m.group(1))
    except Exception:
        pass
    out["io_full_avg10"] = io_full

    try:
        up = float(Path("/proc/uptime").read_text().split()[0])
        out["uptime_hours"] = round(up / 3600, 1)
    except Exception:
        out["uptime_hours"] = 0

    try:
        st = os.statvfs("/")
        out["disk"] = {
            "total_gb": round(st.f_blocks * st.f_frsize / 1e9, 1),
            "free_gb": round(st.f_bavail * st.f_frsize / 1e9, 1),
        }
    except Exception:
        out["disk"] = {}

    # AstrBot 插件
    jwt = astrbot_jwt()
    out["plugins"] = []
    if jwt:
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:6185/api/v1/plugins",
                headers={"Authorization": f"Bearer {jwt}"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                for p in json.loads(r.read().decode()).get("data") or []:
                    out["plugins"].append({
                        "name": p.get("name"),
                        "version": p.get("version"),
                        "activated": p.get("activated"),
                    })
        except Exception:
            pass

    # 视觉模型（用于看懂图片/表情包）
    cfg = read_json(ASTRBOT_CFG, {}) or {}
    cap_id = (cfg.get("provider_settings") or {}).get("default_image_caption_provider_id") or ""
    provider_ids = [str(p.get("id")) for p in (cfg.get("provider") or []) if p.get("id")]
    out["vision"] = {
        "caption_provider_id": cap_id,
        "providers": provider_ids,
        "ready": bool(cap_id),
    }

    out["ok"] = True
    out["ts"] = int(time.time())
    return out


def cmd_balance():
    key = deepseek_key()
    if not key:
        return {"ok": False, "error": "服务器上没找到 DeepSeek Key"}
    try:
        req = urllib.request.Request(
            "https://api.deepseek.com/user/balance",
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode())
        infos = d.get("balance_infos") or []
        info = infos[0] if infos else {}
        return {
            "ok": True,
            "available": d.get("is_available"),
            "currency": info.get("currency", ""),
            "total": info.get("total_balance", ""),
            "granted": info.get("granted_balance", ""),
            "topped_up": info.get("topped_up_balance", ""),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _load_rules():
    r = read_json(RULES_PATH, None)
    if not isinstance(r, dict):
        r = dict(DEFAULT_RULES)
    r.setdefault("enabled", True)
    r.setdefault("random_probability", 0.15)
    r.setdefault("rules", [])
    return r


def cmd_stickers():
    STICKER_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(STICKER_DIR.glob("*")):
        if f.suffix.lower() in IMG_EXT and not f.name.startswith("_"):
            files.append({"name": f.name, "size": f.stat().st_size})
    return {"ok": True, "rules": _load_rules(), "stickers": files}


def cmd_save_rules():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception as exc:
        return {"ok": False, "error": f"JSON 解析失败: {exc}"}
    if not isinstance(data, dict):
        return {"ok": False, "error": "规则必须是对象"}
    data.setdefault("enabled", True)
    data.setdefault("random_probability", 0.15)
    data.setdefault("rules", [])
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


def cmd_upload():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
        name = os.path.basename(data["name"])
        blob = base64.b64decode(data["data_b64"])
    except Exception as exc:
        return {"ok": False, "error": f"参数错误: {exc}"}
    ext = Path(name).suffix.lower()
    if ext not in IMG_EXT:
        return {"ok": False, "error": f"不支持的图片格式: {ext}"}
    if len(blob) > 8 * 1024 * 1024:
        return {"ok": False, "error": "图片超过 8MB"}
    STICKER_DIR.mkdir(parents=True, exist_ok=True)
    (STICKER_DIR / name).write_bytes(blob)
    return {"ok": True, "name": name, "size": len(blob)}


def cmd_delete_sticker():
    raw = sys.stdin.read()
    try:
        name = os.path.basename(json.loads(raw)["name"])
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    p = STICKER_DIR / name
    if p.exists():
        p.unlink()
    return {"ok": True}


def cmd_test_rule():
    """测试一句话会命中哪些表情规则（dry-run，不会真发消息）。"""
    raw = sys.stdin.read()
    try:
        text = str(json.loads(raw).get("text") or "")
    except Exception:
        text = ""
    rules = _load_rules()
    hits = []
    for r in rules.get("rules", []):
        kw = str(r.get("keyword") or "").strip()
        if kw and kw in text:
            hits.append({"keyword": kw, "sticker": r.get("sticker")})
    return {
        "ok": True,
        "text": text,
        "enabled": rules.get("enabled", True),
        "random_probability": rules.get("random_probability", 0),
        "hits": hits,
    }


def cmd_cookie():
    """通过 SnowLuma 的 OneBot API 获取 QQ Cookie / csrf token。"""
    tok = onebot_token()
    if not tok:
        return {"ok": False, "error": "找不到 OneBot token"}
    domain = (sys.argv[2] if len(sys.argv) > 2 else "qzone.qq.com") or "qzone.qq.com"

    def call(action: str, body: dict | None = None) -> dict:
        if body is None:
            cmd = ["docker", "exec", "snowluma", "curl", "-sS", "-m", "10",
                   "-H", f"Authorization: Bearer {tok}",
                   f"http://127.0.0.1:3000/{action}"]
        else:
            cmd = ["docker", "exec", "snowluma", "curl", "-sS", "-m", "10",
                   "-X", "POST", "-H", f"Authorization: Bearer {tok}",
                   "-H", "Content-Type: application/json",
                   "-d", json.dumps(body),
                   f"http://127.0.0.1:3000/{action}"]
        raw = run(cmd)
        try:
            return json.loads(raw[raw.index("{"):])
        except Exception:
            return {"status": "failed", "error": raw[:200]}

    c = call("get_cookies", {"domain": domain})
    csrf = call("get_csrf_token")
    cred = call("get_credentials", {"domain": domain})
    cookies = (c.get("data") or {}).get("cookies") or (cred.get("data") or {}).get("cookies") or ""
    csrf_token = (csrf.get("data") or {}).get("token", "")
    bkn = ""
    try:
        # bkn 通常由 skey 计算，这里附带原样返回的 csrf token
        bkn = str(csrf_token)
    except Exception:
        pass
    if not cookies:
        return {"ok": False, "error": "OneBot 没有返回 cookie（QQ 可能未登录）"}
    return {
        "ok": True,
        "domain": domain,
        "cookies": cookies,
        "csrf_token": csrf_token,
        "bkn": bkn,
        "cookie_count": len([x for x in cookies.split(";") if "=" in x]),
        "ts": int(time.time()),
    }


def cmd_restart():
    target = sys.argv[2] if len(sys.argv) > 2 else ""
    if target == "all":
        run(["docker", "restart", "astrbot", "snowluma"], timeout=90)
    elif target in ("astrbot", "snowluma"):
        run(["docker", "restart", target], timeout=90)
    else:
        return {"ok": False, "error": "未知目标"}
    return {"ok": True}


def cmd_logs():
    n = sys.argv[2] if len(sys.argv) > 2 else "100"
    out = run(["docker", "logs", "--tail", str(n), "astrbot"], timeout=25)
    return {"ok": True, "logs": out[-12000:]}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    handlers = {
        "status": cmd_status,
        "balance": cmd_balance,
        "stickers": cmd_stickers,
        "save_rules": cmd_save_rules,
        "upload": cmd_upload,
        "delete_sticker": cmd_delete_sticker,
        "test_rule": cmd_test_rule,
        "cookie": cmd_cookie,
        "restart": cmd_restart,
        "logs": cmd_logs,
    }
    fn = handlers.get(cmd)
    if not fn:
        print(json.dumps({"ok": False, "error": f"unknown command {cmd}"}))
        return
    try:
        print(json.dumps(fn(), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
