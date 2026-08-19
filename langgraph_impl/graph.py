"""LangGraph 编排：Team A（UX Writer）→ Team B（审校）端到端。

图结构：
    START → source_review →[阻断?]→ (abort→END)
                              └→ en_copy → localize → team_b_review → verdict → END

- Team A：源文审校 → 英文 SoT → 逐语言创译(localizer) + 程序化约束校验
- Team B：逐语言四维走查(语言/术语/文化/视觉) → 程序化终裁 + 路由 + 回流候选
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import StateGraph, START, END

import agents as A
import data as D


class LocState(TypedDict, total=False):
    item: dict
    refs: Any
    source_review: dict
    en_copy: dict
    results: list
    escalate_to_human: list
    team_a: dict
    reviews_by_lang: dict
    verdict: dict
    trace: Annotated[list, operator.add]  # 各节点返回的 trace 会被拼接


def _gloss_ctx(refs, item, lang=None):
    """喂给 LLM 的紧凑术语库切片：源文命中项 + 不可翻译词。"""
    out = []
    for r in refs.relevant_glossary(item["zh"]):
        d = {"zh": r["term_zh"], "en": r["term_en"], "do_not_translate": r.get("do_not_translate")}
        if lang and r.get(lang):
            d[lang] = r[lang]
        out.append(d)
    return out


def _tm_ctx(refs, item, lang=None):
    """喂给 LLM 的 TM 命中（approved）：该 key 的历史译法。"""
    hits = refs.tm_for_key(item["key"])
    if lang:
        hits = [h for h in hits if h["lang"] in (lang, "en")]
    return [{"lang": h["lang"], "translation": h["translation"]} for h in hits]


def _call(name, payload, stub_thunk, image_path=None):
    """真实模式调 LLM（可带 UI 截图）；失败(网络/JSON 解析)自动回退桩，保证 demo 不崩。

    返回 (result_dict, warn_or_None)。
    """
    if not A.use_llm():
        return stub_thunk(), None
    try:
        return A.call_agent(name, payload, image_path=image_path), None
    except Exception as e:
        return stub_thunk(), f"⚠ {name} 调用/解析失败，回退桩: {type(e).__name__}: {e}"


# ---------- Team A ----------
def node_source_review(state: LocState):
    item, refs = state["item"], state["refs"]
    out, warn = _call("source-copy-reviewer",
                      {"key": item["key"], "zh": item["zh"], "control": item["control"],
                       "scene": item["scene"], "vars": item.get("vars", [])},
                      lambda: A.stub_source_review(item, refs))
    logs = ([warn] if warn else []) + \
        [f"[A] source-copy-reviewer → verdict={out['verdict']} blocking={out.get('blocking')}"]
    return {"source_review": out, "trace": logs}


def gate_source(state: LocState):
    sr = state["source_review"]
    return "abort" if sr.get("verdict") == "needs_fix" and sr.get("blocking") else "continue"


def node_abort(state: LocState):
    return {"team_a": {"key": state["item"]["key"], "aborted": True,
                       "source_review": state["source_review"]},
            "trace": ["[A] 源文阻断性问题 → 停止，回退人工 PM"]}


def node_en_copy(state: LocState):
    item, refs = state["item"], state["refs"]
    out, warn = _call("en-copywriter",
                      {"key": item["key"], "zh": item["zh"], "control": item["control"],
                       "tone": item["tone"], "scene": item["scene"],
                       "char_limit_en": item.get("char_limit_en"), "vars": item.get("vars", []),
                       "glossary": _gloss_ctx(refs, item, "en"), "tm": _tm_ctx(refs, item, "en")},
                      lambda: A.stub_en_copywriter(item, refs),
                      image_path=item.get("ui_shot"))
    logs = ([warn] if warn else []) + \
        [f"[A] en-copywriter → en_copy=「{out['en_copy']}」 risks={out.get('risks')}"]
    return {"en_copy": out, "trace": logs}


def node_localize(state: LocState):
    item, refs = state["item"], state["refs"]
    en = state["en_copy"]["en_copy"]
    en_has_risk = bool(state["en_copy"].get("risks"))
    results, escalate, logs = [], [], []
    for lang in item["target_langs"]:
        loc, warn = _call("multilingual-localizer",
                          {"target_lang": lang, "en_copy": en, "zh": item["zh"],
                           "control": item["control"], "tone": item["tone"],
                           "scene": item["scene"], "char_limit_en": item.get("char_limit_en"),
                           "vars": item.get("vars", []),
                           "glossary": _gloss_ctx(refs, item, lang), "tm": _tm_ctx(refs, item, lang)},
                          lambda lang=lang: A.stub_localizer(item, lang, en, refs),
                          image_path=item.get("ui_shot"))
        loc.setdefault("rtl", lang in D.RTL_LANGS)
        if warn:
            logs.append(warn)

        cons = D.constraint_validate(item, lang, loc["translation"], loc.get("rtl", False))
        risks = list(loc.get("risks", [])) + ([] if cons["passed"] else cons["violations"])
        needs_human = ("需确认" in loc.get("risks", [])) or en_has_risk \
            or item.get("control") in D.HIGH_RISK_CONTROLS
        results.append({
            "lang": lang, "translation": loc["translation"], "gloss": loc.get("gloss", ""),
            "note": loc.get("note", ""), "rtl": loc.get("rtl", False),
            "constraint": cons, "risks": risks, "needs_human": needs_human,
        })
        if needs_human:
            escalate.append(lang)
        flag = "" if cons["passed"] else f" ⚠{cons['violations']}"
        hu = " 🙋" if needs_human else ""
        logs.append(f"[A] localizer[{lang}] → 「{loc['translation']}」{flag}{hu}")

    team_a = {"key": item["key"], "source_review": state["source_review"],
              "en_copy": en, "results": results, "escalate_to_human": escalate}
    return {"results": results, "escalate_to_human": escalate, "team_a": team_a, "trace": logs}


# ---------- Team B ----------
def node_team_b_review(state: LocState):
    item, refs = state["item"], state["refs"]
    by_lang, logs = {}, []
    for r in state["results"]:
        lang, tr = r["lang"], r["translation"]
        ling, w1 = _call("native-linguistic-reviewer",
                         {"lang": lang, "translation": tr, "gloss": r["gloss"], "zh": item["zh"]},
                         lambda lang=lang, tr=tr: A.stub_native_linguistic(item, lang, tr))
        cult, w2 = _call("cultural-compliance-checker",
                         {"lang": lang, "translation": tr, "scene": item["scene"],
                          "control": item["control"], "glossary": _gloss_ctx(refs, item, lang)},
                         lambda lang=lang, tr=tr: A.stub_cultural(item, lang, tr))
        vis, w3 = _call("visual-context-checker",
                        {"lang": lang, "translation": tr, "control": item["control"],
                         "char_limit_en": item.get("char_limit_en"), "vars": item.get("vars", [])},
                        lambda lang=lang, tr=tr: A.stub_visual(item, lang, tr),
                        image_path=item.get("ui_shot"))
        logs += [w for w in (w1, w2, w3) if w]
        term = D.terminology_check(refs, item, lang, tr)  # 程序化维度
        # 把 Team A 的约束校验结果作为一维并入，缺陷会体现在终裁里
        cons = r["constraint"]
        constraint_dim = {"dimension": "constraint", "pass": cons["passed"],
                          "issues": [{"severity": "major", "desc": v} for v in cons["violations"]]}
        by_lang[lang] = {"translation": tr,
                         "dims": [ling, term, cult, vis, constraint_dim],
                         "needs_human_a": r["needs_human"]}
        logs.append(f"[B] 四维+约束走查[{lang}] done")
    return {"reviews_by_lang": by_lang, "trace": logs}


def node_verdict(state: LocState):
    v = D.aggregate_verdict(state["item"]["key"], state["reviews_by_lang"])  # 程序化终裁
    passed = sum(1 for rv in v["reviews"] if rv["verdict"] == "pass")
    return {"verdict": v,
            "trace": [f"[B] verdict-aggregator → {passed}/{len(v['reviews'])} pass, 回流候选 {len(v['approved_for_tm'])}"]}


def build_graph():
    g = StateGraph(LocState)
    g.add_node("source_review", node_source_review)
    g.add_node("abort", node_abort)
    g.add_node("en_copy", node_en_copy)
    g.add_node("localize", node_localize)
    g.add_node("team_b_review", node_team_b_review)
    g.add_node("verdict", node_verdict)

    g.add_edge(START, "source_review")
    g.add_conditional_edges("source_review", gate_source,
                            {"abort": "abort", "continue": "en_copy"})
    g.add_edge("abort", END)
    g.add_edge("en_copy", "localize")
    g.add_edge("localize", "team_b_review")
    g.add_edge("team_b_review", "verdict")
    g.add_edge("verdict", END)
    return g.compile()
