"""Agent 层：真实 Claude 调用 + 无 key 时的数据驱动桩。

- 有 ANTHROPIC_API_KEY：为每个 agent 加载它自己的 system prompt（teams/*/agents/*.md），
  传结构化输入，解析其契约 JSON。
- 无 key：走 stub_*，用 TM/术语库数据产出确定性响应，用于验证编排 wiring。

注意：constraint-validator / terminology-checker / verdict-aggregator 属于程序化护栏，
不在本文件里走 LLM，见 data.py。
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from pathlib import Path

from data import RTL_LANGS, HIGH_RISK_CONTROLS
from tracing import traceable

BASE = Path(__file__).resolve().parent
TEAMS = BASE.parent / "teams"


def _load_dotenv():
    """加载本目录下 .env（形如 ANTHROPIC_API_KEY=sk-...），无需额外依赖。"""
    p = BASE / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

_AGENT_FILES = {
    "source-copy-reviewer": "ux-writer/agents/source-copy-reviewer.md",
    "en-copywriter": "ux-writer/agents/en-copywriter.md",
    "multilingual-localizer": "ux-writer/agents/multilingual-localizer.md",
    "native-linguistic-reviewer": "reviewer/agents/native-linguistic-reviewer.md",
    "cultural-compliance-checker": "reviewer/agents/cultural-compliance-checker.md",
    "visual-context-checker": "reviewer/agents/visual-context-checker.md",
}


def load_system_prompt(name):
    text = (TEAMS / _AGENT_FILES[name]).read_text(encoding="utf-8")
    if text.startswith("---"):  # 去掉 YAML frontmatter
        text = text.split("---", 2)[2]
    return text.strip()


# ---------- LLM 客户端 ----------
_llm = None
_llm_init = False
_llm_label = "STUB"


def get_llm():
    """按可用的 key 选择 provider（可用 LLM_PROVIDER 显式指定）：

    - ANTHROPIC_API_KEY → Claude(ChatAnthropic)，模型 ANTHROPIC_MODEL(默认 claude-sonnet-5)
    - OPENAI_API_KEY    → ChatOpenAI，模型 OPENAI_MODEL，base_url OPENAI_BASE_URL
      OpenAI 兼容端点(DeepSeek/Kimi/通义千问兼容模式/智谱等)都走这一支，只需改 base_url + model
    - 都没有 → None(桩模式)
    """
    global _llm, _llm_init, _llm_label
    if _llm_init:
        return _llm
    _llm_init = True
    provider = os.getenv("LLM_PROVIDER", "").lower()
    try:
        use_anthropic = provider == "anthropic" or (not provider and os.getenv("ANTHROPIC_API_KEY"))
        use_openai = provider in {"openai", "openai-compatible", "deepseek", "kimi", "moonshot",
                                  "qwen", "dashscope", "zhipu", "glm"} or \
            (not provider and os.getenv("OPENAI_API_KEY"))
        if use_anthropic:
            from langchain_anthropic import ChatAnthropic
            model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
            _llm = ChatAnthropic(model=model, temperature=0, max_tokens=1024)
            _llm_label = f"anthropic · {model}"
        elif use_openai:
            from langchain_openai import ChatOpenAI
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            kwargs = dict(model=model, temperature=0, max_tokens=1024,
                          api_key=os.getenv("OPENAI_API_KEY"))
            base = os.getenv("OPENAI_BASE_URL")
            if base:
                kwargs["base_url"] = base
            _llm = ChatOpenAI(**kwargs)
            _llm_label = f"openai-compat · {model}" + (f" @ {base}" if base else "")
        else:
            _llm = None
    except Exception as e:  # 缺包/初始化失败 → 回退桩
        print(f"[warn] LLM 初始化失败，回退桩模式: {e}")
        _llm = None
    return _llm


def use_llm():
    return get_llm() is not None


def llm_label():
    get_llm()
    return _llm_label


def _extract_json(text):
    if not isinstance(text, str):
        text = str(text)
    m = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, re.S)
    raw = m.group(1) if m else text
    if not m:
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e != -1:
            raw = raw[s:e + 1]
    return json.loads(raw)


def _image_content_block(image_path):
    """把本地图片读成多模态 image_url 块；找不到就返回 None（不阻断流程）。

    path 可为绝对路径，或相对 langgraph_impl / localization-agents / data 目录。
    """
    candidates = [Path(image_path), BASE / image_path,
                  BASE.parent / image_path, BASE.parent / "data" / image_path]
    p = next((c for c in candidates if c.exists()), None)
    if not p:
        return None
    mime = mimetypes.guess_type(str(p))[0] or "image/png"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


@traceable(run_type="chain", name="agent")
def call_agent(name, user_payload, image_path=None):
    """接真实模型：system prompt = 该 agent 的 .md，user = 结构化输入（+可选 UI 截图）。"""
    from langchain_core.messages import SystemMessage, HumanMessage
    llm = get_llm()
    sys = load_system_prompt(name)
    payload = json.dumps(user_payload, ensure_ascii=False, indent=2)
    text = f"输入(JSON)：\n{payload}\n\n严格只输出你契约要求的 JSON。"
    human_content = text
    if image_path:
        block = _image_content_block(image_path)
        if block:  # 找不到图片时静默跳过，仍按纯文本跑
            human_content = [
                {"type": "text", "text": "以下是该文案所在的 UI 截图，请结合界面语境理解后再作答："},
                block,
                {"type": "text", "text": text},
            ]
    resp = llm.invoke([SystemMessage(content=sys), HumanMessage(content=human_content)])
    return _extract_json(resp.content)


# ---------- 桩（无 key 时）----------
@traceable(run_type="tool", name="stub:source-copy-reviewer")
def stub_source_review(item, refs):
    # demo 数据源文清晰，无阻断问题；真实场景由 LLM 判定歧义/不可译。
    return {"verdict": "ok", "blocking": False, "issues": []}


@traceable(run_type="tool", name="stub:en-copywriter")
def stub_en_copywriter(item, refs):
    hit = refs.tm_lookup(item["key"], "en")
    if hit:
        return {"en_copy": hit["translation"], "shorter_alt": None,
                "rationale": "TM 命中 approved 英文", "risks": []}
    return {"en_copy": f"[stub-EN] {item['zh']}", "shorter_alt": None,
            "rationale": "stub 占位，接入 Claude 后由 en-copywriter 创译", "risks": ["需确认"]}


@traceable(run_type="tool", name="stub:multilingual-localizer")
def stub_localizer(item, lang, en_copy, refs):
    rtl = lang in RTL_LANGS
    hit = refs.tm_lookup(item["key"], lang)
    if hit:
        return {"lang": lang, "translation": hit["translation"], "gloss": en_copy,
                "note": "TM 命中(approved)", "rtl": rtl, "risks": []}
    g = refs.glossary_row_for_zh(item["zh"])
    if g and g.get(lang):
        return {"lang": lang, "translation": g[lang], "gloss": g.get("term_en", ""),
                "note": "术语库固定译法", "rtl": rtl, "risks": []}
    return {"lang": lang, "translation": en_copy, "gloss": "[stub] = English SoT",
            "note": "stub 回退，接入 Claude 后由 localizer 创译", "rtl": rtl, "risks": ["需确认"]}


@traceable(run_type="tool", name="stub:native-linguistic-reviewer")
def stub_native_linguistic(item, lang, tr):
    return {"lang": lang, "dimension": "linguistic", "pass": True, "score": 5, "issues": []}


@traceable(run_type="tool", name="stub:cultural-compliance-checker")
def stub_cultural(item, lang, tr):
    issues = []
    if item.get("control") in HIGH_RISK_CONTROLS:
        issues.append({"severity": "minor",
                       "desc": f"{item['control']} 属高风险，需人工文化/合规终审",
                       "suggestion": "人工 signoff", "needs_human": True})
    return {"lang": lang, "dimension": "cultural", "pass": True, "issues": issues}


@traceable(run_type="tool", name="stub:visual-context-checker")
def stub_visual(item, lang, tr):
    issues = []
    limit = item.get("char_limit_en") if lang == "en" else None
    if limit and "plural" not in tr and len(tr) > limit:
        issues.append({"severity": "major",
                       "desc": f"{lang} 译文 {len(tr)} 字符超控件上限 {limit}，将被截断",
                       "suggestion": "改用更短表达或缩写"})
    return {"lang": lang, "dimension": "visual", "pass": not issues, "issues": issues}
