# 本地化 Agent Teams 设计

将图中 **UX Writer**(②:审校中文 + 撰写英文 + 英译多)和 **海外母语 tester 走查**(⑦:审校/验证)两个环节,
拆成两个独立的 Agent Team。可直接在 Claude Code 中使用(`agents/*.md` + `skills/*/SKILL.md`)。

---

## Agent Teams 设计原则(本方案遵循)

1. **编排者-执行者(Orchestrator-Worker)**:每个团队有一个 `*-lead` 编排者,负责拆解任务、分派给专职子 agent、汇总结果,不亲自做具体翻译/审校。
2. **单一职责**:每个子 agent 只做一件事(如"只审中文"/"只查术语一致性"),`description` 写清楚触发场景,便于自动路由。
3. **最小权限**:每个 agent 只给它需要的 `tools`(审校类只读,写回类才给 Write)。
4. **结构化交接**:agent 之间用固定 JSON 契约传递,避免自然语言歧义(见各文件的"输出契约")。
5. **职责分离下的对抗式验证**:审校团队(Team B)与撰写团队(Team A)**完全独立**,审校者被要求"默认挑错",防止自我背书。
6. **能力沉淀为 Skill**:术语库、翻译记忆、约束规则、评分 rubric 等做成可复用 skill,两个团队共享同一套标准。
7. **人在环(HITL)**:高风险文案(营销/法务/支付/文化敏感)必须人工 Signoff;Agent 定位是提效不是无人化。
8. **可度量 + 反馈闭环**:审校结论回流进翻译记忆与术语库,让系统越用越准(对应图中⑦的问题回退路径)。
9. **可并行**:多语言之间相互独立,`multilingual-localizer` 与各语言审校可并行 fan-out。

---

## 两个团队与原流程的映射

| 原流程环节 | 对应 Team | 编排者 | 产出 |
|---|---|---|---|
| ② UX Writer:审校中文 + 撰写英文 + 英译多 | **Team A** | `ux-writer-lead` | 中文审校意见 + 英文文案 + 多语言初稿(带译者注/风险) |
| ⑦ 海外母语 tester 走查/验证 | **Team B** | `review-lead` | 逐语言裁定(通过/打回)+ 问题分类 + 回流数据 |

## 团队协作流(端到端)

```
PM 提交单(中文+PRD+UI图+字符限制+key)
        │
        ▼
┌─────────────── Team A · UX Writer ───────────────┐
│ ux-writer-lead 编排:                              │
│   source-copy-reviewer  → 审校中文,挑歧义/不可译     │
│   en-copywriter         → 撰写英文(source of truth)│
│   multilingual-localizer→ 逐语言创译(并行)         │
│   constraint-validator  → 长度/占位符/复数/RTL 校验  │
└──────────────────────┬───────────────────────────┘
                       │ 结构化产物(JSON)
                       ▼
                 人工 Signoff(PM) → 上传 Starling
                       │
                       ▼
┌─────────────── Team B · 审校 ────────────────────┐
│ review-lead 编排:                                 │
│   native-linguistic-reviewer   → 母语语言质量        │
│   terminology-consistency-checker → 术语一致性       │
│   cultural-compliance-checker  → 文化/合规/敏感      │
│   visual-context-checker       → UI 走查(截断/占位) │
│   verdict-aggregator           → 汇总裁定 + 分类问题  │
└──────────────────────┬───────────────────────────┘
                       │
        ┌──────────────┴───────────────┐
   中英文问题 → 回退 Team A          多语言问题 → 回退对应语言 localizer
        └──────────────┬───────────────┘
                       ▼
              verdict-aggregator 回流:
              通过项 → 写入翻译记忆(TM)+ 术语库(feedback-loop skill)
```

## 目录结构

```
teams/
  ux-writer/   # Team A
    agents/    ux-writer-lead / source-copy-reviewer / en-copywriter /
               multilingual-localizer / constraint-validator
    skills/    glossary-and-tm / transcreation-guide / localization-constraints
  reviewer/    # Team B
    agents/    review-lead / native-linguistic-reviewer /
               terminology-consistency-checker / cultural-compliance-checker /
               visual-context-checker / verdict-aggregator
    skills/    review-rubric / issue-taxonomy / feedback-loop
```

> 使用方式:将 `agents/` 下文件放入项目 `.claude/agents/`,`skills/` 下目录放入 `.claude/skills/`,
> 即可在 Claude Code 中通过 `@ux-writer-lead` / `@review-lead` 调用整条链路。
