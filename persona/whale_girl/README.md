# 人格包 · DeepSeek娘（鲸鱼娘）

> 一套可编辑、可替换的「人格工程」文件。改 `.md` 即改人格，不用动 AstrBot 面板。

## 四件套

| 文件 | 管什么 | 被谁读 |
|---|---|---|
| `persona.md` | **谁**：身份、形象、性格六条、关系、情绪仪表盘 | AstrBot 人格（system_prompt） |
| `expression-dna.md` | **怎么说**：称呼铁律、句长、语气词预算、动作规则、甜度 | 人格包插件注入 |
| `style-bank.md` | **长什么样**：台词库、验收 Q&A | 前 3 组作为 few-shot；另取 6 条台词注入 |
| `boundaries.md` | **不能做什么**：红线、拒绝方式、OOC 清单、优先级 | 人格包插件注入 |

## 部署位置

**服务器**（容器内挂载）：

```
/opt/qqbot/astrbot/data/persona_pack/
├── active.json                 # 装载配置
└── whale_girl/
    ├── persona.md
    ├── expression-dna.md
    ├── style-bank.md
    └── boundaries.md
```

对应的容器内路径：`/AstrBot/data/persona_pack/...`

插件：`astrbot_plugin_persona_pack`（容器内 `/AstrBot/data/plugins/`）

## active.json

```json
{
  "enabled": true,
  "pack": "whale_girl",
  "base_dir": "/AstrBot/data/persona_pack",
  "include": ["expression-dna.md", "boundaries.md"],
  "style_samples": 6,
  "max_chars": 6000
}
```

- `include`：要注入哪些文件（`persona.md` 单独由 AstrBot 人格承载，不重复注入）
- `style_samples`：从 style-bank 里取多少条台词
- `max_chars`：注入上限（防止提示词膨胀）

## 怎么改

1. 编辑本目录下的 `.md`
2. 上传到服务器对应路径（或直接改服务器上的文件）
3. **即时生效**：插件每次请求都会重读文件；`persona.md` 改动需同步到 AstrBot 人格（见下）

同步 persona.md 到 AstrBot 人格（面板改也可以）：

```bash
# 面板操作：AstrBot → 人格 → DeepSeek娘 → 粘贴 persona.md 内容 → 保存
```

## 换人格包

新建 `persona_pack/另一个包/`，放同名四个文件，把 `active.json` 的 `pack` 改成新目录名即可。

## 甜度调节

`expression-dna.md` 第 7 节：甜度 1（当助手）/ 2（默认）/ 3（浓度拉满）。
按需要把对应描述强调或删减即可。

## 验收标准

见 `style-bank.md` 的 L 节（Q&A 期望回答）；`boundaries.md` 第 5 节是不 OOC 清单。

## 成本说明

人格包注入约 2.4k 字符。DeepSeek 前缀缓存命中后（`input_cached`），实际增量成本可忽略。
实测单次请求：`input_cached≈9k, input_other≈1.4k, output≈20`。
