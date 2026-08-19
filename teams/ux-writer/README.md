# Team A · UX Writer 团队

对应原流程 ② :**审校中文文案 + 撰写英文文案 + 英译多**。
把原本 1 周的人工产出,压缩为「AI 出初稿(分钟级) + 人工终审」。

## 团队编制

| Agent | 职责(单一) | 权限(tools) | 依赖 Skill |
|---|---|---|---|
| `ux-writer-lead` | 编排:拆解需求、按序分派、汇总产物、决定是否需人工 | Read, Task | — |
| `source-copy-reviewer` | 只审**中文源文**:歧义、不可译、不一致、缺 context | Read | glossary-and-tm |
| `en-copywriter` | 撰写**英文文案**(作为多语言的 source of truth) | Read | transcreation-guide, glossary-and-tm |
| `multilingual-localizer` | 逐目标语言**创译**(可并行 fan-out) | Read | transcreation-guide, glossary-and-tm, localization-constraints |
| `constraint-validator` | 机械校验:长度/占位符/复数/RTL,不做语义判断 | Read | localization-constraints |

## 编排顺序

```
source-copy-reviewer(审中文)
   └─(若中文有阻断性问题 → 回 PM,不继续)
en-copywriter(写英文)
   └─ multilingual-localizer × N 语言(并行)
        └─ constraint-validator(逐条校验)
ux-writer-lead 汇总 → 输出统一 JSON → 人工 Signoff
```

## 团队级输出契约

```json
{
  "key": "sku.button.sold_out",
  "source_review": {"verdict": "ok|needs_fix", "issues": ["..."]},
  "en_copy": "Sold Out",
  "results": [
    {"lang":"ja","translation":"完売","gloss":"回译","note":"译者注",
     "risks":["超长 6/5"],"needs_human": false}
  ],
  "escalate_to_human": ["ar"]   // 需人工终审的语言/条目
}
```

## 设计要点

- **source-of-truth 分层**:先定稿英文,再由英文派生多语言,保证一致(与原流程"英译多"一致)。
- **并行**:各目标语言互不依赖,`multilingual-localizer` 按语言 fan-out。
- **不硬猜**:任何 agent 不确定时,写入 `risks: ["需确认"]` 并置 `needs_human: true`,交人工。
