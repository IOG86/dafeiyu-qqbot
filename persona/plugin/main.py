"""人格包加载插件

目录结构（容器内）：
  /AstrBot/data/persona_pack/active.json          —— 装载配置
  /AstrBot/data/persona_pack/<pack>/persona.md    —— 身份/性格（也可直接作为 AstrBot 人格）
  /AstrBot/data/persona_pack/<pack>/expression-dna.md
  /AstrBot/data/persona_pack/<pack>/style-bank.md
  /AstrBot/data/persona_pack/<pack>/boundaries.md

行为：每次 LLM 请求前，把 include 里列出的文件（默认 expression-dna + boundaries）
+ 若干条台词样本追加进 system_prompt。改 md 文件后重载插件即可生效。
"""

from __future__ import annotations

import json
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.core import AstrBotConfig

BASE_DIR = Path("/AstrBot/data/persona_pack")
CONFIG_PATH = BASE_DIR / "active.json"
MARKER = "【人格包·"
DEBUG_LOG = Path("/tmp/persona_pack.log")


def _debug(msg: str) -> None:
    try:
        if DEBUG_LOG.exists() and DEBUG_LOG.stat().st_size > 200_000:
            DEBUG_LOG.write_text("", encoding="utf-8")
        with DEBUG_LOG.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


class PersonaPack(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.config = config
        self._cache: tuple[float, dict] | None = None

    def _load_config(self) -> dict:
        try:
            mtime = CONFIG_PATH.stat().st_mtime
            if not self._cache or self._cache[0] != mtime:
                self._cache = (mtime, json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
            return self._cache[1] or {}
        except Exception:
            return {}

    @staticmethod
    def _read(base: Path, name: str) -> str:
        try:
            return (base / name).read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    @staticmethod
    def _samples(base: Path, n: int) -> str:
        txt = PersonaPack._read(base, "style-bank.md")
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip().startswith("- ")]
        return "\n".join(lines[:n])

    @filter.on_llm_request(priority=-320000)
    async def inject_pack(self, event: AstrMessageEvent, req=None, *args, **kwargs):
        cfg = self._load_config()
        if not cfg.get("enabled", True) or req is None:
            return
        pack = str(cfg.get("pack") or "whale_girl")
        base = Path(str(cfg.get("base_dir") or BASE_DIR)) / pack
        cur = getattr(req, "system_prompt", "") or ""
        if MARKER in cur:
            return

        parts: list[str] = []
        for name in cfg.get("include") or ["expression-dna.md", "boundaries.md"]:
            body = self._read(base, str(name))
            if body:
                parts.append(f"{MARKER}{name}】\n{body}")

        n = int(cfg.get("style_samples") or 0)
        if n > 0:
            s = self._samples(base, n)
            if s:
                parts.append(f"{MARKER}台词样本】\n{s}")

        if not parts:
            return
        block = "\n\n" + "\n\n".join(parts)
        limit = int(cfg.get("max_chars") or 6000)
        if len(block) > limit:
            block = block[:limit]
        try:
            req.system_prompt = cur + block
            _debug(f"[inject] pack={pack} add={len(block)} total={len(req.system_prompt)}")
        except Exception as exc:
            _debug(f"[inject-fail] {exc}")
