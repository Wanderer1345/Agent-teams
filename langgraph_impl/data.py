"""参考数据加载 + 程序化护栏。

这些是 PRODUCT-PLAN §5 里 R4「程序化护栏：长度/占位符/复数用代码校验，不信 LLM 自评」
对应的确定性逻辑。无论是否接真实 Claude，这一层都由代码执行。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from tracing import traceable

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data"

RTL_LANGS = {"ar", "he", "fa", "ur"}
HIGH_RISK_CONTROLS = {"营销 Banner", "法务", "支付", "隐私"}


# ---------- 数据加载 ----------
def load_glossary(path=None):
    path = Path(path) if path else DATA_DIR / "glossary.csv"
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_tm(path=None):
    path = Path(path) if path else DATA_DIR / "tm.jsonl"
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_submission(path=None):
    path = Path(path) if path else DATA_DIR / "sample_submission.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Refs:
    """术语库 + 翻译记忆的只读访问封装。"""

    def __init__(self, glossary, tm):
        self.glossary = glossary
        self.tm = tm

    def tm_lookup(self, key, lang, status="approved"):
        for r in self.tm:
            if r.get("key") == key and r.get("lang") == lang and r.get("status") == status:
                return r
        return None

    def glossary_row_for_zh(self, zh):
        for r in self.glossary:
            if r.get("term_zh") == zh:
                return r
        return None

    def do_not_translate(self):
        return [r for r in self.glossary if str(r.get("do_not_translate", "")).lower() == "true"]

    def tm_for_key(self, key, status="approved"):
        return [r for r in self.tm if r.get("key") == key and r.get("status") == status]

    def relevant_glossary(self, zh):
        """源文中出现的术语行 + 所有不可翻译品牌词（喂给 LLM 用）。"""
        hits = [r for r in self.glossary if r.get("term_zh") and r["term_zh"] in zh]
        dnt = [r for r in self.do_not_translate() if r not in hits]
        return hits + dnt


def load_refs():
    return Refs(load_glossary(), load_tm())


# ---------- 程序化护栏 ----------
def _limit_for(item, lang):
    # 数据里只有英文字符上限；其他语言无 per-lang 上限。
    return item.get("char_limit_en") if lang == "en" else None


def _is_icu(text):
    return "{" in text and "plural" in text


@traceable(run_type="tool", name="constraint-validator")
def constraint_validate(item, lang, translation, rtl):
    """constraint-validator：长度 / 占位符 / RTL 机械校验（纯代码，客观可判定）。"""
    violations = []
    limit = _limit_for(item, lang)
    if limit is not None and not _is_icu(translation) and len(translation) > limit:
        violations.append(f"超长 {len(translation)}/{limit}")

    for var in item.get("vars", []):
        token = var.strip("{}%0123456789")  # {count} -> count
        present = (var in translation) or (token and token in translation)
        if not present:
            violations.append(f"占位符丢失 {var}")

    if lang in RTL_LANGS and not rtl:
        violations.append("RTL 标记缺失")

    if translation != translation.strip():
        violations.append("首尾多余空格")

    return {"lang": lang, "passed": not violations, "violations": violations}


@traceable(run_type="tool", name="terminology-checker")
def terminology_check(refs: Refs, item, lang, translation):
    """terminology-consistency-checker：do_not_translate 保留 + TM 一致性（程序化）。"""
    issues = []
    for r in refs.do_not_translate():
        term = r.get("term_zh", "")
        if term and term in item.get("zh", "") and term not in translation:
            issues.append({
                "severity": "major", "term": term,
                "expected": term, "actual": "(missing)",
                "desc": "不可翻译品牌词未原样保留",
            })
    hit = refs.tm_lookup(item["key"], lang)
    if hit and translation != hit["translation"]:
        issues.append({
            "severity": "minor", "term": item["key"],
            "expected": hit["translation"], "actual": translation,
            "desc": "与 TM approved 历史译法不同，请确认是否有意改写（TM 为杠杆，非硬性）",
        })
    # 只有 major（品牌词等硬规则）才判失败；minor（TM 差异）仅提示。
    major = [i for i in issues if i.get("severity") == "major"]
    return {"lang": lang, "dimension": "terminology", "pass": not major, "issues": issues}


_SEV = {"blocker": 3, "major": 2, "minor": 1}


@traceable(run_type="tool", name="verdict-aggregator")
def aggregate_verdict(key, per_lang_reviews):
    """verdict-aggregator：四维(+约束) → 终裁 + 路由 + 回流候选（程序化终裁）。

    per_lang_reviews: {lang: {"translation": str, "dims": [dim_result, ...],
                              "needs_human_a": bool}}
    - dims 含 Team B 四维 + Team A 的 constraint 结果，任一 fail → 整条 fail。
    - Team A 已标 needs_human（如 "需确认" 或高风险控件）会并入 escalate_human，
      待人工确认的不进 approved_for_tm。
    """
    reviews = []
    approved = []
    for lang, bundle in per_lang_reviews.items():
        dims = bundle["dims"]
        fail = any(not d.get("pass", True) for d in dims)
        needs_human = bool(bundle.get("needs_human_a"))
        top_sev = None
        issues = []
        for d in dims:
            for it in d.get("issues", []):
                issues.append({
                    "dimension": d["dimension"],
                    "severity": it.get("severity"),
                    "desc": it.get("desc", ""),
                    "suggestion": it.get("suggestion", ""),
                })
                if it.get("needs_human"):
                    needs_human = True
                s = it.get("severity")
                if s and (top_sev is None or _SEV.get(s, 0) > _SEV.get(top_sev, 0)):
                    top_sev = s

        verdict = "fail" if fail else "pass"
        # 简化路由：失败默认回该语言 localizer；完整根因分类见 issue-taxonomy skill。
        route = "back_to_localizer" if fail else "approved"
        escalate_human = needs_human or top_sev == "blocker"
        reviews.append({
            "lang": lang, "verdict": verdict, "severity": top_sev,
            "route": route, "escalate_human": escalate_human, "issues": issues,
        })
        if verdict == "pass" and not escalate_human:
            approved.append({"lang": lang, "translation": bundle["translation"]})

    return {"key": key, "reviews": reviews, "approved_for_tm": approved}
