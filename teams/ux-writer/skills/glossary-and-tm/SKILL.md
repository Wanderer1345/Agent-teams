---
name: glossary-and-tm
description: 本地化术语库(Glossary/TermBase)与翻译记忆(Translation Memory)的查询与使用规范。当撰写或审校任何语言文案、需要固定专名译法或复用历史译文时使用。
---

# 术语库 + 翻译记忆 Skill

保证**跨文案、跨语言的一致性**,并复用已确认的历史译文。UX Writer 团队与审校团队共享同一份数据。

## 一、术语库(Glossary / TermBase)

固定的专有名词译法,**任何 agent 必须优先使用,不得自创**。

数据文件建议:`data/glossary.csv`,列:
```
term_zh, term_en, lang_ja, lang_ko, ..., domain, note, do_not_translate
笔记, Note, ノート, 노트, ..., content, 平台核心内容单元, false
薯队长, Captain, ..., ..., brand, 品牌 IP,音译需人工确认, false
XHS, XHS, XHS, XHS, ..., brand, 品牌缩写不翻译, true
```

使用规则:
1. 命中 `term_zh` → 目标语言直接用对应列;`do_not_translate=true` 的词原样保留。
2. 未登记的疑似新功能名/品牌词 → **不要自创译法**,标 `需确认` 交人工登记。
3. 术语冲突(同词多译)→ 报给编排者,不静默选一个。

## 二、翻译记忆(Translation Memory, TM)

历史"源文 → 已确认译文"对,用于复用与一致性。

数据文件建议:`data/tm.jsonl`,每行:
```json
{"key":"sku.button.sold_out","zh":"已抢光","lang":"ja","translation":"完売","status":"approved","approved_at":"2026-07-01","approved_by":"native-tester-ja"}
```

使用规则(匹配优先级):
1. **精确匹配**(同 `zh` + 同 `lang` + `status:approved`)→ 直接复用,风险最低。
2. **模糊匹配**(相似源文,如仅变量不同)→ 作为强参考,微调后使用,并说明改动。
3. 无匹配 → 正常创译,产出后经审校 approved 再回流写入 TM(见 `feedback-loop` skill)。

## 三、注意
- 术语库/TM 是"活资产":审校团队的 approved 结论会持续回流,越用越准。
- 只有 `status:approved` 的条目可被复用;`rejected`/`pending` 不得直接使用。
